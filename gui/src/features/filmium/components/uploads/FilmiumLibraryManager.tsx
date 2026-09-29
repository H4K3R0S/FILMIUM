import { useEffect, useMemo, useState } from "react";
import {
  CheckCircle2,
  Download,
  LoaderCircle,
  ListChecks,
  X,
} from "lucide-react";
import { openPathDialog } from "../../../../lib/pathPicker";
import { useNavigate } from "react-router";

import { useFilmiumLibraries } from "../../hooks/useFilmiumLibraries";
import { useFilmiumSeriesImport } from "../../hooks/useFilmiumSeriesImport";
import {
  type ShareScanEntry,
} from "../../context/FilmiumWorkspace";
import { useFilmiumWorkspace } from "../../context/useFilmiumWorkspace";
import { confirmFilmiumLibraryImportStream } from "../../../../services/filmiumLibraryApi";
import { confirmFilmiumSeriesStream } from "../../../../services/filmiumSeriesApi";
import {
  sseOverallPercent,
  type SseProgress,
} from "../../../../services/httpClient";
import { type FilmiumContentMode } from "./ContentModeToggle";
import { notifyFilmiumCatalogChanged } from "../../events/filmiumCatalogEvents";
import FilmiumLibraryLocations from "./FilmiumLibraryLocations";
import FilmiumSeriesImport from "./FilmiumSeriesImport";
import FilmiumAutoImportPanel from "./FilmiumAutoImportPanel";
import FilmiumLibraryNotifications from "./FilmiumLibraryNotifications";
import FilmiumLibraryQuickActions from "./FilmiumLibraryQuickActions";
import FilmiumLibraryScanResults from "./FilmiumLibraryScanResults";
import FilmiumLibraryStatistics from "./FilmiumLibraryStatistics";
import { calculateLibraryStatistics } from "./libraryStatistics";
import type {
  FilmiumImportOverrides,
  FilmiumLibraryImportPreview,
} from "../../../../types/filmiumLibrary";
import "../../styles/filmium-library-picker.css";

type QueueItemStatus = "queued" | "downloading" | "done" | "error";

interface ImportQueueItem {
  id: string;
  rootId: number;
  relativeDirectory: string;
  title: string;
  mediaType: "movie" | "series";
  releaseYear: number | null;
  overrides: FilmiumImportOverrides;
  contentMode: FilmiumContentMode;
  synchronized: boolean;
  status: QueueItemStatus;
  errorMessage: string | null;
}

function queueKey(rootId: number, relativeDirectory: string): string {
  return `${rootId}:${relativeDirectory}`;
}

function queueStatusLabel(status: QueueItemStatus): string {
  switch (status) {
    case "downloading":
      return "Preuzimam";
    case "done":
      return "Zavrseno";
    case "error":
      return "Greska";
    default:
      return "Ceka";
  }
}


/**
 * Koordinira lokacije, skeniranje i uvoz na FILMIUM Uploads stranici.
 */
