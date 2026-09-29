import type {
  FavoriteFilter,
  MediaTypeFilter,
  WatchStatusFilter,
} from "../../types/filmium";



// ==========          SVOJSTVA ALATNE TRAKE          ==========

type FilmiumToolbarProps = {
  searchQuery: string;
  mediaTypeFilter: MediaTypeFilter;
  watchStatusFilter: WatchStatusFilter;
  favoriteFilter: FavoriteFilter;
  visibleCount: number;
  availableGenres: string[];
  genreFilter: string;
  onSearchChange: (value: string) => void;
  onMediaTypeChange: (value: MediaTypeFilter) => void;
  onWatchStatusChange: (value: WatchStatusFilter) => void;
  onFavoriteChange: (value: FavoriteFilter) => void;
  onGenreChange: (value: string) => void;
  onClear: () => void;
  showMediaTypeFilter?: boolean;
  showFavoriteFilter?: boolean;
};


// ==========          FILMIUM ALATNA TRAKA          ==========

/**
 * Prikazuje pretragu i filtere FILMIUM kataloga.
 */
function FilmiumToolbar({
  searchQuery,
  mediaTypeFilter,
  watchStatusFilter,
  favoriteFilter,
  visibleCount,
  availableGenres,
  genreFilter,
  showMediaTypeFilter = true,
  showFavoriteFilter = true,
  onSearchChange,
  onMediaTypeChange,
  onWatchStatusChange,
  onFavoriteChange,
  onGenreChange,
  onClear,
}: FilmiumToolbarProps) {

  const hasActiveFilters =
    searchQuery.trim() !== "" ||
    (showMediaTypeFilter && mediaTypeFilter !== "all") ||
    watchStatusFilter !== "all" ||
    genreFilter !== "all" ||
    (showFavoriteFilter && favoriteFilter !== "all");

  return (
    <div className="filmium-toolbar">
      <label className="filmium-search">
        <span>Pretraga kataloga</span>

        <input
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder="Pretraži naslove i beleške..."
          type="search"
          value={searchQuery}
        />
      </label>

      {showMediaTypeFilter && (
        <label className="filmium-filter">
          <span>Tip</span>

          <select
            onChange={(event) =>
              onMediaTypeChange(
                event.target.value as MediaTypeFilter,
              )
            }
            value={mediaTypeFilter}
          >
            <option value="all">Sve</option>
            <option value="movie">Filmovi</option>
            <option value="series">Serije</option>
          </select>
        </label>
      )}

      <label className="filmium-filter">
        <span>Status</span>

        <select
          onChange={(event) =>
            onWatchStatusChange(
              event.target.value as WatchStatusFilter,
            )
          }
          value={watchStatusFilter}
        >
          <option value="all">Svi statusi</option>
          <option value="planned">Planirano</option>
          <option value="watching">Gledam</option>
          <option value="completed">Odgledano</option>
          <option value="paused">Pauzirano</option>
          <option value="dropped">Napušteno</option>
        </select>
      </label>

      <label className="filmium-filter">
        <span>Žanr</span>

        <select
          onChange={(event) => onGenreChange(event.target.value)}
          value={genreFilter}
        >
          <option value="all">Svi žanrovi</option>

          {availableGenres.map((genre) => (
            <option key={genre} value={genre}>
              {genre}
            </option>
          ))}
        </select>
      </label>

      {showFavoriteFilter && (
        <label className="filmium-filter">
          <span>Omiljeno</span>

          <select
            onChange={(event) =>
              onFavoriteChange(
                event.target.value as FavoriteFilter,
              )
            }
            value={favoriteFilter}
          >
            <option value="all">Svi sadržaji</option>
            <option value="favorites">Samo omiljeni</option>
          </select>
        </label>
      )}

      <div className="filmium-toolbar-summary">
        <span>{visibleCount} rezultata</span>

        <button
          className="secondary-button"
          disabled={!hasActiveFilters}
          onClick={onClear}
          type="button"
        >
          Očisti filtere
        </button>
      </div>
    </div>
  );
}

export default FilmiumToolbar;