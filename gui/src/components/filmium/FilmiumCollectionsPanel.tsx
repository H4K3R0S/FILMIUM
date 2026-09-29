import { useState, type FormEvent } from "react";

import type {
  CollectionCreateRequest,
  MediaCollection,
} from "../../types/filmium";


// ==========          SVOJSTVA COLLECTION PANELA          ==========

type FilmiumCollectionsPanelProps = {
  collections: MediaCollection[];
  deletingCollectionId: number | null;
  onCreate: (request: CollectionCreateRequest) => Promise<void>;
  onDelete: (collection: MediaCollection) => void;
};


// ==========          COLLECTION PANEL          ==========

/**
 * Prikazuje i kreira FILMIUM kolekcije.
 */
function FilmiumCollectionsPanel({
  collections,
  deletingCollectionId,
  onCreate,
  onDelete,
}: FilmiumCollectionsPanelProps) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  /**
   * Kreira novu FILMIUM kolekciju.
   */
  async function handleSubmit(
    event: FormEvent<HTMLFormElement>,
  ): Promise<void> {
    event.preventDefault();

    try {
      setIsSubmitting(true);
      setErrorMessage(null);

      await onCreate({
        name,
        description: description || null,
      });

      setName("");
      setDescription("");
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : "Kreiranje FILMIUM kolekcije nije uspelo.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="filmium-collections-layout">
      {/* ==========          NOVA KOLEKCIJA          ========== */}

      <form
        className="filmium-collection-form"
        onSubmit={handleSubmit}
      >
        <label className="filmium-field">
          <span>Naziv kolekcije</span>
          <input
            maxLength={100}
            onChange={(event) => setName(event.target.value)}
            placeholder="Na primer: Sci-Fi Favorites"
            required
            type="text"
            value={name}
          />
        </label>

        <label className="filmium-field">
          <span>Opis</span>
          <textarea
            maxLength={2_000}
            onChange={(event) => setDescription(event.target.value)}
            placeholder="Opcioni opis kolekcije..."
            rows={3}
            value={description}
          />
        </label>

        {errorMessage && (
          <p className="system-message error">{errorMessage}</p>
        )}

        <button
          className="primary-button"
          disabled={isSubmitting}
          type="submit"
        >
          {isSubmitting ? "Kreiranje..." : "Kreiraj kolekciju"}
        </button>
      </form>

      {/* ==========          LISTA KOLEKCIJA          ========== */}

      <div className="filmium-collection-list">
        {collections.length === 0 ? (
          <p className="system-message">
            Još nema FILMIUM kolekcija.
          </p>
        ) : (
          collections.map((collection) => (
            <article
              className="filmium-collection-card"
              key={collection.id}
            >
              <div>
                <h3>{collection.name}</h3>

                {collection.description && (
                  <p>{collection.description}</p>
                )}

                <span>
                  {collection.item_ids.length} sadržaja
                </span>
              </div>

              <button
                className="danger-button"
                disabled={
                  deletingCollectionId === collection.id
                }
                onClick={() => onDelete(collection)}
                type="button"
              >
                {deletingCollectionId === collection.id
                  ? "Brisanje..."
                  : "Obriši"}
              </button>
            </article>
          ))
        )}
      </div>
    </div>
  );
}

export default FilmiumCollectionsPanel;