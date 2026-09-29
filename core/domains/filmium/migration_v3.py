from core.database import DatabaseMigration

# ==========          FILMIUM MIGRACIJA VERZIJE 3          ==========

FILMIUM_MIGRATION_V3 = DatabaseMigration(
        scope="filmium",
        version=3,
        name="create_collections",
        statements=(
            """
            CREATE TABLE filmium_collections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL COLLATE NOCASE UNIQUE,
                description TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE filmium_collection_items (
                collection_id INTEGER NOT NULL,
                media_id INTEGER NOT NULL,
                position INTEGER NOT NULL DEFAULT 0
                    CHECK (position >= 0),
                added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (collection_id, media_id),
                FOREIGN KEY (collection_id)
                    REFERENCES filmium_collections (id)
                    ON DELETE CASCADE,
                FOREIGN KEY (media_id)
                    REFERENCES filmium_media_items (id)
                    ON DELETE CASCADE
            )
            """,
            """
            CREATE INDEX filmium_collection_items_media_id_index
            ON filmium_collection_items (media_id)
            """,
        ),
    )
