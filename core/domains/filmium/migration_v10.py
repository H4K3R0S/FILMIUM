from core.database import DatabaseMigration

# ==========          FILMIUM MIGRACIJA VERZIJE 10          ==========

FILMIUM_MIGRATION_V10 = DatabaseMigration(
        scope="filmium",
        version=10,
        name="create_media_sources",
        statements=(
            """
            CREATE TABLE filmium_media_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                media_id INTEGER NOT NULL,
                library_root_id INTEGER,
                root_path_snapshot TEXT NOT NULL COLLATE NOCASE,
                relative_directory TEXT NOT NULL COLLATE NOCASE,
                manifest_path TEXT NOT NULL DEFAULT 'filmium_info.json',
                availability_status TEXT NOT NULL DEFAULT 'available'
                    CHECK (
                        availability_status IN (
                            'available',
                            'offline',
                            'missing'
                        )
                    ),
                last_verified_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (
                    media_id,
                    root_path_snapshot,
                    relative_directory
                ),
                FOREIGN KEY (media_id)
                    REFERENCES filmium_media_items (id)
                    ON DELETE CASCADE,
                FOREIGN KEY (library_root_id)
                    REFERENCES filmium_library_roots (id)
                    ON DELETE SET NULL
            )
            """,
            """
            CREATE TABLE filmium_media_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id INTEGER NOT NULL,
                role TEXT NOT NULL
                    CHECK (
                        role IN (
                            'video',
                            'poster',
                            'backdrop',
                            'trailer',
                            'subtitle',
                            'manifest',
                            'unknown'
                        )
                    ),
                relative_path TEXT NOT NULL COLLATE NOCASE,
                language TEXT,
                size_bytes INTEGER NOT NULL DEFAULT 0
                    CHECK (size_bytes >= 0),
                modified_at TEXT,
                file_status TEXT NOT NULL DEFAULT 'available'
                    CHECK (
                        file_status IN (
                            'available',
                            'offline',
                            'missing'
                        )
                    ),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (source_id, relative_path),
                FOREIGN KEY (source_id)
                    REFERENCES filmium_media_sources (id)
                    ON DELETE CASCADE
            )
            """,
            """
            CREATE INDEX filmium_media_sources_media_index
            ON filmium_media_sources (
                media_id,
                availability_status
            )
            """,
            """
            CREATE INDEX filmium_media_sources_library_root_index
            ON filmium_media_sources (
                library_root_id,
                relative_directory COLLATE NOCASE
            )
            """,
            """
            CREATE INDEX filmium_media_files_source_role_index
            ON filmium_media_files (
                source_id,
                role,
                file_status
            )
            """,
        ),
    )
