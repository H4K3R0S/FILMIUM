"""Sinhronizacija poster/backdrop slika serije (serija + po sezoni).

Deljena logika: koristi je i uvoz serije i osvežavanje biblioteke. Skenira
folder serije istim skenerom kao upload (bez dupliranja logike za traženje
slika), pa registruje managed kopije:

- serija (kartica) → reprezentativna slika (cela serija ili sezona 1),
- svaka sezona → sopstveni poster/backdrop.

Tolerantno: nedostatak slike ili greška ne ruši uvoz/osvežavanje.
"""

from dataclasses import dataclass
from pathlib import Path

from core.domains.filmium import tmdb_client
from core.domains.filmium.asset_service import (
    MediaAssetService,
    MediaAssetType,
)
from core.domains.filmium.repository import MediaRepository
from core.domains.filmium.season_repository import SeasonRepository
from core.domains.filmium.series_scanner import (
    ArtworkRef,
    scan_series_directory,
)


@dataclass
class ArtworkSyncResult:
    """Sažetak primenjenih slika."""

    media_poster: bool = False
    media_backdrop: bool = False
    season_posters: int = 0
    season_backdrops: int = 0

    @property
    def changed(self) -> bool:
        return (
            self.media_poster
            or self.media_backdrop
            or self.season_posters > 0
            or self.season_backdrops > 0
        )


def _read_bytes(path: Path | None) -> bytes | None:
    if path is None:
        return None
    try:
        candidate = Path(path)
        if not candidate.is_file():
            return None
        return candidate.read_bytes() or None
    except OSError:
        return None


def _needs_refresh(
    asset_service: MediaAssetService,
    relative_path: str | None,
    force: bool,
) -> bool:
    """
    Da li treba (ponovo) napraviti managed sliku.

    Regeneriše se ne samo kad putanja u bazi nedostaje, nego i kad putanja
    postoji ali managed datoteka na disku NE postoji — čest slučaj: uvoz je
    upisao poster_path ka keš kopiji koja nikad nije napravljena (`data/
    filmium/assets` ne postoji), pa je slika 404. `force` uvek regeneriše.
    """

    if force or not relative_path:
        return True
    return asset_service.get_asset_path(relative_path) is None


def _sync_series_visual(
    media,
    media_id: int,
    scan,
    enrichment,
    asset_service: MediaAssetService,
    media_repository: MediaRepository,
    force: bool,
    result: ArtworkSyncResult,
) -> None:
    """Reprezentativna slika serije (kartica): poster + backdrop (folder pa TMDB)."""

    poster_path = media.poster_path
    backdrop_path = media.backdrop_path

    if _needs_refresh(asset_service, poster_path, force):
        content = _read_bytes(scan.poster_path) or tmdb_client.download_image(
            getattr(enrichment, "poster_url", None)
        )
        if content:
            poster_path = asset_service.save_asset(
                media_id, MediaAssetType.POSTER, content
            )
            result.media_poster = True

    if _needs_refresh(asset_service, backdrop_path, force):
        content = _read_bytes(
            scan.backdrop_path
        ) or tmdb_client.download_image(
            getattr(enrichment, "backdrop_url", None)
        )
        if content:
            backdrop_path = asset_service.save_asset(
                media_id, MediaAssetType.BACKDROP, content
            )
            result.media_backdrop = True

    if result.media_poster or result.media_backdrop:
        media_repository.set_visual_assets(
            item_id=media_id,
            poster_path=poster_path,
            backdrop_path=backdrop_path,
        )


def _group_season_artwork(scan) -> dict[int, dict[str, "ArtworkRef"]]:
    """Grupiši slike po sezoni i vrsti (poster/backdrop; prva po sezoni pobeđuje)."""

    grouped: dict[int, dict[str, ArtworkRef]] = {}
    for ref in scan.artwork:
        if ref.season is None or ref.kind not in ("poster", "backdrop"):
            continue
        grouped.setdefault(ref.season, {}).setdefault(ref.kind, ref)
    return grouped


def _sync_one_season(
    media_id: int,
    season_number: int,
    season,
    refs: dict[str, "ArtworkRef"],
    asset_service: MediaAssetService,
    season_repository: SeasonRepository,
    force: bool,
    result: ArtworkSyncResult,
) -> None:
    """Primeni poster/backdrop jedne sezone (varijanta s<broj>) i upiši u bazu."""

    new_poster: str | None = None
    new_backdrop: str | None = None

    poster_ref = refs.get("poster")
    if poster_ref and _needs_refresh(
        asset_service, season.poster_path, force
    ):
        content = _read_bytes(poster_ref.path)
        if content:
            new_poster = asset_service.save_asset(
                media_id,
                MediaAssetType.POSTER,
                content,
                variant=f"s{season_number}",
            )
            result.season_posters += 1

    backdrop_ref = refs.get("backdrop")
    if backdrop_ref and _needs_refresh(
        asset_service, season.backdrop_path, force
    ):
        content = _read_bytes(backdrop_ref.path)
        if content:
            new_backdrop = asset_service.save_asset(
                media_id,
                MediaAssetType.BACKDROP,
                content,
                variant=f"s{season_number}",
            )
            result.season_backdrops += 1

    if new_poster or new_backdrop:
        season_repository.set_visual_assets(
            season.id,
            poster_path=new_poster,
            backdrop_path=new_backdrop,
        )


def apply_series_artwork(
    directory: Path,
    media_id: int,
    *,
    asset_service: MediaAssetService,
    season_repository: SeasonRepository,
    media_repository: MediaRepository,
    enrichment: "tmdb_client.MediaTitleEnrichment | None" = None,
    force: bool = False,
) -> ArtworkSyncResult:
    """Primeni slike iz foldera serije na bazu (serija + sezone)."""

    result = ArtworkSyncResult()

    media = media_repository.get_by_id(media_id)
    if media is None:
        return result

    scan = scan_series_directory(Path(directory))

    # ----- Reprezentativna slika serije (kartica) -----
    _sync_series_visual(
        media, media_id, scan, enrichment, asset_service,
        media_repository, force, result,
    )

    # ----- Slike po sezoni -----
    seasons = {
        season.season_number: season
        for season in season_repository.list_for_media(media_id)
    }

    grouped = _group_season_artwork(scan)

    for season_number, refs in grouped.items():
        season = seasons.get(season_number)
        if season is None:
            continue
        _sync_one_season(
            media_id, season_number, season, refs, asset_service,
            season_repository, force, result,
        )

    return result
