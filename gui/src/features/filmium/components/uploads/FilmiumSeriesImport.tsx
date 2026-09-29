import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  File,
  FileImage,
  Film,
  LoaderCircle,
  Play,
  Tv,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { getFilmiumLibraryArtworkUrl } from "../../../../services/filmiumLibraryApi";
import {
  sseFilePercent,
  sseOverallPercent,
  type SseProgress,
} from "../../../../services/httpClient";
import { pickAndReplaceArtwork } from "../../utils/replaceArtwork";
import ContentModeToggle, {
  type FilmiumContentMode,
} from "./ContentModeToggle";
import {
  getFilmiumSeriesEpisodeThumbnailUrl,
  getFilmiumTmdbSeason,
  matchFilmiumTmdbSeries,
  probeFilmiumSeriesEpisode,
} from "../../../../services/filmiumSeriesApi";
import type { FilmiumLibraryRoot } from "../../../../types/filmiumLibrary";
import type { FilmiumSeriesImportController } from "../../hooks/useFilmiumSeriesImport";
import type {
  FilmiumSeriesImportResult,
  FilmiumSeriesProbe,
  FilmiumSeriesScan,
  FilmiumTmdbEpisode,
  FilmiumTmdbSeries,
} from "../../../../types/filmiumSeries";
import "../../styles/filmium-library-scan-results.css";
import "../../styles/filmium-series-import.css";


type SeriesImportState = FilmiumSeriesImportController;
type EpisodeKey = { season: number; episode: number };
type ContentTab = "epizode" | "posteri" | "backdropovi" | "fanart" | "extras";

const ART_SLOTS: { label: string; kind: string }[] = [
  { label: "Poster", kind: "poster" },
  { label: "Backdrop", kind: "backdrop" },
  { label: "Wallpaper", kind: "wallpaper" },
  { label: "Fanart", kind: "fanart" },
];


function formatBytes(sizeBytes: number): string {
  if (sizeBytes <= 0) {
    return "0 B";
  }
  const units = ["B", "KB", "MB", "GB", "TB"];
  const power = Math.min(
    units.length - 1,
    Math.floor(Math.log(sizeBytes) / Math.log(1024)),
  );
  const value = sizeBytes / 1024 ** power;
  return `${value.toFixed(power === 0 ? 0 : 2)} ${units[power]}`;
}

function libraryLabel(library: FilmiumLibraryRoot): string {
  const free =
    typeof library.free_bytes === "number"
      ? ` — ${formatBytes(library.free_bytes)} slobodno`
      : "";
  return `${library.name} (${library.path})${free}`;
}

function formatDuration(seconds: number | null | undefined): string | null {
  if (typeof seconds !== "number" || seconds <= 0) {
    return null;
  }
  const totalMinutes = Math.round(seconds / 60);
  if (totalMinutes < 60) {
    return `${totalMinutes} min`;
  }
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  return `${hours}h ${String(minutes).padStart(2, "0")}min`;
}

function formatChannels(channels: number | null): string | null {
  if (!channels) {
    return null;
  }
  const map: Record<number, string> = {
    1: "Mono",
    2: "Stereo",
    6: "5.1",
    8: "7.1",
  };
  return map[channels] ?? `${channels}ch`;
}

function formatVideo(probe: FilmiumSeriesProbe | undefined): string {
  if (!probe || !probe.available) {
    return "—";
  }
  const parts: string[] = [];
  if (probe.width && probe.height) {
    parts.push(`${probe.width}x${probe.height}`);
  }
  if (probe.video_codec) {
    parts.push(probe.video_codec);
  }
  if (probe.frame_rate) {
    parts.push(`${probe.frame_rate} FPS`);
  }
  return parts.length > 0 ? parts.join("  ·  ") : "—";
}

