import {
  deleteRequest,
  getJson,
  patchJson,
  postFormData,
  postJson,
  postRequest,
  postSse,
  type SseProgress,
} from "./httpClient";

import type {
  FilmiumMediaSource,
} from "../types/filmiumMediaSource";
import type { ExternalRatingsData, MediaItem } from "../types/filmium";


// ==========          FILMIUM MEDIA SOURCE API          ==========

/**
 * Učitava sve registrovane izvore (diskove/foldere) jednog FILMIUM sadržaja.
 *
 * Vraća listu izvora zajedno sa njihovim datotekama (video, prevodi,
 * posteri, backdrops...) i statusom dostupnosti.
 */
export function getFilmiumMediaSources(
  mediaId: number,
): Promise<FilmiumMediaSource[]> {
  return getJson<FilmiumMediaSource[]>(
    `/api/v1/filmium/media/${mediaId}/sources`,
  );
}

/**
 * Ponovo skenira registrovani folder jednog FILMIUM izvora.
 */
export function rescanFilmiumMediaSource(
  sourceId: number,
): Promise<FilmiumMediaSource> {
  return postRequest<FilmiumMediaSource>(
    `/api/v1/filmium/media-sources/${sourceId}/rescan`,
  );
}

/**
 * Dodaje titl fajl u folder izvora (upisuje na disk + rescan).
 */
export function addSubtitleToSource(
  sourceId: number,
  file: File,
): Promise<FilmiumMediaSource> {
  const form = new FormData();
  form.append("file", file);
  return postFormData<FilmiumMediaSource>(
    `/api/v1/filmium/media-sources/${sourceId}/subtitles`,
    form,
  );
}

/**
 * Briše fizičku datoteku izvora (npr. titl) sa diska.
 */
export function deleteSourceFile(
  sourceId: number,
  fileId: number,
): Promise<FilmiumMediaSource> {
  return deleteRequest<FilmiumMediaSource>(
    `/api/v1/filmium/media-sources/${sourceId}/files/${fileId}`,
  );
}

/**
 * Kopira datoteku izvora na Desktop korisnika i vraća putanju.
 */
export function downloadSourceFileToDesktop(
  sourceId: number,
  fileId: number,
): Promise<{ path: string }> {
  return postRequest<{ path: string }>(
    `/api/v1/filmium/media-sources/${sourceId}/files/${fileId}/download`,
  );
}


export interface FilmiumEpisode {
  id: number;
  episode_number: number;
  title: string | null;
  runtime_minutes: number | null;
  watch_status: string;
  root_id: number | null;
  video_source: string | null;
}

export interface FilmiumSeason {
  id: number;
  season_number: number;
  name: string | null;
  poster_path: string | null;
  backdrop_path: string | null;
  episodes: FilmiumEpisode[];
}

/**
 * Menja polja jedne epizode (naslov / trajanje / status gledanja).
 */
export function updateFilmiumEpisode(
  mediaId: number,
  episodeId: number,
  body: {
    title?: string | null;
    runtime_minutes?: number | null;
    watch_status?: string;
  },
): Promise<FilmiumEpisode> {
  return patchJson<FilmiumEpisode, typeof body>(
    `/api/v1/filmium/media/${mediaId}/episodes/${episodeId}`,
    body,
  );
}

/**
 * Briše jednu epizodu iz kataloga.
 */
export function deleteFilmiumEpisode(
  mediaId: number,
  episodeId: number,
): Promise<void> {
  return deleteRequest<void>(
    `/api/v1/filmium/media/${mediaId}/episodes/${episodeId}`,
  );
}

/**
 * Učitava sezone jedne serije sa njihovim epizodama (za detaljnu stranicu).
 */
export function getFilmiumMediaSeasons(
  mediaId: number,
): Promise<FilmiumSeason[]> {
  return getJson<FilmiumSeason[]>(
    `/api/v1/filmium/media/${mediaId}/seasons`,
  );
}


export interface FilmiumTmdbEnrichment {
  available: boolean;
  matched: boolean;
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
  external_ratings: ExternalRatingsData | null;
}

/**
 * Traži sadržaj na TMDB-u i vraća podatke za dopunu editora.
 */
export function enrichFilmiumMediaFromTmdb(
  mediaId: number,
): Promise<FilmiumTmdbEnrichment> {
  return postRequest<FilmiumTmdbEnrichment>(
    `/api/v1/filmium/media/${mediaId}/tmdb-enrich`,
  );
}


export interface AutoUpdateResponse {
  matched: boolean;
  changed_fields: string[];
  message: string;
  item: MediaItem;
}

/**
 * „Updatuj": serverski dopuni naslov iz TMDB-a (naslov/opis na latinici,
 * ključne reči) i snimi u bazu. Opcioni override kad automatika promaši.
 */
