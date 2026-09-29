// ==========          TIPOVI: FILMIUM AUTO-IMPORT          ==========

export interface AutoImportRuleRequest {
  folder_path: string;
  file_types?: string[];
  min_size_mb?: number;
  auto_scan?: boolean;
  auto_import?: boolean;
  target_library_id?: number | null;
  security_scan?: boolean;
}

export interface AutoImportRule {
  id: number;
  folder_path: string;
  file_types: string[];
  min_size_mb: number;
  auto_scan: boolean;
  auto_import: boolean;
  target_library_id: number | null;
  security_scan: boolean;
  created_at: string;
}

export interface MonitoredFolder {
  folder_path: string;
  is_active: boolean;
  rule_id: number | null;
  last_check: string | null;
}

export type DetectedFileStatus =
  | "detected"
  | "scanning"
  | "ready"
  | "imported"
  | "rejected";

export type SecurityStatus =
  | "unknown"
  | "clean"
  | "suspicious"
  | "malware";

export interface DetectedFile {
  id: number;
  file_path: string;
  file_size: number;
  rule_id: number | null;
  status: DetectedFileStatus;
  security_status: SecurityStatus;
  scan_result: Record<string, unknown> | null;
  detected_at: string;
}
