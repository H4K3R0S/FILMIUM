# ========== TORRENT SERVIS ==========
# Poslovna logika modula: dodavanje pauziranog torrenta, čekanje metapodataka,
# štikliranje fajlova, odobrenje, praćenje i predaja uvozu po završetku.
#
# Ovaj modul NE zna za qBittorrent — radi isključivo kroz TorrentEngine.
from __future__ import annotations

import os
import threading
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from core.domains.filmium.reveal_path import open_folder
from core.domains.filmium.torrents.torrent_archive import TorrentArchive
from core.domains.filmium.torrents.torrent_engine import (
    TorrentEngine,
    TorrentEngineError,
)
from core.domains.filmium.torrents.torrent_errors import TorrentServiceError
from core.domains.filmium.torrents.torrent_file_reader import (
    TORRENT_EXTENSION,
    read_torrent_file,
    scan_folders,
)
from core.domains.filmium.torrents.torrent_models import (
    DiscoveredFile,
    DiscoveredTorrent,
    EngineHealth,
    TorrentEntry,
    TorrentFileEntry,
    TorrentProgress,
    TorrentSettings,
    TorrentStatus,
)
from core.domains.filmium.torrents.torrent_reconcile import (
    PRIORITY_NORMAL,
    PRIORITY_SKIP,
    _TorrentReconcileMixin,
)
from core.domains.filmium.torrents.torrent_repository import TorrentRepository
from core.domains.filmium.torrents.torrent_settings import TorrentSettingsStore

# Koliko čekamo metapodatke magnet linka pre nego što odustanemo.

# qBittorrent prioriteti: 0 = ne skidaj, 1 = normalno.

# Statusi u kojima „nastavi" i „pauziraj" uopšte imaju smisla.
RESUMABLE_STATUSES = (TorrentStatus.PAUSED, TorrentStatus.DOWNLOADING)
PAUSABLE_STATUSES = (TorrentStatus.DOWNLOADING, TorrentStatus.PAUSED)

# Statusi koji znače „ovaj torrent je još u igri" — dok ih ima, pozadinska
# anketa radi na kratkom razmaku.
ACTIVE_STATUSES = (
    TorrentStatus.DETECTED,
    TorrentStatus.METADATA_FETCHING,
    TorrentStatus.AWAITING_APPROVAL,
    TorrentStatus.DOWNLOADING,
    TorrentStatus.PAUSED,
)


def _is_magnet(source: str) -> bool:
    return source.strip().lower().startswith("magnet:")


def _normalized(path: str) -> str:
    return path.replace("\\", "/").strip("/").lower()


def _is_wanted(engine_path: str, wanted: set[str]) -> bool:
    """Da li putanja fajla iz klijenta odgovara nekom izboru iz .torrent fajla.

    Putanje se porede po repu: qBittorrent ispred svake stavke stavlja ime
    korenskog foldera torrenta, koje u samom .torrent zapisu ne postoji.
    """

    candidate = _normalized(engine_path)
    for item in wanted:
        if candidate == item or candidate.endswith("/" + item):
            return True
    return False


