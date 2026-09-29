import FilmiumCollectionsPanel from "../components/filmium/FilmiumCollectionsPanel";
import { useFilmiumWorkspace } from "../features/filmium/context/useFilmiumWorkspace";


// ==========          FILMIUM COLLECTIONS EKRAN          ==========

/**
 * Prikazuje i upravlja FILMIUM kolekcijama.
 */
function FilmiumCollectionsPage() {
  const { collections: collectionState } =
    useFilmiumWorkspace();

  const {
    collectionErrorMessage,
    collections,
    createCollection,
    deleteCollection,
    deletingCollectionId,
  } = collectionState;

  return (
    <section className="filmium-section filmium-collections-page">
      <div className="section-heading">
        <p className="eyebrow">FILMIUM Library</p>
        <h2>Kolekcije</h2>

        <p className="filmium-page-description">
          Organizuj filmove i serije u sopstvene tematske kolekcije.
        </p>
      </div>

      {collectionErrorMessage && (
        <p className="system-message error">
          {collectionErrorMessage}
        </p>
      )}

      <FilmiumCollectionsPanel
        collections={collections}
        deletingCollectionId={deletingCollectionId}
        onCreate={createCollection}
        onDelete={deleteCollection}
      />
    </section>
  );
}

export default FilmiumCollectionsPage;