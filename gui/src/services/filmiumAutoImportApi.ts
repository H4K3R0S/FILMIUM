import {
  deleteRequest,
  getJson,
  postJson,
  postRequest,
} from "./httpClient";

import type {
  AutoImportRule,
  AutoImportRuleRequest,
  DetectedFile,
  DetectedFileStatus,
  MonitoredFolder,
} from "../types/filmiumAutoImport";


const BASE = "/api/v1/filmium/auto-import";


// ==========          FILMIUM AUTO-IMPORT API          ==========

/**
 * Dodaje folder za automatsko praćenje sa pravilom uvoza.
 */
export function addMonitoredFolder(
  rule: AutoImportRuleRequest,
): Promise<AutoImportRule> {
  return postJson<AutoImportRule, AutoImportRuleRequest>(
    `${BASE}/folders`,
    rule,
  );
}

/**
 * Vraća praćene foldere i njihov status.
 */
export function listMonitoredFolders(): Promise<MonitoredFolder[]> {
  return getJson<MonitoredFolder[]>(`${BASE}/folders`);
}

/**
 * Uklanja folder iz praćenja.
 */
export function removeMonitoredFolder(path: string): Promise<void> {
  return deleteRequest<void>(
    `${BASE}/folders?path=${encodeURIComponent(path)}`,
  );
}

/**
 * Vraća detektovane fajlove; opciono filtrirano po statusu.
 */
export function listDetectedFiles(
  status?: DetectedFileStatus,
): Promise<DetectedFile[]> {
  const query = status ? `?status=${encodeURIComponent(status)}` : "";
  return getJson<DetectedFile[]>(`${BASE}/detected${query}`);
}

/**
 * Potvrđuje uvoz detektovanog fajla.
 */
export function confirmDetectedImport(fileId: number): Promise<DetectedFile> {
  return postRequest<DetectedFile>(`${BASE}/confirm/${fileId}`);
}

/**
 * Odbacuje detektovani fajl.
 */
export function rejectDetectedImport(fileId: number): Promise<DetectedFile> {
  return postRequest<DetectedFile>(`${BASE}/reject/${fileId}`);
}