# ========== SERVIS ==========
class TorrentService(_TorrentReconcileMixin):
    """Životni ciklus torrenta koje je FILMIUM dodao."""

    def __init__(
        self,
        repository: TorrentRepository,
        engine: TorrentEngine,
        settings_store: TorrentSettingsStore,
        *,
        archive: TorrentArchive | None = None,
        on_completed: Callable[[TorrentEntry], None] | None = None,
        notify: Callable[[str, str], None] | None = None,
        on_settings_saved: Callable[[TorrentSettings], None] | None = None,
    ) -> None:
        self._repository = repository
        self._engine = engine
        self._settings_store = settings_store
        self._archive = archive or TorrentArchive()
        self._on_completed = on_completed
        self._notify = notify or (lambda _title, _message: None)
        self._on_settings_saved = on_settings_saved

        # Poslednji snimak napretka koji je pozadinska anketa sačuvala.
        # SSE ga samo čita — tako postoji tačno JEDAN pisac stanja.
        self._lock = threading.Lock()
        self._latest_progress: list[TorrentProgress] = []

        # Trenutak kad je OVAJ proces počeo da čeka metapodatke, po torrentu.
        # Tajmaut se meri odavde, a ne od `added_at`: posle restarta CORE-a
        # svaki stariji magnet bi inače odmah pao u ERROR.
        self._metadata_since: dict[str, datetime] = {}

    # ---------- zdravlje i podešavanja ----------
    def health(self) -> EngineHealth:
        return self._engine.is_available()

    def settings(self) -> TorrentSettings:
        return self._settings_store.load()

    def save_settings(self, settings: TorrentSettings) -> TorrentSettings:
        saved = self._settings_store.save(settings)
        try:
            self._engine.apply_limits(saved)
        except TorrentEngineError:
            pass  # klijent nije dostupan; ograničenja idu pri sledećem upisu

        # Nadzirani folder se menja bez restarta CORE-a: vlasnik nadzora
        # (runtime) dobija upis i ponovo pali nadzor na novoj putanji.
        if self._on_settings_saved is not None:
            try:
                self._on_settings_saved(saved)
            except Exception:  # noqa: BLE001, S110
                pass

        return saved

    # ---------- snimak napretka (za SSE) ----------
    def latest_progress(self) -> list[TorrentProgress]:
        """Poslednji snimak koji je pozadinska anketa sačuvala.

        Prazno pre prvog kruga. SSE ruta koristi isključivo ovo i nikada
        ne zove `poll()` — inače bi dva otvorena strima pisala u istu bazu.
        """

        with self._lock:
            return list(self._latest_progress)

    def has_active(self) -> bool:
        """Ima li torrenta u statusu koji se još menja."""

        return any(
            entry.status in ACTIVE_STATUSES for entry in self._repository.list()
        )

    # ---------- dodavanje ----------
    def add(self, source: str) -> TorrentEntry:
        cleaned = source.strip()
        if not cleaned:
            raise TorrentServiceError("Unesi magnet link ili izaberi .torrent fajl.")

        settings = self.settings()
        if not settings.download_path:
            raise TorrentServiceError(
                "Odredište preuzimanja nije podešeno "
                "(FILMIUM podešavanja → Torrenti)."
            )
        os.makedirs(settings.download_path, exist_ok=True)

        try:
            metadata = self._engine.add(
                cleaned,
                save_path=settings.download_path,
            )
        except TorrentEngineError as error:
            raise TorrentServiceError(str(error)) from error

        # Kopija .torrent fajla ulazi u CORE pre nego što izvorni fajl
        # uopšte može da nestane — iz nadziranog foldera ga uklanja i sam
        # korisnik, i podešavanje „obriši izvorni .torrent".
        archived = (
            ""
            if _is_magnet(cleaned)
            else self._archive.store(cleaned, metadata.info_hash)
        )

        entry = TorrentEntry(
            info_hash=metadata.info_hash,
            name=metadata.name,
            source=cleaned,
            source_kind="magnet" if _is_magnet(cleaned) else "file",
            status=TorrentStatus.METADATA_FETCHING,
            save_path=settings.download_path,
            total_bytes=metadata.total_bytes,
            added_at=datetime.now(),  # noqa: DTZ005
            archived_path=archived,
        )
        self._repository.upsert(entry)

        if settings.delete_source_torrent and entry.source_kind == "file":
            try:
                os.remove(cleaned)
            except OSError:
                pass  # brisanje izvornog fajla nije razlog za pad

        return entry

    # ---------- pronađeni .torrent fajlovi ----------
    def has_content(self, entry: TorrentEntry) -> bool:
        """Da li preuzeti sadržaj torrenta i dalje postoji na disku.

        Gleda se baš sadržaj, a ne odredište preuzimanja: odredište je
        zajedničko za sve torrente i postoji i kad je film obrisan.
        """

        save_path = entry.save_path.strip()
        if not save_path:
            return False

        files = self._repository.list_files(entry.info_hash)
        wanted = [item for item in files if item.selected] or files

        if wanted:
            return any(
                os.path.exists(os.path.join(save_path, item.path))
                for item in wanted
            )

        # Bez zapamćenog spiska fajlova ostaje podfolder pod imenom torrenta.
        return bool(entry.name.strip()) and os.path.isdir(
            os.path.join(save_path, entry.name)
        )

    def _is_stale(self, entry: TorrentEntry) -> bool:
        """Zapis koji više ne odgovara stanju na disku.

        Završen (ili pukao) torrent čiji je sadržaj obrisan ne sme da drži
        karticu kao „preuzeto" — isti .torrent fajl tada treba da se ponudi
        iznova, sa podrazumevanim izborom fajlova.
        """

        if entry.status not in (TorrentStatus.COMPLETED, TorrentStatus.ERROR):
            return False

        return not self.has_content(entry)

    def discover(self) -> list[DiscoveredTorrent]:
        """Kartice za sve .torrent fajlove iz nadziranih foldera.

        Čita se sam fajl — qBittorrent za ovo ne mora da radi. Torrent koji
        je već predat klijentu nosi svoj status; zapis čiji je sadržaj u
        međuvremenu obrisan broji se kao da ga nema, pa kartica kreće iznova.
        """

        found = scan_folders(self.settings().watch_folders)
        known = {
            entry.info_hash.lower(): (
                None if self._is_stale(entry) else entry.status
            )
            for entry in self._repository.list()
        }
        handed = self._repository.handed_off_hashes()

        return [
            replace(
                item,
                status=known.get(item.info_hash.lower()),
                handed_to_library=item.info_hash.lower() in handed,
            )
            for item in found
        ]

    def start_discovered(
        self,
        source_path: str,
        selected_paths: list[str],
    ) -> TorrentEntry:
        """Predaje pronađen .torrent klijentu sa tačno izabranim fajlovima.

        Jedan korak umesto dva: torrent se doda pauziran, izbor se prenese
        na prioritete i preuzimanje odmah kreće (ako je auto start uključen).
        """

        cleaned = source_path.strip()
        if not os.path.isfile(cleaned):
            raise TorrentServiceError(f"Torrent fajl ne postoji: {cleaned}")

        if not selected_paths:
            raise TorrentServiceError("Štikliraj bar jedan fajl pre preuzimanja.")

        # Isti torrent je možda već jednom skinut, pa mu je sadržaj obrisan.
        # Stari zapis (i stari izbor fajlova) odlazi pre novog pokušaja —
        # inače bi qBittorrent odbio duplikat, a kartica ostala na „Završen".
        found = read_torrent_file(cleaned)
        if found is not None:
            previous = self._repository.get(found.info_hash)
            if previous is not None and self._is_stale(previous):
                self.remove(previous.info_hash)

            # Novo preuzimanje još nije nikome predato; stara beleška o
            # predaji uvozu se ne prenosi na njega.
            self._repository.clear_handoff(found.info_hash)

        entry = self.add(cleaned)

        try:
            files = self._engine.list_files(entry.info_hash)
        except TorrentEngineError as error:
            raise TorrentServiceError(str(error)) from error

        if not files:
            raise TorrentServiceError(
                "qBittorrent još nije pročitao spisak fajlova ovog torrenta."
            )

        wanted = {_normalized(item) for item in selected_paths if item.strip()}
        prepared = [
            TorrentFileEntry(
                file_index=item.file_index,
                path=item.path,
                size_bytes=item.size_bytes,
                selected=_is_wanted(item.path, wanted),
            )
            for item in files
        ]
        self._repository.replace_files(entry.info_hash, prepared)

        indexes = [item.file_index for item in prepared if item.selected]
        if not indexes:
            raise TorrentServiceError(
                "Nijedan izabrani fajl nije pronađen u torrentu."
            )

        return self.approve(entry.info_hash, indexes)

    def save_torrent_bytes(self, filename: str, data: bytes) -> DiscoveredTorrent:
        """Upisuje prevučen .torrent fajl u prvi nadzirani folder.

        Sadržaj se pre upisa pročita: sve što nije ispravan .torrent zapis
        biva odbijeno, pa u nadziranom folderu ne završi tuđi fajl.
        """

        name = os.path.basename(filename.strip().replace("\\", "/"))
        if not name.lower().endswith(TORRENT_EXTENSION):
            raise TorrentServiceError(
                f"Prihvata se samo {TORRENT_EXTENSION} fajl: {name or filename}"
            )

        folder = self._drop_folder()
        target = os.path.join(folder, name)

        try:
            with open(target, "wb") as handle:
                handle.write(data)
        except OSError as error:
            raise TorrentServiceError(
                f"Upis torrent fajla nije uspeo: {error}"
            ) from error

        found = read_torrent_file(target)
        if found is None:
            try:
                os.remove(target)
            except OSError:
                pass
            raise TorrentServiceError(
                f'„{name}” nije ispravan .torrent fajl.'
            )

        known = self._repository.get(found.info_hash)
        return replace(
            found,
            status=known.status if known is not None else None,
            handed_to_library=self._repository.is_handed_off(found.info_hash),
        )

    def _drop_folder(self) -> str:
        """Folder u koji ide prevučen .torrent: prvi nadzirani koji postoji."""

        settings = self.settings()
        for folder in settings.watch_folders:
            cleaned = folder.strip()
            if not cleaned:
                continue
            resolved = os.path.abspath(cleaned)
            try:
                os.makedirs(resolved, exist_ok=True)
            except OSError:
                continue
            if os.path.isdir(resolved):
                return resolved

        raise TorrentServiceError(
            "Nijedan nadzirani folder nije podešen "
            "(FILMIUM podešavanja → Torrenti)."
        )

    # ---------- čitanje ----------
    def list(self, status: TorrentStatus | None = None) -> list[TorrentEntry]:
        return self._repository.list(status)

    def files(self, info_hash: str) -> list[TorrentFileEntry]:
        """Fajlovi torrenta: izbor iz baze, napredak iz klijenta.

        Baza je vlasnik štikliranja (preživi restart), a napredak po fajlu
        zna samo klijent. Kad klijent nije dostupan, napredak ostaje 0.
        """

        self._require(info_hash)
        stored = self._repository.list_files(info_hash)

        try:
            live = {
                item.file_index: item.progress
                for item in self._engine.list_files(info_hash)
            }
        except TorrentEngineError:
            return stored

        return [
            replace(item, progress=live.get(item.file_index, 0.0))
            for item in stored
        ]

    # ---------- odobrenje ----------
    def approve(self, info_hash: str, selected_indexes: list[int]) -> TorrentEntry:
        entry = self._require(info_hash)
        if not selected_indexes:
            raise TorrentServiceError("Štikliraj bar jedan fajl pre odobrenja.")

        known = {item.file_index for item in self._repository.list_files(info_hash)}
        unknown = sorted(set(selected_indexes) - known)
        if unknown:
            raise TorrentServiceError(
                f"Nepoznati indeksi fajlova: {', '.join(str(i) for i in unknown)}."
            )

        self._repository.set_selected(info_hash, selected_indexes)
        priorities = {
            index: (
                PRIORITY_NORMAL if index in set(selected_indexes) else PRIORITY_SKIP
            )
            for index in sorted(known)
        }

        try:
            self._engine.set_file_priorities(info_hash, priorities)
        except TorrentEngineError as error:
            raise TorrentServiceError(str(error)) from error

        settings = self.settings()
        if settings.auto_start:
            # Baza se menja TEK pošto je klijent zaista pustio torrent —
            # inače bi pad klijenta ostavio zapis na „skida se", a ništa
            # se ne bi skidalo.
            try:
                self._engine.start(info_hash)
            except TorrentEngineError as error:
                raise TorrentServiceError(
                    f"Torrent nije pokrenut u qBittorrent-u: {error}"
                ) from error
            status = TorrentStatus.DOWNLOADING
        else:
            status = TorrentStatus.PAUSED

        self._repository.update_status(info_hash, status)
        entry.status = status
        return entry

    # ---------- predaja uvozu u biblioteku ----------
    def mark_library_handoff(self, info_hash: str) -> None:
        """Beleži da je korisnik torrent poslao ka ekranu uvoza.

        Zapis NAMERNO preživljava uklanjanje torrenta: po njemu se kasnije
        zna da izvorni .torrent fajl više nikome ne treba, pa se briše bez
        dodatnog pitanja.

        Ovo je „predat uvozu", a ne „uvezen": sam uvoz je zaseban korak na
        ekranu uvoza i modul za njegov ishod nema signal.
        """

        self._require(info_hash)
        self._repository.mark_handoff(info_hash, datetime.now())  # noqa: DTZ005

    def is_handed_to_library(self, info_hash: str) -> bool:
        return self._repository.is_handed_off(info_hash)

    # ---------- otvaranje foldera ----------
    def content_folder(self, info_hash: str) -> str:
        """Folder u kome je sadržaj torrenta na disku.

        Višefajlni torrent qBittorrent smešta u podfolder pod imenom
        torrenta; kad tog podfoldera nema (jedan fajl, ili skidanje još
        nije napravilo folder), vraća se samo odredište preuzimanja.
        """

        entry = self._require(info_hash)
        save_path = entry.save_path.strip()
        if not save_path:
            return ""

        nested = os.path.join(save_path, entry.name)
        if entry.name.strip() and os.path.isdir(nested):
            return nested

        return save_path if os.path.isdir(save_path) else ""

    def reveal(self, info_hash: str) -> bool:
        """Otvara folder sa sadržajem torrenta u menadžeru fajlova.

        Putanja se UVEK čita iz zapisa o torrentu, nikad iz zahteva — tako
        ova ruta ne može da posluži za otvaranje proizvoljnog foldera.
        """

        folder = self.content_folder(info_hash)
        if not folder:
            raise TorrentServiceError(
                "Folder sa sadržajem još ne postoji na disku."
            )

        return open_folder(Path(folder))

    # ---------- kontrola ----------
    def pause(self, info_hash: str) -> TorrentEntry:
        entry = self._require(info_hash)
        if entry.status not in PAUSABLE_STATUSES:
            raise TorrentServiceError(
                f'Torrent u statusu „{entry.status.value}” nije moguće pauzirati.'
            )

        try:
            self._engine.pause(info_hash)
        except TorrentEngineError as error:
            raise TorrentServiceError(
                f"Pauza nije prošla u qBittorrent-u: {error}"
            ) from error

        self._repository.update_status(info_hash, TorrentStatus.PAUSED)
        entry.status = TorrentStatus.PAUSED
        return entry

    def resume(self, info_hash: str) -> TorrentEntry:
        """Nastavlja SAMO torrent koji je korisnik već odobrio.

        Centralna garancija modula: torrent u `awaiting_approval` još nema
        nijedan štikliran fajl, pa bi „nastavi" značio skidanje svega.
        """

        entry = self._require(info_hash)
        if entry.status not in RESUMABLE_STATUSES:
            raise TorrentServiceError(
                f'Torrent u statusu „{entry.status.value}” nije moguće nastaviti. '
                "Najpre izaberi fajlove i odobri preuzimanje."
            )

        try:
            self._engine.resume(info_hash)
        except TorrentEngineError as error:
            raise TorrentServiceError(
                f"Nastavak nije prošao u qBittorrent-u: {error}"
            ) from error

        self._repository.update_status(info_hash, TorrentStatus.DOWNLOADING)
        entry.status = TorrentStatus.DOWNLOADING
        return entry

    def pause_all(self) -> int:
        """Pauzira svaki torrent koji se trenutno skida. Vraća broj pauziranih."""

        paused = 0
        for entry in self._repository.list():
            if entry.status is not TorrentStatus.DOWNLOADING:
                continue
            try:
                self.pause(entry.info_hash)
            except TorrentServiceError:
                continue  # jedan neuspeh ne sme da zaustavi ostale
            paused += 1
        return paused

    def default_selection(self, files: tuple[DiscoveredFile, ...]) -> list[str]:
        """Podrazumevani izbor fajlova — isti koji kartica prikazuje.

        Ekstenzije iz filtera (`.nfo`, `.jpg`, …) ostaju neštiklirane. Kad
        bi filter pojeo SVE fajlove, izbor pada na ceo torrent: bolje je
        skinuti sve nego ne skinuti ništa.
        """

        skipped = tuple(
            extension.lower()
            for extension in self.settings().unselected_extensions
        )
        wanted = [
            item.path
            for item in files
            if not (skipped and item.path.lower().endswith(skipped))
        ]
        return wanted or [item.path for item in files]

    def start_all(self) -> tuple[int, int]:
        """Pokreće SVE što može da krene. Vraća (pokrenuto, neuspelo).

        Tri slučaja, svaki radi ono što bi i klik na samoj kartici:
        pauziran torrent se nastavlja; torrent koji čeka izbor fajlova
        kreće sa izborom koji već stoji u bazi; pronađen .torrent fajl se
        predaje klijentu sa podrazumevanim izborom.

        Podrazumevani izbor NIJE „skini sve": ekstenzije iz filtera ostaju
        neštiklirane, isto kao na kartici. Ko želi drugačije, bira na
        kartici pa pokreće odatle.

        Jedan neuspeh ne zaustavlja ostale — grupna radnja nad listom mora
        da odradi sve što može.
        """

        started = 0
        failed = 0

        for entry in self._repository.list():
            if entry.status is TorrentStatus.PAUSED:
                try:
                    self.resume(entry.info_hash)
                except TorrentServiceError:
                    failed += 1
                    continue
                started += 1
                continue

            if entry.status is TorrentStatus.AWAITING_APPROVAL:
                indexes = [
                    item.file_index
                    for item in self._repository.list_files(entry.info_hash)
                    if item.selected
                ]
                if not indexes:
                    failed += 1
                    continue
                try:
                    self.approve(entry.info_hash, indexes)
                except TorrentServiceError:
                    failed += 1
                    continue
                started += 1

        # Pronađeni .torrent fajlovi koji još nisu stigli do klijenta.
        for found in self.discover():
            if found.status is not None:
                continue
            try:
                self.start_discovered(
                    found.source_path,
                    self.default_selection(found.files),
                )
            except TorrentServiceError:
                failed += 1
                continue
            started += 1

        return started, failed

    def remove_discovered(self, source_path: str) -> None:
        """Briše .torrent fajl iz nadziranog foldera (kartica nestaje).

        Brisanje je ograničeno na nadzirane foldere — bez toga bi putanja
        iz zahteva mogla da obriše bilo koji fajl na disku.
        """

        target = os.path.abspath(source_path.strip())

        if not target.lower().endswith(TORRENT_EXTENSION):
            raise TorrentServiceError(
                f"Uklanja se samo {TORRENT_EXTENSION} fajl: {source_path}"
            )

        folders = {
            os.path.abspath(folder.strip())
            for folder in self.settings().watch_folders
            if folder.strip()
        }
        if os.path.dirname(target) not in folders:
            raise TorrentServiceError(
                "Fajl nije u nadziranom folderu, pa se odavde ne briše."
            )

        # Pre brisanja iz korisnikovog foldera, kopija ulazi u CORE: „X"
        # sklanja karticu, ali sam torrent ostaje da se može ponoviti.
        found = read_torrent_file(target)
        if found is not None:
            self._archive.store(target, found.info_hash)

            # Kartica je pokazivala zastareo zapis (sadržaj obrisan sa
            # diska); „X" sklanja i njega, da se ne vrati na sledeći krug.
            previous = self._repository.get(found.info_hash)
            if previous is not None and self._is_stale(previous):
                self.remove(previous.info_hash)

            # Izvorni fajl odlazi; beleška o predaji uvozu nema više šta da
            # čuva, pa ne sme da zbuni sledeći isti torrent.
            self._repository.clear_handoff(found.info_hash)

        try:
            os.remove(target)
        except FileNotFoundError:
            pass  # već ga nema — kartica je ionako trebalo da nestane
        except OSError as error:
            raise TorrentServiceError(
                f"Brisanje torrent fajla nije uspelo: {error}"
            ) from error

    def remove(self, info_hash: str, *, delete_files: bool = False) -> None:
        """Briše zapis o torrentu, a sa njim i arhiviranu kopiju .torrent fajla.

        Kopija postoji da bi se preuzimanje moglo ponoviti dok torrent živi
        u FILMIUM-u; kad korisnik ukloni torrent, nema šta da čuva.
        """

        self._require(info_hash)
        try:
            self._engine.remove(info_hash, delete_files=delete_files)
        except TorrentEngineError:
            pass  # zapis brišemo i ako klijent trenutno nije dostupan
        self._repository.delete(info_hash)
        self._archive.discard(info_hash)

    # ---------- pomoćno ----------
    def _require(self, info_hash: str) -> TorrentEntry:
        entry = self._repository.get(info_hash)
        if entry is None:
            raise TorrentServiceError(f"Torrent nije pronađen: {info_hash}")
        return entry
