import { getJson, postRequest } from "./httpClient";

import type {
  InstallJob,
  SystemDependenciesResponse,
} from "../types/system";


// ==========          SISTEMSKI API (ZAVISNOSTI)          ==========

/**
 * Učitava zdravstveni status svih zavisnosti ćelije.
 */
export function getSystemDependencies(): Promise<SystemDependenciesResponse> {
  return getJson<SystemDependenciesResponse>(
    "/api/v1/system/dependencies",
  );
}


/**
 * Pokreće instalaciju alata po ključu zavisnosti.
 */
export function startDependencyInstall(key: string): Promise<InstallJob> {
  return postRequest<InstallJob>(
    `/api/v1/system/dependencies/${encodeURIComponent(key)}/install`,
  );
}


/**
 * Status trenutnog install posla (za polling).
 */
export function getInstallStatus(): Promise<InstallJob> {
  return getJson<InstallJob>("/api/v1/system/install/status");
}
