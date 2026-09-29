// ==========          FILMIUM MEDIA SOURCE TIPOVI          ==========

/**
 * Uloge datoteka unutar jednog filmskog direktorijuma.
 *
 * Vrednosti prate backend enum `MediaFileRole`.
 */
export type FilmiumMediaFileRole =
  | "video"
  | "poster"
  | "backdrop"
  | "wallpaper"
  | "fanart"
  | "trailer"
  | "subtitle"
  | "manifest"
  | "unknown";

/**
 * Trenutno stanje jedne indeksirane datoteke ili izvora.
 *
 * Vrednosti prate backend enum `MediaFileStatus`.
 */
export type FilmiumMediaFileStatus =
  | "available"
  | "offline"
  | "missing";


// ==========          DATOTEKA IZVORA          ==========

export interface FilmiumMediaFile {
  id: number;
  source_id: number;
  role: FilmiumMediaFileRole;
  relative_path: string;
  language: string | null;
  size_bytes: number;
  modified_at: string | null;
  file_status: FilmiumMediaFileStatus;
  created_at: string;
  updated_at: string;
}


// ==========          IZVOR SADRŽAJA          ==========

export interface FilmiumMediaSource {
  id: number;
  media_id: number;
  library_root_id: number | null;
  root_path_snapshot: string;
  relative_directory: string;
  manifest_path: string;
  availability_status: FilmiumMediaFileStatus;
  last_verified_at: string | null;
  created_at: string;
  updated_at: string;
  files: FilmiumMediaFile[];
}
