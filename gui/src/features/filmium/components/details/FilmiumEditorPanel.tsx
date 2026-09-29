import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";

import {
  CalendarDays,
  Check,
  Clock,
  Copy,
  Download,
  ExternalLink,
  Folder,
  FolderOpen,
  GripVertical,
  Languages,
  Image as ImageIcon,
  Info,
  Link2,
  Minus,
  Music,
  Pencil,
  Play,
  Plus,
  RefreshCw,
  Save,
  Sparkles,
  Star,
  ThumbsUp,
  Trash2,
  TriangleAlert,
  Trophy,
  UploadCloud,
  Users,
  X,
} from "lucide-react";

import {
  deleteFilmiumMediaAsset,
  deleteFilmiumMediaItem,
  getFilmiumAssetUrl,
  getFilmiumGenres,
  getFilmiumMediaItem,
  updateFilmiumMediaItem,
} from "../../../../services/filmiumApi";
import {
  addSubtitleToSource,
  autoUpdateFilmiumMedia,
  deleteFilmiumEpisode,
  deleteSourceFile,
  downloadSourceFileToDesktop,
  enrichFilmiumMediaFromTmdb,
  getFilmiumEpisodeMetadata,
  getFilmiumEpisodeTechnical,
  getFilmiumMediaTechnical,
  rescanFilmiumMediaSource,
  updateFilmiumEpisode,
  type FilmiumEpisode,
  type FilmiumEpisodeMetadata,
  type FilmiumSeason,
  type FilmiumTechnical,
  type FilmiumTmdbEnrichment,
} from "../../../../services/filmiumMediaSourceApi";
import { getFilmiumSeriesEpisodeThumbnailUrl } from "../../../../services/filmiumSeriesApi";
import FilmiumSubtitleRepairPanel from "../uploads/FilmiumSubtitleRepairPanel";
import type {
  ExternalRatingsData,
  MediaCollection,
  MediaItem,
  MediaItemCreateRequest,
  WatchStatus,
} from "../../../../types/filmium";
import type { FilmiumMediaSource } from "../../../../types/filmiumMediaSource";


// ==========          SVOJSTVA PANELA          ==========

type FilmiumEditorPanelProps = {
  item: MediaItem;
  sources: FilmiumMediaSource[];
  seasons: FilmiumSeason[];
  catalog?: MediaItem[];
  collections?: MediaCollection[];
  onAddToCollection?: (
    collectionId: number,
    itemId: number,
  ) => void | Promise<void>;
  onOpenSubtitleTool?: () => void;
  onDeleteMedia?: () => void;
  onSaved?: () => void;
  onClose: () => void;
};


// ==========          TABOVI          ==========

const EDITOR_TABS = [
  "Osnovno",
  "Mediji",
  "Fajlovi",
  "Ocene",
  "Kategorije",
  "Prevodi",
  "Epizode",
  "Napredno",
] as const;

type EditorTab = (typeof EDITOR_TABS)[number];


// ==========          TIP SADRŽAJA          ==========

const CONTENT_TYPE_OPTIONS = [
  "Film",
  "Serija",
  "Mini-serija",
  "Specijal",
] as const;

const WATCH_STATUS_OPTIONS = [
  "Planirano",
  "Gleda se",
  "Završeno",
  "Pauzirano",
  "Napušteno",
] as const;

const WATCH_STATUS_LABEL: Record<string, string> = {
  planned: "Planirano",
  watching: "Gleda se",
  completed: "Završeno",
  paused: "Pauzirano",
  dropped: "Napušteno",
};

const WATCH_STATUS_FROM_LABEL: Record<string, WatchStatus> = {
  Planirano: "planned",
  "Gleda se": "watching",
  Završeno: "completed",
  Pauzirano: "paused",
  Napušteno: "dropped",
};

const WATCH_PRIORITY_OPTIONS = [
  "Nizak",
  "Srednji",
  "Visok",
  "Sledeće na redu",
] as const;

const SUBTITLE_FORMAT_OPTIONS = [
  "SRT",
  "ASS",
  "SUB",
  "VTT",
] as const;


// ==========          MOCK STANJE EPIZODE          ==========

type EpisodeDraft = {
  id: number;
  seasonNumber: number;
  episodeNumber: number;
  title: string;
  runtimeMinutes: number | null;
  status: string;
};


// ==========          POMOĆNE KOMPONENTE          ==========

/**
 * Mala TMDB oznaka koja obeležava polja koja TMDB može automatski dopuniti.
 */
function TmdbBadge() {
  return (
    <span
      className="filmium-editor-tmdb-badge"
      title="Može se automatski dopuniti sa TMDB"
    >
      TMDB
    </span>
  );
}

type FieldProps = {
  label: string;
  children: ReactNode;
  required?: boolean;
  tmdb?: boolean;
};

/**
 * Prikazuje jedno polje editora sa labelom.
 */
function Field({ label, children, required, tmdb }: FieldProps) {
  return (
    <label className="filmium-editor-field">
      <span className="filmium-editor-field-label">
        {label}
        {required && <em> *</em>}
        {tmdb && <TmdbBadge />}
      </span>
      {children}
    </label>
  );
}

type TagListProps = {
  values: string[];
  onChange: (values: string[]) => void;
  placeholder?: string;
  highlight?: boolean;
};

/**
 * Uređuje listu oznaka (glumci, žanrovi, liste...).
 */
function TagList({
  values,
  onChange,
  placeholder,
  highlight,
}: TagListProps) {
  const [draft, setDraft] = useState("");

  function commitDraft(): void {
    const trimmed = draft.trim();
    if (trimmed === "" || values.includes(trimmed)) {
      setDraft("");
      return;
    }
    onChange([...values, trimmed]);
    setDraft("");
  }

  return (
    <div
      className={`filmium-editor-tags${highlight ? " tmdb-filled" : ""}`}
    >
      {values.map((value) => (
        <span className="filmium-editor-tag" key={value}>
          {value}
          <button
            aria-label={`Ukloni ${value}`}
            onClick={() =>
              onChange(values.filter((entry) => entry !== value))}
            type="button"
          >
            <X size={12} />
          </button>
        </span>
      ))}

      <input
        className="filmium-editor-tag-input"
        onBlur={commitDraft}
        onChange={(event) => setDraft(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            event.preventDefault();
            commitDraft();
          }
        }}
        placeholder={placeholder ?? "Dodaj +"}
        value={draft}
      />
    </div>
  );
}

type InfoRowProps = {
  label: string;
  value: string;
  onChange: (value: string) => void;
  tmdb?: boolean;
  highlight?: boolean;
};

/**
 * Prikazuje jedan red u tehničkoj/ocena tabeli sa inline izmenom.
 */
function InfoRow({
  label,
  value,
  onChange,
  tmdb,
  highlight,
}: InfoRowProps) {
  return (
    <div className="filmium-editor-info-row">
      <span className="filmium-editor-info-label">
        {label}
        {tmdb && <TmdbBadge />}
      </span>
      <input
        className={
          highlight
            ? "filmium-editor-info-input tmdb-filled"
            : "filmium-editor-info-input"
        }
        onChange={(event) => onChange(event.target.value)}
        value={value}
      />
    </div>
  );
}


// ==========          FILMIUM EDITOR PANEL          ==========

/**
 * Veliki editor sadržaja koji se otvara iz detalja filma/serije.
 *
 * Panel je samostalan i koristi lokalni mock state — čuvanje na backend
 * povezaćemo kada editor API bude spreman.
 */
