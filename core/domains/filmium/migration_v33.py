from core.database import DatabaseMigration

# ==========          VIŠE NADZIRANIH FOLDERA          ==========
#
# `watch_folder` (jedna putanja) postaje `watch_folders` — spisak putanja
# razdvojen novim redom. Nov red se koristi namerno: putanja sme da sadrži
# zarez, pa bi zarez kao razdvajač razbio ime foldera.
#
# Stara kolona ostaje u tabeli, ali je ništa više ne čita: ovde se njena
# vrednost jednokratno prepisuje u novu, da postojeće podešavanje ne nestane.

FILMIUM_MIGRATION_V33 = DatabaseMigration(
    scope="filmium",
    version=33,
    name="torrent_watch_folders",
    statements=(
        """
        ALTER TABLE filmium_torrent_settings
        ADD COLUMN watch_folders TEXT NOT NULL DEFAULT ''
        """,
        """
        UPDATE filmium_torrent_settings
        SET watch_folders = watch_folder
        WHERE watch_folders = '' AND watch_folder <> ''
        """,
    ),
)
