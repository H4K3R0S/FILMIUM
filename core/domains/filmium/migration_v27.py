from core.database import DatabaseMigration

# ==========          KEYWORDS + BELONGS_TO_COLLECTION          ==========
#
# TMDB ključne reči (JSON lista imena) i naziv kolekcije kojoj film
# pripada (belongs_to_collection). Serije nemaju kolekciju — polje ostaje
# NULL. Keywords se čuva kao JSON lista radi doslednosti sa cast_names.

FILMIUM_MIGRATION_V27 = DatabaseMigration(
    scope="filmium",
    version=27,
    name="add_keywords_collection",
    statements=(
        """
        ALTER TABLE filmium_media_items
        ADD COLUMN keywords TEXT NOT NULL DEFAULT '[]'
        """,
        """
        ALTER TABLE filmium_media_items
        ADD COLUMN collection TEXT
        """,
    ),
)