export default function FilmiumLibraryManager() {
  const navigate = useNavigate();
  const {
    addAndScanDirectory,
    busyImportKey,
    busyRootId,
    clearImportPreview,
    clearRootScanResult,
    confirmImport,
    dismissEntry,
    errorMessage,
    ignoreDirectory,
    fetchImportPreview,
    importPreviews,
    importResults,
    isCreating,
    isLoading,
    previewImport,
    refreshRoots,
    removeRoot,
    roots,
    scanResults,
    scanRoot,
    setMainLibrary,
    setRootPersistence,
  } = useFilmiumLibraries();
  const seriesImport = useFilmiumSeriesImport();
  const { setLastScan } = useFilmiumWorkspace();
  const [isChoosingDirectory, setIsChoosingDirectory] = useState(false);
  const [pickerErrorMessage, setPickerErrorMessage] =
    useState<string | null>(null);
  const [importQueue, setImportQueue] = useState<ImportQueueItem[]>([]);
  const [isQueueRunning, setIsQueueRunning] = useState(false);
  const [napredakStavke, setCurrentQueueProgress] = useState(0);
  // PREVODI: da li sken uključuje i titlove (default isključeno).
  const [scanSubtitles, setScanSubtitles] = useState(false);
  // SAMO NOVO: prikaži samo nove filmove/serije (default uključeno).
  const [onlyNew, setOnlyNew] = useState(true);
  const statistics = calculateLibraryStatistics(scanResults);
  const isChoosingOrCreating = isChoosingDirectory || isCreating;
  const activeQueueItem = importQueue.find(
    (item) => item.status === "downloading",
  ) ?? null;
  // Bez aktivne stavke napredak je nula — to se IZVODI pri crtanju. Upis iz
  // efekta značio bi da se jedan kadar vidi napredak stavke koje više nema.
  const activeQueueId = activeQueueItem?.id ?? null;
  const currentQueueProgress = activeQueueId === null ? 0 : napredakStavke;

  const completedQueueCount = importQueue.filter(
    (item) => item.status === "done",
  ).length;
  const queueTotalProgress = importQueue.length === 0
    ? 0
    : Math.round(
        ((completedQueueCount + currentQueueProgress / 100) /
          importQueue.length) *
          100,
      );

  // Deli poslednje skeniranje (filmovi + pronađene serije) sa „Podeli"
  // ekranom kao podrazumevanu listu za prenos.
  const seriesPreview = seriesImport.preview;
  useEffect(() => {
    const movieEntries: ShareScanEntry[] = Object.entries(scanResults)
      .flatMap(([rootId, result]) =>
        result.entries
          .filter((entry) => entry.can_import && entry.title)
          .map((entry) => ({
            id: `scan:movie:${rootId}:${entry.directory}`,
            title: entry.title as string,
            subtitle: `${entry.release_year ?? "—"} · Film`,
            mediaType: "movie" as const,
            directory: entry.directory,
          })),
      );

    const seriesEntries: ShareScanEntry[] = (
      seriesPreview?.series ?? []
    ).map((series) => ({
      id: `scan:series:${series.relative_directory}`,
      title: series.title,
      subtitle: "Serija",
      mediaType: "series" as const,
      directory: series.relative_directory,
    }));

    setLastScan([...movieEntries, ...seriesEntries]);
  }, [scanResults, seriesPreview, setLastScan]);

  /**
   * Otvara Windows birač foldera i vraća putanju (ili null).
   */
  async function pickDirectory(title: string): Promise<string | null> {
    const selectedPath = await openPathDialog({
      directory: true,
      multiple: false,
      title,
    });

    return typeof selectedPath === "string" ? selectedPath : null;
  }

  function directoryLabel(path: string): string {
    return (
      path.split(/[\\/]/).filter(Boolean).at(-1) ?? "FILMIUM lokacija"
    );
  }

  /**
   * „Dodaj film" — skenira izabrani folder samo u filmskom režimu.
   */
  async function scanMovieFolder(): Promise<void> {
    setIsChoosingDirectory(true);
    setPickerErrorMessage(null);

    try {
      const path = await pickDirectory("Izaberi folder sa filmovima");
      if (path === null) {
        return;
      }
      await addAndScanDirectory(
        path,
        directoryLabel(path),
        false,
        scanSubtitles,
        onlyNew,
      );
    } catch (error) {
      setPickerErrorMessage(
        error instanceof Error
          ? error.message
          : "Windows birač direktorijuma nije otvoren.",
      );
    } finally {
      setIsChoosingDirectory(false);
    }
  }

  /**
   * Skeniranje registrovane lokacije (iz liste diskova): prvo filmski,
   * pa serijski ako filmovi nisu pronađeni — kao „Skeniraj folder".
   */
  async function scanRootBoth(rootId: number): Promise<void> {
    const result = await scanRoot(rootId, scanSubtitles, onlyNew);

    if (result && result.importable_count > 0) {
      return;
    }

    const foundSeries = await seriesImport.scanExistingRoot(rootId);
    if (foundSeries) {
      clearRootScanResult(rootId);
    }
    await refreshRoots();
  }

  /**
   * „Skeniraj sve" — kombinovano (film pa serija) za svaku uključenu
   * registrovanu lokaciju.
   */
  async function scanAllRootsBoth(): Promise<void> {
    for (const root of roots) {
      if (root.is_enabled) {
        await scanRootBoth(root.id);
      }
    }
  }

  /**
   * „Skeniraj folder" — prvo filmski režim; ako filmovi nisu pronađeni,
   * automatski prelazi na serijsko skeniranje istog foldera.
   */
  async function scanFolderBoth(): Promise<void> {
    setIsChoosingDirectory(true);
    setPickerErrorMessage(null);

    try {
      const path = await pickDirectory(
        "Izaberi folder za skeniranje (filmovi pa serije)",
      );
      if (path === null) {
        return;
      }

      const outcome = await addAndScanDirectory(
        path,
        directoryLabel(path),
        false,
        scanSubtitles,
        onlyNew,
      );

      // Filmovi pronađeni → prikaži filmske rezultate.
      if (outcome && outcome.result.importable_count > 0) {
        return;
      }

      // Nema filmova → probaj serijsko skeniranje istog foldera.
      if (outcome) {
        const foundSeries = await seriesImport.scanExistingRoot(
          outcome.rootId,
        );
        if (foundSeries) {
          clearRootScanResult(outcome.rootId);
        }
        await refreshRoots();
      }
    } catch (error) {
      setPickerErrorMessage(
        error instanceof Error
          ? error.message
          : "Windows birač direktorijuma nije otvoren.",
      );
    } finally {
      setIsChoosingDirectory(false);
    }
  }

  function addImportToQueue(
    rootId: number,
    relativeDirectory: string,
    preview: FilmiumLibraryImportPreview,
    overrides: FilmiumImportOverrides,
    contentMode: FilmiumContentMode = "regular",
    synchronized: boolean = false,
  ): void {
    const id = queueKey(rootId, relativeDirectory);

    setImportQueue((current) => {
      const exists = current.some((item) => item.id === id);

      if (exists) {
        return current.map((item) =>
          item.id === id
            ? {
                ...item,
                overrides,
                contentMode,
                synchronized,
                status: item.status === "done" ? "queued" : item.status,
                errorMessage: null,
              }
            : item,
        );
      }

      return [
        ...current,
        {
          id,
          rootId,
          relativeDirectory,
          title: preview.title,
          mediaType: preview.media_type,
          releaseYear: preview.release_year,
          overrides,
          contentMode,
          synchronized,
          status: "queued",
          errorMessage: null,
        },
      ];
    });
  }

  function addSeriesToQueue(
    rootId: number,
    relativeDirectory: string,
    title: string,
    releaseYear: number | null,
    targetLibraryRootId: number | null,
    contentMode: FilmiumContentMode = "regular",
    synchronized: boolean = false,
  ): void {
    const id = queueKey(rootId, relativeDirectory);
    const overrides: FilmiumImportOverrides =
      targetLibraryRootId != null
        ? { target_library_root_id: targetLibraryRootId }
        : {};

    setImportQueue((current) => {
      const exists = current.some((item) => item.id === id);

      if (exists) {
        return current.map((item) =>
          item.id === id
            ? {
                ...item,
                overrides,
                contentMode,
                synchronized,
                status: item.status === "done" ? "queued" : item.status,
                errorMessage: null,
              }
            : item,
        );
      }

      return [
        ...current,
        {
          id,
          rootId,
          relativeDirectory,
          title,
          mediaType: "series",
          releaseYear,
          overrides,
          contentMode,
          synchronized,
          status: "queued",
          errorMessage: null,
        },
      ];
    });
  }

  function removeImportFromQueue(id: string): void {
    if (isQueueRunning) {
      return;
    }

    setImportQueue((current) =>
      current.filter((item) => item.id !== id),
    );
  }

  async function downloadQueuedImports(): Promise<void> {
    if (isQueueRunning || importQueue.length === 0) {
      return;
    }

    setIsQueueRunning(true);

    try {
      const pendingItems = importQueue.filter(
        (item) => item.status === "queued" || item.status === "error",
      );

      for (const item of pendingItems) {
        setImportQueue((current) =>
          current.map((queueItem) =>
            queueItem.id === item.id
              ? {
                  ...queueItem,
                  status: "downloading",
                  errorMessage: null,
                }
              : queueItem,
          ),
        );
        setCurrentQueueProgress(0);

        // Stvarni progres: SSE događaji iz backenda (ceo prenos stavke).
        const handleProgress = (progress: SseProgress): void => {
          setCurrentQueueProgress(sseOverallPercent(progress));
        };

        let succeeded = false;
        let failureMessage: string | null = null;

        try {
          if (item.mediaType === "series") {
            await confirmFilmiumSeriesStream(
              item.rootId,
              item.relativeDirectory,
              item.overrides.target_library_root_id ?? null,
              handleProgress,
              item.contentMode,
              item.synchronized,
            );
          } else {
            await confirmFilmiumLibraryImportStream(
              item.rootId,
              {
                relative_directory: item.relativeDirectory,
                confirmed: true,
                target_media_id: null,
                ...(item.overrides.title !== undefined
                  ? { title: item.overrides.title }
                  : {}),
                ...(item.overrides.release_year !== undefined
                  ? { release_year: item.overrides.release_year }
                  : {}),
                ...(item.overrides.genres !== undefined
                  ? { genres: item.overrides.genres }
                  : {}),
                ...(item.overrides.target_library_root_id != null
                  ? {
                      target_library_root_id:
                        item.overrides.target_library_root_id,
                    }
                  : {}),
                content_mode: item.contentMode,
                synchronized: item.synchronized,
              },
              handleProgress,
            );
          }
          succeeded = true;
        } catch (error) {
          failureMessage =
            error instanceof Error
              ? error.message
              : "Uvoz nije uspeo.";
        }

        setCurrentQueueProgress(100);
        setImportQueue((current) =>
          current.map((queueItem) =>
            queueItem.id === item.id
              ? {
                  ...queueItem,
                  status: succeeded ? "done" : "error",
                  errorMessage: succeeded ? null : failureMessage,
                }
              : queueItem,
          ),
        );

        // Uspešno preneta stavka pokaže zeleni status pa se posle 3s
        // sama ukloni iz liste za preuzimanje.
        if (succeeded) {
          const doneId = item.id;
          window.setTimeout(() => {
            setImportQueue((current) =>
              current.filter((queueItem) => queueItem.id !== doneId),
            );
          }, 3000);
        }
      }

      notifyFilmiumCatalogChanged();
      await refreshRoots();
    } finally {
      setIsQueueRunning(false);
      setCurrentQueueProgress(0);
    }
  }

  return (
    <div className="filmium-library-dashboard">
      <main className="filmium-library-dashboard-main">
        <FilmiumLibraryQuickActions
          isBusy={isChoosingOrCreating || seriesImport.isBusy}
          onScanBoth={() => void scanFolderBoth()}
          onScanMovies={() => void scanMovieFolder()}
          onScanSeries={() => {
            void seriesImport
              .chooseFolder()
              .then(() => refreshRoots());
          }}
          onShare={() => navigate("/filmium/share")}
        />

        {errorMessage && (
          <div className="system-message error">{errorMessage}</div>
        )}
        {pickerErrorMessage && (
          <div className="system-message error">{pickerErrorMessage}</div>
        )}

        <FilmiumLibraryLocations
          busyRootId={busyRootId}
          isLoading={isLoading}
          onRemove={(rootId) => void removeRoot(rootId)}
          onlyNew={onlyNew}
          onScan={(rootId) => void scanRootBoth(rootId)}
          onScanAll={() => void scanAllRootsBoth()}
          onSetMain={(rootId) => void setMainLibrary(rootId)}
          onSetPersistence={(rootId, isPersistent) => {
            void setRootPersistence(rootId, isPersistent);
          }}
          onToggleOnlyNew={() => setOnlyNew((value) => !value)}
          onToggleScanSubtitles={() =>
            setScanSubtitles((value) => !value)}
          roots={roots}
          scanResults={scanResults}
          scanSubtitles={scanSubtitles}
        />

        <FilmiumLibraryStatistics statistics={statistics} />

        {Object.entries(scanResults).map(([rootId, result]) => (
          <section
            className="filmium-library-scan-group"
            key={rootId}
          >
            <FilmiumLibraryScanResults
              busyImportKey={busyImportKey}
              importPreviews={importPreviews}
              importResults={importResults}
              libraries={roots}
              onClear={() => clearRootScanResult(Number(rootId))}
              onClosePreview={clearImportPreview}
              onConfirmImport={confirmImport}
              onFetchPreview={fetchImportPreview}
              onIgnore={dismissEntry}
              onNeverDetect={ignoreDirectory}
              onlyNew={onlyNew}
              onPreviewImport={previewImport}
              onQueueImport={addImportToQueue}
              result={result}
              rootId={Number(rootId)}
            />
          </section>
        ))}

        <FilmiumSeriesImport
          libraries={roots}
          onQueue={addSeriesToQueue}
          state={seriesImport}
        />
      </main>

      <aside className="filmium-library-sidebar">
        <FilmiumLibraryNotifications
          onRefresh={() => void refreshRoots()}
          roots={roots}
          statistics={statistics}
        />
        <FilmiumImportQueuePanel
          activeItem={activeQueueItem}
          currentProgress={currentQueueProgress}
          isRunning={isQueueRunning}
          items={importQueue}
          onRemove={removeImportFromQueue}
          onStart={() => void downloadQueuedImports()}
          totalProgress={queueTotalProgress}
        />
        <FilmiumAutoImportPanel />
      </aside>
    </div>
  );
}

