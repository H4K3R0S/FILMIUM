import { openPathDialog } from "../lib/pathPicker";
import {
  ArrowLeft,
  ChevronRight,
  Film,
  FolderOpen,
  Layers,
  RefreshCw,
  Send,
  Share2,
  Tv,
  Users,
  X,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router";

import { getFilmiumAssetUrl } from "../services/filmiumApi";
import { getFilmiumLibraryRoots } from "../services/filmiumLibraryApi";
import {
  createFilmiumShareProfile,
  getFilmiumShareQueue,
  listFilmiumShareProfiles,
  transferFilmiumShareStream,
  type FilmiumShareProfile,
} from "../services/filmiumShareApi";
import { sseOverallPercent } from "../services/httpClient";
import {
  type ShareScanEntry,
} from "../features/filmium/context/FilmiumWorkspace";
import { useFilmiumWorkspace } from "../features/filmium/context/useFilmiumWorkspace";
import type { MediaCollection, MediaItem } from "../types/filmium";
import type { FilmiumLibraryRoot } from "../types/filmiumLibrary";
import "../features/filmium/styles/filmium-share.css";


// ==========          MODEL STAVKE ZA PRENOS          ==========

/** Jedinstvena stavka u listi za prenos: film/serija iz kataloga ili fajl. */
type ShareEntry = {
  id: string;
  kind: "media" | "file";
  title: string;
  subtitle: string | null;
  posterUrl: string | null;
  mediaType: "movie" | "series" | null;
  path: string | null;
};

/** Koji izvor puni „Dostupni...": poslednje skeniranje, kolekcija ili profil. */
type SourceMode = "scan" | "collection" | "profile";

/** Otvoreni bočni izborni panel (kliza zdesna u okviru dostupnih). */
type SourcePanel = "collections" | "profiles";


function formatBytes(sizeBytes: number | null | undefined): string {
  if (typeof sizeBytes !== "number" || sizeBytes <= 0) {
    return "—";
  }
  const units = ["B", "KB", "MB", "GB", "TB"];
  const power = Math.min(
    units.length - 1,
    Math.floor(Math.log(sizeBytes) / Math.log(1024)),
  );
  return `${(sizeBytes / 1024 ** power).toFixed(power === 0 ? 0 : 2)} ${units[power]}`;
}

function baseName(path: string): string {
  return path.split(/[\\/]/).filter(Boolean).at(-1) ?? path;
}

/** Pretvara stavku poslednjeg skeniranja u stavku za prenos. */
function scanToEntry(entry: ShareScanEntry): ShareEntry {
  return {
    id: entry.id,
    kind: "media",
    title: entry.title,
    subtitle: entry.subtitle,
    posterUrl: null,
    mediaType: entry.mediaType,
    path: entry.directory,
  };
}

/** Pretvara katalog film/seriju u stavku za prenos. */
function mediaToEntry(item: MediaItem): ShareEntry {
  return {
    id: `media:${item.id}`,
    kind: "media",
    title: item.title,
    subtitle: `${item.release_year ?? "—"} · ${
      item.media_type === "movie" ? "Film" : "Serija"
    }`,
    posterUrl: getFilmiumAssetUrl(
      item.poster_path ?? item.backdrop_path,
    ),
    mediaType: item.media_type,
    path: null,
  };
}


/**
 * FILMIUM „Podeli" — full-screen radno okruženje (kliza zdesna) za prenos
 * sadržaja na izabrani disk/lokaciju. Levo dostupni filmovi/serije (poslednje
 * skeniranje, kolekcija ili profil), desno red za slanje sa odredištem.
 */
export default function FilmiumSharePage() {
  const navigate = useNavigate();
  const { catalog, collections, lastScan } = useFilmiumWorkspace();

  const [closing, setClosing] = useState(false);

  const [roots, setRoots] = useState<FilmiumLibraryRoot[]>([]);
  const [sourceMode, setSourceMode] = useState<SourceMode>("scan");
  const [izabraniIzvori, setSourceEntries] = useState<ShareEntry[]>([]);
  const [fileEntries, setFileEntries] = useState<ShareEntry[]>([]);
  const [queue, setQueue] = useState<ShareEntry[]>([]);
  const [destinationRootId, setDestinationRootId] =
    useState<number | null>(null);
  const [customDestination, setCustomDestination] =
    useState<string | null>(null);

  // Prenos (kopiranje) sa progresom.
  const [isTransferring, setIsTransferring] = useState(false);
  const [transferPercent, setTransferPercent] = useState(0);
  const [transferMessage, setTransferMessage] =
    useState<string | null>(null);
  const [transferError, setTransferError] =
    useState<string | null>(null);

  // Bočni izborni panel (kolekcije / profili) + stanje zatvaranja (slide-out).
  const [sourcePanel, setSourcePanel] = useState<SourcePanel | null>(null);
  const [panelClosing, setPanelClosing] = useState(false);
  const [profiles, setProfiles] = useState<FilmiumShareProfile[]>([]);

  // Brz pristup katalogu po ID-u (za kolekcije i redove profila).
  const catalogById = useMemo(
    () => new Map(catalog.items.map((item) => [item.id, item])),
    [catalog.items],
  );

  const refreshRoots = useCallback(async (
    josTraje: () => boolean = () => true,
  ): Promise<void> => {
    try {
      const list = await getFilmiumLibraryRoots();
      if (!josTraje()) {
        return;
      }
      setRoots(list);
      setDestinationRootId((current) =>
        current ?? list.find((root) => root.is_main)?.id ?? list[0]?.id ?? null,
      );
    } catch {
      // tolerantno
    }
  }, []);

  useEffect(() => {
    let ziv = true;
    async function pokreni() {
      await refreshRoots(() => ziv);
    }
    void pokreni();
    return () => {
      ziv = false;
    };
  }, [refreshRoots]);

  // Podrazumevani izvor: rezultati poslednjeg skeniranja iz Uploads-a
  // (Film/Serija/Skeniraj folder). Kolekcija/profil ga zamenjuju.
  //
  // Spisak se IZVODI iz načina i poslednjeg skeniranja, ne prepisuje iz efekta:
  // upis bi značio da se posle svakog skeniranja jedan kadar vidi stari spisak.
  const sourceEntries = useMemo(
    () => (sourceMode === "scan" ? lastScan.map(scanToEntry) : izabraniIzvori),
    [sourceMode, lastScan, izabraniIzvori],
  );

  function handleBack(): void {
    setClosing(true);
  }

  async function addFromDirectory(): Promise<void> {
    const selected = await openPathDialog({
      multiple: true,
      title: "Izaberi fajlove za deljenje",
    });
    if (!selected) {
      return;
    }
    const paths = Array.isArray(selected) ? selected : [selected];
    setFileEntries((current) => {
      const known = new Set(current.map((file) => file.id));
      const added: ShareEntry[] = paths
        .filter((path) => !known.has(path))
        .map((path) => ({
          id: path,
          kind: "file",
          title: baseName(path),
          subtitle: "Fajl",
          posterUrl: null,
          mediaType: null,
          path,
        }));
      return [...current, ...added];
    });
  }

  async function pickDestinationFolder(): Promise<void> {
    const selected = await openPathDialog({
      directory: true,
      multiple: false,
      title: "Izaberi odredišni folder",
    });
    if (typeof selected === "string") {
      setCustomDestination(selected);
    }
  }

  // ==========          BOČNI IZBORNI PANEL          ==========

  function closeSourcePanel(): void {
    setPanelClosing(true);
  }

  function openCollectionsPanel(): void {
    setPanelClosing(false);
    setSourcePanel("collections");
  }

  async function openProfilesPanel(): Promise<void> {
    setPanelClosing(false);
    setSourcePanel("profiles");
    try {
      let list = await listFilmiumShareProfiles();
      // Ako nijedan profil ne postoji, napravi podrazumevani „DEKI".
      if (list.length === 0) {
        await createFilmiumShareProfile({
          name: "DEKI",
          description: "Podrazumevani profil za deljenje.",
        });
        list = await listFilmiumShareProfiles();
      }
      setProfiles(list);
    } catch {
      // tolerantno
    }
  }

  function selectCollection(collection: MediaCollection): void {
    const entries = collection.item_ids
      .map((itemId) => catalogById.get(itemId))
      .filter((item): item is MediaItem => Boolean(item))
      .map(mediaToEntry);
    setSourceMode("collection");
    setSourceEntries(entries);
    closeSourcePanel();
  }

  async function selectProfile(
    profile: FilmiumShareProfile,
  ): Promise<void> {
    try {
      const profileQueue = await getFilmiumShareQueue(profile.id);
      const entries = profileQueue
        .map((item) => catalogById.get(item.media_id))
        .filter((item): item is MediaItem => Boolean(item))
        .map(mediaToEntry);
      setSourceMode("profile");
      setSourceEntries(entries);
    } catch {
      // tolerantno
    }
    closeSourcePanel();
  }

  // ==========          RED ZA SLANJE          ==========

  function moveToQueue(entry: ShareEntry): void {
    setQueue((current) =>
      current.some((item) => item.id === entry.id)
        ? current
        : [...current, entry],
    );
  }

  function removeFromQueue(entry: ShareEntry): void {
    setQueue((current) => current.filter((item) => item.id !== entry.id));
  }

  // Dostupno = izvor (katalog/kolekcija/profil) + fajlovi, bez onih u redu.
  const queuedIds = new Set(queue.map((entry) => entry.id));
  const available = [...sourceEntries, ...fileEntries].filter(
    (entry) => !queuedIds.has(entry.id),
  );

  const availableLabel =
    sourceMode === "collection"
      ? "iz kolekcije"
      : sourceMode === "profile"
        ? "iz profila"
        : "iz poslednjeg skeniranja";

  const destinationRoot = roots.find(
    (root) => root.id === destinationRootId,
  );
  const destinationLabel =
    customDestination ??
    (destinationRoot
      ? `${destinationRoot.path}`
      : "Izaberi odredište");

  // Samo kataloške stavke (media:ID iz kolekcije/profila) se prenose.
  const transferMediaIds = queue
    .filter((entry) => entry.id.startsWith("media:"))
    .map((entry) => Number(entry.id.slice("media:".length)))
    .filter((id) => Number.isFinite(id));

  const transferDestination =
    customDestination ?? destinationRoot?.path ?? null;

  const canTransfer =
    !isTransferring &&
    transferMediaIds.length > 0 &&
    transferDestination !== null;

  async function handleSend(): Promise<void> {
    if (transferDestination === null || transferMediaIds.length === 0) {
      return;
    }

    setIsTransferring(true);
    setTransferPercent(0);
    setTransferMessage(null);
    setTransferError(null);

    try {
      const summary = await transferFilmiumShareStream(
        transferMediaIds,
        transferDestination,
        (progress) => setTransferPercent(sseOverallPercent(progress)),
      );
      setTransferPercent(100);
      const skipped = summary.skipped_media_ids.length;
      setTransferMessage(
        `Preneto ${summary.copied_files} fajlova u ` +
          `${summary.destination}` +
          (skipped > 0 ? ` · ${skipped} preskočeno` : ""),
      );
      const transferred = new Set(
        transferMediaIds.map((id) => `media:${id}`),
      );
      setQueue((current) =>
        current.filter((entry) => !transferred.has(entry.id)),
      );
    } catch (error) {
      setTransferError(
        error instanceof Error ? error.message : "Prenos nije uspeo.",
      );
    } finally {
      setIsTransferring(false);
    }
  }

  // ==========          PRIKAZ          ==========

  // Portal na <body>: „Podeli" je full-screen overlay (position: fixed).
  // Route-stage animacija ostavlja transform ≠ none i pravi containing block,
  // pa bi fixed bio zatvoren unutra i sabijen uz vrh — portal to izbegava.
  return createPortal(
    <div
      className={`filmium-share${closing ? " closing" : ""}`}
      onAnimationEnd={(event) => {
        if (closing && event.target === event.currentTarget) {
          navigate(-1);
        }
      }}
    >
      {/* ==========          HEADER          ========== */}
      <header className="filmium-share-head">
        <button
          className="filmium-share-back"
          onClick={handleBack}
          type="button"
        >
          <ArrowLeft size={18} />
          Nazad
        </button>
        <div className="filmium-share-title">
          <Share2 size={20} />
          <strong>PODELI</strong>
          <span>{queue.length} za slanje</span>
        </div>
      </header>

      {/* ==========          TOOLBAR          ========== */}
      <div className="filmium-share-toolbar">
        <button
          className="filmium-share-tool"
          onClick={openCollectionsPanel}
          type="button"
        >
          <Layers size={16} />
          Dodaj iz kolekcije
        </button>
        <button
          className="filmium-share-tool"
          onClick={() => void addFromDirectory()}
          type="button"
        >
          <FolderOpen size={16} />
          Dodaj iz direktorijuma
        </button>
        <button
          className="filmium-share-tool"
          onClick={() => void openProfilesPanel()}
          type="button"
        >
          <Users size={16} />
          Profili
        </button>
      </div>

      {/* ==========          DVA PANELA          ========== */}
      <div className="filmium-share-body">
        {/* Levo: dostupni filmovi/serije za prenos */}
        <section className="filmium-share-panel">
          <header className="filmium-share-panel-head">
            <span>Dostupni Filmovi / Serije za prenos</span>
            <em>{available.length}</em>
          </header>
          <div className="filmium-share-list">
            {available.length === 0 ? (
              <p className="filmium-share-empty">
                Nema sadržaja {availableLabel}. Dodaj iz kolekcije,
                profila ili direktorijuma.
              </p>
            ) : (
              available.map((entry) => (
                <button
                  className="filmium-share-card"
                  key={entry.id}
                  onClick={() => moveToQueue(entry)}
                  title="Dodaj u red za slanje"
                  type="button"
                >
                  <ShareEntryPoster entry={entry} />
                  <span className="filmium-share-card-text">
                    <strong>{entry.title}</strong>
                    {entry.subtitle && <span>{entry.subtitle}</span>}
                  </span>
                  <ChevronRight size={16} />
                </button>
              ))
            )}
          </div>

          {/* Bočni izbor: kolekcije / profili (kliza zdesna) */}
          {sourcePanel && (
            <div
              className={`filmium-share-subpanel${
                panelClosing ? " closing" : ""
              }`}
              onAnimationEnd={(event) => {
                if (panelClosing && event.target === event.currentTarget) {
                  setSourcePanel(null);
                  setPanelClosing(false);
                }
              }}
            >
              <header className="filmium-share-subpanel-head">
                <span>
                  {sourcePanel === "collections" ? "Kolekcije" : "Profili"}
                </span>
                <button
                  aria-label="Zatvori"
                  className="filmium-share-icon-button"
                  onClick={closeSourcePanel}
                  type="button"
                >
                  <X size={15} />
                </button>
              </header>

              <div className="filmium-share-list">
                {sourcePanel === "collections" ? (
                  collections.collections.length === 0 ? (
                    <p className="filmium-share-empty">
                      Nema kolekcija u bazi.
                    </p>
                  ) : (
                    collections.collections.map((collection) => (
                      <button
                        className="filmium-share-source-card"
                        key={collection.id}
                        onClick={() => selectCollection(collection)}
                        type="button"
                      >
                        <Layers size={16} />
                        <span className="filmium-share-card-text">
                          <strong>{collection.name}</strong>
                          <span>{collection.item_ids.length} sadržaja</span>
                        </span>
                        <ChevronRight size={16} />
                      </button>
                    ))
                  )
                ) : profiles.length === 0 ? (
                  <p className="filmium-share-empty">Učitavam profile…</p>
                ) : (
                  profiles.map((profile) => (
                    <button
                      className="filmium-share-source-card"
                      key={profile.id}
                      onClick={() => void selectProfile(profile)}
                      type="button"
                    >
                      <Users size={16} />
                      <span className="filmium-share-card-text">
                        <strong>{profile.name}</strong>
                        {profile.description && (
                          <span>{profile.description}</span>
                        )}
                      </span>
                      <ChevronRight size={16} />
                    </button>
                  ))
                )}
              </div>
            </div>
          )}
        </section>

        {/* Desno: red za slanje + odredište */}
        <section className="filmium-share-panel">
          <div className="filmium-share-destination">
            <select
              aria-label="Odredišni disk"
              className="filmium-share-select"
              onChange={(event) => {
                setCustomDestination(null);
                setDestinationRootId(Number(event.target.value));
              }}
              value={customDestination ? "" : destinationRootId ?? ""}
            >
              {roots.map((root) => (
                <option key={root.id} value={root.id}>
                  {root.name} — {formatBytes(root.free_bytes)} slobodno
                </option>
              ))}
              {customDestination && (
                <option value="">{baseName(customDestination)} (izbor)</option>
              )}
            </select>
            <button
              className="filmium-share-icon-button"
              onClick={() => void pickDestinationFolder()}
              title="Izaberi lokaciju (folder)"
              type="button"
            >
              <FolderOpen size={16} />
            </button>
            <button
              className="filmium-share-icon-button"
              onClick={() => void refreshRoots()}
              title="Osveži diskove (USB…)"
              type="button"
            >
              <RefreshCw size={16} />
            </button>
          </div>

          <header className="filmium-share-panel-head">
            <span>Za slanje</span>
            <em>{queue.length}</em>
          </header>
          <div className="filmium-share-list">
            {queue.length === 0 ? (
              <p className="filmium-share-empty">
                Klikni sadržaj levo da ga dodaš u red za slanje.
              </p>
            ) : (
              queue.map((entry) => (
                <div className="filmium-share-card queued" key={entry.id}>
                  <ShareEntryPoster entry={entry} />
                  <span className="filmium-share-card-text">
                    <strong>{entry.title}</strong>
                    {entry.subtitle && <span>{entry.subtitle}</span>}
                  </span>
                  <button
                    aria-label="Ukloni iz reda"
                    className="filmium-share-icon-button"
                    onClick={() => removeFromQueue(entry)}
                    type="button"
                  >
                    <X size={15} />
                  </button>
                </div>
              ))
            )}
          </div>

          {(isTransferring || transferPercent > 0) && (
            <div className="filmium-share-progress">
              <div className="filmium-share-progress-head">
                <span>{isTransferring ? "Prenosim…" : "Preneto"}</span>
                <strong>{transferPercent}%</strong>
              </div>
              <div className="filmium-share-progress-track">
                <span style={{ width: `${transferPercent}%` }} />
              </div>
            </div>
          )}

          {transferMessage && (
            <p className="filmium-share-transfer-note ok">
              {transferMessage}
            </p>
          )}
          {transferError && (
            <p className="filmium-share-transfer-note error">
              {transferError}
            </p>
          )}

          <div className="filmium-share-footer">
            <span className="filmium-share-destination-note">
              Odredište: <strong>{destinationLabel}</strong>
            </span>
            <button
              className="primary-button"
              disabled={!canTransfer}
              onClick={() => void handleSend()}
              type="button"
            >
              <Send size={16} />
              {isTransferring
                ? `Prenosim… ${transferPercent}%`
                : `Prenesi (${transferMediaIds.length})`}
            </button>
          </div>
        </section>
      </div>
    </div>,
    document.body,
  );
}


// ==========          POSTER STAVKE          ==========

/** Mali vizuelni indikator: poster filma/serije ili ikonica fajla. */
function ShareEntryPoster({ entry }: { entry: ShareEntry }) {
  if (entry.posterUrl) {
    return (
      <span className="filmium-share-card-poster">
        <img alt="" loading="lazy" src={entry.posterUrl} />
      </span>
    );
  }

  return (
    <span className="filmium-share-card-poster empty">
      {entry.kind === "file" ? (
        <FolderOpen size={16} />
      ) : entry.mediaType === "series" ? (
        <Tv size={16} />
      ) : (
        <Film size={16} />
      )}
    </span>
  );
}
