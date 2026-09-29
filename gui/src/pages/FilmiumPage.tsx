import { useNavigate } from "react-router";

import { useFilmiumWorkspace } from "../features/filmium/context/useFilmiumWorkspace";
import { useFilmiumIntro } from "../features/filmium/hooks/useFilmiumIntro";
import FilmiumGenreBar from "../features/filmium/components/layout/FilmiumGenreBar";
import FilmiumToolbar from "../components/filmium/FilmiumToolbar";
import FilmiumFeaturedCarousel from "../features/filmium/components/home/FilmiumFeaturedCarousel";
import FilmiumHomeShelves from "../features/filmium/components/home/FilmiumHomeShelves";
import FilmiumWishlistShelf from "../features/filmium/components/home/FilmiumWishlistShelf";
import type { MediaItem } from "../types/filmium";


// ==========          FILMIUM EKRAN          ==========

/**
 * Sastavlja trenutni FILMIUM katalog i njegove UI sekcije.
 */
function FilmiumPage() {
  const navigate = useNavigate();

  const {
    catalog,
    filters,
    wishlist,
    filtersVisible,
    allGenres,
    setWorkspaceBackdropPath,
    introPlayed,
    markIntroPlayed,
  } = useFilmiumWorkspace();

  const {
    actionErrorMessage,
    errorMessage,
    isLoading,
    toggleFavorite,
    updatingFavoriteItemId,
  } = catalog;

  const {
    availableGenres,
    clearFilters,
    favoriteFilter,
    filteredItems,
    genreFilter,
    mediaTypeFilter,
    searchQuery,
    setFavoriteFilter,
    setGenreFilter,
    setMediaTypeFilter,
    setSearchQuery,
    setWatchStatusFilter,
    watchStatusFilter,
  } = filters;

  // Paljenje FILMIUM ekrana: elementi ulaze postepeno, ali samo jednom po
  // ulasku u domen (Home klik i pod-rute ne ponavljaju animaciju).
  const { searchReady, carouselReady, shelvesReady } =
    useFilmiumIntro(introPlayed, markIntroPlayed);

  // Polje sa žanrovima prikazuje SVE žanrove iz registra (fallback: iz kataloga).
  const genreOptions = allGenres.length > 0 ? allGenres : availableGenres;

  /**
   * Otvara namenski ekran detalja FILMIUM sadržaja.
   */
  function handleOpenDetails(item: MediaItem): void {
    navigate(`/filmium/media/${item.id}`);
  }

  return (
    <>
      {/* ==========          FILTERI (skriveni dok se ne otvore)          ========== */}

      {filtersVisible && (
        <div
          className={`filmium-intro-drop ${
            searchReady ? "is-in" : ""
          }`}
        >
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
            showFavoriteFilter
            showMediaTypeFilter
            visibleCount={filteredItems.length}
            watchStatusFilter={watchStatusFilter}
            onClear={clearFilters}
            onFavoriteChange={setFavoriteFilter}
            onGenreChange={setGenreFilter}
            onMediaTypeChange={setMediaTypeFilter}
            onSearchChange={setSearchQuery}
            onWatchStatusChange={setWatchStatusFilter}
          />
        </div>
      )}

      {/* ==========          FEATURED CAROUSEL          ========== */}

      <div
        className={`filmium-intro-slide ${
          carouselReady ? "is-in" : ""
        }`}
      >
        <FilmiumFeaturedCarousel
          items={filteredItems}
          updatingFavoriteItemId={updatingFavoriteItemId}
          onActiveBackdropChange={setWorkspaceBackdropPath}
          onOpenDetails={handleOpenDetails}
          onToggleFavorite={toggleFavorite}
        />
      </div>

      {isLoading && (
        <p className="system-message">
          Učitavam FILMIUM katalog...
        </p>
      )}

      {!isLoading && !errorMessage && (
        <div
          className={`filmium-intro-rise ${
            shelvesReady ? "is-in" : ""
          }`}
        >
          <FilmiumWishlistShelf
            entries={wishlist.entries}
            onRemove={(entryId) => {
              void wishlist.removeEntry(entryId);
            }}
          />

          <FilmiumHomeShelves
            items={filteredItems}
            onOpenDetails={handleOpenDetails}
          />
        </div>
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
    </>
  );
}

export default FilmiumPage;
