import { useEffect, useMemo, useState } from "react";

import { getFilmiumGenres } from "../../../../services/filmiumApi";
import "../../styles/filmium-genres.css";


// ==========          SVOJSTVA SELEKTORA          ==========

type FilmiumGenreSelectorProps = {
  disabled?: boolean;
  onChange: (genres: string[]) => void;
  selectedGenres: string[];
};


// ==========          FILMIUM GENRE SELECTOR          ==========

/**
 * Prikazuje kontrolisanu listu FILMIUM zanrova.
 */
function FilmiumGenreSelector({
  disabled = false,
  onChange,
  selectedGenres,
}: FilmiumGenreSelectorProps) {
  const [availableGenres, setAvailableGenres] = useState<string[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let isCancelled = false;

    async function loadGenres(): Promise<void> {
      try {
        setIsLoading(true);
        setErrorMessage(null);

        const genres = await getFilmiumGenres();

        if (!isCancelled) {
          setAvailableGenres(genres);
        }
      } catch (error) {
        if (!isCancelled) {
          setErrorMessage(
            error instanceof Error
              ? error.message
              : "Ucitavanje zanrova nije uspelo.",
          );
        }
      } finally {
        if (!isCancelled) {
          setIsLoading(false);
        }
      }
    }

    void loadGenres();

    return () => {
      isCancelled = true;
    };
  }, [reloadKey]);

  const selectedGenreKeys = useMemo(
    () => new Set(
      selectedGenres.map((genre) => genre.toLocaleLowerCase()),
    ),
    [selectedGenres],
  );

  const availableGenreKeys = useMemo(
    () => new Set(availableGenres.map((genre) => genre.toLocaleLowerCase())),
    [availableGenres],
  );

  const legacyGenres = selectedGenres.filter(
    (genre) => !availableGenreKeys.has(genre.toLocaleLowerCase()),
  );

  function toggleGenre(genre: string): void {
    const genreKey = genre.toLocaleLowerCase();
    const isSelected = selectedGenreKeys.has(genreKey);

    if (isSelected) {
      onChange(
        selectedGenres.filter(
          (selectedGenre) =>
            selectedGenre.toLocaleLowerCase() !== genreKey,
        ),
      );
      return;
    }

    onChange([...selectedGenres, genre]);
  }

  return (
    <fieldset
      className="filmium-genre-selector filmium-field-wide"
      disabled={disabled}
    >
      <legend>{"\u017danrovi"}</legend>

      <p className="filmium-genre-help">
        {"Izaberi jedan ili vi\u0161e \u017eanrova."}
      </p>

      {isLoading && (
        <p className="filmium-genre-status">
          {"U\u010ditavam \u017eanrove..."}
        </p>
      )}

      {errorMessage && (
        <div className="filmium-genre-error" role="alert">
          <span>{errorMessage}</span>

          <button
            className="secondary-button"
            onClick={() => setReloadKey((value) => value + 1)}
            type="button"
          >
            {"Poku\u0161aj ponovo"}
          </button>
        </div>
      )}

      {!isLoading && !errorMessage && legacyGenres.length > 0 && (
        <div className="filmium-genre-legacy">
          <small>
            {"Stari \u017eanrovi vi\u0161e nisu u aktivnom registru. "}
            {"Klikni da ih ukloni\u0161."}
          </small>

          <div className="filmium-genre-options">
            {legacyGenres.map((genre) => (
              <button
                aria-pressed="true"
                className="filmium-genre-chip legacy active"
                key={genre}
                onClick={() => toggleGenre(genre)}
                type="button"
              >
                {genre}
              </button>
            ))}
          </div>
        </div>
      )}

      {!isLoading && !errorMessage && (
        <div
          aria-label={"Dostupni \u017eanrovi"}
          className="filmium-genre-options"
        >
          {availableGenres.map((genre) => {
            const isSelected = selectedGenreKeys.has(
              genre.toLocaleLowerCase(),
            );

            return (
              <button
                aria-pressed={isSelected}
                className={
                  `filmium-genre-chip${isSelected ? " active" : ""}`
                }
                key={genre}
                onClick={() => toggleGenre(genre)}
                type="button"
              >
                {genre}
              </button>
            );
          })}
        </div>
      )}
    </fieldset>
  );
}

export default FilmiumGenreSelector;