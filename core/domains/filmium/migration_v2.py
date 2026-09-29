from core.database import DatabaseMigration

# ==========          FILMIUM MIGRACIJA VERZIJE 2          ==========

FILMIUM_MIGRATION_V2 = DatabaseMigration(
        scope="filmium",
        version=2,
        name="create_genres",
        statements=(
            """
            CREATE TABLE filmium_genres (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL COLLATE NOCASE UNIQUE,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE filmium_media_genres (
                media_id INTEGER NOT NULL,
                genre_id INTEGER NOT NULL,
                PRIMARY KEY (media_id, genre_id),
                FOREIGN KEY (media_id)
                    REFERENCES filmium_media_items (id)
                    ON DELETE CASCADE,
                FOREIGN KEY (genre_id)
                    REFERENCES filmium_genres (id)
                    ON DELETE CASCADE
            )
            """,
            """
            CREATE INDEX filmium_media_genres_genre_id_index
            ON filmium_media_genres (genre_id)
            """,
        ),
    )
