"""Pomoćne funkcije za library_import_commit_service (payload/asset) —
izdvojeno radi veličine fajla."""

from core.domains.filmium.models import MediaItemCreate


def _build_media_create_payload(
    manifest,
    enrichment,
    effective_title: str,
    effective_release_year: int | None,
    effective_genres: tuple[str, ...],
    content_mode: str,
    synchronized: bool,
) -> MediaItemCreate:
    """MediaItemCreate za nov naslov: lokalni naslov/žanrovi netaknuti, TMDB
    (enrichment) puni samo prazna polja (None kad enrichmenta nema)."""

    return MediaItemCreate(
        title=effective_title,
        original_title=(
            (enrichment.original_title if enrichment else None)
            or manifest.original_title
        ),
        english_title=(
            enrichment.english_title if enrichment else None
        ),
        media_type=manifest.media_type,
        release_year=(
            effective_release_year
            or (enrichment.year if enrichment else None)
        ),
        runtime_minutes=manifest.runtime_minutes,
        notes=(
            manifest.description
            or (enrichment.local_overview if enrichment else None)
        ),
        english_description=(
            enrichment.english_overview if enrichment else None
        ),
        content_category=content_mode,
        cast_names=(
            enrichment.cast_names if enrichment else ()
        ),
        studio=(
            enrichment.studio if enrichment else None
        ),
        director=(
            enrichment.director if enrichment else None
        ),
        keywords=(
            enrichment.keywords if enrichment else ()
        ),
        collection=(
            enrichment.collection if enrichment else None
        ),
        is_synchronized=synchronized,
        tmdb_id=(
            enrichment.tmdb_id if enrichment else None
        ),
        genres=effective_genres,
    )


def _delete_asset_safe(visual_service, media_id: int, asset_type) -> None:
    """Ukloni managed sliku; greska pri rollback-u se tiho ignorise."""

    try:
        visual_service.delete_media_asset(media_id, asset_type)
    except Exception:  # noqa: BLE001, S110
        pass
