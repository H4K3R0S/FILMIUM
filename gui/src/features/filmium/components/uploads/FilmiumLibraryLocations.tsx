import {
  Check,
  EllipsisVertical,
  HardDrive,
  LoaderCircle,
  RefreshCw,
  Trash2,
  WifiOff,
} from "lucide-react";
import { useEffect, useState } from "react";

import type {
  FilmiumLibraryRoot,
  FilmiumLibraryScanResult,
} from "../../../../types/filmiumLibrary";


const STATUS_LABELS = {
  never_scanned: "Nije skenirano",
  available: "Dostupna",
  offline: "Disk nije povezan",
  disabled: "Isključena",
} as const;


function statusClass(root: FilmiumLibraryRoot): string {
  return `status-${root.last_scan_status.replace("_", "-")}`;
}


type FilmiumLibraryLocationsProps = {
  busyRootId: number | null;
  isLoading: boolean;
  onlyNew: boolean;
  onRemove: (rootId: number) => void;
  onScan: (rootId: number) => void;
  onScanAll: () => void;
  onSetMain: (rootId: number) => void;
  onSetPersistence: (
    rootId: number,
    isPersistent: boolean,
  ) => void;
  onToggleOnlyNew: () => void;
  onToggleScanSubtitles: () => void;
  roots: FilmiumLibraryRoot[];
  scanResults: Record<number, FilmiumLibraryScanResult>;
  scanSubtitles: boolean;
};


function formatScanTime(value: string | null): string {
  if (!value) {
    return "Još nije skenirano";
  }

  return new Intl.DateTimeFormat("sr-Latn-RS", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
}


/**
 * Pretvara broj bajtova u kompaktnu, čitljivu veličinu (npr. "1.24 TB").
 */
function formatBytes(bytes: number): string {
  const units = ["B", "KB", "MB", "GB", "TB", "PB"];
  let value = bytes;
  let unitIndex = 0;

  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }

  const decimals = unitIndex >= 3 ? 2 : unitIndex === 0 ? 0 : 1;

  return `${value.toFixed(decimals)} ${units[unitIndex]}`;
}


/**
 * Prikazuje registrovane diskove i direktorijume sa njihovim akcijama.
 */
