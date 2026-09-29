from core.database import DatabaseMigration

# ==========          FILMIUM MIGRACIJA VERZIJE 11          ==========

FILMIUM_MIGRATION_V11 = DatabaseMigration(
        scope="filmium",
        version=11,
        name="create_media_artwork_registry",
        statements=(
            """
            ALTER TABLE filmium_media_files
            RENAME TO filmium_media_files_legacy
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
                            'wallpaper',
                            'fanart',
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
            INSERT INTO filmium_media_files (
                id,
                source_id,
                role,
                relative_path,
                language,
                size_bytes,
                modified_at,
                file_status,
                created_at,
                updated_at
            )
            SELECT
                id,
                source_id,
                role,
                relative_path,
                language,
                size_bytes,
                modified_at,
                file_status,
                created_at,
                updated_at
            FROM filmium_media_files_legacy
            """,
            """
            DROP TABLE filmium_media_files_legacy
            """,
            """
            CREATE INDEX filmium_media_files_source_role_index
            ON filmium_media_files (
                source_id,
                role,
                file_status
            )
            """,
            """
            CREATE TABLE filmium_media_artworks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                media_id INTEGER NOT NULL,
                source_id INTEGER,
                artwork_type TEXT NOT NULL
                    CHECK (
                        artwork_type IN (
                            'poster',
                            'backdrop',
                            'wallpaper',
                            'fanart',
                            'logo',
                            'episode_still'
                        )
                    ),
                storage_kind TEXT NOT NULL
                    CHECK (
                        storage_kind IN (
                            'source',
                            'managed'
                        )
                    ),
                relative_path TEXT NOT NULL COLLATE NOCASE,
                label TEXT,
                width_pixels INTEGER
                    CHECK (
                        width_pixels IS NULL
                        OR width_pixels > 0
                    ),
                height_pixels INTEGER
                    CHECK (
                        height_pixels IS NULL
                        OR height_pixels > 0
                    ),
                file_size_bytes INTEGER NOT NULL DEFAULT 0
                    CHECK (file_size_bytes >= 0),
                is_primary INTEGER NOT NULL DEFAULT 0
                    CHECK (is_primary IN (0, 1)),
                sort_order INTEGER NOT NULL DEFAULT 0
                    CHECK (sort_order >= 0),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CHECK (
                    (
                        storage_kind = 'source'
                        AND source_id IS NOT NULL
                    )
                    OR (
                        storage_kind = 'managed'
                        AND source_id IS NULL
                    )
                ),
                FOREIGN KEY (media_id)
                    REFERENCES filmium_media_items (id)
                    ON DELETE CASCADE,
                FOREIGN KEY (source_id)
                    REFERENCES filmium_media_sources (id)
                    ON DELETE CASCADE
            )
            """,
            """
            CREATE UNIQUE INDEX filmium_media_artworks_identity_index
            ON filmium_media_artworks (
                media_id,
                artwork_type,
                storage_kind,
                IFNULL(source_id, -1),
                relative_path COLLATE NOCASE
            )
            """,
            """
            CREATE INDEX filmium_media_artworks_media_index
            ON filmium_media_artworks (
                media_id,
                artwork_type,
                is_primary DESC,
                sort_order,
                id
            )
            """,
            """
            CREATE INDEX filmium_media_artworks_source_index
            ON filmium_media_artworks (
                source_id,
                artwork_type
            )
            """,
        ),
    )
