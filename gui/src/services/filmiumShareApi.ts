import {
  getJson,
  postJson,
  postSse,
  type SseProgress,
} from "./httpClient";


// ==========          FILMIUM SHARE (PROFILI)          ==========

export interface FilmiumShareProfile {
  id: number;
  name: string;
  description: string | null;
  default_destination_folder: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface FilmiumShareQueueItem {
  id: number;
  profile_id: number;
  media_id: number;
  transfer_mode: "playback" | "complete";
  status: string;
}

/**
 * Vraća sve profile funkcije Podeli.
 */
export function listFilmiumShareProfiles(): Promise<
  FilmiumShareProfile[]
> {
  return getJson<FilmiumShareProfile[]>(
    "/api/v1/filmium/share/profiles",
  );
}

/**
 * Pravi novi profil za deljenje.
 */
export function createFilmiumShareProfile(body: {
  name: string;
  description?: string | null;
  default_destination_folder?: string;
}): Promise<FilmiumShareProfile> {
  return postJson<FilmiumShareProfile, typeof body>(
    "/api/v1/filmium/share/profiles",
    body,
  );
}

/**
 * Vraća red (pripremljene medije) izabranog profila.
 */
export function getFilmiumShareQueue(
  profileId: number,
): Promise<FilmiumShareQueueItem[]> {
  return getJson<FilmiumShareQueueItem[]>(
    `/api/v1/filmium/share/profiles/${profileId}/queue`,
  );
}

// ==========          PRENOS (KOPIRANJE SA PROGRESOM)          ==========

export interface FilmiumShareTransferSummary {
  copied_files: number;
  total_bytes: number;
  destination: string;
  skipped_media_ids: number[];
}

/**
 * Kopira izabrane kataloške stavke (film/serija) na lokaciju uz per-fajl
 * progres (SSE). `onProgress` javlja ukupni napredak preko svih stavki.
 */
export function transferFilmiumShareStream(
  mediaIds: number[],
  destinationPath: string,
  onProgress: (progress: SseProgress) => void,
): Promise<FilmiumShareTransferSummary> {
  return postSse<
    FilmiumShareTransferSummary,
    { media_ids: number[]; destination_path: string }
  >(
    "/api/v1/filmium/share/transfer/stream",
    { media_ids: mediaIds, destination_path: destinationPath },
    onProgress,
  );
}

/**
 * Dodaje sadržaj u red izabranog profila (playback = delovi, complete = ceo).
 */
export function addToFilmiumShareQueue(
  profileId: number,
  mediaId: number,
  transferMode: "playback" | "complete",
): Promise<FilmiumShareQueueItem> {
  return postJson<
    FilmiumShareQueueItem,
    { media_id: number; transfer_mode: "playback" | "complete" }
  >(`/api/v1/filmium/share/profiles/${profileId}/queue`, {
    media_id: mediaId,
    transfer_mode: transferMode,
  });
}
