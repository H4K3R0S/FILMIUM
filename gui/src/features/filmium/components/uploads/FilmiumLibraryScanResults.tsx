import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  File,
  Languages,
  LoaderCircle,
  X,
} from "lucide-react";
import { useState } from "react";

import {
  destroyFilmiumScannedDirectory,
  getFilmiumLibraryArtworkUrl,
} from "../../../../services/filmiumLibraryApi";
import type { SseProgress } from "../../../../services/httpClient";
import type {
  FilmiumBulkImportSettings,
  FilmiumImportOverrides,
  FilmiumLibraryFolderScan,
  FilmiumLibraryImportCommitResult,
  FilmiumLibraryImportPreview as ImportPreview,
  FilmiumLibraryRoot,
  FilmiumLibraryScanResult,
} from "../../../../types/filmiumLibrary";
import FilmiumLibraryImportPreview from "./FilmiumLibraryImportPreview";
import { type FilmiumContentMode } from "./ContentModeToggle";
import "../../styles/filmium-library-scan-results.css";


interface FilmiumLibraryScanResultsProps {
  busyImportKey: string | null;
  importPreviews: Record<string, ImportPreview>;
  importResults: Record<string, FilmiumLibraryImportCommitResult>;
  onClosePreview: (
    rootId: number,
    relativeDirectory: string,
  ) => void;
  onConfirmImport: (
    rootId: number,
    relativeDirectory: string,
    targetMediaId?: number | null,
    overrides?: FilmiumImportOverrides | null,
    onProgress?: (progress: SseProgress) => void,
    conflictMode?: "fail" | "skip" | "overwrite",
    contentMode?: FilmiumContentMode,
    synchronized?: boolean,
  ) => Promise<FilmiumLibraryImportCommitResult | null>;
  onIgnore: (
    rootId: number,
    relativeDirectory: string,
  ) => void;
  onNeverDetect: (
    rootId: number,
    relativeDirectory: string,
  ) => Promise<void>;
  onPreviewImport: (
    rootId: number,
    relativeDirectory: string,
  ) => Promise<boolean>;
  onFetchPreview: (
    rootId: number,
    relativeDirectory: string,
    includeTmdb?: boolean,
  ) => Promise<ImportPreview | null>;
  onQueueImport: (
    rootId: number,
    relativeDirectory: string,
    preview: ImportPreview,
    overrides: FilmiumImportOverrides,
    contentMode?: FilmiumContentMode,
    synchronized?: boolean,
  ) => void;
  onClear?: () => void;
  onlyNew?: boolean;
  libraries: FilmiumLibraryRoot[];
  result: FilmiumLibraryScanResult;
  rootId: number;
}

type DiscoveryFilter = "all" | "new" | "review" | "library";


function importKey(
  rootId: number,
  relativeDirectory: string,
): string {
  return `${rootId}:${relativeDirectory}`;
}

function catalogStatusLabel(
  entry: FilmiumLibraryFolderScan,
): string {
  switch (entry.catalog_status) {
    case "available":
      return "U biblioteci i dostupno";
    case "unavailable":
      return "U biblioteci, izvor nije dostupan";
    case "catalog_only":
      return "Već postoji u katalogu";
    case "ambiguous":
      return "Mogući duplikat — potrebna provera";
    default:
      return entry.can_import
        ? "Novo otkriveno — spremno za pregled"
        : entry.error_message ??
            entry.warnings[0] ??
            "Potrebna ručna provera";
  }
}

function discoveryFilter(
  entry: FilmiumLibraryFolderScan,
): Exclude<DiscoveryFilter, "all"> {
  if (
    entry.catalog_status === "available" ||
    entry.catalog_status === "unavailable" ||
    entry.catalog_status === "catalog_only"
  ) {
    return "library";
  }

  if (
    !entry.can_import ||
    entry.catalog_status === "ambiguous"
  ) {
    return "review";
  }

  return "new";
}

type DiscoveryBadge = {
  label: string;
  tone: "available" | "offline" | "missing" | "review" | "new";
};

/**
 * Vraća prominentnu oznaku stanja (desni badge) po statusu kataloga.
 */
function discoveryBadge(
  entry: FilmiumLibraryFolderScan,
): DiscoveryBadge {
  switch (entry.catalog_status) {
    case "available":
      return { label: "Dostupan", tone: "available" };
    case "unavailable":
      return { label: "Offline", tone: "offline" };
    case "catalog_only":
      return { label: "Bez video-fajla", tone: "missing" };
    case "ambiguous":
      return { label: "Proveri", tone: "review" };
    default:
      return entry.can_import
        ? { label: "Novo", tone: "new" }
        : { label: "Proveri", tone: "review" };
  }
}