export default function FilmiumLibraryLocations({
  busyRootId,
  isLoading,
  onlyNew,
  onRemove,
  onScan,
  onScanAll,
  onSetMain,
  onSetPersistence,
  onToggleOnlyNew,
  onToggleScanSubtitles,
  roots,
  scanResults,
  scanSubtitles,
}: FilmiumLibraryLocationsProps) {
  const [openMenuId, setOpenMenuId] = useState<number | null>(null);

  // Zatvori otvoreni meni klikom van njega ili tasterom Escape.
  useEffect(() => {
    if (openMenuId === null) {
      return;
    }

    function handlePointerDown(event: MouseEvent): void {
      const target = event.target as HTMLElement | null;
      if (!target?.closest(".filmium-library-menu-wrap")) {
        setOpenMenuId(null);
      }
    }

    function handleKeyDown(event: KeyboardEvent): void {
      if (event.key === "Escape") {
        setOpenMenuId(null);
      }
    }

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [openMenuId]);

  return (
    <section className="filmium-library-manager">
      <div className="filmium-library-heading">
        <div>
          <p className="eyebrow">Lokacije biblioteke</p>
          <h2>Diskovi i direktorijumi</h2>
        </div>
        <div className="filmium-library-scan-controls">
          <button
            aria-label="Uključi/isključi skeniranje prevoda"
            aria-pressed={scanSubtitles}
            className={`filmium-scan-toggle${scanSubtitles ? " on" : ""}`}
            onClick={onToggleScanSubtitles}
            title="Kada je uključeno, sken obuhvata i prevode"
            type="button"
          >
            PREVODI
          </button>
          <button
            aria-label="Prikaži samo nove filmove i serije"
            aria-pressed={onlyNew}
            className={`filmium-scan-toggle${onlyNew ? " on" : ""}`}
            onClick={onToggleOnlyNew}
            title="Kada je uključeno, prikazuju se samo nove stavke"
            type="button"
          >
            SAMO NOVO
          </button>
          <button
            aria-label="Skeniraj sve lokacije"
            className="secondary-button"
            disabled={isLoading || busyRootId !== null}
            onClick={onScanAll}
            type="button"
          >
            <RefreshCw size={17} />
            Skeniraj sve
          </button>
        </div>
      </div>

      {roots.length === 0 && !isLoading && (
        <p className="filmium-library-empty">
          Dodaj trajnu lokaciju ili izaberi folder za skeniranje.
        </p>
      )}

      <div className="filmium-library-list">
        {roots.map((root) => {
          const isBusy = busyRootId === root.id;
          const menuOpen = openMenuId === root.id;
          const scanResult = scanResults[root.id];

          const hasCapacity =
            typeof root.total_bytes === "number" &&
            root.total_bytes > 0 &&
            typeof root.free_bytes === "number";
          const usedBytes = hasCapacity
            ? Math.max(0, root.total_bytes! - root.free_bytes!)
            : 0;
          const usedPercent = hasCapacity
            ? Math.min(100, Math.round((usedBytes / root.total_bytes!) * 100))
            : 0;

          return (
            <article
              className={`filmium-library-card${
                menuOpen ? " menu-open" : ""
              }`}
              key={root.id}
            >
              <div className="filmium-library-card-main">
                <div className={`filmium-library-drive ${statusClass(root)}`}>
                  {root.last_scan_status === "offline"
                    ? <WifiOff size={21} />
                    : <HardDrive size={21} />}
                </div>
                <div className="filmium-library-identity">
                  <div>
                    <h3>{root.name}</h3>
                    <span
                      className={
                        `filmium-library-status ${statusClass(root)}`
                      }
                    >
                      {STATUS_LABELS[root.last_scan_status]}
                    </span>
                    <span className="filmium-library-kind">
                      {root.is_persistent ? "Trajna" : "Privremena"}
                    </span>
                    {root.is_main && (
                      <span className="filmium-library-main-badge">
                        Glavni disk
                      </span>
                    )}
                  </div>
                  <code>{root.path}</code>
                  {hasCapacity && (
                    <div className="filmium-library-capacity">
                      <div
                        aria-hidden="true"
                        className="filmium-library-capacity-bar"
                      >
                        <span style={{ width: `${usedPercent}%` }} />
                      </div>
                      <span className="filmium-library-capacity-label">
                        {formatBytes(usedBytes)} / {formatBytes(root.total_bytes!)}
                      </span>
                    </div>
                  )}
                  <div className="filmium-library-location-meta">
                    <span>
                      Poslednje skeniranje: {formatScanTime(root.last_scanned_at)}
                    </span>
                    {scanResult && (
                      <>
                        <span>{scanResult.discovered_count} pronađeno</span>
                        <span>{scanResult.importable_count} spremno</span>
                        {scanResult.problem_count > 0 && (
                          <span className="attention">
                            {scanResult.problem_count} za proveru
                          </span>
                        )}
                      </>
                    )}
                  </div>
                </div>
                <div className="filmium-library-actions">
                  <button
                    className="secondary-button"
                    disabled={isBusy || !root.is_enabled}
                    onClick={() => onScan(root.id)}
                    type="button"
                  >
                    {isBusy
                      ? <LoaderCircle className="spinning" size={16} />
                      : <RefreshCw size={16} />}
                    Skeniraj
                  </button>
                  <div className="filmium-library-menu-wrap">
                    <button
                      aria-expanded={menuOpen}
                      aria-label={`Opcije lokacije ${root.name}`}
                      className="filmium-library-icon-button"
                      onClick={() => {
                        setOpenMenuId(menuOpen ? null : root.id);
                      }}
                      type="button"
                    >
                      <EllipsisVertical size={18} />
                    </button>
                    {menuOpen && (
                      <div className="filmium-library-menu">
                        <button
                          onClick={() => {
                            setOpenMenuId(null);
                            onSetMain(root.id);
                          }}
                          type="button"
                        >
                          {root.is_main && <Check size={15} />}
                          {root.is_main
                            ? "Glavni disk"
                            : "Postavi kao glavni disk"}
                        </button>
                        <button
                          onClick={() => {
                            setOpenMenuId(null);
                            onSetPersistence(
                              root.id,
                              !root.is_persistent,
                            );
                          }}
                          type="button"
                        >
                          {root.is_persistent && <Check size={15} />}
                          {root.is_persistent
                            ? "Trajna lokacija"
                            : "Sačuvaj kao trajnu"}
                        </button>
                        <button
                          onClick={() => {
                            setOpenMenuId(null);
                            onScan(root.id);
                          }}
                          type="button"
                        >
                          <RefreshCw size={15} />
                          Ponovo skeniraj
                        </button>
                        <button
                          className="danger"
                          onClick={() => {
                            setOpenMenuId(null);
                            onRemove(root.id);
                          }}
                          type="button"
                        >
                          <Trash2 size={15} />
                          Ukloni zapis
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
