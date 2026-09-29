from core.database import DatabaseMigration

# ==========          TMDB ID NA KATALOGU          ==========
#
# Čuva TMDB ID uz sadržaj kataloga kako bi lista „za preuzeti" mogla
# pouzdano (nezavisno od jezika naslova) da prepozna da je željeni naslov
# ušao u biblioteku i da se automatski ukloni. Postojeći redovi ostaju
# NULL dok se ne dopune (uvoz/auto-update).

FILMIUM_MIGRATION_V29 = DatabaseMigration(
    scope="filmium",
    version=29,
    name="add_media_tmdb_id",
    statements=(
        """
        ALTER TABLE filmium_media_items
        ADD COLUMN tmdb_id INTEGER
        """,
    ),
)
