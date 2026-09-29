from core.database import DatabaseMigration

# ==========          EDITOR SETTINGS (JSON)          ==========
#
# Jedna JSON kolona koja čuva sva ostala editor polja koja nemaju svoju
# kolonu: mood tagovi, liste, pod-ocene (rejting profil), automatika/pristup
# toggeri, sync ofseti, IMDb/TVDB ID, franšiza, prioritet, preporuka,
# lična napomena, tip sadržaja, domaći naslovi (HR/BS), itd.

FILMIUM_MIGRATION_V25 = DatabaseMigration(
    scope="filmium",
    version=25,
    name="add_editor_settings",
    statements=(
        """
        ALTER TABLE filmium_media_items
        ADD COLUMN editor_settings TEXT NOT NULL DEFAULT '{}'
        """,
    ),
)
