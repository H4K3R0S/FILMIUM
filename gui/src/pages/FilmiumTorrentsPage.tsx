import { useCallback, useEffect, useMemo, useState } from "react";

import { Upload } from "lucide-react";
import { useNavigate } from "react-router";

import FilmiumTorrentCard from "../features/filmium/components/torrents/FilmiumTorrentCard";
import FilmiumTorrentToolbar from "../features/filmium/components/torrents/FilmiumTorrentToolbar";
import {
  bulkNotice,
  formatBytes,
  formatEta,
} from "../features/filmium/components/torrents/torrentFormat";
import { useTorrentProgress } from "../features/filmium/hooks/useTorrentProgress";
import { TORRENT_DROPPED_EVENT } from "../features/filmium/torrentDrop";
import {
  addTorrent,
  approveTorrent,
  getTorrentHealth,
  getTorrentSettings,
  listDiscoveredTorrents,
  listTorrentFiles,
  listTorrents,
  markTorrentHandoff,
  pauseAllTorrents,
  pauseTorrent,
  removeDiscoveredTorrent,
  removeTorrent,
  revealTorrentFolder,
  resumeTorrent,
  startAllTorrents,
  startDiscoveredTorrent,
  uploadTorrentFile,
} from "../services/filmiumTorrentsApi";

import type {
  TorrentCardModel,
  TorrentCardPlayState,
} from "../features/filmium/components/torrents/FilmiumTorrentCard";
import type {
  DiscoveredTorrent,
  Torrent,
  TorrentFile,
  TorrentHealth,
  TorrentProgress,
  TorrentStatus,
} from "../types/filmiumTorrents";


// ==========          STATUSI          ==========

const STATUS_LABELS: Record<TorrentStatus, string> = {
  detected: "Zabeležen",
  metadata_fetching: "Čeka metapodatke",
  awaiting_approval: "Čeka izbor fajlova",
  downloading: "Skida se",
  paused: "Pauziran",
  completed: "Završen",
  error: "Greška",
};

const STATUS_TONES: Record<TorrentStatus, TorrentCardModel["tone"]> = {
  detected: "waiting",
  metadata_fetching: "waiting",
  awaiting_approval: "waiting",
  downloading: "active",
  paused: "paused",
  completed: "done",
  error: "error",
};

// Statusi za koje se očekuje da se sami promene na serveru (SSE ne nosi
// status, samo napredak preuzimanja) — dok ih ima, lista se periodično
// ponovo učitava.
const PENDING_STATUSES: TorrentStatus[] = [
  "detected",
  "metadata_fetching",
  "downloading",
  // Pauziran torrent qBittorrent i dalje može da dovrši (npr. kad je pauza
  // stigla u samom finišu), pa i on mora da drži anketu u životu.
  "paused",
];

// Razmak između anketa dok ima torrenta u toku.
const POLL_INTERVAL_MS = 4000;

// Razmak između dva skeniranja nadziranih foldera.
const DISCOVERY_INTERVAL_MS = 15000;

// Statusi u kojima sadržaj već postoji (ili se pravi) na disku, pa
// „otvori direktorijum" ima šta da pokaže.
const ON_DISK_STATUSES: TorrentStatus[] = [
  "downloading",
  "paused",
  "completed",
  "error",
];


// ==========          MODELI KARTICA          ==========

/** Koje dugme (start/nastavi/pauza) kartica nudi za dati status. */
function playStateFor(status: TorrentStatus): TorrentCardPlayState {
  if (status === "downloading") {
    return "pause";
  }

  if (status === "paused") {
    return "resume";
  }

  // „Čeka izbor fajlova" pokreće se tek sa štikliranim fajlovima — otuda
  // `start`, a ne `resume`: bez izbora bi se skidalo sve.
  if (status === "awaiting_approval") {
    return "start";
  }

  return null;
}

/** Druga linija kartice za torrent koji je već u qBittorrent-u. */
function managedMeta(
  torrent: Torrent,
  progress: TorrentProgress | undefined,
): string {
  if (torrent.status === "completed") {
    return `Putanja: ${torrent.save_path}`;
  }

  if (torrent.status === "awaiting_approval") {
    return "Otvori karticu i izaberi šta se skida.";
  }

  if (torrent.status === "downloading" || torrent.status === "paused") {
    return (
      `${formatBytes(progress?.downloadRate ?? 0)}/s · `
      + `seed ${progress?.seeds ?? 0} / peer ${progress?.peers ?? 0}`
    );
  }

  return "Čeka podatke iz qBittorrent-a.";
}

