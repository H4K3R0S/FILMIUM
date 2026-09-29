import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  File,
  FileImage,
  Film,
  FolderInput,
  Languages,
  LoaderCircle,
  ListChecks,
  ListPlus,
  X,
} from "lucide-react";
import { useState } from "react";

import { getFilmiumLibraryArtworkUrl } from "../../../../services/filmiumLibraryApi";
import {
  sseFilePercent,
  sseOverallPercent,
  type SseProgress,
} from "../../../../services/httpClient";
import {
  pickAndReplaceArtwork,
  pickAndReplaceSubtitle,
} from "../../utils/replaceArtwork";
import ContentModeToggle, {
  type FilmiumContentMode,
} from "./ContentModeToggle";
import type {
  FilmiumBulkImportSettings,
  FilmiumImportOverrides,
  FilmiumImportPreviewFile,
  FilmiumImportTechnicalInfo,
  FilmiumLibraryFolderScan,
  FilmiumLibraryImportPreview as ImportPreview,
  FilmiumLibraryRoot,
} from "../../../../types/filmiumLibrary";


interface FilmiumLibraryImportPreviewProps {
  busy: boolean;
  bulkBusy: boolean;
  selectedCount: number;
  onSelectAllSameStatus: () => void;
  onTransferAll: (settings: FilmiumBulkImportSettings) => void;
  onClearSelection: () => void;
  entry: FilmiumLibraryFolderScan;
  libraries: FilmiumLibraryRoot[];
  onClose: () => void;
  onConfirm: (
    overrides: FilmiumImportOverrides,
    onProgress?: (progress: SseProgress) => void,
    conflictMode?: "fail" | "skip" | "overwrite",
    contentMode?: FilmiumContentMode,
    synchronized?: boolean,
  ) => void;
  onQueue: (
    overrides: FilmiumImportOverrides,
    contentMode?: FilmiumContentMode,
    synchronized?: boolean,
  ) => void;
  onIgnore: () => void;
  onNeverDetect: () => void;
  onDestroy?: () => void;
  preview: ImportPreview;
}


// ==========          FORMATIRANJE          ==========

function formatBytes(sizeBytes: number): string {
  if (sizeBytes < 1024) {
    return `${sizeBytes} B`;
  }

  const units = ["KB", "MB", "GB", "TB"];
  let value = sizeBytes / 1024;
  let unitIndex = 0;

  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }

  return `${value.toFixed(value >= 10 ? 1 : 2)} ${units[unitIndex]}`;
}


/**
 * Vraća ekstenziju (kontejner) fajla velikim slovima, npr. "MKV".
 */
function fileContainer(path: string): string | null {
  const extension = path.split(".").pop();

  if (!extension || extension.length > 5) {
    return null;
  }

  return extension.toUpperCase();
}


/**
 * Izvlači približne tehničke tagove iz imena video fajla.
 *
 * Ovo je privremena heuristika dok se ne uključi prava media-probe
 * (ffprobe) koja daje tačnu rezoluciju, kodek i broj sličica.
 */
function parseVideoTags(path: string): string[] {
  const tags: string[] = [];
  const upper = path.toUpperCase();

  if (/2160P|\b4K\b|UHD/.test(upper)) {
    tags.push("2160p");
  } else if (/1080P/.test(upper)) {
    tags.push("1080p");
  } else if (/720P/.test(upper)) {
    tags.push("720p");
  } else if (/480P/.test(upper)) {
    tags.push("480p");
  }

  if (/X265|H\.?265|HEVC/.test(upper)) {
    tags.push("HEVC");
  } else if (/X264|H\.?264|AVC/.test(upper)) {
    tags.push("H.264");
  }

  if (/DTS[-.]?HD/.test(upper)) {
    tags.push("DTS-HD");
  } else if (/DTS/.test(upper)) {
    tags.push("DTS");
  } else if (/AAC/.test(upper)) {
    tags.push("AAC");
  } else if (/AC3|DD5|EAC3|DDP/.test(upper)) {
    tags.push("AC3");
  }

  return tags;
}


