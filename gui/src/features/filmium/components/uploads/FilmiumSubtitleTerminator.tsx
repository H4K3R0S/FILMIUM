import {
  AlertTriangle,
  ArrowLeft,
  Ban,
  CheckCircle2,
  FileText,
  Info,
  Languages,
  LoaderCircle,
  Pencil,
  RefreshCw,
  Save,
  Trash2,
  Wand2,
  X,
} from "lucide-react";
import {
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import type { SubtitleRepairQueueItem } from "../../../../types/filmiumSubtitles";
import { transliterateSubtitle } from "../../../../services/filmiumSubtitlesApi";
import type { useFilmiumSubtitleRepairs } from "../../hooks/useFilmiumSubtitleRepairs";
import { findActiveCueLineRange } from "../../utils/subtitleCues";
import "../../styles/filmium-subtitles.css";


type RepairController = ReturnType<typeof useFilmiumSubtitleRepairs>;


// ==========          PROBLEM PO KODIRANJU (boja + kod)          ==========

function problemKey(item: SubtitleRepairQueueItem): string {
  return (item.detected_encoding || "?").toLowerCase();
}

function problemColor(key: string): string {
  if (key.includes("utf")) return "#22c55e";
  if (key.includes("1250")) return "#f59e0b";
  if (key.includes("1251")) return "#38bdf8";
  if (key.includes("1252")) return "#fb923c";
  if (key.includes("8859")) return "#a855f7";
  return "#ef4444";
}

// Fiksne vrste problema (kodiranja) — za legendu kvadratića iznad liste.
// „other" = sve što ne prepoznajemo (crveno). UTF-8 = ispravno (zeleno).
const PROBLEM_TYPES: { id: string; label: string }[] = [
  { id: "1250", label: "Windows-1250 — srednjoevropski (šđčćž)" },
  { id: "1251", label: "Windows-1251 — ćirilica" },
  { id: "1252", label: "Windows-1252 — zapadni" },
  { id: "8859", label: "ISO-8859 — latinica" },
  { id: "other", label: "Nepoznato / oštećeno kodiranje" },
  { id: "utf", label: "UTF-8 — ispravno kodiranje" },
];

function matchesType(key: string, id: string): boolean {
  if (id === "other") {
    return !["utf", "1250", "1251", "1252", "8859"].some((t) =>
      key.includes(t),
    );
  }
  return key.includes(id);
}


// Redovi koji su najverovatnije potpisi prevodioca / URL-ovi
// (žuto — za brisanje).
const CREDIT_URL = new RegExp(
  "(https?://|www\\.|\\.(com|net|org|rs)\\b|opensubtitles|titlovi" +
    "|preveo|prevela|preveli|prevod\\s*:|sinhronizov|sync\\b|obrada\\s*:" +
    "|[\\w.+-]+@[\\w.-]+\\.[a-z]{2,})",
  "i",
);

function isCreditOrUrl(line: string): boolean {
  return CREDIT_URL.test(line);
}

/**
 * Segmentira red na deo pre izmene, izmenjeni deo i deo posle (poredeći
 * sa drugom verzijom istog reda) — zajednički prefiks i sufiks.
 */
function charSegments(
  text: string,
  other: string,
): { prefix: string; middle: string; suffix: string } {
  let start = 0;
  const max = Math.min(text.length, other.length);
  while (start < max && text[start] === other[start]) {
    start += 1;
  }
  let endText = text.length;
  let endOther = other.length;
  while (
    endText > start &&
    endOther > start &&
    text[endText - 1] === other[endOther - 1]
  ) {
    endText -= 1;
    endOther -= 1;
  }
  return {
    prefix: text.slice(0, start),
    middle: text.slice(start, endText),
    suffix: text.slice(endText),
  };
}

const NBSP = " ";

type DiffRow = {
  type: "equal" | "changed" | "removed" | "added";
  a: string | null;
  b: string | null;
};

/**
 * LCS diff original↔popravljeno na nivou redova: uklonjeni redovi
 * (potpisi) i izmenjeni redovi (mojibake) se tačno prikažu, a paneli
 * ostaju poravnati.
 */
function buildDiffRows(original: string, repaired: string): DiffRow[] {
  // Deli neosetljivo na završetke linija: reparacija normalizuje CRLF→LF, pa bi
  // `split("\n")` poredio „1\r" vs „1" i lažno označio SVE redove izmenjenim
  // (repaired panel bi ostao prazan). `/\r?\n/` izjednačava CRLF i LF.
  const a = original.split(/\r?\n/);
  const b = repaired.split(/\r?\n/);
  const n = a.length;
  const m = b.length;

  const dp: number[][] = Array.from({ length: n + 1 }, () =>
    new Array<number>(m + 1).fill(0),
  );
  for (let i = n - 1; i >= 0; i -= 1) {
    for (let j = m - 1; j >= 0; j -= 1) {
      dp[i][j] =
        a[i] === b[j]
          ? dp[i + 1][j + 1] + 1
          : Math.max(dp[i + 1][j], dp[i][j + 1]);
    }
  }

  const raw: DiffRow[] = [];
  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    if (a[i] === b[j]) {
      raw.push({ type: "equal", a: a[i], b: b[j] });
      i += 1;
      j += 1;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      raw.push({ type: "removed", a: a[i], b: null });
      i += 1;
    } else {
      raw.push({ type: "added", a: null, b: b[j] });
      j += 1;
    }
  }
  while (i < n) {
    raw.push({ type: "removed", a: a[i], b: null });
    i += 1;
  }
  while (j < m) {
    raw.push({ type: "added", a: null, b: b[j] });
    j += 1;
  }

  const rows: DiffRow[] = [];
  let k = 0;
  while (k < raw.length) {
    if (raw[k].type === "removed") {
      const removed: DiffRow[] = [];
      while (k < raw.length && raw[k].type === "removed") {
        removed.push(raw[k]);
        k += 1;
      }
      const added: DiffRow[] = [];
      while (k < raw.length && raw[k].type === "added") {
        added.push(raw[k]);
        k += 1;
      }
      const pairs = Math.min(removed.length, added.length);
      for (let p = 0; p < pairs; p += 1) {
        rows.push({ type: "changed", a: removed[p].a, b: added[p].b });
      }
      for (let p = pairs; p < removed.length; p += 1) {
        rows.push(removed[p]);
      }
      for (let p = pairs; p < added.length; p += 1) {
        rows.push(added[p]);
      }
    } else {
      rows.push(raw[k]);
      k += 1;
    }
  }

  return rows;
}

