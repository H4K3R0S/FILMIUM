from core.database import DatabaseMigration

# ==========          PREDAJA UVOZU U BIBLIOTEKU          ==========
#
# Jedan red po torrentu koji je korisnik poslao ka ekranu uvoza. Tabela je
# odvojena od `filmium_torrents` NAMERNO: zapis o preuzimanju se uklanja
# („X" na kartici), a ovaj podatak mora da ga preživi — po njemu se posle
# odlučuje da li brisanje izvornog .torrent fajla traži potvrdu.

FILMIUM_MIGRATION_V35 = DatabaseMigration(
    scope="filmium",
    version=35,
    name="torrent_library_handoffs",
    statements=(
        """
        CREATE TABLE IF NOT EXISTS filmium_torrent_handoffs (
            info_hash TEXT PRIMARY KEY,
            handed_at TEXT NOT NULL
        )
        """,
    ),
)
