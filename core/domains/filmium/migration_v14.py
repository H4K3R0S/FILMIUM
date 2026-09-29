from core.database import DatabaseMigration

# ==========          FILMIUM MIGRACIJA VERZIJE 14          ==========

FILMIUM_MIGRATION_V14 = DatabaseMigration(
        scope="filmium",
        version=14,
        name="create_subtitle_repair_queue",
        statements=(
            """
            CREATE TABLE filmium_subtitle_repair_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                media_id INTEGER,
                source_id INTEGER,
                file_path TEXT NOT NULL COLLATE NOCASE UNIQUE,
                file_name TEXT NOT NULL,
                source_sha256 TEXT NOT NULL,
                detected_encoding TEXT NOT NULL,
                detected_language_code TEXT,
                language_confidence REAL NOT NULL DEFAULT 0
                    CHECK (
                        language_confidence BETWEEN 0 AND 1
                    ),
                issue_count INTEGER NOT NULL DEFAULT 0
                    CHECK (issue_count >= 0),
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK (
                        status IN (
                            'pending',
                            'reviewed',
                            'repaired',
                            'dismissed',
                            'ignored'
                        )
                    ),
                discovered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                reviewed_at TEXT,
                resolved_at TEXT,
                FOREIGN KEY (media_id)
                    REFERENCES filmium_media_items (id)
                    ON DELETE SET NULL,
                FOREIGN KEY (source_id)
                    REFERENCES filmium_media_sources (id)
                    ON DELETE SET NULL
            )
            """,
            """
            CREATE INDEX filmium_subtitle_repair_queue_status_index
            ON filmium_subtitle_repair_queue (
                status,
                discovered_at DESC,
                id DESC
            )
            """,
            """
            CREATE INDEX filmium_subtitle_repair_queue_media_index
            ON filmium_subtitle_repair_queue (
                media_id,
                status
            )
            """,
            """
            CREATE INDEX filmium_subtitle_repair_queue_source_index
            ON filmium_subtitle_repair_queue (
                source_id,
                status
            )
            """,
        ),
    )
