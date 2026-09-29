from core.database import DatabaseMigration

# ==========          SEZONE I EPIZODE          ==========

FILMIUM_MIGRATION_V18 = DatabaseMigration(
    scope="filmium",
    version=18,
    name="add_series_seasons_episodes",
    statements=(
        """
        CREATE TABLE filmium_seasons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            media_id INTEGER NOT NULL,
            season_number INTEGER NOT NULL,
            name TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (media_id, season_number),
            FOREIGN KEY (media_id)
                REFERENCES filmium_media_items (id)
                ON DELETE CASCADE
        )
        """,
        """
        CREATE INDEX filmium_seasons_media_index
        ON filmium_seasons (media_id)
        """,
        """
        CREATE TABLE filmium_episodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            season_id INTEGER NOT NULL,
            episode_number INTEGER NOT NULL,
            title TEXT,
            runtime_minutes INTEGER,
            watch_status TEXT NOT NULL DEFAULT 'planned',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (season_id, episode_number),
            FOREIGN KEY (season_id)
                REFERENCES filmium_seasons (id)
                ON DELETE CASCADE
        )
        """,
        """
        CREATE INDEX filmium_episodes_season_index
        ON filmium_episodes (season_id)
        """,
    ),
)
