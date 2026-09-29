from core.database import DatabaseMigration

# ==========          ARHIVIRAN .torrent FAJL          ==========
#
# Putanja do kopije .torrent fajla unutar CORE-a. Nadzirani folder je
# korisnikov i tamo izvorni fajl ume da nestane; kopija ostaje dok postoji
# zapis o torrentu, pa se preuzimanje uvek može ponoviti.
#
# Prazna niska znači „nema kopije" (stariji zapisi, ili izvor koji u
# trenutku dodavanja nije bio čitljiv).

FILMIUM_MIGRATION_V34 = DatabaseMigration(
    scope="filmium",
    version=34,
    name="torrent_archived_path",
    statements=(
        """
        ALTER TABLE filmium_torrents
        ADD COLUMN archived_path TEXT NOT NULL DEFAULT ''
        """,
    ),
)
