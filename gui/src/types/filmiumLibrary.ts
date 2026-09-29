export type LibraryRootScanStatus =
  | "never_scanned"
  | "available"
  | "offline"
  | "disabled";

export interface FilmiumLibraryRoot {
  id: number;
  name: string;
  path: string;
  volume_id: string | null;
  volume_label: string | null;
  is_enabled: boolean;
  is_persistent?: boolean;
  is_main?: boolean;
  last_scan_status: LibraryRootScanStatus;
  last_scanned_at: string | null;
  last_seen_at: string | null;
  created_at: string;
  updated_at: string;
  total_bytes?: number | null;
  free_bytes?: number | null;
}

export interface FilmiumLibraryRootRequest {
  name: string;
  path: string;
  volume_id?: string | null;
  volume_label?: string | null;
  is_enabled?: boolean;
  is_persistent?: boolean;
}

export interface FilmiumLibraryFolderScan {
  directory: string;
  title: string | null;
  release_year: number | null;
  can_import: boolean;
  catalog_status?:
    | "new"
    | "catalog_only"
    | "available"
    | "unavailable"
    | "ambiguous";
  matching_media_ids?: number[];
  warnings: string[];
  error_message: string | null;
}

export interface FilmiumLibraryScanResult {
  root: string;
  status: "available" | "offline" | "disabled";
  discovered_count: number;
  importable_count: number;
  problem_count: number;
  ignored_file_count: number;
  discovered_subtitle_count: number;
  inspected_subtitle_count: number;
  clean_subtitle_count: number;
  subtitle_repair_count: number;
  queued_subtitle_count: number;
  unsupported_subtitle_count: number;
  subtitle_scan_warnings: string[];
  warnings: string[];
  entries: FilmiumLibraryFolderScan[];
}


// ==========          IMPORT PREVIEW          ==========

export interface FilmiumImportPreviewFile {
  relative_path: string;
  role: string;
  size_bytes: number;
  language: string | null;
}

export interface FilmiumImportPreviewAction {
  action_type: string;
  source: string | null;
  destination: string;
  reason: string;
}

export interface FilmiumImportTechnicalInfo {
  width: number | null;
  height: number | null;
  video_codec: string | null;
  frame_rate: number | null;
  audio_codec: string | null;
  audio_channels: number | null;
  duration_seconds: number | null;
}

export interface FilmiumImportTmdbInfo {
  tmdb_id: number | null;
  original_title: string | null;
  english_title: string | null;
  english_overview: string | null;
  local_title: string | null;
  local_overview: string | null;
  year: number | null;
  genres: string[];
  rating: number | null;
  cast_names: string[];
  studio: string | null;
  director: string | null;
  vote_count: number | null;
  original_language: string | null;
  country: string | null;
  keywords: string[];
  collection: string | null;
}

export interface FilmiumLibraryImportPreview {
  library_root_id: number;
  relative_directory: string;
  title: string;
  original_title: string | null;
  media_type: "movie" | "series";
  release_year: number | null;
  runtime_minutes: number | null;
  description: string | null;
  genres: string[];
  unrecognized_genres: string[];
  studio: string | null;
  franchise: string | null;
  franchise_order: number | null;
  ownership_status: "owned" | "catalog_only";
  match_status: "new" | "existing" | "ambiguous";
  matching_media_ids: number[];
  planned_target_directory: string;
  detected_files: FilmiumImportPreviewFile[];
  actions: FilmiumImportPreviewAction[];
  warnings: string[];
  blocking_warnings: string[];
  can_confirm: boolean;
  requires_organization: boolean;
  technical?: FilmiumImportTechnicalInfo | null;
  suggested_genres?: string[];
  // Puna TMDB dopuna (svi glumci/keywords/kolekcija) — samo kad je
  // zatražena (include_tmdb) pri „Prebaci sve".
  tmdb?: FilmiumImportTmdbInfo | null;
}


// Podešavanja koja „Prebaci sve" prenosi sa prve stavke na sve izabrane.
export interface FilmiumBulkImportSettings {
  contentMode: "regular" | "animated" | "domestic";
  synchronized: boolean;
  targetRootId: number;
}


// ==========          POTVRDJENI UVOZ          ==========

export type FilmiumImportConflictMode = "fail" | "skip" | "overwrite";

export interface FilmiumLibraryImportCommitRequest {
  relative_directory: string;
  confirmed: boolean;
  target_media_id?: number | null;
  target_library_root_id?: number | null;
  title?: string;
  release_year?: number | null;
  genres?: string[];
  conflict_mode?: FilmiumImportConflictMode;
  content_mode?: "regular" | "animated" | "domestic";
  synchronized?: boolean;
}

// Izmene koje korisnik napravi u panelu pre potvrde uvoza.
export interface FilmiumImportOverrides {
  title?: string;
  release_year?: number | null;
  genres?: string[];
  target_library_root_id?: number | null;
}

export interface FilmiumLibraryImportCommitResult {
  media_id: number;
  source_id: number;
  title: string;
  media_type: "movie" | "series";
  relative_directory: string;
  artwork_ids: number[];
  created_media: boolean;
  created_source: boolean;
  moved_file_count: number;
  created_directory_count: number;
}
