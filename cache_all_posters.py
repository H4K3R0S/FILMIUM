#!/usr/bin/env python3
"""Batch keširanje FILMIUM postera/backdrops iz izvorne biblioteke.

Za svaku stavku kojoj lokalni keš (data/filmium/assets/{posters|backdrops}/<id>/)
ne postoji, pročita izvornu sliku sa diska, umanji je na keš dimenzije
(poster 500x750, backdrop 1280x720) i sačuva kao mali keš + upiše u bazu.

Pokretati SISTEMSKIM/venv python-om iz korena ćelije. Idempotentno:
već keširane stavke se preskaču.
"""

import sys
from pathlib import Path

CELL_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(CELL_ROOT))

# Bootstrap ćelije (putanje, baza, OS sync korena) — isti put kao cell_app.
import cell_app  # noqa: F401
from apps.api.dependencies import get_filmium_service
from core.domains.filmium.artwork_models import ArtworkType
from core.domains.filmium.asset_service import MediaAssetType

ASSETS = CELL_ROOT / "data" / "filmium" / "assets"


def _has_cache(kind: str, media_id: int) -> bool:
    directory = ASSETS / kind / str(media_id)
    return directory.is_dir() and any(directory.iterdir())


def main() -> int:
    service = get_filmium_service()
    repo = service._repository

    ids = [row.id for row in repo.list_all()] if hasattr(repo, "list_all") else None
    if ids is None:
        # fallback: direktno iz baze
        import sqlite3

        conn = sqlite3.connect(str(CELL_ROOT / "data" / "filmium.db"))
        ids = [r[0] for r in conn.execute("SELECT id FROM filmium_media_items")]
        conn.close()

    total = len(ids)
    print(f"Stavki ukupno: {total}")

    jobs = (
        ("posters", ArtworkType.POSTER, MediaAssetType.POSTER),
        ("backdrops", ArtworkType.BACKDROP, MediaAssetType.BACKDROP),
    )

    cached = skipped = no_source = errors = 0

    for index, media_id in enumerate(ids, start=1):
        for kind, artwork_type, asset_type in jobs:
            if _has_cache(kind, media_id):
                skipped += 1
                continue
            try:
                result = service._cache_source_visual_path(
                    media_id, artwork_type, asset_type
                )
                if result:
                    cached += 1
                else:
                    no_source += 1
            except Exception as error:  # noqa: BLE001
                errors += 1
                print(f"  GREŠKA id={media_id} {kind}: {error}")

        if index % 50 == 0:
            print(
                f"[{index}/{total}] keširano={cached} "
                f"bez_izvora={no_source} preskočeno={skipped} greške={errors}"
            )

    print(
        f"\nGOTOVO: keširano={cached}, bez_izvora={no_source}, "
        f"preskočeno={skipped}, greške={errors}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
