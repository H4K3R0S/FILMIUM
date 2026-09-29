# ========== TORRENT ENGINE (qBittorrent Web API) ==========
# Jedini modul koji zna za qBittorrent. Uvoz `qbittorrentapi` je LENJ, pa
# CORE radi i kada paket nije instaliran — modul tada prijavi da nije spreman.
#
# Svi pozivi idu nad kategorijom FILMIUM: torrenti koje je korisnik ručno
# pustio u qBittorrent-u ostaju nevidljivi i netaknuti.
from __future__ import annotations

import base64
import os
import threading
from collections.abc import Callable
from typing import Any, Protocol, TypeVar

from core.domains.filmium.torrents.torrent_bencode import info_hash_of
from core.domains.filmium.torrents.torrent_models import (
    QBIT_CATEGORY,
    EngineHealth,
    TorrentFileEntry,
    TorrentMetadata,
    TorrentProgress,
    TorrentSettings,
)

# qBittorrent stanja koja znače „gotovo" i „pauzirano".
#
# Web API v2.11 (qBittorrent 5.0) je preimenovao `paused*` u `stopped*`.
# Oba imena stoje u skupovima da modul radi i na 4.x i na 5.x.
_FINISHED_STATES = {
    "uploading", "stalledUP", "pausedUP", "stoppedUP", "queuedUP",
    "forcedUP", "checkingUP",
}
_PAUSED_STATES = {"pausedDL", "pausedUP", "stoppedDL", "stoppedUP"}
_ERROR_STATES = {"error", "missingFiles"}

# qBittorrent prioriteti fajla: 0 = ne skidaj.
_PRIORITY_SKIP = 0

# Delovi poruke po kojima prepoznajemo da je sesija istekla ili da prijava
# nije prošla — tada se keširan klijent baca i pravi se nov.
_AUTH_HINTS = (
    "403", "401", "forbidden", "unauthorized", "login", "unauthenticated",
)

_T = TypeVar("_T")


class TorrentEngineError(RuntimeError):
    """Greška u komunikaciji sa torrent klijentom, sa porukom za korisnika."""


# ========== PROTOKOL ==========
class TorrentEngine(Protocol):
    def is_available(self) -> EngineHealth: ...

    def add(self, source: str, *, save_path: str) -> TorrentMetadata: ...

    def list_files(self, info_hash: str) -> list[TorrentFileEntry]: ...

    def set_file_priorities(
        self, info_hash: str, priorities: dict[int, int]
    ) -> None: ...

    def start(self, info_hash: str) -> None: ...

    def pause(self, info_hash: str) -> None: ...

    def resume(self, info_hash: str) -> None: ...

    def remove(self, info_hash: str, *, delete_files: bool) -> None: ...

    def poll_status(self) -> list[TorrentProgress]: ...

    def apply_limits(self, settings: TorrentSettings) -> None: ...


def _default_client_factory(**kwargs: Any) -> Any:
    # Lenji uvoz: bez instaliranog paketa modul samo nije dostupan.
    import qbittorrentapi

    return qbittorrentapi.Client(**kwargs)


# ========== INFO HASH IZ .torrent FAJLA ==========
# Sam bencode čitač živi u `torrent_bencode` — dele ga engine i čitač
# pronađenih .torrent fajlova.

def torrent_file_info_hash(path: str) -> str | None:
    """SHA-1 nad `info` rečnikom `.torrent` fajla, kao heks niska.

    Vraća `None` kada fajl nije čitljiv ili nije ispravan bencode — poziv
    tada pada na traženje najnovijeg torrenta u kategoriji.
    """

    try:
        with open(path, "rb") as handle:
            raw = handle.read()
    except OSError:
        return None

    return info_hash_of(raw)


def _normalize_btih(token: str) -> str | None:
    """`urn:btih:` vrednost u heks obliku; prima i base32 zapis."""

    cleaned = token.strip()

    if len(cleaned) == 40:
        try:
            int(cleaned, 16)
        except ValueError:
            return None
        return cleaned.lower()

    if len(cleaned) == 32:
        try:
            return base64.b32decode(cleaned.upper()).hex()
        except (ValueError, TypeError):
            return None

    return None


def _magnet_hash(source: str) -> str | None:
    """Info hash iz magnet linka, ili `None` kada ga nije moguće izvesti.

    `urn:btmh:` (BitTorrent v2) se namerno ne pogađa — poziv pada na
    traženje torrenta u kategoriji, isto kao za `.torrent` fajl bez hash-a.
    """

    marker = "urn:btih:"
    if marker not in source:
        return None

    rest = source.split(marker, 1)[1]
    token = rest.split("&", 1)[0]
    return _normalize_btih(token)


def _is_auth_error(error: BaseException) -> bool:
    haystack = f"{type(error).__name__} {error}".lower()
    return any(hint in haystack for hint in _AUTH_HINTS)