/**
 * Pretvara broj audio kanala u uobičajenu oznaku rasporeda (npr. "5.1").
 */
function channelLayout(channels: number | null): string | null {
  if (!channels || channels <= 0) {
    return null;
  }

  const layouts: Record<number, string> = {
    1: "Mono",
    2: "2.0",
    6: "5.1",
    8: "7.1",
  };

  return layouts[channels] ?? `${channels}.0`;
}


/**
 * Gradi čitljive čipove iz stvarnih ffprobe tehničkih podataka.
 */
function technicalChips(
  technical: FilmiumImportTechnicalInfo,
): string[] {
  const chips: string[] = [];

  if (technical.width && technical.height) {
    chips.push(`${technical.width}×${technical.height}`);
  }

  if (technical.video_codec) {
    chips.push(technical.video_codec);
  }

  if (technical.audio_codec) {
    const layout = channelLayout(technical.audio_channels);
    chips.push(
      layout ? `${technical.audio_codec} ${layout}` : technical.audio_codec,
    );
  }

  if (technical.frame_rate) {
    chips.push(`${technical.frame_rate} FPS`);
  }

  return chips;
}


// ==========          UMETNIČKA DELA          ==========

const ART_SLOTS: { label: string; role: string }[] = [
  { label: "Poster", role: "poster" },
  { label: "Backdrop", role: "backdrop" },
  { label: "Wallpaper", role: "wallpaper" },
  { label: "Fanart", role: "fanart" },
];


/**
 * Naziv biblioteke u padajućem meniju: ime, putanja i slobodan prostor.
 */
function libraryOptionLabel(library: FilmiumLibraryRoot): string {
  const free =
    typeof library.free_bytes === "number"
      ? ` — ${formatBytes(library.free_bytes)} slobodno`
      : "";

  return `${library.name} (${library.path})${free}`;
}


// ==========          STABLO ORGANIZACIJE          ==========

interface OrganizationTreeNode {
  name: string;
  isFile: boolean;
  children: Map<string, OrganizationTreeNode>;
}

/**
 * Gradi ugnježdeno stablo iz ravne liste planiranih akcija.
 */
function buildOrganizationTree(
  actions: ImportPreview["actions"],
): OrganizationTreeNode {
  const root: OrganizationTreeNode = {
    name: "",
    isFile: false,
    children: new Map(),
  };

  for (const action of actions) {
    const isFile = action.action_type !== "CREATE_DIRECTORY";
    const segments = action.destination
      .split(/[\\/]/)
      .filter(Boolean);
    let node = root;

    segments.forEach((segment, index) => {
      let child = node.children.get(segment);

      if (!child) {
        child = { name: segment, isFile: false, children: new Map() };
        node.children.set(segment, child);
      }

      if (index === segments.length - 1 && isFile) {
        child.isFile = true;
      }

      node = child;
    });
  }

  return root;
}

function OrganizationTreeItem({
  depth,
  node,
}: {
  depth: number;
  node: OrganizationTreeNode;
}) {
  const childCount = node.children.size;
  const isFolder = childCount > 0;
  // Folderi sa puno fajlova (npr. "subtitles") su skupljeni po defaultu.
  const [expanded, setExpanded] = useState(childCount <= 6);
  const indent = `${8 + depth * 16}px`;

  if (!isFolder) {
    return (
      <div
        className="filmium-import-tree-row file"
        style={{ paddingLeft: indent }}
      >
        <File size={14} />
        <span>{node.name}</span>
      </div>
    );
  }

  return (
    <>
      <button
        className="filmium-import-tree-row folder"
        onClick={() => setExpanded((value) => !value)}
        style={{ paddingLeft: indent }}
        type="button"
      >
        {expanded ? (
          <ChevronDown size={13} />
        ) : (
          <ChevronRight size={13} />
        )}
        <FolderInput size={14} />
        <span>{node.name}</span>
        {!expanded && (
          <em className="filmium-import-tree-count">{childCount}</em>
        )}
      </button>
      {expanded &&
        [...node.children.values()].map((child) => (
          <OrganizationTreeItem
            depth={depth + 1}
            key={child.name}
            node={child}
          />
        ))}
    </>
  );
}