function managedModel(
  torrent: Torrent,
  progress: TorrentProgress | undefined,
  files: TorrentFile[] | undefined,
): TorrentCardModel {
  const selectable = torrent.status === "awaiting_approval";
  const known = files ?? [];
  const started = !selectable && torrent.status !== "detected";

  return {
    id: torrent.info_hash,
    name: torrent.name,
    statusLabel: STATUS_LABELS[torrent.status] ?? torrent.status,
    tone: STATUS_TONES[torrent.status] ?? "waiting",
    totalBytes: torrent.total_bytes,
    percent: selectable ? null : Math.round((progress?.progress ?? 0) * 100),
    metaLine: managedMeta(torrent, progress),
    etaLabel:
      torrent.status === "downloading"
        ? formatEta(progress?.etaSeconds ?? null)
        : null,
    files: known.map((file) => ({
      key: String(file.file_index),
      path: file.path,
      sizeBytes: file.size_bytes,
      // Napredak stoji samo uz fajlove koji se stvarno skidaju; kod
      // odštikliranih bi prazna traka lagala da nešto čeka.
      percent:
        started && file.selected ? Math.round(file.progress * 100) : null,
    })),
    errorMessage: torrent.error_message,
    archivedPath:
      torrent.archived_path.length > 0 ? torrent.archived_path : null,
    selectable,
    defaultSelected: known
      .filter((file) => file.selected)
      .map((file) => String(file.file_index)),
    playState: playStateFor(torrent.status),
  };
}

/** Kartica za .torrent fajl koji još nije predat klijentu. */
function discoveredModel(
  found: DiscoveredTorrent,
  unselectedExtensions: string[],
): TorrentCardModel {
  const skipped = (path: string) =>
    unselectedExtensions.some((extension) =>
      path.toLowerCase().endsWith(extension.toLowerCase()));

  return {
    id: found.info_hash,
    name: found.name,
    statusLabel: "Pronađen",
    tone: "found",
    totalBytes: found.total_bytes,
    percent: null,
    metaLine: `${found.files.length} fajlova · ${found.source_path}`,
    etaLabel: null,
    files: found.files.map((file) => ({
      key: file.path,
      path: file.path,
      sizeBytes: file.size_bytes,
      percent: null,
    })),
    errorMessage: null,
    archivedPath: null,
    selectable: true,
    defaultSelected: found.files
      .filter((file) => !skipped(file.path))
      .map((file) => file.path),
    playState: "start",
  };
}


// ==========          STRANICA: TORRENTI          ==========

/**
 * FILMIUM ekran za torrente: gornja traka sa unosom i grupnim radnjama,
 * pa jedna lista kartica.
 *
 * Gore stoje .torrent fajlovi pronađeni u nadziranim folderima — pročitani
 * lokalno, pa se vide i kada qBittorrent ne radi. Ispod njih su torrenti
 * koje je modul već predao klijentu. Svaka kartica se otvara na klik i
 * unutra se štikliranjem bira šta se skida.
 */
