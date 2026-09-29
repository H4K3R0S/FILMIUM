import FilmiumLibraryManager from "../features/filmium/components/uploads/FilmiumLibraryManager";
import FilmiumSubtitleRepairPanel from "../features/filmium/components/uploads/FilmiumSubtitleRepairPanel";
import "../features/filmium/styles/filmium-uploads.css";
import "../features/filmium/styles/filmium-uploads-layout.css";

function FilmiumUploadsPage() {
  return (
    <section className="filmium-section filmium-uploads-page">
      <header className="filmium-uploads-page-heading">
        <div>
          <h1>FILMIUM biblioteka</h1>
          <p>Skeniranje, uvoz i praćenje lokalne kolekcije.</p>
        </div>
      </header>

      <FilmiumLibraryManager />

      <FilmiumSubtitleRepairPanel />
    </section>
  );
}

export default FilmiumUploadsPage;