/**
 * Jedan red u jednom panelu (levi = original, desni = popravljeno).
 */
function DiffRowLine({
  row,
  side,
}: {
  row: DiffRow;
  side: "orig" | "repaired";
}) {
  const text = side === "orig" ? row.a : row.b;
  const other = side === "orig" ? row.b : row.a;

  if (text === null) {
    return <div className="filmium-terminator-line placeholder">{NBSP}</div>;
  }

  if (row.type === "removed") {
    const credit = isCreditOrUrl(text);
    return (
      <div
        className={`filmium-terminator-line removed${credit ? " credit" : ""}`}
      >
        <mark className={credit ? "cred" : "deleted"}>{text || NBSP}</mark>
      </div>
    );
  }

  if (row.type === "added") {
    return (
      <div className="filmium-terminator-line added">{text || NBSP}</div>
    );
  }

  if (row.type === "changed" && other !== null) {
    const { prefix, middle, suffix } = charSegments(text, other);
    return (
      <div className="filmium-terminator-line">
        {prefix}
        {middle ? <mark className="mojibake">{middle}</mark> : null}
        {suffix}
      </div>
    );
  }

  return <div className="filmium-terminator-line">{text || NBSP}</div>;
}


/**
 * „TERMINATOR PREVODA" — puno radno okruženje za pregled i popravku svih
 * pronađenih prevoda. Levo lista fajlova + vrsta problema, desno dva
 * prozora: originalni prevod i izmenjena (popravljena) verzija.
 */
export type TerminatorAdHocFile = {
  path: string;
  label: string;
};

