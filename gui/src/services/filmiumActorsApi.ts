import { getApiUrl, getJson } from "./httpClient";
import type {
  FilmiumActorDetail,
  FilmiumActorsListResponse,
  FilmiumMediaCastResponse,
} from "../types/filmiumActors";


// ==========          FILMIUM GLUMCI API          ==========
// Prati `apps/api/routers/filmium_actors.py` (Faza A, gotovo) — samo čitanje.

const BASE = "/api/v1/filmium/actors";

export type FilmiumActorsQuery = {
  q?: string;
  role?: "" | "reditelj";
  onlyWithImage?: boolean;
  limit?: number;
  offset?: number;
};

/** Učitava listu glumaca/reditelja (pretraga + paginacija). */
export function getFilmiumActors(
  query: FilmiumActorsQuery = {},
): Promise<FilmiumActorsListResponse> {
  const params = new URLSearchParams();

  if (query.q && query.q.trim() !== "") {
    params.set("q", query.q.trim());
  }
  if (query.role) {
    params.set("role", query.role);
  }
  params.set("only_with_image", String(query.onlyWithImage ?? true));
  params.set("limit", String(query.limit ?? 60));
  params.set("offset", String(query.offset ?? 0));

  return getJson<FilmiumActorsListResponse>(`${BASE}?${params.toString()}`);
}

/** Učitava detalje jednog glumca (bio, filmografija, biblioteka). */
export function getFilmiumActorDetail(
  slug: string,
): Promise<FilmiumActorDetail> {
  return getJson<FilmiumActorDetail>(`${BASE}/${encodeURIComponent(slug)}`);
}

/** Glavna slika glumca. */
export function getFilmiumActorImageUrl(slug: string): string {
  return getApiUrl(`${BASE}/${encodeURIComponent(slug)}/image`);
}

/** Jedna slika iz galerije glumca (`idx` 0..gallery_count-1). */
export function getFilmiumActorGalleryUrl(slug: string, idx: number): string {
  return getApiUrl(`${BASE}/${encodeURIComponent(slug)}/gallery/${idx}`);
}

/** Normalizuje TMDB "movie"/"tv" (i slično) u domaći `MediaType`. */
export function normalizeActorMediaType(
  value: string | null | undefined,
): "movie" | "series" {
  return value === "tv" || value === "series" ? "series" : "movie";
}

/**
 * Glumačka postava jednog naslova (`apps/api/routers` — media cast, novo).
 * Sortirano na backendu: glumci po billing redosledu, reditelj na kraju.
 * `limit=0` (podrazumevano) vraća kompletnu postavu.
 */
export function getFilmiumMediaCast(
  mediaId: number,
  limit = 0,
): Promise<FilmiumMediaCastResponse> {
  return getJson<FilmiumMediaCastResponse>(
    `/api/v1/filmium/media/${mediaId}/cast?limit=${limit}`,
  );
}
