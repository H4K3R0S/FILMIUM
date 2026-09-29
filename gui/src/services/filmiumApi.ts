



// ==========          HTTP FUNKCIJE          ==========

// postFormData
import {
  deleteRequest,
  getApiUrl,
  getJson,
  patchJson,
  postFormData,
  postJson,
  postRequest,
  putJson,
} from "./httpClient";

// postFormData
import type {
  CollectionCreateRequest,
  MediaAssetType,
  MediaCollection,
  MediaItemFavoriteRequest,
  MediaItem,
  MediaItemCreateRequest,
  FilmiumActivityItem,
} from "../types/filmium";




// ==========          FILMIUM API          ==========

/**
 * Učitava kompletan FILMIUM katalog.
 */
export function getFilmiumMedia(): Promise<MediaItem[]> {
  return getJson<MediaItem[]>("/api/v1/filmium/media");
}

/**
 * Ucitava kontrolisanu listu aktivnih FILMIUM zanrova.
 */
export function getFilmiumGenres(): Promise<string[]> {
  return getJson<string[]>("/api/v1/filmium/genres");
}

/**
 * Učitava jedan FILMIUM sadržaj po ID-u.
 */
export function getFilmiumMediaItem(
  itemId: number,
): Promise<MediaItem> {
  return getJson<MediaItem>(`/api/v1/filmium/media/${itemId}`);
}

/**
 * Dodaje novi film ili seriju u FILMIUM katalog.
 */
export function createFilmiumMediaItem(
  request: MediaItemCreateRequest,
): Promise<MediaItem> {
  return postJson<MediaItem, MediaItemCreateRequest>(
    "/api/v1/filmium/media",
    request,
  );
}


/**
 * Menja postojeći FILMIUM sadržaj.
 */
export function updateFilmiumMediaItem(
  itemId: number,
  request: MediaItemCreateRequest,
): Promise<MediaItem> {
  return putJson<MediaItem, MediaItemCreateRequest>(
    `/api/v1/filmium/media/${itemId}`,
    request,
  );
}


/**
 * Parcijalni update: menja samo ključne reči i editor_settings (bez rizika
 * da se prepišu ostala polja sadržaja).
 */
export function updateFilmiumMediaKeywords(
  itemId: number,
  request: {
    keywords: string[];
    editor_settings: Record<string, unknown>;
  },
): Promise<MediaItem> {
  return patchJson<
    MediaItem,
    { keywords: string[]; editor_settings: Record<string, unknown> }
  >(`/api/v1/filmium/media/${itemId}/keywords`, request);
}



/**
 * Menja samo favorite status FILMIUM sadržaja.
 */
export function setFilmiumFavoriteStatus(
  itemId: number,
  isFavorite: boolean,
): Promise<MediaItem> {
  return patchJson<MediaItem, MediaItemFavoriteRequest>(
    `/api/v1/filmium/media/${itemId}/favorite`,
    {
      is_favorite: isFavorite,
    },
  );
}



/**
 * Briše FILMIUM sadržaj.
 */
export function deleteFilmiumMediaItem(
  itemId: number,
): Promise<void> {
  return deleteRequest(`/api/v1/filmium/media/${itemId}`);
}



// ==========          FILMIUM COLLECTION API          ==========

/**
 * Učitava sve FILMIUM kolekcije.
 */
export function getFilmiumCollections(): Promise<MediaCollection[]> {
  return getJson<MediaCollection[]>(
    "/api/v1/filmium/collections",
  );
}

/**
 * Kreira novu FILMIUM kolekciju.
 */
export function createFilmiumCollection(
  request: CollectionCreateRequest,
): Promise<MediaCollection> {
  return postJson<MediaCollection, CollectionCreateRequest>(
    "/api/v1/filmium/collections",
    request,
  );
}

/**
 * Briše FILMIUM kolekciju.
 */
export function deleteFilmiumCollection(
  collectionId: number,
): Promise<void> {
  return deleteRequest(
    `/api/v1/filmium/collections/${collectionId}`,
  );
}

/**
 * Dodaje sadržaj u FILMIUM kolekciju.
 */
export function addMediaToFilmiumCollection(
  collectionId: number,
  itemId: number,
): Promise<MediaCollection> {
  return postRequest<MediaCollection>(
    `/api/v1/filmium/collections/${collectionId}/media/${itemId}`,
  );
}

/**
 * Uklanja sadržaj iz FILMIUM kolekcije.
 */
export function removeMediaFromFilmiumCollection(
  collectionId: number,
  itemId: number,
): Promise<MediaCollection> {
  return deleteRequest<MediaCollection>(
    `/api/v1/filmium/collections/${collectionId}/media/${itemId}`,
  );
}



// ==========          FILMIUM VISUAL ASSET API          ==========

/**
 * Uploaduje poster ili backdrop jednog FILMIUM sadržaja.
 */
export function uploadFilmiumMediaAsset(
  itemId: number,
  assetType: MediaAssetType,
  file: File,
): Promise<MediaItem> {
  const formData = new FormData();

  formData.append("file", file);

  return postFormData<MediaItem>(
    `/api/v1/filmium/media/${itemId}/assets/${assetType}`,
    formData,
  );
}

/**
 * Uklanja poster ili backdrop jednog FILMIUM sadržaja.
 */
export function deleteFilmiumMediaAsset(
  itemId: number,
  assetType: MediaAssetType,
): Promise<MediaItem> {
  return deleteRequest<MediaItem>(
    `/api/v1/filmium/media/${itemId}/assets/${assetType}`,
  );
}

/**
 * Pravi URL preko kojeg GUI može da prikaže FILMIUM asset.
 */
export function getFilmiumAssetUrl(
  relativePath: string | null,
): string | null {
  if (!relativePath) {
    return null;
  }

  const encodedPath = relativePath
    .split("/")
    .map((pathPart) => encodeURIComponent(pathPart))
    .join("/");

  return getApiUrl(
    `/api/v1/filmium/assets/${encodedPath}`,
  );
}

// ==========          FILMIUM ACTIVITY API          ==========

/**
 * Učitava najnovije događaje iz FILMIUM istorije.
 */
export function getFilmiumActivity(
  limit = 100,
): Promise<FilmiumActivityItem[]> {
  return getJson<FilmiumActivityItem[]>(
    `/api/v1/filmium/activity?limit=${limit}`,
  );
}