export default function FilmiumSubtitleTerminator({
  controller,
  onBack,
  adHocFiles,
  currentTimeMs = 0,
}: {
  controller: RepairController;
  onBack: () => void;
  /** Kad je zadato, Terminator radi ad-hoc nad ovim fajlovima (Editor sa
   * filmske strane), sa prekidačem jezika umesto reda popravke. */
  adHocFiles?: TerminatorAdHocFile[];
  /** Trenutak plejera (ms) — u Editor modu skače na tu liniju prevoda. */
  currentTimeMs?: number;
}) {
  const {
    activeItems,
    busyItemId,
    confirmRepair,
    errorMessage,
    inspection,
    isSavingEdit,
    openFile,
    previewItem,
    saveManualEdit,
    selectedItemId,
    setItemStatus,
  } = controller;

  const [closing, setClosing] = useState(false);
  // Sa filmske strane (ad-hoc) otvara se odmah „Editor"; iz reda popravke
  // podrazumevano „Terminator".
  const [mode, setMode] = useState<"terminator" | "editor">(
    adHocFiles ? "editor" : "terminator",
  );
  const editRef = useRef<HTMLTextAreaElement>(null);

  // Poslednji poznati trenutak plejera (bez okidanja jump-a na svaki update).
  const timeRef = useRef(currentTimeMs);
  useEffect(() => {
    timeRef.current = currentTimeMs;
  });

  // Strelice ↑/↓ — prethodni/sledeći prevod (preview). Preskoči kad je fokus u
  // polju za unos (Editor textarea) da strelice tamo pomeraju kursor.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key !== "ArrowDown" && event.key !== "ArrowUp") {
        return;
      }
      const target = event.target as HTMLElement | null;
      if (
        target &&
        (target.tagName === "TEXTAREA" ||
          target.tagName === "INPUT" ||
          target.isContentEditable)
      ) {
        return;
      }
      const dir = event.key === "ArrowDown" ? 1 : -1;

      if (adHocFiles) {
        if (adHocFiles.length === 0) {
          return;
        }
        const cur = adHocFiles.findIndex(
          (file) => file.path === inspection?.file_path,
        );
        const next =
          cur < 0
            ? dir > 0
              ? 0
              : adHocFiles.length - 1
            : Math.min(adHocFiles.length - 1, Math.max(0, cur + dir));
        if (next !== cur) {
          event.preventDefault();
          void openFile(adHocFiles[next].path);
        }
        return;
      }

      if (activeItems.length === 0) {
        return;
      }
      const cur = activeItems.findIndex((item) => item.id === selectedItemId);
      const next =
        cur < 0
          ? dir > 0
            ? 0
            : activeItems.length - 1
          : Math.min(activeItems.length - 1, Math.max(0, cur + dir));
      if (next !== cur) {
        event.preventDefault();
        void previewItem(activeItems[next].id);
      }
    }

    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [
    adHocFiles,
    activeItems,
    inspection?.file_path,
    selectedItemId,
    openFile,
    previewItem,
  ]);

  // Kada se otvori Editor (ili učita fajl), skoči na liniju prevoda iz
  // trenutnog vremena plejera i označi je (selekcija + scroll).
  useEffect(() => {
    if (mode !== "editor" || !inspection || timeRef.current <= 0) {
      return;
    }
    const area = editRef.current;
    if (!area) {
      return;
    }
    const text = inspection.preview.original_text;
    const range = findActiveCueLineRange(text, timeRef.current);
    if (!range) {
      return;
    }
    const frame = requestAnimationFrame(() => {
      area.focus();
      area.setSelectionRange(range.start, range.end);
      const lineNo = text.slice(0, range.start).split("\n").length - 1;
      const lineHeight =
        parseFloat(window.getComputedStyle(area).lineHeight) || 18;
      area.scrollTop = Math.max(
        0,
        lineNo * lineHeight - area.clientHeight / 2,
      );
    });
    return () => cancelAnimationFrame(frame);
  }, [mode, inspection]);

  // „Poveži sve" — povezuje sve fajlove sa istim problemom (kodiranjem).
  const [connectedKey, setConnectedKey] = useState<string | null>(null);
  // Batch prekodiranje: napredak (koliko od koliko gotovo) — za naslov + traku.
  const [batch, setBatch] = useState<{ done: number; total: number } | null>(null);
  // Transliteracija (latinica↔ćirilica): status pravljenja drugog pisma.
  const [translitBusy, setTranslitBusy] = useState(false);
  const [translitMsg, setTranslitMsg] = useState<string | null>(null);
  const filesRef = useRef<HTMLDivElement>(null);
  const [cable, setCable] = useState<{
    ys: number[];
    width: number;
    height: number;
  } | null>(null);

  // Uvek drži izabrani fajl u vidokrugu (npr. pri navigaciji strelicama).
  useEffect(() => {
    filesRef.current
      ?.querySelector(".filmium-terminator-file.active")
      ?.scrollIntoView({ block: "nearest" });
  }, [selectedItemId, inspection?.file_path]);

  const originalRef = useRef<HTMLDivElement>(null);
  const repairedRef = useRef<HTMLDivElement>(null);
  const syncing = useRef(false);

  // Meri pozicije povezanih kartica i crta „kabl".
  useLayoutEffect(() => {
    const container = filesRef.current;
    if (!connectedKey || !container) {
      setCable(null);
      return;
    }
    const nodes = container.querySelectorAll<HTMLElement>(
      '[data-connected="true"]',
    );
    const ys = Array.from(nodes).map(
      (node) => node.offsetTop + node.offsetHeight / 2,
    );
    setCable({
      ys,
      width: container.clientWidth,
      height: container.scrollHeight,
    });
  }, [connectedKey, activeItems, selectedItemId]);

  function syncScroll(
    source: HTMLDivElement | null,
    target: HTMLDivElement | null,
  ): void {
    if (!source || !target || syncing.current) {
      return;
    }
    // Sinhrono resetovanje (bez requestAnimationFrame): pri brzom skrolovanju
    // rAF je propuštao događaje pa su se paneli razilazili. Eho-scroll na
    // target-u upisuje istu vrednost i ne okida novi event, pa nema petlje.
    syncing.current = true;
    target.scrollTop = source.scrollTop;
    target.scrollLeft = source.scrollLeft;
    syncing.current = false;
  }

  const rows = useMemo(
    () =>
      inspection
        ? buildDiffRows(
            inspection.preview.original_text,
            inspection.preview.repaired_text,
          )
        : [],
    [inspection],
  );

  // Virtuelizacija preview-a: renderuj samo redove koji staju u okvir (+~15%),
  // ostatak se dodaje lagano kako se skroluje. Ubrzava otvaranje dugih prevoda
  // (nema render svih ~1200 redova odjednom). Okidač: IntersectionObserver nad
  // „sentinel"-om na dnu (pouzdanije od merenja scrollHeight/clientHeight).
  const LINES_STEP = 60;
  const [renderCount, setRenderCount] = useState(LINES_STEP);
  const sentinelRef = useRef<HTMLDivElement>(null);

  // Nov prevod → počni malo + skrol na vrh oba panela.
  useEffect(() => {
    setRenderCount(LINES_STEP);
    if (originalRef.current) originalRef.current.scrollTop = 0;
    if (repairedRef.current) repairedRef.current.scrollTop = 0;
  }, [inspection?.file_path, selectedItemId]);

  // Kada je „sentinel" (dno renderovanog dela) blizu vidljivog okvira (rootMargin
  // 15% → malo pre nego što se vidi), dodaj sledeći komad. Sam popuni okvir (dok
  // je sentinel vidljiv jer je sadržaj kraći) i otkriva ostatak pri skrolu.
  const rowsLen = rows.length;
  useEffect(() => {
    const root = originalRef.current;
    const sentinel = sentinelRef.current;
    if (!root || !sentinel) return;
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setRenderCount((count) =>
            count < rowsLen ? Math.min(rowsLen, count + LINES_STEP) : count,
          );
        }
      },
      // ~350px unapred (malo više od vidljivog okvira) — px je pouzdanije od %.
      { root, rootMargin: "0px 0px 350px 0px", threshold: 0 },
    );
    io.observe(sentinel);
    return () => io.disconnect();
  }, [rowsLen, renderCount]);

  const visibleRows = rows.slice(0, renderCount);

  // Pismo trenutnog prevoda (ima li ćirilice) → dugme nudi DRUGO pismo.
  const isCyrillic = inspection
    ? /[Ѐ-ӿ]/.test(inspection.preview.original_text)
    : false;

  async function handleTransliterate(): Promise<void> {
    if (!inspection) return;
    setTranslitBusy(true);
    setTranslitMsg(null);
    try {
      const result = await transliterateSubtitle(inspection.file_path);
      setTranslitMsg(`Napravljeno: ${result.created_name}`);
    } catch (error) {
      setTranslitMsg(
        "Greška: " + (error instanceof Error ? error.message : "nepoznata"),
      );
    } finally {
      setTranslitBusy(false);
    }
  }

  function handleBack(): void {
    setClosing(true);
  }

  // „Terminator" mod: red popravke → potvrdi popravku; ad-hoc fajl → upiši
  // auto-očišćeni tekst (preview.repaired_text) ručnim snimanjem.
  async function handleTerminatorSave(): Promise<void> {
    if (selectedItemId !== null) {
      await confirmRepair(selectedItemId);
    } else if (inspection) {
      await saveManualEdit(inspection.preview.repaired_text);
    }
  }

  // „Editor" mod: upiši ono što je korisnik ručno izmenio u polju.
  async function handleEditorSave(): Promise<void> {
    await saveManualEdit(editRef.current?.value ?? "");
  }

  const selectedItem =
    activeItems.find((item) => item.id === selectedItemId) ?? null;
  const selectedKey = selectedItem ? problemKey(selectedItem) : null;

  // Legenda problema: za svaku vrstu koliko fajlova + reprezentativni ključ
  // (za „poveži sve tog problema" na klik kvadratića).
  const problemTypes = PROBLEM_TYPES.map((type) => {
    const matching = activeItems.filter((item) =>
      matchesType(problemKey(item), type.id),
    );
    return {
      ...type,
      count: matching.length,
      repKey: matching[0] ? problemKey(matching[0]) : null,
    };
  });

  // Koliko je fajlova trenutno povezano (isti problem kao connectedKey).
  const connectedCount = connectedKey
    ? activeItems.filter((item) => problemKey(item) === connectedKey).length
    : 0;

  // „Prekodiraj": prekodira izabrani fajl (ili sve povezane sa istim
  // problemom) u UTF-8, na originalnoj lokaciji.
  async function handlePrekodiraj(): Promise<void> {
    if (connectedKey) {
      const targets = activeItems.filter(
        (item) => problemKey(item) === connectedKey,
      );
      setBatch({ done: 0, total: targets.length });
      try {
        for (const target of targets) {
          await confirmRepair(target.id);
          setBatch((current) =>
            current ? { ...current, done: current.done + 1 } : current,
          );
        }
      } finally {
        setBatch(null);
        setConnectedKey(null);
      }
      return;
    }
    if (selectedItemId !== null) {
      await confirmRepair(selectedItemId);
    }
  }

  const changeCount = rows.filter((row) => row.type !== "equal").length;
  const encoding =
    selectedItem?.detected_encoding ??
    inspection?.detected_encoding ??
    "?";
  const issueTypes = inspection?.issues.map((issue) => issue.issue_type) ?? [];
  const hasMojibake = issueTypes.some(
    (type) => type === "mojibake" || type === "replacement_character",
  );
  const isUtf = encoding.toLowerCase().includes("utf");
  const hasBinary = issueTypes.includes("binary_or_suspicious");
  const hasEncodingIssue =
    issueTypes.includes("invalid_encoding") && !isUtf;
  const problemLabel = hasBinary
    ? "Binaran / sumnjiv fajl"
    : hasEncodingIssue
      ? "Kodiranje"
      : hasMojibake
        ? "Loša slova (mojibake)"
        : issueTypes.includes("invalid_srt_structure")
          ? "SRT struktura"
          : "Za proveru";

  return (
    <div
      className={`filmium-terminator${closing ? " closing" : ""}`}
      onAnimationEnd={(event) => {
        if (closing && event.target === event.currentTarget) {
          onBack();
        }
      }}
    >
      {/* ==========          HEADER          ========== */}
      <header className="filmium-terminator-head">
        <button
          className="filmium-terminator-back"
          onClick={handleBack}
          type="button"
        >
          <ArrowLeft size={18} />
          Nazad
        </button>
        <div className="filmium-terminator-title">
          <AlertTriangle size={20} />
          <strong>TERMINATOR PREVODA</strong>
          {batch ? (
            <span>
              Prekodiram {batch.done}/{batch.total} gotovo
            </span>
          ) : (
            !adHocFiles && (
              <span>{activeItems.length} fajlova za popravku</span>
            )
          )}
        </div>

        {/* Modovi: automatsko čišćenje vs ručni editor. */}
        <div className="filmium-terminator-modes" role="group">
          <button
            className={mode === "terminator" ? "active" : ""}
            onClick={() => setMode("terminator")}
            type="button"
          >
            <Wand2 size={14} /> Terminator
          </button>
          <button
            className={mode === "editor" ? "active" : ""}
            onClick={() => setMode("editor")}
            type="button"
          >
            <Pencil size={14} /> Editor
          </button>
        </div>
      </header>

      {/* Tanka traka napretka batch prekodiranja — odmah ispod naslova. */}
      {batch && (
        <div
          aria-valuemax={batch.total}
          aria-valuemin={0}
          aria-valuenow={batch.done}
          className="filmium-terminator-progress"
          role="progressbar"
        >
          <span
            style={{
              width: `${(batch.done / Math.max(1, batch.total)) * 100}%`,
            }}
          />
        </div>
      )}

      {errorMessage && (
        <div className="system-message error">{errorMessage}</div>
      )}

      {/* ==========          RADNO OKRUŽENJE          ========== */}
      <div className="filmium-terminator-body">
        {/* Leva strana: lista fajlova + vrsta problema */}
        <aside className="filmium-terminator-list">
          {adHocFiles ? (
            <>
              <p className="filmium-terminator-list-title">
                Prevodi filma ({adHocFiles.length})
              </p>
              <div className="filmium-terminator-files">
                {adHocFiles.map((file) => (
                  <button
                    className={`filmium-terminator-file${
                      inspection?.file_path === file.path ? " active" : ""
                    }`}
                    key={file.path}
                    onClick={() => void openFile(file.path)}
                    type="button"
                  >
                    <span className="filmium-terminator-file-icon">
                      <FileText size={16} />
                    </span>
                    <span className="filmium-terminator-file-copy">
                      <strong>{file.label}</strong>
                      <small>{file.path.split(/[\\/]/).pop()}</small>
                    </span>
                  </button>
                ))}
              </div>
            </>
          ) : (
          <>
          <p className="filmium-terminator-list-title">
            <span>Pronađeni fajlovi ({activeItems.length})</span>
            {connectedCount > 0 && (
              <span className="filmium-terminator-list-connected">
                {connectedCount} povezano
              </span>
            )}
          </p>
          {/* Legenda: [✕ Razveži] [kvadratići vrsta problema] [Prekodiraj].
              Kvadratić upaljen ako takav problem postoji; hover = naziv;
              klik = poveži sve prevode sa tim problemom. */}
          <div className="filmium-terminator-legend">
            <button
              aria-label="Razveži"
              className="filmium-terminator-legend-clear"
              disabled={!connectedKey || batch !== null}
              onClick={() => setConnectedKey(null)}
              title="Razveži"
              type="button"
            >
              <X size={14} />
            </button>
            <div className="filmium-terminator-legend-dots">
              {problemTypes.map((type) => {
                const present = type.count > 0;
                const active =
                  type.repKey !== null && connectedKey === type.repKey;
                return (
                  <button
                    aria-label={type.label}
                    className={`filmium-terminator-legend-dot${
                      present ? "" : " off"
                    }${active ? " active" : ""}`}
                    disabled={!present || batch !== null}
                    key={type.id}
                    onClick={() =>
                      type.repKey &&
                      setConnectedKey((current) =>
                        current === type.repKey ? null : type.repKey,
                      )
                    }
                    style={{ background: problemColor(type.id) }}
                    title={
                      present
                        ? `${type.label} — ${type.count} ${
                            type.count === 1 ? "fajl" : "fajlova"
                          } · klik: poveži sve`
                        : `${type.label} — nema`
                    }
                    type="button"
                  />
                );
              })}
            </div>
            <button
              className="filmium-terminator-legend-recode"
              disabled={
                busyItemId !== null ||
                batch !== null ||
                (!connectedKey && selectedItemId === null)
              }
              onClick={() => void handlePrekodiraj()}
              title="Prekodiraj"
              type="button"
            >
              {busyItemId !== null ? (
                <LoaderCircle className="spinning" size={14} />
              ) : (
                <RefreshCw size={14} />
              )}
              Prekodiraj
            </button>
          </div>
          <div className="filmium-terminator-files" ref={filesRef}>
            {activeItems.map((item) => {
              const key = problemKey(item);
              const connected = connectedKey === key;

              return (
                <button
                  className={`filmium-terminator-file${
                    selectedItemId === item.id ? " active" : ""
                  }${connected ? " connected" : ""}`}
                  data-connected={connected ? "true" : "false"}
                  disabled={busyItemId === item.id}
                  key={item.id}
                  onClick={() => void previewItem(item.id)}
                  type="button"
                >
                  <span
                    aria-hidden="true"
                    className="filmium-terminator-dot"
                    style={{ background: problemColor(key) }}
                    title={item.detected_encoding}
                  />
                  <span className="filmium-terminator-file-icon">
                    {busyItemId === item.id ? (
                      <LoaderCircle className="spinning" size={16} />
                    ) : (
                      <FileText size={16} />
                    )}
                  </span>
                  <span className="filmium-terminator-file-copy">
                    <strong>{item.file_name}</strong>
                    <small>
                      {item.detected_encoding} ·{" "}
                      {item.detected_language_code ?? "?"} ·{" "}
                      {item.issue_count}{" "}
                      {item.issue_count === 1 ? "problem" : "problema"}
                    </small>
                  </span>
                </button>
              );
            })}
            {activeItems.length === 0 && (
              <p className="filmium-terminator-empty">
                Nema više prevoda za popravku.
              </p>
            )}

            {cable && connectedKey && cable.ys.length > 1 && (
              <svg
                className="filmium-terminator-cable"
                height={cable.height}
                width={cable.width}
              >
                <line
                  stroke={problemColor(connectedKey)}
                  strokeWidth={2}
                  x1={cable.width - 3}
                  x2={cable.width - 3}
                  y1={Math.min(...cable.ys)}
                  y2={Math.max(...cable.ys)}
                />
                {cable.ys.map((y, index) => (
                  <g key={index}>
                    <line
                      stroke={problemColor(connectedKey)}
                      strokeWidth={2}
                      x1={cable.width - 14}
                      x2={cable.width - 3}
                      y1={y}
                      y2={y}
                    />
                    <circle
                      cx={cable.width - 3}
                      cy={y}
                      fill={problemColor(connectedKey)}
                      r={3.5}
                    />
                  </g>
                ))}
              </svg>
            )}
          </div>

          {/* Prozorčić: koja je vrsta problema */}
          <div className="filmium-terminator-problem">
            {selectedItem && selectedKey ? (
              <>
                <div className="filmium-terminator-problem-row main">
                  <span>VRSTA PROBLEMA</span>
                  <strong>{problemLabel}</strong>
                </div>
                <div className="filmium-terminator-problem-row">
                  <span>Fajl je</span>
                  <strong>
                    {hasEncodingIssue ? `ANSI/${encoding}` : encoding}
                  </strong>
                </div>
                {hasEncodingIssue && (
                  <div className="filmium-terminator-problem-row">
                    <span>Treba biti</span>
                    <strong>UTF-8</strong>
                  </div>
                )}
                <p className="filmium-terminator-problem-note">
                  <Info size={13} />
                  {hasEncodingIssue
                    ? "Tekst izgleda isto, ali se bajtovi menjaju u UTF-8."
                    : hasMojibake
                      ? "Slova šđžčć su pogrešno dekodirana i biće ispravljena."
                      : "Fajl je već UTF-8; nema izmene kodiranja."}
                </p>
              </>
            ) : (
              <p className="filmium-terminator-problem-note">
                <Info size={13} />
                Izaberi fajl da vidiš vrstu problema.
              </p>
            )}
          </div>
          </>
          )}
        </aside>

        {/* Desna strana: original vs izmenjena verzija */}
        <section className="filmium-terminator-workspace">
          {inspection ? (
            <>
              <div className="filmium-terminator-file-head">
                <div>
                  <p className="eyebrow">Prevod</p>
                  <h3>{inspection.file_name}</h3>
                </div>
                <div className="filmium-terminator-head-right">
                  <button
                    className="filmium-terminator-translit"
                    disabled={translitBusy}
                    onClick={() => void handleTransliterate()}
                    title={
                      isCyrillic
                        ? "Napravi latiničnu verziju (.sr-Latn)"
                        : "Napravi ćiriličnu verziju (.sr-Cyrl)"
                    }
                    type="button"
                  >
                    {translitBusy ? (
                      <LoaderCircle className="spinning" size={14} />
                    ) : (
                      <Languages size={14} />
                    )}
                    {isCyrillic ? "→ Latinica" : "→ Ćirilica"}
                  </button>
                  <span className="filmium-terminator-change-count">
                    <CheckCircle2 size={15} />
                    {changeCount > 0
                      ? `${changeCount} izmena`
                      : "Normalizacija kodiranja u UTF-8"}
                  </span>
                </div>
              </div>
              {translitMsg && (
                <p className="filmium-terminator-translit-msg">{translitMsg}</p>
              )}

              {/* Sačuvaj — centrirano iznad prozora sa tekstom */}
              <div className="filmium-terminator-save">
                <button
                  className="primary-button"
                  disabled={
                    mode === "editor"
                      ? isSavingEdit
                      : selectedItemId !== null
                        ? busyItemId === selectedItemId
                        : isSavingEdit
                  }
                  onClick={() =>
                    mode === "editor"
                      ? void handleEditorSave()
                      : void handleTerminatorSave()}
                  type="button"
                >
                  {(mode === "editor" && isSavingEdit) ||
                  (mode === "terminator" &&
                    (selectedItemId !== null
                      ? busyItemId === selectedItemId
                      : isSavingEdit)) ? (
                    <LoaderCircle className="spinning" size={17} />
                  ) : (
                    <Save size={17} />
                  )}
                  {mode === "editor" ? "Sačuvaj izmene" : "Sačuvaj"}
                </button>
              </div>

              {mode === "editor" ? (
                <div className="filmium-terminator-editor">
                  <header>Ručno menjanje sadržaja fajla</header>
                  <textarea
                    className="filmium-terminator-editarea"
                    defaultValue={inspection.preview.original_text}
                    key={inspection.file_path}
                    ref={editRef}
                    spellCheck={false}
                  />
                </div>
              ) : (
                <div className="filmium-terminator-diff">
                  <div className="filmium-terminator-pane">
                    <header>Originalni prevod</header>
                    <div
                      className="filmium-terminator-lines"
                      onScroll={() =>
                        syncScroll(originalRef.current, repairedRef.current)}
                      ref={originalRef}
                    >
                      {visibleRows.map((row, index) => (
                        <DiffRowLine key={index} row={row} side="orig" />
                      ))}
                      <div
                        aria-hidden="true"
                        className="filmium-terminator-sentinel"
                        ref={sentinelRef}
                      />
                    </div>
                  </div>
                  <div className="filmium-terminator-pane repaired">
                    <header>Izmenjena verzija</header>
                    <div
                      className="filmium-terminator-lines"
                      onScroll={() =>
                        syncScroll(repairedRef.current, originalRef.current)}
                      ref={repairedRef}
                    >
                      {visibleRows.map((row, index) => (
                        <DiffRowLine key={index} row={row} side="repaired" />
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {mode === "terminator" && selectedItemId !== null && (
                <div className="filmium-terminator-actions">
                  <button
                    className="filmium-subtitle-text-button"
                    disabled={busyItemId === selectedItemId}
                    onClick={() =>
                      void setItemStatus(selectedItemId, "dismissed")}
                    type="button"
                  >
                    <Trash2 size={15} />
                    Ukloni iz reda
                  </button>
                  <button
                    className="filmium-subtitle-text-button"
                    disabled={busyItemId === selectedItemId}
                    onClick={() =>
                      void setItemStatus(selectedItemId, "ignored")}
                    type="button"
                  >
                    <Ban size={15} />
                    Više ne prijavljuj
                  </button>
                </div>
              )}
            </>
          ) : (
            <div className="filmium-terminator-placeholder">
              <FileText size={40} />
              <p>
                {adHocFiles
                  ? "Izaberi prevod filma sa leve strane."
                  : "Izaberi fajl sa leve strane da vidiš popravku."}
              </p>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