# ========== IMPLEMENTACIJA ==========
class QbittorrentEngine:
    """TorrentEngine nad qBittorrent Web API-jem."""

    def __init__(
        self,
        settings_provider: Callable[[], TorrentSettings],
        *,
        client_factory: Callable[..., Any] | None = None,
    ) -> None:
        self._settings_provider = settings_provider
        self._client_factory = client_factory or _default_client_factory
        self._lock = threading.Lock()
        self._cached_client: Any | None = None
        self._cached_key: tuple[str, int, str, str] | None = None

    # ---------- veza ----------
    @staticmethod
    def _connection_key(settings: TorrentSettings) -> tuple[str, int, str, str]:
        return (
            settings.host,
            int(settings.port),
            settings.username,
            settings.password,
        )

    def _client(self) -> Any:
        """Keširan klijent; nova prijava samo kad je zaista potrebna.

        `poll_status()` ide jednom u sekundi — nov klijent i `auth_log_in()`
        po pozivu bi značili novu qBittorrent sesiju svake sekunde.
        """

        settings = self._settings_provider()
        key = self._connection_key(settings)

        with self._lock:
            if self._cached_client is not None and self._cached_key == key:
                return self._cached_client

        client = self._connect(settings)

        with self._lock:
            self._cached_client = client
            self._cached_key = key

        return client

    def _connect(self, settings: TorrentSettings) -> Any:
        try:
            client = self._client_factory(
                host=settings.host,
                port=settings.port,
                username=settings.username or None,
                password=settings.password or None,
            )
            client.auth_log_in()
            return client
        except ImportError:
            # Propušta se nepromenjen — is_available() ga prepoznaje i
            # korisniku javlja uputstvo za instalaciju paketa, a ne host:port.
            raise
        except Exception as error:
            raise TorrentEngineError(
                f"qBittorrent nije dostupan na {settings.host}:{settings.port} "
                f"({error})."
            ) from error

    def _invalidate(self) -> None:
        with self._lock:
            self._cached_client = None
            self._cached_key = None

    def _unreachable(self, error: BaseException) -> TorrentEngineError:
        settings = self._settings_provider()
        return TorrentEngineError(
            f"qBittorrent nije dostupan na {settings.host}:{settings.port} "
            f"({error})."
        )

    def _with_client(self, operation: Callable[[Any], _T]) -> _T:
        """Poziv nad keširanim klijentom, sa jednom obnovom na auth grešci."""

        client = self._client()
        try:
            return operation(client)
        except (ImportError, TorrentEngineError):
            raise
        except Exception as error:
            if not _is_auth_error(error):
                raise self._unreachable(error) from error

        # Sesija je istekla ili prijava nije prošla: nov klijent, jedan pokušaj.
        self._invalidate()
        client = self._client()
        try:
            return operation(client)
        except (ImportError, TorrentEngineError):
            raise
        except Exception as error:
            raise self._unreachable(error) from error

    def is_available(self) -> EngineHealth:
        try:
            version = self._with_client(lambda client: str(client.app.version))
            return EngineHealth(available=True, version=version)
        except TorrentEngineError as error:
            return EngineHealth(available=False, message=str(error))
        except ImportError:
            return EngineHealth(
                available=False,
                message=(
                    "Paket qbittorrent-api nije instaliran "
                    "(python -m pip install qbittorrent-api)."
                ),
            )

    # ---------- dodavanje ----------
    def add(self, source: str, *, save_path: str) -> TorrentMetadata:
        cleaned = source.strip()
        if not cleaned:
            raise TorrentEngineError("Prazan magnet link ili putanja do .torrent fajla.")

        payload: dict[str, Any] = {
            "category": QBIT_CATEGORY,
            "is_paused": True,
            "save_path": save_path,
        }

        if cleaned.lower().startswith("magnet:"):
            payload["urls"] = cleaned
            info_hash = _magnet_hash(cleaned)
        else:
            if not os.path.isfile(cleaned):
                raise TorrentEngineError(f"Torrent fajl ne postoji: {cleaned}")
            payload["torrent_files"] = cleaned
            # Info hash se računa iz samog fajla — pogađanje „najnoviji u
            # kategoriji" promaši kad dva torrenta stignu u istoj sekundi.
            info_hash = torrent_file_info_hash(cleaned)

        result = self._with_client(lambda client: client.torrents.add(**payload))
        if isinstance(result, str) and result.strip().lower() not in {"ok.", "ok"}:
            raise TorrentEngineError(f"qBittorrent je odbio torrent: {result}")

        if info_hash is None:
            info_hash = self._with_client(self._latest_hash)

        if not info_hash:
            raise TorrentEngineError(
                "Torrent je dodat, ali qBittorrent nije vratio info hash."
            )

        # Odbrana od nepauziranog torrenta: dok korisnik ne odobri izbor,
        # nijedan poznat fajl nema prioritet veći od 0. Kod magnet linkova
        # bez metapodataka isto radi servis čim lista fajlova stigne.
        files = self.block_all_files(info_hash)

        return TorrentMetadata(
            info_hash=info_hash,
            name=self.torrent_name(info_hash) or cleaned,
            total_bytes=sum(item.size_bytes for item in files),
            files=tuple(files),
            has_metadata=bool(files),
        )

    def block_all_files(self, info_hash: str) -> list[TorrentFileEntry]:
        """Svi poznati fajlovi torrenta dobijaju prioritet 0.

        Vraća listu fajlova (prazna kad metapodaci još nisu stigli).
        """

        try:
            files = self.list_files(info_hash)
        except TorrentEngineError:
            return []

        if files:
            self.set_file_priorities(
                info_hash,
                {item.file_index: _PRIORITY_SKIP for item in files},
            )

        return files

    def torrent_name(self, info_hash: str) -> str | None:
        """Ime torrenta iz qBittorrent-a, ili `None` dok ga još nema."""

        try:
            rows = self._with_client(
                lambda client: client.torrents.info(
                    category=QBIT_CATEGORY,
                    torrent_hashes=info_hash,
                )
            )
        except TorrentEngineError:
            return None

        for row in rows:
            if str(row.get("hash", "")).lower() != info_hash.lower():
                continue
            name = str(row.get("name", "") or "").strip()
            return name or None
        return None

    def _latest_hash(self, client: Any) -> str | None:
        rows = client.torrents.info(category=QBIT_CATEGORY, sort="added_on", reverse=True)
        for row in rows:
            return str(row["hash"]).lower()
        return None

    # ---------- fajlovi ----------
    def list_files(self, info_hash: str) -> list[TorrentFileEntry]:
        rows = self._with_client(
            lambda client: client.torrents.files(torrent_hash=info_hash)
        )
        return [
            TorrentFileEntry(
                file_index=int(row.get("index", position)),
                path=str(row["name"]),
                size_bytes=int(row.get("size", 0)),
                selected=int(row.get("priority", 1)) > 0,
                progress=float(row.get("progress", 0.0) or 0.0),
            )
            for position, row in enumerate(rows)
        ]

    def set_file_priorities(
        self,
        info_hash: str,
        priorities: dict[int, int],
    ) -> None:
        grouped: dict[int, list[int]] = {}
        for file_index, priority in priorities.items():
            grouped.setdefault(int(priority), []).append(int(file_index))

        def _apply(client: Any) -> None:
            for priority, file_ids in grouped.items():
                client.torrents.file_priority(
                    torrent_hash=info_hash,
                    file_ids=sorted(file_ids),
                    priority=priority,
                )

        self._with_client(_apply)

    # ---------- kontrola ----------
    def start(self, info_hash: str) -> None:
        self.resume(info_hash)

    def resume(self, info_hash: str) -> None:
        self._with_client(
            lambda client: client.torrents.resume(torrent_hashes=info_hash)
        )

    def pause(self, info_hash: str) -> None:
        self._with_client(
            lambda client: client.torrents.pause(torrent_hashes=info_hash)
        )

    def remove(self, info_hash: str, *, delete_files: bool) -> None:
        self._with_client(
            lambda client: client.torrents.delete(
                torrent_hashes=info_hash,
                delete_files=delete_files,
            )
        )

    # ---------- status ----------
    def poll_status(self) -> list[TorrentProgress]:
        rows = self._with_client(
            lambda client: client.torrents.info(category=QBIT_CATEGORY)
        )

        progress: list[TorrentProgress] = []
        for row in rows:
            state = str(row.get("state", ""))
            eta = row.get("eta")
            progress.append(
                TorrentProgress(
                    info_hash=str(row["hash"]).lower(),
                    name=str(row.get("name", "") or ""),
                    total_bytes=int(row.get("total_size", 0) or 0),
                    progress=float(row.get("progress", 0.0)),
                    download_rate=int(row.get("dlspeed", 0)),
                    upload_rate=int(row.get("upspeed", 0)),
                    eta_seconds=int(eta) if eta not in (None, 8640000) else None,
                    seeds=int(row.get("num_seeds", 0)),
                    peers=int(row.get("num_leechs", 0)),
                    is_finished=state in _FINISHED_STATES
                    or float(row.get("progress", 0.0)) >= 1.0,
                    is_paused=state in _PAUSED_STATES,
                    error_message="Greška u torrent klijentu."
                    if state in _ERROR_STATES
                    else None,
                )
            )
        return progress

    # ---------- ograničenja ----------
    def apply_limits(self, settings: TorrentSettings) -> None:
        def _apply(client: Any) -> None:
            client.transfer.set_download_limit(int(settings.max_download_kbs) * 1024)
            client.transfer.set_upload_limit(int(settings.max_upload_kbs) * 1024)
            client.app.set_preferences(
                {"max_active_downloads": int(settings.max_active)}
            )

        self._with_client(_apply)
