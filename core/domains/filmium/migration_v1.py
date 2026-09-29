from core.database import DatabaseMigration

# ==========          FILMIUM MIGRACIJA VERZIJE 1          ==========

FILMIUM_MIGRATION_V1 = DatabaseMigration(
        scope="filmium",
        version=1,
        name="create_media_items",
        statements=(
            """
            CREATE TABLE filmium_media_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                original_title TEXT,
                media_type TEXT NOT NULL
                    CHECK (media_type IN ('movie', 'series')),
                release_year INTEGER
                    CHECK (
                        release_year IS NULL
                        OR release_year BETWEEN 1888 AND 9999
                    ),
                watch_status TEXT NOT NULL DEFAULT 'planned'
                    CHECK (
                        watch_status IN (
                            'planned',
                            'watching',
                            'completed',
                            'paused',
                            'dropped'
                        )
                    ),
                rating INTEGER
                    CHECK (
                        rating IS NULL
                        OR rating BETWEEN 1 AND 10
                    ),
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """,
        ),
    )