function formatAudio(probe: FilmiumSeriesProbe | undefined): string {
  if (!probe || !probe.available) {
    return "—";
  }
  const parts: string[] = [];
  if (probe.audio_codec) {
    parts.push(probe.audio_codec);
  }
  const channels = formatChannels(probe.audio_channels);
  if (channels) {
    parts.push(channels);
  }
  return parts.length > 0 ? parts.join("  ·  ") : "—";
}


/**
 * Pregled skeniranih serija — svaka kao kompaktna kartica (kao filmovi),
 * sa proširenim detaljnim pregledom na klik.
 */
type SeriesQueueHandler = (
  rootId: number,
  relativeDirectory: string,
  title: string,
  releaseYear: number | null,
  targetLibraryRootId: number | null,
  contentMode: FilmiumContentMode,
  synchronized: boolean,
) => void;

export default function FilmiumSeriesImport({
  libraries,
  onQueue,
  state,
}: {
  libraries: FilmiumLibraryRoot[];
  onQueue?: SeriesQueueHandler;
  state: SeriesImportState;
}) {
  const {
    busyDirectory,
    confirmImport,
    errorMessage,
    isBusy,
    preview,
    reset,
    results,
  } = state;

  if (!preview && !errorMessage) {
    return null;
  }

  const series = preview?.series ?? [];
  const totalSeasons = series.reduce(
    (count, item) => count + item.seasons.length,
    0,
  );
  const totalEpisodes = series.reduce(
    (count, item) =>
      count
      + item.seasons.reduce(
        (sum, season) => sum + season.episodes.length,
        0,
      ),
    0,
  );
  const totalProblems = series.reduce(
    (count, item) => count + item.warnings.length,
    0,
  );
  const seriesLabel = series.length === 1 ? "serija" : "serije";

  return (
    <div className="filmium-series-panel">
      {errorMessage && (
        <div className="system-message error">{errorMessage}</div>
      )}

      {preview && series.length > 0 && (
        <section className="filmium-library-scan-group">
          <div className="filmium-library-scan-result">
            <div className="filmium-library-scan-head">
              <div className="filmium-library-scan-stats">
                <span>
                  <Tv size={15} /> {series.length} {seriesLabel}
                </span>
                <span>
                  <Film size={15} /> {totalSeasons} sezona
                </span>
                <span>
                  <File size={15} /> {totalEpisodes} epizoda
                </span>
                {totalProblems > 0 && (
                  <span>
                    <AlertTriangle size={15} /> {totalProblems} problema
                  </span>
                )}
              </div>
              <button
                aria-label="Obriši rezultate skeniranja serija"
                className="filmium-library-icon-button"
                onClick={reset}
                type="button"
              >
                <X size={18} />
              </button>
            </div>

            <div className="filmium-discovery-toolbar">
              <div>
                <p className="eyebrow">Rezultati poslednjeg skeniranja</p>
                <strong>
                  {series.length} {seriesLabel}
                </strong>
              </div>
            </div>

            <div className="filmium-library-discovery-list">
              {series.map((item) => (
                <SeriesDiscoveryCard
                  busyDirectory={busyDirectory}
                  isBusy={isBusy}
                  key={item.relative_directory}
                  libraries={libraries}
                  onImport={confirmImport}
                  onQueue={onQueue}
                  result={results[item.relative_directory] ?? null}
                  rootId={preview!.rootId}
                  series={item}
                />
              ))}
            </div>
          </div>
        </section>
      )}
    </div>
  );
}


/**
 * Kompaktna kartica serije + prošireni detalj po klik.
 */
