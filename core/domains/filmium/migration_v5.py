from core.database import DatabaseMigration

# ==========          FILMIUM MIGRACIJA VERZIJE 5          ==========

FILMIUM_MIGRATION_V5 = DatabaseMigration(
        scope="filmium",
        version=5,
        name="create_activity_log",
        statements=(
            """
            CREATE TABLE filmium_activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                entity_type TEXT NOT NULL
                    CHECK (
                        entity_type IN (
                            'media',
                            'collection'
                        )
                    ),
                entity_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE INDEX filmium_activity_created_at_index
            ON filmium_activity (created_at DESC, id DESC)
            """,
            """
            CREATE INDEX filmium_activity_entity_index
            ON filmium_activity (
                entity_type,
                entity_id
            )
            """,
            """
            CREATE INDEX filmium_activity_event_type_index
            ON filmium_activity (event_type)
            """,
        ),
    )