function OrganizationTree({
  depth,
  node,
}: {
  depth: number;
  node: OrganizationTreeNode;
}) {
  return (
    <>
      {[...node.children.values()].map((child) => (
        <OrganizationTreeItem
          depth={depth}
          key={child.name}
          node={child}
        />
      ))}
    </>
  );
}


export default function FilmiumLibraryImportPreview({
  busy,
  bulkBusy,
  selectedCount,
  onSelectAllSameStatus,
  onTransferAll,
  onClearSelection,
  entry,
  libraries,
  onClose,
  onConfirm,
  onQueue,
  onIgnore,
  onNeverDetect,
  onDestroy,
  preview,
}: FilmiumLibraryImportPreviewProps) {
  const warnings = [...preview.warnings, ...preview.blocking_warnings];

  const suggestedGenres = preview.suggested_genres ?? [];

  // Moguća odredišta: sve trajne biblioteke + glavni disk + skenirana lokacija.
  const targetLibraries = libraries.filter(
    (library) =>
      library.is_persistent !== false ||
      library.is_main ||
      library.id === preview.library_root_id,
  );
  // Podrazumevano odredište: glavni disk → bilo koja trajna biblioteka →
  // (tek na kraju) trenutno skenirana lokacija.
  const mainLibrary = libraries.find((library) => library.is_main);
  const defaultTargetRootId =
    mainLibrary?.id
    ?? libraries.find(
      (library) => library.is_persistent !== false,
    )?.id
    ?? preview.library_root_id;
  // Dok čovek sam ne izabere odredište, prati se glavni disk — i to se IZVODI
  // pri crtanju. Upis iz efekta značio je jedan kadar sa starim odredištem
  // pošto se glavni disk već promenio.
  const [izabranoOdrediste, setTargetRootId] = useState<number | null>(null);
  const targetRootId = izabranoOdrediste ?? defaultTargetRootId;
  const [showAllSubtitles, setShowAllSubtitles] = useState(false);
  const [artVersions, setArtVersions] = useState<Record<string, number>>(
    {},
  );
  // Stvarni progres uvoza (dva bara: ceo film + tekući fajl). Van uvoza ga
  // nema — izvodi se iz `busy`, umesto da ga efekat briše.
  const [napredakUvoza, setImportProgress] =
    useState<SseProgress | null>(null);
  const importProgress = busy ? napredakUvoza : null;

  // FILM / ANIME / DOMAĆE: rutiranje pri uvozu.
  const [contentMode, setContentMode] =
    useState<FilmiumContentMode>("regular");

  // Sinhronizovano (SINH) vs. titlovan (podrazumevano).
  const [synchronized, setSynchronized] = useState(false);

  const targetLibrary = targetLibraries.find(
    (library) => library.id === targetRootId,
  );
  const organizationTree = buildOrganizationTree(preview.actions);

  // Stanje predloženih žanrova: "suggested" (žuto, dodaje se),
  // "confirmed" (zeleno, korisnik potvrdio, dodaje se), "off" (isključen).
  const [genreStates, setGenreStates] = useState<
    Record<string, "suggested" | "confirmed" | "off">
  >(() =>
    Object.fromEntries(
      suggestedGenres.map((genre) => [genre, "suggested"]),
    ),
  );

  function cycleGenre(genre: string): void {
    setGenreStates((current) => {
      const state = current[genre] ?? "suggested";
      const next =
        state === "suggested"
          ? "confirmed"
          : state === "confirmed"
            ? "off"
            : "suggested";

      return { ...current, [genre]: next };
    });
  }

  /**
   * Šalje uniju postojećih i izabranih predloženih žanrova pri uvozu.
   */
  function handleConfirm(
    conflictMode: "fail" | "skip" | "overwrite" = "fail",
  ): void {
    setImportProgress({
      files_done: 0,
      files_total: 0,
      file_done: 0,
      file_total: 0,
    });
    onConfirm(
      buildOverrides(),
      (value) => setImportProgress(value),
      conflictMode,
      contentMode,
      synchronized,
    );
  }

  // Podudaranje sa postojećim zapisom u biblioteci (žuta kartica).
  const hasExistingMatch = preview.match_status === "existing";

  function handleQueue(): void {
    onQueue(buildOverrides(), contentMode, synchronized);
  }

  // Podešavanja koja se prenose na sve izabrane stavke pri „Prebaci sve".
  function bulkSettings(): FilmiumBulkImportSettings {
    return { contentMode, synchronized, targetRootId };
  }

  function buildOverrides(): FilmiumImportOverrides {
    const overrides: FilmiumImportOverrides = {
      target_library_root_id: targetRootId,
    };

    const acceptedSuggestions = suggestedGenres.filter(
      (genre) => (genreStates[genre] ?? "suggested") !== "off",
    );

    if (acceptedSuggestions.length > 0) {
      overrides.genres = [...preview.genres, ...acceptedSuggestions];
    }

    return overrides;
  }

  const videoFile: FilmiumImportPreviewFile | undefined =
    preview.detected_files.find((file) => file.role === "video");
  const subtitleFiles = preview.detected_files.filter(
    (file) => file.role === "subtitle",
  );
  const videoTags = videoFile
    ? parseVideoTags(videoFile.relative_path)
    : [];
  const realTechChips = preview.technical
    ? technicalChips(preview.technical)
    : [];
  const hasRealTech = realTechChips.length > 0;
  const displayTechChips = hasRealTech ? realTechChips : videoTags;
  const backdropFile = preview.detected_files.find(
    (file) => file.role === "backdrop",
  );
  const backdropUrl = backdropFile
    ? getFilmiumLibraryArtworkUrl(
        preview.library_root_id,
        preview.relative_directory,
        backdropFile.relative_path,
      )
    : null;

  return (
    <div
      className={`filmium-import-preview${
        hasExistingMatch ? " has-match" : ""
      }`}
    >
      {backdropUrl && (
        <div
          aria-hidden="true"
          className="filmium-import-backdrop"
          style={{ backgroundImage: `url("${backdropUrl}")` }}
        />
      )}
      {hasExistingMatch && (
        <div className="filmium-import-match-banner">
          Podudaranje sa postojećim u biblioteci. Izaberi: „Dodaj novo" (samo
          fajlovi kojih nema), „Dodaj sve" ili „Overriduj postojeće".
        </div>
      )}
      <div className="filmium-import-preview-heading">
        <div>
          <p className="eyebrow">Pregled pre uvoza</p>
          <h4>{preview.title}</h4>
        </div>
        <button
          aria-label={`Zatvori pregled ${entry.title ?? entry.directory}`}
          className="filmium-library-icon-button"
          onClick={onClose}
          type="button"
        >
          <X size={17} />
        </button>
      </div>

      <div className="filmium-import-editor">
        {/* ==========          KOLONA 1 — DETALJI          ========== */}
        <section className="filmium-import-col">
          <div className="filmium-import-field-row">
            <div className="filmium-import-field">
              <span>Naslov</span>
              <p className="filmium-import-field-value">
                {preview.title}
              </p>
            </div>
            <div className="filmium-import-field year">
              <span>Godina</span>
              <p className="filmium-import-field-value">
                {preview.release_year ?? "—"}
              </p>
            </div>
          </div>

          {videoFile && (
            <div className="filmium-import-block">
              <p className="filmium-import-block-label">Otkriven video</p>
              <div className="filmium-import-video">
                <span className="filmium-import-video-icon">
                  <Film size={18} />
                </span>
                <div className="filmium-import-video-copy">
                  <strong title={videoFile.relative_path}>
                    {videoFile.relative_path}
                  </strong>
                  <small>
                    {[
                      formatBytes(videoFile.size_bytes),
                      fileContainer(videoFile.relative_path),
                      ...videoTags,
                    ]
                      .filter(Boolean)
                      .join(" · ")}
                  </small>
                </div>
                <button
                  className="filmium-import-ghost-button"
                  disabled
                  title="Uskoro"
                  type="button"
                >
                  Promeni
                </button>
              </div>
            </div>
          )}

          <div className="filmium-import-block">
            <p className="filmium-import-block-label">
              Titlovi
              {subtitleFiles.length > 0
                ? ` (${subtitleFiles.length})`
                : ""}
            </p>
            <div className="filmium-import-subtitles">
              {subtitleFiles.length === 0 && (
                <span className="filmium-import-empty">
                  Nije pronađen nijedan prevod.
                </span>
              )}
              {(showAllSubtitles
                ? subtitleFiles
                : subtitleFiles.slice(0, 2)
              ).map((file) => {
                const relPath =
                  preview.relative_directory === "."
                    ? file.relative_path
                    : `${preview.relative_directory}/${file.relative_path}`;
                return (
                  <button
                    className="filmium-import-subtitle-chip"
                    key={file.relative_path}
                    onClick={() =>
                      void pickAndReplaceSubtitle(
                        preview.library_root_id,
                        relPath,
                      )}
                    title="Zameni prevod (izaberi novi)"
                    type="button"
                  >
                    <Languages size={13} />
                    {file.language
                      ? file.language.toUpperCase()
                      : "Prevod"}
                  </button>
                );
              })}
              {subtitleFiles.length > 2 && (
                <button
                  className="filmium-import-subtitle-add"
                  onClick={() =>
                    setShowAllSubtitles((value) => !value)}
                  type="button"
                >
                  {showAllSubtitles
                    ? "Prikaži manje"
                    : `Pokaži sve (${subtitleFiles.length})`}
                </button>
              )}
            </div>
          </div>

          {(preview.genres.length > 0
            || suggestedGenres.length > 0) && (
            <div className="filmium-import-block">
              <p className="filmium-import-block-label">Žanrovi</p>
              <div className="filmium-import-genres">
                {preview.genres.map((genre) => (
                  <span
                    className="filmium-import-genre-chip state-confirmed"
                    key={genre}
                  >
                    {genre}
                  </span>
                ))}
                {suggestedGenres.map((genre) => {
                  const state = genreStates[genre] ?? "suggested";

                  return (
                    <button
                      className={
                        `filmium-import-genre-chip state-${state}`
                      }
                      key={genre}
                      onClick={() => cycleGenre(genre)}
                      type="button"
                    >
                      {genre}
                    </button>
                  );
                })}
              </div>
              {suggestedGenres.length > 0 && (
                <small className="filmium-import-genre-hint">
                  Žuto = predloženo iz sličnih filmova (dodaje se);
                  klik = potvrdi (zeleno), još klik = isključi.
                </small>
              )}
            </div>
          )}

          <div className="filmium-import-block">
            <p className="filmium-import-block-label">
              Tehničke informacije
            </p>
            <div className="filmium-import-tech">
              {displayTechChips.length > 0 ? (
                displayTechChips.map((tag) => (
                  <span className="filmium-import-tech-chip" key={tag}>
                    {tag}
                  </span>
                ))
              ) : (
                <span className="filmium-import-empty">
                  Detekcija u pripremi (media-probe).
                </span>
              )}
            </div>
            {!hasRealTech && (
              <small className="filmium-import-tech-note">
                Približno iz imena fajla; tačne vrednosti stižu kad je
                ffprobe dostupan.
              </small>
            )}
          </div>

        </section>

        {/* ==========          KOLONA 2 — UMETNIČKA DELA          ========== */}
        <section className="filmium-import-col">
          <p className="filmium-import-block-label">
            Otkrivena umetnička dela
          </p>
          <div className="filmium-import-artwork-grid">
            {ART_SLOTS.map((slot) => {
              const file = preview.detected_files.find(
                (item) => item.role === slot.role,
              );
              const version = artVersions[slot.role] ?? 0;
              const imageUrl = file
                ? `${getFilmiumLibraryArtworkUrl(
                    preview.library_root_id,
                    preview.relative_directory,
                    file.relative_path,
                  )}&v=${version}`
                : null;

              const relPath = file
                ? preview.relative_directory === "."
                  ? file.relative_path
                  : `${preview.relative_directory}/${file.relative_path}`
                : null;

              return (
                <button
                  className={`filmium-import-artwork filmium-artwork-button${
                    file ? " detected" : ""
                  }`}
                  disabled={!relPath}
                  key={slot.role}
                  onClick={() => {
                    if (!relPath) {
                      return;
                    }
                    void pickAndReplaceArtwork(
                      preview.library_root_id,
                      relPath,
                    ).then((ok) => {
                      if (ok) {
                        setArtVersions((current) => ({
                          ...current,
                          [slot.role]: version + 1,
                        }));
                      }
                    });
                  }}
                  title={
                    file
                      ? "Promeni sliku (izaberi novu)"
                      : "Slika nije pronađena"
                  }
                  type="button"
                >
                  <div className="filmium-import-artwork-thumb">
                    {imageUrl ? (
                      <img
                        alt={slot.label}
                        loading="lazy"
                        src={imageUrl}
                      />
                    ) : (
                      <FileImage size={22} />
                    )}
                  </div>
                  <div className="filmium-import-artwork-meta">
                    <strong>{slot.label}</strong>
                    <small>{file ? "Promeni" : "Nije pronađeno"}</small>
                  </div>
                </button>
              );
            })}
          </div>
        </section>

        {/* ==========          KOLONA 3 — PLAN ORGANIZACIJE          ========== */}
        <section className="filmium-import-col">
          <p className="filmium-import-block-label">
            Planirana organizacija
          </p>
          <div className="filmium-import-plan">
            {preview.actions.length === 0 ? (
              <p className="filmium-import-empty">
                Fajlovi su već pravilno organizovani.
              </p>
            ) : (
              <div className="filmium-import-tree">
                <div className="filmium-import-tree-row folder root">
                  <FolderInput size={14} />
                  <span>{targetLibrary?.name ?? "Biblioteka"}</span>
                </div>
                <OrganizationTree depth={1} node={organizationTree} />
              </div>
            )}
          </div>
        </section>
      </div>

      {warnings.length > 0 && (
        <div className="filmium-import-warnings">
          {warnings.map((warning) => (
            <p key={warning}>
              <AlertTriangle size={15} />
              {warning}
            </p>
          ))}
        </div>
      )}

      {(busy || importProgress) && (
        <div className="filmium-import-progress">
          <div className="filmium-import-progress-heading">
            <strong>Ceo film</strong>
            <span>
              {importProgress ? sseOverallPercent(importProgress) : 0}%
            </span>
          </div>
          <div className="filmium-import-progress-track">
            <span
              style={{
                width: `${
                  importProgress ? sseOverallPercent(importProgress) : 0
                }%`,
              }}
            />
          </div>

          <div className="filmium-import-progress-heading">
            <strong>Trenutni fajl</strong>
            <span>
              {importProgress ? sseFilePercent(importProgress) : 0}%
            </span>
          </div>
          <div className="filmium-import-progress-track">
            <span
              style={{
                width: `${
                  importProgress ? sseFilePercent(importProgress) : 0
                }%`,
              }}
            />
          </div>

          <small>
            Organizujem fajlove, upisujem podatke i osvežavam FILMIUM.
          </small>
        </div>
      )}

      <div className="filmium-import-mode-row">
        <div className="filmium-import-mode-left">
          <ContentModeToggle mode={contentMode} onChange={setContentMode} />
          {!hasExistingMatch && (
            <div className="filmium-import-bulk">
              <button
                className="secondary-button filmium-import-bulk-button"
                disabled={bulkBusy}
                onClick={onSelectAllSameStatus}
                title="Izaberi sve stavke istog statusa u ovom skenu"
                type="button"
              >
                <ListChecks size={14} />
                Selektuj sve
              </button>
              <button
                className="primary-button filmium-import-bulk-button"
                disabled={bulkBusy || selectedCount === 0}
                onClick={() => onTransferAll(bulkSettings())}
                title="Prebaci sve izabrane u listu (sa TMDB podacima)"
                type="button"
              >
                {bulkBusy ? (
                  <LoaderCircle className="spinning" size={14} />
                ) : (
                  <FolderInput size={14} />
                )}
                Prebaci sve
                {selectedCount > 0 ? ` (${selectedCount})` : ""}
              </button>
              {selectedCount > 0 && !bulkBusy && (
                <button
                  className="filmium-import-ghost-button filmium-import-bulk-clear"
                  onClick={onClearSelection}
                  type="button"
                >
                  Poništi
                </button>
              )}
            </div>
          )}
        </div>
        <div className="filmium-sync-row">
          <span className="filmium-sync-label">
            {synchronized ? "Sinhronizovano" : "Titlovan"}
          </span>
          <button
            aria-pressed={synchronized}
            className={`filmium-sync-toggle${synchronized ? " on" : ""}`}
            onClick={() => setSynchronized((value) => !value)}
            type="button"
          >
            <span className="filmium-sync-knob" />
            SINH
          </button>
        </div>
      </div>

      <div className="filmium-import-preview-footer">
        <button
          className="filmium-import-ghost-button"
          onClick={onIgnore}
          title="Sakrij iz trenutnih rezultata"
          type="button"
        >
          Ignoriši
        </button>
        <button
          className="filmium-import-ghost-button danger"
          onClick={onNeverDetect}
          title="Trajno izuzmi ovaj folder iz skeniranja"
          type="button"
        >
          Nikada više ne otkrivaj
        </button>
        {onDestroy && (
          <button
            className="filmium-import-ghost-button danger"
            disabled={busy}
            onClick={onDestroy}
            title="Trajno obriši ovaj folder sa diska"
            type="button"
          >
            Uništi
          </button>
        )}
        <select
          aria-label="Ciljna biblioteka"
          className="filmium-import-target-select"
          onChange={(event) => {
            setTargetRootId(Number(event.target.value));
          }}
          value={targetRootId}
        >
          {targetLibraries.map((library) => (
            <option key={library.id} value={library.id}>
              {libraryOptionLabel(library)}
            </option>
          ))}
        </select>
        {!hasExistingMatch && (
          <button
            className="secondary-button filmium-import-queue-button"
            disabled={busy || !preview.can_confirm}
            onClick={handleQueue}
            type="button"
          >
            <ListPlus size={17} />
            Dodaj u listu
          </button>
        )}
        {hasExistingMatch ? (
          <>
            <button
              className="secondary-button"
              disabled={busy || !preview.can_confirm}
              onClick={() => handleConfirm("skip")}
              title="Dodaj samo fajlove kojih još nema"
              type="button"
            >
              Dodaj novo
            </button>
            <button
              className="secondary-button"
              disabled={busy || !preview.can_confirm}
              onClick={() => handleConfirm("overwrite")}
              title="Dodaj sve (postojeće se prepisuje)"
              type="button"
            >
              Dodaj sve
            </button>
            <button
              className="primary-button"
              disabled={busy || !preview.can_confirm}
              onClick={() => handleConfirm("overwrite")}
              title="Prepiši postojeće fajlove novima"
              type="button"
            >
              {busy
                ? <LoaderCircle className="spinning" size={17} />
                : <CheckCircle2 size={17} />}
              Overriduj
            </button>
          </>
        ) : (
          <button
            className="primary-button"
            disabled={busy || !preview.can_confirm}
            onClick={() => handleConfirm("fail")}
            type="button"
          >
            {busy
              ? <LoaderCircle className="spinning" size={17} />
              : <CheckCircle2 size={17} />}
            + Biblioteka
          </button>
        )}
      </div>
    </div>
  );
}
