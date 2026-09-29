import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { Check, X } from "lucide-react";

import {
  addToFilmiumShareQueue,
  createFilmiumShareProfile,
  listFilmiumShareProfiles,
  type FilmiumShareProfile,
} from "../../../../services/filmiumShareApi";


// ==========          SVOJSTVA IZBORNIKA PROFILA          ==========

type FilmiumProfilePickerProps = {
  mediaId: number;
  title: string;
  onClose: () => void;
};


// ==========          IZBORNIK PROFILA (MODAL)          ==========

/**
 * Mali centrirani prozor: bira profil (personalizovana kolekcija — npr. za
 * Anđeliju, Srećka, Deki-ja), kreira novi i dodaje trenutni film/seriju u
 * njegov red za deljenje.
 */
function FilmiumProfilePicker({
  mediaId,
  title,
  onClose,
}: FilmiumProfilePickerProps) {
  const [profiles, setProfiles] = useState<FilmiumShareProfile[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [newName, setNewName] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [isAdding, setIsAdding] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    listFilmiumShareProfiles()
      .then((list) => {
        if (isMounted) {
          setProfiles(list);
        }
      })
      .catch(() => {
        if (isMounted) {
          setErrorMessage("Učitavanje profila nije uspelo.");
        }
      });

    return () => {
      isMounted = false;
    };
  }, []);

  /**
   * Kreira novi profil (personalizovana kolekcija) iz upisanog imena.
   */
  async function handleCreate(): Promise<void> {
    const name = newName.trim();
    if (name === "" || isCreating) {
      return;
    }

    setIsCreating(true);
    setErrorMessage(null);
    try {
      const created = await createFilmiumShareProfile({ name });
      setProfiles((current) => [...current, created]);
      setSelectedId(created.id);
      setNewName("");
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : "Kreiranje profila nije uspelo.",
      );
    } finally {
      setIsCreating(false);
    }
  }

  /**
   * Dodaje trenutni sadržaj u red izabranog profila pa zatvara prozor.
   */
  async function handleAdd(): Promise<void> {
    if (selectedId === null || isAdding) {
      return;
    }

    setIsAdding(true);
    setErrorMessage(null);
    try {
      await addToFilmiumShareQueue(selectedId, mediaId, "complete");
      onClose();
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : "Dodavanje u profil nije uspelo.",
      );
    } finally {
      setIsAdding(false);
    }
  }

  return createPortal(
    <div
      className="filmium-collection-picker-overlay"
      onClick={onClose}
      role="presentation"
    >
      <div
        aria-label="Izbor profila"
        className="filmium-collection-picker"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
      >
        {/* ==========          ZAGLAVLJE          ========== */}

        <div className="filmium-collection-picker-head">
          <h3>Dodaj u profil</h3>

          <button
            aria-label="Zatvori"
            className="filmium-collection-picker-close"
            onClick={onClose}
            type="button"
          >
            <X size={16} />
          </button>
        </div>

        <p className="filmium-collection-picker-subtitle">
          „{title}" → izaberi profil (personalizovana kolekcija).
        </p>

        {/* ==========          RED: KREIRAJ + DODAJ          ========== */}

        <div className="filmium-collection-picker-controls">
          <input
            aria-label="Naziv novog profila"
            onChange={(event) => setNewName(event.target.value)}
            placeholder="Novi profil (npr. Anđelija, Srećko, Deki)..."
            type="text"
            value={newName}
          />

          <button
            className="secondary-button"
            disabled={newName.trim() === "" || isCreating}
            onClick={() => void handleCreate()}
            type="button"
          >
            Kreiraj
          </button>

          <button
            className="primary-button"
            disabled={selectedId === null || isAdding}
            onClick={() => void handleAdd()}
            type="button"
          >
            DODAJ
          </button>
        </div>

        {errorMessage && (
          <p className="filmium-collection-picker-error">
            {errorMessage}
          </p>
        )}

        {/* ==========          KARTICE PROFILA          ========== */}

        <div className="filmium-collection-picker-list">
          {profiles.length === 0 && !errorMessage && (
            <p className="filmium-collection-picker-empty">
              Još nema profila. Kreiraj prvi iznad.
            </p>
          )}

          {profiles.map((profile) => {
            const isSelected = selectedId === profile.id;

            return (
              <button
                className={`filmium-collection-picker-card ${
                  isSelected ? "selected" : ""
                }`}
                key={profile.id}
                onClick={() => setSelectedId(profile.id)}
                type="button"
              >
                <span className="filmium-collection-picker-card-name">
                  {profile.name}
                </span>

                {isSelected && (
                  <span className="filmium-collection-picker-card-badge">
                    <Check size={13} />
                    Izabran
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>
    </div>,
    document.body,
  );
}

export default FilmiumProfilePicker;
