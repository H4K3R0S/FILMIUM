// ==========          SISTEMSKE ZAVISNOSTI          ==========
// Tipovi za dependency indikator ćelije (dno sidebar-a).

export type SystemHealthStatus = "ok" | "warning" | "critical";

export type SystemDependencySeverity =
  | "critical"
  | "important"
  | "optional";

export interface SystemDependency {
  key: string;
  label: string;
  kind: string;
  severity: SystemDependencySeverity;
  installed: boolean;
  purpose: string;
  install_hint: string;
  installer: "pip" | "npm" | "winget" | "portable_zip" | "none";
}

export interface SystemDependenciesResponse {
  status: SystemHealthStatus;
  dependencies: SystemDependency[];
}

// ==========          INSTALL POSAO          ==========

export interface InstallJob {
  key: string | null;
  status: "idle" | "running" | "done" | "error";
  started_at: string | null;
  returncode: number | null;
  log: string[];
}
