import { getCurrentWindow } from "@tauri-apps/api/window";


// ==========          CUSTOM TITLEBAR          ==========

/**
 * Borderless titlebar bez OS okvira, brenda i pozadine. Cela traka pomera
 * prozor (data-tauri-drag-region); kontrole desno rade minimize/maximize/close.
 */
function TitleBar() {
  return (
    <div className="titlebar" data-tauri-drag-region>
      <div className="titlebar-controls">
        <button
          aria-label="Minimizuj"
          className="titlebar-button titlebar-minimize"
          onClick={() => getCurrentWindow().minimize()}
          type="button"
        >
          <span className="titlebar-glyph" aria-hidden="true" />
        </button>

        <button
          aria-label="Maksimizuj"
          className="titlebar-button titlebar-maximize"
          onClick={() => getCurrentWindow().toggleMaximize()}
          type="button"
        >
          <span className="titlebar-glyph" aria-hidden="true" />
        </button>

        <button
          aria-label="Zatvori"
          className="titlebar-button titlebar-close"
          onClick={() => getCurrentWindow().close()}
          type="button"
        >
          <span className="titlebar-glyph" aria-hidden="true" />
        </button>
      </div>
    </div>
  );
}

export default TitleBar;
