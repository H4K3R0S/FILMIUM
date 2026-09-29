import { useEffect, useRef, useState } from "react";

import { getApiUrl } from "../../../services/httpClient";

import type { TorrentProgress } from "../../../types/filmiumTorrents";


type ProgressPayload = {
  info_hash: string;
  progress?: number;
  download_rate?: number;
  upload_rate?: number;
  eta_seconds?: number | null;
  seeds?: number;
  peers?: number;
  is_finished?: boolean;
  is_paused?: boolean;
};

// Pauza pre ponovnog povezivanja kad strim pukne.
const RECONNECT_DELAY_MS = 3000;


// ==========          PROGRES TORRENTA (SSE)          ==========

/**
 * Čita `/api/v1/filmium/torrents/stream` i drži progres po info hash-u.
 *
 * Strim se otvara jednom po komponenti; pri prekidu veze pokušava ponovo
 * posle kratke pauze. Tolerantan na neispravan JSON — takav otkucaj
 * se preskače umesto da obori komponentu.
 */
export function useTorrentProgress(): {
  progressByHash: Record<string, TorrentProgress>;
  isConnected: boolean;
} {
  const [progressByHash, setProgressByHash] = useState<
    Record<string, TorrentProgress>
  >({});
  const [isConnected, setIsConnected] = useState(true);
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    let source: EventSource | null = null;
    let cancelled = false;

    const connect = () => {
      if (cancelled) {
        return;
      }

      source = new EventSource(getApiUrl("/api/v1/filmium/torrents/stream"));
      setIsConnected(true);

      source.addEventListener("progress", (event: MessageEvent) => {
        try {
          const rows = JSON.parse(event.data) as ProgressPayload[];
          const next: Record<string, TorrentProgress> = {};

          for (const row of rows) {
            next[row.info_hash] = {
              infoHash: row.info_hash,
              progress: row.progress ?? 0,
              downloadRate: row.download_rate ?? 0,
              uploadRate: row.upload_rate ?? 0,
              etaSeconds: row.eta_seconds ?? null,
              seeds: row.seeds ?? 0,
              peers: row.peers ?? 0,
              isFinished: row.is_finished ?? false,
              isPaused: row.is_paused ?? false,
            };
          }

          setProgressByHash(next);
        } catch {
          // Neispravan otkucaj se preskače.
        }
      });

      source.onerror = () => {
        setIsConnected(false);
        source?.close();
        timerRef.current = window.setTimeout(connect, RECONNECT_DELAY_MS);
      };
    };

    connect();

    return () => {
      cancelled = true;
      if (timerRef.current !== null) {
        window.clearTimeout(timerRef.current);
      }
      source?.close();
    };
  }, []);

  return { progressByHash, isConnected };
}
