import {
  useEffect,
  useMemo,
} from "react";

import { useNavigate } from "react-router";

import FilmiumToolbar from "../components/filmium/FilmiumToolbar";
import { useFilmiumWorkspace } from "../features/filmium/context/useFilmiumWorkspace";
import FilmiumMediaPosterGrid
  from "../features/filmium/components/media/FilmiumMediaPosterGrid";
import FilmiumGenreBar
  from "../features/filmium/components/layout/FilmiumGenreBar";
import FilmiumFeaturedCarousel
  from "../features/filmium/components/home/FilmiumFeaturedCarousel";


import type {
  FavoriteFilter,
  MediaItem,
} from "../types/filmium";


// ==========          TIP BIBLIOTEKE          ==========

export type FilmiumLibraryView =
  | "strano"
  | "domace"
  | "animirano"
  | "favorites"
  | "top-rated"
  | "upcoming"
  | "all";

type FilmiumLibraryPageProps = {
  view: FilmiumLibraryView;
};


// ==========          KONFIGURACIJA PRIKAZA          ==========

const viewTitles: Record<FilmiumLibraryView, string> = {
  all: "Kompletan katalog",
  strano: "Strano",
  domace: "Domaće",
  animirano: "Animirano",
  favorites: "Favoriti",
  "top-rated": "Najbolje ocenjeni",
  upcoming: "Nadolazeći",
};

// Mapiranje rute (view) na kategorijski filter (content_category).
const viewCategory: Record<
  FilmiumLibraryView,
  "strano" | "domace" | "animirano" | "all"
> = {
  strano: "strano",
  domace: "domace",
  animirano: "animirano",
  all: "all",
  favorites: "all",
  "top-rated": "all",
  upcoming: "all",
};


// ==========          FILMIUM LIBRARY EKRAN          ==========

/**
 * Prikazuje filtriranu FILMIUM biblioteku bez dupliranja kataloga.
 */
