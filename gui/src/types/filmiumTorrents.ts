// ==========          TIPOVI: FILMIUM TORRENTI          ==========

export type TorrentStatus =
  | "detected"
  | "metadata_fetching"
  | "awaiting_approval"
  | "downloading"
  | "paused"
  | "completed"
  | "error";

export type Torrent = {
  info_hash: string;
  name: string;
  source_kind: "magnet" | "file";
  status: TorrentStatus;
  save_path: string;
  total_bytes: number;
  added_at: string;
  completed_at: string | null;
  error_message: string | null;
  /** Kopija .torrent fajla u CORE-u; prazno kad kopije nema. */
  archived_path: string;
};

export type TorrentFile = {
  file_index: number;
  path: string;
  size_bytes: number;
  selected: boolean;
  /** Napredak pojedinačnog fajla (0.0–1.0); 0 dok klijent ne javi. */
  progress: number;
};

/** Fajl unutar pronađenog .torrent zapisa (pročitan lokalno). */
export type DiscoveredFile = {
  file_index: number;
  path: string;
  size_bytes: number;
};

/**
 * Kartica pronađenog .torrent fajla iz nadziranog foldera.
 *
 * `status` je `null` dok torrent postoji samo kao fajl; kad je predat
 * qBittorrent-u, nosi status zapisa iz baze.
 */
export type DiscoveredTorrent = {
  source_path: string;
  info_hash: string;
  name: string;
  total_bytes: number;
  files: DiscoveredFile[];
  status: TorrentStatus | null;
  /** Da li je torrent već poslat ka ekranu uvoza u biblioteku. */
  handed_to_library: boolean;
};

export type TorrentHealth = {
  engine_available: boolean;
  version: string | null;
  message: string | null;
};

export type TorrentSettings = {
  host: string;
  port: number;
  username: string;
  has_password: boolean;
  watch_folders: string[];
  download_path: string;
  max_download_kbs: number;
  max_upload_kbs: number;
  max_active: number;
  auto_start: boolean;
  seed_after_complete: boolean;
  delete_source_torrent: boolean;
  unselected_extensions: string[];
};

/** Telo PUT zahteva; `password` se šalje samo kad se menja. */
export type TorrentSettingsRequest = Omit<TorrentSettings, "has_password"> & {
  password?: string;
};

/** Normalizovan progres, onako kako ga hook izlaže komponentama. */
export type TorrentProgress = {
  infoHash: string;
  progress: number;
  downloadRate: number;
  uploadRate: number;
  etaSeconds: number | null;
  seeds: number;
  peers: number;
  isFinished: boolean;
  isPaused: boolean;
};


/** Ishod grupne radnje (pokreni sve / pauziraj sve). */
export type TorrentBulk = {
  affected: number;
  failed: number;
};


/** Ishod otvaranja foldera sa preuzetim sadržajem. */
export type TorrentReveal = {
  revealed: boolean;
  folder: string;
};
