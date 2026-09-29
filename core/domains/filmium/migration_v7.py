from core.database import DatabaseMigration

# ==========          FILMIUM MIGRACIJA VERZIJE 7          ==========

FILMIUM_MIGRATION_V7 = DatabaseMigration(
        scope="filmium",
        version=7,
        name="add_media_runtime",
        statements=(
            """
            ALTER TABLE filmium_media_items
            ADD COLUMN runtime_minutes INTEGER
                CHECK (
                    runtime_minutes IS NULL
                    OR runtime_minutes BETWEEN 1 AND 10000
                )
            """,
        ),
    )
