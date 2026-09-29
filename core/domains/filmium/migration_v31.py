from core.database import DatabaseMigration

# ==========          NASLOVI NA LISTI „ZA PREUZETI"          ==========
#
# Dodaje originalni i domaći naslov uz stavku liste za preuzimanje, da bi
# se uz „ime filma" mogli uneti i sačuvati posebni naslovi (npr. iz TMDB
# pretrage ili ručno). Postojeći redovi ostaju NULL.

FILMIUM_MIGRATION_V31 = DatabaseMigration(
    scope="filmium",
    version=31,
    name="add_wishlist_titles",
    statements=(
        """
        ALTER TABLE filmium_wishlist
        ADD COLUMN original_title TEXT
        """,
        """
        ALTER TABLE filmium_wishlist
        ADD COLUMN local_title TEXT
        """,
    ),
)
