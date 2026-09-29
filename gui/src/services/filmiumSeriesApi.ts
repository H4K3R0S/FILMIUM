import {
  getApiUrl,
  getJson,
  postJson,
  postSse,
  type SseProgress,
} from "./httpClient";

import type {
  FilmiumSeriesImportResult,
  FilmiumSeriesLibraryScan,
  FilmiumSeriesProbe,
  FilmiumTmdbSeason,
  FilmiumTmdbSeries,
} from "../types/filmiumSeries";


const LIBRARY_ENDPOINT = "/api/v1/filmium/libraries";


// ==========          OSVEŽAVANJE BIBLIOTEKE          ==========

export interface FilmiumLibraryRefreshResult {
  scanned_series: number;
  new_series: number;
  posters_added: number;
  backdrops_added: number;
  season_posters_added: number;
  season_backdrops_added: number;
  seasons_added: number;
  episodes_added: number;
  manifests_written: number;
  removed_series: number;
  movie_folders_scanned: number;
  movie_sources_added: number;
  errors: number;
}

/**
 * Skenira sve registrovane biblioteke i dopunjava bazu (slike, epizode,
 * nove serije, JSON manifeste). Uklanja serije kojih više nema na disku.
 */
export function refreshFilmiumLibrary(): Promise<FilmiumLibraryRefreshResult> {
  return postJson<FilmiumLibraryRefreshResult, Record<string, never>>(
    `${LIBRARY_ENDPOINT}/refresh`,
    {},
  );
}

/**
 * Osvežava samo folder jedne serije (dugme na stranici detalja).
 */
export function refreshFilmiumMedia(
  mediaId: number,
): Promise<FilmiumLibraryRefreshResult> {
  return postJson<FilmiumLibraryRefreshResult, Record<string, never>>(
    `${LIBRARY_ENDPOINT}/refresh/media/${mediaId}`,
    {},
  );
}

/**
 * URL za reprodukciju video fajla (uz Range podršku za seek u plejeru).
 */
export function getFilmiumStreamUrl(
  rootId: number,
  source: string,
): string {
  const query = new URLSearchParams({ source });
  return getApiUrl(
    `${LIBRARY_ENDPOINT}/${rootId}/stream?${query.toString()}`,
  );
}

// ==========          SPOLJNI PLEJER (VLC)          ==========

/**
 * Da li je VLC dostupan za spoljnu reprodukciju.
 */
export async function getFilmiumVlcAvailable(): Promise<boolean> {
  try {
    const result = await getJson<{ vlc_available: boolean }>(
      `${LIBRARY_ENDPOINT}/external-player`,
    );
    return result.vlc_available;
  } catch {
    return false;
  }
}

/**
 * Otvara video u VLC-u (svi kodeci). Vraća true ako je pokrenut.
 */
export async function playFilmiumInVlc(
  rootId: number,
  source: string,
): Promise<boolean> {
  try {
    await postJson<{ launched: boolean }, Record<string, never>>(
      `${LIBRARY_ENDPOINT}/${rootId}/play-external`
        + `?source=${encodeURIComponent(source)}`,
      {},
    );
    return true;
  } catch {
    return false;
  }
}

/**
 * URL za prekodiranje uživo (H.264/AAC) — fallback za nepodržane kodeke.
 */
export function getFilmiumTranscodeUrl(
  rootId: number,
  source: string,
): string {
  const query = new URLSearchParams({ source });
  return getApiUrl(
    `${LIBRARY_ENDPOINT}/${rootId}/stream/transcode?${query.toString()}`,
  );
}

/**
 * URL prevoda konvertovanog u WebVTT (za <track> u plejeru).
 */
export function getFilmiumSubtitleUrl(
  rootId: number,
  source: string,
): string {
  const query = new URLSearchParams({ source });
  return getApiUrl(
    `${LIBRARY_ENDPOINT}/${rootId}/subtitle?${query.toString()}`,
  );
}


/**
 * URL sličice epizode (ffmpeg, keširano na serveru).
 */
