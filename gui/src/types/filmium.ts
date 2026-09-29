// ==========          FILMIUM TIPOVI          ==========

export type MediaType = "movie" | "series";

/** Lagani TMDB povezan naslov (recommendations). */
export type RelatedTitle = {
  tmdb_id: number;
  title: string;
  year: number | null;
  poster_path: string | null;
  media_type: MediaType;
};

export type WatchStatus =
  | "planned"
  | "watching"
  | "completed"
  | "paused"
  | "dropped";



// ==========          FILMIUM VIZUELNI ASSETI          ==========

export type MediaAssetType = "poster" | "backdrop";





// ==========          SPOLJNE OCENE (IMDb / RT / TVmaze / MAL)          ==========

/**
 * Jedan izvor spoljne ocene, kako ga backend upisuje u
 * `editor_settings.ratings.external[<label>]`. Sva polja su opciona jer se
 * oblik razlikuje po izvoru (IMDb → score/url, RT → tomatometer/audience,
 * TVmaze → score/network, MAL → score/studio/episodes).
 */
export interface ExternalRatingSource {
  score?: number | null;
  scale?: number;
  url?: string;
  tomatometer?: number | null;
  audience?: number | null;
  network?: string;
  studio?: string;
  episodes?: number;
}

/** Perzistirani blok spoljnih ocena (`editor_settings.ratings`). */
export interface ExternalRatingsData {
  external?: Record<string, ExternalRatingSource | null>;
  votes?: Record<string, number | null>;
}

/**
 * Tipiziran `editor_settings` — zadržava slobodan indeks (ostali tabovi upisuju
 * svoje blokove) uz precizan oblik za `ratings.external`/`ratings.votes`.
 */
export interface MediaEditorSettings {
  ratings?: ExternalRatingsData & Record<string, unknown>;
  [key: string]: unknown;
}


// ==========          FILMIUM SADRŽAJ          ==========

export interface MediaItem {
  id: number;
  title: string;
  original_title: string | null;
  english_title?: string | null;
  media_type: MediaType;
  release_year: number | null;
  runtime_minutes: number | null;
  watch_status: WatchStatus;
  rating: number | null;
  notes: string | null;
  english_description?: string | null;
  created_at: string;
  updated_at: string;
  genres: string[];
  poster_path: string | null;
  backdrop_path: string | null;
  is_favorite: boolean;
  content_category?: "regular" | "animated" | "domestic";
  cast_names?: string[];
  studio?: string | null;
  director?: string | null;
  is_synchronized?: boolean;
  keywords?: string[];
  editor_settings?: MediaEditorSettings;
  tmdb_id?: number | null;
  related_tmdb?: RelatedTitle[];
}

// ==========          FILMIUM FILTER TIPOVI          ==========

export type MediaTypeFilter = "all" | MediaType;
export type WatchStatusFilter = "all" | WatchStatus;
export type FavoriteFilter = "all" | "favorites";
export type CategoryFilter = "all" | "strano" | "domace" | "animirano";


// ==========          KREIRANJE I IZMENA SADRŽAJA          ==========

export interface MediaItemCreateRequest {
  title: string;
  media_type: MediaType;
  original_title?: string | null;
  release_year?: number | null;
  runtime_minutes?: number | null;
  watch_status?: WatchStatus;
  rating?: number | null;
  notes?: string | null;
  genres?: string[];
  is_favorite?: boolean;
  english_title?: string | null;
  english_description?: string | null;
  content_category?: "regular" | "animated" | "domestic";
  cast_names?: string[];
  keywords?: string[];
  studio?: string | null;
  director?: string | null;
  is_synchronized?: boolean;
  editor_settings?: Record<string, unknown>;
}


// ==========          FAVORITE STATUS          ==========

export interface MediaItemFavoriteRequest {
  is_favorite: boolean;
}

// ==========          FILMIUM KOLEKCIJE          ==========

export interface MediaCollection {
  id: number;
  name: string;
  description: string | null;
  item_ids: number[];
  created_at: string;
  updated_at: string;
}

export interface CollectionCreateRequest {
  name: string;
  description?: string | null;
}



// ==========          FILMIUM ACTIVITY          ==========

export type ActivityEventType =
  | "media_created"
  | "media_updated"
  | "media_deleted"
  | "favorite_added"
  | "favorite_removed"
  | "collection_created"
  | "collection_deleted"
  | "collection_media_added"
  | "collection_media_removed";

export type ActivityEntityType =
  | "media"
  | "collection";

export interface FilmiumActivityItem {
  id: number;
  event_type: ActivityEventType;
  entity_type: ActivityEntityType;
  entity_id: number;
  title: string;
  metadata: Record<string, unknown>;
  created_at: string;
}