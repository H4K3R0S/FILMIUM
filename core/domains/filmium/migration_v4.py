from core.database import DatabaseMigration

# ==========          FILMIUM MIGRACIJA VERZIJE 4          ==========

FILMIUM_MIGRATION_V4 = DatabaseMigration(
        scope="filmium",
        version=4,
        name="add_media_favorite",
        statements=(
            """
            ALTER TABLE filmium_media_items
            ADD COLUMN is_favorite INTEGER NOT NULL DEFAULT 0
                CHECK (is_favorite IN (0, 1))
            """,
            """
            CREATE INDEX filmium_media_items_favorite_index
            ON filmium_media_items (is_favorite)
            """,
        ),
    )
