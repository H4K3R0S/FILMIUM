// ==========          DOGAĐAJI FILMIUM KATALOGA          ==========

export const FILMIUM_CATALOG_CHANGED_EVENT =
  "filmium:catalog-changed";


/**
 * Obaveštava aktivno FILMIUM radno okruženje da ponovo učita katalog.
 */
export function notifyFilmiumCatalogChanged(): void {
  window.dispatchEvent(
    new Event(FILMIUM_CATALOG_CHANGED_EVENT),
  );
}