interface FilmiumImportQueuePanelProps {
  activeItem: ImportQueueItem | null;
  currentProgress: number;
  isRunning: boolean;
  items: ImportQueueItem[];
  onRemove: (id: string) => void;
  onStart: () => void;
  totalProgress: number;
}

function FilmiumImportQueuePanel({
  activeItem,
  currentProgress,
  isRunning,
  items,
  onRemove,
  onStart,
  totalProgress,
}: FilmiumImportQueuePanelProps) {
  const pendingCount = useMemo(
    () =>
      items.filter(
        (item) => item.status === "queued" || item.status === "error",
      ).length,
    [items],
  );

  return (
    <section className="filmium-import-queue-panel">
      <div className="filmium-library-aside-heading">
        <h3>Lista za preuzimanje</h3>
        <span className="filmium-import-queue-count">
          {items.length}
        </span>
      </div>

      {items.length === 0 ? (
        <p className="filmium-library-aside-empty">
          Stavke koje dodaš u listu pojaviće se ovde.
        </p>
      ) : (
        <>
          <div className="filmium-import-queue-progress">
            <div>
              <span>Trenutno</span>
              <strong>
                {activeItem?.title ?? "Nista se ne preuzima"}
              </strong>
            </div>
            <ProgressLine value={currentProgress} />
          </div>

          <div className="filmium-import-queue-progress">
            <div>
              <span>Ceo queue</span>
              <strong>{totalProgress}%</strong>
            </div>
            <ProgressLine value={totalProgress} />
          </div>

          <div className="filmium-import-queue-list">
            {items.map((item) => (
              <article
                className={`filmium-import-queue-item status-${item.status}`}
                key={item.id}
              >
                <span className="filmium-import-queue-icon">
                  {item.status === "downloading" ? (
                    <LoaderCircle className="spinning" size={15} />
                  ) : item.status === "done" ? (
                    <CheckCircle2 size={15} />
                  ) : (
                    <ListChecks size={15} />
                  )}
                </span>
                <div>
                  <strong>
                    {item.title}
                    {item.releaseYear ? ` (${item.releaseYear})` : ""}
                  </strong>
                  <small>
                    {item.mediaType === "movie" ? "Film" : "Serija"} ·{" "}
                    {queueStatusLabel(item.status)}
                  </small>
                  {item.errorMessage && <em>{item.errorMessage}</em>}
                </div>
                <button
                  aria-label={`Ukloni ${item.title} iz queue-a`}
                  disabled={isRunning}
                  onClick={() => onRemove(item.id)}
                  type="button"
                >
                  <X size={14} />
                </button>
              </article>
            ))}
          </div>

          <button
            className="primary-button filmium-import-queue-start"
            disabled={isRunning || pendingCount === 0}
            onClick={onStart}
            type="button"
          >
            {isRunning ? (
              <LoaderCircle className="spinning" size={17} />
            ) : (
              <Download size={17} />
            )}
            Preuzmi sve
          </button>
        </>
      )}
    </section>
  );
}

function ProgressLine({ value }: { value: number }) {
  const boundedValue = Math.max(0, Math.min(100, value));

  return (
    <div
      aria-valuemax={100}
      aria-valuemin={0}
      aria-valuenow={boundedValue}
      className="filmium-import-queue-track"
      role="progressbar"
    >
      <span style={{ width: `${boundedValue}%` }} />
    </div>
  );
}
