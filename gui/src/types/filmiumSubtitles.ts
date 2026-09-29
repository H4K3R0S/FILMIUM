export type SubtitleRepairQueueStatus =
  | "pending"
  | "reviewed"
  | "repaired"
  | "dismissed"
  | "ignored";

export interface SubtitleInspectionIssue {
  issue_type: string;
  message: string;
  severity: "info" | "warning" | "error";
  line_number: number | null;
  original_text: string | null;
  suggested_text: string | null;
}

export interface SubtitleRepairPreview {
  file_name: string;
  detected_encoding: string;
  detected_language_code: string | null;
  original_text: string;
  repaired_text: string;
  changes: unknown[];
  backup_required: boolean;
}

export interface SubtitleInspectionResult {
  file_path: string;
  source_sha256: string;
  file_name: string;
  detected_encoding: string;
  detected_language_code: string | null;
  language_confidence: number;
  is_probably_serbian: boolean;
  needs_repair: boolean;
  issues: SubtitleInspectionIssue[];
  preview: SubtitleRepairPreview;
  queue_item: SubtitleRepairQueueItem | null;
}

export interface SubtitleRepairQueueItem {
  id: number;
  media_id: number | null;
  source_id: number | null;
  file_path: string;
  file_name: string;
  source_sha256: string;
  status: SubtitleRepairQueueStatus;
  detected_encoding: string;
  detected_language_code: string | null;
  language_confidence: number;
  issue_count: number;
  discovered_at: string;
  updated_at: string;
  reviewed_at: string | null;
  resolved_at: string | null;
}

export interface SubtitleRepairStatusRequest {
  status: SubtitleRepairQueueStatus;
}

export interface SubtitleRepairRequest {
  confirmed: boolean;
}

export interface SubtitleRepairResult {
  queue_item: SubtitleRepairQueueItem;
  file_path: string;
  backup_path: string;
  detected_encoding: string;
  applied_change_count: number;
}

export interface SubtitleManualSaveRequest {
  file_path: string;
  source_sha256: string;
  content: string;
  confirmed: boolean;
}

export interface SubtitleManualSaveResult {
  file_path: string;
  backup_path: string;
  source_sha256: string;
  saved_sha256: string;
  output_encoding: string;
  changed_lines: number;
}