function FilmiumLibraryPage({
  view,
}: FilmiumLibraryPageProps) {
  const navigate = useNavigate();

  const {
    catalog,
    collections: collectionState,
    filters,
    filtersVisible,
    allGenres,
    setWorkspaceBackdropPath,
  } = useFilmiumWorkspace();

  const {
    actionErrorMessage,
    errorMessage,
    isLoading,
    toggleFavorite,
    updatingFavoriteItemId,
  } = catalog;

  const {
    membershipErrorMessage,
  } = collectionState;

  const {
    availableGenres,
    clearFilters,
    favoriteFilter,
    filteredItems,
    genreFilter,
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
  } = filters;

  const lockedCategory = viewCategory[view];

  const lockedFavoriteFilter: FavoriteFilter =
    view === "favorites"
      ? "favorites"
      : "all";

  // ==========          SINHRONIZACIJA RUTE I FILTERA          ==========

  // Ruta zaključava kategoriju (Strano/Domaće/Animirano); tip (film/serija)
  // ostaje na FILM/SERIJE toggle-u iz gornje trake.
  useEffect(() => {
    setCategoryFilter(lockedCategory);
    setFavoriteFilter(lockedFavoriteFilter);

    // „#" kolekcija je trenutni filter (sleće na /filmium/library, view "all").
    // Klik na Strano/Domaće/Animirano/Favorite/… (bilo koji drugi view) ga
    // poništava da se prikaz vrati na normalno.
    if (view !== "all") {
      setCollectionFilter(null, null);
    }
  }, [
    view,
    lockedCategory,
    lockedFavoriteFilter,
    setCategoryFilter,
    setCollectionFilter,
    setFavoriteFilter,
  ]);



    // ==========          PRIKAZ PODATAKA          ==========

  const displayedItems = useMemo(() => {
    if (view === "top-rated") {
      return [...filteredItems]
        .filter((item) => item.rating !== null)
        .sort(
          (firstItem, secondItem) =>
            (secondItem.rating ?? 0)
            - (firstItem.rating ?? 0),
        );
    }

    if (view === "upcoming") {
      const currentYear = new Date().getFullYear();

      return [...filteredItems]
        .filter(
          (item) =>
            item.release_year !== null
            && item.release_year > currentYear,
        )
        .sort(
          (firstItem, secondItem) =>
            (firstItem.release_year ?? 0)
            - (secondItem.release_year ?? 0),
        );
    }

    // Kategorija (Strano/Domaće/Animirano) već filtrira `filteredItems`
    // preko categoryFilter-a; ovde samo sortiramo.
    // Default prikaz: najnovije prvo (godina), pa abecedno po naslovu.
    return [...filteredItems].sort((firstItem, secondItem) => {
      const yearDelta =
        (secondItem.release_year ?? 0)
        - (firstItem.release_year ?? 0);

      if (yearDelta !== 0) {
        return yearDelta;
      }

      return firstItem.title.localeCompare(secondItem.title);
    });
  }, [filteredItems, view]);


  /**
   * Čisti promenljive filtere i vraća zaključane vrednosti rute.
   */
  function handleClearFilters(): void {
    clearFilters();
    setCategoryFilter(lockedCategory);
    setFavoriteFilter(lockedFavoriteFilter);
  }

  /**
   * Otvara detalje iz poster prikaza.
   */
  function handleOpenDetails(item: MediaItem): void {
    navigate(`/filmium/media/${item.id}`);
  }

  const emptyMessage =
    view === "top-rated"
      ? "Trenutno nema ocenjenih FILMIUM sadržaja."
      : view === "upcoming"
        ? "Trenutno nema nadolazećih sadržaja u katalogu."
        : "Nijedan sadržaj ne odgovara izabranom prikazu.";

  // Polje sa žanrovima prikazuje SVE žanrove iz registra (fallback: katalog).
  const genreOptions =
    allGenres.length > 0 ? allGenres : availableGenres;

  return (
    <section className="filmium-section filmium-library-page">
      <div className="section-heading">
        <p className="eyebrow">
          FILMIUM Library
          <span className="filmium-library-count">
            {displayedItems.length}
          </span>
        </p>
        <h2>{viewTitles[view]}</h2>
      </div>

      {/* ==========          FILTERI (skriveni dok se ne otvore)          ========== */}

      {filtersVisible && (
        <>
          <FilmiumGenreBar
            availableGenres={genreOptions}
            selectedGenre={genreFilter}
            onGenreChange={setGenreFilter}
          />

          <FilmiumToolbar
            availableGenres={genreOptions}
            favoriteFilter={favoriteFilter}
            genreFilter={genreFilter}
            mediaTypeFilter={mediaTypeFilter}
            searchQuery={searchQuery}
            showFavoriteFilter={view !== "favorites"}
            showMediaTypeFilter
            visibleCount={displayedItems.length}
            watchStatusFilter={watchStatusFilter}
            onClear={handleClearFilters}
            onFavoriteChange={setFavoriteFilter}
            onGenreChange={setGenreFilter}
            onMediaTypeChange={setMediaTypeFilter}
            onSearchChange={setSearchQuery}
            onWatchStatusChange={setWatchStatusFilter}
          />
        </>
      )}

      {/* ==========          PREPORUKE ODELJENJA          ========== */}

      {!isLoading && !errorMessage && (
        <FilmiumFeaturedCarousel
          items={displayedItems}
          updatingFavoriteItemId={updatingFavoriteItemId}
          onActiveBackdropChange={setWorkspaceBackdropPath}
          onOpenDetails={handleOpenDetails}
          onToggleFavorite={toggleFavorite}
        />
      )}

      {isLoading && (
        <p className="system-message">
          Učitavam FILMIUM katalog...
        </p>
      )}

      {errorMessage && (
        <p className="system-message error">
          FILMIUM API nije dostupan: {errorMessage}
        </p>
      )}

      {actionErrorMessage && (
        <p className="system-message error">
          {actionErrorMessage}
        </p>
      )}

      {membershipErrorMessage && (
        <p className="system-message error">
          {membershipErrorMessage}
        </p>
      )}

      {!isLoading && !errorMessage && (
        <FilmiumMediaPosterGrid
          emptyMessage={emptyMessage}
          items={displayedItems}
          onOpenDetails={handleOpenDetails}
        />
      )}
    </section>
  );
}

export default FilmiumLibraryPage;
