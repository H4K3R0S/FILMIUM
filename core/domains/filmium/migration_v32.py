from core.database import DatabaseMigration

# ==========          TORRENTI (MODUL 6)          ==========
#
# Tri tabele: torrenti koje je modul dodao, njihovi fajlovi sa štikliranjem,
# i jedan red podešavanja. Stanje samog preuzimanja drži qBittorrent; ovde
# se pamti šta je korisnik izabrao i odobrio.

FILMIUM_MIGRATION_V32 = DatabaseMigration(
    scope="filmium",
    version=32,
    name="add_torrents",
    statements=(
        """
        CREATE TABLE IF NOT EXISTS filmium_torrents (
            info_hash TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            source TEXT NOT NULL,
            source_kind TEXT NOT NULL,
            status TEXT NOT NULL,
            save_path TEXT NOT NULL DEFAULT '',
            total_bytes INTEGER NOT NULL DEFAULT 0,
            added_at TEXT NOT NULL,
            completed_at TEXT,
            error_message TEXT
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_filmium_torrents_status
        ON filmium_torrents (status)
        """,
        """
        CREATE TABLE IF NOT EXISTS filmium_torrent_files (
            info_hash TEXT NOT NULL,
            file_index INTEGER NOT NULL,
            path TEXT NOT NULL,
            size_bytes INTEGER NOT NULL DEFAULT 0,
            selected INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY (info_hash, file_index)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS filmium_torrent_settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            host TEXT NOT NULL DEFAULT '127.0.0.1',
            port INTEGER NOT NULL DEFAULT 8090,
            username TEXT NOT NULL DEFAULT '',
            password TEXT NOT NULL DEFAULT '',
            watch_folder TEXT NOT NULL DEFAULT '',
            download_path TEXT NOT NULL DEFAULT '',
            max_download_kbs INTEGER NOT NULL DEFAULT 0,
            max_upload_kbs INTEGER NOT NULL DEFAULT 0,
            max_active INTEGER NOT NULL DEFAULT 3,
            auto_start INTEGER NOT NULL DEFAULT 1,
            seed_after_complete INTEGER NOT NULL DEFAULT 0,
            delete_source_torrent INTEGER NOT NULL DEFAULT 0,
            unselected_extensions TEXT NOT NULL
                DEFAULT '.nfo,.txt,.url,.jpg,.png,.sfv'
        )
        """,
        """
        INSERT OR IGNORE INTO filmium_torrent_settings (id) VALUES (1)
        """,
    ),
)
