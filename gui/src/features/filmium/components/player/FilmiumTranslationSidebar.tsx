import { Languages, LocateFixed, Search, X } from "lucide-react";
import {
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  activeCueIndex,
  formatCueTime,
  parseSubtitleCues,
  searchCues,
  type SubtitleCue,
} from "../../utils/subtitleCues";
import "../../styles/filmium-subtitles.css";


// Broj cue-ova iznad/ispod centra koji se prikazuju.
const WINDOW_RADIUS = 5;


type FilmiumTranslationSidebarProps = {
  open: boolean;
  subtitleSrc: string | null;
  currentTimeMs: number;
  onSeek?: (ms: number) => void;
  onClose: () => void;
};


/**
 * „PREVODNI SIDEBAR" — panel koji izleti sa desne strane plejera i prikazuje
 * prevod kao text editor: trenutni cue u centru (uvećan), susedni iznad/ispod
 * (manji i zatamnjeni). Skrol točkićem pomera niz; gore je pretraga po reči
 * ili vremenu; desno stilizovan indikator pozicije.
 */
export default function FilmiumTranslationSidebar({
  open,
  subtitleSrc,
  currentTimeMs,
  onSeek,
  onClose,
}: FilmiumTranslationSidebarProps) {
  const [cues, setCues] = useState<SubtitleCue[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  // Ručno pregledanje (skrol/klik) privremeno „otkači" panel od videa; klik na
  // „Prati" (ili seek klikom na cue) vraća praćenje. Centar se izvodi tokom
  // rendera — kad se prati, centar je aktivni cue; u ručnom režimu je izabrani.
  const [manual, setManual] = useState(false);
  const [manualCenter, setManualCenter] = useState(0);
  const [query, setQuery] = useState("");
  const [closing, setClosing] = useState(false);

  const activeIndex = useMemo(
    () => activeCueIndex(cues, currentTimeMs),
    [cues, currentTimeMs],
  );

  // Učitava i parsira prevod kad se izvor promeni.
  useEffect(() => {
    let active = true;
    setLoadError(null);
    if (!subtitleSrc) {
      setCues((prev) => (prev.length ? [] : prev));
      return;
    }
    void fetch(subtitleSrc)
      .then((response) => {
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        return response.text();
      })
      .then((text) => {
        if (active) {
          setCues(parseSubtitleCues(text));
        }
      })
      .catch(() => {
        if (active) {
          setCues([]);
          setLoadError("Prevod nije moguće učitati.");
        }
      });
    return () => {
      active = false;
    };
  }, [subtitleSrc]);

  const viewportRef = useRef<HTMLDivElement | null>(null);

  function clampIndex(value: number): number {
    if (cues.length === 0) {
      return 0;
    }
    return Math.min(cues.length - 1, Math.max(0, value));
  }

  const centerIndex = manual
    ? clampIndex(manualCenter)
    : activeIndex >= 0
      ? activeIndex
      : 0;

  // Ogledala za native wheel handler (bez zastarelog state-a u listeneru).
  const centerRef = useRef(centerIndex);
  const cuesLenRef = useRef(cues.length);
  useEffect(() => {
    centerRef.current = centerIndex;
    cuesLenRef.current = cues.length;
  });

  // Native wheel listener (non-passive): React onWheel je passive, pa
  // preventDefault ne radi — stranica se paralelno skroluje i osećaj je trzav.
  useEffect(() => {
    const node = viewportRef.current;
    if (!node) {
      return;
    }
    function onWheel(event: globalThis.WheelEvent): void {
      const total = cuesLenRef.current;
      if (total === 0) {
        return;
      }
      event.preventDefault();
      const steps = Math.max(1, Math.round(Math.abs(event.deltaY) / 60));
      const dir = event.deltaY > 0 ? 1 : -1;
      const next = Math.min(
        total - 1,
        Math.max(0, centerRef.current + dir * steps),
      );
      setManualCenter(next);
      setManual(true);
    }
    node.addEventListener("wheel", onWheel, { passive: false });
    return () => node.removeEventListener("wheel", onWheel);
  }, [open]);

  function goToCue(index: number, seek: boolean): void {
    const target = clampIndex(index);
    if (seek && onSeek && cues[target]) {
      onSeek(cues[target].startMs);
      setManual(false);
    } else {
      setManualCenter(target);
      setManual(true);
    }
  }

  function resumeFollow(): void {
    setManual(false);
  }

  function handleClose(): void {
    setClosing(true);
  }

  const results = useMemo(
    () => searchCues(cues, query),
    [cues, query],
  );

  const visible = useMemo(() => {
    const rows: SubtitleCue[] = [];
    for (
      let i = centerIndex - WINDOW_RADIUS;
      i <= centerIndex + WINDOW_RADIUS;
      i += 1
    ) {
      if (i >= 0 && i < cues.length) {
        rows.push(cues[i]);
      }
    }
    return rows;
  }, [cues, centerIndex]);

  if (!open) {
    return null;
  }

  const thumbTop =
    cues.length > 1 ? (centerIndex / (cues.length - 1)) * 100 : 0;

  return (
    <aside
      className={`filmium-translation-sidebar${closing ? " closing" : ""}`}
      onAnimationEnd={(event) => {
        if (closing && event.target === event.currentTarget) {
          setClosing(false);
          onClose();
        }
      }}
    >
      <header className="filmium-translation-head">
        <div className="filmium-translation-title">
          <Languages size={17} />
          <strong>PREVOD</strong>
          {cues.length > 0 && <span>{cues.length}</span>}
        </div>
        <button
          className="filmium-translation-close"
          onClick={handleClose}
          title="Zatvori"
          type="button"
        >
          <X size={16} />
        </button>
      </header>

      <div className="filmium-translation-search">
        <Search size={14} />
        <input
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Traži reč ili vreme (01:12:32)…"
          type="text"
          value={query}
        />
        {manual && (
          <button
            className="filmium-translation-live"
            onClick={resumeFollow}
            title="Prati video"
            type="button"
          >
            <LocateFixed size={13} /> Prati
          </button>
        )}
      </div>

      {query && (
        <div className="filmium-translation-results">
          {results.length === 0 ? (
            <p className="filmium-translation-empty">Nema pogodaka.</p>
          ) : (
            results.slice(0, 40).map((index) => (
              <button
                className="filmium-translation-result"
                key={index}
                onClick={() => goToCue(index, true)}
                type="button"
              >
                <time>{formatCueTime(cues[index].startMs)}</time>
                <span>{cues[index].text}</span>
              </button>
            ))
          )}
        </div>
      )}

      <div className="filmium-translation-viewport" ref={viewportRef}>
        {loadError && (
          <p className="filmium-translation-empty">{loadError}</p>
        )}
        {!loadError && cues.length === 0 && (
          <p className="filmium-translation-empty">
            Nema učitanog prevoda.
          </p>
        )}
        <div className="filmium-translation-stack">
          {visible.map((cue) => {
            const distance = Math.abs(cue.index - centerIndex);
            const isCenter = cue.index === centerIndex;
            const isActive = cue.index === activeIndex;
            return (
              <button
                className={
                  "filmium-translation-cue" +
                  (isCenter ? " center" : "") +
                  (isActive ? " active" : "")
                }
                data-dist={Math.min(distance, WINDOW_RADIUS)}
                key={cue.index}
                onClick={() => goToCue(cue.index, true)}
                type="button"
              >
                <time>
                  {formatCueTime(cue.startMs)} - {formatCueTime(cue.endMs)}
                </time>
                <p>{cue.text}</p>
              </button>
            );
          })}
        </div>

        {/* Stilizovan indikator pozicije umesto klasičnog scrollbara. */}
        {cues.length > 1 && (
          <div
            className="filmium-translation-rail"
            onClick={(event) => {
              const rect = event.currentTarget.getBoundingClientRect();
              const ratio = (event.clientY - rect.top) / rect.height;
              goToCue(Math.round(ratio * (cues.length - 1)), false);
            }}
          >
            <span
              className="filmium-translation-thumb"
              style={{ top: `${thumbTop}%` }}
            />
          </div>
        )}
      </div>
    </aside>
  );
}
