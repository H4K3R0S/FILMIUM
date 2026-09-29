import {
  ArrowLeft,
  CalendarDays,
  Clock,
  FolderPlus,
  HardDrive,
  Heart,
  Languages,
  Layers,
  LoaderCircle,
  Pencil,
  Play,
  RefreshCw,
  Share2,
  UserPlus,
} from "lucide-react";
import {
  Link,
  useLocation,
  useNavigate,
  useParams,
} from "react-router";
import { useEffect, useMemo, useRef, useState } from "react";

import FilmiumCastSection
  from "../features/filmium/components/details/FilmiumCastSection";
import FilmiumExternalRatings
  from "../features/filmium/components/details/FilmiumExternalRatings";
import FilmiumCollectionPicker
  from "../features/filmium/components/details/FilmiumCollectionPicker";
import FilmiumKeywordsBox
  from "../features/filmium/components/details/FilmiumKeywordsBox";
import FilmiumProfilePicker
  from "../features/filmium/components/details/FilmiumProfilePicker";
import {
  getFilmiumAssetUrl,
  updateFilmiumMediaKeywords,
} from "../services/filmiumApi";
import {
  getFilmiumMediaSeasons,
  getFilmiumMediaSources,
  rescanFilmiumMediaSource,
  type FilmiumEpisode,
  type FilmiumSeason,
} from "../services/filmiumMediaSourceApi";
import {
  getFilmiumSeriesEpisodeThumbnailUrl,
  getFilmiumStreamUrl,
  getFilmiumSubtitleUrl,
  getFilmiumTranscodeUrl,
  refreshFilmiumMedia,
} from "../services/filmiumSeriesApi";
import { useFilmiumWorkspace } from "../features/filmium/context/useFilmiumWorkspace";
import { useFitToLines } from "../features/filmium/hooks/useFitToLines";
import FilmiumEditorPanel
  from "../features/filmium/components/details/FilmiumEditorPanel";
import FilmiumTransferPanel
  from "../features/filmium/components/details/FilmiumTransferPanel";
import FilmiumSubtitleEditorOverlay
  from "../features/filmium/components/details/FilmiumSubtitleEditorOverlay";
import type { TerminatorAdHocFile }
  from "../features/filmium/components/uploads/FilmiumSubtitleTerminator";
import FilmiumPlayer, {
  type FilmiumSubtitleTrack,
} from "../features/filmium/components/player/FilmiumPlayer";
import { playMpvVideo } from "../services/filmiumPlayer";
import FilmiumAcquireModal, {
  type FilmiumAcquirePrefill,
} from "../features/filmium/components/uploads/FilmiumAcquireModal";
import {
  cascadeDedupe,
  scoreByGenre,
  scoreRecommended,
  splitRelated,
  type RelatedCard,
} from "../features/filmium/lib/filmiumRecommendations";
import type { MediaItem, RelatedTitle } from "../types/filmium";
import type {
  FilmiumMediaFileRole,
  FilmiumMediaFileStatus,
  FilmiumMediaSource,
} from "../types/filmiumMediaSource";

// ==========          FILMIUM DETAILS EKRAN          ==========


// ==========          OZNAKE IZVORA          ==========

const FILE_ROLE_LABELS: Record<FilmiumMediaFileRole, string> = {
  video: "Video",
  poster: "Poster",
  backdrop: "Pozadina",
  wallpaper: "Wallpaper",
  fanart: "Fanart",
  trailer: "Trejler",
  subtitle: "Prevod",
  manifest: "Manifest",
  unknown: "Nepoznato",
};

const FILE_STATUS_LABELS: Record<FilmiumMediaFileStatus, string> = {
  available: "Dostupno",
  offline: "Van mreže",
  missing: "Nedostaje",
};


// ==========          FORMATIRANJE          ==========

/**
 * Pretvara broj minuta u čitljivo trajanje (npr. "1h 52min").
 */
function formatRuntime(minutes: number | null): string | null {
  if (!minutes || minutes <= 0) {
    return null;
  }

  const hours = Math.floor(minutes / 60);
  const restMinutes = minutes % 60;

  if (hours === 0) {
    return `${restMinutes}min`;
  }

  if (restMinutes === 0) {
    return `${hours}h`;
  }

  return `${hours}h ${restMinutes}min`;
}

/**
 * Formatira ISO datum u lokalni, čitljiv oblik.
 */
function formatDate(value: string | null): string | null {
  if (!value) {
    return null;
  }

  const parsed = new Date(value);

  if (Number.isNaN(parsed.getTime())) {
    return null;
  }

  return new Intl.DateTimeFormat("sr-Latn-RS", {
    dateStyle: "medium",
  }).format(parsed);
}

/**
 * Pretvara broj bajtova u čitljivu veličinu.
 */
function formatFileSize(bytes: number): string | null {
  if (!bytes || bytes <= 0) {
    return null;
  }

  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes;
  let unitIndex = 0;

  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }

  const rounded = value >= 100 || unitIndex === 0
    ? Math.round(value)
    : Math.round(value * 10) / 10;

  return `${rounded.toLocaleString("sr")} ${units[unitIndex]}`;
}

/**
 * Prikazuje kompletne informacije jednog FILMIUM sadržaja.
 */
function FilmiumMediaDetailsPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { itemId } = useParams();

  const {
    catalog,
    collections,
    setWorkspaceBackdropPath,
  } = useFilmiumWorkspace();

  const {
    errorMessage,
    isLoading,
    items,
    refreshCatalog,
    toggleFavorite,
    updatingFavoriteItemId,
  } = catalog;

  const parsedItemId = Number(itemId);

  const item = Number.isInteger(parsedItemId)
    ? items.find(
        (catalogItem) => catalogItem.id === parsedItemId,
      )
    : undefined;

  // ==========          IZVORI SADRŽAJA          ==========

  const [ucitaniIzvori, setUcitaniIzvori] = useState<FilmiumMediaSource[]>([]);
  const [isLoadingSources, setIsLoadingSources] = useState(false);
  // ID sadržaja za koji su izvori GOTOVI učitani (ne samo "trenutno se ne
  // učitava" — to je tačno i pre nego što učitavanje i počne). Koristi ga
  // autoplay efekat ispod da ne pokrene reprodukciju pre nego što izvori
  // stvarno stignu.
  const [sourcesReadyId, setSourcesReadyId] = useState<number | null>(null);
  const [sourcesErrorMessage, setSourcesErrorMessage] =
    useState<string | null>(null);
  const [isEditPanelOpen, setIsEditPanelOpen] = useState(false);
  const [isCollectionPickerOpen, setIsCollectionPickerOpen] =
    useState(false);
  const [isProfilePickerOpen, setIsProfilePickerOpen] =
    useState(false);
  const [acquireOpen, setAcquireOpen] = useState(false);
  const [acquirePrefill, setAcquirePrefill] =
    useState<FilmiumAcquirePrefill | null>(null);
  const [keywordsBusy, setKeywordsBusy] = useState(false);
  const [isTransferOpen, setIsTransferOpen] = useState(false);
  const [isEditPrevodOpen, setIsEditPrevodOpen] = useState(false);
  // Vreme inline plejera (ms) — Editor prevoda skače na liniju iz ovog trenutka.
  const [playerTimeMs, setPlayerTimeMs] = useState(0);
  const [rescanningSourceId, setRescanningSourceId] =
    useState<number | null>(null);
  const [ucitaneSezone, setUcitaneSezone] = useState<FilmiumSeason[]>([]);
  const [izabranaSezona, setIzabranaSezona] = useState<number | null>(null);
  const [selectedEpisode, setSelectedEpisode] =
    useState<FilmiumEpisode | null>(null);
  const [isRefreshingMedia, setIsRefreshingMedia] = useState(false);
  const [manualPlayback, setManualPlayback] = useState<{
    src: string;
    fallbackSrc: string;
    subtitles: FilmiumSubtitleTrack[];
    rootId: number;
    source: string;
  } | null>(null);

  // Sezone i izvori zavise od IDENTITETA sadržaja, ne od celog objekta: objekat
  // se menja i kad se promeni polje koje ove efekte ne zanima. (`itemId` je već
  // zauzeto — to je parametar rute, tekst; ovo je broj iz kataloga.)
  const ucitanId = item?.id ?? null;
  const ucitanTip = item?.media_type ?? null;

  // Film nema sezone, a sadržaj bez učitanih izvora ih nema još uvek: oboje se
  // IZVODI pri crtanju. Upis praznog spiska iz efekta značio bi dodatni crtež i
  // kratak tren u kojem se vide sezone prethodnog naslova.
  const seasons = ucitanTip === "series" ? ucitaneSezone : [];
  const activeSeason = ucitanTip === "series" ? izabranaSezona : null;
  const sources = ucitanId === null ? [] : ucitaniIzvori;

  useEffect(() => {
    if (ucitanId === null || ucitanTip !== "series") {
      return;
    }

    let isMounted = true;
    getFilmiumMediaSeasons(ucitanId)
      .then((loaded) => {
        if (!isMounted) {
          return;
        }
        setUcitaneSezone(loaded);
        setIzabranaSezona(loaded[0]?.season_number ?? null);
      })
      .catch(() => {
        if (isMounted) {
          setUcitaneSezone([]);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [ucitanId, ucitanTip]);

  useEffect(() => {
    if (ucitanId === null) {
      return;
    }

    let isMounted = true;

    loadSources(ucitanId)
      .then((loadedSources) => {
        if (isMounted) {
          setUcitaniIzvori(loadedSources);
        }
      })
      .catch((error: unknown) => {
        if (isMounted) {
          setSourcesErrorMessage(
            error instanceof Error
              ? error.message
              : "Učitavanje izvora sadržaja nije uspelo.",
          );
        }
      })
      .finally(() => {
        if (isMounted) {
          setIsLoadingSources(false);
          setSourcesReadyId(ucitanId);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [ucitanId]);

  // ==========          AUTOPLAY (KOMANDA IZ KURATORA)          ==========

  // Kurator navigira ovde sa `state: { autoplay: true }` kad komanda znači
  // "pusti <naslov>" — navigacija sama po sebi ne sme da bude dovoljna, mora
  // i da pusti (isto što `handlePlayMain` radi na klik dugmeta "Pusti").
  // Čeka se da izvori STVARNO stignu (`sourcesReadyId`), inače bi efekat
  // pukao u "video nije pronađen" iako je samo učitavanje u toku; za seriju
  // se čekaju i sezone (za film nisu potrebne).
  const autoplayHandledForId = useRef<number | null>(null);

  useEffect(() => {
    const treba = Boolean(
      (location.state as { autoplay?: boolean } | null)?.autoplay,
    );
    if (!treba) {
      return;
    }
    if (ucitanId === null || sourcesReadyId !== ucitanId) {
      return;
    }
    if (ucitanTip === "series" && ucitaneSezone.length === 0) {
      return;
    }
    if (autoplayHandledForId.current === ucitanId) {
      return;
    }
    autoplayHandledForId.current = ucitanId;
    handlePlayMain();
    // Ukloni signal iz istorije rute — povratak/refresh ne sme ponovo da
    // pokrene reprodukciju.
    navigate(location.pathname, { replace: true, state: null });
  }, [
    location.state,
    location.pathname,
    ucitanId,
    ucitanTip,
    sourcesReadyId,
    ucitaneSezone,
    navigate,
  ]);

  /**
   * Ucitava izvore jednog sadrzaja.
   */
  async function loadSources(
    mediaId: number,
  ): Promise<FilmiumMediaSource[]> {
    setIsLoadingSources(true);
    setSourcesErrorMessage(null);

    try {
      return await getFilmiumMediaSources(mediaId);
    } finally {
      setIsLoadingSources(false);
    }
  }

  // ==========          GLOBALNA DETAILS POZADINA          ==========

  useEffect(() => {
    const visualPath =
      item?.backdrop_path
      ?? item?.poster_path
      ?? null;

    setWorkspaceBackdropPath(visualPath);

    return () => {
      setWorkspaceBackdropPath(null);
    };
  }, [
    item?.backdrop_path,
    item?.poster_path,
    setWorkspaceBackdropPath,
  ]);


  // Naslov: uklopi u max 2 reda smanjivanjem fonta (umesto prelivanja u 3–4).
  const titleRef = useFitToLines<HTMLHeadingElement>(item?.title ?? "", {
    maxFontPx: 83,
    minFontPx: 32,
    maxLines: 2,
  });

  // Tri odeljka preporuka: Povezani (TMDB recommendations), Preporučeni
  // (naziv+žanr+ključne reči), Po žanru. Logika je u filmiumRecommendations;
  // ovde samo memoizacija + kaskadni dedup (10 po odeljku).
  //
  // Stoje IZNAD ranih `return`-a namerno. Kada su bili ispod, prvi crtež (dok
  // se učitava) preskakao je ova četiri hook-a, a sledeći ih je zvao — React
  // broji hook-ove po redu i takva razlika obara ceo ekran. Zato su ovde, sa
  // proverom `item` unutar same memoizacije.
  const relatedCards = useMemo(
    () => (item ? splitRelated(item.related_tmdb ?? [], items) : []),
    [item, items],
  );
  const recommendedRaw = useMemo(
    () => (item ? scoreRecommended(item, items) : []),
    [item, items],
  );
  const genreRaw = useMemo(
    () => (item ? scoreByGenre(item, items) : []),
    [item, items],
  );
  const sections = useMemo(
    () => cascadeDedupe(relatedCards, recommendedRaw, genreRaw, 10),
    [relatedCards, recommendedRaw, genreRaw],
  );

  if (isLoading) {
    return (
      <p className="system-message">
        Učitavam FILMIUM sadržaj...
      </p>
    );
  }

  if (errorMessage) {
    return (
      <p className="system-message error">
        FILMIUM API nije dostupan: {errorMessage}
      </p>
    );
  }

  if (!item) {
    return (
      <section className="filmium-section">
        <div className="section-heading">
          <p className="eyebrow">FILMIUM Details</p>
          <h2>Sadržaj nije pronađen</h2>
        </div>

        <button
          className="secondary-button"
          onClick={() => navigate("/filmium/library")}
          type="button"
        >
          Vrati se u biblioteku
        </button>
      </section>
    );
  }

  // Slika izabrane sezone (default sezona 1); fallback na sliku serije.
  const activeSeasonData = seasons.find(
    (season) => season.season_number === activeSeason,
  );

  const posterUrl = getFilmiumAssetUrl(
    activeSeasonData?.poster_path ?? item.poster_path,
  );

  const backdropUrl = getFilmiumAssetUrl(
    activeSeasonData?.backdrop_path
      ?? activeSeasonData?.poster_path
      ?? item.backdrop_path
      ?? item.poster_path,
  );

  const inlinePlayback = resolveInlinePlayback();

  const runtimeLabel = formatRuntime(item.runtime_minutes);
  const createdLabel = formatDate(item.created_at);
  const updatedLabel = formatDate(item.updated_at);
  const basicSettings = (item.editor_settings?.basic ?? {}) as {
    local_title_sr?: string;
  };
  const displayTitle = basicSettings.local_title_sr?.trim() || item.title;
  const originalNameLabel =
    item.english_title?.trim() || item.original_title?.trim() || "";

  const memberCollections = collections.collections.filter(
    (collection) => collection.item_ids.includes(item.id),
  );

  /**
   * Otvara sadržaj u režimu izmene.
   */
  function handleEdit(): void {
    if (!item) {
      return;
    }

    setIsEditPanelOpen(true);
  }

  // Ključne reči: IMDB/TMDB (item.keywords) + korisničke
  // (editor_settings.user_keywords).
  const imdbKeywords = item.keywords ?? [];
  const userKeywords =
    (item.editor_settings?.user_keywords as string[] | undefined) ?? [];

  /**
   * Snima izmenjenu listu korisničkih ključnih reči (parcijalni PATCH) i
   * osvežava katalog. IMDB ključne reči ostaju netaknute.
   */
  async function saveUserKeywords(nextUser: string[]): Promise<void> {
    if (!item) {
      return;
    }
    setKeywordsBusy(true);
    try {
      await updateFilmiumMediaKeywords(item.id, {
        keywords: imdbKeywords,
        editor_settings: {
          ...(item.editor_settings ?? {}),
          user_keywords: nextUser,
        },
      });
      await refreshCatalog();
    } finally {
      setKeywordsBusy(false);
    }
  }

  function handleAddKeyword(keyword: string): void {
    void saveUserKeywords([...userKeywords, keyword]);
  }

  function handleRemoveUserKeyword(keyword: string): void {
    void saveUserKeywords(
      userKeywords.filter((entry) => entry !== keyword),
    );
  }

  /**
   * Primarni izvor: MP4/MOV/WEBM direktno (sa seek-om), ostali kontejneri
   * (MKV/AVI/TS...) odmah kroz kompatibilni tok (ffmpeg) da ne trepće.
   */
  function primaryStreamUrl(rootId: number, source: string): string {
    return /\.(mp4|m4v|mov|webm)$/i.test(source)
      ? getFilmiumStreamUrl(rootId, source)
      : getFilmiumTranscodeUrl(rootId, source);
  }

  /**
   * Spaja relativne delove putanje u jedan POSIX izvor od korena biblioteke.
   */
  function joinSource(...parts: (string | null | undefined)[]): string {
    return parts
      .filter((part): part is string => Boolean(part))
      .join("/")
      .replace(/\\/g, "/")
      .replace(/\/+/g, "/")
      .replace(/^\.\//, "")
      .replace(/^\//, "");
  }

  /**
   * Pronalazi izvor za reprodukciju filma (root + video fajl).
   */
  function resolveMoviePlayback(): { rootId: number; source: string } | null {
    const videoExtension =
      /\.(mp4|mkv|avi|m4v|mov|webm|ts|m2ts|wmv|flv|mpe?g|vob|ogv|divx|3gp|rmvb)$/i;

    for (const source of sources) {
      if (source.library_root_id === null) {
        continue;
      }
      const video =
        source.files.find((file) => file.role === "video")
        ?? source.files.find((file) =>
          videoExtension.test(file.relative_path),
        );
      if (video) {
        return {
          rootId: source.library_root_id,
          source: joinSource(
            source.relative_directory,
            video.relative_path,
          ),
        };
      }
    }
    return null;
  }

  /**
   * Vraća izvor za reprodukciju jedne epizode.
   */
  function resolveEpisodePlayback(
    episode: FilmiumEpisode | null,
  ): { rootId: number; source: string } | null {
    if (
      !episode
      || episode.root_id === null
      || !episode.video_source
    ) {
      return null;
    }
    return {
      rootId: episode.root_id,
      source: joinSource(episode.video_source),
    };
  }

  /**
   * Vraća izvor trailera ako postoji u nekom registrovanom folderu.
   */
  function resolveTrailerPlayback(): {
    rootId: number;
    source: string;
  } | null {
    for (const source of sources) {
      if (source.library_root_id === null) {
        continue;
      }
      const trailer = source.files.find(
        (file) => file.role === "trailer",
      );
      if (trailer) {
        return {
          rootId: source.library_root_id,
          source: joinSource(
            source.relative_directory,
            trailer.relative_path,
          ),
        };
      }
    }
    return null;
  }

  /**
   * Bira šta plejer prikazuje: ručni izbor > trailer > film/epizoda.
   */
  /**
   * Trenutni izvor reprodukcije (ručni izbor > trailer > film/epizoda).
   */
  function currentTarget(): { rootId: number; source: string } | null {
    if (manualPlayback) {
      return {
        rootId: manualPlayback.rootId,
        source: manualPlayback.source,
      };
    }
    const trailer = resolveTrailerPlayback();
    if (trailer) {
      return trailer;
    }
    if (item?.media_type === "movie") {
      return resolveMoviePlayback();
    }
    const seasonData =
      seasons.find(
        (season) => season.season_number === activeSeason,
      ) ?? seasons[0];
    const episode = selectedEpisode ?? seasonData?.episodes[0] ?? null;
    return resolveEpisodePlayback(episode);
  }

  /**
   * mpv režim: pušta trenutni sadržaj ugradjen u prozor aplikacije.
   */
  /**
   * Srpski prevod (relativni izvor) za dati rootId — za mpv --sub-file.
   */
  function subtitleSourceFor(rootId: number): string | null {
    for (const source of sources) {
      if (source.library_root_id !== rootId) {
        continue;
      }
      const subs = source.files.filter(
        (file) => file.role === "subtitle",
      );
      const chosen =
        subs.find((file) =>
          (file.language ?? "").toLowerCase().startsWith("sr"),
        ) ?? subs[0];
      if (chosen) {
        return joinSource(
          source.relative_directory,
          chosen.relative_path,
        );
      }
    }
    return null;
  }

  async function handleNativePlay(opts: {
    windowId: string | null;
    geometry: string;
  }): Promise<boolean> {
    const target = currentTarget();
    if (!target) {
      return false;
    }
    // Za film prosledi srpski prevod; za seriju mpv auto-učita po epizodi.
    const subtitle =
      item?.media_type === "movie"
        ? subtitleSourceFor(target.rootId)
        : null;
    return playMpvVideo(
      target.rootId,
      target.source,
      opts.windowId,
      opts.geometry,
      subtitle,
    );
  }

  function resolveInlinePlayback(): {
    src: string | null;
    fallbackSrc: string | null;
    subtitles: FilmiumSubtitleTrack[];
  } {
    if (manualPlayback) {
      return manualPlayback;
    }

    const trailer = resolveTrailerPlayback();
    if (trailer) {
      return {
        src: primaryStreamUrl(trailer.rootId, trailer.source),
        fallbackSrc: getFilmiumTranscodeUrl(
          trailer.rootId,
          trailer.source,
        ),
        subtitles: [],
      };
    }

    if (item?.media_type === "movie") {
      const movie = resolveMoviePlayback();
      return {
        src: movie
          ? getFilmiumStreamUrl(movie.rootId, movie.source)
          : null,
        fallbackSrc: movie
          ? getFilmiumTranscodeUrl(movie.rootId, movie.source)
          : null,
        subtitles: movie ? buildSubtitleTracks() : [],
      };
    }

    const seasonData =
      seasons.find(
        (season) => season.season_number === activeSeason,
      ) ?? seasons[0];
    const episode =
      selectedEpisode ?? seasonData?.episodes[0] ?? null;
    const target = resolveEpisodePlayback(episode);

    return {
      src: target
        ? getFilmiumStreamUrl(target.rootId, target.source)
        : null,
      fallbackSrc: target
        ? getFilmiumTranscodeUrl(target.rootId, target.source)
        : null,
      subtitles: episode ? buildEpisodeSubtitles(episode) : [],
    };
  }

  /**
   * Skuplja prevode iz izvora i sortira ih sa srpskim na prvom mestu.
   */
  function buildSubtitleTracks(): FilmiumSubtitleTrack[] {
    const tracks: FilmiumSubtitleTrack[] = [];

    for (const source of sources) {
      if (source.library_root_id === null) {
        continue;
      }
      for (const file of source.files) {
        if (file.role !== "subtitle") {
          continue;
        }
        const lang = (file.language ?? "und").toLowerCase();
        tracks.push({
          src: getFilmiumSubtitleUrl(
            source.library_root_id,
            joinSource(source.relative_directory, file.relative_path),
          ),
          lang,
          label: lang.toUpperCase(),
        });
      }
    }

    // Srpski ima prednost (sr / sr-Latn), pa hrvatski/bosanski, pa ostali.
    const priority = (lang: string): number => {
      if (lang.startsWith("sr")) return 0;
      if (lang.startsWith("hr") || lang.startsWith("bs")) return 1;
      if (lang.startsWith("en")) return 2;
      return 3;
    };
    tracks.sort((a, b) => priority(a.lang) - priority(b.lang));

    if (tracks.length > 0) {
      tracks[0] = { ...tracks[0], isDefault: true };
    }

    return tracks;
  }

  /**
   * Apsolutne putanje SRT prevoda filma za „Edit Prevoda" (Terminator ad-hoc).
   * Srpski ima prednost, pa se otvara prvi.
   */
  function buildSubtitleEditFiles(): TerminatorAdHocFile[] {
    const list: { path: string; lang: string; label: string }[] = [];

    for (const source of sources) {
      for (const file of source.files) {
        if (file.role !== "subtitle") {
          continue;
        }
        if (!file.relative_path.toLowerCase().endsWith(".srt")) {
          continue;
        }
        const lang = (file.language ?? "und").toLowerCase();
        const name =
          file.relative_path.split(/[\\/]/).pop() ?? file.relative_path;
        list.push({
          path: joinSource(
            source.root_path_snapshot,
            source.relative_directory,
            file.relative_path,
          ),
          lang,
          label: `${lang.toUpperCase()} — ${name}`,
        });
      }
    }

    const priority = (lang: string): number => {
      if (lang.startsWith("sr")) return 0;
      if (lang.startsWith("hr") || lang.startsWith("bs")) return 1;
      if (lang.startsWith("en")) return 2;
      return 3;
    };
    list.sort((a, b) => priority(a.lang) - priority(b.lang));

    return list.map(({ path, label }) => ({ path, label }));
  }

  /**
   * Prevodi jedne epizode: u istom folderu sezone (uklj. subs pod-folder),
   * a naziv sadrži broj epizode. Srpski ima prednost.
   */
  function buildEpisodeSubtitles(
    episode: FilmiumEpisode,
  ): FilmiumSubtitleTrack[] {
    if (episode.root_id === null || !episode.video_source) {
      return [];
    }

    const videoPath = episode.video_source.replace(/\\/g, "/");
    const seasonDir = videoPath.slice(0, videoPath.lastIndexOf("/"));
    const num = episode.episode_number;
    const episodeRe = new RegExp(
      `(?:^|[^0-9])(?:s\\d{1,2})?(?:e|x|ep|episode)?0*${num}(?![0-9])`,
      "i",
    );

    const tracks: FilmiumSubtitleTrack[] = [];

    for (const source of sources) {
      if (source.library_root_id !== episode.root_id) {
        continue;
      }
      for (const file of source.files) {
        if (file.role !== "subtitle") {
          continue;
        }
        const full = joinSource(
          source.relative_directory,
          file.relative_path,
        );
        const name = full.slice(full.lastIndexOf("/") + 1);
        if (!full.startsWith(seasonDir) || !episodeRe.test(name)) {
          continue;
        }
        const lang = (file.language ?? "und").toLowerCase();
        tracks.push({
          src: getFilmiumSubtitleUrl(episode.root_id, full),
          lang,
          label: lang.toUpperCase(),
        });
      }
    }

    const priority = (lang: string): number => {
      if (lang.startsWith("sr")) return 0;
      if (lang.startsWith("hr") || lang.startsWith("bs")) return 1;
      if (lang.startsWith("en")) return 2;
      return 3;
    };
    tracks.sort((a, b) => priority(a.lang) - priority(b.lang));

    if (tracks.length > 0) {
      tracks[0] = { ...tracks[0], isDefault: true };
    }

    return tracks;
  }

  /**
   * Pušta glavni sadržaj: film → filmski fajl; serija → izabrana ili prva
   * epizoda trenutne (ili prve) sezone. Prevodi se učitavaju (sr prvi).
   */
  function handlePlayMain(): void {
    if (!item) {
      return;
    }

    if (item.media_type === "movie") {
      const target = resolveMoviePlayback();
      if (!target) {
        window.alert(
          "Video fajl filma nije pronađen. Klikni Osveži da se "
          + "registruje putanja iz biblioteke.",
        );
        return;
      }
      setManualPlayback({
        src: primaryStreamUrl(target.rootId, target.source),
        fallbackSrc: getFilmiumTranscodeUrl(target.rootId, target.source),
        subtitles: buildSubtitleTracks(),
        rootId: target.rootId,
        source: target.source,
      });
      return;
    }

    const seasonData =
      seasons.find(
        (season) => season.season_number === activeSeason,
      ) ?? seasons[0];

    const episode =
      selectedEpisode
      ?? seasonData?.episodes[0]
      ?? null;

    const target = resolveEpisodePlayback(episode);
    if (!target || !episode) {
      window.alert(
        "Video epizode nije pronađen. Pokušaj Osveži ili izaberi epizodu.",
      );
      return;
    }

    setManualPlayback({
      src: primaryStreamUrl(target.rootId, target.source),
      fallbackSrc: getFilmiumTranscodeUrl(target.rootId, target.source),
      subtitles: buildEpisodeSubtitles(episode),
      rootId: target.rootId,
      source: target.source,
    });
  }

  /**
   * Pušta konkretnu epizodu (dvoklik na epizodu).
   */
  function handlePlayEpisode(
    episode: FilmiumEpisode,
  ): void {
    if (!item) {
      return;
    }

    const target = resolveEpisodePlayback(episode);
    if (!target) {
      window.alert("Video epizode nije pronađen u biblioteci.");
      return;
    }

    setSelectedEpisode(episode);
    setManualPlayback({
      src: primaryStreamUrl(target.rootId, target.source),
      fallbackSrc: getFilmiumTranscodeUrl(target.rootId, target.source),
      subtitles: buildEpisodeSubtitles(episode),
      rootId: target.rootId,
      source: target.source,
    });
  }

  /**
   * Osvežava samo folder ovog sadržaja (skenira nove slike/epizode).
   */
  async function handleRefreshThisMedia(): Promise<void> {
    if (!item || isRefreshingMedia) {
      return;
    }

    setIsRefreshingMedia(true);

    try {
      const summary = await refreshFilmiumMedia(item.id);
      const [refreshedSources, refreshedSeasons] = await Promise.all([
        loadSources(item.id).catch(() => sources),
        item.media_type === "series"
          ? getFilmiumMediaSeasons(item.id).catch(() => seasons)
          : Promise.resolve(seasons),
      ]);
      setUcitaniIzvori(refreshedSources);
      setUcitaneSezone(refreshedSeasons);

      const images =
        summary.posters_added
        + summary.backdrops_added
        + summary.season_posters_added
        + summary.season_backdrops_added;

      window.alert(
        "Osvežavanje završeno:\n"
        + `• Slika dodato: ${images}\n`
        + `• Novih sezona/epizoda: ${summary.seasons_added}`
        + `/${summary.episodes_added}\n`
        + `• Foldera filmova skenirano: ${summary.movie_folders_scanned}\n`
        + `• Izvora filmova registrovano: ${summary.movie_sources_added}`,
      );
    } catch {
      window.alert("Osvežavanje ovog sadržaja nije uspelo.");
    } finally {
      setIsRefreshingMedia(false);
    }
  }

  /**
   * Vraca korisnika na ekran sa kog je otvorio detalje.
   */
  function handleBack(): void {
    if (window.history.length > 1) {
      navigate(-1);
      return;
    }

    navigate("/filmium");
  }

  /**
   * Ponovo skenira primarni registrovani izvor.
   */
  async function handleRescan(): Promise<void> {
    const source = sources[0];

    if (!source || !item) {
      return;
    }

    setRescanningSourceId(source.id);
    setSourcesErrorMessage(null);

    try {
      const rescannedSource = await rescanFilmiumMediaSource(
        source.id,
      );

      setUcitaniIzvori((currentSources) =>
        currentSources.map((currentSource) =>
          currentSource.id === rescannedSource.id
            ? rescannedSource
            : currentSource,
        )
      );
      await refreshCatalog();
    } catch (error) {
      setSourcesErrorMessage(
        error instanceof Error
          ? error.message
          : "Ponovno skeniranje nije uspelo.",
      );
    } finally {
      setRescanningSourceId(null);
    }
  }

  const breadcrumbParts = [
    item.media_type === "movie" ? "Filmovi" : "Serije",
    item.genres[0] ?? "Bez žanra",
  ];

  const files = sources.flatMap((source) => source.files);
  const videoFile = files.find((file) => file.role === "video");
  const trailerFile = files.find((file) => file.role === "trailer");
  const subtitles = files.filter((file) => file.role === "subtitle");
  const editableSubtitleFiles = buildSubtitleEditFiles();
  const primarySubtitle =
    subtitles.find((file) =>
      ["sr", "srp", "srb"].includes(
        (file.language ?? "").toLocaleLowerCase("sr-Latn-RS"),
      )
    )
    ?? subtitles[0]
    ?? null;
  const extraSubtitleCount = Math.max(0, subtitles.length - 1);
  const qualityLabel = videoFile ? "Video dostupan" : "Bez videa";
  const selectedEpisodeThumb =
    selectedEpisode?.root_id != null && selectedEpisode.video_source
      ? getFilmiumSeriesEpisodeThumbnailUrl(
          selectedEpisode.root_id,
          selectedEpisode.video_source,
        )
      : null;

  return (
    <article className="filmium-media-details">
      {/* ==========          DETAILS BACKDROP          ========== */}

      <div
        className="filmium-media-details-backdrop"
        style={{
          backgroundImage: backdropUrl
            ? `url("${backdropUrl}")`
            : undefined,
        }}
      >
        <div className="filmium-media-details-backdrop-shade" />
      </div>

      {/* ==========          DETAILS SADRŽAJ          ========== */}

      <div className="filmium-media-details-nav">
        <button
          className="filmium-details-back-button"
          onClick={handleBack}
          type="button"
        >
          <ArrowLeft size={17} />
          Nazad
        </button>

        <div className="filmium-details-breadcrumb">
          <span>{breadcrumbParts.join(" > ")}</span>
        </div>

        <button
          aria-label="Osveži ovaj sadržaj"
          className={
            "filmium-details-refresh-button"
            + (isRefreshingMedia ? " is-refreshing" : "")
          }
          disabled={isRefreshingMedia}
          onClick={handleRefreshThisMedia}
          title="Osveži ovaj folder (nove slike, epizode, prevodi)"
          type="button"
        >
          <RefreshCw size={16} />
          Osveži
        </button>
      </div>

      <header className="filmium-details-identity">
        <h1 ref={titleRef}>{displayTitle}</h1>

        <p className="filmium-details-meta-line">
          {[
            item.release_year ? String(item.release_year) : null,
            ...(item.genres.length > 0 ? item.genres : ["Bez žanra"]),
            item.rating !== null ? `★ ${item.rating}/10` : null,
          ]
            .filter(Boolean)
            .join("  •  ")}
        </p>
      </header>

      <div className="filmium-media-details-body">
        <div className="filmium-details-left">
        <div className="filmium-media-details-poster">
          {posterUrl ? (
            <img
              alt={`Poster za ${item.title}`}
              src={posterUrl}
            />
          ) : (
            <div className="filmium-media-details-poster-fallback">
              <span>
                {item.media_type === "movie"
                  ? "FILM"
                  : "SERIJA"}
              </span>

              <strong>{item.title}</strong>
            </div>
          )}
        </div>

        <div className="filmium-details-facts side filmium-details-infobox">
          <div className="filmium-details-availrow">
            <span
              aria-hidden="true"
              className={`filmium-avail-dot${videoFile ? " is-on" : ""}`}
            />
            <span>{videoFile ? "Dostupno" : "Nedostupno"}</span>
            {subtitles.length > 0 && (
              <span className="filmium-avail-subs">
                Titlovi: {subtitles.length}
              </span>
            )}
          </div>
          {(createdLabel || updatedLabel) && (
            <div className="filmium-details-daterow">
              {createdLabel && <span>Dodato: {createdLabel}</span>}
              {createdLabel && updatedLabel && (
                <span className="filmium-date-sep">|</span>
              )}
              {updatedLabel && <span>Izmena: {updatedLabel}</span>}
            </div>
          )}
        </div>

        <FilmiumExternalRatings item={item} />

        </div>

        <div className="filmium-media-details-content">
          <div className="filmium-details-headtext">
            {originalNameLabel
              && originalNameLabel !== displayTitle && (
                <p className="filmium-details-original-title">
                  {originalNameLabel}
                </p>
              )}

            {item.notes ? (
              <p className="filmium-media-details-description">
                {item.notes}
              </p>
            ) : (
              <p className="filmium-media-details-description muted">
                Opis filma još nije dostupan.
              </p>
            )}

            <FilmiumKeywordsBox
              busy={keywordsBusy}
              imdbKeywords={imdbKeywords}
              userKeywords={userKeywords}
              onAddKeyword={handleAddKeyword}
              onRemoveUserKeyword={handleRemoveUserKeyword}
            />
          </div>

          {/* ==========   PLEJER + DUGMICI (ZAJEDNIČKI OKVIR)   ========== */}

          <div className="filmium-details-stage">
            <div className="filmium-details-stage-main">

          {/* ==========          TEHNIČKI PODACI          ========== */}

          {/* ==========          INLINE PLEJER          ========== */}

          <FilmiumPlayer
            autoPlay={manualPlayback !== null}
            emptyLabel={
              trailerFile
                ? "Video se učitava..."
                : "Klikni Pusti ili Osveži da se registruje video."
            }
            fallbackSrc={inlinePlayback.fallbackSrc}
            poster={selectedEpisodeThumb ?? posterUrl}
            src={inlinePlayback.src}
            subtitles={inlinePlayback.subtitles}
            onNativePlay={handleNativePlay}
            onTimeUpdateMs={setPlayerTimeMs}
          />

            </div>

            {/* ==========   DESNA TRAKA: STATUS + DUGMICI   ========== */}

            <aside className="filmium-details-rail">
              <div className="filmium-details-rail-actions">
                <button
                  className="secondary-button"
                  onClick={handleEdit}
                  type="button"
                >
                  <Pencil size={17} />
                  Izmeni sadržaj
                </button>

                <button
                  className="secondary-button"
                  onClick={() => setIsCollectionPickerOpen(true)}
                  type="button"
                >
                  <FolderPlus size={17} />
                  Kolekcija
                </button>

                <button
                  className="secondary-button"
                  onClick={() => setIsProfilePickerOpen(true)}
                  type="button"
                >
                  <UserPlus size={17} />
                  + Profil
                </button>

                <button
                  className={`favorite-button ${
                    item.is_favorite ? "active" : ""
                  }`}
                  disabled={updatingFavoriteItemId === item.id}
                  onClick={() => void toggleFavorite(item)}
                  type="button"
                >
                  <Heart
                    fill={item.is_favorite ? "currentColor" : "none"}
                    size={17}
                  />
                  {item.is_favorite
                    ? "Ukloni iz favorita"
                    : "Dodaj u favorite"}
                </button>

                <button
                  className="secondary-button"
                  disabled={
                    sources.length === 0 || rescanningSourceId !== null
                  }
                  onClick={() => void handleRescan()}
                  type="button"
                >
                  <RefreshCw
                    className={rescanningSourceId !== null ? "spinning" : ""}
                    size={17}
                  />
                  Rescan
                </button>

                <button
                  className="secondary-button"
                  onClick={() => setIsTransferOpen(true)}
                  type="button"
                >
                  <Share2 size={17} />
                  Podeli
                </button>

                <button
                  className="secondary-button"
                  disabled={editableSubtitleFiles.length === 0}
                  onClick={() => setIsEditPrevodOpen(true)}
                  type="button"
                >
                  <Pencil size={17} />
                  Edit Prevoda
                </button>
              </div>
            </aside>
          </div>

          {/* ==========          KOLEKCIJE          ========== */}

          {memberCollections.length > 0 && (
            <div className="filmium-details-collections">
              <p className="filmium-details-section-label">
                <Layers size={15} />
                Kolekcije
              </p>
              <div className="filmium-details-collection-chips">
                {memberCollections.map((collection) => (
                  <Link
                    className="filmium-details-collection-chip"
                    key={collection.id}
                    to="/filmium/collections"
                  >
                    {collection.name}
                  </Link>
                ))}
              </div>
            </div>
          )}

        </div>
      </div>

      {isTransferOpen && (
        <FilmiumTransferPanel
          mediaId={item.id}
          onClose={() => setIsTransferOpen(false)}
          title={item.title}
        />
      )}

      {isEditPrevodOpen && (
        <FilmiumSubtitleEditorOverlay
          currentTimeMs={playerTimeMs}
          files={editableSubtitleFiles}
          onClose={() => setIsEditPrevodOpen(false)}
        />
      )}

      {item.media_type === "series" && seasons.length > 0 && (
        <section className="filmium-details-episodes">
          <div className="filmium-details-season-bar">
            <span className="filmium-details-season-label">Sezona:</span>
            {seasons.map((season) => (
              <button
                className={`filmium-details-season-tab${
                  activeSeason === season.season_number ? " active" : ""
                }`}
                key={season.id}
                onClick={() => {
                  setIzabranaSezona(season.season_number);
                  setSelectedEpisode(null);
                }}
                type="button"
              >
                S{season.season_number}
              </button>
            ))}
          </div>

          {selectedEpisode && (
            <div className="filmium-details-episode-info">
              <strong>
                S{activeSeason}E
                {String(selectedEpisode.episode_number).padStart(2, "0")}
                {selectedEpisode.title ? ` — ${selectedEpisode.title}` : ""}
              </strong>
              {selectedEpisode.runtime_minutes !== null && (
                <span>{selectedEpisode.runtime_minutes} min</span>
              )}
            </div>
          )}

          <div className="filmium-details-episode-grid">
            {(
              seasons.find(
                (season) => season.season_number === activeSeason,
              )?.episodes ?? []
            ).map((episode) => (
              <button
                className={`filmium-details-episode-card${
                  selectedEpisode?.id === episode.id ? " active" : ""
                }`}
                key={episode.id}
                onClick={() => setSelectedEpisode(episode)}
                onDoubleClick={() => handlePlayEpisode(episode)}
                title={
                  (episode.title ?? `Epizoda ${episode.episode_number}`)
                  + " — dvoklik za reprodukciju"
                }
                type="button"
              >
                <EpisodeThumb episode={episode} />
                <span className="filmium-details-episode-play">
                  <Play fill="currentColor" size={22} />
                </span>
                <span className="filmium-details-episode-name">
                  {episode.title ?? `Epizoda ${episode.episode_number}`}
                </span>
              </button>
            ))}
          </div>
        </section>
      )}

      <FilmiumCastSection mediaId={item.id} />

      {(sections.relatedCards.length > 0
        || sections.recommended.length > 0
        || sections.genre.length > 0) && (
        <section className="filmium-details-recommendations">
          {sections.relatedCards.length > 0 && (
            <RecommendationRow
              cards={sections.relatedCards}
              title={
                item.media_type === "movie"
                  ? "Povezani filmovi"
                  : "Povezane serije"
              }
              onOpen={(recommended) =>
                navigate(`/filmium/media/${recommended.id}`)}
              onAcquire={(related) => {
                setAcquirePrefill({
                  title: related.title,
                  year: related.year,
                  media_type: related.media_type === "series"
                    ? "series"
                    : "movie",
                  tmdb_id: related.tmdb_id,
                });
                setAcquireOpen(true);
              }}
            />
          )}

          {sections.recommended.length > 0 && (
            <RecommendationRow
              items={sections.recommended}
              title={
                item.media_type === "movie"
                  ? "Preporučeni filmovi"
                  : "Preporučene serije"
              }
              onOpen={(recommended) =>
                navigate(`/filmium/media/${recommended.id}`)}
            />
          )}

          {sections.genre.length > 0 && (
            <RecommendationRow
              items={sections.genre}
              title="Preporuka po žanru"
              onOpen={(recommended) =>
                navigate(`/filmium/media/${recommended.id}`)}
            />
          )}
        </section>
      )}

      <FilmiumAcquireModal
        open={acquireOpen}
        prefill={acquirePrefill}
        onAdded={() => {
          setAcquireOpen(false);
          void refreshCatalog();
        }}
        onClose={() => setAcquireOpen(false)}
      />

      {/* ==========          IZVORI I FAJLOVI          ========== */}

      <section className="filmium-details-sources" hidden>
        <div className="filmium-details-sources-heading">
          <HardDrive size={18} />
          <h2>Izvori i fajlovi</h2>
        </div>

        {isLoadingSources && (
          <p className="filmium-details-sources-status">
            <LoaderCircle className="spinning" size={16} />
            Učitavam izvore sadržaja...
          </p>
        )}

        {sourcesErrorMessage && !isLoadingSources && (
          <p className="filmium-details-sources-status error">
            {sourcesErrorMessage}
          </p>
        )}

        {!isLoadingSources
          && !sourcesErrorMessage
          && sources.length === 0 && (
            <p className="filmium-details-sources-status muted">
              Za ovaj sadržaj još nema registrovanih fizičkih fajlova.
              Skeniraj i uvezi film sa Uploads stranice.
            </p>
          )}

        <div className="filmium-details-source-list">
          {sources.map((source) => (
            <article
              className="filmium-details-source"
              key={source.id}
            >
              <header className="filmium-details-source-top">
                <code>{source.relative_directory || "/"}</code>
                <span
                  className={
                    `filmium-details-source-status status-${source.availability_status}`
                  }
                >
                  {FILE_STATUS_LABELS[source.availability_status]}
                </span>
              </header>

              {source.files.length > 0 ? (
                <ul className="filmium-details-file-list">
                  {source.files.map((file) => {
                    const sizeLabel = formatFileSize(file.size_bytes);

                    return (
                      <li
                        className="filmium-details-file"
                        key={file.id}
                      >
                        <span className="filmium-details-file-role">
                          {file.role === "subtitle" && (
                            <Languages size={14} />
                          )}
                          {FILE_ROLE_LABELS[file.role]}
                          {file.language
                            ? ` · ${file.language.toUpperCase()}`
                            : ""}
                        </span>

                        <span className="filmium-details-file-path">
                          {file.relative_path}
                        </span>

                        <span className="filmium-details-file-meta">
                          {sizeLabel && <span>{sizeLabel}</span>}
                          <span
                            className={
                              `filmium-details-file-status status-${file.file_status}`
                            }
                          >
                            {FILE_STATUS_LABELS[file.file_status]}
                          </span>
                        </span>
                      </li>
                    );
                  })}
                </ul>
              ) : (
                <p className="filmium-details-sources-status muted">
                  Ovaj izvor nema evidentirane datoteke.
                </p>
              )}
            </article>
          ))}
        </div>
      </section>

      {/* ==========          IZMENI SADRŽAJ (EDITOR PANEL)          ========== */}
      {isEditPanelOpen && (
        <FilmiumEditorPanel
          catalog={items}
          collections={collections.collections}
          item={item}
          onAddToCollection={collections.addToCollection}
          onClose={() => setIsEditPanelOpen(false)}
          onDeleteMedia={() => {
            setIsEditPanelOpen(false);
            void refreshCatalog();
            navigate("/filmium/library");
          }}
          onSaved={() => void refreshCatalog()}
          seasons={seasons}
          sources={sources}
        />
      )}

      {/* ==========          IZBORNIK PROFILA          ========== */}
      {isProfilePickerOpen && (
        <FilmiumProfilePicker
          mediaId={item.id}
          onClose={() => setIsProfilePickerOpen(false)}
          title={item.title}
        />
      )}

      {/* ==========          IZBORNIK KOLEKCIJA          ========== */}
      {isCollectionPickerOpen && (
        <FilmiumCollectionPicker
          busyMembershipKey={collections.busyMembershipKey}
          collections={collections.collections}
          errorMessage={
            collections.membershipErrorMessage
            ?? collections.collectionErrorMessage
          }
          itemId={item.id}
          onAddToCollection={collections.addToCollection}
          onCreateCollection={collections.createCollection}
          onClose={() => setIsCollectionPickerOpen(false)}
        />
      )}
    </article>
  );
}

// TMDB baza za postere ne-owned povezanih naslova (nemamo lokalnu sliku).
const TMDB_POSTER_BASE = "https://image.tmdb.org/t/p/w500";

type RecommendationRowProps = {
  title: string;
  onOpen: (item: MediaItem) => void;
  /** Standardni odeljci (Preporučeni / Po žanru). */
  items?: MediaItem[];
  /** „Povezani" odeljak — owned + ne-owned kartice. */
  cards?: RelatedCard[];
  /** Klik na ne-owned karticu (otvara „Dodaj" modal). */
  onAcquire?: (related: RelatedTitle) => void;
};

/** Normalizovan opis kartice za jedinstven prikaz. */
type PosterCardModel = {
  key: string;
  title: string;
  year: number | null;
  posterUrl: string | null;
  mediaType: MediaItem["media_type"];
  isWishlist: boolean;
  onClick: () => void;
};

/**
 * Sličica epizode (ffmpeg preko backenda) sa Play ikonom kao rezervom.
 */
function EpisodeThumb({ episode }: { episode: FilmiumEpisode }) {
  const [failed, setFailed] = useState(false);
  const url =
    episode.root_id != null && episode.video_source
      ? getFilmiumSeriesEpisodeThumbnailUrl(
          episode.root_id,
          episode.video_source,
        )
      : null;

  return (
    <div className="filmium-details-episode-thumb">
      {url && !failed ? (
        <img
          alt=""
          loading="lazy"
          onError={() => setFailed(true)}
          src={url}
        />
      ) : (
        <Play fill="currentColor" size={22} />
      )}
      <span className="filmium-details-episode-badge">
        {episode.episode_number}
      </span>
    </div>
  );
}


function RecommendationRow({
  title,
  onOpen,
  items,
  cards,
  onAcquire,
}: RecommendationRowProps) {
  // Jedinstven model kartica bilo iz MediaItem liste bilo iz RelatedCard liste.
  const models: PosterCardModel[] = cards
    ? cards.map((card) =>
        card.owned
          ? {
              key: `owned-${card.owned.id}`,
              title: card.owned.title,
              year: card.owned.release_year,
              posterUrl: getFilmiumAssetUrl(
                card.owned.poster_path ?? card.owned.backdrop_path,
              ),
              mediaType: card.owned.media_type,
              isWishlist: false,
              onClick: () => onOpen(card.owned as MediaItem),
            }
          : {
              key: `related-${card.related.tmdb_id}`,
              title: card.related.title,
              year: card.related.year,
              posterUrl: card.related.poster_path
                ? `${TMDB_POSTER_BASE}${card.related.poster_path}`
                : null,
              mediaType: card.related.media_type,
              isWishlist: true,
              onClick: () => onAcquire?.(card.related),
            },
      )
    : (items ?? []).map((mediaItem) => ({
        key: `item-${mediaItem.id}`,
        title: mediaItem.title,
        year: mediaItem.release_year,
        posterUrl: getFilmiumAssetUrl(
          mediaItem.poster_path ?? mediaItem.backdrop_path,
        ),
        mediaType: mediaItem.media_type,
        isWishlist: false,
        onClick: () => onOpen(mediaItem),
      }));

  return (
    <section className="filmium-home-shelf">
      <div className="filmium-home-shelf-heading">
        <h2>{title}</h2>
        <span>{models.length} preporuka</span>
      </div>

      <div className="filmium-details-poster-track">
        {models.map((model) => (
          <button
            className={
              "filmium-details-poster-card"
              + (model.isWishlist ? " is-wishlist" : "")
            }
            key={model.key}
            onClick={model.onClick}
            title={
              model.isWishlist
                ? `${model.title} — dodaj na listu za preuzimanje`
                : model.title
            }
            type="button"
          >
            <div className="filmium-details-poster-card-visual">
              {model.posterUrl ? (
                <img alt={model.title} loading="lazy" src={model.posterUrl} />
              ) : (
                <div className="filmium-details-poster-card-fallback">
                  <span>
                    {model.mediaType === "movie" ? "FILM" : "SERIJA"}
                  </span>
                  <strong>{model.title}</strong>
                </div>
              )}
              {model.isWishlist && (
                <span className="filmium-details-poster-card-badge">
                  Za preuzeti
                </span>
              )}
            </div>

            <div className="filmium-details-poster-card-copy">
              <strong>{model.title}</strong>
              <span>{model.year ?? "—"}</span>
            </div>
          </button>
        ))}
      </div>
    </section>
  );
}

export default FilmiumMediaDetailsPage;