function SeriesDiscoveryCard({
  busyDirectory,
  isBusy,
  libraries,
  onImport,
  onQueue,
  result,
  rootId,
  series,
}: {
  busyDirectory: string | null;
  isBusy: boolean;
  libraries: FilmiumLibraryRoot[];
  onImport: (
    relativeDirectory: string,
    targetLibraryRootId?: number | null,
    onProgress?: (progress: SseProgress) => void,
    contentMode?: FilmiumContentMode,
    synchronized?: boolean,
  ) => void | Promise<void>;
  onQueue?: SeriesQueueHandler;
  result: FilmiumSeriesImportResult | null;
  rootId: number;
  series: FilmiumSeriesScan;
}) {
  const [expanded, setExpanded] = useState(false);
  const seasons = series.seasons;
  const totalEpisodes = seasons.reduce(
    (count, season) => count + season.episodes.length,
    0,
  );
  const seasonLabel = seasons.length === 1 ? "sezona" : "sezone";
  const summary = result
    ? `Uvezena — ${result.season_count} ${seasonLabel}, ${result.episode_count} epizoda`
    : `${seasons.length} ${seasonLabel} · ${totalEpisodes} epizoda`
      + (series.warnings.length > 0
        ? ` · ${series.warnings.length} problema`
        : "");

  return (
    <article
      className={[
        "filmium-library-discovery",
        "ready",
        expanded ? "expanded" : "",
        result ? "imported" : "",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      <button
        aria-expanded={expanded}
        className="filmium-library-discovery-summary"
        onClick={() => setExpanded((value) => !value)}
        type="button"
      >
        <SeriesCardArt
          poster={series.poster}
          relativeDirectory={series.relative_directory}
          rootId={rootId}
          title={series.title}
        />
        <span className="filmium-discovery-card-copy">
          <strong>{series.title}</strong>
          <small>{summary}</small>
        </span>
        <span className="filmium-discovery-card-footer">
          <span
            className={`filmium-discovery-badge tone-${
              result ? "available" : "new"
            }`}
          >
            <span className="filmium-discovery-badge-dot" />
            {result ? "Uvezena" : "Serija"}
          </span>
          {expanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
        </span>
      </button>

      {expanded && (
        <div className="filmium-library-discovery-details">
          {result ? (
            <div className="filmium-import-success">
              <CheckCircle2 size={19} />
              <div>
                <strong>„{result.series_title}" je dodata u FILMIUM.</strong>
                <span>
                  {result.season_count} sezona, {result.episode_count}{" "}
                  epizoda.
                </span>
              </div>
            </div>
          ) : (
            <SeriesDetail
              busyDirectory={busyDirectory}
              isBusy={isBusy}
              libraries={libraries}
              onImport={onImport}
              onQueue={onQueue}
              rootId={rootId}
              series={series}
            />
          )}
        </div>
      )}
    </article>
  );
}


/**
 * Bogati detaljni pregled serije (hero, izabrana epizoda, tabovi,
 * umetnička dela, ciljna biblioteka).
 */
function SeriesDetail({
  busyDirectory,
  isBusy,
  libraries,
  onImport,
  onQueue,
  rootId,
  series,
}: {
  busyDirectory: string | null;
  isBusy: boolean;
  libraries: FilmiumLibraryRoot[];
  onImport: (
    relativeDirectory: string,
    targetLibraryRootId?: number | null,
    onProgress?: (progress: SseProgress) => void,
    contentMode?: FilmiumContentMode,
    synchronized?: boolean,
  ) => void | Promise<void>;
  onQueue?: SeriesQueueHandler;
  rootId: number;
  series: FilmiumSeriesScan;
}) {
  const seasons = series.seasons;
  const totalEpisodes = seasons.reduce(
    (count, season) => count + season.episodes.length,
    0,
  );

  const [activeSeason, setActiveSeason] = useState<number>(
    seasons[0]?.season_number ?? 1,
  );
  const [contentTab, setContentTab] = useState<ContentTab>("epizode");
  const [selected, setSelected] = useState<EpisodeKey | null>(
    seasons[0]?.episodes[0]
      ? {
          season: seasons[0].season_number,
          episode: seasons[0].episodes[0].episode_number,
        }
      : null,
  );

  const defaultTarget = useMemo(() => {
    const main = libraries.find((library) => library.is_main);
    return main?.id ?? libraries[0]?.id ?? null;
  }, [libraries]);
  const [targetRootId, setTargetRootId] = useState<number | null>(
    defaultTarget,
  );

  // Stvarni progres uvoza (dva bara: cela serija + tekući fajl).
  const [progress, setProgress] = useState<SseProgress | null>(null);

  // FILM / ANIME / DOMAĆE: rutiranje pri uvozu serije.
  const [contentMode, setContentMode] =
    useState<FilmiumContentMode>("regular");

  // Sinhronizovano (SINH) vs. titlovano (podrazumevano).
  const [synchronized, setSynchronized] = useState(false);

  // Tehnički podaci (ffprobe) se čitaju lenjivo po izabranoj epizodi.
  const [probes, setProbes] = useState<
    Record<string, FilmiumSeriesProbe>
  >({});

  // Verzija slika (za osvežavanje thumb-a posle zamene).
  const [artVersions, setArtVersions] = useState<Record<string, number>>({});

  // TMDB metapodaci (opis/ocene/datumi/still slike) — lenjivo.
  const [tmdb, setTmdb] = useState<FilmiumTmdbSeries | null>(null);
  const [tmdbEpisodes, setTmdbEpisodes] = useState<
    Record<number, Record<number, FilmiumTmdbEpisode>>
  >({});

  // Uparivanje serije na TMDB-u pri otvaranju detalja.
  useEffect(() => {
    let active = true;
    void matchFilmiumTmdbSeries(series.title)
      .then((match) => {
        if (active) {
          setTmdb(match);
        }
      })
      .catch(() => {
        // TMDB je best-effort; bez ključa/pogotka ostaju placeholder-i.
      });
    return () => {
      active = false;
    };
  }, [series.title]);

  const currentSeason =
    seasons.find((season) => season.season_number === activeSeason)
    ?? seasons[0];
  const selectedEpisode = selected
    ? (seasons
        .find((season) => season.season_number === selected.season)
        ?.episodes.find(
          (episode) => episode.episode_number === selected.episode,
        ) ?? null)
    : null;

  const posterUrl = series.poster
    ? getFilmiumLibraryArtworkUrl(rootId, series.relative_directory, series.poster)
    : null;
  const backdropUrl = series.backdrop
    ? getFilmiumLibraryArtworkUrl(
        rootId,
        series.relative_directory,
        series.backdrop,
      )
    : null;

  const isImporting = busyDirectory === series.relative_directory;

  // Lenjivo pročitaj ffprobe za izabranu epizodu (jednom po fajlu).
  const selectedSource = selectedEpisode?.source ?? null;
  useEffect(() => {
    if (!selectedSource || probes[selectedSource]) {
      return;
    }
    let active = true;
    void probeFilmiumSeriesEpisode(rootId, selectedSource)
      .then((probe) => {
        if (active) {
          setProbes((current) => ({ ...current, [selectedSource]: probe }));
        }
      })
      .catch(() => {
        // Probe je best-effort; bez ffprobe ostaju placeholder-i „—".
      });
    return () => {
      active = false;
    };
  }, [rootId, selectedSource, probes]);

  const selectedProbe = selectedSource ? probes[selectedSource] : undefined;

  // TMDB epizode aktivne sezone (jednom po sezoni, kad postoji tmdb_id).
  const tmdbId = tmdb?.tmdb_id ?? null;
  const activeNumber = currentSeason?.season_number ?? null;
  useEffect(() => {
    if (tmdbId === null || activeNumber === null || tmdbEpisodes[activeNumber]) {
      return;
    }
    let active = true;
    void getFilmiumTmdbSeason(tmdbId, activeNumber)
      .then((season) => {
        if (!active) {
          return;
        }
        const byNumber: Record<number, FilmiumTmdbEpisode> = {};
        for (const episode of season.episodes) {
          byNumber[episode.episode_number] = episode;
        }
        setTmdbEpisodes((current) => ({
          ...current,
          [activeNumber]: byNumber,
        }));
      })
      .catch(() => {
        // best-effort
      });
    return () => {
      active = false;
    };
  }, [tmdbId, activeNumber, tmdbEpisodes]);

  const selectedTmdb =
    selectedEpisode
      ? tmdbEpisodes[selectedEpisode.season_number]?.[
          selectedEpisode.episode_number
        ]
      : undefined;

  const galleryKind =
    contentTab === "posteri"
      ? "poster"
      : contentTab === "backdropovi"
        ? "backdrop"
        : contentTab === "fanart"
          ? "fanart"
          : null;
  const gallery = galleryKind
    ? series.artwork.filter((art) => art.kind === galleryKind)
    : [];

  return (
    <div className="filmium-series-detail">
      {/* ==========          HERO          ========== */}
      <header className="filmium-series-hero">
        {backdropUrl && (
          <div
            aria-hidden="true"
            className="filmium-series-hero-backdrop"
            style={{ backgroundImage: `url("${backdropUrl}")` }}
          />
        )}
        <div className="filmium-series-hero-poster">
          {posterUrl ? (
            <img alt={`Poster ${series.title}`} src={posterUrl} />
          ) : (
            <Tv size={30} />
          )}
        </div>
        <div className="filmium-series-hero-body">
          <h2>
            {series.title}
            {tmdb?.matched && tmdb.year ? ` (${tmdb.year})` : ""}
          </h2>
          <p className="filmium-series-hero-meta">
            {tmdb?.matched && tmdb.genres.length > 0
              ? `${tmdb.genres.join(", ")} · `
              : ""}
            {seasons.length} sezona · {totalEpisodes} epizoda
            {tmdb?.matched && tmdb.rating
              ? ` · TMDB ${tmdb.rating}/10`
              : ""}
          </p>
          {tmdb?.matched && tmdb.overview && (
            <p className="filmium-series-hero-overview">{tmdb.overview}</p>
          )}
          <div className="filmium-series-hero-tags">
            <span className="filmium-series-status">Dostupno</span>
            {series.warnings.length > 0 && (
              <span>{series.warnings.length} problema</span>
            )}
          </div>
        </div>
      </header>

      {/* ==========          IZABRANA EPIZODA          ========== */}
      {selectedEpisode && (
        <div className="filmium-series-episode-detail">
          <div className="filmium-series-episode-hero">
            <EpisodeThumb
              rootId={rootId}
              size={26}
              source={selectedEpisode.source}
              stillUrl={selectedTmdb?.still_url ?? null}
            />
            <Play className="filmium-series-play-overlay" size={30} />
          </div>
          <div className="filmium-series-episode-info">
            <div className="filmium-series-episode-head">
              <strong>
                S{String(selectedEpisode.season_number).padStart(2, "0")}
                E{String(selectedEpisode.episode_number).padStart(2, "0")}
                {selectedEpisode.title ?? selectedTmdb?.name
                  ? ` - ${selectedEpisode.title ?? selectedTmdb?.name}`
                  : ""}
              </strong>
              <span className="filmium-series-status">Dostupno</span>
            </div>
            <dl className="filmium-series-episode-meta">
              <div>
                <dt>Datum emitovanja</dt>
                <dd>{selectedTmdb?.air_date ?? "—"}</dd>
              </div>
              <div>
                <dt>Trajanje</dt>
                <dd>
                  {formatDuration(selectedProbe?.duration_seconds) ?? "—"}
                </dd>
              </div>
              <div>
                <dt>TMDB</dt>
                <dd>{selectedTmdb?.rating ? `${selectedTmdb.rating}` : "—"}</dd>
              </div>
              <div>
                <dt>Sezona</dt>
                <dd>{selectedEpisode.season_number}</dd>
              </div>
            </dl>
            {selectedTmdb?.overview ? (
              <small className="filmium-series-episode-overview">
                {selectedTmdb.overview}
              </small>
            ) : (
              <small className="filmium-series-selected-note">
                Opis i datum stižu sa TMDB-a; trajanje i tehnički podaci
                nakon media-probe.
              </small>
            )}
          </div>
          <div className="filmium-series-tech">
            <div className="filmium-series-tech-row">
              <span>Video</span><span>{formatVideo(selectedProbe)}</span>
            </div>
            <div className="filmium-series-tech-row">
              <span>Audio</span><span>{formatAudio(selectedProbe)}</span>
            </div>
            <div className="filmium-series-tech-row">
              <span>Titlovi</span>
              <span>
                {selectedEpisode.subtitles.length > 0
                  ? selectedEpisode.subtitles
                      .slice(0, 6)
                      .map((code) => code.toUpperCase())
                      .join(" ")
                  : "—"}
              </span>
            </div>
            <div className="filmium-series-tech-row path">
              <span>Putanja</span>
              <span title={selectedEpisode.video}>
                {series.title}\Sezona {selectedEpisode.season_number}\
                {selectedEpisode.video}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* ==========          TABOVI          ========== */}
      <div className="filmium-series-tabbar">
        <div className="filmium-series-tabs">
          <span className="filmium-series-tabs-label">Sezona</span>
          {seasons.map((season) => (
            <button
              className={
                season.season_number === currentSeason?.season_number
                  ? "active"
                  : ""
              }
              key={season.season_number}
              onClick={() => {
                setActiveSeason(season.season_number);
                setContentTab("epizode");
              }}
              type="button"
            >
              S{season.season_number}
            </button>
          ))}
          {series.extras.length > 0 && (
            <button
              className={contentTab === "extras" ? "active" : ""}
              onClick={() => setContentTab("extras")}
              type="button"
            >
              Extras
              <span>{series.extras.length}</span>
            </button>
          )}
        </div>
        <div className="filmium-series-subtabs">
          {([
            ["epizode", "Epizode"],
            ["posteri", "Posteri"],
            ["backdropovi", "Backdropovi"],
            ["fanart", "Fanart"],
          ] as const).map(([value, label]) => (
            <button
              className={contentTab === value ? "active" : ""}
              key={value}
              onClick={() => setContentTab(value)}
              type="button"
            >
              {label}
            </button>
          ))}
          <span className="filmium-series-episode-count">
            {currentSeason?.episodes.length ?? 0} epizoda
          </span>
        </div>
      </div>

      {/* ==========          SADRŽAJ TABA          ========== */}
      {contentTab === "epizode" && currentSeason && (
        <div className="filmium-series-episode-grid">
          {currentSeason.episodes.map((episode) => {
            const isSelected =
              selected !== null
              && selected.season === currentSeason.season_number
              && selected.episode === episode.episode_number;

            return (
              <button
                className={`filmium-series-episode-card${
                  isSelected ? " selected" : ""
                }`}
                key={episode.episode_number}
                onClick={() =>
                  setSelected({
                    season: currentSeason.season_number,
                    episode: episode.episode_number,
                  })}
                type="button"
              >
                <div className="filmium-series-episode-thumb">
                  <EpisodeThumb
                    rootId={rootId}
                    size={20}
                    source={episode.source}
                    stillUrl={
                      tmdbEpisodes[currentSeason.season_number]?.[
                        episode.episode_number
                      ]?.still_url ?? null
                    }
                  />
                  <span className="filmium-series-episode-num">
                    {episode.episode_number}
                  </span>
                  {isSelected && (
                    <CheckCircle2
                      className="filmium-series-episode-check"
                      size={17}
                    />
                  )}
                  <span className="filmium-series-episode-dot" />
                </div>
                <div className="filmium-series-episode-copy">
                  <strong>
                    {episode.title ?? `Epizoda ${episode.episode_number}`}
                  </strong>
                  <small>
                    {formatDuration(
                      probes[episode.source]?.duration_seconds,
                    ) ?? "—"}
                  </small>
                </div>
              </button>
            );
          })}
        </div>
      )}

      {galleryKind && (
        gallery.length > 0 ? (
          <div className="filmium-series-gallery">
            {gallery.map((art) => (
              <div className="filmium-series-gallery-item" key={art.file}>
                <img
                  alt={art.kind}
                  loading="lazy"
                  src={getFilmiumLibraryArtworkUrl(
                    rootId,
                    series.relative_directory,
                    art.file,
                  )}
                />
                <span>
                  {art.season ? `Sezona ${art.season}` : "Cela serija"}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <div className="filmium-series-gallery-empty">
            Nije pronađeno.
          </div>
        )
      )}

      {contentTab === "extras" && (
        <div className="filmium-series-extras">
          {series.extras.map((name) => (
            <span className="filmium-series-extra-chip" key={name}>
              {name}
            </span>
          ))}
        </div>
      )}

      {/* ==========          UMETNIČKA DELA          ========== */}
      <section className="filmium-series-artwork">
        <p className="filmium-series-org-title">Otkrivena umetnička dela</p>
        <div className="filmium-import-artwork-grid">
          {ART_SLOTS.map((slot) => {
            const art = series.artwork.find(
              (item) => item.kind === slot.kind,
            );
            const version = artVersions[slot.kind] ?? 0;
            const url = art
              ? `${getFilmiumLibraryArtworkUrl(
                  rootId,
                  series.relative_directory,
                  art.file,
                )}&v=${version}`
              : null;

            const relPath = art
              ? series.relative_directory === "."
                ? art.file
                : `${series.relative_directory}/${art.file}`
              : null;

            return (
              <button
                className={`filmium-import-artwork filmium-artwork-button${
                  art ? " detected" : ""
                }`}
                disabled={!relPath}
                key={slot.kind}
                onClick={() => {
                  if (!relPath) {
                    return;
                  }
                  void pickAndReplaceArtwork(rootId, relPath).then(
                    (ok) => {
                      if (ok) {
                        setArtVersions((current) => ({
                          ...current,
                          [slot.kind]: version + 1,
                        }));
                      }
                    },
                  );
                }}
                title={
                  art
                    ? "Promeni sliku (izaberi novu)"
                    : "Slika nije pronađena"
                }
                type="button"
              >
                <div className="filmium-import-artwork-thumb">
                  {url ? (
                    <img alt={slot.label} loading="lazy" src={url} />
                  ) : (
                    <FileImage size={20} />
                  )}
                </div>
                <div className="filmium-import-artwork-meta">
                  <strong>{slot.label}</strong>
                  <small>{art ? "Promeni" : "Nije pronađeno"}</small>
                </div>
              </button>
            );
          })}
        </div>
      </section>

      {/* ==========          PROGRES UVOZA (DVA BARA)          ========== */}
      {(isImporting || progress) && (
        <div className="filmium-series-import-progress">
          <div className="filmium-series-progress-row">
            <span>Cela serija</span>
            <strong>
              {progress ? sseOverallPercent(progress) : 0}%
            </strong>
          </div>
          <SeriesProgressLine
            value={progress ? sseOverallPercent(progress) : 0}
          />
          <div className="filmium-series-progress-row">
            <span>Trenutni fajl</span>
            <strong>{progress ? sseFilePercent(progress) : 0}%</strong>
          </div>
          <SeriesProgressLine
            value={progress ? sseFilePercent(progress) : 0}
          />
        </div>
      )}

      {/* ==========          FILM / ANIME TOGGLE + SINH          ========== */}
      <div className="filmium-import-mode-row">
        <ContentModeToggle mode={contentMode} onChange={setContentMode} />
        <div className="filmium-sync-row">
          <span className="filmium-sync-label">
            {synchronized ? "Sinhronizovano" : "Titlovano"}
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

      {/* ==========          FOOTER (JEDAN RED)          ========== */}
      <div className="filmium-series-detail-footer">
        <button className="filmium-import-ghost-button" disabled title="Uskoro" type="button">
          Ignoriši seriju
        </button>
        <button className="filmium-import-ghost-button danger" disabled title="Uskoro" type="button">
          Nikada više ne otkrivaj
        </button>
        <select
          aria-label="Ciljna biblioteka"
          className="filmium-import-target-select filmium-series-target-select"
          onChange={(event) => setTargetRootId(Number(event.target.value))}
          value={targetRootId ?? ""}
        >
          {libraries.map((library) => (
            <option key={library.id} value={library.id}>
              {libraryLabel(library)}
            </option>
          ))}
        </select>
        {onQueue && (
          <button
            className="filmium-import-ghost-button"
            onClick={() =>
              onQueue(
                rootId,
                series.relative_directory,
                series.title,
                tmdb?.matched && tmdb.year ? tmdb.year : null,
                targetRootId,
                contentMode,
                synchronized,
              )}
            type="button"
          >
            Dodaj u listu
          </button>
        )}
        <button
          className="primary-button"
          disabled={isBusy}
          onClick={() => {
            setProgress({
              files_done: 0,
              files_total: 0,
              file_done: 0,
              file_total: 0,
            });
            void onImport(
              series.relative_directory,
              targetRootId,
              (value) => setProgress(value),
              contentMode,
              synchronized,
            );
          }}
          type="button"
        >
          {isImporting && <LoaderCircle className="spinning" size={17} />}
          + Biblioteka
        </button>
      </div>
    </div>
  );
}


/**
 * Traka progresa (inline stilizovana, radi i bez dodatnog CSS-a).
 */
function SeriesProgressLine({ value }: { value: number }) {
  const bounded = Math.max(0, Math.min(100, value));

  return (
    <div
      aria-valuemax={100}
      aria-valuemin={0}
      aria-valuenow={bounded}
      className="filmium-series-progress-track"
      role="progressbar"
      style={{
        height: 6,
        borderRadius: 999,
        background: "rgba(255,255,255,0.12)",
        overflow: "hidden",
      }}
    >
      <span
        style={{
          display: "block",
          height: "100%",
          width: `${bounded}%`,
          borderRadius: 999,
          background: "var(--accent, #4f9dff)",
          transition: "width 0.2s ease",
        }}
      />
    </div>
  );
}


/**
 * Sličica epizode (ffmpeg) sa Film ikonom kao rezervom.
 */
function EpisodeThumb({
  rootId,
  size,
  source,
  stillUrl,
}: {
  rootId: number;
  size: number;
  source: string;
  stillUrl?: string | null;
}) {
  // Prvo TMDB still, pa ffmpeg sličica, pa Film ikona.
  const candidates = [
    stillUrl ?? undefined,
    getFilmiumSeriesEpisodeThumbnailUrl(rootId, source),
  ].filter((url): url is string => Boolean(url));
  const [index, setIndex] = useState(0);

  if (index >= candidates.length) {
    return <Film size={size} />;
  }

  return (
    <img
      alt=""
      className="filmium-series-episode-image"
      key={candidates[index]}
      loading="lazy"
      onError={() => setIndex((value) => value + 1)}
      src={candidates[index]}
    />
  );
}


/**
 * Poster serije u kompaktnoj kartici (sa monogramom kao rezervom).
 */
function SeriesCardArt({
  poster,
  relativeDirectory,
  rootId,
  title,
}: {
  poster: string | null;
  relativeDirectory: string;
  rootId: number;
  title: string;
}) {
  const [failed, setFailed] = useState(false);
  const initials = title
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
  const src = poster
    ? getFilmiumLibraryArtworkUrl(rootId, relativeDirectory, poster)
    : getFilmiumLibraryArtworkUrl(rootId, relativeDirectory);

  return (
    <span className="filmium-discovery-card-art">
      {!failed && (
        <img
          alt=""
          loading="lazy"
          onError={() => setFailed(true)}
          src={src}
        />
      )}
      {failed && (
        <span aria-hidden="true" className="filmium-discovery-monogram">
          {initials || "S"}
        </span>
      )}
    </span>
  );
}
