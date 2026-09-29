// ==========          FILMIUM BULK CRON API          ==========

import { getJson, postRequest } from "./httpClient";


export interface CronStatus {
  status: "idle" | "running" | "done" | "stopped";
  total?: number;
  cursor?: number;
  done_count?: number;
  error_count?: number;
  current?: { id: number; title: string } | null;
  started_at?: string;
  updated_at?: string;
}


/**
 * Trenutno stanje pozadinskog bulk auto-update posla.
 */
export function getFilmiumCronStatus(): Promise<CronStatus> {
  return getJson<CronStatus>("/api/v1/filmium/auto-update/status");
}


/**
 * Pokreće bulk auto-update (lista svih filmova/serija + obrada u pozadini).
 */
export function startFilmiumCron(): Promise<CronStatus> {
  return postRequest<CronStatus>("/api/v1/filmium/auto-update/start");
}


/**
 * Zaustavlja bulk auto-update posao.
 */
export function stopFilmiumCron(): Promise<CronStatus> {
  return postRequest<CronStatus>("/api/v1/filmium/auto-update/stop");
}
