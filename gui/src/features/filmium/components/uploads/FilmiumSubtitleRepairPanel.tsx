import {
  AlertTriangle,
  Ban,
  Eye,
  FileText,
  LoaderCircle,
  RefreshCw,
  Trash2,
  X,
} from "lucide-react";
import { useState } from "react";
import { createPortal } from "react-dom";

import { useFilmiumSubtitleRepairs } from "../../hooks/useFilmiumSubtitleRepairs";
import type { SubtitleRepairQueueItem } from "../../../../types/filmiumSubtitles";
import FilmiumSubtitleTerminator from "./FilmiumSubtitleTerminator";
import "../../styles/filmium-subtitles.css";

function fileName(filePath: string): string {
  return filePath.split(/[\\/]/).at(-1) ?? filePath;
}

function SubtitleQueueCard({
  busy,
  item,
  onDismiss,
  onIgnore,
  onPreview,
}: {
  busy: boolean;
  item: SubtitleRepairQueueItem;
  onDismiss: () => void;
  onIgnore: () => void;
  onPreview: () => void;
}) {
  return (
    <article className="filmium-subtitle-card">
      <div className="filmium-subtitle-file-icon">
        <FileText size={20} />
      </div>

      <div className="filmium-subtitle-card-content">
        <div className="filmium-subtitle-card-heading">
          <div>
            <h3>{fileName(item.file_path)}</h3>
            <code title={item.file_path}>{item.file_path}</code>
          </div>
          <span className={`status-${item.status}`}>
            {item.status === "reviewed" ? "Pregledano" : "Nova provera"}
          </span>
        </div>

        <div className="filmium-subtitle-facts">
          <span>{item.detected_encoding}</span>
          <span>
            {item.detected_language_code ?? "Nepoznat jezik"}
          </span>
          <span>
            {item.issue_count}{" "}
            {item.issue_count === 1 ? "problem" : "problema"}
          </span>
        </div>

        <div className="filmium-subtitle-card-actions">
          <button
            className="primary-button"
            disabled={busy}
            onClick={onPreview}
            type="button"
          >
            {busy
              ? <LoaderCircle className="spinning" size={16} />
              : <Eye size={16} />}
            Pregledaj popravku
          </button>
          <button
            className="secondary-button"
            disabled={busy}
            onClick={onDismiss}
            type="button"
          >
            <X size={16} />
            Ukloni iz reda
          </button>
          <button
            className="filmium-subtitle-text-button"
            disabled={busy}
            onClick={onIgnore}
            type="button"
          >
            <Ban size={15} />
            Više ne prijavljuj
          </button>
        </div>
      </div>
    </article>
  );
}

export default function FilmiumSubtitleRepairPanel() {
  const repairs = useFilmiumSubtitleRepairs();
  const {
    activeItems,
    busyItemId,
    clearScanResults,
    closeInspection,
    errorMessage,
    isClearing,
    isLoading,
    previewItem,
    refreshQueue,
    setItemStatus,
    successMessage,
  } = repairs;
  const [terminatorOpen, setTerminatorOpen] = useState(false);

  if (
    !isLoading &&
    activeItems.length === 0 &&
    !errorMessage &&
    !successMessage
  ) {
    return null;
  }

  function openTerminator(itemId: number): void {
    void previewItem(itemId);
    setTerminatorOpen(true);
  }

  async function handleClearScanResults(): Promise<void> {
    const confirmed = window.confirm(
      "Obrisati rezultate trenutnog skeniranja?\n\n" +
      "Prevodi, backup fajlovi, ignorisana pravila i istorija " +
      "popravki neće biti obrisani.",
    );

    if (confirmed) {
      await clearScanResults();
    }
  }

  return (
    <section className="filmium-subtitle-panel">
      <div className="filmium-subtitle-heading">
        <div>
          <p className="eyebrow">Automatska kontrola</p>
          <h2>
            <AlertTriangle size={21} />
            Popravi prevod
          </h2>
          <p>
            FILMIUM je pronašao prevode sa pogrešnim kodiranjem ili
            oštećenim srpskim slovima. Original ostaje sačuvan kao{" "}
            <code>.bak</code> pre svake potvrđene izmene.
          </p>
        </div>

        <div className="filmium-subtitle-heading-actions">
          {activeItems.length > 0 && (
            <span>{activeItems.length} za proveru</span>
          )}
          {activeItems.length > 0 && (
            <button
              className="secondary-button"
              disabled={isClearing || isLoading}
              onClick={() => void handleClearScanResults()}
              type="button"
            >
              {isClearing
                ? <LoaderCircle className="spinning" size={16} />
                : <Trash2 size={16} />}
              Obriši trenutno skeniranje
            </button>
          )}
          <button
            aria-label="Osveži prevode za proveru"
            className="filmium-library-icon-button"
            disabled={isLoading}
            onClick={() => void refreshQueue()}
            type="button"
          >
            <RefreshCw
              className={isLoading ? "spinning" : ""}
              size={18}
            />
          </button>
        </div>
      </div>

      {errorMessage && (
        <div className="system-message error">{errorMessage}</div>
      )}

      {successMessage && (
        <div className="system-message success">{successMessage}</div>
      )}

      {isLoading && activeItems.length === 0 ? (
        <div className="filmium-subtitle-loading">
          <LoaderCircle className="spinning" size={18} />
          Proveravam prevode...
        </div>
      ) : (
        <div className="filmium-subtitle-list">
          {activeItems.map((item) => (
            <SubtitleQueueCard
              busy={busyItemId === item.id}
              item={item}
              key={item.id}
              onDismiss={() =>
                void setItemStatus(item.id, "dismissed")}
              onIgnore={() =>
                void setItemStatus(item.id, "ignored")}
              onPreview={() => openTerminator(item.id)}
            />
          ))}
        </div>
      )}

      {/* Portal na document.body: kad je RepairPanel u draweru (EditorPanel),
          predak ima backdrop-filter → „containing block" za position:fixed, pa
          bi Terminator bio veći od prozora (beskonačni skrol). Portal ga vraća
          na viewport — fiksni okvir + unutrašnji skrol liste/preview-a. */}
      {terminatorOpen &&
        createPortal(
          <FilmiumSubtitleTerminator
            controller={repairs}
            onBack={() => {
              setTerminatorOpen(false);
              closeInspection();
            }}
          />,
          document.body,
        )}
    </section>
  );
}
