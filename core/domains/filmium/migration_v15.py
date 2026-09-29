from core.database import DatabaseMigration

# ==========          TRAJNE I PRIVREMENE LOKACIJE          ==========

FILMIUM_MIGRATION_V15 = DatabaseMigration(
    scope="filmium",
    version=15,
    name="add_library_root_persistence",
    statements=(
        """
        ALTER TABLE filmium_library_roots
        ADD COLUMN is_persistent INTEGER NOT NULL DEFAULT 1
            CHECK (is_persistent IN (0, 1))
        """,
        """
        CREATE INDEX filmium_library_roots_persistence_index
        ON filmium_library_roots (is_persistent, is_enabled)
        """,
    ),
)
