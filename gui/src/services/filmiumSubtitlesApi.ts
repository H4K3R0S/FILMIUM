import {
  deleteRequest,
  getJson,
  patchJson,
  postJson,
  postRequest,
} from "./httpClient";
import type {
  SubtitleInspectionResult,
  SubtitleManualSaveRequest,
  SubtitleManualSaveResult,
  SubtitleRepairQueueItem,
  SubtitleRepairRequest,
  SubtitleRepairResult,
  SubtitleRepairStatusRequest,
} from "../types/filmiumSubtitles";

const SUBTITLES_ENDPOINT = "/api/v1/filmium/subtitles";

export interface SubtitleRepairQueueClearResult {
  deleted_count: number;
}

export function getSubtitleRepairQueue():
Promise<SubtitleRepairQueueItem[]> {
  return getJson<SubtitleRepairQueueItem[]>(
    `${SUBTITLES_ENDPOINT}/repair-queue`,
  );
}

export function clearSubtitleRepairScanResults():
Promise<SubtitleRepairQueueClearResult> {
  return deleteRequest<SubtitleRepairQueueClearResult>(
    `${SUBTITLES_ENDPOINT}/repair-queue?confirmed=true`,
  );
}

export function previewSubtitleRepair(
  itemId: number,
): Promise<SubtitleInspectionResult> {
  return postRequest<SubtitleInspectionResult>(
    `${SUBTITLES_ENDPOINT}/repair-queue/${itemId}/preview`,
  );
}

export function updateSubtitleRepairStatus(
  itemId: number,
  request: SubtitleRepairStatusRequest,
): Promise<SubtitleRepairQueueItem> {
  return patchJson<
    SubtitleRepairQueueItem,
    SubtitleRepairStatusRequest
  >(
    `${SUBTITLES_ENDPOINT}/repair-queue/${itemId}/status`,
    request,
  );
}

export function repairSubtitle(
  itemId: number,
  request: SubtitleRepairRequest,
): Promise<SubtitleRepairResult> {
  return postJson<SubtitleRepairResult, SubtitleRepairRequest>(
    `${SUBTITLES_ENDPOINT}/repair-queue/${itemId}/repair`,
    request,
  );
}

/** Editor mod: učitava bilo koji SRT po putanji (van reda popravke). */
export function editPreviewSubtitle(
  filePath: string,
): Promise<SubtitleInspectionResult> {
  return postJson<SubtitleInspectionResult, { file_path: string }>(
    `${SUBTITLES_ENDPOINT}/edit/preview`,
    { file_path: filePath },
  );
}

/** Editor mod: snima ručno izmenjen sadržaj (sha provera + backup). */
export function saveEditedSubtitle(
  request: SubtitleManualSaveRequest,
): Promise<SubtitleManualSaveResult> {
  return postJson<SubtitleManualSaveResult, SubtitleManualSaveRequest>(
    `${SUBTITLES_ENDPOINT}/edit/save`,
    request,
  );
}

export interface SubtitleTransliterateResult {
  from_script: string;
  to_script: string;
  source: string;
  created: string;
  created_name: string;
}

/** Prepozna pismo prevoda i napravi drugo (latinica↔ćirilica) u nov fajl. */
export function transliterateSubtitle(
  filePath: string,
): Promise<SubtitleTransliterateResult> {
  return postJson<SubtitleTransliterateResult, { file_path: string }>(
    `${SUBTITLES_ENDPOINT}/transliterate`,
    { file_path: filePath },
  );
}
