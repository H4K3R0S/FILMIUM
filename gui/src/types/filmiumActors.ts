// ==========          FILMIUM GLUMCI — TIPOVI          ==========
// Prati ugovor `apps/api/routers/filmium_actors.py` (Faza A, gotovo). Ne
// izmišljati polja koja backend ne vraća.

import type { MediaType } from "./filmium";

/** Jedan glumac/reditelj u listi (`GET /api/v1/filmium/actors`). */
export type FilmiumActorListItem = {
  slug: string;
  name: string;
  image_path: string | null;
  is_director: number | boolean;
  gallery_count: number;
  birthday: string | null;
  place_of_birth: string | null;
  film_count: number;
  professions?: string[];
};

export type FilmiumActorsListResponse = {
  total: number;
  items: FilmiumActorListItem[];
};

/** Naslov iz lične biblioteke (uvek `in_library: true`). */
export type FilmiumActorLibraryFilm = {
  media_id: number;
  title: string;
  year: number | null;
  media_type: MediaType;
  tmdb_id: number | null;
  poster_path: string | null;
  role: string | null;
  character: string | null;
  sort_order?: number | null;
  in_library: true;
};

/** Jedan unos pune TMDB filmografije (biblioteka ili „za dodavanje"). */
export type FilmiumActorFilmographyEntry = {
  tmdb_id: number;
  title: string | null;
  year: number | null;
  /** TMDB šalje "movie" / "tv" — normalizuj pre prikaza (vidi `filmiumActorsApi`). */
  media_type: string | null;
  character: string | null;
  role: string | null;
  in_library: boolean;
  media_id: number | null;
};

export type FilmiumActorDetail = {
  person: {
    slug: string;
    name: string;
    bio: string | null;
    birthday: string | null;
    deathday: string | null;
    place_of_birth: string | null;
    known_for: string | null;
    is_director: number | boolean;
    gallery_count: number;
    professions?: string[];
    native_name?: string | null;
    imdb_id?: string | null;
  };
  library_films: FilmiumActorLibraryFilm[];
  filmography: FilmiumActorFilmographyEntry[];
};

/** Jedinstvena kartica filma/serije na stranici glumca (spoj oba izvora). */
export type FilmiumActorFilmCard = {
  key: string;
  tmdb_id: number | null;
  title: string;
  year: number | null;
  media_type: MediaType;
  character: string | null;
  in_library: boolean;
  media_id: number | null;
  poster_path: string | null;
};

/**
 * Jedan glumac/reditelj u glumačkoj postavi JEDNOG naslova
 * (`GET /api/v1/filmium/media/{media_id}/cast`). Sortirano na backendu:
 * glumci po billing redosledu, reditelj na kraju.
 */
export type FilmiumMediaCastMember = {
  slug: string;
  name: string;
  image_path: string | null;
  is_director: number | boolean;
  role: string | null;
  character: string | null;
  sort_order: number | null;
};

/** Odgovor `GET /api/v1/filmium/media/{media_id}/cast`. */
export type FilmiumMediaCastResponse = {
  media_id: number;
  total: number;
  cast: FilmiumMediaCastMember[];
};
