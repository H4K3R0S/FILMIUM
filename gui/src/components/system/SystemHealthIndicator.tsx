import {
  AlertTriangle,
  CheckCircle2,
  RefreshCw,
  X,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { createPortal } from "react-dom";

import {
  getInstallStatus,
  getSystemDependencies,
  startDependencyInstall,
} from "../../services/systemApi";
import {
  DEPENDENCY_TABS,
  countMissing,
  selectForTab,
} from "./dependencyTabs";
import type { DependencyTabId } from "./dependencyTabs";
import type {
  InstallJob,
  SystemDependenciesResponse,
  SystemDependency,
} from "../../types/system";
import "./system-health.css";


const SEVERITY_LABELS: Record<string, string> = {
  critical: "Hitno",
  important: "Važno",
  optional: "Opciono",
};


/**
 * Prikazuje zdravstveni indikator zavisnosti kraj „CORE Online".
 *
 * Zeleno = sve ok, žuto = nešto važno nedostaje, crveno = hitno.
 * Klik otvara panel sa listom i komandama za instalaciju.
 */
export default function SystemHealthIndicator() {
  const [data, setData] = useState<SystemDependenciesResponse | null>(
    null,
  );
  const [isOpen, setIsOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<DependencyTabId>("all");

  const loadHealth = useCallback(async (
    josTraje: () => boolean = () => true,
  ): Promise<void> => {
    try {
      const response = await getSystemDependencies();
      if (josTraje()) {
        setData(response);
      }
    } catch {
      // Backend je verovatno offline — indikator se sakriva.
      if (josTraje()) {
        setData(null);
      }
    }
  }, []);

  // Osvežava se periodično (10s) da bi indikator uhvatio novo instalirane alate.
  useEffect(() => {
    let ziv = true;
    async function pokreni() {
      await loadHealth(() => ziv);
    }
    void pokreni();
    const timer = window.setInterval(() => void loadHealth(() => ziv), 10_000);

    return () => {
      ziv = false;
      window.clearInterval(timer);
    };
  }, [loadHealth]);

  // Otvaranje panela uvek povlači svež status.
  useEffect(() => {
    if (!isOpen) {
      return;
    }
    let ziv = true;
    async function pokreni() {
      await loadHealth(() => ziv);
    }
    void pokreni();
    return () => {
      ziv = false;
    };
  }, [isOpen, loadHealth]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    function handleKeyDown(event: KeyboardEvent): void {
      if (event.key === "Escape") {
        setIsOpen(false);
      }
    }

    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen]);

  if (data === null) {
    return null;
  }

  const missingCount = data.dependencies.filter(
    (dependency) => !dependency.installed,
  ).length;
  const visibleDependencies = selectForTab(data.dependencies, activeTab);

  return (
    <div className={`system-health status-${data.status}`}>
      <button
        aria-label={
          data.status === "ok"
            ? "Zavisnosti sistema: sve u redu"
            : `Zavisnosti sistema: ${missingCount} zahteva akciju`
        }
        className="system-health-trigger"
        onClick={() => setIsOpen((open) => !open)}
        type="button"
      >
        {data.status === "ok" ? (
          <CheckCircle2 size={16} />
        ) : (
          <AlertTriangle size={16} />
        )}
        {missingCount > 0 && (
          <span className="system-health-badge">{missingCount}</span>
        )}
      </button>

      {isOpen && createPortal(
        <div
          className="system-health-overlay"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) {
              setIsOpen(false);
            }
          }}
        >
          <div
            aria-label="Zavisnosti sistema"
            className="system-health-modal"
            role="dialog"
          >
            <div className="system-health-panel-head">
              <div>
                <p className="system-health-eyebrow">Zdravlje sistema</p>
                <strong>Zavisnosti</strong>
              </div>
              <div className="system-health-panel-actions">
                <button
                  aria-label="Osveži"
                  className="system-health-icon-button"
                  onClick={() => void loadHealth()}
                  type="button"
                >
                  <RefreshCw size={15} />
                </button>
                <button
                  aria-label="Zatvori"
                  className="system-health-icon-button"
                  onClick={() => setIsOpen(false)}
                  type="button"
                >
                  <X size={15} />
                </button>
              </div>
            </div>

            {/* ========== TABOVI PO PRIORITETU ========== */}
            <div className="system-health-tabs" role="tablist">
              {DEPENDENCY_TABS.map((tab) => {
                const missing = countMissing(data.dependencies, tab.id);

                return (
                  <button
                    aria-selected={activeTab === tab.id}
                    className={`system-health-tab${
                      activeTab === tab.id ? " active" : ""
                    }`}
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    role="tab"
                    type="button"
                  >
                    {tab.label}
                    {missing > 0 && (
                      <span className="system-health-tab-count">
                        {missing}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>

            <div className="system-health-list">
              {visibleDependencies.length === 0 ? (
                <p className="system-health-empty">
                  Nema alata u ovoj grupi.
                </p>
              ) : (
                visibleDependencies.map((dependency) => (
                  <DependencyRow
                    dependency={dependency}
                    key={dependency.key}
                    onInstalled={() => void loadHealth()}
                  />
                ))
              )}
            </div>
          </div>
        </div>,
        document.body,
      )}
    </div>
  );
}


function DependencyRow({
  dependency,
  onInstalled,
}: {
  dependency: SystemDependency;
  onInstalled: () => void;
}) {
  const [copied, setCopied] = useState(false);
  const [job, setJob] = useState<InstallJob | null>(null);

  const canInstall =
    !dependency.installed && dependency.installer !== "none";
  const isInstalling = job?.status === "running";

  function handleInstall(): void {
    void startDependencyInstall(dependency.key).then((started) => {
      setJob(started);

      const timer = window.setInterval(() => {
        void getInstallStatus().then((next) => {
          setJob(next);

          if (next.status === "done" || next.status === "error") {
            window.clearInterval(timer);

            if (next.status === "done") {
              onInstalled();
            }
          }
        });
      }, 1500);
    });
  }

  function handleCopy(): void {
    if (!navigator.clipboard) {
      return;
    }

    void navigator.clipboard
      .writeText(dependency.install_hint)
      .then(() => {
        setCopied(true);
        window.setTimeout(() => setCopied(false), 1500);
      })
      .catch(() => {
        // Kopiranje nije dostupno — komanda i dalje piše u panelu.
      });
  }

  return (
    <article
      className={`system-health-row${
        dependency.installed ? " ok" : ` missing-${dependency.severity}`
      }`}
    >
      <span className="system-health-row-icon">
        {dependency.installed ? (
          <CheckCircle2 size={15} />
        ) : (
          <AlertTriangle size={15} />
        )}
      </span>
      <div className="system-health-row-copy">
        <div className="system-health-row-head">
          <strong>{dependency.label}</strong>
          {!dependency.installed && (
            <span className="system-health-chip">
              {SEVERITY_LABELS[dependency.severity] ?? dependency.severity}
            </span>
          )}
        </div>
        <small>{dependency.purpose}</small>
        {!dependency.installed && (
          <div className="system-health-command">
            <code title={dependency.install_hint}>{dependency.install_hint}</code>
            <button
              className="system-health-copy"
              onClick={handleCopy}
              type="button"
            >
              {copied ? "Kopirano" : "Kopiraj"}
            </button>
          </div>
        )}
        {canInstall && (
          <button
            className="system-health-install"
            disabled={isInstalling}
            onClick={handleInstall}
            type="button"
          >
            {isInstalling ? "Instaliram…" : "INSTALL"}
          </button>
        )}
        {job && (job.status === "running" || job.status === "error") && (
          <pre className="system-health-log">
            {job.log.slice(-6).join("\n")}
          </pre>
        )}
      </div>
    </article>
  );
}
