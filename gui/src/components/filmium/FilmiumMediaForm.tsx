import { useState, type FormEvent } from "react";

import {
  createFilmiumMediaItem,
  updateFilmiumMediaItem,
} from "../../services/filmiumApi";
import type {
  MediaItem,
  MediaType,
  WatchStatus,
} from "../../types/filmium";
import FilmiumGenreSelector from "../../features/filmium/components/media/FilmiumGenreSelector";


// ==========          SVOJSTVA FORME          ==========

type FilmiumMediaFormProps = {
  editingItem: MediaItem | null;
  onCancelEdit: () => void;
  onSaved: (item: MediaItem, wasUpdated: boolean) => void;
};


// ==========          FILMIUM FORMA          ==========

/**
 * Dodaje novi ili menja postojeći FILMIUM sadržaj.
 */
function FilmiumMediaForm({
  editingItem,
  onCancelEdit,
  onSaved,
}: FilmiumMediaFormProps) {
  // Polja se pune iz stavke koja se menja, i to JEDNOM — pri pravljenju
  // komponente. Roditelj prosleđuje `key` po stavci, pa promena stavke pravi
  // novu formu umesto da efekat prepisuje deset polja preko starih (što je
  // značilo jedan kadar sa tuđim podacima u poljima).
  const [title, setTitle] = useState(() => editingItem?.title ?? "");
  const [originalTitle, setOriginalTitle] = useState(
    () => editingItem?.original_title ?? "",
  );

  const [mediaType, setMediaType] = useState<MediaType>(
    () => editingItem?.media_type ?? "movie",
  );

  const [releaseYear, setReleaseYear] = useState(
    () => editingItem?.release_year?.toString() ?? "",
  );

  const [runtimeMinutes, setRuntimeMinutes] = useState(
    () => editingItem?.runtime_minutes?.toString() ?? "",
  );

  const [watchStatus, setWatchStatus] = useState<WatchStatus>(
    () => editingItem?.watch_status ?? "planned",
  );

  const [rating, setRating] = useState(
    () => editingItem?.rating?.toString() ?? "",
  );
  const [genres, setGenres] = useState<string[]>(
    () => editingItem?.genres ?? [],
  );
  const [notes, setNotes] = useState(() => editingItem?.notes ?? "");
  const [isFavorite, setIsFavorite] = useState(
    () => editingItem?.is_favorite ?? false,
  );

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const maximumReleaseYear = new Date().getFullYear() + 10;
  const isEditing = editingItem !== null;

  /**
   * Šalje nove ili izmenjene podatke FILMIUM API-ju.
   */
  async function handleSubmit(
    event: FormEvent<HTMLFormElement>,
  ): Promise<void> {
    event.preventDefault();

    try {
      setIsSubmitting(true);
      setErrorMessage(null);

      const request = {
        title,
        original_title: originalTitle || null,
        media_type: mediaType,
        release_year: releaseYear ? Number(releaseYear) : null,
        runtime_minutes:
          runtimeMinutes ? Number(runtimeMinutes) : null,
        watch_status: watchStatus,
        rating: rating ? Number(rating) : null,
        genres,
        notes: notes || null,
        is_favorite: isFavorite,
      };

      const savedItem = editingItem
        ? await updateFilmiumMediaItem(editingItem.id, request)
        : await createFilmiumMediaItem(request);

      onSaved(savedItem, isEditing);

      if (!isEditing) {
        setTitle("");
        setOriginalTitle("");
        setReleaseYear("");
        setRuntimeMinutes("");
        setRating("");
        setNotes("");
        setWatchStatus("planned");
        setGenres([]);
        setIsFavorite(false);
      }
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : "Čuvanje FILMIUM sadržaja nije uspelo.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form className="filmium-form" onSubmit={handleSubmit}>
      <div className="filmium-form-grid">
        <label className="filmium-field">
          <span>Naslov</span>
          <input
            maxLength={300}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="Na primer: The Matrix"
            required
            type="text"
            value={title}
          />
        </label>

        <label className="filmium-field">
          <span>Originalni naslov</span>
          <input
            maxLength={300}
            onChange={(event) => setOriginalTitle(event.target.value)}
            placeholder="Opcionalno"
            type="text"
            value={originalTitle}
          />
        </label>

        <label className="filmium-field">
          <span>Tip sadržaja</span>
          <select
            onChange={(event) =>
              setMediaType(event.target.value as MediaType)
            }
            value={mediaType}
          >
            <option value="movie">Film</option>
            <option value="series">Serija</option>
          </select>
        </label>

        <label className="filmium-field">
          <span>Godina</span>
          <input
            max={maximumReleaseYear}
            min={1888}
            onChange={(event) => setReleaseYear(event.target.value)}
            placeholder="2024"
            type="number"
            value={releaseYear}
          />
        </label>

        <label className="filmium-field">
  <span>Trajanje u minutima</span>

  <input
    max={10_000}
    min={1}
    onChange={(event) =>
      setRuntimeMinutes(event.target.value)
    }
    placeholder="Na primer: 155"
    type="number"
    value={runtimeMinutes}
  />
</label>

        <label className="filmium-field">
          <span>Status gledanja</span>
          <select
            onChange={(event) =>
              setWatchStatus(event.target.value as WatchStatus)
            }
            value={watchStatus}
          >
            <option value="planned">Planirano</option>
            <option value="watching">Gledam</option>
            <option value="completed">Odgledano</option>
            <option value="paused">Pauzirano</option>
            <option value="dropped">Napušteno</option>
          </select>
        </label>

        <label className="filmium-field">
          <span>Ocena</span>
          <input
            max={10}
            min={1}
            onChange={(event) => setRating(event.target.value)}
            placeholder="1–10"
            type="number"
            value={rating}
          />
        </label>


        {/* ==========          ZANROVI          ========== */}

        <FilmiumGenreSelector
          disabled={isSubmitting}
          onChange={setGenres}
          selectedGenres={genres}
        />



        {/* ==========          FAVORITE STATUS          ========== */}

        <label className="filmium-favorite-field filmium-field-wide">
        <input
            checked={isFavorite}
            onChange={(event) => setIsFavorite(event.target.checked)}
            type="checkbox"
        />

        <span>
            <strong>Omiljeni sadržaj</strong>
            <small>
            Označi film ili seriju za prikaz u Favorites kolekciji.
            </small>
        </span>
        </label>


{/* ==========          BELESKE          ========== */}
        <label className="filmium-field filmium-field-wide">
          <span>Beleška</span>
          <textarea
            maxLength={10_000}
            onChange={(event) => setNotes(event.target.value)}
            placeholder="Lična beleška o filmu ili seriji..."
            rows={4}
            value={notes}
          />
        </label>
      </div>

      {errorMessage && (
        <p className="system-message error">{errorMessage}</p>
      )}

      <div className="filmium-form-actions">
        {isEditing && (
          <button
            className="secondary-button"
            disabled={isSubmitting}
            onClick={onCancelEdit}
            type="button"
          >
            Otkaži izmenu
          </button>
        )}

        <button
          className="primary-button"
          disabled={isSubmitting}
          type="submit"
        >
          {isSubmitting
            ? "Čuvanje..."
            : isEditing
              ? "Sačuvaj izmene"
              : "Dodaj u katalog"}
        </button>
      </div>
    </form>
  );
}

export default FilmiumMediaForm;