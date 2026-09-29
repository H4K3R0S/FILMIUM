from core.database import DatabaseMigration

# ==========          FILMIUM MIGRACIJA VERZIJE 9          ==========

FILMIUM_MIGRATION_V9 = DatabaseMigration(
        scope="filmium",
        version=9,
        name="create_library_roots",
        statements=(
            """
            CREATE TABLE filmium_library_roots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL COLLATE NOCASE UNIQUE,
                path TEXT NOT NULL COLLATE NOCASE UNIQUE,
                volume_id TEXT,
                volume_label TEXT,
                is_enabled INTEGER NOT NULL DEFAULT 1
                    CHECK (is_enabled IN (0, 1)),
                last_scan_status TEXT NOT NULL DEFAULT 'never_scanned'
                    CHECK (
                        last_scan_status IN (
                            'never_scanned',
                            'available',
                            'offline',
                            'disabled'
                        )
                    ),
                last_scanned_at TEXT,
                last_seen_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE INDEX filmium_library_roots_enabled_index
            ON filmium_library_roots (
                is_enabled,
                name COLLATE NOCASE
            )
            """,
            """
            CREATE INDEX filmium_library_roots_volume_index
            ON filmium_library_roots (
                volume_id,
                volume_label COLLATE NOCASE
            )
            """,
            """
            CREATE INDEX filmium_library_roots_status_index
            ON filmium_library_roots (
                last_scan_status,
                last_scanned_at DESC
            )
            """,
        ),
    )