function FilmiumEditorPanel({
  item,
  sources,
  seasons,
  catalog = [],
  collections: allCollections = [],
  onAddToCollection,
  onOpenSubtitleTool,
  onDeleteMedia,
  onSaved,
  onClose,
}: FilmiumEditorPanelProps) {
  const [activeTab, setActiveTab] = useState<EditorTab>("Osnovno");
  const [subtitleToolOpen, setSubtitleToolOpen] = useState(false);

  // Sačuvana „basic" podešavanja iz baze (za round-trip Osnovno polja).
  const savedBasic = (item.editor_settings?.basic ?? {}) as {
    content_type?: string;
    local_title_sr?: string;
    local_title_hr?: string;
    local_title_bs?: string;
    personal_note?: string;
    watch_priority?: string;
  };

  // ==========          OSNOVNE INFORMACIJE          ==========

  const [title, setTitle] = useState(item.title);
  const [originalTitle, setOriginalTitle] = useState(
    item.original_title ?? "",
  );
  const [englishTitle, setEnglishTitle] = useState(
    item.english_title ?? "",
  );
  const [localTitleSr, setLocalTitleSr] = useState(
    savedBasic.local_title_sr ?? "",
  );
  const [localTitleHr, setLocalTitleHr] = useState(
    savedBasic.local_title_hr ?? "",
  );
  const [localTitleBs, setLocalTitleBs] = useState(
    savedBasic.local_title_bs ?? "",
  );
  const [contentType, setContentType] = useState<string>(
    savedBasic.content_type
      ?? (item.media_type === "series" ? "Serija" : "Film"),
  );
  const [descriptionLocal, setDescriptionLocal] = useState(
    item.notes ?? "",
  );
  const [descriptionEnglish, setDescriptionEnglish] = useState(
    item.english_description ?? "",
  );
  const [year, setYear] = useState(
    item.release_year ? String(item.release_year) : "",
  );
  const [releaseDate, setReleaseDate] = useState("");
  const [runtime, setRuntime] = useState(
    item.runtime_minutes ? String(item.runtime_minutes) : "",
  );
  const [studio, setStudio] = useState(item.studio ?? "");
  const [director, setDirector] = useState(item.director ?? "");
  const [cast, setCast] = useState<string[]>(
    Array.from(item.cast_names ?? []),
  );
  const [watchStatus, setWatchStatus] = useState<string>(
    WATCH_STATUS_LABEL[item.watch_status] ?? "Planirano",
  );
  const [personalNote, setPersonalNote] = useState(
    savedBasic.personal_note ?? "",
  );
  const [synchronized, setSynchronized] = useState(
    item.is_synchronized ?? false,
  );
  const [isSaving, setIsSaving] = useState(false);

  // Sva dodatna polja iz pod-tabova (mood, pod-ocene, automatika, sync
  // ofseti, IMDb/TVDB, franšiza…) skupljaju se ovde i snimaju kao JSON.
  const initialSettings = useMemo(
    () => (item.editor_settings ?? {}) as Record<string, unknown>,
    [item.editor_settings],
  );
  const [extraSettings, setExtraSettings] = useState<
    Record<string, unknown>
  >(initialSettings);
  const reportSettings = useCallback(
    (scope: string, data: unknown) => {
      setExtraSettings((prev) => ({ ...prev, [scope]: data }));
    },
    [],
  );

  // ==========          TEHNIČKI PODACI          ==========

  const primaryVideo = useMemo(
    () =>
      sources
        .flatMap((source) => source.files)
        .find((file) => file.role === "video"),
    [sources],
  );

  const [resolution, setResolution] = useState("4K");
  const [format, setFormat] = useState("MKV");
  const [videoCodec, setVideoCodec] = useState("H.265 / HEVC");
  const [audioCodec, setAudioCodec] = useState("AC3");
  const [audioLanguages, setAudioLanguages] = useState("SR / EN");
  const [fileSize, setFileSize] = useState(
    primaryVideo ? formatSize(primaryVideo.size_bytes) : "",
  );
  const [bitrate, setBitrate] = useState("");
  const [fps, setFps] = useState("24");
  const [hdr, setHdr] = useState("Da");
  const [filePath, setFilePath] = useState(
    primaryVideo?.relative_path ?? "",
  );
  const [sourceLabel, setSourceLabel] = useState(
    sources[0]?.relative_directory ?? "",
  );

  // ==========          OCENE          ==========

  const [myRating, setMyRating] = useState(
    item.rating !== null ? String(item.rating) : "",
  );
  const [imdb, setImdb] = useState("");
  const [tmdb, setTmdb] = useState("");
  const [rotten, setRotten] = useState("");
  const [metacritic, setMetacritic] = useState("");
  const [audience, setAudience] = useState("");
  const [critics, setCritics] = useState("");

  // ==========          KATEGORIJE          ==========

  const [watchPriority, setWatchPriority] = useState<string>(
    savedBasic.watch_priority ?? "Srednji",
  );
  const [genres, setGenres] = useState<string[]>(
    Array.from(item.genres),
  );
  const [collections, setCollections] = useState<string[]>([]);
  const [lists, setLists] = useState<string[]>([]);
  const [keywords, setKeywords] = useState<string[]>(
    Array.from(item.keywords ?? []),
  );

  // ==========          PREVODI          ==========

  const [srSubtitle, setSrSubtitle] = useState("");
  const [enSubtitle, setEnSubtitle] = useState("");
  const [subtitleFormat, setSubtitleFormat] = useState<string>("SRT");
  const [embeddedSubtitle, setEmbeddedSubtitle] = useState(false);
  const [externalSubtitle, setExternalSubtitle] = useState(true);
  const [dubbing, setDubbing] = useState(false);
  const [subtitleVersion, setSubtitleVersion] = useState("");

  // ==========          SERIJA          ==========

  const [isSeries, setIsSeries] = useState(
    item.media_type === "series",
  );
  const [activeSeason, setActiveSeason] = useState<number>(
    seasons[0]?.season_number ?? 1,
  );
  const [editingEpisode, setEditingEpisode] =
    useState<EpisodeDraft | null>(null);

  const episodeDrafts = useMemo<EpisodeDraft[]>(
    () =>
      seasons.flatMap((season) =>
        season.episodes.map((episode) => ({
          id: episode.id,
          seasonNumber: season.season_number,
          episodeNumber: episode.episode_number,
          title: episode.title ?? "",
          runtimeMinutes: episode.runtime_minutes,
          status: episode.watch_status,
        })),
      ),
    [seasons],
  );

  // ==========          ESC ZATVARANJE          ==========

  useEffect(() => {
    function handleKey(event: KeyboardEvent): void {
      if (event.key === "Escape") {
        onClose();
      }
    }

    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [onClose]);

  // ==========          TMDB DOPUNA          ==========

  /*
   * Skup ključeva polja koja je TMDB upravo popunio — dobijaju svetlo plavi
   * okvir. Trenutno je enrich lokalni mock; pravi TMDB poziv (jezički lanac
   * sr-RS → hr-HR → bs-BA → en-US + credits, uz preferiranje srpskog) se
   * uključuje ovde kada editor/enrich API bude spreman.
   */
  const [tmdbFilled, setTmdbFilled] = useState<Set<string>>(
    () => new Set(),
  );
  const [isEnriching, setIsEnriching] = useState(false);
  const [enrichMessage, setEnrichMessage] =
    useState<string | null>(null);
  // Poslednji TMDB rezultat — dele ga Ocene i Kategorije tabovi.
  const [enrichData, setEnrichData] =
    useState<FilmiumTmdbEnrichment | null>(null);

  // Ručni override kada „Updatuj" ne pronađe naslov na TMDB-u.
  const [overrideOpen, setOverrideOpen] = useState(false);
  const [overrideText, setOverrideText] = useState("");

  /**
   * Vraća klasu inputa sa oznakom TMDB dopune ako je polje upravo popunjeno.
   */
  function tmdbClass(key: string, base: string): string {
    return tmdbFilled.has(key) ? `${base} tmdb-filled` : base;
  }

  // Kada „Updatuj" donese TMDB podatke (`enrichData`), popuni SAMO prazna
  // Osnovno polja i obeleži ih „tmdb-filled" okvirom. Nikad ne pregazi ono
  // što je korisnik/DB već popunio (empty-only: `prev === "" ? novo : prev`).
  useEffect(() => {
    if (!enrichData?.matched) {
      return;
    }
    const filled = new Set<string>();

    if (enrichData.original_title && originalTitle === "") {
      setOriginalTitle(enrichData.original_title);
      filled.add("originalTitle");
    }
    if (enrichData.english_title && englishTitle === "") {
      setEnglishTitle(enrichData.english_title);
      filled.add("englishTitle");
    }
    if (enrichData.studio && studio === "") {
      setStudio(enrichData.studio);
      filled.add("studio");
    }
    if (enrichData.director && director === "") {
      setDirector(enrichData.director);
      filled.add("director");
    }
    if (enrichData.cast_names.length > 0 && cast.length === 0) {
      setCast(Array.from(enrichData.cast_names));
      filled.add("cast");
    }
    if (enrichData.genres.length > 0 && genres.length === 0) {
      setGenres(Array.from(enrichData.genres));
      filled.add("genres");
    }

    if (filled.size > 0) {
      setTmdbFilled((prev) => new Set([...prev, ...filled]));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enrichData]);

  const posterUrl = getFilmiumAssetUrl(item.poster_path);
  const backdropUrl = getFilmiumAssetUrl(
    item.backdrop_path ?? item.poster_path,
  );

  /**
   * Ponovo puni sva polja editora iz svežeg zapisa iz baze, da prikaz uvek
   * odražava bazu (posle „Updatuj" ili „Sačuvaj"), bez zatvaranja panela.
   */
  function hydrateFromItem(next: MediaItem): void {
    const basic = (next.editor_settings?.basic ?? {}) as {
      content_type?: string;
      local_title_sr?: string;
      local_title_hr?: string;
      local_title_bs?: string;
      personal_note?: string;
      watch_priority?: string;
    };
    setTitle(next.title);
    setOriginalTitle(next.original_title ?? "");
    setEnglishTitle(next.english_title ?? "");
    setLocalTitleSr(basic.local_title_sr ?? "");
    setLocalTitleHr(basic.local_title_hr ?? "");
    setLocalTitleBs(basic.local_title_bs ?? "");
    setContentType(
      basic.content_type
        ?? (next.media_type === "series" ? "Serija" : "Film"),
    );
    setDescriptionLocal(next.notes ?? "");
    setDescriptionEnglish(next.english_description ?? "");
    setYear(next.release_year ? String(next.release_year) : "");
    setRuntime(next.runtime_minutes ? String(next.runtime_minutes) : "");
    setStudio(next.studio ?? "");
    setDirector(next.director ?? "");
    setCast(Array.from(next.cast_names ?? []));
    setGenres(Array.from(next.genres));
    setKeywords(Array.from(next.keywords ?? []));
    setWatchStatus(WATCH_STATUS_LABEL[next.watch_status] ?? "Planirano");
    setSynchronized(next.is_synchronized ?? false);
    setMyRating(next.rating !== null ? String(next.rating) : "");
    setPersonalNote(basic.personal_note ?? "");
    setWatchPriority(basic.watch_priority ?? "Srednji");
    setExtraSettings((next.editor_settings ?? {}) as Record<string, unknown>);
  }

  /**
   * Povlači svež zapis iz baze i osvežava sva polja. Tolerantno na greške.
   */
  async function reloadFromDb(): Promise<void> {
    try {
      hydrateFromItem(await getFilmiumMediaItem(item.id));
    } catch {
      /* prikaz ostaje kakav jeste ako refetch ne uspe */
    }
  }

  /**
   * „Updatuj": serverski dopuni naslov iz TMDB-a (naslov/opis na srpskoj
   * latinici, ključne reči) i snimi u bazu, pa osveži prikaz. Ako TMDB ne
   * pronađe naslov, otvara polje za ručni TMDB naziv/ID.
   */
  async function runAutoUpdate(): Promise<void> {
    if (isEnriching) {
      return;
    }

    setIsEnriching(true);
    setEnrichMessage(null);

    const trimmedOverride = overrideText.trim();
    const body: { tmdb_id?: number; override_title?: string } = {};
    if (trimmedOverride !== "") {
      if (/^\d+$/.test(trimmedOverride)) {
        body.tmdb_id = Number.parseInt(trimmedOverride, 10);
      } else {
        body.override_title = trimmedOverride;
      }
    }

    try {
      const result = await autoUpdateFilmiumMedia(item.id, body);
      setEnrichMessage(result.message);
      if (result.matched) {
        setOverrideOpen(false);
        // Osveži sva polja iz baze (naslovi, opisi, ključne reči…).
        await reloadFromDb();
        // Osveži TMDB podatke za Ocene/Kategorije tabove.
        try {
          setEnrichData(await enrichFilmiumMediaFromTmdb(item.id));
        } catch {
          /* tolerantno — tabovi rade i bez ovoga */
        }
        onSaved?.();
      } else {
        setOverrideOpen(true);
      }
    } catch (error) {
      setEnrichMessage(
        error instanceof Error ? error.message : "Ažuriranje nije uspelo.",
      );
    } finally {
      setIsEnriching(false);
    }
  }

  /**
   * Snima izmene u bazu (INSERT/UPDATE preko PUT). Mapira polja editora na
   * kolone koje baza podržava (naslovi, opisi, godina, trajanje, status,
   * ocena, žanrovi, glumci, kategorija). Prazna polja se čuvaju kao NULL.
   */
  async function persistChanges(closeAfter: boolean): Promise<void> {
    if (isSaving) {
      return;
    }
    setIsSaving(true);
    setEnrichMessage(null);

    function toNullableInt(value: string): number | null {
      const trimmed = value.trim();
      if (trimmed === "") {
        return null;
      }
      const parsed = Number.parseInt(trimmed, 10);
      return Number.isFinite(parsed) ? parsed : null;
    }

    try {
      const parsedRating = toNullableInt(myRating);
      const payload: MediaItemCreateRequest = {
        title: title.trim() || item.title,
        media_type: item.media_type,
        original_title: originalTitle.trim() || null,
        english_title: englishTitle.trim() || null,
        release_year: toNullableInt(year),
        runtime_minutes: toNullableInt(runtime),
        watch_status:
          WATCH_STATUS_FROM_LABEL[watchStatus] ?? item.watch_status,
        rating:
          parsedRating === null
            ? null
            : Math.min(10, Math.max(1, parsedRating)),
        notes: descriptionLocal.trim() || null,
        english_description: descriptionEnglish.trim() || null,
        genres,
        cast_names: cast,
        keywords,
        content_category: item.content_category ?? "regular",
        is_favorite: item.is_favorite,
        studio: studio.trim() || null,
        director: director.trim() || null,
        is_synchronized: synchronized,
        editor_settings: {
          ...extraSettings,
          basic: {
            content_type: contentType,
            local_title_sr: localTitleSr,
            local_title_hr: localTitleHr,
            local_title_bs: localTitleBs,
            personal_note: personalNote,
            watch_priority: watchPriority,
          },
        },
      };

      await updateFilmiumMediaItem(item.id, payload);
      onSaved?.();
      setEnrichMessage("Izmene su sačuvane u bazu.");
      if (closeAfter) {
        onClose();
      } else {
        // Osveži prikaz iz baze (naslovi, opisi, ključne reči…).
        await reloadFromDb();
      }
    } catch (error) {
      setEnrichMessage(
        error instanceof Error ? error.message : "Čuvanje nije uspelo.",
      );
    } finally {
      setIsSaving(false);
    }
  }

  const hasPoster = Boolean(posterUrl);
  const hasBackdrop = Boolean(backdropUrl);
  const showBasic = activeTab === "Osnovno";

  return createPortal(
    <div
      className="filmium-editor-overlay"
      onClick={onClose}
      role="presentation"
    >
      <aside
        aria-label="Uredi sadržaj"
        className="filmium-editor-panel"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
      >
        {/* ==========          HEADER          ========== */}

        <header className="filmium-editor-header">
          <div className="filmium-editor-header-title">
            <span className="filmium-editor-header-icon">
              <Pencil size={18} />
            </span>
            <div>
              <h2>Uredi sadržaj</h2>
              <p>{item.title}</p>
            </div>
          </div>

          <div className="filmium-editor-header-actions">
            <button
              className="filmium-editor-button tmdb"
              disabled={isEnriching}
              onClick={() => void runAutoUpdate()}
              type="button"
            >
              <Sparkles size={16} />
              {isEnriching ? "Ažuriram…" : "Updatuj"}
            </button>

            <button
              className="filmium-editor-button ghost"
              disabled={isSaving}
              onClick={() => void persistChanges(false)}
              type="button"
            >
              <Save size={16} />
              {isSaving ? "Čuvam…" : "Sačuvaj"}
            </button>

            <button
              className="filmium-editor-button primary"
              disabled={isSaving}
              onClick={() => void persistChanges(true)}
              type="button"
            >
              <UploadCloud size={16} />
              Objavi
            </button>

            <button
              className="filmium-editor-button ghost"
              onClick={onClose}
              type="button"
            >
              <X size={16} />
              Zatvori
            </button>
          </div>
        </header>

        {/* ==========          TABOVI          ========== */}

        <nav className="filmium-editor-tabs">
          {EDITOR_TABS.map((tab) => (
            <button
              className={`filmium-editor-tab${
                activeTab === tab ? " active" : ""
              }`}
              key={tab}
              onClick={() => setActiveTab(tab)}
              type="button"
            >
              {tab}
            </button>
          ))}
        </nav>

        {enrichMessage && (
          <p className="filmium-editor-enrich-message">
            {enrichMessage}
          </p>
        )}

        {overrideOpen && (
          <div className="filmium-editor-override-row">
            <input
              className="filmium-editor-input"
              onChange={(event) => setOverrideText(event.target.value)}
              placeholder="TMDB naziv ili ID (npr. Ballerina ili 917496)"
              value={overrideText}
            />
            <button
              className="filmium-editor-button ghost small"
              disabled={isEnriching}
              onClick={() => void runAutoUpdate()}
              type="button"
            >
              <RefreshCw size={14} />
              Pokušaj ponovo
            </button>
          </div>
        )}

        {/* ==========          TELO          ========== */}

        <div className="filmium-editor-body">
          {activeTab === "Mediji" && (
            <MediaTab
              backdropUrl={backdropUrl}
              hasBackdrop={hasBackdrop}
              hasPoster={hasPoster}
              item={item}
              posterUrl={posterUrl}
            />
          )}

          {activeTab === "Fajlovi" && (
            <FilesTab item={item} sources={sources} />
          )}

          {activeTab === "Ocene" && (
            <RatingsTab
              catalog={catalog}
              collections={allCollections}
              enrichment={enrichData}
              initialSettings={extraSettings.ratings}
              item={item}
              onReport={(data) => reportSettings("ratings", data)}
            />
          )}

          {activeTab === "Kategorije" && (
            <CategoriesTab
              catalog={catalog}
              collections={allCollections}
              enrichment={enrichData}
              initialSettings={extraSettings.categories}
              item={item}
              onAddToCollection={onAddToCollection}
              onReport={(data) => reportSettings("categories", data)}
            />
          )}

          {activeTab === "Prevodi" && (
            <SubtitlesTab
              initialSettings={extraSettings.subtitles}
              item={item}
              onReport={(data) => reportSettings("subtitles", data)}
              sources={sources}
            />
          )}

          {activeTab === "Napredno" && (
            <AdvancedTab
              enrichment={enrichData}
              initialSettings={extraSettings.advanced}
              item={item}
              onDeleteMedia={onDeleteMedia}
              onReport={(data) => reportSettings("advanced", data)}
              sources={sources}
            />
          )}

          <div
            className="filmium-editor-columns"
            hidden={
              activeTab === "Mediji"
              || activeTab === "Fajlovi"
              || activeTab === "Ocene"
              || activeTab === "Kategorije"
              || activeTab === "Prevodi"
              || activeTab === "Epizode"
              || activeTab === "Napredno"
            }
          >
            {/* ----------  LEVA: MEDIJI  ---------- */}

            {showBasic && (
              <section className="filmium-editor-column media">
                <div className="filmium-editor-media-block">
                  <p className="filmium-editor-block-label">
                    POSTER
                    {!hasPoster && <TmdbBadge />}
                  </p>
                  <div className="filmium-editor-poster">
                    {posterUrl ? (
                      <img alt="" src={posterUrl} />
                    ) : (
                      <span>{title || "Poster"}</span>
                    )}
                    <button
                      className="filmium-editor-image-edit"
                      type="button"
                    >
                      <Pencil size={14} />
                    </button>
                  </div>
                  <button
                    className="filmium-editor-block-button"
                    type="button"
                  >
                    <Pencil size={13} />
                    Izmeni poster
                  </button>
                </div>

                <div className="filmium-editor-media-block">
                  <p className="filmium-editor-block-label">
                    BACKDROP
                    {!hasBackdrop && <TmdbBadge />}
                  </p>
                  <div className="filmium-editor-backdrop">
                    {backdropUrl ? (
                      <img alt="" src={backdropUrl} />
                    ) : (
                      <span>Backdrop</span>
                    )}
                    <button
                      className="filmium-editor-image-edit"
                      type="button"
                    >
                      <Pencil size={14} />
                    </button>
                  </div>
                  <button
                    className="filmium-editor-block-button"
                    type="button"
                  >
                    <Pencil size={13} />
                    Izmeni backdrop
                  </button>
                </div>

                <div className="filmium-editor-media-block">
                  <p className="filmium-editor-block-label">
                    WALLPAPER / FANART
                  </p>
                  <div className="filmium-editor-fanart-grid">
                    {[0, 1, 2, 3, 4].map((slot) => (
                      <div
                        className="filmium-editor-fanart-slot"
                        key={slot}
                      >
                        {backdropUrl && (
                          <img alt="" src={backdropUrl} />
                        )}
                      </div>
                    ))}
                    <button
                      className="filmium-editor-fanart-add"
                      type="button"
                    >
                      <Plus size={16} />
                      Dodaj još
                    </button>
                  </div>
                  <button
                    className="filmium-editor-block-button"
                    type="button"
                  >
                    <Pencil size={13} />
                    Dodaj slike
                  </button>
                </div>
              </section>
            )}

            {/* ----------  SREDNJA: INFORMACIJE  ---------- */}

            {showBasic && (
              <section className="filmium-editor-column info">
                <p className="filmium-editor-block-label">INFORMACIJE</p>

                <div className="filmium-sync-row">
                  <span className="filmium-sync-label">
                    {synchronized ? "Sinhronizovano" : "Titlovan"}
                  </span>
                  <button
                    aria-pressed={synchronized}
                    className={`filmium-sync-toggle${
                      synchronized ? " on" : ""
                    }`}
                    onClick={() => setSynchronized((value) => !value)}
                    type="button"
                  >
                    <span className="filmium-sync-knob" />
                    SINH
                  </button>
                </div>

                <Field label="Naslov" required>
                  <input
                    className="filmium-editor-input"
                    onChange={(event) => setTitle(event.target.value)}
                    value={title}
                  />
                </Field>

                <Field label="Originalni naslov" tmdb>
                  <input
                    className={tmdbClass(
                      "originalTitle",
                      "filmium-editor-input",
                    )}
                    onChange={(event) =>
                      setOriginalTitle(event.target.value)}
                    value={originalTitle}
                  />
                </Field>

                <Field label="Engleski naslov" tmdb>
                  <input
                    className={tmdbClass(
                      "englishTitle",
                      "filmium-editor-input",
                    )}
                    onChange={(event) =>
                      setEnglishTitle(event.target.value)}
                    value={englishTitle}
                  />
                </Field>

                <Field label="Domaći naslov (SR / HR / BS)" tmdb>
                  <div className="filmium-editor-field-row">
                    <input
                      className={tmdbClass(
                        "localTitleSr",
                        "filmium-editor-input",
                      )}
                      onChange={(event) =>
                        setLocalTitleSr(event.target.value)}
                      placeholder="Srpski"
                      value={localTitleSr}
                    />
                    <input
                      className="filmium-editor-input"
                      onChange={(event) =>
                        setLocalTitleHr(event.target.value)}
                      placeholder="Hrvatski"
                      value={localTitleHr}
                    />
                    <input
                      className="filmium-editor-input"
                      onChange={(event) =>
                        setLocalTitleBs(event.target.value)}
                      placeholder="Bosanski"
                      value={localTitleBs}
                    />
                  </div>
                </Field>

                <Field label="Tip sadržaja">
                  <select
                    className="filmium-editor-input"
                    onChange={(event) =>
                      setContentType(event.target.value)}
                    value={contentType}
                  >
                    {CONTENT_TYPE_OPTIONS.map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                </Field>

                <Field label="Opis (domaći — SR)" tmdb>
                  <textarea
                    className={tmdbClass(
                      "descriptionLocal",
                      "filmium-editor-input filmium-editor-textarea",
                    )}
                    maxLength={1000}
                    onChange={(event) =>
                      setDescriptionLocal(event.target.value)}
                    rows={4}
                    value={descriptionLocal}
                  />
                  <span className="filmium-editor-counter">
                    {descriptionLocal.length} / 1000
                  </span>
                </Field>

                <Field label="Opis (engleski)" tmdb>
                  <textarea
                    className={tmdbClass(
                      "descriptionEnglish",
                      "filmium-editor-input filmium-editor-textarea",
                    )}
                    maxLength={1000}
                    onChange={(event) =>
                      setDescriptionEnglish(event.target.value)}
                    rows={4}
                    value={descriptionEnglish}
                  />
                  <span className="filmium-editor-counter">
                    {descriptionEnglish.length} / 1000
                  </span>
                </Field>

                <div className="filmium-editor-field-row">
                  <Field label="Godina" tmdb>
                    <div className="filmium-editor-input-icon">
                      <input
                        className={tmdbClass(
                          "year",
                          "filmium-editor-input",
                        )}
                        onChange={(event) => setYear(event.target.value)}
                        value={year}
                      />
                      <CalendarDays size={15} />
                    </div>
                  </Field>

                  <Field label="Datum izlaska" tmdb>
                    <input
                      className="filmium-editor-input"
                      onChange={(event) =>
                        setReleaseDate(event.target.value)}
                      placeholder="DD.MM.GGGG"
                      value={releaseDate}
                    />
                  </Field>

                  <Field label="Trajanje" tmdb>
                    <div className="filmium-editor-input-icon">
                      <input
                        className={tmdbClass(
                          "runtime",
                          "filmium-editor-input",
                        )}
                        onChange={(event) =>
                          setRuntime(event.target.value)}
                        value={runtime}
                      />
                      <Clock size={15} />
                    </div>
                  </Field>
                </div>

                <div className="filmium-editor-field-row">
                  <Field label="Studio" tmdb>
                    <input
                      className={tmdbClass("studio", "filmium-editor-input")}
                      onChange={(event) => setStudio(event.target.value)}
                      value={studio}
                    />
                  </Field>

                  <Field label="Režiser" tmdb>
                    <input
                      className={tmdbClass(
                        "director",
                        "filmium-editor-input",
                      )}
                      onChange={(event) =>
                        setDirector(event.target.value)}
                      value={director}
                    />
                  </Field>
                </div>

                <Field label="Glumci" tmdb>
                  <TagList
                    highlight={tmdbFilled.has("cast")}
                    onChange={setCast}
                    values={cast}
                  />
                </Field>

                <div className="filmium-editor-field-row">
                  <Field label="Status gledanja">
                    <select
                      className="filmium-editor-input"
                      onChange={(event) =>
                        setWatchStatus(event.target.value)}
                      value={watchStatus}
                    >
                      {WATCH_STATUS_OPTIONS.map((option) => (
                        <option key={option} value={option}>
                          {option}
                        </option>
                      ))}
                    </select>
                  </Field>

                  <Field label="Prioritet gledanja">
                    <select
                      className="filmium-editor-input"
                      onChange={(event) =>
                        setWatchPriority(event.target.value)}
                      value={watchPriority}
                    >
                      {WATCH_PRIORITY_OPTIONS.map((option) => (
                        <option key={option} value={option}>
                          {option}
                        </option>
                      ))}
                    </select>
                  </Field>
                </div>

                <Field label="Lična napomena">
                  <textarea
                    className="filmium-editor-input filmium-editor-textarea"
                    onChange={(event) =>
                      setPersonalNote(event.target.value)}
                    rows={2}
                    value={personalNote}
                  />
                </Field>
              </section>
            )}

            {/* ----------  DESNA: TEHNIKA / OCENE / KATEGORIJE  ---------- */}

            {showBasic && (
              <section className="filmium-editor-column tech">
                {showBasic && (
                  <div className="filmium-editor-card">
                    <p className="filmium-editor-block-label">
                      TEHNIČKE INFORMACIJE
                    </p>
                    <InfoRow
                      label="Rezolucija"
                      onChange={setResolution}
                      value={resolution}
                    />
                    <InfoRow
                      label="Format"
                      onChange={setFormat}
                      value={format}
                    />
                    <InfoRow
                      label="Video codec"
                      onChange={setVideoCodec}
                      value={videoCodec}
                    />
                    <InfoRow
                      label="Audio codec"
                      onChange={setAudioCodec}
                      value={audioCodec}
                    />
                    <InfoRow
                      label="Audio jezici"
                      onChange={setAudioLanguages}
                      value={audioLanguages}
                    />
                    <InfoRow
                      label="Veličina"
                      onChange={setFileSize}
                      value={fileSize}
                    />
                    <InfoRow
                      label="Bitrate"
                      onChange={setBitrate}
                      value={bitrate}
                    />
                    <InfoRow label="FPS" onChange={setFps} value={fps} />
                    <InfoRow label="HDR" onChange={setHdr} value={hdr} />
                    <InfoRow
                      label="Putanja fajla"
                      onChange={setFilePath}
                      value={filePath}
                    />
                    <InfoRow
                      label="Izvor"
                      onChange={setSourceLabel}
                      value={sourceLabel}
                    />
                  </div>
                )}

                {showBasic && (
                  <div className="filmium-editor-card">
                    <p className="filmium-editor-block-label">OCENE</p>
                    <div className="filmium-editor-rating-row">
                      <span>
                        <Star size={14} /> Moja ocena
                      </span>
                      <input
                        className="filmium-editor-info-input"
                        onChange={(event) =>
                          setMyRating(event.target.value)}
                        value={myRating}
                      />
                    </div>
                    <InfoRow
                      label="IMDb"
                      onChange={setImdb}
                      tmdb
                      value={imdb}
                    />
                    <InfoRow
                      label="TMDB"
                      onChange={setTmdb}
                      tmdb
                      value={tmdb}
                    />
                    <InfoRow
                      label="Rotten Tomatoes"
                      onChange={setRotten}
                      value={rotten}
                    />
                    <InfoRow
                      label="Metacritic"
                      onChange={setMetacritic}
                      value={metacritic}
                    />
                    <div className="filmium-editor-rating-row">
                      <span>
                        <Users size={14} /> Publika
                        <TmdbBadge />
                      </span>
                      <input
                        className="filmium-editor-info-input"
                        onChange={(event) =>
                          setAudience(event.target.value)}
                        value={audience}
                      />
                    </div>
                    <InfoRow
                      label="Kritika"
                      onChange={setCritics}
                      value={critics}
                    />
                  </div>
                )}

                {showBasic && (
                  <div className="filmium-editor-card">
                    <p className="filmium-editor-block-label">
                      KATEGORIJE / OZNAKE
                    </p>
                    <Field label="Žanrovi" tmdb>
                      <TagList
                        highlight={tmdbFilled.has("genres")}
                        onChange={setGenres}
                        values={genres}
                      />
                    </Field>
                    <Field label="Kolekcije">
                      <TagList
                        onChange={setCollections}
                        values={collections}
                      />
                    </Field>
                    <Field label="Liste">
                      <TagList onChange={setLists} values={lists} />
                    </Field>
                    <Field label="Ključne reči" tmdb>
                      <TagList
                        highlight={tmdbFilled.has("keywords")}
                        onChange={setKeywords}
                        values={keywords}
                      />
                    </Field>
                  </div>
                )}
              </section>
            )}
          </div>

          {/* ==========          PREVODI          ========== */}

          {showBasic && (
            <section className="filmium-editor-translations">
              <p className="filmium-editor-block-label">PREVODI</p>
              <div className="filmium-editor-field-row">
                <Field label="Srpski titl">
                  <input
                    className="filmium-editor-input"
                    onChange={(event) =>
                      setSrSubtitle(event.target.value)}
                    placeholder="npr. Film.sr.srt"
                    value={srSubtitle}
                  />
                </Field>
                <Field label="Engleski titl">
                  <input
                    className="filmium-editor-input"
                    onChange={(event) =>
                      setEnSubtitle(event.target.value)}
                    placeholder="npr. Film.en.srt"
                    value={enSubtitle}
                  />
                </Field>
                <Field label="Format titla">
                  <select
                    className="filmium-editor-input"
                    onChange={(event) =>
                      setSubtitleFormat(event.target.value)}
                    value={subtitleFormat}
                  >
                    {SUBTITLE_FORMAT_OPTIONS.map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Verzija titla">
                  <input
                    className="filmium-editor-input"
                    onChange={(event) =>
                      setSubtitleVersion(event.target.value)}
                    value={subtitleVersion}
                  />
                </Field>
              </div>

              <div className="filmium-editor-toggle-row">
                <label className="filmium-editor-toggle">
                  <input
                    checked={embeddedSubtitle}
                    onChange={(event) =>
                      setEmbeddedSubtitle(event.target.checked)}
                    type="checkbox"
                  />
                  Ugrađen titl
                </label>
                <label className="filmium-editor-toggle">
                  <input
                    checked={externalSubtitle}
                    onChange={(event) =>
                      setExternalSubtitle(event.target.checked)}
                    type="checkbox"
                  />
                  Eksterni titl
                </label>
                <label className="filmium-editor-toggle">
                  <input
                    checked={dubbing}
                    onChange={(event) => setDubbing(event.target.checked)}
                    type="checkbox"
                  />
                  Sinhronizacija
                </label>
              </div>
            </section>
          )}

          {/* ==========          SEZONE I EPIZODE          ========== */}

          {activeTab === "Epizode" && (
            <EpisodesTab
              enrichment={enrichData}
              item={item}
              onEditSubtitle={() => {
                if (onOpenSubtitleTool) {
                  onOpenSubtitleTool();
                } else {
                  setSubtitleToolOpen(true);
                }
              }}
              seasons={seasons}
              sources={sources}
            />
          )}

          {showBasic && (
            <section className="filmium-editor-series">
              <div className="filmium-editor-series-head">
                <div>
                  <p className="filmium-editor-block-label">
                    AKO JE SERIJA (OPCIONO)
                  </p>
                  <label className="filmium-editor-toggle">
                    <input
                      checked={isSeries}
                      onChange={(event) =>
                        setIsSeries(event.target.checked)}
                      type="checkbox"
                    />
                    Ovo je serija
                  </label>
                </div>

                {isSeries && (
                  <div className="filmium-editor-series-actions">
                    <button
                      className="filmium-editor-button ghost small"
                      onClick={() =>
                        setEditingEpisode({
                          id: -Date.now(),
                          seasonNumber: activeSeason,
                          episodeNumber:
                            episodeDrafts.filter(
                              (draft) =>
                                draft.seasonNumber === activeSeason,
                            ).length + 1,
                          title: "",
                          runtimeMinutes: null,
                          status: "planned",
                        })}
                      type="button"
                    >
                      <Plus size={14} />
                      Dodaj epizodu
                    </button>
                    <button
                      className="filmium-editor-button ghost small"
                      type="button"
                    >
                      <UploadCloud size={14} />
                      Uvezi epizode
                    </button>
                  </div>
                )}
              </div>

              {isSeries && (
                <div className="filmium-editor-series-grid">
                  <div className="filmium-editor-season-list">
                    <p className="filmium-editor-mini-label">SEZONE</p>
                    {seasons.map((season) => (
                      <button
                        className={`filmium-editor-season${
                          activeSeason === season.season_number
                            ? " active"
                            : ""
                        }`}
                        key={season.id}
                        onClick={() =>
                          setActiveSeason(season.season_number)}
                        type="button"
                      >
                        <span>
                          {season.name
                            ?? `Sezona ${season.season_number}`}
                        </span>
                        <span className="filmium-editor-season-count">
                          {season.episodes.length} epizoda
                        </span>
                      </button>
                    ))}
                    <button
                      className="filmium-editor-button ghost small full"
                      type="button"
                    >
                      <Plus size={14} />
                      Dodaj sezonu
                    </button>
                  </div>

                  <div className="filmium-editor-episode-table">
                    <p className="filmium-editor-mini-label">
                      EPIZODE — SEZONA {activeSeason}
                    </p>
                    <table>
                      <thead>
                        <tr>
                          <th />
                          <th>Ep</th>
                          <th>Naslov</th>
                          <th>Trajanje</th>
                          <th>Datum</th>
                          <th>Rezolucija</th>
                          <th>Titl</th>
                          <th>Status</th>
                          <th>Akcije</th>
                        </tr>
                      </thead>
                      <tbody>
                        {episodeDrafts
                          .filter(
                            (draft) =>
                              draft.seasonNumber === activeSeason,
                          )
                          .map((draft) => (
                            <tr key={draft.id}>
                              <td className="drag">
                                <GripVertical size={14} />
                              </td>
                              <td>{draft.episodeNumber}</td>
                              <td>
                                {draft.title
                                  || `Epizoda ${draft.episodeNumber}`}
                              </td>
                              <td>
                                {draft.runtimeMinutes
                                  ? `${draft.runtimeMinutes}m`
                                  : "—"}
                              </td>
                              <td>—</td>
                              <td>{resolution}</td>
                              <td>SR</td>
                              <td>
                                <span className="filmium-editor-status-pill">
                                  {draft.status}
                                </span>
                              </td>
                              <td>
                                <button
                                  className="filmium-editor-row-edit"
                                  onClick={() =>
                                    setEditingEpisode(draft)}
                                  type="button"
                                >
                                  <Pencil size={13} />
                                  Uredi
                                </button>
                              </td>
                            </tr>
                          ))}

                        {episodeDrafts.filter(
                          (draft) =>
                            draft.seasonNumber === activeSeason,
                        ).length === 0 && (
                          <tr>
                            <td className="empty" colSpan={9}>
                              Nema epizoda u ovoj sezoni.
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </section>
          )}
        </div>
      </aside>

      {/* ==========          EPISODE EDITOR (MODAL)          ========== */}

      {editingEpisode && (
        <EpisodeEditorModal
          episode={editingEpisode}
          onClose={() => setEditingEpisode(null)}
        />
      )}

      {/* ==========          TERMINATOR PREVODA (DRAWER)          ========== */}

      {subtitleToolOpen && (
        <div
          className="filmium-subtool-overlay"
          onClick={() => setSubtitleToolOpen(false)}
          role="presentation"
        >
          <aside
            className="filmium-subtool-panel"
            onClick={(event) => event.stopPropagation()}
            role="dialog"
          >
            <header className="filmium-subtool-head">
              <div className="filmium-editor-header-title">
                <span className="filmium-editor-header-icon">
                  <Languages size={18} />
                </span>
                <div>
                  <h2>Terminator prevoda</h2>
                  <p>{item.title}</p>
                </div>
              </div>
              <button
                className="filmium-editor-button ghost"
                onClick={() => setSubtitleToolOpen(false)}
                type="button"
              >
                <X size={16} />
                Zatvori
              </button>
            </header>

            <div className="filmium-subtool-body">
              <FilmiumSubtitleRepairPanel />
              <p className="filmium-media-empty">
                Ako lista nije prikazana, prevodi još nisu skenirani —
                pokreni „Skeniraj automatski" u tabu Prevodi ili uvezi
                titlove, pa se vrati ovde.
              </p>
            </div>
          </aside>
        </div>
      )}
    </div>,
    document.body,
  );
}


// ==========          NAPREDNO TAB          ==========

type AdvancedTabProps = {
  item: MediaItem;
  sources: FilmiumMediaSource[];
  enrichment: FilmiumTmdbEnrichment | null;
  onDeleteMedia?: () => void;
  initialSettings?: unknown;
  onReport?: (data: unknown) => void;
};

/**
 * Pravi slug iz naslova i godine.
 */
function slugify(title: string, year: number | null): string {
  const base = title
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");
  return year ? `${base}-${year}` : base;
}

/**
 * „Napredno" tab: identitet metapodataka, integracije, automatizacija,
 * održavanje, backup i opasne akcije.
 *
 * ID-evi/jezik/zemlja iz TMDB-a, statusi integracija i sistemski status iz
 * stvarnih izvora. Akcije su povezane gde backend postoji (osveži, rescan,
 * export, brisanje slika, brisanje sadržaja).
 */
function AdvancedTab({
  item,
  sources,
  enrichment,
  onDeleteMedia,
  initialSettings,
  onReport,
}: AdvancedTabProps) {
  const saved = (initialSettings ?? {}) as {
    imdbId?: string;
    tvdbId?: string;
    metaStatus?: string;
    checkFreq?: string;
    automation?: Record<string, boolean>;
    access?: Record<string, boolean>;
  };
  const [tmdbId, setTmdbId] = useState<number | null>(
    enrichment?.tmdb_id ?? null,
  );
  const [origLang, setOrigLang] = useState(
    enrichment?.original_language
      ? languageLabel(enrichment.original_language)
      : "",
  );
  const [country, setCountry] = useState(enrichment?.country ?? "");
  const [imdbId, setImdbId] = useState(saved.imdbId ?? "");
  const [tvdbId, setTvdbId] = useState(saved.tvdbId ?? "");
  const [metaStatus, setMetaStatus] = useState(
    saved.metaStatus ?? "Sinhronizovano",
  );
  const [visibility, setVisibility] = useState("Privatno");
  const [ageRec, setAgeRec] = useState("13+");
  const [checkFreq, setCheckFreq] = useState(
    saved.checkFreq ?? "Nedeljno",
  );
  const [automation, setAutomation] = useState<Record<string, boolean>>(
    () =>
      saved.automation ?? {
        metadata: true,
        posters: true,
        files: true,
        subtitles: true,
        thumbnails: true,
        recommend: false,
      },
  );
  const [access, setAccess] = useState<Record<string, boolean>>(
    () =>
      saved.access ?? {
        library: true,
        recommend: true,
        export: true,
        lock: false,
        hidePublic: false,
      },
  );
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);

  // Prijavi stanje panelu za snimanje (editor_settings.advanced).
  useEffect(() => {
    onReport?.({
      imdbId,
      tvdbId,
      metaStatus,
      checkFreq,
      automation,
      access,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [imdbId, tvdbId, metaStatus, checkFreq, automation, access]);

  function applyEnrich(data: FilmiumTmdbEnrichment): void {
    if (!data.matched) {
      return;
    }
    if (data.tmdb_id) {
      setTmdbId(data.tmdb_id);
    }
    if (data.original_language) {
      setOrigLang(languageLabel(data.original_language));
    }
    if (data.country) {
      setCountry(data.country);
    }
  }

  // Rezultat „Dopuni preko TMDB" se primenjuje TOKOM crtanja, čim stigne nov —
  // to je React-ov obrazac za podešavanje stanja po promeni props-a. Efekat bi
  // ovde značio jedan crtež sa starim poljima pa drugi sa dopunjenim, a polja
  // su ista ona koja čovek u tom trenutku možda već kuca.
  const [primenjenoObogacenje, setPrimenjenoObogacenje] =
    useState<FilmiumTmdbEnrichment | null>(null);

  if (enrichment && enrichment !== primenjenoObogacenje) {
    setPrimenjenoObogacenje(enrichment);
    applyEnrich(enrichment);
  }

  useEffect(() => {
    let active = true;
    enrichFilmiumMediaFromTmdb(item.id)
      .then((data) => {
        if (active) {
          applyEnrich(data);
        }
      })
      .catch(() => {
        /* tolerantno */
      });
    return () => {
      active = false;
    };
  }, [item.id]);

  const allFiles = sources.flatMap((source) => source.files);
  const hasVideo = allFiles.some((file) => file.role === "video");
  const hasSubtitle = allFiles.some((file) => file.role === "subtitle");
  const hasTrailer = allFiles.some((file) => file.role === "trailer");
  const hasImage = item.poster_path !== null || item.backdrop_path !== null;

  async function runAction(
    label: string,
    action: () => Promise<void>,
  ): Promise<void> {
    setBusy(true);
    setStatus(null);
    try {
      await action();
    } catch (error) {
      setStatus(
        error instanceof Error ? error.message : `${label} nije uspelo.`,
      );
    } finally {
      setBusy(false);
    }
  }

  function refreshMetadata(): void {
    void runAction("Osvežavanje metapodataka", async () => {
      applyEnrich(await enrichFilmiumMediaFromTmdb(item.id));
      setStatus("Metapodaci osveženi sa TMDB-a.");
    });
  }

  function rescanContent(): void {
    const sourceId = sources[0]?.id;
    if (sourceId === undefined) {
      setStatus("Nema registrovanog izvora za rescan.");
      return;
    }
    void runAction("Rescan", async () => {
      await rescanFilmiumMediaSource(sourceId);
      setStatus("Sadržaj ponovo skeniran.");
    });
  }

  function exportJson(): void {
    const payload = {
      id: item.id,
      title: item.title,
      original_title: item.original_title,
      media_type: item.media_type,
      release_year: item.release_year,
      runtime_minutes: item.runtime_minutes,
      watch_status: item.watch_status,
      rating: item.rating,
      notes: item.notes,
      genres: item.genres,
      content_category: item.content_category ?? "regular",
      cast_names: item.cast_names ?? [],
      is_favorite: item.is_favorite,
      tmdb_id: tmdbId,
      imdb_id: imdbId || null,
      created_at: item.created_at,
      updated_at: item.updated_at,
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${slugify(item.title, item.release_year)}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
    setStatus("JSON izvezen.");
  }

  function removeAllImages(): void {
    void runAction("Uklanjanje slika", async () => {
      if (item.poster_path) {
        await deleteFilmiumMediaAsset(item.id, "poster");
      }
      if (item.backdrop_path) {
        await deleteFilmiumMediaAsset(item.id, "backdrop");
      }
      setStatus("Slike uklonjene.");
    });
  }

  function deleteMedia(): void {
    if (
      !window.confirm(
        `Obrisati „${item.title}" iz biblioteke? Ovo se ne može lako `
        + "poništiti.",
      )
    ) {
      return;
    }
    void runAction("Brisanje sadržaja", async () => {
      await deleteFilmiumMediaItem(item.id);
      setStatus("Sadržaj obrisan.");
      onDeleteMedia?.();
    });
  }

  const integrations = [
    {
      name: "TMDB",
      connected: tmdbId !== null,
      label: tmdbId !== null ? "Povezano" : "Nije povezano",
    },
    { name: "IMDb", connected: imdbId !== "", label: "Ručni unos" },
    { name: "OpenSubtitles", connected: false, label: "Onemogućeno" },
    {
      name: "Lokalni folder",
      connected: sources.length > 0,
      label: sources.length > 0 ? "Povezano" : "Nedostaje",
    },
    {
      name: "Trailer izvor",
      connected: hasTrailer,
      label: hasTrailer ? "Povezano" : "Nedostaje",
    },
  ];

  const systemChecks = [
    { label: "Baza OK", ok: true },
    { label: "Fajl postoji", ok: hasVideo },
    { label: "Slike učitane", ok: hasImage },
    { label: "Titlovi povezani", ok: hasSubtitle },
    { label: "Trailer izvor", ok: hasTrailer },
  ];

  const auditLog = [
    {
      time: formatEditorDate(item.updated_at) ?? "—",
      action: "Poslednja izmena",
      user: "system",
    },
    {
      time: formatEditorDate(item.created_at) ?? "—",
      action: "Sadržaj dodat u katalog",
      user: "system",
    },
  ];

  return (
    <section className="filmium-adv-tab">
      {status && (
        <p className="filmium-editor-enrich-message">{status}</p>
      )}

      {/* ----------  STAT ČIPOVI  ---------- */}

      <div className="filmium-ratings-stats">
        <RatingStat label="METADATA" value={metaStatus} />
        <RatingStat
          label="TMDB ID"
          value={tmdbId !== null ? String(tmdbId) : "—"}
        />
        <RatingStat label="IMDb ID" value={imdbId || "—"} />
        <RatingStat
          label="AUTOMATIKA"
          value={
            Object.values(automation).some(Boolean) ? "Aktivna" : "—"
          }
        />
        <RatingStat label="INTERNI ID" value={String(item.id)} />
        <RatingStat label="VIDLJIVOST" value={visibility} />
      </div>

      <div className="filmium-adv-body">
        {/* ==========  LEVA KOLONA  ========== */}

        <div className="filmium-adv-col">
          <div className="filmium-editor-card">
            <p className="filmium-editor-block-label">METADATA IDENTITET</p>
            <div className="filmium-adv-id-grid">
              <Field label="Interni ID">
                <input
                  className="filmium-editor-input"
                  readOnly
                  value={`film_${String(item.id).padStart(6, "0")}`}
                />
              </Field>
              <Field label="Originalni jezik" tmdb>
                <input
                  className={
                    origLang
                      ? "filmium-editor-input tmdb-filled"
                      : "filmium-editor-input"
                  }
                  onChange={(event) => setOrigLang(event.target.value)}
                  value={origLang}
                />
              </Field>
              <Field label="Slug">
                <input
                  className="filmium-editor-input"
                  readOnly
                  value={slugify(item.title, item.release_year)}
                />
              </Field>
              <Field label="Zemlja" tmdb>
                <input
                  className={
                    country
                      ? "filmium-editor-input tmdb-filled"
                      : "filmium-editor-input"
                  }
                  onChange={(event) => setCountry(event.target.value)}
                  value={country}
                />
              </Field>
              <Field label="TMDB ID" tmdb>
                <input
                  className={
                    tmdbId !== null
                      ? "filmium-editor-input tmdb-filled"
                      : "filmium-editor-input"
                  }
                  readOnly
                  value={tmdbId !== null ? String(tmdbId) : ""}
                />
              </Field>
              <Field label="Godina">
                <input
                  className="filmium-editor-input"
                  readOnly
                  value={item.release_year ?? ""}
                />
              </Field>
              <Field label="IMDb ID">
                <input
                  className="filmium-editor-input"
                  onChange={(event) => setImdbId(event.target.value)}
                  placeholder="tt…"
                  value={imdbId}
                />
              </Field>
              <Field label="Status metadata">
                <select
                  className="filmium-editor-input"
                  onChange={(event) => setMetaStatus(event.target.value)}
                  value={metaStatus}
                >
                  {["Sinhronizovano", "Zastarelo", "Ručno"].map(
                    (option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ),
                  )}
                </select>
              </Field>
              <Field label="TVDB ID">
                <input
                  className="filmium-editor-input"
                  onChange={(event) => setTvdbId(event.target.value)}
                  value={tvdbId}
                />
              </Field>
            </div>
            <div className="filmium-files-actions">
              <button
                className="filmium-editor-button primary small"
                disabled={busy}
                onClick={refreshMetadata}
                type="button"
              >
                <RefreshCw size={13} />
                Osveži metadata
              </button>
              <button
                className="filmium-editor-button ghost small"
                onClick={() =>
                  setStatus("Ručno povezivanje: unesi TMDB/IMDb ID.")}
                type="button"
              >
                <Link2 size={13} />
                Poveži ručno
              </button>
            </div>
          </div>

          <div className="filmium-editor-card">
            <p className="filmium-editor-block-label">
              INTEGRACIJE I IZVORI
            </p>
            <div className="filmium-adv-integrations">
              {integrations.map((integration) => (
                <div
                  className="filmium-adv-integration"
                  key={integration.name}
                >
                  <span
                    className={`filmium-adv-dot ${
                      integration.connected ? "on" : "off"
                    }`}
                  />
                  <span className="filmium-adv-int-name">
                    {integration.name}
                  </span>
                  <span className="filmium-adv-int-label">
                    {integration.label}
                  </span>
                </div>
              ))}
            </div>
          </div>

          <div className="filmium-editor-card">
            <p className="filmium-editor-block-label">AUDIT LOG</p>
            <div className="filmium-editor-episode-table">
              <table>
                <thead>
                  <tr>
                    <th>Vreme</th>
                    <th>Akcija</th>
                    <th>Korisnik</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {auditLog.map((entry) => (
                    <tr key={entry.action}>
                      <td>{entry.time}</td>
                      <td>{entry.action}</td>
                      <td>{entry.user}</td>
                      <td>
                        <span className="filmium-files-status available">
                          Uspešno
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* ==========  SREDNJA KOLONA  ========== */}

        <div className="filmium-adv-col">
          <div className="filmium-editor-card">
            <p className="filmium-editor-block-label">AUTOMATIZACIJA</p>
            <RatingToggle
              checked={automation.metadata ?? false}
              label="Automatski osveži metadata"
              onChange={(value) =>
                setAutomation((prev) => ({ ...prev, metadata: value }))}
            />
            <RatingToggle
              checked={automation.posters ?? false}
              label="Automatski pronađi postere"
              onChange={(value) =>
                setAutomation((prev) => ({ ...prev, posters: value }))}
            />
            <RatingToggle
              checked={automation.files ?? false}
              label="Automatski skeniraj fajlove"
              onChange={(value) =>
                setAutomation((prev) => ({ ...prev, files: value }))}
            />
            <RatingToggle
              checked={automation.subtitles ?? false}
              label="Automatski poveži titlove"
              onChange={(value) =>
                setAutomation((prev) => ({ ...prev, subtitles: value }))}
            />
            <RatingToggle
              checked={automation.thumbnails ?? false}
              label="Automatski generiši thumbnailove"
              onChange={(value) =>
                setAutomation((prev) => ({ ...prev, thumbnails: value }))}
            />
            <RatingToggle
              checked={automation.recommend ?? false}
              label="Automatski dodaj u preporuke"
              onChange={(value) =>
                setAutomation((prev) => ({ ...prev, recommend: value }))}
            />
            <Field label="Učestalost provere">
              <select
                className="filmium-editor-input"
                onChange={(event) => setCheckFreq(event.target.value)}
                value={checkFreq}
              >
                {["Dnevno", "Nedeljno", "Mesečno", "Ručno"].map(
                  (option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ),
                )}
              </select>
            </Field>
            <button
              className="filmium-editor-button tmdb full"
              onClick={() =>
                setStatus("Automatike se izvršavaju u pozadini.")}
              type="button"
            >
              <Play size={14} />
              Pokreni sve automatike
            </button>
          </div>

          <div className="filmium-editor-card">
            <p className="filmium-editor-block-label">VIDLJIVOST I PRISTUP</p>
            <Field label="Vidljivost">
              <select
                className="filmium-editor-input"
                onChange={(event) => setVisibility(event.target.value)}
                value={visibility}
              >
                <option value="Privatno">Privatno</option>
                <option value="Javno">Javno</option>
              </select>
            </Field>
            <RatingToggle
              checked={access.library ?? false}
              label="Prikaži u biblioteci"
              onChange={(value) =>
                setAccess((prev) => ({ ...prev, library: value }))}
            />
            <RatingToggle
              checked={access.recommend ?? false}
              label="Prikaži u preporukama"
              onChange={(value) =>
                setAccess((prev) => ({ ...prev, recommend: value }))}
            />
            <RatingToggle
              checked={access.export ?? false}
              label="Dozvoli export"
              onChange={(value) =>
                setAccess((prev) => ({ ...prev, export: value }))}
            />
            <RatingToggle
              checked={access.lock ?? false}
              label="Zaključaj ručne izmene"
              onChange={(value) =>
                setAccess((prev) => ({ ...prev, lock: value }))}
            />
            <RatingToggle
              checked={access.hidePublic ?? false}
              label="Sakrij iz javnih lista"
              onChange={(value) =>
                setAccess((prev) => ({ ...prev, hidePublic: value }))}
            />
            <Field label="Starosna preporuka">
              <select
                className="filmium-editor-input"
                onChange={(event) => setAgeRec(event.target.value)}
                value={ageRec}
              >
                {["Bez ograničenja", "7+", "13+", "16+", "18+"].map(
                  (option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ),
                )}
              </select>
            </Field>
          </div>

          <div className="filmium-editor-card filmium-adv-danger">
            <p className="filmium-editor-block-label">OPASNE AKCIJE</p>
            <p className="filmium-adv-danger-note">
              <TriangleAlert size={14} />
              Ove akcije ne mogu lako da se ponište.
            </p>
            <button
              className="filmium-editor-button danger full"
              disabled={busy || !onDeleteMedia}
              onClick={deleteMedia}
              type="button"
            >
              <Trash2 size={14} />
              Obriši iz biblioteke
            </button>
            <button
              className="filmium-editor-button danger full"
              disabled={busy || !hasImage}
              onClick={removeAllImages}
              type="button"
            >
              <ImageIcon size={14} />
              Ukloni sve slike
            </button>
            <button
              className="filmium-editor-button danger full"
              onClick={() =>
                setStatus(
                  "Reset metapodataka zahteva potvrdu — koristi „Osveži "
                  + "metadata" + "\".",
                )}
              type="button"
            >
              <RefreshCw size={14} />
              Resetuj metadata
            </button>
          </div>
        </div>

        {/* ==========  DESNA KOLONA  ========== */}

        <div className="filmium-adv-col">
          <div className="filmium-editor-card">
            <p className="filmium-editor-block-label">ODRŽAVANJE</p>
            <button
              className="filmium-editor-button ghost full"
              disabled={busy}
              onClick={rescanContent}
              type="button"
            >
              <RefreshCw size={14} />
              Rescan sadržaja
            </button>
            <button
              className="filmium-editor-button ghost full"
              onClick={() =>
                setStatus(
                  "Rebuild thumbnailova: pokreće se pri rescan-u epizoda.",
                )}
              type="button"
            >
              <ImageIcon size={14} />
              Rebuild thumbnailova
            </button>
            <button
              className="filmium-editor-button ghost full"
              disabled={busy}
              onClick={rescanContent}
              type="button"
            >
              <Folder size={14} />
              Proveri putanje
            </button>
            <button
              className="filmium-editor-button ghost full"
              onClick={refreshMetadata}
              type="button"
            >
              <Pencil size={14} />
              Popravi metadata
            </button>
          </div>

          <div className="filmium-editor-card">
            <p className="filmium-editor-block-label">BACKUP I VERZIJE</p>
            <button
              className="filmium-editor-button ghost full"
              onClick={exportJson}
              type="button"
            >
              <Download size={14} />
              Export JSON
            </button>
            <button
              className="filmium-editor-button ghost full"
              onClick={() =>
                setStatus("Backup/verzionisanje se dodaje uz istoriju.")}
              type="button"
            >
              <ExternalLink size={14} />
              Napravi backup
            </button>
          </div>

          <div className="filmium-editor-card">
            <p className="filmium-editor-block-label">SISTEMSKI STATUS</p>
            <div className="filmium-adv-status-list">
              {systemChecks.map((check) => (
                <span
                  className={`filmium-files-check${
                    check.ok ? " ok" : " warn"
                  }`}
                  key={check.label}
                >
                  {check.ok ? (
                    <Check size={15} />
                  ) : (
                    <TriangleAlert size={15} />
                  )}
                  {check.label}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}


// ==========          EPIZODE TAB          ==========

type EpisodesTabProps = {
  item: MediaItem;
  sources: FilmiumMediaSource[];
  seasons: FilmiumSeason[];
  enrichment: FilmiumTmdbEnrichment | null;
  onEditSubtitle: () => void;
};

const EPISODE_STATUS_SR: Record<string, string> = {
  planned: "Planirano",
  watching: "Gledam",
  completed: "Pogledano",
  paused: "Pauzirano",
  dropped: "Napušteno",
};

/**
 * „YYYY-MM-DD" → „DD.MM.YYYY".
 */
function formatAirDate(value: string | null): string {
  if (!value) {
    return "—";
  }
  const parts = value.split("-");
  if (parts.length !== 3) {
    return value;
  }
  return `${parts[2]}.${parts[1]}.${parts[0]}`;
}

/**
 * „Epizode" tab: sezone, tabela epizoda i detalji epizode.
 *
 * Sve iz stvarnih podataka: epizode iz kataloga, sličice + tehnički podaci
 * (rezolucija/codec/veličina) iz ffprobe-a, a datum/opis/originalni naziv/
 * ocena iz TMDB-a (kada je serija upar­ena).
 */
function EpisodesTab({
  item,
  sources,
  seasons,
  enrichment,
  onEditSubtitle,
}: EpisodesTabProps) {
  // Lokalne izmene (gledano/nije) pamte se UZ spisak sezona od koga su krenule.
  // Kad roditelj donese nov spisak, ključ se razlikuje i prikaz je njegov —
  // bez upisa iz efekta, koji je značio jedan kadar sa sezonama prethodnog
  // naslova.
  const [izmenjeneSezone, setIzmenjeneSezone] = useState<{
    osnova: FilmiumSeason[];
    sezone: FilmiumSeason[];
  } | null>(null);

  const localSeasons = izmenjeneSezone?.osnova === seasons
    ? izmenjeneSezone.sezone
    : seasons;

  const setLocalSeasons = useCallback(
    (izmena: (prethodne: FilmiumSeason[]) => FilmiumSeason[]) => {
      setIzmenjeneSezone((staro) => ({
        osnova: seasons,
        sezone: izmena(
          staro?.osnova === seasons ? staro.sezone : seasons,
        ),
      }));
    },
    [seasons],
  );

  const [activeSeasonId, setActiveSeasonId] = useState<number | null>(
    seasons[0]?.id ?? null,
  );
  const [selectedEpisodeId, setSelectedEpisodeId] =
    useState<number | null>(null);
  // Sve troje nosi oznaku upita kome pripada, pa se prazno stanje IZVODI pri
  // crtanju: dok stigne odgovor za novu sezonu ili epizodu, prikaz nije podatak
  // prethodne. Ranije su ta brisanja bila upisi iz efekta — dodatni crtež, a
  // između njih se video tuđ podatak.
  const [ucitanTech, setTech] = useState<{
    kljuc: string;
    tech: FilmiumTechnical | null;
  } | null>(null);
  const [ucitaneTmdbEpizode, setTmdbEpisodes] = useState<{
    kljuc: string;
    epizode: FilmiumEpisodeMetadata[];
  } | null>(null);
  // `tmdb_id` iz zajedničkog obogaćivanja ima prednost; sopstveni upit je
  // rezerva kad ga tamo nema.
  const [sopstveniTmdbId, setTmdbId] = useState<number | null>(null);
  const tmdbId = enrichment?.tmdb_id ?? sopstveniTmdbId;
  const [sortAsc, setSortAsc] = useState(true);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);

  const replaceInputRef = useRef<HTMLInputElement>(null);

  const activeSeason =
    localSeasons.find((season) => season.id === activeSeasonId)
    ?? localSeasons[0]
    ?? null;

  const episodes = useMemo(() => {
    const list = [...(activeSeason?.episodes ?? [])];
    list.sort((first, second) =>
      sortAsc
        ? first.episode_number - second.episode_number
        : second.episode_number - first.episode_number,
    );
    return list;
  }, [activeSeason, sortAsc]);

  const selectedEpisode =
    episodes.find((episode) => episode.id === selectedEpisodeId)
    ?? episodes[0]
    ?? null;

  // Ključevi upita: po njima se zna da li učitan podatak pripada baš ovoj
  // sezoni odnosno epizodi.
  const kljucSezone = `${item.id}|${tmdbId ?? ""}|${activeSeason?.season_number ?? ""}`;
  const kljucEpizode = `${item.id}|${selectedEpisode?.root_id ?? ""}|${selectedEpisode?.video_source ?? ""}`;

  const tmdbEpisodes = ucitaneTmdbEpizode?.kljuc === kljucSezone
    ? ucitaneTmdbEpizode.epizode
    : [];
  const tech = ucitanTech?.kljuc === kljucEpizode ? ucitanTech.tech : null;

  // Veličina fajla i titlovi po epizodi iz registrovanih izvora.
  const fileIndex = useMemo(() => {
    const sizeByPath = new Map<string, number>();
    const subsByKey = new Map<string, string[]>();
    for (const source of sources) {
      for (const file of source.files) {
        const rootRelative = joinPath(
          source.relative_directory,
          file.relative_path,
        );
        if (file.role === "video") {
          sizeByPath.set(rootRelative, file.size_bytes);
        }
        if (file.role === "subtitle") {
          const seasonMatch = /Sezona\s*(\d+)/i.exec(file.relative_path);
          const episodeMatch = /E(\d+)/i.exec(file.relative_path);
          if (seasonMatch && episodeMatch) {
            const key = `${Number(seasonMatch[1])}-${Number(
              episodeMatch[1],
            )}`;
            const lang =
              (file.language ?? "").toUpperCase() || "SR";
            const langs = subsByKey.get(key) ?? [];
            if (!langs.includes(lang)) {
              langs.push(lang);
            }
            subsByKey.set(key, langs);
          }
        }
      }
    }
    return { sizeByPath, subsByKey };
  }, [sources]);

  function episodeSize(episode: FilmiumEpisode): number | null {
    return episode.video_source
      ? fileIndex.sizeByPath.get(episode.video_source) ?? null
      : null;
  }

  function episodeSubs(
    seasonNumber: number,
    episode: FilmiumEpisode,
  ): string[] {
    return (
      fileIndex.subsByKey.get(
        `${seasonNumber}-${episode.episode_number}`,
      ) ?? []
    );
  }

  function tmdbFor(
    episode: FilmiumEpisode,
  ): FilmiumEpisodeMetadata | undefined {
    return tmdbEpisodes.find(
      (entry) => entry.episode_number === episode.episode_number,
    );
  }

  // Razreši tmdb_id: iz deljenog enrich rezultata (izvedeno gore) ili
  // sopstvenim pozivom kada ga tamo nema.
  useEffect(() => {
    if (enrichment?.tmdb_id) {
      return;
    }
    let active = true;
    enrichFilmiumMediaFromTmdb(item.id)
      .then((data) => {
        if (active && data.matched && data.tmdb_id) {
          setTmdbId(data.tmdb_id);
        }
      })
      .catch(() => {
        /* tolerantno */
      });
    return () => {
      active = false;
    };
  }, [enrichment, item.id]);

  // TMDB podaci sezone (datum/opis/ocena/originalni naziv).
  useEffect(() => {
    if (tmdbId === null || !activeSeason) {
      return;
    }
    let active = true;
    const kljuc = kljucSezone;
    getFilmiumEpisodeMetadata(
      item.id,
      tmdbId,
      activeSeason.season_number,
    )
      .then((data) => {
        if (active) {
          setTmdbEpisodes({ kljuc, epizode: data });
        }
      })
      .catch(() => {
        if (active) {
          setTmdbEpisodes({ kljuc, epizode: [] });
        }
      });
    return () => {
      active = false;
    };
  }, [tmdbId, activeSeason, item.id, kljucSezone]);

  // ffprobe za izabranu epizodu.
  useEffect(() => {
    if (
      !selectedEpisode
      || selectedEpisode.root_id == null
      || !selectedEpisode.video_source
    ) {
      return;
    }
    let active = true;
    const kljuc = kljucEpizode;
    getFilmiumEpisodeTechnical(
      item.id,
      selectedEpisode.root_id,
      selectedEpisode.video_source,
    )
      .then((data) => {
        if (active) {
          setTech({ kljuc, tech: data });
        }
      })
      .catch(() => {
        if (active) {
          setTech({ kljuc, tech: null });
        }
      });
    return () => {
      active = false;
    };
  }, [item.id, selectedEpisode, kljucEpizode]);

  const totalEpisodes = localSeasons.reduce(
    (sum, season) => sum + season.episodes.length,
    0,
  );
  const watchedEpisodes = localSeasons.reduce(
    (sum, season) =>
      sum
      + season.episodes.filter(
        (episode) => episode.watch_status === "completed",
      ).length,
    0,
  );

  function mergeEpisode(updated: FilmiumEpisode): void {
    // PATCH odgovor ne nosi root_id/video_source — čuvamo ih iz postojeće.
    setLocalSeasons((prev) =>
      prev.map((season) => ({
        ...season,
        episodes: season.episodes.map((episode) =>
          episode.id === updated.id
            ? {
                ...episode,
                title: updated.title,
                runtime_minutes: updated.runtime_minutes,
                watch_status: updated.watch_status,
              }
            : episode,
        ),
      })),
    );
  }

  async function runAction(
    label: string,
    action: () => Promise<void>,
  ): Promise<void> {
    setBusy(true);
    setStatus(null);
    try {
      await action();
    } catch (error) {
      setStatus(
        error instanceof Error ? error.message : `${label} nije uspelo.`,
      );
    } finally {
      setBusy(false);
    }
  }

  async function saveEpisode(
    episode: FilmiumEpisode,
    patch: {
      title?: string | null;
      runtime_minutes?: number | null;
      watch_status?: string;
    },
  ): Promise<void> {
    await runAction("Čuvanje epizode", async () => {
      mergeEpisode(
        await updateFilmiumEpisode(item.id, episode.id, patch),
      );
      setStatus("Epizoda sačuvana.");
    });
  }

  async function handleDeleteEpisode(): Promise<void> {
    if (!selectedEpisode) {
      return;
    }
    await runAction("Brisanje epizode", async () => {
      await deleteFilmiumEpisode(item.id, selectedEpisode.id);
      setLocalSeasons((prev) =>
        prev.map((season) => ({
          ...season,
          episodes: season.episodes.filter(
            (episode) => episode.id !== selectedEpisode.id,
          ),
        })),
      );
      setSelectedEpisodeId(null);
      setStatus("Epizoda obrisana.");
    });
  }

  async function markSeasonWatched(): Promise<void> {
    if (!activeSeason) {
      return;
    }
    await runAction("Označavanje sezone", async () => {
      for (const episode of activeSeason.episodes) {
        if (episode.watch_status !== "completed") {
          mergeEpisode(
            await updateFilmiumEpisode(item.id, episode.id, {
              watch_status: "completed",
            }),
          );
        }
      }
      setStatus("Sezona označena kao odgledana.");
    });
  }

  async function handleScan(): Promise<void> {
    const sourceId = sources[0]?.id;
    if (sourceId === undefined) {
      return;
    }
    await runAction("Skeniranje", async () => {
      await rescanFilmiumMediaSource(sourceId);
      setStatus("Folder skeniran — fajlovi osveženi.");
    });
  }

  const selectedTmdb = selectedEpisode
    ? tmdbFor(selectedEpisode)
    : undefined;
  const selectedThumb =
    selectedEpisode?.root_id != null && selectedEpisode.video_source
      ? getFilmiumSeriesEpisodeThumbnailUrl(
          selectedEpisode.root_id,
          selectedEpisode.video_source,
        )
      : null;
  const techResolution =
    tech?.width && tech?.height ? `${tech.width} x ${tech.height}` : "—";
  const techFormat = selectedEpisode?.video_source
    ? fileExt(selectedEpisode.video_source)
    : "—";
  const techSize = selectedEpisode
    ? formatSize(episodeSize(selectedEpisode) ?? 0) || "—"
    : "—";

  return (
    <section className="filmium-eps-tab">
      <input
        accept="video/*,.mkv,.mp4,.avi"
        hidden
        onChange={(event) => {
          if (event.target.files && event.target.files.length > 0) {
            const picked = event.target.files[0].name;
            setStatus(
              `Izabran fajl „${picked}" — zamena videa se primenjuje `
              + "kroz uvoz serije.",
            );
          }
          event.target.value = "";
        }}
        ref={replaceInputRef}
        type="file"
      />

      {status && (
        <p className="filmium-editor-enrich-message">{status}</p>
      )}

      {/* ----------  STAT ČIPOVI  ---------- */}

      <div className="filmium-ratings-stats">
        <RatingStat
          label="TIP"
          value={item.media_type === "series" ? "Serija" : "Film"}
        />
        <RatingStat label="SEZONE" value={String(localSeasons.length)} />
        <RatingStat label="EPIZODE" value={String(totalEpisodes)} />
        <RatingStat
          label="ODGLEDANO"
          value={`${watchedEpisodes} / ${totalEpisodes}`}
        />
        <RatingStat
          label="STATUS"
          value={
            totalEpisodes > 0 && watchedEpisodes === totalEpisodes
              ? "Završeno"
              : "U toku"
          }
        />
        <RatingStat
          label="TMDB"
          value={enrichment?.tmdb_id ? "Upareno" : "—"}
        />
      </div>

      <div className="filmium-eps-body">
        {/* ==========  SEZONE  ========== */}

        <aside className="filmium-eps-seasons">
          <p className="filmium-editor-block-label">SEZONE</p>
          {localSeasons.map((season) => {
            const watched = season.episodes.filter(
              (episode) => episode.watch_status === "completed",
            ).length;
            const seasonStatus =
              season.episodes.length === 0
                ? "Planirano"
                : watched === season.episodes.length
                  ? "Kompletna"
                  : watched > 0
                    ? "Delimično"
                    : "Planirano";
            return (
              <button
                className={`filmium-eps-season${
                  activeSeasonId === season.id ? " active" : ""
                }`}
                key={season.id}
                onClick={() => {
                  setActiveSeasonId(season.id);
                  setSelectedEpisodeId(null);
                }}
                type="button"
              >
                <strong>
                  {season.name ?? `Sezona ${season.season_number}`}
                </strong>
                <span>{season.episodes.length} epizoda</span>
                <span
                  className={`filmium-eps-season-status ${seasonStatus.toLowerCase()}`}
                >
                  {seasonStatus}
                </span>
              </button>
            );
          })}

          <button
            className="filmium-editor-button ghost small full"
            disabled={busy}
            onClick={() => void handleScan()}
            type="button"
          >
            <Folder size={14} />
            Skeniraj folder
          </button>
        </aside>

        {/* ==========  EPIZODE + PROGRES  ========== */}

        <div className="filmium-eps-main">
          <div className="filmium-editor-card">
            <div className="filmium-ratings-card-head">
              <p className="filmium-editor-block-label">
                EPIZODE — {activeSeason
                  ? activeSeason.name
                    ?? `Sezona ${activeSeason.season_number}`
                  : "—"}
              </p>
              <div className="filmium-files-row-actions">
                <button
                  className="filmium-editor-button ghost small"
                  onClick={() => setSortAsc((value) => !value)}
                  type="button"
                >
                  Sortiraj {sortAsc ? "↑" : "↓"}
                </button>
              </div>
            </div>

            <div className="filmium-editor-episode-table">
              <table>
                <thead>
                  <tr>
                    <th>Ep</th>
                    <th>Poster</th>
                    <th>Naslov</th>
                    <th>Trajanje</th>
                    <th>Datum</th>
                    <th>Titl</th>
                    <th>Status</th>
                    <th>Akcije</th>
                  </tr>
                </thead>
                <tbody>
                  {episodes.map((episode) => {
                    const tmdb = tmdbFor(episode);
                    const subs = episodeSubs(
                      activeSeason?.season_number ?? 0,
                      episode,
                    );
                    const thumb =
                      episode.root_id != null && episode.video_source
                        ? getFilmiumSeriesEpisodeThumbnailUrl(
                            episode.root_id,
                            episode.video_source,
                          )
                        : null;
                    return (
                      <tr
                        className={
                          selectedEpisodeId === episode.id ? "selected" : ""
                        }
                        key={episode.id}
                        onClick={() => setSelectedEpisodeId(episode.id)}
                      >
                        <td>
                          {String(episode.episode_number).padStart(2, "0")}
                        </td>
                        <td>
                          <span className="filmium-eps-thumb">
                            {thumb ? (
                              <img alt="" loading="lazy" src={thumb} />
                            ) : (
                              <Play size={12} />
                            )}
                          </span>
                        </td>
                        <td>
                          {episode.title
                            ?? tmdb?.name
                            ?? `Epizoda ${episode.episode_number}`}
                        </td>
                        <td>
                          {episode.runtime_minutes
                            ? `${episode.runtime_minutes}m`
                            : "—"}
                        </td>
                        <td>{formatAirDate(tmdb?.air_date ?? null)}</td>
                        <td>{subs.length > 0 ? subs.join("/") : "—"}</td>
                        <td>
                          <span
                            className={`filmium-eps-status ${episode.watch_status}`}
                          >
                            {EPISODE_STATUS_SR[episode.watch_status]
                              ?? episode.watch_status}
                          </span>
                        </td>
                        <td>
                          <button
                            className="filmium-editor-row-edit"
                            onClick={() => setSelectedEpisodeId(episode.id)}
                            type="button"
                          >
                            <Pencil size={12} />
                          </button>
                        </td>
                      </tr>
                    );
                  })}

                  {episodes.length === 0 && (
                    <tr>
                      <td className="empty" colSpan={8}>
                        Nema epizoda u ovoj sezoni.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* ----------  PROGRES SEZONE  ---------- */}

          {activeSeason && activeSeason.episodes.length > 0 && (
            <div className="filmium-editor-card">
              <p className="filmium-editor-block-label">PROGRES SEZONE</p>
              <ProgressBar
                label="Fajlovi dodati"
                done={
                  activeSeason.episodes.filter(
                    (episode) => episode.video_source,
                  ).length
                }
                total={activeSeason.episodes.length}
                tone="green"
              />
              <ProgressBar
                label="Odgledano"
                done={
                  activeSeason.episodes.filter(
                    (episode) => episode.watch_status === "completed",
                  ).length
                }
                total={activeSeason.episodes.length}
                tone="purple"
              />
              <ProgressBar
                label="Titlovi"
                done={
                  activeSeason.episodes.filter(
                    (episode) =>
                      episodeSubs(
                        activeSeason.season_number,
                        episode,
                      ).length > 0,
                  ).length
                }
                total={activeSeason.episodes.length}
                tone="blue"
              />
            </div>
          )}

          {/* ----------  MASOVNE AKCIJE  ---------- */}

          <div className="filmium-editor-card">
            <p className="filmium-editor-block-label">MASOVNE AKCIJE</p>
            <div className="filmium-eps-bulk">
              <button
                className="filmium-editor-button ghost small"
                disabled={busy}
                onClick={() => void handleScan()}
                type="button"
              >
                <RefreshCw size={13} />
                Skeniraj sve epizode
              </button>
              <button
                className="filmium-editor-button ghost small"
                disabled={busy || !activeSeason}
                onClick={() => void markSeasonWatched()}
                type="button"
              >
                <Check size={13} />
                Označi sezonu kao odgledanu
              </button>
            </div>
          </div>
        </div>

        {/* ==========  DETALJI EPIZODE  ========== */}

        <aside className="filmium-eps-detail">
          <p className="filmium-editor-block-label">DETALJI EPIZODE</p>

          <div className="filmium-eps-detail-thumb">
            {selectedThumb ? (
              <img alt="" src={selectedThumb} />
            ) : (
              <Play size={26} />
            )}
          </div>

          {selectedEpisode ? (
            <EpisodeDetailForm
              // Druga epizoda = nova forma: polja se pune pri pravljenju
              // komponente, umesto da ih efekat prepisuje preko unetih.
              key={selectedEpisode.id}
              busy={busy}
              episode={selectedEpisode}
              format={techFormat}
              onDelete={() => void handleDeleteEpisode()}
              onEditSubtitle={onEditSubtitle}
              onReplace={() => replaceInputRef.current?.click()}
              onSave={(patch) => void saveEpisode(selectedEpisode, patch)}
              resolution={techResolution}
              seasonNumber={activeSeason?.season_number ?? 0}
              size={techSize}
              subs={episodeSubs(
                activeSeason?.season_number ?? 0,
                selectedEpisode,
              )}
              techFound={tech?.found ?? false}
              tmdb={selectedTmdb}
            />
          ) : (
            <p className="filmium-media-empty">
              Izaberi epizodu iz tabele.
            </p>
          )}
        </aside>
      </div>
    </section>
  );
}

function ProgressBar({
  label,
  done,
  total,
  tone,
}: {
  label: string;
  done: number;
  total: number;
  tone: "green" | "purple" | "blue";
}) {
  const percent = total > 0 ? Math.round((done / total) * 100) : 0;
  return (
    <div className="filmium-eps-progress">
      <div className="filmium-eps-progress-head">
        <span>{label}</span>
        <strong>
          {done} / {total}
        </strong>
      </div>
      <div className="filmium-eps-progress-track">
        <div
          className={`filmium-eps-progress-fill ${tone}`}
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}

type EpisodeDetailFormProps = {
  episode: FilmiumEpisode;
  seasonNumber: number;
  tmdb: FilmiumEpisodeMetadata | undefined;
  resolution: string;
  format: string;
  size: string;
  subs: string[];
  techFound: boolean;
  busy: boolean;
  onSave: (patch: {
    title?: string | null;
    runtime_minutes?: number | null;
    watch_status?: string;
  }) => void;
  onDelete: () => void;
  onReplace: () => void;
  onEditSubtitle: () => void;
};

/**
 * Forma za izmenu jedne epizode (naslov, trajanje, status…).
 */
function EpisodeDetailForm({
  episode,
  seasonNumber,
  tmdb,
  resolution,
  format,
  size,
  subs,
  techFound,
  busy,
  onSave,
  onDelete,
  onReplace,
  onEditSubtitle,
}: EpisodeDetailFormProps) {
  const [title, setTitle] = useState(episode.title ?? "");
  const [runtime, setRuntime] = useState(
    episode.runtime_minutes ? String(episode.runtime_minutes) : "",
  );
  const [watchStatus, setWatchStatus] = useState(episode.watch_status);
  const [favorite, setFavorite] = useState(false);

  return (
    <>
      <div className="filmium-editor-field-row">
        <Field label="Naslov epizode">
          <input
            className="filmium-editor-input"
            onChange={(event) => setTitle(event.target.value)}
            value={title}
          />
        </Field>
        <Field label="Originalni naslov" tmdb>
          <input
            className={
              tmdb?.name
                ? "filmium-editor-input tmdb-filled"
                : "filmium-editor-input"
            }
            readOnly
            value={tmdb?.name ?? ""}
          />
        </Field>
      </div>

      <div className="filmium-editor-field-row">
        <Field label="Broj sezone">
          <input
            className="filmium-editor-input"
            readOnly
            value={seasonNumber}
          />
        </Field>
        <Field label="Broj epizode">
          <input
            className="filmium-editor-input"
            readOnly
            value={episode.episode_number}
          />
        </Field>
        <Field label="Trajanje">
          <input
            className="filmium-editor-input"
            onChange={(event) => setRuntime(event.target.value)}
            value={runtime}
          />
        </Field>
      </div>

      <div className="filmium-editor-field-row">
        <Field label="Datum emitovanja" tmdb>
          <input
            className={
              tmdb?.air_date
                ? "filmium-editor-input tmdb-filled"
                : "filmium-editor-input"
            }
            readOnly
            value={formatAirDate(tmdb?.air_date ?? null)}
          />
        </Field>
        <Field label="Ocena epizode (TMDB)" tmdb>
          <input
            className={
              tmdb?.rating
                ? "filmium-editor-input tmdb-filled"
                : "filmium-editor-input"
            }
            readOnly
            value={tmdb?.rating ? tmdb.rating.toFixed(1) : ""}
          />
        </Field>
      </div>

      <Field label="Opis epizode (domaći — SR/HR/BS)" tmdb>
        <textarea
          className={
            tmdb?.overview_local
              ? "filmium-editor-input filmium-editor-textarea tmdb-filled"
              : "filmium-editor-input filmium-editor-textarea"
          }
          readOnly
          rows={3}
          value={tmdb?.overview_local ?? ""}
        />
      </Field>

      <Field label="Opis epizode (engleski)" tmdb>
        <textarea
          className={
            tmdb?.overview_en
              ? "filmium-editor-input filmium-editor-textarea tmdb-filled"
              : "filmium-editor-input filmium-editor-textarea"
          }
          readOnly
          rows={3}
          value={tmdb?.overview_en ?? ""}
        />
      </Field>

      <div className="filmium-editor-card filmium-eps-file-card">
        <p className="filmium-editor-block-label">FAJL EPIZODE</p>
        <FileDetailRow
          label="Putanja"
          value={episode.video_source}
          mono
        />
        <div className="filmium-eps-tech">
          <FileTech label="Rezolucija" value={resolution} />
          <FileTech label="Format" value={format} />
          <FileTech label="Veličina" value={size} />
          <FileTech
            label="Status"
            value={techFound ? "OK" : "—"}
          />
        </div>
        <div className="filmium-eps-tech-subs">
          Titlovi: {subs.length > 0 ? subs.join(" / ") : "Nema"}
        </div>
      </div>

      <div className="filmium-editor-field-row">
        <Field label="Status gledanja">
          <select
            className="filmium-editor-input"
            onChange={(event) => setWatchStatus(event.target.value)}
            value={watchStatus}
          >
            {Object.entries(EPISODE_STATUS_SR).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </Field>
        <label className="filmium-editor-toggle filmium-eps-fav">
          <input
            checked={favorite}
            onChange={(event) => setFavorite(event.target.checked)}
            type="checkbox"
          />
          Omiljena epizoda
        </label>
      </div>

      <div className="filmium-subs-detail-actions">
        <button
          className="filmium-editor-button primary small"
          disabled={busy}
          onClick={() =>
            onSave({
              title: title.trim() === "" ? null : title,
              runtime_minutes:
                runtime.trim() === "" ? null : Number(runtime),
              watch_status: watchStatus,
            })}
          type="button"
        >
          <Save size={13} />
          Sačuvaj epizodu
        </button>
        <button
          className="filmium-editor-button ghost small"
          disabled={busy}
          onClick={onReplace}
          type="button"
        >
          <RefreshCw size={13} />
          Zameni fajl
        </button>
        <button
          className="filmium-editor-button ghost small"
          onClick={onEditSubtitle}
          type="button"
        >
          <Languages size={13} />
          Uredi titl
        </button>
        <button
          className="filmium-editor-button danger small"
          disabled={busy}
          onClick={onDelete}
          type="button"
        >
          <Trash2 size={13} />
          Obriši epizodu
        </button>
      </div>
    </>
  );
}


// ==========          PREVODI TAB          ==========

type SubtitlesTabProps = {
  item: MediaItem;
  sources: FilmiumMediaSource[];
  initialSettings?: unknown;
  onReport?: (data: unknown) => void;
};

const SUBTITLE_LANG_LABELS: Record<string, string> = {
  sr: "Srpski",
  srp: "Srpski",
  srb: "Srpski",
  en: "Engleski",
  eng: "Engleski",
  hr: "Hrvatski",
  hrv: "Hrvatski",
  bs: "Bosanski",
  bos: "Bosanski",
  mk: "Makedonski",
  mkd: "Makedonski",
};

function subtitleLangLabel(code: string | null): string {
  if (!code) {
    return "Nepoznato";
  }
  return SUBTITLE_LANG_LABELS[code.toLowerCase()] ?? code.toUpperCase();
}

type SubtitleEntry = {
  id: number;
  source: FilmiumMediaSource;
  name: string;
  lang: string | null;
  format: string;
  sizeBytes: number;
  fileStatus: string;
  path: string;
};

/**
 * „Prevodi" tab: titlovi, pregled, sinhronizacija i jezički profil.
 *
 * Lista titlova, verzije i detalji dolaze iz stvarnih subtitle fajlova
 * registrovanih izvora. Sadržaj titla se ne učitava u pregled (to radi
 * player), a polja koja se ne skladište (encoding, broj linija, autor)
 * prikazuju „—".
 */
function SubtitlesTab({
  item,
  sources,
  initialSettings,
  onReport,
}: SubtitlesTabProps) {
  void item;
  const saved = (initialSettings ?? {}) as {
    delay?: number;
    fpsConversion?: string;
    detailFlags?: Record<string, boolean>;
    auto?: Record<string, boolean>;
    priority?: string[];
  };
  // Lokalna kopija izvora — osvežava se posle upload/brisanje/rescan akcija.
  // Isti obrazac kao kod sezona: izmene se pamte uz spisak izvora od koga su
  // krenule, pa nov spisak sa strane odmah preuzima prikaz.
  const [izmenjeniIzvori, setIzmenjeniIzvori] = useState<{
    osnova: FilmiumMediaSource[];
    izvori: FilmiumMediaSource[];
  } | null>(null);

  const localSources = izmenjeniIzvori?.osnova === sources
    ? izmenjeniIzvori.izvori
    : sources;

  const setLocalSources = useCallback(
    (izmena: (prethodni: FilmiumMediaSource[]) => FilmiumMediaSource[]) => {
      setIzmenjeniIzvori((staro) => ({
        osnova: sources,
        izvori: izmena(
          staro?.osnova === sources ? staro.izvori : sources,
        ),
      }));
    },
    [sources],
  );

  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const addInputRef = useRef<HTMLInputElement>(null);
  const replaceInputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);

  // Folder izbor: webkitdirectory nije u React tipovima → set preko ref-a.
  useEffect(() => {
    folderInputRef.current?.setAttribute("webkitdirectory", "");
    folderInputRef.current?.setAttribute("directory", "");
  }, []);

  const subtitles = useMemo<SubtitleEntry[]>(
    () =>
      localSources.flatMap((source) =>
        source.files
          .filter((file) => file.role === "subtitle")
          .map((file) => ({
            id: file.id,
            source,
            name: fileName(file.relative_path),
            lang: file.language,
            format: fileExt(file.relative_path),
            sizeBytes: file.size_bytes,
            fileStatus: file.file_status,
            path: joinPath(
              source.root_path_snapshot,
              source.relative_directory,
              file.relative_path,
            ),
          })),
      ),
    [localSources],
  );

  const [selectedId, setSelectedId] = useState<number | null>(
    subtitles[0]?.id ?? null,
  );
  const [defaultId, setDefaultId] = useState<number | null>(
    subtitles[0]?.id ?? null,
  );
  const [delay, setDelay] = useState(saved.delay ?? 0);
  const [fpsConversion, setFpsConversion] = useState(
    saved.fpsConversion ?? "Nema",
  );
  const [detailFlags, setDetailFlags] = useState<Record<string, boolean>>(
    () =>
      saved.detailFlags ?? {
        default: true,
        show: true,
        export: true,
        autoload: false,
      },
  );
  const [auto, setAuto] = useState<Record<string, boolean>>(
    () =>
      saved.auto ?? {
        find: true,
        linkVideo: true,
        detectLang: true,
        fixEncoding: true,
        warnLate: false,
      },
  );
  const [priority, setPriority] = useState<string[]>(
    saved.priority ?? ["Srpski", "Engleski", "Hrvatski"],
  );

  // Prijavi stanje panelu za snimanje (editor_settings.subtitles).
  useEffect(() => {
    onReport?.({ delay, fpsConversion, detailFlags, auto, priority });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [delay, fpsConversion, detailFlags, auto, priority]);

  const selected =
    subtitles.find((entry) => entry.id === selectedId)
    ?? subtitles[0]
    ?? null;

  const primarySourceId = localSources[0]?.id ?? null;

  function mergeSource(updated: FilmiumMediaSource): void {
    setLocalSources((prev) =>
      prev.map((source) =>
        source.id === updated.id ? updated : source,
      ),
    );
  }

  async function runAction(
    label: string,
    action: () => Promise<void>,
  ): Promise<void> {
    setBusy(true);
    setStatus(null);
    try {
      await action();
    } catch (error) {
      setStatus(
        error instanceof Error ? error.message : `${label} nije uspelo.`,
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleAddFiles(
    files: FileList | null,
    replace?: { sourceId: number; fileId: number },
  ): Promise<void> {
    if (!files || files.length === 0 || primarySourceId === null) {
      return;
    }
    const picked = Array.from(files).filter((file) =>
      /\.(srt|ass|ssa|vtt|sub)$/i.test(file.name),
    );
    if (picked.length === 0) {
      setStatus("Nema titl fajlova (.srt, .ass, .vtt…) u izboru.");
      return;
    }
    await runAction("Dodavanje titla", async () => {
      let updated: FilmiumMediaSource | undefined;
      for (const file of picked) {
        updated = await addSubtitleToSource(primarySourceId, file);
      }
      if (updated) {
        mergeSource(updated);
      }
      if (replace) {
        mergeSource(
          await deleteSourceFile(replace.sourceId, replace.fileId),
        );
      }
      setStatus(
        picked.length > 1
          ? `Uvezeno ${picked.length} titlova.`
          : replace
            ? "Titl zamenjen."
            : "Titl dodat.",
      );
    });
  }

  async function handleScan(): Promise<void> {
    if (primarySourceId === null) {
      return;
    }
    await runAction("Skeniranje", async () => {
      mergeSource(await rescanFilmiumMediaSource(primarySourceId));
      setStatus("Folder skeniran — titlovi osveženi.");
    });
  }

  async function handleDelete(): Promise<void> {
    if (!selected) {
      return;
    }
    await runAction("Brisanje", async () => {
      mergeSource(
        await deleteSourceFile(selected.source.id, selected.id),
      );
      setSelectedId(null);
      setStatus("Titl obrisan.");
    });
  }

  async function handleDownload(): Promise<void> {
    if (!selected) {
      return;
    }
    await runAction("Preuzimanje", async () => {
      const result = await downloadSourceFileToDesktop(
        selected.source.id,
        selected.id,
      );
      setStatus(`Kopirano na: ${result.path}`);
    });
  }

  const hasLang = (codes: string[]) =>
    subtitles.some((entry) =>
      codes.includes((entry.lang ?? "").toLowerCase()),
    );

  const formats = Array.from(
    new Set(subtitles.map((entry) => entry.format).filter(Boolean)),
  );

  const langOrderChips = ["SR", "EN", "HR", "BS", "MK"];

  function movePriority(index: number, direction: -1 | 1): void {
    setPriority((prev) => {
      const next = [...prev];
      const target = index + direction;
      if (target < 0 || target >= next.length) {
        return prev;
      }
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
  }

  return (
    <section className="filmium-subs-tab">
      {/* Skriveni file/folder pickeri (otvaraju OS dijalog). */}
      <input
        accept=".srt,.ass,.ssa,.vtt,.sub"
        hidden
        multiple
        onChange={(event) => {
          void handleAddFiles(event.target.files);
          event.target.value = "";
        }}
        ref={addInputRef}
        type="file"
      />
      <input
        accept=".srt,.ass,.ssa,.vtt,.sub"
        hidden
        onChange={(event) => {
          if (selected) {
            void handleAddFiles(event.target.files, {
              sourceId: selected.source.id,
              fileId: selected.id,
            });
          }
          event.target.value = "";
        }}
        ref={replaceInputRef}
        type="file"
      />
      <input
        hidden
        multiple
        onChange={(event) => {
          void handleAddFiles(event.target.files);
          event.target.value = "";
        }}
        ref={folderInputRef}
        type="file"
      />

      {status && (
        <p className="filmium-editor-enrich-message">{status}</p>
      )}

      {/* ----------  STAT ČIPOVI  ---------- */}

      <div className="filmium-ratings-stats">
        <RatingStat
          label="SRPSKI TITL"
          value={hasLang(["sr", "srp", "srb"]) ? "Dostupan" : "—"}
          suffix=""
        />
        <RatingStat
          label="ENGLESKI TITL"
          value={hasLang(["en", "eng"]) ? "Dostupan" : "—"}
        />
        <RatingStat
          label="EKSTERNI"
          value={`${subtitles.length} fajla`}
        />
        <RatingStat
          label="SINHRONIZACIJA"
          value={subtitles.length > 0 ? "OK" : "—"}
        />
        <RatingStat
          label="FORMAT"
          value={formats.length > 0 ? formats.join(" / ") : "—"}
        />
        <RatingStat
          label="JEZICI"
          value={String(
            new Set(
              subtitles.map((entry) => subtitleLangLabel(entry.lang)),
            ).size,
          )}
        />
      </div>

      <div className="filmium-ratings-body">
        <div className="filmium-ratings-main">
          {/* ----------  TITLOVI  ---------- */}

          <div className="filmium-editor-card">
            <div className="filmium-ratings-card-head">
              <p className="filmium-editor-block-label">TITLOVI</p>
              <button
                className="filmium-editor-button primary small"
                disabled={busy || primarySourceId === null}
                onClick={() => addInputRef.current?.click()}
                type="button"
              >
                <Plus size={13} />
                Dodaj titl
              </button>
            </div>

            <div className="filmium-editor-episode-table">
              <table>
                <thead>
                  <tr>
                    <th>Jezik</th>
                    <th>Format</th>
                    <th>Veličina</th>
                    <th>Status</th>
                    <th>Default</th>
                    <th>Akcije</th>
                  </tr>
                </thead>
                <tbody>
                  {subtitles.map((entry) => (
                    <tr
                      className={selectedId === entry.id ? "selected" : ""}
                      key={entry.id}
                      onClick={() => setSelectedId(entry.id)}
                    >
                      <td>{subtitleLangLabel(entry.lang)}</td>
                      <td>{entry.format}</td>
                      <td>{formatSize(entry.sizeBytes) || "—"}</td>
                      <td>
                        <span
                          className={`filmium-files-status ${entry.fileStatus}`}
                        >
                          {FILE_STATUS_TEXT[entry.fileStatus]
                            ?? entry.fileStatus}
                        </span>
                      </td>
                      <td>
                        <input
                          checked={defaultId === entry.id}
                          name="filmium-subtitle-default"
                          onChange={() => setDefaultId(entry.id)}
                          type="radio"
                        />
                      </td>
                      <td>
                        <div className="filmium-files-row-actions">
                          <button
                            className="filmium-editor-row-edit"
                            onClick={() => setSelectedId(entry.id)}
                            type="button"
                          >
                            Uredi
                          </button>
                          <button
                            className="filmium-editor-row-edit danger"
                            type="button"
                          >
                            <Trash2 size={13} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}

                  {subtitles.length === 0 && (
                    <tr>
                      <td className="empty" colSpan={6}>
                        Nema registrovanih titlova za ovaj sadržaj.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* ----------  IZABRANI TITL - PREGLED  ---------- */}

          <div className="filmium-editor-card">
            <p className="filmium-editor-block-label">
              IZABRANI TITL — PREGLED
            </p>
            <div className="filmium-subs-preview">
              <Languages size={26} />
              <p>
                {selected
                  ? selected.name
                  : "Nije izabran titl."}
              </p>
              <span>
                Sadržaj titla se prikazuje u plejeru pri reprodukciji.
              </span>
            </div>

            <div className="filmium-subs-sync-controls">
              <span className="filmium-subs-delay-label">
                Kašnjenje
              </span>
              <div className="filmium-ratings-stepper">
                <button
                  onClick={() =>
                    setDelay((value) => Math.round((value - 0.1) * 10) / 10)}
                  type="button"
                >
                  <Minus size={14} />
                </button>
                <strong>
                  {delay > 0 ? "+" : ""}
                  {delay.toFixed(2)}s
                </strong>
                <button
                  onClick={() =>
                    setDelay((value) => Math.round((value + 0.1) * 10) / 10)}
                  type="button"
                >
                  <Plus size={14} />
                </button>
              </div>

              <button
                className="filmium-editor-button ghost small"
                onClick={() =>
                  setDelay((value) => Math.round((value - 0.5) * 10) / 10)}
                type="button"
              >
                Pomeri -0.5s
              </button>
              <button
                className="filmium-editor-button ghost small"
                onClick={() =>
                  setDelay((value) => Math.round((value + 0.5) * 10) / 10)}
                type="button"
              >
                Pomeri +0.5s
              </button>
              <button
                className="filmium-editor-button primary small"
                type="button"
              >
                <Save size={13} />
                Sačuvaj sync
              </button>
            </div>
          </div>

          {/* ----------  SINHRONIZACIJA  ---------- */}

          <div className="filmium-editor-card">
            <p className="filmium-editor-block-label">SINHRONIZACIJA</p>
            <div className="filmium-editor-field-row">
              <Field label="Globalni offset">
                <input
                  className="filmium-editor-input"
                  onChange={(event) =>
                    setDelay(Number(event.target.value))}
                  step={0.1}
                  type="number"
                  value={delay}
                />
              </Field>
              <Field label="FPS konverzija">
                <select
                  className="filmium-editor-input"
                  onChange={(event) => setFpsConversion(event.target.value)}
                  value={fpsConversion}
                >
                  {["Nema", "23.976 → 25", "25 → 23.976", "24 → 25"].map(
                    (option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ),
                  )}
                </select>
              </Field>
            </div>
            <div className="filmium-files-checks">
              <span className="filmium-files-check ok">
                <Check size={15} />
                Titl pronađen
              </span>
              <span
                className={`filmium-files-check ${
                  ["SRT", "ASS", "VTT", "SUB"].includes(
                    selected?.format ?? "",
                  )
                    ? "ok"
                    : "warn"
                }`}
              >
                {["SRT", "ASS", "VTT", "SUB"].includes(
                  selected?.format ?? "",
                ) ? (
                  <Check size={15} />
                ) : (
                  <TriangleAlert size={15} />
                )}
                Format podržan
              </span>
            </div>
          </div>

          {/* ----------  VERZIJE TITLOVA  ---------- */}

          <div className="filmium-editor-card">
            <p className="filmium-editor-block-label">VERZIJE TITLOVA</p>
            {subtitles.length > 0 ? (
              <div className="filmium-subs-versions">
                {subtitles.map((entry) => (
                  <button
                    className={`filmium-subs-version${
                      selectedId === entry.id ? " active" : ""
                    }`}
                    key={entry.id}
                    onClick={() => setSelectedId(entry.id)}
                    type="button"
                  >
                    <strong>
                      {subtitleLangLabel(entry.lang)} · {entry.format}
                    </strong>
                    <span>{formatSize(entry.sizeBytes) || "—"}</span>
                    {defaultId === entry.id && (
                      <span className="filmium-subs-version-badge">
                        Glavni
                      </span>
                    )}
                  </button>
                ))}
              </div>
            ) : (
              <p className="filmium-media-empty">
                Nema titl verzija.
              </p>
            )}
          </div>

          {/* ----------  UPLOAD + AUTOMATIKA  ---------- */}

          <div className="filmium-subs-bottom">
            <div className="filmium-editor-card">
              <p className="filmium-editor-block-label">
                UPLOAD / UVOZ TITLOVA
              </p>
              <div className="filmium-media-dropzone">
                <UploadCloud size={24} />
                <p>Prevuci SRT, ASS ili VTT fajlove ovde</p>
              </div>
              <div className="filmium-files-actions">
                <button
                  className="filmium-editor-button ghost small"
                  disabled={busy || primarySourceId === null}
                  onClick={() => addInputRef.current?.click()}
                  type="button"
                >
                  <Folder size={13} />
                  Izaberi fajl
                </button>
                <button
                  className="filmium-editor-button ghost small"
                  disabled={busy || primarySourceId === null}
                  onClick={() => folderInputRef.current?.click()}
                  type="button"
                >
                  <FolderOpen size={13} />
                  Uvezi iz foldera
                </button>
                <button
                  className="filmium-editor-button ghost small"
                  disabled={busy || primarySourceId === null}
                  onClick={() => void handleScan()}
                  type="button"
                >
                  <RefreshCw size={13} />
                  Skeniraj automatski
                </button>
              </div>
            </div>

            <div className="filmium-editor-card">
              <p className="filmium-editor-block-label">AUTOMATIKA</p>
              <RatingToggle
                checked={auto.find ?? false}
                label="Automatski pronađi titlove"
                onChange={(value) =>
                  setAuto((prev) => ({ ...prev, find: value }))}
              />
              <RatingToggle
                checked={auto.linkVideo ?? false}
                label="Poveži sa video verzijom"
                onChange={(value) =>
                  setAuto((prev) => ({ ...prev, linkVideo: value }))}
              />
              <RatingToggle
                checked={auto.detectLang ?? false}
                label="Prepoznaj jezik"
                onChange={(value) =>
                  setAuto((prev) => ({ ...prev, detectLang: value }))}
              />
              <RatingToggle
                checked={auto.fixEncoding ?? false}
                label="Popravi encoding"
                onChange={(value) =>
                  setAuto((prev) => ({ ...prev, fixEncoding: value }))}
              />
              <RatingToggle
                checked={auto.warnLate ?? false}
                label="Upozori ako titl kasni"
                onChange={(value) =>
                  setAuto((prev) => ({ ...prev, warnLate: value }))}
              />
            </div>
          </div>
        </div>

        {/* ==========  RAIL  ========== */}

        <aside className="filmium-ratings-rail">
          {/* ----------  DETALJI TITLA  ---------- */}

          <div className="filmium-editor-card">
            <p className="filmium-editor-block-label">DETALJI TITLA</p>

            <FileDetailRow label="Naziv fajla" value={selected?.name} />
            <div className="filmium-files-detail-row">
              <span>Jezik</span>
              <strong>{subtitleLangLabel(selected?.lang ?? null)}</strong>
            </div>
            <FileDetailRow label="Format" value={selected?.format} />
            <FileDetailRow label="Tip" value="Eksterni" />
            <FileDetailRow label="Encoding" value={null} />
            <FileDetailRow label="Broj linija" value={null} />
            <FileDetailRow label="Izvor" value={null} />
            <FileDetailRow label="Autor" value={null} />
            <FileDetailRow
              label="Putanja"
              value={selected?.path}
              mono
            />
            <FileDetailRow
              label="Datum dodavanja"
              value={
                selected
                  ? formatEditorDate(selected.source.created_at)
                  : null
              }
            />
            <FileDetailRow
              label="Poslednja provera"
              value={
                selected
                  ? formatEditorDate(selected.source.last_verified_at)
                  : null
              }
            />

            <div className="filmium-subs-flags">
              <RatingToggle
                checked={detailFlags.default ?? false}
                label="Postavi kao default"
                onChange={(value) =>
                  setDetailFlags((prev) => ({ ...prev, default: value }))}
              />
              <RatingToggle
                checked={detailFlags.show ?? false}
                label="Prikaži uz film"
                onChange={(value) =>
                  setDetailFlags((prev) => ({ ...prev, show: value }))}
              />
              <RatingToggle
                checked={detailFlags.export ?? false}
                label="Uključi u export"
                onChange={(value) =>
                  setDetailFlags((prev) => ({ ...prev, export: value }))}
              />
              <RatingToggle
                checked={detailFlags.autoload ?? false}
                label="Automatski učitaj"
                onChange={(value) =>
                  setDetailFlags((prev) => ({ ...prev, autoload: value }))}
              />
            </div>

            <div className="filmium-subs-detail-actions">
              <button
                className="filmium-editor-button primary small"
                disabled={!selected}
                onClick={() =>
                  setStatus(
                    "Titl je sačuvan na disku u originalnoj formi.",
                  )}
                type="button"
              >
                <Save size={13} />
                Sačuvaj titl
              </button>
              <button
                className="filmium-editor-button ghost small"
                disabled={busy || !selected}
                onClick={() => replaceInputRef.current?.click()}
                type="button"
              >
                <RefreshCw size={13} />
                Zameni fajl
              </button>
              <button
                className="filmium-editor-button ghost small"
                disabled={busy || !selected}
                onClick={() => void handleDownload()}
                type="button"
              >
                <Download size={13} />
                Preuzmi
              </button>
              <button
                className="filmium-editor-button danger small"
                disabled={busy || !selected}
                onClick={() => void handleDelete()}
                type="button"
              >
                <Trash2 size={13} />
                Obriši
              </button>
            </div>
          </div>

          {/* ----------  JEZIČKI PROFIL  ---------- */}

          <div className="filmium-editor-card">
            <p className="filmium-editor-block-label">JEZIČKI PROFIL</p>
            <div className="filmium-cats-chips">
              {langOrderChips.map((code) => (
                <span
                  className={`filmium-cats-chip${
                    hasLang([code.toLowerCase()]) ? " on" : ""
                  }`}
                  key={code}
                >
                  {code}
                </span>
              ))}
            </div>

            <p className="filmium-editor-field-label">Prioritet redosled</p>
            <div className="filmium-subs-priority">
              {priority.map((lang, index) => (
                <div className="filmium-subs-priority-row" key={lang}>
                  <span className="filmium-subs-priority-num">
                    {index + 1}
                  </span>
                  <span className="filmium-subs-priority-name">{lang}</span>
                  <button
                    aria-label="Gore"
                    disabled={index === 0}
                    onClick={() => movePriority(index, -1)}
                    type="button"
                  >
                    ▲
                  </button>
                  <button
                    aria-label="Dole"
                    disabled={index === priority.length - 1}
                    onClick={() => movePriority(index, 1)}
                    type="button"
                  >
                    ▼
                  </button>
                </div>
              ))}
            </div>
          </div>
        </aside>
      </div>
    </section>
  );
}


// ==========          KATEGORIJE TAB          ==========

type CategoriesTabProps = {
  item: MediaItem;
  catalog: MediaItem[];
  collections: MediaCollection[];
  enrichment: FilmiumTmdbEnrichment | null;
  onAddToCollection?: (
    collectionId: number,
    itemId: number,
  ) => void | Promise<void>;
  initialSettings?: unknown;
  onReport?: (data: unknown) => void;
};

const LIST_OPTIONS = [
  "Za gledanje",
  "Omiljeno",
  "Preporučeno",
  "Gledano sa društvom",
  "Za vikend",
  "Za ponovno gledanje",
  "Arhiva",
  "Top 2024",
];

const AGE_OPTIONS = ["Bez ograničenja", "7+", "13+", "16+", "18+"];

const LANGUAGE_LABELS: Record<string, string> = {
  en: "Engleski",
  hi: "Hindi",
  sr: "Srpski",
  hr: "Hrvatski",
  bs: "Bosanski",
  ja: "Japanski",
  ko: "Korejski",
  zh: "Kineski",
  fr: "Francuski",
  de: "Nemački",
  es: "Španski",
  it: "Italijanski",
  ru: "Ruski",
  pt: "Portugalski",
  tr: "Turski",
};

function languageLabel(code: string): string {
  return LANGUAGE_LABELS[code.toLowerCase()] ?? code.toUpperCase();
}

/**
 * „Kategorije" tab: žanrovi, kolekcije, liste, mood i pravila preporuka.
 *
 * Žanrovi/jezik/zemlja se dopunjavaju stvarno sa TMDB-a (auto na otvaranju
 * i preko „Dopuni preko TMDB"); kolekcije i povezani sadržaj dolaze iz
 * stvarnih podataka biblioteke.
 */
function CategoriesTab({
  item,
  catalog,
  collections,
  enrichment,
  onAddToCollection,
  initialSettings,
  onReport,
}: CategoriesTabProps) {
  const saved = (initialSettings ?? {}) as {
    lists?: Record<string, boolean>;
    moodTags?: string[];
    mainList?: string;
    ageRec?: string;
    franchise?: string;
    rules?: Record<string, boolean>;
    weights?: Record<string, number>;
    visibility?: string;
  };
  const memberCollections = useMemo(
    () =>
      collections.filter((collection) =>
        collection.item_ids.includes(item.id),
      ),
    [collections, item.id],
  );
  const availableCollections = useMemo(
    () =>
      collections.filter(
        (collection) => !collection.item_ids.includes(item.id),
      ),
    [collections, item.id],
  );

  const [genrePool, setGenrePool] = useState<string[]>([]);
  const [addCollectionId, setAddCollectionId] = useState<string>("");
  const [upisaniZanrovi, setGenres] = useState<string[]>(() =>
    Array.from(item.genres),
  );
  const [genreDraft, setGenreDraft] = useState("");
  const [tmdbGenres, setTmdbGenres] = useState(false);
  const [lists, setLists] = useState<Record<string, boolean>>(
    () => saved.lists ?? { Omiljeno: item.is_favorite },
  );
  const [moodTags, setMoodTags] = useState<string[]>(
    saved.moodTags ?? [],
  );
  const [primaryGenre, setPrimaryGenre] = useState(item.genres[0] ?? "");
  const [mainCollection, setMainCollection] = useState(
    memberCollections[0]?.name ?? "",
  );

  // Kanonski žanrovi iz baze (jedinstveni izvor — bez nepostojećih).
  useEffect(() => {
    let active = true;
    getFilmiumGenres()
      .then((list) => {
        if (active) {
          setGenrePool(list);
        }
      })
      .catch(() => {
        /* tolerantno */
      });
    return () => {
      active = false;
    };
  }, []);
  const [mainList, setMainList] = useState(
    saved.mainList ?? "Preporučeno",
  );
  const [ageRec, setAgeRec] = useState(saved.ageRec ?? "13+");
  const [language, setLanguage] = useState("");
  const [country, setCountry] = useState("");
  const [franchise, setFranchise] = useState(saved.franchise ?? "");
  const [tmdbLang, setTmdbLang] = useState(false);
  const [tmdbCountry, setTmdbCountry] = useState(false);
  const [rules, setRules] = useState<Record<string, boolean>>(
    () =>
      saved.rules ?? {
        recommend: true,
        similar: true,
        trending: true,
        hidePublic: false,
      },
  );
  const [weights, setWeights] = useState<Record<string, number>>(
    () =>
      saved.weights ?? {
        genre: 80,
        mood: 70,
        collection: 60,
        franchise: 90,
      },
  );
  const [visibility, setVisibility] = useState(
    saved.visibility ?? "Privatno",
  );

  // Prijavi stanje panelu za snimanje (editor_settings.categories).
  useEffect(() => {
    onReport?.({
      lists,
      moodTags,
      mainList,
      ageRec,
      franchise,
      rules,
      weights,
      visibility,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    lists,
    moodTags,
    mainList,
    ageRec,
    franchise,
    rules,
    weights,
    visibility,
  ]);

  function applyEnrichment(data: FilmiumTmdbEnrichment): void {
    if (!data.matched) {
      return;
    }
    if (data.genres.length > 0) {
      setGenres((prev) => Array.from(new Set([...prev, ...data.genres])));
      setTmdbGenres(true);
    }
    if (data.original_language) {
      setLanguage((prev) =>
        prev === "" ? languageLabel(data.original_language as string) : prev,
      );
      setTmdbLang(true);
    }
    if (data.country) {
      setCountry((prev) => (prev === "" ? (data.country as string) : prev));
      setTmdbCountry(true);
    }
  }

  // Auto-dopuna sa TMDB-a kada se otvori tab.
  useEffect(() => {
    let active = true;
    enrichFilmiumMediaFromTmdb(item.id)
      .then((data) => {
        if (active) {
          applyEnrichment(data);
        }
      })
      .catch(() => {
        /* tolerantno */
      });
    return () => {
      active = false;
    };
  }, [item.id]);

  // Reaguj na „Dopuni preko TMDB" iz headera — tokom crtanja, iz istog razloga
  // kao u zaglavlju editora.
  const [primenjeno, setPrimenjeno] =
    useState<FilmiumTmdbEnrichment | null>(null);

  if (enrichment && enrichment !== primenjeno) {
    setPrimenjeno(enrichment);
    applyEnrichment(enrichment);
  }

  // Normalizacija: kad se učita registar žanrova, aktivni žanrovi se svode na
  // kanonski oblik (isto pisanje) i bez duplikata (Akcija vs. akcija).
  //
  // Računica, ne stanje: isti upis i isti registar uvek daju isti spisak, pa se
  // izvodi pri crtanju. Upis iz efekta značio je da se posle učitavanja
  // registra ceo spisak jednom prepiše, uz još jedan crtež.
  const genres = useMemo(() => {
    if (genrePool.length === 0) {
      return upisaniZanrovi;
    }
    const byKey = new Map(
      genrePool.map((genre) => [genre.toLowerCase(), genre]),
    );
    const seen = new Set<string>();
    const next: string[] = [];
    for (const genre of upisaniZanrovi) {
      const canonical = byKey.get(genre.toLowerCase()) ?? genre;
      const key = canonical.toLowerCase();
      if (!seen.has(key)) {
        seen.add(key);
        next.push(canonical);
      }
    }
    return next;
  }, [upisaniZanrovi, genrePool]);

  const genreChips = useMemo(() => {
    const poolKeys = new Set(
      genrePool.map((genre) => genre.toLowerCase()),
    );
    const extra = genres.filter(
      (genre) => !poolKeys.has(genre.toLowerCase()),
    );
    return [...extra, ...genrePool];
  }, [genres, genrePool]);

  function toggleGenre(genre: string): void {
    const key = genre.toLowerCase();
    setGenres((prev) =>
      prev.some((entry) => entry.toLowerCase() === key)
        ? prev.filter((entry) => entry.toLowerCase() !== key)
        : [...prev, genre],
    );
  }

  function addGenre(): void {
    const value = genreDraft.trim();
    const key = value.toLowerCase();
    if (
      value !== ""
      && !genres.some((entry) => entry.toLowerCase() === key)
    ) {
      setGenres((prev) => [...prev, value]);
    }
    setGenreDraft("");
  }

  // Povezani sadržaj: članovi istih kolekcija (stvarno).
  const related = useMemo(() => {
    const memberIds = new Set<number>();
    collections
      .filter((collection) => collection.item_ids.includes(item.id))
      .forEach((collection) =>
        collection.item_ids.forEach((id) => memberIds.add(id)),
      );
    return catalog
      .filter(
        (candidate) =>
          candidate.id !== item.id && memberIds.has(candidate.id),
      )
      .slice(0, 6);
  }, [catalog, collections, item.id]);

  // Predlozi auto-kategorizacije iz stvarnih podataka.
  const suggestions = useMemo(() => {
    const list: { label: string; strong: boolean }[] = [];
    genres.slice(0, 2).forEach((genre) =>
      list.push({ label: `Predlog: ${genre}`, strong: true }),
    );
    if (country) {
      list.push({ label: `Predlog: ${country} film`, strong: false });
    }
    if (language) {
      list.push({ label: `Predlog: ${language}`, strong: true });
    }
    return list.slice(0, 4);
  }, [genres, country, language]);

  const activeListCount = Object.values(lists).filter(Boolean).length;

  return (
    <section className="filmium-cats-tab">
      {/* ----------  STAT ČIPOVI  ---------- */}

      <div className="filmium-ratings-stats">
        <RatingStat label="ŽANROVI" value={`${genres.length} aktivna`} />
        <RatingStat
          label="KOLEKCIJE"
          value={`${memberCollections.length} dodate`}
        />
        <RatingStat label="LISTE" value={`${activeListCount} liste`} />
        <RatingStat label="OZNAKE" value={`${moodTags.length} tagova`} />
        <RatingStat
          label="PREPORUKE"
          value={rules.recommend ? "Uključeno" : "Isključeno"}
        />
        <RatingStat label="VIDLJIVOST" value={visibility} />
      </div>

      <div className="filmium-ratings-body">
        {/* ==========  GLAVNA KOLONA  ========== */}

        <div className="filmium-ratings-main">
          {/* ----------  ŽANROVI  ---------- */}

          <div
            className={`filmium-editor-card${
              tmdbGenres ? " tmdb-filled" : ""
            }`}
          >
            <p className="filmium-editor-block-label">ŽANROVI</p>
            <div className="filmium-cats-chips">
              {genreChips.map((genre) => {
                const on = genres.some(
                  (entry) => entry.toLowerCase() === genre.toLowerCase(),
                );
                return (
                  <button
                    className={`filmium-cats-chip${on ? " on" : ""}`}
                    key={genre}
                    onClick={() => toggleGenre(genre)}
                    type="button"
                  >
                    {on && <Check size={13} />}
                    {genre}
                  </button>
                );
              })}
            </div>
            <div className="filmium-cats-add">
              <input
                className="filmium-editor-input"
                onChange={(event) => setGenreDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.preventDefault();
                    addGenre();
                  }
                }}
                placeholder="Dodaj novi žanr…"
                value={genreDraft}
              />
              <button
                aria-label="Dodaj žanr"
                className="filmium-files-copy"
                onClick={addGenre}
                type="button"
              >
                <Plus size={15} />
              </button>
            </div>
          </div>

          {/* ----------  KOLEKCIJE  ---------- */}

          <div className="filmium-editor-card">
            <p className="filmium-editor-block-label">KOLEKCIJE</p>
            {memberCollections.length > 0 ? (
              <div className="filmium-cats-collections">
                {memberCollections.map((collection, index) => (
                  <div
                    className="filmium-cats-collection"
                    key={collection.id}
                  >
                    <div className="filmium-cats-collection-thumb">
                      <Folder size={18} />
                    </div>
                    <span className="filmium-cats-collection-name">
                      {collection.name}
                      {index === 0 && (
                        <span className="filmium-cats-main-badge">
                          Glavna kolekcija
                        </span>
                      )}
                    </span>
                    <span className="filmium-cats-collection-count">
                      {collection.item_ids.length} naslova
                    </span>
                    <button
                      className="filmium-editor-button ghost small"
                      type="button"
                    >
                      Otvori
                    </button>
                    <button
                      className="filmium-editor-button danger small"
                      type="button"
                    >
                      Ukloni
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <p className="filmium-media-empty">
                Film još nije ni u jednoj kolekciji.
              </p>
            )}

            <div className="filmium-cats-add">
              <select
                className="filmium-editor-input"
                onChange={(event) => setAddCollectionId(event.target.value)}
                value={addCollectionId}
              >
                <option value="">
                  {availableCollections.length > 0
                    ? "Izaberi kolekciju…"
                    : "Nema dostupnih kolekcija"}
                </option>
                {availableCollections.map((collection) => (
                  <option key={collection.id} value={String(collection.id)}>
                    {collection.name}
                  </option>
                ))}
              </select>
              <button
                className="filmium-editor-button primary small"
                disabled={addCollectionId === "" || !onAddToCollection}
                onClick={() => {
                  if (addCollectionId !== "" && onAddToCollection) {
                    void onAddToCollection(
                      Number(addCollectionId),
                      item.id,
                    );
                    setAddCollectionId("");
                  }
                }}
                type="button"
              >
                <Plus size={14} />
                Dodaj u kolekciju
              </button>
            </div>
          </div>

          {/* ----------  LISTE I STATUSI  ---------- */}

          <div className="filmium-editor-card">
            <p className="filmium-editor-block-label">LISTE I STATUSI</p>
            <div className="filmium-cats-lists">
              {LIST_OPTIONS.map((list) => {
                const on = lists[list] ?? false;
                return (
                  <button
                    className={`filmium-cats-list${on ? " on" : ""}`}
                    key={list}
                    onClick={() =>
                      setLists((prev) => ({ ...prev, [list]: !prev[list] }))}
                    type="button"
                  >
                    {list}
                    {on && <Check size={13} />}
                  </button>
                );
              })}
            </div>
          </div>

          {/* ----------  MOOD / TEMATSKE OZNAKE  ---------- */}

          <div className="filmium-editor-card">
            <p className="filmium-editor-block-label">
              MOOD / TEMATSKE OZNAKE
            </p>
            <TagList onChange={setMoodTags} values={moodTags} />
          </div>

          {/* ----------  AUTO-KATEGORIZACIJA  ---------- */}

          <div className="filmium-editor-card">
            <p className="filmium-editor-block-label">
              AUTO-KATEGORIZACIJA
            </p>
            <p className="filmium-media-empty">
              Predlozi na osnovu TMDB metapodataka.
            </p>
            {suggestions.length > 0 ? (
              <div className="filmium-cats-suggestions">
                {suggestions.map((suggestion) => (
                  <div
                    className="filmium-cats-suggestion"
                    key={suggestion.label}
                  >
                    <strong>{suggestion.label}</strong>
                    <span
                      className={`filmium-cats-confidence${
                        suggestion.strong ? " high" : ""
                      }`}
                    >
                      {suggestion.strong
                        ? "Visoka sigurnost"
                        : "Srednja sigurnost"}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="filmium-media-empty">
                Nema dovoljno podataka za predlog.
              </p>
            )}
            <div className="filmium-files-actions">
              <button
                className="filmium-editor-button primary small"
                onClick={() =>
                  setGenres((prev) =>
                    Array.from(
                      new Set([
                        ...prev,
                        ...suggestions
                          .map((s) => s.label.replace("Predlog: ", ""))
                          .filter((label) => genrePool.includes(label)),
                      ]),
                    ),
                  )}
                type="button"
              >
                <Check size={13} />
                Prihvati sve
              </button>
              <button
                className="filmium-editor-button ghost small"
                type="button"
              >
                <X size={13} />
                Odbaci
              </button>
            </div>
          </div>
        </div>

        {/* ==========  RAIL  ========== */}

        <aside className="filmium-ratings-rail">
          {/* ----------  DETALJI KATEGORIZACIJE  ---------- */}

          <div className="filmium-editor-card">
            <p className="filmium-editor-block-label">
              DETALJI KATEGORIZACIJE
            </p>

            <Field label="Primarni žanr">
              <select
                className="filmium-editor-input"
                onChange={(event) => setPrimaryGenre(event.target.value)}
                value={primaryGenre}
              >
                <option value="">—</option>
                {genres.map((genre) => (
                  <option key={genre} value={genre}>
                    {genre}
                  </option>
                ))}
              </select>
            </Field>

            <Field label="Glavna kolekcija">
              <select
                className="filmium-editor-input"
                onChange={(event) => setMainCollection(event.target.value)}
                value={mainCollection}
              >
                <option value="">—</option>
                {memberCollections.map((collection) => (
                  <option key={collection.id} value={collection.name}>
                    {collection.name}
                  </option>
                ))}
              </select>
            </Field>

            <Field label="Glavna lista">
              <select
                className="filmium-editor-input"
                onChange={(event) => setMainList(event.target.value)}
                value={mainList}
              >
                {LIST_OPTIONS.map((list) => (
                  <option key={list} value={list}>
                    {list}
                  </option>
                ))}
              </select>
            </Field>

            <Field label="Starosna preporuka">
              <select
                className="filmium-editor-input"
                onChange={(event) => setAgeRec(event.target.value)}
                value={ageRec}
              >
                {AGE_OPTIONS.map((age) => (
                  <option key={age} value={age}>
                    {age}
                  </option>
                ))}
              </select>
            </Field>

            <Field label="Jezik sadržaja" tmdb>
              <input
                className={
                  tmdbLang
                    ? "filmium-editor-input tmdb-filled"
                    : "filmium-editor-input"
                }
                onChange={(event) => setLanguage(event.target.value)}
                value={language}
              />
            </Field>

            <Field label="Zemlja" tmdb>
              <input
                className={
                  tmdbCountry
                    ? "filmium-editor-input tmdb-filled"
                    : "filmium-editor-input"
                }
                onChange={(event) => setCountry(event.target.value)}
                value={country}
              />
            </Field>

            <Field label="Univerzum / Franšiza">
              <input
                className="filmium-editor-input"
                onChange={(event) => setFranchise(event.target.value)}
                value={franchise}
              />
            </Field>
          </div>

          {/* ----------  PRAVILA PREPORUKA  ---------- */}

          <div className="filmium-editor-card">
            <p className="filmium-editor-block-label">PRAVILA PREPORUKA</p>
            <RatingToggle
              checked={rules.recommend ?? false}
              label="Koristi za preporuke"
              onChange={(value) =>
                setRules((prev) => ({ ...prev, recommend: value }))}
            />
            <RatingToggle
              checked={rules.similar ?? false}
              label="Prikaži u sličnim filmovima"
              onChange={(value) =>
                setRules((prev) => ({ ...prev, similar: value }))}
            />
            <RatingToggle
              checked={rules.trending ?? false}
              label="Uključi u trending"
              onChange={(value) =>
                setRules((prev) => ({ ...prev, trending: value }))}
            />
            <RatingToggle
              checked={rules.hidePublic ?? false}
              label="Sakrij iz javnih lista"
              onChange={(value) =>
                setRules((prev) => ({ ...prev, hidePublic: value }))}
            />

            <WeightSlider
              label="Sličnost po žanru"
              onChange={(value) =>
                setWeights((prev) => ({ ...prev, genre: value }))}
              value={weights.genre ?? 0}
            />
            <WeightSlider
              label="Sličnost po mood oznakama"
              onChange={(value) =>
                setWeights((prev) => ({ ...prev, mood: value }))}
              value={weights.mood ?? 0}
            />
            <WeightSlider
              label="Sličnost po kolekciji"
              onChange={(value) =>
                setWeights((prev) => ({ ...prev, collection: value }))}
              value={weights.collection ?? 0}
            />
            <WeightSlider
              label="Sličnost po univerzumu / franšizi"
              onChange={(value) =>
                setWeights((prev) => ({ ...prev, franchise: value }))}
              value={weights.franchise ?? 90}
            />
          </div>

          {/* ----------  POVEZANI SADRŽAJ  ---------- */}

          <div className="filmium-editor-card">
            <p className="filmium-editor-block-label">POVEZANI SADRŽAJ</p>
            {related.length > 0 ? (
              <div className="filmium-cats-related">
                {related.map((entry) => {
                  const url = getFilmiumAssetUrl(
                    entry.poster_path ?? entry.backdrop_path,
                  );
                  return (
                    <div className="filmium-cats-related-card" key={entry.id}>
                      <div className="filmium-cats-related-thumb">
                        {url ? (
                          <img alt="" src={url} />
                        ) : (
                          <ImageIcon size={18} />
                        )}
                      </div>
                      <strong>{entry.title}</strong>
                      <span>
                        {entry.release_year ?? "—"}
                        {entry.rating !== null
                          ? ` · ★ ${entry.rating}`
                          : ""}
                      </span>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="filmium-media-empty">
                Nema povezanih naslova iz iste kolekcije.
              </p>
            )}
            <button
              className="filmium-editor-button ghost small full"
              type="button"
            >
              <Plus size={14} />
              Dodaj povezani sadržaj
            </button>
          </div>

          <div className="filmium-ratings-visibility">
            <Field label="Vidljivost">
              <select
                className="filmium-editor-input"
                onChange={(event) => setVisibility(event.target.value)}
                value={visibility}
              >
                <option value="Privatno">Privatno</option>
                <option value="Javno">Javno</option>
              </select>
            </Field>
          </div>
        </aside>
      </div>
    </section>
  );
}

function WeightSlider({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
}) {
  return (
    <div className="filmium-cats-weight">
      <div className="filmium-cats-weight-head">
        <span>{label}</span>
        <strong>{value}%</strong>
      </div>
      <input
        className="filmium-ratings-slider"
        max={100}
        min={0}
        onChange={(event) => onChange(Number(event.target.value))}
        step={5}
        type="range"
        value={value}
      />
    </div>
  );
}


// ==========          OCENE TAB          ==========

type RatingsTabProps = {
  item: MediaItem;
  catalog: MediaItem[];
  collections: MediaCollection[];
  enrichment: FilmiumTmdbEnrichment | null;
  initialSettings?: unknown;
  onReport?: (data: unknown) => void;
};

const RATING_ASPECTS = [
  "Priča",
  "Gluma",
  "Režija",
  "Vizuelni stil",
  "Zvuk",
  "Tempo",
  "Ponovno gledanje",
] as const;

const RATING_PRIORITY_OPTS = [
  "Nizak",
  "Srednji",
  "Visok",
  "Sledeće na redu",
] as const;

const RECOMMENDATION_OPTS = [
  "Preporučujem",
  "Uslovno",
  "Ne preporučujem",
] as const;

const WATCH_STATUS_SR: Record<string, string> = {
  planned: "Planirano",
  watching: "Gleda se",
  completed: "Odgledano",
  paused: "Pauzirano",
  dropped: "Napušteno",
};

const EXTERNAL_SOURCES = [
  "IMDb",
  "TMDB",
  "Rotten Tomatoes",
  "TVmaze",
  "MAL",
  "Metacritic",
  "Letterboxd",
] as const;

/**
 * Spljošti perzistirani/enrich oblik spoljnih ocena
 * (`{ external: {<label>: {...}}, votes: {<label>: int} }`) na proste mape koje
 * čipovi „Ocene" taba koriste: ocena po izvoru (na skali 10 / procenat za RT),
 * broj glasova po izvoru i posebno publika (RT audience) za „PUBLIKA" čip.
 */
function readExternalRatings(raw: ExternalRatingsData | null | undefined): {
  scores: Record<string, number>;
  voteCounts: Record<string, number>;
  audience: number | null;
} {
  const scores: Record<string, number> = {};
  const voteCounts: Record<string, number> = {};
  let audience: number | null = null;

  const external = raw?.external ?? {};

  const imdb = external["IMDb"];
  if (imdb && typeof imdb.score === "number") {
    scores.IMDb = imdb.score;
  }
  const rt = external["Rotten Tomatoes"];
  if (rt) {
    if (typeof rt.tomatometer === "number") {
      scores["Rotten Tomatoes"] = rt.tomatometer;
    }
    if (typeof rt.audience === "number") {
      audience = rt.audience;
    }
  }
  const tvmaze = external["TVmaze"];
  if (tvmaze && typeof tvmaze.score === "number") {
    scores.TVmaze = tvmaze.score;
  }
  const mal = external["MAL"];
  if (mal && typeof mal.score === "number") {
    scores.MAL = mal.score;
  }

  const votes = raw?.votes ?? {};
  if (typeof votes["IMDb"] === "number") {
    voteCounts.IMDb = votes["IMDb"] as number;
  }

  return { scores, voteCounts, audience };
}

const QUICK_TAGS = [
  { key: "top", label: "Top film", icon: Trophy },
  { key: "recommend", label: "Za preporuku", icon: ThumbsUp },
  { key: "weak_end", label: "Slab kraj", icon: Clock },
  { key: "soundtrack", label: "Dobar soundtrack", icon: Music },
  { key: "family", label: "Za porodicu", icon: Users },
  { key: "not_for_me", label: "Nije za mene", icon: X },
] as const;

/**
 * Formatira ocenu na jednu decimalu.
 */
function fmtRating(value: number): string {
  return value.toFixed(1);
}

/**
 * „Ocene" tab: lična ocena, rejting profil, spoljne ocene i procena.
 *
 * Lična ocena i sve procene su stvarni korisnički unosi. Spoljne ocene se
 * povlače stvarno sa TMDB-a („Osveži ocene"); ostali izvori ostaju „Nije
 * povezano" dok se ne povežu — bez izmišljenih brojeva.
 */
function RatingsTab({
  item,
  catalog,
  collections,
  enrichment,
  initialSettings,
  onReport,
}: RatingsTabProps) {
  const saved = (initialSettings ?? {}) as {
    priority?: string;
    recommendation?: string;
    impression?: string;
    tags?: string[];
    profile?: Record<string, number>;
    watchDate?: string;
    watchCount?: number;
    quick?: Record<string, boolean>;
    external?: ExternalRatingsData["external"];
    votes?: ExternalRatingsData["votes"];
  };
  // Perzistirane spoljne ocene (`editor_settings.ratings.external/votes`)
  // spljoštene na čip-mape; služe kao početno stanje „Ocene" taba.
  const persistedRatings = readExternalRatings({
    external: saved.external,
    votes: saved.votes,
  });
  const [myRating, setMyRating] = useState<number>(item.rating ?? 0);
  const [priority, setPriority] = useState<string>(
    saved.priority ?? "Srednji",
  );
  const [recommendation, setRecommendation] = useState<string>(
    saved.recommendation ?? "Preporučujem",
  );
  const [impression, setImpression] = useState(saved.impression ?? "");
  const [tags, setTags] = useState<string[]>(saved.tags ?? []);
  const [profile, setProfile] = useState<Record<string, number>>(() =>
    saved.profile
      ? { ...Object.fromEntries(RATING_ASPECTS.map((a) => [a, 0])), ...saved.profile }
      : Object.fromEntries(RATING_ASPECTS.map((aspect) => [aspect, 0])),
  );
  const [status, setStatus] = useState<string>(
    WATCH_STATUS_SR[item.watch_status] ?? "Planirano",
  );
  const [watchDate, setWatchDate] = useState(saved.watchDate ?? "");
  const [watchCount, setWatchCount] = useState(saved.watchCount ?? 1);
  const [favorite, setFavorite] = useState(item.is_favorite);
  const [inCollection, setInCollection] = useState(() =>
    collections.some((collection) => collection.item_ids.includes(item.id)),
  );
  const [quick, setQuick] = useState<Record<string, boolean>>(
    saved.quick ?? {},
  );
  const [auto, setAuto] = useState<Record<string, boolean>>({
    imdb: true,
    tmdb: true,
    recommend: true,
    ranking: true,
  });

  // Prijavi stanje panelu radi snimanja u bazu (editor_settings.ratings).
  useEffect(() => {
    onReport?.({
      priority,
      recommendation,
      impression,
      tags,
      profile,
      watchDate,
      watchCount,
      quick,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    priority,
    recommendation,
    impression,
    tags,
    profile,
    watchDate,
    watchCount,
    quick,
  ]);
  const [external, setExternal] = useState<Record<string, number | null>>(
    () => ({
      ...Object.fromEntries(EXTERNAL_SOURCES.map((src) => [src, null])),
      ...persistedRatings.scores,
    }),
  );
  const [votes, setVotes] = useState<Record<string, number | null>>(
    () => ({
      ...Object.fromEntries(EXTERNAL_SOURCES.map((src) => [src, null])),
      ...persistedRatings.voteCounts,
    }),
  );
  // RT „audience" (publika) — poseban čip, stiže sa RT-a na skali 0–100.
  const [audience, setAudience] = useState<number | null>(
    () => persistedRatings.audience,
  );
  const [refreshing, setRefreshing] = useState(false);

  /**
   * Uliva enrich/persistirani `external_ratings` odgovor u čip-stanje
   * (ocene po izvoru, broj glasova, RT publika). Ne dira izvore kojih nema.
   */
  function mergeExternalResponse(
    raw: ExternalRatingsData | null | undefined,
  ): void {
    const merged = readExternalRatings(raw);
    if (Object.keys(merged.scores).length > 0) {
      setExternal((prev) => ({ ...prev, ...merged.scores }));
    }
    if (Object.keys(merged.voteCounts).length > 0) {
      setVotes((prev) => ({ ...prev, ...merged.voteCounts }));
    }
    if (merged.audience !== null) {
      setAudience(merged.audience);
    }
  }

  // TMDB ocena se automatski povlači kada se otvori „Ocene" tab.
  useEffect(() => {
    let active = true;
    enrichFilmiumMediaFromTmdb(item.id)
      .then((data) => {
        if (!active || !data.matched) {
          return;
        }
        if (data.rating) {
          setExternal((prev) => ({ ...prev, TMDB: data.rating }));
        }
        if (data.vote_count) {
          setVotes((prev) => ({ ...prev, TMDB: data.vote_count }));
        }
        mergeExternalResponse(data.external_ratings);
      })
      .catch(() => {
        /* tolerantno */
      });
    return () => {
      active = false;
    };
  }, [item.id]);

  // Primeni TMDB rezultat kada „Dopuni preko TMDB" napuni deljeni podatak —
  // tokom crtanja, po promeni props-a.
  const [ocenaPrimenjenaZa, setOcenaPrimenjenaZa] =
    useState<FilmiumTmdbEnrichment | null>(null);

  if (enrichment?.matched && enrichment !== ocenaPrimenjenaZa) {
    setOcenaPrimenjenaZa(enrichment);
    if (enrichment.rating) {
      setExternal((prev) => ({ ...prev, TMDB: enrichment.rating }));
    }
    if (enrichment.vote_count) {
      setVotes((prev) => ({ ...prev, TMDB: enrichment.vote_count }));
    }
    mergeExternalResponse(enrichment.external_ratings);
  }

  // Poređenje sa kolekcijom: stvarni članovi kolekcija kojima film pripada.
  const collectionRanking = useMemo(() => {
    const memberIds = new Set<number>();
    collections
      .filter((collection) => collection.item_ids.includes(item.id))
      .forEach((collection) =>
        collection.item_ids.forEach((id) => memberIds.add(id)),
      );
    memberIds.add(item.id);

    return catalog
      .filter(
        (candidate) =>
          memberIds.has(candidate.id) && candidate.rating !== null,
      )
      .sort(
        (first, second) => (second.rating ?? 0) - (first.rating ?? 0),
      )
      .slice(0, 8);
  }, [catalog, collections, item.id]);

  async function refreshExternal(): Promise<void> {
    setRefreshing(true);
    try {
      const data = await enrichFilmiumMediaFromTmdb(item.id);
      if (data.matched && data.rating) {
        setExternal((prev) => ({ ...prev, TMDB: data.rating }));
      }
      if (data.matched && data.vote_count) {
        setVotes((prev) => ({ ...prev, TMDB: data.vote_count }));
      }
      mergeExternalResponse(data.external_ratings);
    } catch {
      /* tolerantno: ostavi kako jeste */
    } finally {
      setRefreshing(false);
    }
  }

  const roundedStars = Math.round(myRating);

  return (
    <section className="filmium-ratings-tab">
      {/* ----------  STAT ČIPOVI  ---------- */}

      <div className="filmium-ratings-stats">
        <RatingStat
          accent
          icon={<Star fill="currentColor" size={16} />}
          label="MOJA OCENA"
          suffix="/ 10"
          value={myRating > 0 ? fmtRating(myRating) : "—"}
        />
        <RatingStat
          icon={<Star fill="currentColor" size={16} />}
          label="IMDb"
          suffix="/ 10"
          value={external.IMDb !== null ? fmtRating(external.IMDb) : "—"}
        />
        <RatingStat
          label="TMDB"
          suffix="/ 10"
          value={external.TMDB !== null ? fmtRating(external.TMDB) : "—"}
        />
        <RatingStat
          icon={<Users size={16} />}
          label="PUBLIKA"
          value={audience !== null ? `${Math.round(audience)}%` : "—"}
        />
        <RatingStat label="KRITIKA" value="—" />
        <RatingStat label="PRIORITET" value={priority} />
      </div>

      <div className="filmium-ratings-body">
        {/* ==========  GLAVNA KOLONA  ========== */}

        <div className="filmium-ratings-main">
          {/* ----------  MOJA OCENA  ---------- */}

          <div className="filmium-editor-card">
            <div className="filmium-ratings-card-head">
              <p className="filmium-editor-block-label">MOJA OCENA</p>
              <span className="filmium-ratings-hint">
                <Info size={13} />
                Kako ocenjujem?
              </span>
            </div>

            <div className="filmium-ratings-stars-row">
              <div className="filmium-ratings-stars">
                {Array.from({ length: 10 }, (_, index) => (
                  <button
                    aria-label={`Oceni ${index + 1}`}
                    className={`filmium-ratings-star${
                      index < roundedStars ? " on" : ""
                    }`}
                    key={index}
                    onClick={() => setMyRating(index + 1)}
                    type="button"
                  >
                    <Star fill="currentColor" size={26} />
                    <span>{index + 1}</span>
                  </button>
                ))}
              </div>

              <input
                className="filmium-editor-input filmium-ratings-number"
                max={10}
                min={0}
                onChange={(event) =>
                  setMyRating(Number(event.target.value))}
                step={0.1}
                type="number"
                value={myRating}
              />
            </div>

            <input
              className="filmium-ratings-slider"
              max={10}
              min={0}
              onChange={(event) => setMyRating(Number(event.target.value))}
              step={0.1}
              type="range"
              value={myRating}
            />
            <div className="filmium-ratings-slider-scale">
              <span>0</span>
              <strong>{fmtRating(myRating)}</strong>
              <span>10</span>
            </div>

            <div className="filmium-editor-field-row">
              <Field label="Prioritet gledanja">
                <select
                  className="filmium-editor-input"
                  onChange={(event) => setPriority(event.target.value)}
                  value={priority}
                >
                  {RATING_PRIORITY_OPTS.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Preporuka">
                <select
                  className="filmium-editor-input"
                  onChange={(event) =>
                    setRecommendation(event.target.value)}
                  value={recommendation}
                >
                  {RECOMMENDATION_OPTS.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </Field>
            </div>

            <Field label="Lični utisak">
              <textarea
                className="filmium-editor-input filmium-editor-textarea"
                onChange={(event) => setImpression(event.target.value)}
                rows={2}
                value={impression}
              />
            </Field>

            <Field label="Tagovi / osećaj">
              <TagList onChange={setTags} values={tags} />
            </Field>
          </div>

          {/* ----------  SPOLJNE OCENE  ---------- */}

          <div className="filmium-editor-card">
            <p className="filmium-editor-block-label">SPOLJNE OCENE</p>
            <div className="filmium-editor-episode-table">
              <table>
                <thead>
                  <tr>
                    <th>Izvor</th>
                    <th>Ocena</th>
                    <th>Broj glasova</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {EXTERNAL_SOURCES.map((source) => {
                    const value = external[source];
                    const voteCount = votes[source];
                    return (
                      <tr key={source}>
                        <td>{source}</td>
                        <td>
                          {value === null
                            ? "—"
                            : source === "Rotten Tomatoes"
                              ? `${Math.round(value)}%`
                              : `${fmtRating(value)}${
                                  source === "TMDB"
                                  || source === "IMDb"
                                  || source === "TVmaze"
                                  || source === "MAL"
                                    ? " / 10"
                                    : ""
                                }`}
                        </td>
                        <td>
                          {voteCount !== null
                            ? voteCount.toLocaleString("sr-RS")
                            : "—"}
                        </td>
                        <td>
                          <span
                            className={`filmium-files-status ${
                              value !== null ? "available" : ""
                            }`}
                          >
                            {value !== null
                              ? "Sinhronizovano"
                              : "Nije povezano"}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <div className="filmium-files-actions">
              <button
                className="filmium-editor-button ghost small"
                disabled={refreshing}
                onClick={() => void refreshExternal()}
                type="button"
              >
                <RefreshCw size={13} />
                {refreshing ? "Osvežavam…" : "Osveži ocene"}
              </button>
              <button
                className="filmium-editor-button ghost small"
                type="button"
              >
                <Pencil size={13} />
                Ručno unesi
              </button>
              <button
                className="filmium-editor-button ghost small"
                type="button"
              >
                <Link2 size={13} />
                Poveži izvor
              </button>
            </div>
            <p className="filmium-media-empty">
              TMDB se povlači automatski. IMDb, Rotten Tomatoes, Metacritic i
              Letterboxd zahtevaju sopstveni pristup (API ključ) i povezuju se
              preko „Poveži izvor".
            </p>
          </div>

          {/* ----------  POREĐENJE SA KOLEKCIJOM  ---------- */}

          <div className="filmium-editor-card">
            <p className="filmium-editor-block-label">
              POREĐENJE SA KOLEKCIJOM
            </p>
            {collectionRanking.length > 0 ? (
              <div className="filmium-ratings-rank">
                {collectionRanking.map((entry, index) => (
                  <div
                    className={`filmium-ratings-rank-row${
                      entry.id === item.id ? " active" : ""
                    }`}
                    key={entry.id}
                  >
                    <span className="filmium-ratings-rank-num">
                      {index + 1}
                    </span>
                    <span className="filmium-ratings-rank-name">
                      {entry.title}
                    </span>
                    <span className="filmium-ratings-rank-score">
                      {entry.rating !== null
                        ? fmtRating(entry.rating)
                        : "—"}
                      <Star fill="currentColor" size={12} />
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="filmium-media-empty">
                Film nije u kolekciji sa drugim ocenjenim naslovima.
              </p>
            )}
          </div>
        </div>

        {/* ==========  RAIL  ========== */}

        <aside className="filmium-ratings-rail">
          {/* ----------  REJTING PROFIL  ---------- */}

          <div className="filmium-editor-card">
            <p className="filmium-editor-block-label">REJTING PROFIL</p>
            {RATING_ASPECTS.map((aspect) => (
              <div className="filmium-ratings-aspect" key={aspect}>
                <span className="filmium-ratings-aspect-label">
                  {aspect}
                </span>
                <input
                  className="filmium-ratings-aspect-slider"
                  max={10}
                  min={0}
                  onChange={(event) =>
                    setProfile((prev) => ({
                      ...prev,
                      [aspect]: Number(event.target.value),
                    }))}
                  step={0.1}
                  type="range"
                  value={profile[aspect] ?? 0}
                />
                <span className="filmium-ratings-aspect-value">
                  {fmtRating(profile[aspect] ?? 0)}
                </span>
              </div>
            ))}
          </div>

          {/* ----------  STATUS GLEDANJA  ---------- */}

          <div className="filmium-editor-card">
            <p className="filmium-editor-block-label">STATUS GLEDANJA</p>

            <Field label="Status">
              <select
                className="filmium-editor-input"
                onChange={(event) => setStatus(event.target.value)}
                value={status}
              >
                {Object.values(WATCH_STATUS_SR).map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </Field>

            <Field label="Datum gledanja">
              <input
                className="filmium-editor-input"
                onChange={(event) => setWatchDate(event.target.value)}
                placeholder="DD.MM.GGGG"
                value={watchDate}
              />
            </Field>

            <div className="filmium-ratings-stepper-row">
              <span>Broj gledanja</span>
              <div className="filmium-ratings-stepper">
                <button
                  onClick={() =>
                    setWatchCount((count) => Math.max(0, count - 1))}
                  type="button"
                >
                  <Minus size={14} />
                </button>
                <strong>{watchCount}</strong>
                <button
                  onClick={() => setWatchCount((count) => count + 1)}
                  type="button"
                >
                  <Plus size={14} />
                </button>
              </div>
            </div>

            <RatingToggle
              checked={favorite}
              label="Omiljeni film"
              onChange={setFavorite}
            />
            <RatingToggle
              checked={inCollection}
              label="U kolekciji"
              onChange={setInCollection}
            />
          </div>

          {/* ----------  BRZA PROCENA  ---------- */}

          <div className="filmium-editor-card">
            <p className="filmium-editor-block-label">BRZA PROCENA</p>
            <div className="filmium-ratings-quick">
              {QUICK_TAGS.map((tag) => {
                const Icon = tag.icon;
                return (
                  <button
                    className={`filmium-ratings-quick-tag${
                      quick[tag.key] ? " on" : ""
                    }`}
                    key={tag.key}
                    onClick={() =>
                      setQuick((prev) => ({
                        ...prev,
                        [tag.key]: !prev[tag.key],
                      }))}
                    type="button"
                  >
                    <Icon size={14} />
                    {tag.label}
                  </button>
                );
              })}
            </div>
            <button
              className="filmium-editor-button primary full"
              type="button"
            >
              <Save size={14} />
              Sačuvaj procenu
            </button>
          </div>

          {/* ----------  AUTOMATIKA  ---------- */}

          <div className="filmium-editor-card">
            <p className="filmium-editor-block-label">AUTOMATIKA</p>
            <RatingToggle
              checked={auto.imdb ?? false}
              label="Automatski osveži IMDb"
              onChange={(value) =>
                setAuto((prev) => ({ ...prev, imdb: value }))}
            />
            <RatingToggle
              checked={auto.tmdb ?? false}
              label="Automatski osveži TMDB"
              onChange={(value) =>
                setAuto((prev) => ({ ...prev, tmdb: value }))}
            />
            <RatingToggle
              checked={auto.recommend ?? false}
              label="Uključi u preporuke"
              onChange={(value) =>
                setAuto((prev) => ({ ...prev, recommend: value }))}
            />
            <RatingToggle
              checked={auto.ranking ?? false}
              label="Koristi za rangiranje"
              onChange={(value) =>
                setAuto((prev) => ({ ...prev, ranking: value }))}
            />
          </div>
        </aside>
      </div>
    </section>
  );
}

function RatingStat({
  label,
  value,
  suffix,
  icon,
  accent,
}: {
  label: string;
  value: string;
  suffix?: string;
  icon?: ReactNode;
  accent?: boolean;
}) {
  return (
    <div
      className={`filmium-ratings-stat${accent ? " accent" : ""}`}
    >
      <span className="filmium-ratings-stat-top">
        {icon}
        {label}
      </span>
      <strong>
        {value}
        {suffix && <em>{suffix}</em>}
      </strong>
    </div>
  );
}

function RatingToggle({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <label className="filmium-ratings-toggle">
      <span>{label}</span>
      <input
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        type="checkbox"
      />
    </label>
  );
}


// ==========          FAJLOVI TAB          ==========

type FilesTabProps = {
  item: MediaItem;
  sources: FilmiumMediaSource[];
};

const FILE_STATUS_TEXT: Record<string, string> = {
  available: "Dostupno",
  offline: "Van mreže",
  missing: "Nedostaje",
};

/**
 * Naziv fajla iz putanje (podržava / i \\).
 */
function fileName(path: string): string {
  return path.split(/[\\/]/).pop() ?? path;
}

/**
 * Ekstenzija fajla velikim slovima (npr. „MKV").
 */
function fileExt(path: string): string {
  const name = fileName(path);
  const dot = name.lastIndexOf(".");
  return dot > 0 ? name.slice(dot + 1).toUpperCase() : "—";
}

/**
 * Spaja delove putanje u „/" oblik.
 */
function joinPath(...parts: (string | null | undefined)[]): string {
  return parts
    .filter((part): part is string => Boolean(part))
    .join("/")
    .replace(/\\/g, "/")
    .replace(/\/{2,}/g, "/");
}

/**
 * Čitljivo trajanje iz minuta.
 */
function runtimeText(minutes: number | null): string {
  if (!minutes || minutes <= 0) {
    return "—";
  }
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  if (hours === 0) {
    return `${rest}m`;
  }
  return rest === 0 ? `${hours}h` : `${hours}h ${rest}m`;
}

/**
 * Prijateljski naziv rezolucije iz visine (npr. 2160 → „4K UHD").
 */
function qualityFromHeight(height: number | null): string {
  if (!height) {
    return "—";
  }
  if (height >= 2000) {
    return "4K UHD";
  }
  if (height >= 1400) {
    return "1440p";
  }
  if (height >= 1000) {
    return "1080p";
  }
  if (height >= 700) {
    return "720p";
  }
  return `${height}p`;
}

/**
 * Oznaka audio kanala (6 → „5.1", 8 → „7.1", 2 → „2.0").
 */
function channelsLabel(channels: number): string {
  if (channels === 8) {
    return "7.1";
  }
  if (channels === 6) {
    return "5.1";
  }
  if (channels >= 1) {
    return `${channels}.0`;
  }
  return String(channels);
}

/**
 * Izvor kvaliteta iz naziva fajla (WEB-DL, BluRay, HDTV, WEBRip...).
 */
function sourceQualityFromName(name: string | undefined): string {
  if (!name) {
    return "—";
  }
  const upper = name.toUpperCase();
  const tokens = [
    "WEB-DL",
    "WEBRIP",
    "BLURAY",
    "BLU-RAY",
    "BRRIP",
    "BDRIP",
    "HDTV",
    "DVDRIP",
    "REMUX",
    "WEB",
    "CAM",
  ];
  for (const token of tokens) {
    if (upper.includes(token)) {
      return token === "BLURAY" ? "BluRay" : token;
    }
  }
  return "—";
}

type FileVersion = {
  fileId: number;
  source: FilmiumMediaSource;
  name: string;
  format: string;
  sizeBytes: number;
  fileStatus: string;
  path: string;
};

/**
 * „Fajlovi" tab: glavni video fajl, verzije, audio, provera, fascikle.
 *
 * Sve iz stvarnih registrovanih izvora/fajlova. Polja koja se još ne
 * skladište (codec, bitrate, FPS, HDR, checksum) prikazuju „—" dok
 * probe/scan ne budu popunjavali te podatke.
 */
function FilesTab({ item, sources }: FilesTabProps) {
  const versions = useMemo<FileVersion[]>(
    () =>
      sources.flatMap((source) =>
        source.files
          .filter((file) => file.role === "video")
          .map((file) => ({
            fileId: file.id,
            source,
            name: fileName(file.relative_path),
            format: fileExt(file.relative_path),
            sizeBytes: file.size_bytes,
            fileStatus: file.file_status,
            path: joinPath(
              source.root_path_snapshot,
              source.relative_directory,
              file.relative_path,
            ),
          })),
      ),
    [sources],
  );

  const subtitleLangs = useMemo(
    () =>
      Array.from(
        new Set(
          sources
            .flatMap((source) => source.files)
            .filter((file) => file.role === "subtitle")
            .map((file) => (file.language ?? "").toUpperCase())
            .filter(Boolean),
        ),
      ),
    [sources],
  );

  const hasTrailer = useMemo(
    () =>
      sources
        .flatMap((source) => source.files)
        .some((file) => file.role === "trailer"),
    [sources],
  );

  const [selectedId, setSelectedId] = useState<number | null>(
    versions[0]?.fileId ?? null,
  );
  const [autoScan, setAutoScan] = useState<Record<string, boolean>>({
    follow: true,
    metadata: true,
    subtitles: true,
    thumbnail: true,
  });
  const [copied, setCopied] = useState(false);
  const [tech, setTech] = useState<FilmiumTechnical | null>(null);

  useEffect(() => {
    let active = true;
    getFilmiumMediaTechnical(item.id)
      .then((data) => {
        if (active) {
          setTech(data);
        }
      })
      .catch(() => {
        if (active) {
          setTech(null);
        }
      });
    return () => {
      active = false;
    };
  }, [item.id]);

  const selected =
    versions.find((version) => version.fileId === selectedId)
    ?? versions[0]
    ?? null;

  const totalSize = versions.reduce(
    (sum, version) => sum + version.sizeBytes,
    0,
  );

  const checks: { label: string; ok: boolean }[] = [
    { label: "Fajl postoji", ok: selected?.fileStatus === "available" },
    { label: "Metadata učitan", ok: selected !== null },
    {
      label: "Trajanje poklapa",
      ok: item.runtime_minutes !== null,
    },
    { label: "Titlovi pronađeni", ok: subtitleLangs.length > 0 },
    { label: "Poster/backdrop", ok: item.poster_path !== null },
    { label: "Lokalni trailer", ok: hasTrailer },
  ];

  async function copyPath(): Promise<void> {
    if (!selected) {
      return;
    }
    try {
      await navigator.clipboard.writeText(selected.path);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  }

  const subtitleLabel =
    subtitleLangs.length > 0 ? subtitleLangs.join(" / ") : "—";

  // Prikazne vrednosti iz ffprobe-a (kad su dostupne).
  const found = tech?.found ?? false;
  const resolutionText =
    tech?.width && tech?.height ? `${tech.width} x ${tech.height}` : "—";
  const qualityText = qualityFromHeight(tech?.height ?? null);
  const fpsText =
    tech?.frame_rate ? String(Math.round(tech.frame_rate * 100) / 100) : "—";
  const bitrateText =
    tech?.bit_rate ? `${(tech.bit_rate / 1_000_000).toFixed(1)} Mbps` : "—";
  const hdrText = found ? (tech?.is_hdr ? "Da" : "Ne") : "—";
  const videoText = tech?.video_codec ?? "—";
  const audioText = tech?.audio_codec
    ? `${tech.audio_codec}${
        tech.audio_channels ? ` ${channelsLabel(tech.audio_channels)}` : ""
      }`
    : "—";
  const sourceQuality = sourceQualityFromName(selected?.name);
  const durationText =
    item.runtime_minutes !== null
      ? runtimeText(item.runtime_minutes)
      : tech?.duration_seconds
        ? runtimeText(Math.round(tech.duration_seconds / 60))
        : "—";

  return (
    <section className="filmium-files-tab">
      {/* ----------  STAT ČIPOVI  ---------- */}

      <div className="filmium-files-stats">
        <FileStat
          label="Glavni fajl"
          value={selected ? "Pronađen" : "Nedostaje"}
          tone={selected ? "ok" : "warn"}
        />
        <FileStat label="Rezolucija" value={qualityText} />
        <FileStat
          label="Veličina"
          value={totalSize > 0 ? (formatSize(totalSize) || "—") : "—"}
        />
        <FileStat label="Trajanje" value={durationText} />
        <FileStat label="Kvalitet" value={sourceQuality} />
        <FileStat
          label="Provera"
          value={selected?.fileStatus === "available" ? "OK" : "Proveri"}
          tone={selected?.fileStatus === "available" ? "ok" : "warn"}
        />
      </div>

      <div className="filmium-files-body">
        <div className="filmium-files-main">
          {/* ----------  GLAVNI VIDEO FAJL  ---------- */}

          <div className="filmium-editor-card">
            <p className="filmium-editor-block-label">GLAVNI VIDEO FAJL</p>

            <div className="filmium-files-path-row">
              <input
                className="filmium-editor-input"
                readOnly
                value={selected?.path ?? "Nema registrovanog video fajla"}
              />
              <button
                aria-label="Kopiraj putanju"
                className="filmium-files-copy"
                disabled={!selected}
                onClick={() => void copyPath()}
                type="button"
              >
                {copied ? <Check size={15} /> : <Copy size={15} />}
              </button>
            </div>

            <div className="filmium-files-actions">
              <button
                className="filmium-editor-button ghost small"
                type="button"
              >
                <Folder size={13} />
                Izaberi fajl
              </button>
              <button
                className="filmium-editor-button ghost small"
                type="button"
              >
                <FolderOpen size={13} />
                Otvori lokaciju
              </button>
              <button
                className="filmium-editor-button ghost small"
                type="button"
              >
                <Check size={13} />
                Proveri fajl
              </button>
              <button
                className="filmium-editor-button ghost small"
                type="button"
              >
                <Play size={13} />
                Pusti test
              </button>
            </div>

            <div className="filmium-files-tech">
              <FileTech label="Format" value={selected?.format ?? "—"} />
              <FileTech label="Video" value={videoText} />
              <FileTech label="Rezolucija" value={resolutionText} />
              <FileTech label="FPS" value={fpsText} />
              <FileTech label="Bitrate" value={bitrateText} />
              <FileTech label="HDR" value={hdrText} />
              <FileTech label="Audio" value={audioText} />
              <FileTech label="Titlovi" value={subtitleLabel} />
            </div>

            {tech && !tech.available && (
              <p className="filmium-media-empty">
                ffprobe nije dostupan na sistemu — tehnički podaci se ne
                mogu očitati.
              </p>
            )}
            {tech?.available && !tech.found && (
              <p className="filmium-media-empty">
                Video fajl nije pronađen na disku za očitavanje podataka.
              </p>
            )}
          </div>

          {/* ----------  VERZIJE FAJLA  ---------- */}

          <div className="filmium-editor-card">
            <p className="filmium-editor-block-label">VERZIJE FAJLA</p>
            <div className="filmium-editor-episode-table">
              <table>
                <thead>
                  <tr>
                    <th>Naziv fajla</th>
                    <th>Status</th>
                    <th>Veličina</th>
                    <th>Format</th>
                    <th>Akcije</th>
                  </tr>
                </thead>
                <tbody>
                  {versions.map((version) => (
                    <tr
                      className={
                        selectedId === version.fileId ? "selected" : ""
                      }
                      key={version.fileId}
                    >
                      <td>{version.name}</td>
                      <td>
                        <span
                          className={`filmium-files-status ${version.fileStatus}`}
                        >
                          {FILE_STATUS_TEXT[version.fileStatus]
                            ?? version.fileStatus}
                        </span>
                      </td>
                      <td>{formatSize(version.sizeBytes) || "—"}</td>
                      <td>{version.format}</td>
                      <td>
                        <div className="filmium-files-row-actions">
                          <button
                            className="filmium-editor-row-edit"
                            onClick={() => setSelectedId(version.fileId)}
                            type="button"
                          >
                            Izaberi
                          </button>
                          <button
                            className="filmium-editor-row-edit danger"
                            type="button"
                          >
                            <Trash2 size={13} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}

                  {versions.length === 0 && (
                    <tr>
                      <td className="empty" colSpan={5}>
                        Nema registrovanih video fajlova.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
            <button
              className="filmium-editor-button ghost small"
              type="button"
            >
              <Plus size={14} />
              Dodaj verziju
            </button>
          </div>

          {/* ----------  AUDIO TRACKOVI  ---------- */}

          <div className="filmium-editor-card">
            <p className="filmium-editor-block-label">AUDIO TRACKOVI</p>
            <p className="filmium-media-empty">
              Audio trackovi se prikazuju kada ih scan/probe evidentira.
            </p>
            <button
              className="filmium-editor-button ghost small"
              type="button"
            >
              <Plus size={14} />
              Dodaj audio
            </button>
          </div>

          {/* ----------  PROVERA FAJLA  ---------- */}

          <div className="filmium-editor-card">
            <p className="filmium-editor-block-label">PROVERA FAJLA</p>
            <div className="filmium-files-checks">
              {checks.map((check) => (
                <span
                  className={`filmium-files-check${
                    check.ok ? " ok" : " warn"
                  }`}
                  key={check.label}
                >
                  {check.ok ? (
                    <Check size={15} />
                  ) : (
                    <TriangleAlert size={15} />
                  )}
                  {check.label}
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* ----------  DETALJI IZABRANE VERZIJE  ---------- */}

        <aside className="filmium-files-rail">
          <div className="filmium-editor-card">
            <p className="filmium-editor-block-label">
              DETALJI IZABRANE VERZIJE
            </p>

            <FileDetailRow label="Naziv fajla" value={selected?.name} />
            <FileDetailRow
              label="Format"
              value={selected?.format}
            />
            <FileDetailRow
              label="Putanja"
              value={selected?.path}
              mono
            />
            <FileDetailRow label="Checksum" value={null} />
            <FileDetailRow
              label="Datum dodavanja"
              value={
                selected
                  ? formatEditorDate(selected.source.created_at)
                  : null
              }
            />
            <FileDetailRow
              label="Poslednja provera"
              value={
                selected
                  ? formatEditorDate(selected.source.last_verified_at)
                  : null
              }
            />
            <FileDetailRow
              label="Status"
              value={
                selected
                  ? FILE_STATUS_TEXT[selected.source.availability_status]
                    ?? selected.source.availability_status
                  : null
              }
            />
          </div>

          <button
            className="filmium-editor-button primary full"
            disabled={!selected}
            type="button"
          >
            <Save size={14} />
            Sačuvaj verziju
          </button>
          <button
            className="filmium-editor-button ghost full"
            type="button"
          >
            <RefreshCw size={14} />
            Zameni fajl
          </button>
          <button
            className="filmium-editor-button danger full"
            disabled={!selected}
            type="button"
          >
            <Trash2 size={14} />
            Ukloni verziju
          </button>
        </aside>
      </div>

      {/* ----------  FASCIKLE + AUTO SKENIRANJE  ---------- */}

      <div className="filmium-files-bottom">
        <div className="filmium-editor-card">
          <p className="filmium-editor-block-label">LOKALNE FASCIKLE</p>
          <FolderRow
            label="Film"
            path={
              selected
                ? joinPath(
                    selected.source.root_path_snapshot,
                    selected.source.relative_directory,
                  )
                : null
            }
          />
          <FolderRow label="Titlovi" path={null} />
          <FolderRow label="Poster" path={null} />
          <FolderRow label="Trailer" path={null} />
        </div>

        <div className="filmium-editor-card">
          <p className="filmium-editor-block-label">AUTOMATSKO SKENIRANJE</p>
          <div className="filmium-files-toggles">
            <ScanToggle
              checked={autoScan.follow ?? false}
              label="Prati folder"
              onChange={(value) =>
                setAutoScan((prev) => ({ ...prev, follow: value }))}
            />
            <ScanToggle
              checked={autoScan.metadata ?? false}
              label="Automatski učitaj metadata"
              onChange={(value) =>
                setAutoScan((prev) => ({ ...prev, metadata: value }))}
            />
            <ScanToggle
              checked={autoScan.subtitles ?? false}
              label="Prepoznaj titlove"
              onChange={(value) =>
                setAutoScan((prev) => ({ ...prev, subtitles: value }))}
            />
            <ScanToggle
              checked={autoScan.thumbnail ?? false}
              label="Generiši thumbnail"
              onChange={(value) =>
                setAutoScan((prev) => ({ ...prev, thumbnail: value }))}
            />
          </div>
          <button
            className="filmium-editor-button ghost full"
            type="button"
          >
            <RefreshCw size={14} />
            Pokreni rescan
          </button>
        </div>
      </div>
    </section>
  );
}

/**
 * Čitljiv datum za editor (ISO → lokalni), ili „—".
 */
function formatEditorDate(value: string | null): string | null {
  if (!value) {
    return null;
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return null;
  }
  return new Intl.DateTimeFormat("sr-Latn-RS", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(parsed);
}

function FileStat({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "ok" | "warn";
}) {
  return (
    <div className="filmium-files-stat">
      <span className="filmium-files-stat-label">{label}</span>
      <strong
        className={
          tone ? `filmium-files-stat-value ${tone}` : "filmium-files-stat-value"
        }
      >
        {value}
      </strong>
    </div>
  );
}

function FileTech({ label, value }: { label: string; value: string }) {
  return (
    <div className="filmium-files-tech-cell">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function FileDetailRow({
  label,
  value,
  mono,
}: {
  label: string;
  value?: string | null;
  mono?: boolean;
}) {
  return (
    <div className="filmium-files-detail-row">
      <span>{label}</span>
      <strong className={mono ? "mono" : ""}>{value || "—"}</strong>
    </div>
  );
}

function FolderRow({
  label,
  path,
}: {
  label: string;
  path: string | null;
}) {
  return (
    <div className="filmium-files-folder">
      <Folder size={15} />
      <span className="filmium-files-folder-label">{label}</span>
      <code>{path ?? "—"}</code>
      <button
        className="filmium-editor-button ghost small"
        disabled={!path}
        type="button"
      >
        Otvori
      </button>
    </div>
  );
}

function ScanToggle({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <label className="filmium-files-toggle">
      <span>{label}</span>
      <input
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        type="checkbox"
      />
    </label>
  );
}


// ==========          MEDIJI TAB          ==========

type MediaTabProps = {
  item: MediaItem;
  posterUrl: string | null;
  backdropUrl: string | null;
  hasPoster: boolean;
  hasBackdrop: boolean;
};

type GalleryImage = {
  id: string;
  kind: string;
  url: string | null;
  name: string;
};

const IMAGE_CATEGORY_LABELS: Record<string, string> = {
  poster: "Poster",
  backdrop: "Backdrop",
  wallpaper: "Wallpaper",
  fanart: "Fanart",
};

/**
 * Vraća naziv fajla iz relativne putanje.
 */
function baseName(path: string | null): string {
  if (!path) {
    return "";
  }
  return path.split("/").pop() ?? path;
}

/**
 * „Mediji" tab: poster, backdrop, galerija, upload, trejler i logo.
 *
 * Galerija koristi stvarne slike iz biblioteke (poster/backdrop). Dodatne
 * kategorije (wallpaper/fanart/screenshot) dobijaju svoje slike kada budu
 * podržane u asset skladištu.
 */
function MediaTab({
  item,
  posterUrl,
  backdropUrl,
  hasPoster,
  hasBackdrop,
}: MediaTabProps) {
  const images = useMemo<GalleryImage[]>(() => {
    const list: GalleryImage[] = [];
    if (hasPoster) {
      list.push({
        id: "poster",
        kind: "Poster",
        url: posterUrl,
        name: baseName(item.poster_path),
      });
    }
    if (hasBackdrop) {
      list.push({
        id: "backdrop",
        kind: "Backdrop",
        url: backdropUrl,
        name: baseName(item.backdrop_path),
      });
    }
    return list;
  }, [
    hasPoster,
    hasBackdrop,
    posterUrl,
    backdropUrl,
    item.poster_path,
    item.backdrop_path,
  ]);

  const [selectedId, setSelectedId] = useState<string | null>(
    images[0]?.id ?? null,
  );
  const [primaryId, setPrimaryId] = useState<string | null>(
    hasPoster ? "poster" : null,
  );
  const [trailerUrl, setTrailerUrl] = useState("");
  const [trailerAdded, setTrailerAdded] = useState(false);
  const [categories, setCategories] = useState<
    Record<string, boolean>
  >({
    poster: false,
    backdrop: false,
    wallpaper: true,
    fanart: true,
  });

  const selected =
    images.find((image) => image.id === selectedId) ?? images[0] ?? null;

  return (
    <section className="filmium-media-tab">
      {/* ----------  GLAVNE SLIKE + DETALJI  ---------- */}

      <div className="filmium-media-main">
        <div className="filmium-media-assets">
          <AssetCard
            label="POSTER"
            ok={hasPoster}
            ratio="2 : 3"
            url={posterUrl}
            variant="poster"
            onPrimary={() => setPrimaryId("poster")}
            editLabel="Izmeni poster"
          />

          <AssetCard
            label="BACKDROP"
            ok={hasBackdrop}
            ratio="16 : 9"
            url={backdropUrl}
            variant="backdrop"
            onPrimary={() => setPrimaryId("backdrop")}
            editLabel="Izmeni backdrop"
          />
        </div>

        {/* ----------  GALERIJA  ---------- */}

        <div className="filmium-media-gallery">
          <span className="filmium-editor-block-label">
            WALLPAPER / FANART / SCREENSHOTOVI
          </span>

          <div className="filmium-media-gallery-grid">
            {images.map((image) => (
              <button
                className={`filmium-media-gallery-card${
                  selectedId === image.id ? " active" : ""
                }`}
                key={image.id}
                onClick={() => setSelectedId(image.id)}
                type="button"
              >
                <div className="filmium-media-gallery-thumb">
                  {image.url ? (
                    <img alt="" src={image.url} />
                  ) : (
                    <ImageIcon size={20} />
                  )}
                  {primaryId === image.id && (
                    <span className="filmium-media-primary-badge">
                      Glavna
                    </span>
                  )}
                </div>
                <div className="filmium-media-gallery-meta">
                  <strong>{image.kind}</strong>
                  <span>{image.name || "—"}</span>
                </div>
              </button>
            ))}

            <button
              className="filmium-media-gallery-add"
              type="button"
            >
              <Plus size={18} />
              Dodaj novu sliku
            </button>
          </div>
        </div>
      </div>

      {/* ----------  DETALJI SLIKE  ---------- */}

      <aside className="filmium-media-detail-card">
        <span className="filmium-editor-block-label">DETALJI SLIKE</span>

        <div className="filmium-media-detail-preview">
          {selected?.url ? (
            <img alt="" src={selected.url} />
          ) : (
            <ImageIcon size={26} />
          )}
          {selected && primaryId === selected.id && (
            <span className="filmium-media-primary-badge">Glavna</span>
          )}
        </div>

        {selected ? (
          <dl className="filmium-media-detail-list">
            <div>
              <dt>Naziv fajla</dt>
              <dd>{selected.name || "—"}</dd>
            </div>
            <div>
              <dt>Tip slike</dt>
              <dd>{selected.kind}</dd>
            </div>
            <div>
              <dt>Izvor</dt>
              <dd>Biblioteka</dd>
            </div>
          </dl>
        ) : (
          <p className="filmium-media-empty">
            Nema izabrane slike u galeriji.
          </p>
        )}

        <div className="filmium-media-cats">
          {Object.keys(IMAGE_CATEGORY_LABELS).map((key) => (
            <label className="filmium-editor-toggle" key={key}>
              <input
                checked={categories[key] ?? false}
                onChange={(event) =>
                  setCategories((prev) => ({
                    ...prev,
                    [key]: event.target.checked,
                  }))}
                type="checkbox"
              />
              {IMAGE_CATEGORY_LABELS[key]}
            </label>
          ))}
        </div>

        <button
          className="filmium-editor-button primary full"
          disabled={!selected}
          type="button"
        >
          <Check size={14} />
          Sačuvaj izmene
        </button>
        <button
          className="filmium-editor-button ghost full"
          disabled={!selected}
          type="button"
        >
          <ImageIcon size={14} />
          Zameni sliku
        </button>
        <button
          className="filmium-editor-button danger full"
          disabled={!selected}
          type="button"
        >
          <Trash2 size={14} />
          Obriši
        </button>
      </aside>

      {/* ----------  UPLOAD / TREJLER / LOGO  ---------- */}

      <div className="filmium-media-extra">
        <div className="filmium-media-extra-card">
          <span className="filmium-editor-block-label">UPLOAD SLIKA</span>
          <div className="filmium-media-dropzone">
            <UploadCloud size={26} />
            <p>Prevuci slike ovde ili klikni za upload</p>
            <div className="filmium-media-pills">
              <span>Poster 2:3</span>
              <span>Backdrop 16:9</span>
              <span>JPG / PNG / WEBP</span>
            </div>
          </div>
        </div>

        <div className="filmium-media-extra-card">
          <span className="filmium-editor-block-label">
            TRAILER I VIDEO MATERIJALI
          </span>
          <div className="filmium-media-trailer">
            <div className="filmium-media-trailer-thumb">
              {backdropUrl && <img alt="" src={backdropUrl} />}
              <span className="filmium-media-play">
                <Play fill="currentColor" size={18} />
              </span>
            </div>
            <div className="filmium-media-trailer-form">
              <label className="filmium-editor-field">
                <span className="filmium-editor-field-label">
                  Trailer URL
                </span>
                <input
                  className={
                    trailerAdded
                      ? "filmium-editor-input filmium-media-input-ok"
                      : "filmium-editor-input"
                  }
                  onChange={(event) => {
                    setTrailerUrl(event.target.value);
                    setTrailerAdded(false);
                  }}
                  placeholder="https://www.youtube.com/watch?v=…"
                  value={trailerUrl}
                />
              </label>

              {trailerAdded && (
                <span className="filmium-media-trailer-ok">
                  <Check size={13} />
                  Trailer link dodat.
                </span>
              )}

              <div className="filmium-media-trailer-actions">
                <button
                  className="filmium-editor-button primary small"
                  disabled={trailerUrl.trim() === ""}
                  onClick={() => {
                    if (trailerUrl.trim() !== "") {
                      setTrailerAdded(true);
                    }
                  }}
                  type="button"
                >
                  <Plus size={13} />
                  Dodaj trailer
                </button>
                <button
                  className="filmium-editor-button ghost small"
                  disabled={trailerUrl.trim() === ""}
                  type="button"
                >
                  <Play size={13} />
                  Pregledaj trailer
                </button>
              </div>
            </div>
          </div>
        </div>

        <div className="filmium-media-extra-card">
          <span className="filmium-editor-block-label">
            LOGO / TRANSPARENTNI ELEMENTI
          </span>
          <div className="filmium-media-logos">
            <div className="filmium-media-logo-slot">
              <span>Clear logo</span>
              <div className="filmium-media-logo-box">
                <ImageIcon size={20} />
              </div>
            </div>
            <div className="filmium-media-logo-slot">
              <span>Title card</span>
              <div className="filmium-media-logo-box">
                {posterUrl ? (
                  <img alt="" src={posterUrl} />
                ) : (
                  <ImageIcon size={20} />
                )}
              </div>
            </div>
          </div>
          <button
            className="filmium-editor-button ghost full"
            type="button"
          >
            <Plus size={14} />
            Dodaj logo
          </button>
        </div>
      </div>
    </section>
  );
}

type AssetCardProps = {
  label: string;
  ok: boolean;
  ratio: string;
  url: string | null;
  variant: "poster" | "backdrop";
  editLabel: string;
  onPrimary: () => void;
};

/**
 * Kartica glavne slike (poster ili backdrop) sa akcijama.
 */
function AssetCard({
  label,
  ok,
  ratio,
  url,
  variant,
  editLabel,
  onPrimary,
}: AssetCardProps) {
  return (
    <div className="filmium-media-asset-card">
      <div className="filmium-media-asset-head">
        <span className="filmium-editor-block-label">{label}</span>
        {ok ? (
          <span className="filmium-media-ok">OK</span>
        ) : (
          <TmdbBadge />
        )}
      </div>

      <div className="filmium-media-asset-body">
        <div className={`filmium-media-asset-thumb ${variant}`}>
          {url ? <img alt="" src={url} /> : <ImageIcon size={26} />}
        </div>

        <div className="filmium-media-asset-side">
          <span className="filmium-media-asset-ratio">{ratio}</span>
          <button
            className="filmium-editor-button primary small full"
            type="button"
          >
            <Pencil size={13} />
            {editLabel}
          </button>
          <button
            className="filmium-editor-button ghost small full"
            onClick={onPrimary}
            type="button"
          >
            <Star size={13} />
            Postavi kao glavni
          </button>
          <button
            className="filmium-editor-button danger small full"
            type="button"
          >
            <Trash2 size={13} />
            Ukloni
          </button>
        </div>
      </div>
    </div>
  );
}


// ==========          EPISODE EDITOR MODAL          ==========

type EpisodeEditorModalProps = {
  episode: EpisodeDraft;
  onClose: () => void;
};

/**
 * Manji editor jedne epizode unutar panela.
 */
function EpisodeEditorModal({
  episode,
  onClose,
}: EpisodeEditorModalProps) {
  const [title, setTitle] = useState(episode.title);
  const [description, setDescription] = useState("");
  const [seasonNumber, setSeasonNumber] = useState(
    String(episode.seasonNumber),
  );
  const [episodeNumber, setEpisodeNumber] = useState(
    String(episode.episodeNumber),
  );
  const [runtime, setRuntime] = useState(
    episode.runtimeMinutes ? String(episode.runtimeMinutes) : "",
  );
  const [airDate, setAirDate] = useState("");
  const [resolution, setResolution] = useState("4K");
  const [audio, setAudio] = useState("SR / EN");
  const [subtitles, setSubtitles] = useState("SR");
  const [rating, setRating] = useState("");
  const [status, setStatus] = useState(episode.status);
  const [note, setNote] = useState("");

  useEffect(() => {
    function handleKey(event: KeyboardEvent): void {
      if (event.key === "Escape") {
        onClose();
      }
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [onClose]);

  return (
    <div
      className="filmium-episode-modal-overlay"
      onClick={onClose}
      role="presentation"
    >
      <div
        className="filmium-episode-modal"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
      >
        <header className="filmium-episode-modal-head">
          <h3>Uredi epizodu</h3>
          <button
            aria-label="Zatvori"
            onClick={onClose}
            type="button"
          >
            <X size={16} />
          </button>
        </header>

        <div className="filmium-episode-modal-body">
          <Field label="Naslov epizode">
            <input
              className="filmium-editor-input"
              onChange={(event) => setTitle(event.target.value)}
              value={title}
            />
          </Field>

          <Field label="Opis epizode">
            <textarea
              className="filmium-editor-input filmium-editor-textarea"
              onChange={(event) => setDescription(event.target.value)}
              rows={3}
              value={description}
            />
          </Field>

          <div className="filmium-editor-field-row">
            <Field label="Broj sezone">
              <input
                className="filmium-editor-input"
                onChange={(event) => setSeasonNumber(event.target.value)}
                value={seasonNumber}
              />
            </Field>
            <Field label="Broj epizode">
              <input
                className="filmium-editor-input"
                onChange={(event) =>
                  setEpisodeNumber(event.target.value)}
                value={episodeNumber}
              />
            </Field>
            <Field label="Trajanje">
              <input
                className="filmium-editor-input"
                onChange={(event) => setRuntime(event.target.value)}
                value={runtime}
              />
            </Field>
          </div>

          <div className="filmium-editor-field-row">
            <Field label="Datum emitovanja">
              <input
                className="filmium-editor-input"
                onChange={(event) => setAirDate(event.target.value)}
                placeholder="DD.MM.GGGG"
                value={airDate}
              />
            </Field>
            <Field label="Rezolucija">
              <input
                className="filmium-editor-input"
                onChange={(event) => setResolution(event.target.value)}
                value={resolution}
              />
            </Field>
          </div>

          <div className="filmium-editor-image-uploads">
            <button className="filmium-editor-block-button" type="button">
              <Pencil size={13} />
              Screenshot / poster epizode
            </button>
            <button className="filmium-editor-block-button" type="button">
              <Pencil size={13} />
              Fajl epizode
            </button>
          </div>

          <div className="filmium-editor-field-row">
            <Field label="Audio">
              <input
                className="filmium-editor-input"
                onChange={(event) => setAudio(event.target.value)}
                value={audio}
              />
            </Field>
            <Field label="Titlovi">
              <input
                className="filmium-editor-input"
                onChange={(event) => setSubtitles(event.target.value)}
                value={subtitles}
              />
            </Field>
            <Field label="Ocena epizode">
              <input
                className="filmium-editor-input"
                onChange={(event) => setRating(event.target.value)}
                value={rating}
              />
            </Field>
          </div>

          <div className="filmium-editor-field-row">
            <Field label="Status gledanja">
              <select
                className="filmium-editor-input"
                onChange={(event) => setStatus(event.target.value)}
                value={status}
              >
                {WATCH_STATUS_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Lična napomena">
              <input
                className="filmium-editor-input"
                onChange={(event) => setNote(event.target.value)}
                value={note}
              />
            </Field>
          </div>
        </div>

        <footer className="filmium-episode-modal-foot">
          <button
            className="filmium-editor-button ghost"
            onClick={onClose}
            type="button"
          >
            Otkaži
          </button>
          <button
            className="filmium-editor-button primary"
            onClick={onClose}
            type="button"
          >
            <Save size={15} />
            Sačuvaj epizodu
          </button>
        </footer>
      </div>
    </div>
  );
}


// ==========          POMOĆNE FUNKCIJE          ==========

/**
 * Pretvara broj bajtova u čitljivu veličinu.
 */
function formatSize(bytes: number): string {
  if (!bytes || bytes <= 0) {
    return "";
  }

  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes;
  let unitIndex = 0;

  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }

  const rounded =
    value >= 100 || unitIndex === 0
      ? Math.round(value)
      : Math.round(value * 10) / 10;

  return `${rounded} ${units[unitIndex]}`;
}

export default FilmiumEditorPanel;
