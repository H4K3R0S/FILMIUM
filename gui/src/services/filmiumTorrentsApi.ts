import {
  deleteRequest,
  getJson,
  postFormData,
  postJson,
  putJson,
} from "./httpClient";

import type {
  DiscoveredTorrent,
  Torrent,
  TorrentBulk,
  TorrentReveal,
  TorrentFile,
  TorrentHealth,
  TorrentSettings,
  TorrentSettingsRequest,
  TorrentStatus,
} from "../types/filmiumTorrents";


const BASE = "/api/v1/filmium/torrents";


// ==========          FILMIUM TORRENTI API          ==========

/** Zdravlje veze sa qBittorrent-om. */
export function getTorrentHealth(): Promise<TorrentHealth> {
  return getJson<TorrentHealth>(`${BASE}/health`);
}

/** Lista torrenta; bez filtera vraća sve. */
export function listTorrents(status?: TorrentStatus): Promise<Torrent[]> {
  const query = status ? `?status_filter=${encodeURIComponent(status)}` : "";
  return getJson<Torrent[]>(`${BASE}/${query}`);
}

/** Dodaje magnet link ili putanju do .torrent fajla (pauzirano). */
export function addTorrent(source: string): Promise<Torrent> {
  return postJson<Torrent, { source: string }>(`${BASE}/add`, { source });
}

/** Torrenti pronađeni kao .torrent fajlovi u nadziranim folderima. */
export function listDiscoveredTorrents(): Promise<DiscoveredTorrent[]> {
  return getJson<DiscoveredTorrent[]>(`${BASE}/discovered`);
}

/** Pušta pronađen torrent sa izabranim fajlovima (putanje iz kartice). */
export function startDiscoveredTorrent(
  sourcePath: string,
  selectedPaths: string[],
): Promise<Torrent> {
  return postJson<
    Torrent,
    { source_path: string; selected_paths: string[] }
  >(`${BASE}/discovered/start`, {
    source_path: sourcePath,
    selected_paths: selectedPaths,
  });
}

/** Briše .torrent fajl iz nadziranog foldera; kartica time nestaje. */
export function removeDiscoveredTorrent(sourcePath: string): Promise<void> {
  return deleteRequest<void>(
    `${BASE}/discovered?source_path=${encodeURIComponent(sourcePath)}`,
  );
}

/** Prima prevučen .torrent fajl i upisuje ga u nadzirani folder. */
export function uploadTorrentFile(file: File): Promise<DiscoveredTorrent> {
  const body = new FormData();
  body.append("file", file);
  return postFormData<DiscoveredTorrent>(`${BASE}/upload`, body);
}

/** Lista fajlova unutar torrenta. */
export function listTorrentFiles(infoHash: string): Promise<TorrentFile[]> {
  return getJson<TorrentFile[]>(`${BASE}/${infoHash}/files`);
}

/** Odobrava izabrane fajlove i pokreće preuzimanje. */
export function approveTorrent(
  infoHash: string,
  selectedIndexes: number[],
): Promise<Torrent> {
  return postJson<Torrent, { selected_indexes: number[] }>(
    `${BASE}/${infoHash}/approve`,
    { selected_indexes: selectedIndexes },
  );
}

export function pauseTorrent(infoHash: string): Promise<Torrent> {
  return postJson<Torrent, Record<string, never>>(
    `${BASE}/${infoHash}/pause`,
    {},
  );
}

export function resumeTorrent(infoHash: string): Promise<Torrent> {
  return postJson<Torrent, Record<string, never>>(
    `${BASE}/${infoHash}/resume`,
    {},
  );
}

/** Beleži da je torrent poslat ka ekranu uvoza u biblioteku. */
export function markTorrentHandoff(infoHash: string): Promise<void> {
  return postJson<void, Record<string, never>>(
    `${BASE}/${infoHash}/handoff`,
    {},
  );
}

/** Otvara folder sa preuzetim sadržajem u menadžeru fajlova. */
export function revealTorrentFolder(infoHash: string): Promise<TorrentReveal> {
  return postJson<TorrentReveal, Record<string, never>>(
    `${BASE}/${infoHash}/reveal`,
    {},
  );
}

/** Otkazuje torrent; opciono briše i već skinute fajlove. */
export function removeTorrent(
  infoHash: string,
  deleteFiles = false,
): Promise<void> {
  return deleteRequest<void>(
    `${BASE}/${infoHash}?delete_files=${deleteFiles ? "true" : "false"}`,
  );
}

/** Pauzira sve torrente koji se skidaju; vraća broj pauziranih. */
export function pauseAllTorrents(): Promise<TorrentBulk> {
  return postJson<TorrentBulk, Record<string, never>>(`${BASE}/pause-all`, {});
}

/**
 * Pokreće sve torrente koji mogu da krenu: pauzirane nastavlja, one koji
 * čekaju izbor pušta sa upisanim izborom, a pronađene .torrent fajlove
 * predaje klijentu sa podrazumevanim izborom.
 */
export function startAllTorrents(): Promise<TorrentBulk> {
  return postJson<TorrentBulk, Record<string, never>>(`${BASE}/start-all`, {});
}

export function getTorrentSettings(): Promise<TorrentSettings> {
  return getJson<TorrentSettings>(`${BASE}/settings`);
}

export function saveTorrentSettings(
  settings: TorrentSettingsRequest,
): Promise<TorrentSettings> {
  return putJson<TorrentSettings, TorrentSettingsRequest>(
    `${BASE}/settings`,
    settings,
  );
}
