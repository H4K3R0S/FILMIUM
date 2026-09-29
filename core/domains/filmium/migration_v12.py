from core.database import DatabaseMigration

# ==========          FILMIUM MIGRACIJA VERZIJE 12          ==========

FILMIUM_MIGRATION_V12 = DatabaseMigration(
        scope="filmium",
        version=12,
        name="create_sharing_profiles_and_queue",
        statements=(
            """
            ALTER TABLE filmium_media_items
            ADD COLUMN library_added_at TEXT
            """,
            """
            UPDATE filmium_media_items
            SET library_added_at = COALESCE(
                created_at,
                CURRENT_TIMESTAMP
            )
            WHERE library_added_at IS NULL
            """,
            """
            CREATE TRIGGER filmium_media_items_library_added_at_trigger
            AFTER INSERT ON filmium_media_items
            FOR EACH ROW
            WHEN NEW.library_added_at IS NULL
            BEGIN
                UPDATE filmium_media_items
                SET library_added_at = COALESCE(
                    NEW.created_at,
                    CURRENT_TIMESTAMP
                )
                WHERE id = NEW.id;
            END
            """,
            """
            CREATE INDEX filmium_media_items_library_added_at_index
            ON filmium_media_items (
                library_added_at DESC,
                id DESC
            )
            """,
            """
            CREATE TABLE filmium_share_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL COLLATE NOCASE UNIQUE,
                description TEXT,
                default_destination_folder TEXT NOT NULL DEFAULT 'VIDEOS',
                is_active INTEGER NOT NULL DEFAULT 1
                    CHECK (is_active IN (0, 1)),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CHECK (
                    length(trim(name)) BETWEEN 1 AND 100
                ),
                CHECK (
                    length(trim(default_destination_folder))
                    BETWEEN 1 AND 100
                )
            )
            """,
            """
            CREATE TABLE filmium_share_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                media_id INTEGER NOT NULL,
                transfer_mode TEXT NOT NULL DEFAULT 'playback'
                    CHECK (
                        transfer_mode IN (
                            'playback',
                            'complete'
                        )
                    ),
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK (
                        status IN (
                            'pending',
                            'transferring',
                            'completed',
                            'unavailable',
                            'insufficient_space',
                            'failed'
                        )
                    ),
                error_message TEXT,
                added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                completed_at TEXT,
                UNIQUE (profile_id, media_id),
                FOREIGN KEY (profile_id)
                    REFERENCES filmium_share_profiles (id)
                    ON DELETE CASCADE,
                FOREIGN KEY (media_id)
                    REFERENCES filmium_media_items (id)
                    ON DELETE CASCADE
            )
            """,
            """
            CREATE INDEX filmium_share_queue_profile_status_index
            ON filmium_share_queue (
                profile_id,
                status,
                added_at DESC
            )
            """,
            """
            CREATE INDEX filmium_share_queue_media_index
            ON filmium_share_queue (
                media_id,
                status
            )
            """,
        ),
    )
