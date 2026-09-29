import { ChevronRight } from "lucide-react";


// ==========          SVOJSTVA GENRE BARA          ==========

type FilmiumGenreBarProps = {
  availableGenres: string[];
  selectedGenre: string;
  onGenreChange: (genre: string) => void;
};


// ==========          FILMIUM GENRE BAR          ==========

/**
 * Prikazuje žanrove u jednom responsive horizontalnom redu.
 */
function FilmiumGenreBar({
  availableGenres,
  selectedGenre,
  onGenreChange,
}: FilmiumGenreBarProps) {
  /**
   * Pomera listu žanrova udesno.
   */
  function handleScrollRight(): void {
    document
      .querySelector(".filmium-genre-scroll")
      ?.scrollBy({
        behavior: "smooth",
        left: 320,
      });
  }

  return (
    <div className="filmium-genre-bar">
      <div className="filmium-genre-scroll">
        <button
          className={`filmium-genre-option ${
            selectedGenre === "all" ? "active" : ""
          }`}
          onClick={() => onGenreChange("all")}
          type="button"
        >
          Svi žanrovi
        </button>

        {availableGenres.map((genre) => (
          <button
            className={`filmium-genre-option ${
              selectedGenre === genre ? "active" : ""
            }`}
            key={genre}
            onClick={() => onGenreChange(genre)}
            type="button"
          >
            {genre}
          </button>
        ))}
      </div>

      <div
        aria-hidden="true"
        className="filmium-genre-fade"
      />

      <button
        aria-label="Prikaži još žanrova"
        className="filmium-genre-next"
        onClick={handleScrollRight}
        title="Još žanrova"
        type="button"
      >
        <ChevronRight aria-hidden="true" size={18} />
      </button>
    </div>
  );
}

export default FilmiumGenreBar;