import { useEffect, useMemo, useState } from "react";

import { ChevronDown, FileDown, FolderOpen, Pause, Play, X } from "lucide-react";

import { formatBytes } from "./torrentFormat";

import type { CSSProperties, ReactNode } from "react";


// ==========          MODEL KARTICE          ==========

export type TorrentCardFile = {
  /** Ključ izbora: putanja unutar torrenta ili indeks fajla. */
  key: string;
  path: string;
  sizeBytes: number;
  /** Napredak fajla (0–100); `null` dok preuzimanje nije krenulo. */
  percent: number | null;
};

/** Ton statusa; određuje boju pločice, ne i tekst. */
export type TorrentCardTone =
  | "found"
  | "waiting"
  | "active"
  | "paused"
  | "done"
  | "error";

/**
 * Koje dugme stoji na kartici:
 * `start` — preuzimanje još nije krenulo, kreće sa štikliranim fajlovima;
 * `resume` — pauziran torrent se nastavlja;
 * `pause` — torrent se skida i može da stane;
 * `null` — nema šta da se pokrene (završen, greška, čeka metapodatke).
 */
export type TorrentCardPlayState = "start" | "resume" | "pause" | null;

export type TorrentCardModel = {
  id: string;
  name: string;
  statusLabel: string;
  tone: TorrentCardTone;
  totalBytes: number;
  /** 0–100 dok preuzimanje traje; `null` dok ga još nema. */
  percent: number | null;
  /** Druga linija ispod naslova (brzina, seed/peer, putanja). */
  metaLine: string;
  /** Procenjeno preostalo vreme; `null` kad ga nema. */
  etaLabel: string | null;
  files: TorrentCardFile[];
  errorMessage: string | null;
  /** Putanja do kopije .torrent fajla u CORE-u; `null` kad kopije nema. */
  archivedPath: string | null;
  /** Da li se fajlovi štikliraju (pre nego što preuzimanje krene). */
  selectable: boolean;
  /** Ključevi koji su unapred štiklirani. */
  defaultSelected: string[];
  playState: TorrentCardPlayState;
};

const PLAY_LABELS: Record<"start" | "resume" | "pause", string> = {
  start: "Pokreni preuzimanje",
  resume: "Nastavi preuzimanje",
  pause: "Pauziraj preuzimanje",
};


// ==========          KARTICA TORRENTA          ==========

type Props = {
  model: TorrentCardModel;
  isOpen: boolean;
  onToggleOpen: () => void;
  isBusy?: boolean;
  /** Tekst glavnog dugmeta u otvorenoj kartici; bez njega ga nema. */
  primaryLabel?: string;
  onPrimary?: (selectedKeys: string[]) => void;
  /** Start/nastavi — dobija tekući izbor fajlova (bitno za `start`). */
  onPlay?: (selectedKeys: string[]) => void;
  onPause?: () => void;
  /** Otvara folder sa preuzetim sadržajem. */
  onOpenFolder?: () => void;
  /** „X" — uklanja karticu iz listinga. */
  onRemove?: () => void;
  /** Dodatne sitne radnje (npr. put ka uvozu za završen torrent). */
  extraControls?: ReactNode;
};

/**
 * Jedna kartica u listi torrenta: naslov, status, napredak i — na klik —
 * sadržaj torrenta sa štikliranjem i napretkom po fajlu.
 *
 * Napredak se crta dvostruko: kao popuna pozadine cele kartice
 * (`--torrent-progress`) i kao tanka traka ispod naslova.
 *
 * Izbor fajlova živi u kartici, a napolje izlazi tek pri radnji
 * („Preuzmi izabrano" ili start), pa otvaranje kartice ništa ne pokreće.
 */
