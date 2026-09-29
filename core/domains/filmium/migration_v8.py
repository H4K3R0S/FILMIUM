from core.database import DatabaseMigration

# ==========          FILMIUM MIGRACIJA VERZIJE 8          ==========

FILMIUM_MIGRATION_V8 = DatabaseMigration(
        scope="filmium",
        version=8,
        name="create_genre_registry",
        statements=(
            """
            ALTER TABLE filmium_genres
            ADD COLUMN is_active INTEGER NOT NULL DEFAULT 0
                CHECK (is_active IN (0, 1))
            """,
            """
            ALTER TABLE filmium_genres
            ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0
                CHECK (sort_order >= 0)
            """,
            """
            INSERT INTO filmium_genres (
                name,
                is_active,
                sort_order
            )
            VALUES
                ('Akcija', 1, 10),
                ('Animacija', 1, 20),
                ('Avantura', 1, 30),
                ('Biografski', 1, 40),
                ('Dokumentarni', 1, 50),
                ('Drama', 1, 60),
                ('Fantazija', 1, 70),
                ('Horor', 1, 80),
                ('Istorijski', 1, 90),
                ('Komedija', 1, 100),
                ('Kriminalistički', 1, 110),
                ('Misterija', 1, 120),
                ('Muzički', 1, 130),
                ('Naučna fantastika', 1, 140),
                ('Porodični', 1, 150),
                ('Ratni', 1, 160),
                ('Romansa', 1, 170),
                ('Sportski', 1, 180),
                ('Triler', 1, 190),
                ('Vestern', 1, 200)
            ON CONFLICT(name) DO UPDATE SET
                is_active = excluded.is_active,
                sort_order = excluded.sort_order
            """,
            """
            CREATE INDEX filmium_genres_active_order_index
            ON filmium_genres (
                is_active,
                sort_order,
                name COLLATE NOCASE
            )
            """,
        ),
    )
