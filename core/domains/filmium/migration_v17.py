from core.database import DatabaseMigration

# ==========          GLAVNI DISK          ==========

FILMIUM_MIGRATION_V17 = DatabaseMigration(
    scope="filmium",
    version=17,
    name="add_library_root_is_main",
    statements=(
        """
        ALTER TABLE filmium_library_roots
        ADD COLUMN is_main INTEGER NOT NULL DEFAULT 0
            CHECK (is_main IN (0, 1))
        """,
    ),
)
