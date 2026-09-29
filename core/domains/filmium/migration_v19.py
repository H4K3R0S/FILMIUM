from core.database import DatabaseMigration

# ==========          AUTO-IMPORT (praćenje foldera)          ==========

FILMIUM_MIGRATION_V19 = DatabaseMigration(
    scope="filmium",
    version=19,
    name="add_auto_import_tables",
    statements=(
        """
        CREATE TABLE filmium_auto_import_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            folder_path TEXT NOT NULL UNIQUE,
            file_types TEXT NOT NULL,              -- JSON lista ekstenzija
            min_size_mb INTEGER NOT NULL DEFAULT 100,
            auto_scan INTEGER NOT NULL DEFAULT 1,
            auto_import INTEGER NOT NULL DEFAULT 0,
            target_library_id INTEGER,             -- opciono, biblioteka odredišta
            security_scan INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE filmium_monitored_folders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            folder_path TEXT NOT NULL UNIQUE,
            is_active INTEGER NOT NULL DEFAULT 1,
            last_check TEXT,
            rule_id INTEGER,
            FOREIGN KEY (rule_id)
                REFERENCES filmium_auto_import_rules (id)
                ON DELETE CASCADE
        )
        """,
        """
        CREATE TABLE filmium_detected_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT NOT NULL UNIQUE,
            file_size INTEGER NOT NULL,
            detected_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            status TEXT NOT NULL DEFAULT 'detected',
            scan_result TEXT,                      -- JSON rezultat skeniranja
            security_status TEXT NOT NULL DEFAULT 'unknown',
            rule_id INTEGER,
            FOREIGN KEY (rule_id)
                REFERENCES filmium_auto_import_rules (id)
                ON DELETE SET NULL
        )
        """,
        """
        CREATE INDEX filmium_detected_files_status_index
        ON filmium_detected_files (status)
        """,
    ),
)
