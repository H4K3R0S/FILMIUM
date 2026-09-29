from core.database import DatabaseMigration

# ==========          GLUMCI (TMDB cast) — za preporuke po akteru  ==========
#
# JSON lista imena glavnih glumaca (top N sa TMDB-a). Koristi se za preporuku
# „Filmovi/Serije sa istim akterom". Karakter-bazirano prepoznavanje dolazi
# kasnije (kroz „Izmeni sadržaj").

FILMIUM_MIGRATION_V22 = DatabaseMigration(
    scope="filmium",
    version=22,
    name="add_cast_names",
    statements=(
        """
        ALTER TABLE filmium_media_items
        ADD COLUMN cast_names TEXT NOT NULL DEFAULT '[]'
        """,
    ),
)
