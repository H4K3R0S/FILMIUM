import { ArrowLeft, FilePenLine } from "lucide-react";
import {
  useNavigate,
  useParams,
} from "react-router";

import FilmiumMediaForm from "../components/filmium/FilmiumMediaForm";
import FilmiumAssetFields from "../features/filmium/components/media/FilmiumAssetFields";
import { useFilmiumWorkspace } from "../features/filmium/context/useFilmiumWorkspace";
import "../features/filmium/styles/filmium-media-editor.css";
import type { MediaItem } from "../types/filmium";


/**
 * Poseban ekran za ručni unos i uređivanje FILMIUM informacija.
 */
function FilmiumMediaEditorPage() {
  const navigate = useNavigate();
  const { itemId } = useParams();
  const { catalog } = useFilmiumWorkspace();
  const isCreating = itemId === undefined;
  const parsedItemId = Number(itemId);
  const editingItem = isCreating
    ? null
    : catalog.items.find(
        (item) => item.id === parsedItemId,
      ) ?? null;

  function handleCancel(): void {
    catalog.cancelMediaEdit();

    if (editingItem) {
      navigate(`/filmium/media/${editingItem.id}`);
      return;
    }

    navigate("/filmium/uploads");
  }

  function handleSaved(
    item: MediaItem,
    wasUpdated: boolean,
  ): void {
    catalog.saveMediaItem(item, wasUpdated);
    navigate(`/filmium/media/${item.id}`);
  }

  if (catalog.isLoading) {
    return (
      <p className="system-message">
        Učitavam FILMIUM sadržaj...
      </p>
    );
  }

  if (!isCreating && editingItem === null) {
    return (
      <section className="filmium-section">
        <p className="system-message error">
          Sadržaj koji želiš da izmeniš nije pronađen.
        </p>
        <button
          className="secondary-button"
          onClick={() => navigate("/filmium/library")}
          type="button"
        >
          <ArrowLeft size={17} />
          Vrati se u biblioteku
        </button>
      </section>
    );
  }

  return (
    <section className="filmium-section filmium-media-editor-page">
      <header className="filmium-media-editor-heading">
        <button
          aria-label="Nazad"
          className="filmium-library-icon-button"
          onClick={handleCancel}
          type="button"
        >
          <ArrowLeft size={18} />
        </button>

        <div>
          <p className="eyebrow">
            {editingItem ? "Izmena informacija" : "Ručni unos"}
          </p>
          <h1>
            {editingItem
              ? `Izmeni: ${editingItem.title}`
              : "Dodaj sadržaj bez video fajla"}
          </h1>
          <p>
            Ovaj ekran menja podatke kataloga. Skeniranje i
            organizovanje fizičkih fajlova ostaje na Uploads stranici.
          </p>
        </div>

        <FilePenLine size={28} />
      </header>

      <div className="filmium-media-editor-panel">
        <FilmiumMediaForm
          // Nova stavka = nova forma: polja se pune pri pravljenju komponente.
          key={editingItem?.id ?? "nova"}
          editingItem={editingItem}
          onCancelEdit={handleCancel}
          onSaved={handleSaved}
        />
      </div>

      {editingItem ? (
        <FilmiumAssetFields
          item={editingItem}
          onUpdated={catalog.updateMediaItem}
        />
      ) : (
        <div className="filmium-upload-assets-notice">
          Poster i backdrop biće dostupni nakon prvog čuvanja.
        </div>
      )}
    </section>
  );
}

export default FilmiumMediaEditorPage;