export function autoUpdateFilmiumMedia(
  mediaId: number,
  body: { tmdb_id?: number; override_title?: string } = {},
): Promise<AutoUpdateResponse> {
  return postJson<AutoUpdateResponse, typeof body>(
    `/api/v1/filmium/media/${mediaId}/auto-update`,
    body,
  );
}


export interface FilmiumDisk {
  path: string;
  label: string;
  total_bytes: number;
  free_bytes: number;
}

export interface FilmiumDirEntry {
  name: string;
  path: string;
}

export interface FilmiumBrowse {
  path: string | null;
  parent: string | null;
  directories: FilmiumDirEntry[];
}

export interface FilmiumFileTreeItem {
  relative_path: string;
  role: string;
  size_bytes: number;
}

export interface FilmiumTransferResult {
  copied_files: number;
  total_bytes: number;
  destination: string;
}

/**
 * Dostupni diskovi/particije za prenos.
 */
export function getFilmiumDisks(): Promise<FilmiumDisk[]> {
  return getJson<FilmiumDisk[]>("/api/v1/filmium/disks");
}

/**
 * Navigacija foldera za izbor odredišta (prazan path = koreni diskova).
 */
export function browseFilmiumFilesystem(
  path?: string,
): Promise<FilmiumBrowse> {
  const query = path ? `?path=${encodeURIComponent(path)}` : "";
  return getJson<FilmiumBrowse>(
    `/api/v1/filmium/filesystem/browse${query}`,
  );
}

/**
 * Lista fajlova sadržaja (za stablo izbora pri prenosu).
 */
export function getFilmiumMediaFileTree(
  mediaId: number,
): Promise<FilmiumFileTreeItem[]> {
  return getJson<FilmiumFileTreeItem[]>(
    `/api/v1/filmium/media/${mediaId}/file-tree`,
  );
}

/**
 * Kopira ceo direktorijum ili izabrane fajlove sadržaja na odredište.
 */
export function transferFilmiumMedia(
  mediaId: number,
  destination: string,
  relativePaths: string[],
): Promise<FilmiumTransferResult> {
  return postJson<
    FilmiumTransferResult,
    { destination: string; relative_paths: string[] }
  >(`/api/v1/filmium/media/${mediaId}/transfer`, {
    destination,
    relative_paths: relativePaths,
  });
}

/**
 * Kopira sadržaj uz stvarni per-fajl progres (SSE).
 */
export function transferFilmiumMediaStream(
  mediaId: number,
  destination: string,
  relativePaths: string[],
  onProgress: (progress: SseProgress) => void,
): Promise<FilmiumTransferResult> {
  return postSse<
    FilmiumTransferResult,
    { destination: string; relative_paths: string[] }
  >(
    `/api/v1/filmium/media/${mediaId}/transfer/stream`,
    { destination, relative_paths: relativePaths },
    onProgress,
  );
}

export interface FilmiumTechnical {
  available: boolean;
  found: boolean;
  width: number | null;
  height: number | null;
  video_codec: string | null;
  frame_rate: number | null;
  audio_codec: string | null;
  audio_channels: number | null;
  duration_seconds: number | null;
  bit_rate: number | null;
  is_hdr: boolean;
  audio_language: string | null;
}

/**
 * Tehnički podaci glavnog video fajla (ffprobe).
 */
export function getFilmiumMediaTechnical(
  mediaId: number,
): Promise<FilmiumTechnical> {
  return getJson<FilmiumTechnical>(
    `/api/v1/filmium/media/${mediaId}/technical`,
  );
}

export interface FilmiumEpisodeMetadata {
  episode_number: number;
  name: string | null;
  overview_en: string | null;
  overview_local: string | null;
  air_date: string | null;
  rating: number | null;
  still_url: string | null;
}

/**
 * TMDB metapodaci epizoda jedne sezone (engleski + lokalni opis).
 */
export function getFilmiumEpisodeMetadata(
  mediaId: number,
  tmdbId: number,
  seasonNumber: number,
): Promise<FilmiumEpisodeMetadata[]> {
  return postJson<
    FilmiumEpisodeMetadata[],
    { tmdb_id: number; season_number: number }
  >(`/api/v1/filmium/media/${mediaId}/episode-metadata`, {
    tmdb_id: tmdbId,
    season_number: seasonNumber,
  });
}

/**
 * ffprobe podaci jedne epizode (rezolucija, codec, veličina, HDR…).
 */
export function getFilmiumEpisodeTechnical(
  mediaId: number,
  rootId: number,
  videoSource: string,
): Promise<FilmiumTechnical> {
  return postJson<
    FilmiumTechnical,
    { root_id: number; video_source: string }
  >(`/api/v1/filmium/media/${mediaId}/episode-technical`, {
    root_id: rootId,
    video_source: videoSource,
  });
}
