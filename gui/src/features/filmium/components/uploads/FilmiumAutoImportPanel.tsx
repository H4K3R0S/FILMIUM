import { useState } from "react";
import {
  Check,
  FolderPlus,
  RefreshCw,
  ShieldCheck,
  Trash2,
  X,
} from "lucide-react";
import { openPathDialog } from "../../../../lib/pathPicker";

import { useFilmiumAutoImport } from "../../hooks/useFilmiumAutoImport";
import type { DetectedFile } from "../../../../types/filmiumAutoImport";


function folderLabel(path: string): string {
  return path.split(/[\\/]/).filter(Boolean).at(-1) ?? path;
}

function statusLabel(status: DetectedFile["status"]): string {
  switch (status) {
    case "ready":
      return "Spreman";
    case "imported":
      return "Uvezen";
    case "rejected":
      return "Odbačen";
    case "scanning":
      return "Skeniram";
    default:
      return "Detektovan";
  }
}


/**
 * Panel za automatsko praćenje foldera (Downloads, VIDEO…): dodavanje foldera,
 * lista praćenih, i detektovani novi video fajlovi sa potvrdom/odbacivanjem.
 */
export default function FilmiumAutoImportPanel() {
  const {
    folders,
    detected,
    isLoading,
    errorMessage,
    refresh,
    addFolder,
    removeFolder,
    confirmFile,
    rejectFile,
  } = useFilmiumAutoImport();
  const [isBusy, setIsBusy] = useState(false);

  async function pickAndAddFolder(): Promise<void> {
    setIsBusy(true);
    try {
      const selected = await openPathDialog({
        directory: true,
        multiple: false,
        title: "Izaberi folder za automatsko praćenje",
      });
      if (typeof selected === "string") {
        await addFolder({ folder_path: selected, security_scan: true });
      }
    } finally {
      setIsBusy(false);
    }
  }

  return (
    <section className="filmium-auto-import-panel">
      <div className="filmium-library-aside-heading">
        <h3>Automatsko praćenje</h3>
        <button
          aria-label="Osveži"
          onClick={() => void refresh()}
          type="button"
        >
          <RefreshCw size={15} />
        </button>
      </div>

      {errorMessage && (
        <p className="system-message error">{errorMessage}</p>
      )}

      <button
        className="primary-button"
        disabled={isBusy}
        onClick={() => void pickAndAddFolder()}
        type="button"
      >
        <FolderPlus size={16} />
        Dodaj folder
      </button>

      {/* ========== PRAĆENI FOLDERI ========== */}
      {folders.length > 0 && (
        <ul className="filmium-auto-import-folders">
          {folders.map((folder) => (
            <li key={folder.folder_path}>
              <span title={folder.folder_path}>
                {folderLabel(folder.folder_path)}
              </span>
              <button
                aria-label={`Ukloni ${folderLabel(folder.folder_path)}`}
                onClick={() => void removeFolder(folder.folder_path)}
                type="button"
              >
                <Trash2 size={14} />
              </button>
            </li>
          ))}
        </ul>
      )}

      {/* ========== DETEKTOVANI FAJLOVI ========== */}
      <div className="filmium-auto-import-detected">
        <h4>
          Detektovano
          <span>{detected.length}</span>
        </h4>

        {isLoading ? (
          <p className="filmium-library-aside-empty">Učitavam…</p>
        ) : detected.length === 0 ? (
          <p className="filmium-library-aside-empty">
            Novi fajlovi iz praćenih foldera pojaviće se ovde.
          </p>
        ) : (
          detected.map((file) => (
            <article
              className={`filmium-auto-import-item status-${file.status}`}
              key={file.id}
            >
              <div>
                <strong title={file.file_path}>
                  {folderLabel(file.file_path)}
                </strong>
                <small>
                  {file.security_status !== "unknown" && (
                    <ShieldCheck size={12} />
                  )}
                  {statusLabel(file.status)}
                </small>
              </div>
              {file.status === "ready" && (
                <div className="filmium-auto-import-actions">
                  <button
                    aria-label="Potvrdi uvoz"
                    onClick={() => void confirmFile(file.id)}
                    type="button"
                  >
                    <Check size={15} />
                  </button>
                  <button
                    aria-label="Odbaci"
                    onClick={() => void rejectFile(file.id)}
                    type="button"
                  >
                    <X size={15} />
                  </button>
                </div>
              )}
            </article>
          ))
        )}
      </div>
    </section>
  );
}
