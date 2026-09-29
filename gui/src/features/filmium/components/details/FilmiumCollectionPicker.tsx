import { useState } from "react";
import { createPortal } from "react-dom";
import { Check, X } from "lucide-react";

import type {
  CollectionCreateRequest,
  MediaCollection,
} from "../../../../types/filmium";


// ==========          SVOJSTVA IZBORNIKA KOLEKCIJA          ==========

type FilmiumCollectionPickerProps = {
  collections: MediaCollection[];
  itemId: number;
  busyMembershipKey: string | null;
  errorMessage: string | null;
  onCreateCollection: (
    request: CollectionCreateRequest,
  ) => Promise<void>;
  onAddToCollection: (
    collectionId: number,
    itemId: number,
  ) => Promise<void>;
  onClose: () => void;
};


// ==========          IZBORNIK KOLEKCIJA (MODAL)          ==========

/**
 * Mali centrirani prozor: bira kolekciju (kartice jedna ispod druge),
 * kreira novu i dodaje trenutni sadržaj u izabranu.
 */
function FilmiumCollectionPicker({
  collections,
  itemId,
  busyMembershipKey,
  errorMessage,
  onCreateCollection,
  onAddToCollection,
  onClose,
}: FilmiumCollectionPickerProps) {
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [newName, setNewName] = useState("");
  const [isCreating, setIsCreating] = useState(false);

  const isAdding = busyMembershipKey !== null;

  /**
   * Kreira novu kolekciju iz upisanog imena.
   */
  async function handleCreate(): Promise<void> {
    const name = newName.trim();
    if (name === "" || isCreating) {
      return;
    }

    setIsCreating(true);
    try {
      await onCreateCollection({ name });
      setNewName("");
    } finally {
      setIsCreating(false);
    }
  }

  /**
   * Dodaje trenutni sadržaj u izabranu kolekciju pa zatvara prozor.
   */
  async function handleAdd(): Promise<void> {
    if (selectedId === null || isAdding) {
      return;
    }

    await onAddToCollection(selectedId, itemId);
    onClose();
  }

  return createPortal(
    <div
      className="filmium-collection-picker-overlay"
      onClick={onClose}
      role="presentation"
    >
      <div
        aria-label="Izbor kolekcije"
        className="filmium-collection-picker"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
      >
        {/* ==========          ZAGLAVLJE          ========== */}

        <div className="filmium-collection-picker-head">
          <h3>Kolekcije</h3>

          <button
            aria-label="Zatvori"
            className="filmium-collection-picker-close"
            onClick={onClose}
            type="button"
          >
            <X size={16} />
          </button>
        </div>

        {/* ==========          RED: KREIRAJ + DODAJ          ========== */}

        <div className="filmium-collection-picker-controls">
          <input
            aria-label="Naziv nove kolekcije"
            onChange={(event) => setNewName(event.target.value)}
            placeholder="Naziv nove kolekcije..."
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

        {/* ==========          KARTICE KOLEKCIJA          ========== */}

        <div className="filmium-collection-picker-list">
          {collections.length === 0 && (
            <p className="filmium-collection-picker-empty">
              Još nema kolekcija. Kreiraj prvu iznad.
            </p>
          )}

          {collections.map((collection) => {
            const alreadyIn = collection.item_ids.includes(itemId);
            const isSelected = selectedId === collection.id;

            return (
              <button
                className={`filmium-collection-picker-card ${
                  isSelected ? "selected" : ""
                }`}
                key={collection.id}
                onClick={() => setSelectedId(collection.id)}
                type="button"
              >
                <span className="filmium-collection-picker-card-name">
                  {collection.name}
                </span>

                {alreadyIn ? (
                  <span className="filmium-collection-picker-card-badge">
                    <Check size={13} />
                    Dodato
                  </span>
                ) : (
                  <span className="filmium-collection-picker-card-count">
                    {collection.item_ids.length}
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

export default FilmiumCollectionPicker;
