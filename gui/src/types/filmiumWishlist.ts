// ==========          TIPOVI LISTE „ZA PREUZETI"          ==========

/** Tip sadržaja za listu za preuzimanje. */
export type WishlistMediaType = "movie" | "series";

/** Kategorija (Strano = regular, Domaće = domestic, Animirano = animated). */
export type WishlistCategory = "regular" | "domestic" | "animated";

/** Vrsta asseta koja se otprema uz stavku. */
export type WishlistAssetKind =
  | "poster"
  | "backdrop"
  | "wallpaper"
  | "original_subtitle"
  | "domestic_subtitle"
  | "english_subtitle"
  | "extra";

/** Podaci koje šaljemo pri kreiranju stavke. */
export type WishlistEntryCreateRequest = {
  title: string;
  release_year: number | null;
  media_type: WishlistMediaType;
  content_category: WishlistCategory;
  is_subtitled: boolean;
  is_synchronized: boolean;
  tmdb_id: number | null;
  english_overview: string | null;
  local_overview: string | null;
  original_title: string | null;
  local_title: string | null;
};

/** Zahtev za prevod naslova + opisa (EN → bosanski). */
export type WishlistTranslateRequest = {
  title: string;
  overview: string;
};

/** Rezultat prevoda. `available` je false ako prevodilac ne radi. */
export type WishlistTranslateResult = {
  available: boolean;
  title: string;
  overview: string;
};

/** Jedan naslov iz liste za preuzimanje. */
export type WishlistEntry = {
  id: number;
  title: string;
  release_year: number | null;
  media_type: WishlistMediaType;
  content_category: WishlistCategory;
  is_subtitled: boolean;
  is_synchronized: boolean;
  tmdb_id: number | null;
  english_overview: string | null;
  local_overview: string | null;
  original_title: string | null;
  local_title: string | null;
  poster_path: string | null;
  backdrop_path: string | null;
  wallpaper_path: string | null;
  original_subtitle_path: string | null;
  domestic_subtitle_path: string | null;
  english_subtitle_path: string | null;
  extra_assets: string[];
  created_at: string;
  updated_at: string;
};

/** Zahtev za TMDB pretragu (popuna forme). */
export type WishlistTmdbPreviewRequest = {
  title: string;
  year: number | null;
  media_type: WishlistMediaType;
};

/** Naslov uklonjen iz liste jer je ušao u biblioteku. */
export type WishlistRemovedEntry = {
  id: number;
  title: string;
};

/** Rezultat usklađivanja liste sa bibliotekom. */
export type WishlistReconcileResult = {
  removed: WishlistRemovedEntry[];
};

/** Rezultat TMDB pretrage — ništa se ne čuva. */
export type WishlistTmdbPreview = {
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
  poster_url: string | null;
  backdrop_url: string | null;
};
