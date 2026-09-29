from core.database import DatabaseMigration

# ==========          LISTA „ZA PREUZETI"          ==========
#
# Zasebna tabela za filmove i serije koje korisnik planira da nabavi.
# Nezavisna je od glavnog kataloga (filmium_media_items) — ovde se drže
# samo želje/predlozi koji se prikazuju u Home redu „FILMOVI ZA PREUZETI".

FILMIUM_MIGRATION_V28 = DatabaseMigration(
    scope="filmium",
    version=28,
    name="create_wishlist",
    statements=(
        """
        CREATE TABLE filmium_wishlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            release_year INTEGER
                CHECK (
                    release_year IS NULL
                    OR release_year BETWEEN 1888 AND 9999
                ),
            media_type TEXT NOT NULL DEFAULT 'movie'
                CHECK (media_type IN ('movie', 'series')),
            content_category TEXT NOT NULL DEFAULT 'regular'
                CHECK (
                    content_category IN (
                        'regular',
                        'domestic',
                        'animated'
                    )
                ),
            is_subtitled INTEGER NOT NULL DEFAULT 0
                CHECK (is_subtitled IN (0, 1)),
            is_synchronized INTEGER NOT NULL DEFAULT 0
                CHECK (is_synchronized IN (0, 1)),
            tmdb_id INTEGER,
            english_overview TEXT,
            local_overview TEXT,
            poster_path TEXT,
            backdrop_path TEXT,
            wallpaper_path TEXT,
            original_subtitle_path TEXT,
            domestic_subtitle_path TEXT,
            english_subtitle_path TEXT,
            extra_assets TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
    ),
)
