import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router";

import type {
  CategoryFilter,
  FavoriteFilter,
  MediaItem,
  MediaTypeFilter,
  WatchStatusFilter,
} from "../../../types/filmium";
import { scoreSearch } from "../lib/filmiumSearch";


// Mapiranje kategorije (sidebar) na vrednost content_category iz baze.
const CATEGORY_TO_CONTENT: Record<
  Exclude<CategoryFilter, "all">,
  string
> = {
  strano: "regular",
  domace: "domestic",
  animirano: "animated",
};


// ==========          FILMIUM FILTERI          ==========

/**
 * Upravlja stanjem i primenom filtera FILMIUM kataloga.
 */
export function useFilmiumFilters(items: MediaItem[]) {
  const [searchQuery, setSearchQuery] = useState("");
  const [mediaTypeFilter, setMediaTypeFilter] =
    useState<MediaTypeFilter>("all");
  const [watchStatusFilter, setWatchStatusFilter] =
    useState<WatchStatusFilter>("all");
  const [genreFilter, setGenreFilter] = useState("all");
  const [favoriteFilter, setFavoriteFilter] =
    useState<FavoriteFilter>("all");
  const [categoryFilter, setCategoryFilter] =
    useState<CategoryFilter>("all");
  // Filter po kolekciji: naziv (za prikaz) + skup id-jeva stavki u njoj.
  const [collectionName, setCollectionName] = useState<string | null>(null);
  const [collectionItemIds, setCollectionItemIds] =
    useState<number[] | null>(null);
  // Preporuka Kuratora: prikaži SAMO ove naslove, u OVOM redosledu (AI rang).
  // Nezavisno od kolekcija — čita se iz ?ids=1,2,3 (recommend navigate odgovor).
  const [recoIds, setRecoIds] = useState<number[] | null>(null);

  // Kurator/URL: primeni filtere iz query parametara (npr. ?media_type=series&genre=SF).
  // Curator navigate odgovor otvara rutu sa ovim query-jem; ovde ih pretvaramo u stanje.
  const [searchParams] = useSearchParams();
  useEffect(() => {
    const mt = searchParams.get("media_type");
    if (mt === "movie" || mt === "series") setMediaTypeFilter(mt);
    const genre = searchParams.get("genre");
    if (genre) setGenreFilter(genre);
    const idsParam = searchParams.get("ids");
    const list = idsParam
      ? idsParam.split(",").map((s) => Number(s)).filter((n) => Number.isInteger(n))
      : [];
    setRecoIds(list.length > 0 ? list : null);
  }, [searchParams]);

  /**
   * Postavlja (ili čisti kad je name null) aktivnu kolekciju kao filter.
   */
  function setCollectionFilter(
    name: string | null,
    itemIds: number[] | null,
  ): void {
    setCollectionName(name);
    setCollectionItemIds(itemIds);
  }

  // ==========          DOSTUPNI ŽANROVI          ==========

  const availableGenres = useMemo(
    () =>
      Array.from(
        new Set(items.flatMap((item) => item.genres)),
      ).sort((firstGenre, secondGenre) =>
        firstGenre.localeCompare(secondGenre),
      ),
    [items],
  );

  // ==========          FILTRIRANI SADRŽAJ          ==========

  const filteredItems = useMemo(() => {
    // Unos koji počinje sa „/" (komanda) ili „#" (kolekcija) NIJE tekstualna
    // pretraga — pripada palette-u, pa ga ovde ignorišemo da ne izbaci sve.
    const isPaletteInput =
      searchQuery.startsWith("/") || searchQuery.startsWith("#");
    const normalizedSearchQuery = isPaletteInput
      ? ""
      : searchQuery.trim().toLowerCase();

    const searching = normalizedSearchQuery !== "";

    const scored = items.map((item) => {
      // Pretraga pokriva: srpski/engleski/originalni naslov, opis, žanrove,
      // glumce i ključne reči — tolerantno na dijakritiku i redosled reči
      // (vidi filmiumSearch). Skor služi za rangiranje (najbolji pogodak gore).
      const searchScore = searching
        ? scoreSearch(searchQuery, {
            title: item.title,
            secondary: [
              item.original_title ?? "",
              item.english_title ?? "",
              item.notes ?? "",
              ...item.genres,
              ...(item.cast_names ?? []),
              ...(item.keywords ?? []),
              ...((item.editor_settings?.user_keywords as
                | string[]
                | undefined) ?? []),
            ],
          })
        : 0;
      return { item, searchScore };
    });

    const matched = scored
      .filter(({ item, searchScore }) => {
      const matchesSearch = !searching || searchScore > 0;

      const matchesMediaType =
        mediaTypeFilter === "all" ||
        item.media_type === mediaTypeFilter;

      const matchesWatchStatus =
        watchStatusFilter === "all" ||
        item.watch_status === watchStatusFilter;

      const matchesGenre =
        genreFilter === "all" ||
        item.genres.includes(genreFilter);

      const matchesFavorite =
        favoriteFilter === "all" ||
        item.is_favorite;

      const matchesCategory =
        categoryFilter === "all" ||
        item.content_category === CATEGORY_TO_CONTENT[categoryFilter];

      const matchesCollection =
        collectionItemIds === null ||
        collectionItemIds.includes(item.id);

      const matchesReco =
        recoIds === null ||
        recoIds.includes(item.id);

      return (
        matchesSearch &&
        matchesMediaType &&
        matchesWatchStatus &&
        matchesGenre &&
        matchesFavorite &&
        matchesCategory &&
        matchesCollection &&
        matchesReco
      );
    });

    // Pri pretrazi: prvo po skoru (najbolji pogodak gore), pa filmovi ispred
    // serija kao tie-break. Bez pretrage — zadrži originalni redosled.
    if (searching) {
      return [...matched]
        .sort((first, second) => {
          const byScore = second.searchScore - first.searchScore;
          if (byScore !== 0) {
            return byScore;
          }
          return (
            Number(second.item.media_type === "movie")
            - Number(first.item.media_type === "movie")
          );
        })
        .map(({ item }) => item);
    }

    // Preporuka: zadrži AI redosled (redosled iz ?ids=), najbolji predlog gore.
    if (recoIds !== null) {
      const rank = new Map(recoIds.map((id, index) => [id, index]));
      return [...matched]
        .sort(
          (first, second) =>
            (rank.get(first.item.id) ?? Infinity)
            - (rank.get(second.item.id) ?? Infinity),
        )
        .map(({ item }) => item);
    }

    return matched.map(({ item }) => item);
  }, [
    categoryFilter,
    collectionItemIds,
    favoriteFilter,
    genreFilter,
    items,
    mediaTypeFilter,
    recoIds,
    searchQuery,
    watchStatusFilter,
  ]);

  const hasActiveFilters =
    searchQuery.trim() !== "" ||
    mediaTypeFilter !== "all" ||
    watchStatusFilter !== "all" ||
    genreFilter !== "all" ||
    favoriteFilter !== "all" ||
    categoryFilter !== "all" ||
    collectionItemIds !== null ||
    recoIds !== null;

  /**
   * Vraća sve filtere na početne vrednosti.
   */
  function clearFilters(): void {
    setSearchQuery("");
    setMediaTypeFilter("all");
    setWatchStatusFilter("all");
    setGenreFilter("all");
    setFavoriteFilter("all");
    setCategoryFilter("all");
    setCollectionFilter(null, null);
    setRecoIds(null);
  }

  return {
    availableGenres,
    categoryFilter,
    clearFilters,
    collectionName,
    favoriteFilter,
    filteredItems,
    genreFilter,
    hasActiveFilters,
    mediaTypeFilter,
    searchQuery,
    setCategoryFilter,
    setCollectionFilter,
    setFavoriteFilter,
    setGenreFilter,
    setMediaTypeFilter,
    setSearchQuery,
    setWatchStatusFilter,
    watchStatusFilter,
  };
}