from core.database import DatabaseMigration

# ==========          STUDIO / REŽISER / SINHRONIZACIJA          ==========
#
# Dodaje kolone koje editor sada snima:
#  - studio, director (iz TMDB-a ili ručno),
#  - is_synchronized: da li je sadržaj sinhronizovan (0 = titlovan, 1 = SINH).
# content_category (Film/Anime/Domaće) je već dodat ranije (v21).

FILMIUM_MIGRATION_V24 = DatabaseMigration(
    scope="filmium",
    version=24,
    name="add_studio_director_synchronized",
    statements=(
        """
        ALTER TABLE filmium_media_items
        ADD COLUMN studio TEXT
        """,
        """
        ALTER TABLE filmium_media_items
        ADD COLUMN director TEXT
        """,
        """
        ALTER TABLE filmium_media_items
        ADD COLUMN is_synchronized INTEGER NOT NULL DEFAULT 0
            CHECK (is_synchronized IN (0, 1))
        """,
    ),
)
