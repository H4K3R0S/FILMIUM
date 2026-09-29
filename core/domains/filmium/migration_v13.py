from core.database import DatabaseMigration

# ==========          FILMIUM MIGRACIJA VERZIJE 13          ==========

FILMIUM_MIGRATION_V13 = DatabaseMigration(
        scope="filmium",
        version=13,
        name="create_media_localizations",
        statements=(
            """
            ALTER TABLE filmium_media_items
            ADD COLUMN origin_scope TEXT NOT NULL DEFAULT 'unknown'
                CHECK (
                    origin_scope IN (
                        'unknown',
                        'domestic',
                        'foreign'
                    )
                )
            """,
            """
            ALTER TABLE filmium_media_items
            ADD COLUMN original_language_code TEXT
                CHECK (
                    original_language_code IS NULL
                    OR length(trim(original_language_code))
                        BETWEEN 2 AND 35
                )
            """,
            """
            CREATE INDEX filmium_media_items_origin_scope_index
            ON filmium_media_items (
                origin_scope,
                title COLLATE NOCASE
            )
            """,
            """
            CREATE TABLE filmium_media_localizations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                media_id INTEGER NOT NULL,
                source_id INTEGER,
                localization_type TEXT NOT NULL
                    CHECK (
                        localization_type IN (
                            'subtitle',
                            'dubbed_audio'
                        )
                    ),
                language_code TEXT NOT NULL COLLATE NOCASE,
                label TEXT,
                is_primary INTEGER NOT NULL DEFAULT 0
                    CHECK (is_primary IN (0, 1)),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CHECK (
                    length(trim(language_code))
                    BETWEEN 2 AND 35
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
            CREATE UNIQUE INDEX filmium_media_localizations_identity_index
            ON filmium_media_localizations (
                media_id,
                IFNULL(source_id, -1),
                localization_type,
                language_code COLLATE NOCASE,
                IFNULL(label, '') COLLATE NOCASE
            )
            """,
            """
            CREATE INDEX filmium_media_localizations_filter_index
            ON filmium_media_localizations (
                localization_type,
                language_code COLLATE NOCASE,
                media_id
            )
            """,
            """
            CREATE INDEX filmium_media_localizations_source_index
            ON filmium_media_localizations (
                source_id,
                localization_type
            )
            """,
        ),
    )