export function getFilmiumSeriesEpisodeThumbnailUrl(
  rootId: number,
  source: string,
): string {
  const query = new URLSearchParams({ source });
  return getApiUrl(
    `${LIBRARY_ENDPOINT}/${rootId}/series/episode-thumbnail?${query.toString()}`,
  );
}


/**
 * Čita tehničke podatke epizode (ffprobe) po putanji od korena.
 */
export function probeFilmiumSeriesEpisode(
  rootId: number,
  source: string,
): Promise<FilmiumSeriesProbe> {
  return postJson<FilmiumSeriesProbe, { source: string }>(
    `${LIBRARY_ENDPOINT}/${rootId}/series/media-probe`,
    { source },
  );
}


/**
 * Traži seriju na TMDB-u po nazivu (+ godini) — opis, žanrovi, ocena.
 */
export function matchFilmiumTmdbSeries(
  title: string,
  year?: number | null,
): Promise<FilmiumTmdbSeries> {
  return postJson<
    FilmiumTmdbSeries,
    { title: string; year: number | null }
  >(`${LIBRARY_ENDPOINT}/tmdb/series-match`, {
    title,
    year: year ?? null,
  });
}


/**
 * Dovlači TMDB podatke o epizodama jedne sezone (naziv/opis/datum/still).
 */
export function getFilmiumTmdbSeason(
  tmdbId: number,
  seasonNumber: number,
): Promise<FilmiumTmdbSeason> {
  return postJson<
    FilmiumTmdbSeason,
    { tmdb_id: number; season_number: number }
  >(`${LIBRARY_ENDPOINT}/tmdb/season`, {
    tmdb_id: tmdbId,
    season_number: seasonNumber,
  });
}


/**
 * Skenira folder biblioteke: vraća sve otkrivene serije (jedna ili više).
 */
export function previewFilmiumSeries(
  rootId: number,
  relativeDirectory: string,
): Promise<FilmiumSeriesLibraryScan> {
  return postJson<
    FilmiumSeriesLibraryScan,
    { relative_directory: string }
  >(`${LIBRARY_ENDPOINT}/${rootId}/series/preview`, {
    relative_directory: relativeDirectory,
  });
}


/**
 * Organizuje i registruje seriju u FILMIUM katalog.
 */
export function confirmFilmiumSeries(
  rootId: number,
  relativeDirectory: string,
  targetLibraryRootId?: number | null,
): Promise<FilmiumSeriesImportResult> {
  return postJson<
    FilmiumSeriesImportResult,
    {
      relative_directory: string;
      confirmed: boolean;
      target_library_root_id?: number | null;
    }
  >(`${LIBRARY_ENDPOINT}/${rootId}/series/confirm`, {
    relative_directory: relativeDirectory,
    confirmed: true,
    ...(targetLibraryRootId != null
      ? { target_library_root_id: targetLibraryRootId }
      : {}),
  });
}


/**
 * Kao ``confirmFilmiumSeries``, ali sa stvarnim per-fajl progresom (SSE).
 */
export function confirmFilmiumSeriesStream(
  rootId: number,
  relativeDirectory: string,
  targetLibraryRootId: number | null | undefined,
  onProgress: (progress: SseProgress) => void,
  contentMode: "regular" | "animated" | "domestic" = "regular",
  synchronized: boolean = false,
): Promise<FilmiumSeriesImportResult> {
  return postSse<
    FilmiumSeriesImportResult,
    {
      relative_directory: string;
      confirmed: boolean;
      target_library_root_id?: number | null;
      content_mode: "regular" | "animated" | "domestic";
      synchronized: boolean;
    }
  >(
    `${LIBRARY_ENDPOINT}/${rootId}/series/confirm/stream`,
    {
      relative_directory: relativeDirectory,
      confirmed: true,
      ...(targetLibraryRootId != null
        ? { target_library_root_id: targetLibraryRootId }
        : {}),
      content_mode: contentMode,
      synchronized,
    },
    onProgress,
  );
}
