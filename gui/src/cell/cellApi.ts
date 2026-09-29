import { getJson, postJson, putJson } from "../services/httpClient";


// ==========          ĆELIJSKI API (generički)          ==========
//
// Domen-agnostičan klijent ćelije: stanje ćelije, persone i asistent. Nijedna
// domenska ruta nije zakucana — asistent gađa generički `/cell/assistant/ask`
// koji cell API nudi samo ako domen ima asistenta; ako ga nema, poziv padne i
// `CellAssistantChat` prikaže razumljivu poruku.

export type CellAssistantAnswer = {
  answer: string;
  sources: string[];
  is_fallback: boolean;
};

export type CellStatus = {
  domain_id: string;
  name: string;
  domain_version: string;
  kernel_version: string;
  port: number;
  operating_system: string;
  node_name: string;
  database_path: string;
  rag_enabled: boolean;
  rag_namespace: string;
  pending_upgrades: number;
  ai_endpoint: string;
  ai_curator_model: string | null;
};

export type CellPersona = {
  id: string;
  name: string;
  markdown: string;
  customized: boolean;
};

export type CellAiConfig = {
  curator_model: string | null;
  endpoint: string;
  default_endpoint: string;
  available_models: string[];
};

export type CellAtom = {
  path: string;
  content: string;
};

/** Pitanje asistentu domena nad lokalnom Ollamom ćelije (ako domen ima asistenta). */
export function askCellAssistant(question: string): Promise<CellAssistantAnswer> {
  return postJson<CellAssistantAnswer, { question: string }>(
    "/cell/assistant/ask",
    { question },
  );
}

/** Stanje ćelije, uključujući Ollama model i adresu iz cell.json. */
export function getCellStatus(): Promise<CellStatus> {
  return getJson<CellStatus>("/cell/status");
}

/** Persone domena ćelije. */
export function listCellPersonas(): Promise<CellPersona[]> {
  return getJson<CellPersona[]>("/cell/personas");
}

/** Upisuje izmenjen tekst persone. */
export function saveCellPersona(id: string, markdown: string): Promise<CellPersona> {
  return putJson<CellPersona, { markdown: string }>(
    `/cell/personas/${encodeURIComponent(id)}`,
    { markdown },
  );
}

/** AI podešavanja ćelije (lokalni model + adresa + dostupni modeli). */
export function getCellAiConfig(): Promise<CellAiConfig> {
  return getJson<CellAiConfig>("/cell/ai-config");
}

/** Upisuje model i adresu u cell.json (primenjuje se po ponovnom pokretanju). */
export function saveCellAiConfig(
  curatorModel: string | null,
  endpoint: string | null,
): Promise<CellAiConfig> {
  return putJson<CellAiConfig, { curator_model: string | null; endpoint: string | null }>(
    "/cell/ai-config",
    { curator_model: curatorModel, endpoint },
  );
}

/** Uređivi Kurator atom fajlovi (persona.md, tools, commands). */
export function listCellAtoms(): Promise<CellAtom[]> {
  return getJson<CellAtom[]>("/cell/kurator/atoms");
}

/** Upisuje sadržaj jednog atoma. `path` je relativan (npr. "tools/pretraga.md"). */
export function saveCellAtom(path: string, content: string): Promise<CellAtom> {
  const delovi = path.split("/").map(encodeURIComponent).join("/");
  return putJson<CellAtom, { content: string }>(`/cell/kurator/atoms/${delovi}`, { content });
}


export type CellJob = {
  id: string;
  opis?: string;
  raspored?: string;
  status?: string;
  last_run?: string | null;
};

/** Registrovani poslovi (jobs/cron) ćelije: id, opis, raspored, status. */
export function listCellJobs(): Promise<CellJob[]> {
  return getJson<CellJob[]>("/api/v1/filmium/jobs");
}

/** Pokreni posao jednokratno (radi u pozadini ćelije). */
export function runCellJob(id: string): Promise<CellJob> {
  return postJson<CellJob, Record<string, never>>(
    `/api/v1/filmium/jobs/${id}/run-once`,
    {},
  );
}
