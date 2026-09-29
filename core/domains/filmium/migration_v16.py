from core.database import DatabaseMigration

# ==========          IGNORISANI FOLDERI          ==========

FILMIUM_MIGRATION_V16 = DatabaseMigration(
    scope="filmium",
    version=16,
    name="add_ignored_directories",
    statements=(
        """
        CREATE TABLE filmium_ignored_directories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            library_root_id INTEGER NOT NULL,
            relative_directory TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (library_root_id, relative_directory),
            FOREIGN KEY (library_root_id)
                REFERENCES filmium_library_roots (id)
                ON DELETE CASCADE
        )
        """,
        """
        CREATE INDEX filmium_ignored_directories_root_index
        ON filmium_ignored_directories (library_root_id)
        """,
    ),
)
