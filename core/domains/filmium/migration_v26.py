from core.database import DatabaseMigration

# ==========          POSTER/BACKDROP PO SEZONI          ==========
#
# Svaka sezona serije ima svoj poster i backdrop. Serija na kartici
# prikazuje sliku sezone 1 (default), a na stranici detalja slika se menja
# prema izabranoj sezoni.

FILMIUM_MIGRATION_V26 = DatabaseMigration(
    scope="filmium",
    version=26,
    name="add_season_visual_assets",
    statements=(
        """
        ALTER TABLE filmium_seasons
        ADD COLUMN poster_path TEXT
        """,
        """
        ALTER TABLE filmium_seasons
        ADD COLUMN backdrop_path TEXT
        """,
    ),
)
