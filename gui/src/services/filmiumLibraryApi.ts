import {
  deleteRequest,
  getApiUrl,
  getJson,
  postJson,
  postRequest,
  postSse,
  putJson,
  type SseProgress,
} from "./httpClient";
import type {
  FilmiumLibraryImportCommitRequest,
  FilmiumLibraryImportCommitResult,
  FilmiumLibraryImportPreview,
  FilmiumLibraryRoot,
  FilmiumLibraryRootRequest,
  FilmiumLibraryScanResult,
} from "../types/filmiumLibrary";


const LIBRARY_ENDPOINT = "/api/v1/filmium/libraries";


/**
 * Otvara sistemski Explorer/Finder na lokaciji fajla (unutar korena).
 */
export function revealFilmiumPath(
  rootId: number,
  relativePath: string,
): Promise<{ revealed: boolean }> {
  return postJson<{ revealed: boolean }, { relative_path: string }>(
    `${LIBRARY_ENDPOINT}/${rootId}/reveal`,
    { relative_path: relativePath },
  );
}


/**
 * Prekopira izabrani izvorni fajl preko postojećeg (zamena slike/prevoda).
 */
export function replaceFilmiumFile(
  rootId: number,
  relativePath: string,
  sourcePath: string,
): Promise<{ replaced: boolean }> {
  return postJson<
    { replaced: boolean },
    { relative_path: string; source_path: string }
  >(`${LIBRARY_ENDPOINT}/${rootId}/replace-file`, {
    relative_path: relativePath,
    source_path: sourcePath,
  });
}


export function getFilmiumLibraryArtworkUrl(
  rootId: number,
  relativeDirectory: string,
  file?: string,
): string {
  const query = new URLSearchParams({
    directory: relativeDirectory,
  });

  if (file) {
    query.set("file", file);
  }

  return getApiUrl(
    `${LIBRARY_ENDPOINT}/${rootId}/entries/artwork?${query.toString()}`,
  );
}


export function getFilmiumLibraryRoots(): Promise<FilmiumLibraryRoot[]> {
  return getJson<FilmiumLibraryRoot[]>(LIBRARY_ENDPOINT);
}


export function createFilmiumLibraryRoot(
  request: FilmiumLibraryRootRequest,
): Promise<FilmiumLibraryRoot> {
  return postJson<FilmiumLibraryRoot, FilmiumLibraryRootRequest>(
    LIBRARY_ENDPOINT,
    request,
  );
}


export function updateFilmiumLibraryRoot(
  rootId: number,
  request: FilmiumLibraryRootRequest,
): Promise<FilmiumLibraryRoot> {
  return putJson<FilmiumLibraryRoot, FilmiumLibraryRootRequest>(
    `${LIBRARY_ENDPOINT}/${rootId}`,
    request,
  );
}


export function deleteFilmiumLibraryRoot(
  rootId: number,
): Promise<void> {
  return deleteRequest(`${LIBRARY_ENDPOINT}/${rootId}`);
}


export function scanFilmiumLibraryRoot(
  rootId: number,
  scanSubtitles = true,
  onlyNew = false,
): Promise<FilmiumLibraryScanResult> {
  const params = new URLSearchParams();
  if (!scanSubtitles) {
    params.set("scan_subtitles", "false");
  }
  if (onlyNew) {
    params.set("only_new", "true");
  }
  const query = params.toString();
  return postRequest<FilmiumLibraryScanResult>(
    `${LIBRARY_ENDPOINT}/${rootId}/scan${query ? `?${query}` : ""}`,
  );
}


export function previewFilmiumLibraryImport(
  rootId: number,
  relativeDirectory: string,
  includeTmdb = false,
): Promise<FilmiumLibraryImportPreview> {
  return postJson<
    FilmiumLibraryImportPreview,
    { relative_directory: string; include_tmdb: boolean }
  >(
    `${LIBRARY_ENDPOINT}/${rootId}/imports/preview`,
    { relative_directory: relativeDirectory, include_tmdb: includeTmdb },
  );
}


export function confirmFilmiumLibraryImport(
  rootId: number,
  request: FilmiumLibraryImportCommitRequest,
): Promise<FilmiumLibraryImportCommitResult> {
  return postJson<
    FilmiumLibraryImportCommitResult,
    FilmiumLibraryImportCommitRequest
  >(
    `${LIBRARY_ENDPOINT}/${rootId}/imports/confirm`,
    request,
  );
}


/**
 * Trajno briše skenirani izvorni folder sa diska („Uništi").
 */
export function destroyFilmiumScannedDirectory(
  rootId: number,
  relativeDirectory: string,
): Promise<void> {
  return postJson<void, { relative_directory: string }>(
    `${LIBRARY_ENDPOINT}/${rootId}/imports/destroy`,
    { relative_directory: relativeDirectory },
  );
}


/**
 * Kao ``confirmFilmiumLibraryImport``, ali sa stvarnim per-fajl progresom
 * (SSE). ``onProgress`` se poziva po premeštenom fajlu.
 */
export function confirmFilmiumLibraryImportStream(
  rootId: number,
  request: FilmiumLibraryImportCommitRequest,
  onProgress: (progress: SseProgress) => void,
): Promise<FilmiumLibraryImportCommitResult> {
  return postSse<
    FilmiumLibraryImportCommitResult,
    FilmiumLibraryImportCommitRequest
  >(
    `${LIBRARY_ENDPOINT}/${rootId}/imports/confirm/stream`,
    request,
    onProgress,
  );
}


/**
 * Označava disk kao glavni (podrazumevano odredište uvoza).
 */
export function setMainFilmiumLibrary(
  rootId: number,
): Promise<FilmiumLibraryRoot> {
  return postRequest<FilmiumLibraryRoot>(
    `${LIBRARY_ENDPOINT}/${rootId}/main`,
  );
}


/**
 * Trajno izuzima folder iz budućih skeniranja biblioteke.
 */
export function ignoreFilmiumLibraryDirectory(
  rootId: number,
  relativeDirectory: string,
): Promise<void> {
  return postJson<void, { relative_directory: string }>(
    `${LIBRARY_ENDPOINT}/${rootId}/ignored`,
    { relative_directory: relativeDirectory },
  );
}