function FilmiumTorrentCard({
  model,
  isOpen,
  onToggleOpen,
  isBusy = false,
  primaryLabel,
  onPrimary,
  onPlay,
  onPause,
  onOpenFolder,
  onRemove,
  extraControls,
}: Props) {
  const [selected, setSelected] = useState<Set<string>>(
    () => new Set(model.defaultSelected),
  );

  // Osvežen spisak sa servera vraća izbor na podrazumevani — dok se kartica
  // ne otvori, izbor ionako niko nije dirao.
  useEffect(() => {
    setSelected(new Set(model.defaultSelected));
    // Zavisnost je spisak, a ne sam niz: nova referenca iz svake ankete bi
    // inače brisala izbor korisniku dok bira fajlove.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [model.defaultSelected.join(" ")]);

  const selectedBytes = useMemo(
    () =>
      model.files
        .filter((file) => selected.has(file.key))
        .reduce((sum, file) => sum + file.sizeBytes, 0),
    [model.files, selected],
  );

  const toggle = (key: string) => {
    setSelected((previous) => {
      const next = new Set(previous);

      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }

      return next;
    });
  };

  const percent = model.percent;
  const playState = model.playState;

  return (
    <li
      className="filmium-torrent-card-row"
      data-open={isOpen ? "on" : "off"}
      data-tone={model.tone}
      style={{ "--torrent-progress": `${percent ?? 0}%` } as CSSProperties}
    >
      <div className="filmium-torrent-card-main">
        <button
          aria-expanded={isOpen}
          className="filmium-torrent-card-open"
          onClick={onToggleOpen}
          type="button"
        >
          <span aria-hidden="true" className="filmium-torrent-card-badge">
            <FileDown size={20} />
          </span>

          <span className="filmium-torrent-card-text">
            <span className="filmium-torrent-card-name">{model.name}</span>

            <span className="filmium-torrent-card-meta">{model.metaLine}</span>
          </span>

          {model.etaLabel !== null && (
            <span className="filmium-torrent-card-eta">
              {`preostalo ${model.etaLabel}`}
            </span>
          )}

          <span className="filmium-torrent-card-size">
            {formatBytes(model.totalBytes)}
          </span>

          <span className="filmium-torrent-status" data-tone={model.tone}>
            {model.statusLabel}
          </span>

          <span aria-hidden="true" className="filmium-torrent-card-chevron">
            <ChevronDown size={18} />
          </span>
        </button>

        <div className="filmium-torrent-card-controls">
          {extraControls}

          {onOpenFolder !== undefined && (
            <button
              aria-label="Otvori direktorijum"
              className="filmium-icon-button"
              disabled={isBusy}
              onClick={onOpenFolder}
              title="Otvori direktorijum sa preuzetim sadržajem"
              type="button"
            >
              <FolderOpen size={16} />
            </button>
          )}

          {playState === "pause" && onPause !== undefined && (
            <button
              aria-label={PLAY_LABELS.pause}
              className="filmium-icon-button"
              disabled={isBusy}
              onClick={onPause}
              title={PLAY_LABELS.pause}
              type="button"
            >
              <Pause size={16} />
            </button>
          )}

          {(playState === "start" || playState === "resume")
            && onPlay !== undefined && (
            <button
              aria-label={PLAY_LABELS[playState]}
              className="filmium-icon-button"
              disabled={
                isBusy || (playState === "start" && selected.size === 0)
              }
              onClick={() => onPlay([...selected])}
              title={PLAY_LABELS[playState]}
              type="button"
            >
              <Play size={16} />
            </button>
          )}

          {onRemove !== undefined && (
            <button
              aria-label="Ukloni iz liste"
              className="filmium-icon-button danger"
              disabled={isBusy}
              onClick={onRemove}
              title="Ukloni iz liste"
              type="button"
            >
              <X size={16} />
            </button>
          )}
        </div>
      </div>

      {percent !== null && (
        <div
          aria-label={`Napredak: ${percent}%`}
          aria-valuemax={100}
          aria-valuemin={0}
          aria-valuenow={percent}
          className="filmium-torrent-bar"
          role="progressbar"
        >
          <span style={{ width: `${percent}%` }} />
        </div>
      )}

      {model.errorMessage !== null && (
        <p className="filmium-torrent-error">{model.errorMessage}</p>
      )}

      {isOpen && (
        <div className="filmium-torrent-card-body">
          {model.archivedPath !== null && (
            <p className="filmium-torrent-path">
              {`Kopija .torrent fajla u CORE-u: ${model.archivedPath}`}
            </p>
          )}

          {model.files.length === 0 ? (
            <p className="filmium-torrent-empty">
              Spisak fajlova još nije poznat.
            </p>
          ) : (
            <>
              {model.selectable && (
                <p className="filmium-torrent-picker-summary">
                  {`Izabrano: ${selected.size} od ${model.files.length}`}
                  {` · ${formatBytes(selectedBytes)}`}
                </p>
              )}

              <ul className="filmium-torrent-picker-list">
                {model.files.map((file) => (
                  <li className="filmium-torrent-picker-row" key={file.key}>
                    <label className="filmium-torrent-picker-label">
                      <input
                        checked={selected.has(file.key)}
                        disabled={!model.selectable}
                        onChange={() => toggle(file.key)}
                        type="checkbox"
                      />

                      <span className="filmium-torrent-picker-path">
                        {file.path}
                      </span>

                      <span className="filmium-torrent-picker-size">
                        {formatBytes(file.sizeBytes)}
                      </span>
                    </label>

                    {file.percent !== null && (
                      <div
                        aria-label={`Napredak fajla: ${file.percent}%`}
                        aria-valuemax={100}
                        aria-valuemin={0}
                        aria-valuenow={file.percent}
                        className="filmium-torrent-file-bar"
                        role="progressbar"
                      >
                        <span style={{ width: `${file.percent}%` }} />
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            </>
          )}

          {primaryLabel !== undefined && onPrimary !== undefined && (
            <div className="filmium-torrent-picker-foot">
              <button
                className="filmium-button primary"
                disabled={isBusy || (model.selectable && selected.size === 0)}
                onClick={() => onPrimary([...selected])}
                type="button"
              >
                {primaryLabel}
              </button>
            </div>
          )}
        </div>
      )}
    </li>
  );
}

export default FilmiumTorrentCard;
