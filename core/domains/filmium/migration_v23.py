from core.database import DatabaseMigration

# ==========          FILMIUM MIGRACIJA VERZIJE 23          ==========

# Proširuje registar žanrova na 30+ kanonskih vrednosti. Postojeći redovi
# se ne diraju; novi se dodaju (ON CONFLICT osvežava aktivnost/redosled).
FILMIUM_MIGRATION_V23 = DatabaseMigration(
    scope="filmium",
    version=23,
    name="expand_genre_registry",
    statements=(
        """
        INSERT INTO filmium_genres (
            name,
            is_active,
            sort_order
        )
        VALUES
            ('Anime', 1, 210),
            ('Superheroj', 1, 220),
            ('Psihološki', 1, 230),
            ('Noar', 1, 240),
            ('Katastrofa', 1, 250),
            ('Špijunski', 1, 260),
            ('Post-apokalipsa', 1, 270),
            ('Slešer', 1, 280),
            ('Mračna komedija', 1, 290),
            ('Rijaliti', 1, 300),
            ('Sapunica', 1, 310),
            ('Kratki film', 1, 320),
            ('TV film', 1, 330),
            ('Vesti', 1, 340)
        ON CONFLICT(name) DO UPDATE SET
            is_active = excluded.is_active,
            sort_order = excluded.sort_order
        """,
    ),
)
