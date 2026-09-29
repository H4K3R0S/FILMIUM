"""TorrentService reconcile/poll mixin — izdvojeno radi veličine fajla."""

from __future__ import annotations

from datetime import datetime

from core.domains.filmium.torrents.torrent_engine import TorrentEngineError
from core.domains.filmium.torrents.torrent_models import (
    TorrentEntry,
    TorrentFileEntry,
    TorrentProgress,
    TorrentSettings,
    TorrentStatus,
)

# Deljene konstante (torrent_service ih uvozi odavde — reconcile je baza mixina).
METADATA_TIMEOUT_SECONDS = 60
PRIORITY_SKIP = 0
PRIORITY_NORMAL = 1

# Koliko dugo ZAVRŠEN torrent ostaje na listi pre samostalnog uklanjanja.
# Kartica i qBittorrent zapis odlaze, preuzeti fajlovi OSTAJU na disku.
COMPLETED_RETENTION_SECONDS = 24 * 3600


class _TorrentReconcileMixin:
    """Metode ankete/uskladjivanja stanja torrenta (koristi atribute iz
    TorrentService.__init__ preko self)."""

    # ---------- anketa ----------
    def poll(self, *, now: datetime | None = None) -> list[TorrentProgress]:
        moment = now or datetime.now()  # noqa: DTZ005

        try:
            progress = self._engine.poll_status()
        except TorrentEngineError:
            return []

        with self._lock:
            self._latest_progress = list(progress)

        by_hash = {item.info_hash: item for item in progress}
        settings = self.settings()

        for entry in self._repository.list():
            item = by_hash.get(entry.info_hash)

            if entry.status is TorrentStatus.METADATA_FETCHING:
                self._advance_metadata(entry, moment, settings, item)
                continue

            if entry.status is TorrentStatus.COMPLETED:
                self._expire_completed(entry, moment)
                continue

            if item is None:
                continue

            if item.error_message:
                self._repository.update_status(
                    entry.info_hash,
                    TorrentStatus.ERROR,
                    error_message=item.error_message,
                )
                continue

            if item.is_finished and entry.status is not TorrentStatus.COMPLETED:
                self._complete(entry, moment, settings)

        return progress

    def reconcile(self) -> int:
        """Usklađuje bazu sa onim što klijent prijavljuje za kategoriju.

        Torrenti koje je neko obrisao spolja prelaze u ERROR, da lista ne
        prikazuje preuzimanja kojih više nema. Vraća broj takvih zapisa.
        """

        try:
            known = {item.info_hash for item in self._engine.poll_status()}
        except TorrentEngineError:
            return 0

        active = {
            TorrentStatus.METADATA_FETCHING,
            TorrentStatus.AWAITING_APPROVAL,
            TorrentStatus.DOWNLOADING,
            TorrentStatus.PAUSED,
        }

        missing = 0
        for entry in self._repository.list():
            if entry.status in active and entry.info_hash not in known:
                self._repository.update_status(
                    entry.info_hash,
                    TorrentStatus.ERROR,
                    error_message="Torrent više ne postoji u qBittorrent-u.",
                )
                missing += 1

        return missing

    def _advance_metadata(
        self,
        entry: TorrentEntry,
        moment: datetime,
        settings: TorrentSettings,
        item: TorrentProgress | None = None,
    ) -> None:
        # Tajmaut se broji od PRVOG kruga u ovom procesu, ne od `added_at`.
        since = self._metadata_since.setdefault(entry.info_hash, moment)

        try:
            files = self._engine.list_files(entry.info_hash)
        except TorrentEngineError:
            files = []

        if files:
            prepared = [
                TorrentFileEntry(
                    file_index=file_item.file_index,
                    path=file_item.path,
                    size_bytes=file_item.size_bytes,
                    selected=not file_item.path.lower().endswith(
                        tuple(settings.unselected_extensions)
                    ),
                )
                for file_item in files
            ]

            # Odbrana pre nego što torrent uđe u „čeka odobrenje": svi
            # fajlovi na prioritet 0. Čak i da je qBittorrent iz nekog
            # razloga primio torrent nepauziran, nema šta da skine dok
            # korisnik ne odobri izbor.
            try:
                self._engine.set_file_priorities(
                    entry.info_hash,
                    {file_item.file_index: PRIORITY_SKIP for file_item in prepared},
                )
            except TorrentEngineError:
                pass  # klijent nije dostupan; torrent je i dalje pauziran

            self._repository.replace_files(entry.info_hash, prepared)

            # Dok su metapodaci u ruci, zapis dobija PRAVO ime i veličinu;
            # do sada je u listi i notifikacijama stajao ceo magnet URI.
            entry.name = self._resolve_name(entry, item, prepared)
            entry.total_bytes = self._resolve_total_bytes(item, prepared)
            entry.status = TorrentStatus.AWAITING_APPROVAL
            self._repository.upsert(entry)

            self._metadata_since.pop(entry.info_hash, None)

            message = (
                f'„{entry.name}" čeka odobrenje: '
                f"{len(prepared)} fajlova spremno za izbor."
            )
            self._notify("FILMIUM torrenti", message)
            return

        waited = (moment - since).total_seconds()
        if waited > METADATA_TIMEOUT_SECONDS:
            self._metadata_since.pop(entry.info_hash, None)
            self._repository.update_status(
                entry.info_hash,
                TorrentStatus.ERROR,
                error_message=(
                    "Preuzimanje metapodataka nije završeno u roku od "
                    f"{METADATA_TIMEOUT_SECONDS} sekundi."
                ),
            )

    @staticmethod
    def _resolve_name(
        entry: TorrentEntry,
        item: TorrentProgress | None,
        files: list[TorrentFileEntry],
    ) -> str:
        """Ime torrenta: prvo od klijenta, pa iz najvećeg fajla."""

        from_client = (item.name if item is not None else "").strip()
        if from_client:
            return from_client

        if files:
            biggest = max(files, key=lambda file_item: file_item.size_bytes)
            head = biggest.path.replace("\\", "/").split("/")[0].strip()
            if head:
                return head

        return entry.name

    @staticmethod
    def _resolve_total_bytes(
        item: TorrentProgress | None,
        files: list[TorrentFileEntry],
    ) -> int:
        if item is not None and item.total_bytes > 0:
            return int(item.total_bytes)
        return sum(file_item.size_bytes for file_item in files)

    def _complete(
        self,
        entry: TorrentEntry,
        moment: datetime,
        settings: TorrentSettings,
    ) -> None:
        self._repository.update_status(
            entry.info_hash,
            TorrentStatus.COMPLETED,
            completed_at=moment,
        )
        entry.status = TorrentStatus.COMPLETED
        entry.completed_at = moment

        # Bez seed-ovanja torrent se zaustavlja čim je fajl na disku.
        if not settings.seed_after_complete:
            try:
                self._engine.pause(entry.info_hash)
            except TorrentEngineError:
                pass

        message = f'„{entry.name}" je spreman. Putanja: {entry.save_path}'
        self._notify("FILMIUM torrenti", message)

        if self._on_completed is not None:
            self._on_completed(entry)

    def _expire_completed(self, entry: TorrentEntry, moment: datetime) -> None:
        """Uklanja ZAVRŠEN torrent 24h posle završetka; fajlovi ostaju.

        Bez `completed_at` (npr. zapis iz starije verzije) ne diramo ništa —
        sat kreće tek kad anketa upiše trenutak završetka.
        """

        if entry.completed_at is None:
            return

        age = (moment - entry.completed_at).total_seconds()
        if age < COMPLETED_RETENTION_SECONDS:
            return

        # `remove` sam guta nedostupnost klijenta; jedina moguća greška je
        # da je zapis u međuvremenu nestao — anketa ne sme da padne zbog toga.
        try:
            self.remove(entry.info_hash, delete_files=False)
        except Exception:  # noqa: BLE001, S110 — anketa preživljava sve
            pass
