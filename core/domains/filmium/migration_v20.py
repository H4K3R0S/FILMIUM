from core.database import DatabaseMigration

# ==========          ENGLESKI NASLOV + OPIS (TMDB)          ==========
#
# Postojeće kolone: `title` = lokalni naslov (sr/hr/bs, fallback en),
# `original_title` = izvorni (TMDB original), `notes` = lokalni opis.
# Dodajemo engleski naslov i engleski opis (TMDB en-US) da uporedo čuvamo
# lokalnu i englesku verziju.

FILMIUM_MIGRATION_V20 = DatabaseMigration(
    scope="filmium",
    version=20,
    name="add_english_title_and_description",
    statements=(
        """
        ALTER TABLE filmium_media_items
        ADD COLUMN english_title TEXT
        """,
        """
        ALTER TABLE filmium_media_items
        ADD COLUMN english_description TEXT
        """,
    ),
)
