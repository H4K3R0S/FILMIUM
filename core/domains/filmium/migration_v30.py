from core.database import DatabaseMigration

# ==========          TMDB RELATED NA KATALOGU          ==========
#
# Čuva TMDB „recommendations" (povezani naslovi) kao JSON tekst uz sadržaj,
# da detalj-stranica prikaže „Povezani filmovi/serije". Postojeći redovi
# ostaju NULL dok se ne dopune (uvoz/auto-update) — puni se samo unapred.

FILMIUM_MIGRATION_V30 = DatabaseMigration(
    scope="filmium",
    version=30,
    name="add_media_related_tmdb",
    statements=(
        """
        ALTER TABLE filmium_media_items
        ADD COLUMN related_tmdb TEXT
        """,
    ),
)
