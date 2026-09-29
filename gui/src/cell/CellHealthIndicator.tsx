import { useEffect, useState } from "react";

import { getJson } from "../services/httpClient";

// ==========          ZDRAVLJE ĆELIJE (sidebar footer)          ==========
/*
 * Zamena za CORE-ov „CORE Online/Offline" u samostalnoj ćeliji: pokazuje
 * zdravlje SOPSTVENIH podsistema (API, Ollama, RAG), ne vezu sa CORE-om.
 * Anketira `/cell/health` na ~10s; svaka greška je bezopasna (crveno stanje).
 */

type CellHealth = { api: boolean; ollama: boolean; rag: boolean | null };

function CellHealthIndicator() {
  const [health, setHealth] = useState<CellHealth | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let alive = true;

    async function probe(): Promise<void> {
      try {
        const data = await getJson<CellHealth>("/cell/health");
        if (alive) {
          setHealth(data);
          setFailed(false);
        }
      } catch {
        if (alive) {
          setFailed(true);
        }
      }
    }

    void probe();
    const timer = window.setInterval(() => void probe(), 10_000);
    return () => {
      alive = false;
      window.clearInterval(timer);
    };
  }, []);

  const online = !failed && health?.ollama === true;
  const label = failed
    ? "Sistem nedostupan"
    : health === null
      ? "Provera…"
      : health.ollama
        ? "Sistem: u redu"
        : "Ollama nedostupna";

  return (
    <>
      <span className={`connection-indicator ${online ? "online" : "offline"}`} />
      <strong>{label}</strong>
    </>
  );
}

export default CellHealthIndicator;
