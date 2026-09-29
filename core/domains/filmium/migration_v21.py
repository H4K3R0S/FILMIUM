from core.database import DatabaseMigration

# ==========          KATEGORIJA SADRŽAJA (regular/animated/domestic)  ==========
#
# Prati ručni „FILM / ANIME / DOMAĆE" togle pri uvozu. Koristi se da preporuke
# (isti žanr i kasnije povezani) budu iz iste posebne kategorije kad je sadržaj
# animirani ili domaći.

FILMIUM_MIGRATION_V21 = DatabaseMigration(
    scope="filmium",
    version=21,
    name="add_content_category",
    statements=(
        """
        ALTER TABLE filmium_media_items
        ADD COLUMN content_category TEXT NOT NULL DEFAULT 'regular'
            CHECK (content_category IN ('regular', 'animated', 'domestic'))
        """,
    ),
)