function FilmiumTorrentsPage() {
  const [torrents, setTorrents] = useState<Torrent[]>([]);
  const [discovered, setDiscovered] = useState<DiscoveredTorrent[]>([]);
  const [unselectedExtensions, setUnselectedExtensions] = useState<string[]>([]);
  const [health, setHealth] = useState<TorrentHealth | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);
  const [filesByHash, setFilesByHash] = useState<Record<string, TorrentFile[]>>(
    {},
  );
  const [isBusy, setIsBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Ishod poslednje grupne radnje (Start/Stop); bez njega klik izgleda
  // kao da se ništa nije desilo.
  const [notice, setNotice] = useState<string | null>(null);

  const navigate = useNavigate();

  const { progressByHash } = useTorrentProgress();

  const refresh = useCallback(async () => {
    try {
      setTorrents(await listTorrents());
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    }
  }, []);

  const rescan = useCallback(async () => {
    try {
      setDiscovered(await listDiscoveredTorrents());
    } catch {
      // Skeniranje foldera je pomoćno — greška ne sme da sakrije listu.
    }
  }, []);

  /** Ponovo dovlači spisak fajlova za otvorenu karticu (napredak po fajlu). */
  const refreshOpenFiles = useCallback(async (infoHash: string) => {
    try {
      const files = await listTorrentFiles(infoHash);
      setFilesByHash((previous) => ({ ...previous, [infoHash]: files }));
    } catch {
      // Spisak fajlova je pomoćni prikaz; kartica ostaje upotrebljiva.
    }
  }, []);

  useEffect(() => {
    void refresh();
    void rescan();
    void getTorrentHealth().then(setHealth).catch(() => setHealth(null));
    void getTorrentSettings()
      .then((settings) => setUnselectedExtensions(settings.unselected_extensions))
      .catch(() => setUnselectedExtensions([]));
  }, [refresh, rescan]);

  // Prevučen .torrent bilo gde u FILMIUM-u završi u nadziranom folderu;
  // stranica na taj događaj odmah ponovo skenira foldere.
  useEffect(() => {
    const onDropped = () => void rescan();
    window.addEventListener(TORRENT_DROPPED_EVENT, onDropped);
    return () => window.removeEventListener(TORRENT_DROPPED_EVENT, onDropped);
  }, [rescan]);

  // SSE nosi samo napredak, ne i status — dok ima torrenta u nezavršenom
  // statusu (npr. metadata_fetching → awaiting_approval), lista se ponovo
  // učitava svakih par sekundi. Kad ih više nema, anketa staje.
  useEffect(() => {
    const hasPending = torrents.some((item) =>
      PENDING_STATUSES.includes(item.status));

    if (!hasPending) {
      return;
    }

    const timer = window.setTimeout(() => {
      void refresh();
      // Napredak po fajlu ne stiže kroz SSE, pa se otvorena kartica
      // osvežava u istom ritmu kao i lista.
      if (openId !== null) {
        void refreshOpenFiles(openId);
      }
    }, POLL_INTERVAL_MS);

    return () => window.clearTimeout(timer);
  }, [torrents, refresh, openId, refreshOpenFiles]);

  // Nadzirani folderi se skeniraju i bez događaja: .torrent fajl ume da
  // stigne dok stranica nije bila otvorena, ili preko drugog programa.
  useEffect(() => {
    const timer = window.setInterval(() => {
      void rescan();
    }, DISCOVERY_INTERVAL_MS);

    return () => window.clearInterval(timer);
  }, [rescan]);

  const guard = async (action: () => Promise<unknown>) => {
    setIsBusy(true);
    setError(null);
    setNotice(null);

    try {
      await action();
      await refresh();
      await rescan();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setIsBusy(false);
    }
  };

  /** Otvara/zatvara karticu; za već dodat torrent dovlači spisak fajlova. */
  const toggleOpen = (id: string, needsFiles: boolean) => {
    if (openId === id) {
      setOpenId(null);
      return;
    }

    setOpenId(id);

    if (!needsFiles) {
      return;
    }

    void refreshOpenFiles(id);
  };

  // Pronađen .torrent bez statusa još nije predat klijentu — ili je zapis o
  // njemu zastareo (sadržaj obrisan sa diska), pa server javlja da statusa
  // nema. U oba slučaja kartica kreće iznova, sa podrazumevanim izborom.
  const waiting = discovered.filter((item) => item.status === null);

  // Zastareo zapis se ne prikazuje pored svoje nove kartice; isti torrent
  // stoji u listi tačno jednom.
  const freshHashes = useMemo(
    () =>
      new Set(
        discovered
          .filter((item) => item.status === null)
          .map((item) => item.info_hash.toLowerCase()),
      ),
    [discovered],
  );

  const managed = torrents.filter(
    (item) => !freshHashes.has(item.info_hash.toLowerCase()),
  );

  const hasAnything = waiting.length > 0 || managed.length > 0;

  // „Start" pušta sve što može da krene: pauzirane, one koji čekaju izbor
  // fajlova i pronađene .torrent fajlove koji još nisu stigli do klijenta.
  const canStartAll =
    waiting.length > 0
    || managed.some(
      (item) => item.status === "paused" || item.status === "awaiting_approval",
    );

  /** Pušta pronađen torrent sa štikliranim fajlovima. */
  const startFound = (found: DiscoveredTorrent, selectedKeys: string[]) => {
    void guard(async () => {
      await startDiscoveredTorrent(found.source_path, selectedKeys);
      setOpenId(null);
    });
  };

  return (
    <section className="filmium-section filmium-torrents-page">
      <div className="section-heading">
        <p className="eyebrow">FILMIUM Torrenti</p>
        <h2>Torrenti</h2>

        <p className="filmium-page-description">
          Torrenti iz nadziranih foldera, izbor sadržaja i praćenje
          preuzimanja preko qBittorrent-a. Prevuci .torrent fajl bilo gde
          u FILMIUM-u da ga dodaš.
        </p>
      </div>

      {health !== null && !health.engine_available && (
        <p className="filmium-torrent-banner">
          {health.message
            ?? "qBittorrent nije dostupan. Proveri da li radi i da li je Web UI uključen."}
        </p>
      )}

      <FilmiumTorrentToolbar
        isBusy={isBusy}
        onAddFiles={(files) =>
          guard(async () => {
            for (const file of files) {
              await uploadTorrentFile(file);
            }
          })}
        onAddMagnet={(source) => guard(() => addTorrent(source))}
        canStartAll={canStartAll}
        canStopAll={managed.some((item) => item.status === "downloading")}
        onStartAll={() =>
          void guard(async () => {
            const { affected, failed } = await startAllTorrents();
            setNotice(
              failed > 0
                ? `${bulkNotice("Pokrenut", affected)}`
                  + ` Nije pokrenuto: ${failed}.`
                : bulkNotice("Pokrenut", affected),
            );
          })}
        onStopAll={() =>
          void guard(async () => {
            const { affected } = await pauseAllTorrents();
            setNotice(bulkNotice("Pauziran", affected));
          })}
      />

      {error !== null && <p className="filmium-torrent-error">{error}</p>}

      {notice !== null && (
        <p aria-live="polite" className="filmium-torrent-notice" role="status">
          {notice}
        </p>
      )}

      {!hasAnything ? (
        <p className="filmium-torrent-empty">
          Nema torrenta. Dodaj magnet link, prevuci .torrent fajl ili upiši
          nadzirani folder u FILMIUM podešavanjima.
        </p>
      ) : (
        <ul className="filmium-torrent-cards">
          {waiting.map((found) => (
            <FilmiumTorrentCard
              isBusy={isBusy}
              isOpen={openId === found.info_hash}
              key={found.info_hash}
              model={discoveredModel(found, unselectedExtensions)}
              onPlay={(selectedKeys) => startFound(found, selectedKeys)}
              onPrimary={(selectedKeys) => startFound(found, selectedKeys)}
              onRemove={() => {
                // Torrent koji je već poslat u biblioteku ne traži pitanje —
                // izvorni .torrent fajl više nikome ne treba. Ako predaje
                // nije bilo, brisanje izvornog fajla se izričito potvrđuje.
                if (!found.handed_to_library) {
                  const potvrdjeno = window.confirm(
                    `„${found.name}" nije poslat u biblioteku.\n\n`
                    + "Ukloniti ipak i obrisati izvorni .torrent fajl?\n"
                    + found.source_path,
                  );

                  if (!potvrdjeno) {
                    return;
                  }
                }

                void guard(() => removeDiscoveredTorrent(found.source_path));
              }}
              onToggleOpen={() => toggleOpen(found.info_hash, false)}
              primaryLabel="Preuzmi izabrano"
            />
          ))}

          {managed.map((torrent) => {
            const model = managedModel(
              torrent,
              progressByHash[torrent.info_hash],
              filesByHash[torrent.info_hash],
            );

            /** Odobrenje i start su ista radnja: izbor pa pokretanje. */
            const approve = (selectedKeys: string[]) => {
              void guard(async () => {
                await approveTorrent(
                  torrent.info_hash,
                  selectedKeys.map(Number),
                );
                setOpenId(null);
              });
            };

            return (
              <FilmiumTorrentCard
                extraControls={
                  torrent.status === "completed" ? (
                    <button
                      aria-label="Pošalji u biblioteku"
                      className="filmium-icon-button"
                      onClick={() => {
                        // Predaja se beleži pre odlaska na ekran uvoza:
                        // po njoj se kasnije izvorni .torrent briše bez
                        // dodatnog pitanja.
                        void markTorrentHandoff(torrent.info_hash)
                          .catch(() => {
                            /* beleška je pomoćna — uvoz se i dalje otvara */
                          })
                          .then(() => navigate("/filmium/uploads"));
                      }}
                      title="Pošalji u biblioteku (otvara ekran uvoza)"
                      type="button"
                    >
                      <Upload size={16} />
                    </button>
                  ) : undefined
                }
                isBusy={isBusy}
                isOpen={openId === torrent.info_hash}
                key={torrent.info_hash}
                model={model}
                onOpenFolder={
                  ON_DISK_STATUSES.includes(torrent.status)
                    ? () => void guard(() => revealTorrentFolder(torrent.info_hash))
                    : undefined
                }
                onPause={() => void guard(() => pauseTorrent(torrent.info_hash))}
                onPlay={(selectedKeys) => {
                  if (model.selectable) {
                    approve(selectedKeys);
                    return;
                  }

                  void guard(() => resumeTorrent(torrent.info_hash));
                }}
                onPrimary={model.selectable ? approve : undefined}
                onRemove={() => {
                  const potvrdjeno = window.confirm(
                    `Ukloniti torrent „${torrent.name}" iz liste? `
                    + "Već skinuti fajlovi ostaju na disku.",
                  );

                  if (potvrdjeno) {
                    void guard(() => removeTorrent(torrent.info_hash));
                  }
                }}
                onToggleOpen={() => toggleOpen(torrent.info_hash, true)}
                primaryLabel={model.selectable ? "Odobri i skini" : undefined}
              />
            );
          })}
        </ul>
      )}
    </section>
  );
}

export default FilmiumTorrentsPage;
