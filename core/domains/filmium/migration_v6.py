from core.database import DatabaseMigration

# ==========          FILMIUM MIGRACIJA VERZIJE 6          ==========

FILMIUM_MIGRATION_V6 = DatabaseMigration(
        scope="filmium",
        version=6,
        name="add_media_visual_assets",
        statements=(
            """
            ALTER TABLE filmium_media_items
            ADD COLUMN poster_path TEXT
            """,
            """
            ALTER TABLE filmium_media_items
            ADD COLUMN backdrop_path TEXT
            """,
        ),
    )