// Redosled prikaza: novo na vrhu, pa stavke za proveru, pa biblioteka.
const DISCOVERY_RANK: Record<DiscoveryBadge["tone"], number> = {
  new: 0,
  review: 1,
  available: 2,
  offline: 3,
  missing: 4,
};

/**
 * Vraća rang stavke za sortiranje (manje = više gore).
 */
function entryRank(entry: FilmiumLibraryFolderScan): number {
  return DISCOVERY_RANK[discoveryBadge(entry).tone];
}


export default function FilmiumLibraryScanResults({
  busyImportKey,
  importPreviews,
  importResults,
  libraries,
  onClosePreview,
  onConfirmImport,
  onFetchPreview,
  onIgnore,
  onNeverDetect,
  onPreviewImport,
  onQueueImport,
  onClear,
  onlyNew = false,
  result,
  rootId,
}: FilmiumLibraryScanResultsProps) {
  const [expandedDirectory, setExpandedDirectory] =
    useState<string | null>(null);
  const [activeFilter, setActiveFilter] =
    useState<DiscoveryFilter>("all");
  const [destroyMessage, setDestroyMessage] =
    useState<string | null>(null);
  // Bulk izbor (Selektuj sve / Prebaci sve).
  const [selectedDirectories, setSelectedDirectories] =
    useState<Set<string>>(new Set());
  const [bulkBusy, setBulkBusy] = useState(false);
  const [bulkProgress, setBulkProgress] =
    useState<{ done: number; total: number } | null>(null);

  /**
   * Direktorijumi svih vidljivih stavki istog statusa (npr. „Novo")
   * koje su spremne za uvoz i još nisu unete u biblioteku.
   */
  function sameStatusDirectories(
    entry: FilmiumLibraryFolderScan,
  ): string[] {
    const tone = discoveryBadge(entry).tone;

    return visibleEntries
      .filter(
        (candidate) =>
          candidate.can_import &&
          !importResults[importKey(rootId, candidate.directory)] &&
          discoveryBadge(candidate).tone === tone,
      )
      .map((candidate) => candidate.directory);
  }

  function handleSelectAllSameStatus(
    entry: FilmiumLibraryFolderScan,
  ): void {
    setSelectedDirectories(new Set(sameStatusDirectories(entry)));
  }

  /**
   * Učitava TMDB-obogaćen preview za sve izabrane i šalje ih u red uvoza,
   * prenoseći podešavanja (FILM/ANIME/DOMAĆE, TITL/SINH, ciljna biblioteka)
   * sa prve stavke na sve. Progres se prati po stavci.
   */
  async function handleTransferAll(
    settings: FilmiumBulkImportSettings,
  ): Promise<void> {
    const directories = [...selectedDirectories];

    if (directories.length === 0 || bulkBusy) {
      return;
    }

    setBulkBusy(true);
    setBulkProgress({ done: 0, total: directories.length });

    try {
      for (let index = 0; index < directories.length; index += 1) {
        const directory = directories[index];
        const key = importKey(rootId, directory);
        let preview: ImportPreview | null = importPreviews[key] ?? null;

        // Dopuni TMDB-om ako preview nije učitan ili nema TMDB blok.
        if (!preview || !preview.tmdb) {
          preview =
            (await onFetchPreview(rootId, directory, true)) ?? preview;
        }

        if (preview && preview.can_confirm) {
          onQueueImport(
            rootId,
            directory,
            preview,
            { target_library_root_id: settings.targetRootId },
            settings.contentMode,
            settings.synchronized,
          );
        }

        setBulkProgress({ done: index + 1, total: directories.length });
      }

      setSelectedDirectories(new Set());
    } finally {
      setBulkBusy(false);
      window.setTimeout(() => setBulkProgress(null), 1500);
    }
  }

  async function handleDestroy(
    entry: FilmiumLibraryFolderScan,
  ): Promise<void> {
    const label = entry.title ?? entry.directory;
    const confirmed = window.confirm(
      `Trajno obrisati folder „${label}" sa diska? Ova radnja se ne`
      + " može opozvati.",
    );
    if (!confirmed) {
      return;
    }

    try {
      await destroyFilmiumScannedDirectory(rootId, entry.directory);
      setExpandedDirectory(null);
      onIgnore(rootId, entry.directory);
      setDestroyMessage(`Folder „${label}" je uništen i uklonjen sa liste.`);
    } catch (error) {
      setDestroyMessage(
        error instanceof Error
          ? `Uništenje nije uspelo: ${error.message}`
          : "Uništenje nije uspelo.",
      );
    }
  }
  // SAMO NOVO toggle: forsira prikaz samo novih stavki i sakriva filter.
  const effectiveFilter: DiscoveryFilter = onlyNew ? "new" : activeFilter;
  const visibleEntries = result.entries
    .filter(
      (entry) =>
        effectiveFilter === "all" ||
        discoveryFilter(entry) === effectiveFilter,
    )
    .sort((first, second) => entryRank(first) - entryRank(second));

  async function toggleEntry(
    entry: FilmiumLibraryFolderScan,
  ): Promise<void> {
    if (expandedDirectory === entry.directory) {
      setExpandedDirectory(null);
      return;
    }

    setExpandedDirectory(entry.directory);
    const key = importKey(rootId, entry.directory);

    if (
      entry.can_import &&
      !importPreviews[key] &&
      !importResults[key]
    ) {
      await onPreviewImport(rootId, entry.directory);
    }
  }

  return (
    <div className="filmium-library-scan-result">
      <div className="filmium-library-scan-head">
        <div className="filmium-library-scan-stats">
          <span>
            <File size={15} /> {result.discovered_count} pronađeno
          </span>
          <span>
            <CheckCircle2 size={15} /> {result.importable_count} spremno
          </span>
          <span>
            <AlertTriangle size={15} /> {result.problem_count} problema
          </span>
          {result.discovered_subtitle_count > 0 && (
            <span>
              <Languages size={15} /> {result.discovered_subtitle_count} prevoda
            </span>
          )}
        </div>
        {onClear && (
          <button
            aria-label="Obriši rezultate skeniranja filmova"
            className="filmium-library-icon-button"
            onClick={onClear}
            type="button"
          >
            <X size={18} />
          </button>
        )}
      </div>

      {destroyMessage && (
        <p
          className="filmium-library-warning filmium-import-destroy-message"
          role="status"
        >
          {destroyMessage}
        </p>
      )}

      {[...result.warnings, ...result.subtitle_scan_warnings].map(
        (warning) => (
          <p className="filmium-library-warning" key={warning}>
            {warning}
          </p>
        ),
      )}

      {result.entries.length > 0 && (
        <>
          <div className="filmium-discovery-toolbar">
            <div>
              <p className="eyebrow">Rezultati poslednjeg skeniranja</p>
              <strong>{result.entries.length} video zapisa</strong>
            </div>
            {!onlyNew && (
              <div
                aria-label="Filter otkrivenog sadržaja"
                className="filmium-discovery-filters"
                role="group"
              >
                {([
                  ["all", "Sve"],
                  ["new", "Novo"],
                  ["review", "Potrebna provera"],
                  ["library", "U biblioteci"],
                ] as const).map(([value, label]) => (
                  <button
                    aria-pressed={activeFilter === value}
                    className={activeFilter === value ? "active" : ""}
                    key={value}
                    onClick={() => setActiveFilter(value)}
                    type="button"
                  >
                    {label}
                  </button>
                ))}
              </div>
            )}
          </div>

          {(bulkProgress || selectedDirectories.size > 0) && (
            <div className="filmium-bulk-banner" role="status">
              {bulkProgress ? (
                <>
                  <LoaderCircle
                    className={bulkBusy ? "spinning" : ""}
                    size={16}
                  />
                  <span>
                    Prebacujem u listu: {bulkProgress.done}/
                    {bulkProgress.total}
                  </span>
                </>
              ) : (
                <>
                  <span>{selectedDirectories.size} izabrano</span>
                  <button
                    className="filmium-bulk-banner-clear"
                    onClick={() => setSelectedDirectories(new Set())}
                    type="button"
                  >
                    Poništi izbor
                  </button>
                </>
              )}
            </div>
          )}

          <div className="filmium-library-discovery-list">
          {visibleEntries.map((entry) => {
            const key = importKey(rootId, entry.directory);
            const isExpanded = expandedDirectory === entry.directory;
            const isBusy = busyImportKey === key;
            const preview = importPreviews[key];
            const imported = importResults[key];
            const badge = discoveryBadge(entry);
            const isSelected = selectedDirectories.has(entry.directory);

            return (
              <article
                className={[
                  "filmium-library-discovery",
                  entry.can_import ? "ready" : "problem",
                  entry.catalog_status &&
                    entry.catalog_status !== "new"
                    ? `catalog-${entry.catalog_status}`
                    : "",
                  isExpanded ? "expanded" : "",
                  imported ? "imported" : "",
                  isSelected ? "selected" : "",
                ].filter(Boolean).join(" ")}
                key={entry.directory}
              >
                <button
                  aria-expanded={isExpanded}
                  className="filmium-library-discovery-summary"
                  onClick={() => void toggleEntry(entry)}
                  type="button"
                >
                  <FilmiumCardArtwork
                    directory={entry.directory}
                    rootId={rootId}
                    title={entry.title ?? entry.directory}
                  />
                  <span className="filmium-discovery-card-copy">
                    <strong>
                      {entry.title ?? entry.directory}
                      {entry.release_year
                        ? ` (${entry.release_year})`
                        : ""}
                    </strong>
                    <small>
                      {catalogStatusLabel(entry)}
                    </small>
                  </span>
                  <span className="filmium-discovery-card-footer">
                    <span className="filmium-discovery-card-year">
                      {entry.release_year ?? "Godina?"}
                    </span>
                    <span
                      className={`filmium-discovery-badge tone-${
                        imported ? "available" : badge.tone
                      }`}
                    >
                      <span className="filmium-discovery-badge-dot" />
                      {imported ? "U biblioteci" : badge.label}
                    </span>
                    {isBusy
                      ? <LoaderCircle className="spinning" size={18} />
                      : isExpanded
                        ? <ChevronUp size={18} />
                        : <ChevronDown size={18} />}
                  </span>
                </button>

                {isExpanded && (
                  <div className="filmium-library-discovery-details">
                    {entry.warnings.map((warning) => (
                      <p
                        className="filmium-import-entry-warning"
                        key={warning}
                      >
                        <AlertTriangle size={15} />
                        {warning}
                      </p>
                    ))}

                    {imported && (
                      <div className="filmium-import-success">
                        <CheckCircle2 size={19} />
                        <div>
                          <strong>{imported.title} je dodat u FILMIUM.</strong>
                          <span>
                            Premešteno fajlova: {imported.moved_file_count}
                          </span>
                        </div>
                      </div>
                    )}

                    {!entry.can_import && !imported && (
                      <div className="filmium-import-blocked">
                        Ovaj folder trenutno nije moguće uvesti. Proveri
                        upozorenja i naziv foldera, pa ponovo pokreni
                        skeniranje.
                      </div>
                    )}

                    {entry.can_import && isBusy && !preview && (
                      <div className="filmium-import-loading">
                        <LoaderCircle className="spinning" size={18} />
                        Analiziram fajlove i pripremam plan uvoza...
                      </div>
                    )}

                    {preview && (
                      <FilmiumLibraryImportPreview
                        busy={isBusy}
                        bulkBusy={bulkBusy}
                        selectedCount={selectedDirectories.size}
                        onSelectAllSameStatus={() =>
                          handleSelectAllSameStatus(entry)}
                        onTransferAll={(settings) =>
                          void handleTransferAll(settings)}
                        onClearSelection={() =>
                          setSelectedDirectories(new Set())}
                        entry={entry}
                        libraries={libraries}
                        onClose={() => {
                          onClosePreview(rootId, entry.directory);
                          setExpandedDirectory(null);
                        }}
                        onConfirm={(
                          overrides,
                          onProgress,
                          conflictMode,
                          contentMode,
                          synchronized,
                        ) =>
                          void onConfirmImport(
                            rootId,
                            entry.directory,
                            undefined,
                            overrides,
                            onProgress,
                            conflictMode,
                            contentMode,
                            synchronized,
                          )}
                        onQueue={(overrides, contentMode, synchronized) =>
                          onQueueImport(
                            rootId,
                            entry.directory,
                            preview,
                            overrides,
                            contentMode,
                            synchronized,
                          )}
                        onIgnore={() =>
                          onIgnore(rootId, entry.directory)}
                        onNeverDetect={() =>
                          void onNeverDetect(rootId, entry.directory)}
                        onDestroy={() => void handleDestroy(entry)}
                        preview={preview}
                      />
                    )}
                  </div>
                )}
              </article>
            );
          })}
          </div>

          {visibleEntries.length === 0 && (
            <div className="filmium-discovery-filter-empty">
              Nema pronađenih sadržaja u ovom filteru.
            </div>
          )}
        </>
      )}
    </div>
  );
}

interface FilmiumCardArtworkProps {
  directory: string;
  rootId: number;
  title: string;
}


function FilmiumCardArtwork({
  directory,
  rootId,
  title,
}: FilmiumCardArtworkProps) {
  const [imageUnavailable, setImageUnavailable] = useState(false);
  const initials = title
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");

  return (
    <span className="filmium-discovery-card-art">
      {!imageUnavailable && (
        <img
          alt=""
          loading="lazy"
          onError={() => setImageUnavailable(true)}
          src={getFilmiumLibraryArtworkUrl(rootId, directory)}
        />
      )}
      {imageUnavailable && (
        <span aria-hidden="true" className="filmium-discovery-monogram">
          {initials || "F"}
        </span>
      )}
    </span>
  );
}
