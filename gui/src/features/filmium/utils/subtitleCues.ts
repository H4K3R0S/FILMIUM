// Parsiranje prevoda (WebVTT / SRT) u listu cue-ova za Prevodni Sidebar.

export type SubtitleCue = {
  index: number;
  startMs: number;
  endMs: number;
  text: string;
};

const TIME_RE =
  /(\d{1,2}):(\d{2}):(\d{2})[.,](\d{1,3})|(\d{1,2}):(\d{2})[.,](\d{1,3})/;

/** `HH:MM:SS[.,]mmm` ili `MM:SS[.,]mmm` u milisekunde. */
function parseTimestamp(token: string): number | null {
  const match = TIME_RE.exec(token.trim());
  if (!match) {
    return null;
  }
  if (match[1] !== undefined) {
    const [, hh, mm, ss, ms] = match;
    return (
      Number(hh) * 3_600_000 +
      Number(mm) * 60_000 +
      Number(ss) * 1000 +
      Number(ms.padEnd(3, "0"))
    );
  }
  const mm = match[5];
  const ss = match[6];
  const ms = match[7];
  return (
    Number(mm) * 60_000 + Number(ss) * 1000 + Number(ms.padEnd(3, "0"))
  );
}

const CUE_TIMING_RE = /-->/;
const TAG_RE = /<[^>]+>/g;

/**
 * Parsira WebVTT ili SRT tekst u cue-ove. Tolerantan je na oba formata
 * (VTT koristi `.` a SRT `,` za milisekunde) i na indeksne redove.
 */
export function parseSubtitleCues(raw: string): SubtitleCue[] {
  const normalized = raw.replace(/\r\n?/g, "\n").replace(/^\uFEFF/, "");
  const blocks = normalized.split(/\n[ \t]*\n/);
  const cues: SubtitleCue[] = [];

  for (const block of blocks) {
    const lines = block.split("\n");
    const timingLineIndex = lines.findIndex((line) =>
      CUE_TIMING_RE.test(line),
    );
    if (timingLineIndex === -1) {
      continue;
    }

    const [startToken, endToken] = lines[timingLineIndex].split("-->");
    const startMs = parseTimestamp(startToken ?? "");
    const endMs = parseTimestamp(endToken ?? "");
    if (startMs === null || endMs === null) {
      continue;
    }

    const text = lines
      .slice(timingLineIndex + 1)
      .join("\n")
      .replace(TAG_RE, "")
      .trim();
    if (!text) {
      continue;
    }

    cues.push({
      index: cues.length,
      startMs,
      endMs,
      text,
    });
  }

  return cues;
}

/**
 * Nalazi znakovni opseg [start, end) reda dijaloga cue-a aktivnog u datom
 * trenutku, U TAČNOM izvornom tekstu (bez normalizacije novih redova) — da bi
 * ofseti odgovarali `textarea.value`. Vraća null ako nema takvog cue-a.
 */
export function findActiveCueLineRange(
  text: string,
  timeMs: number,
): { start: number; end: number } | null {
  const lines = text.split("\n");
  let offset = 0;
  let bestStart = -1;
  let bestEnd = -1;
  let bestTime = -1;

  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
    const lineEnd = offset + line.length;

    if (CUE_TIMING_RE.test(line)) {
      const start = parseTimestamp(line.split("-->")[0] ?? "");
      if (start !== null && start <= timeMs && start > bestTime) {
        // Prvi neprazan red posle vremenske linije je dijalog.
        let dOffset = lineEnd + 1;
        let j = i + 1;
        while (j < lines.length && lines[j].trim() === "") {
          dOffset += lines[j].length + 1;
          j += 1;
        }
        if (j < lines.length) {
          bestTime = start;
          bestStart = dOffset;
          bestEnd = dOffset + lines[j].length;
        }
      }
    }

    offset = lineEnd + 1;
  }

  return bestStart === -1 ? null : { start: bestStart, end: bestEnd };
}

/** Format u obliku `HH:MM:SS:mmm` (dvotačka pre milisekundi). */
export function formatCueTime(ms: number): string {
  const clamped = Math.max(0, Math.floor(ms));
  const hh = Math.floor(clamped / 3_600_000);
  const mm = Math.floor((clamped % 3_600_000) / 60_000);
  const ss = Math.floor((clamped % 60_000) / 1000);
  const millis = clamped % 1000;
  const pad = (value: number, size = 2) => String(value).padStart(size, "0");
  return `${pad(hh)}:${pad(mm)}:${pad(ss)}:${pad(millis, 3)}`;
}

/**
 * Indeks cue-a aktivnog u datom trenutku (start ≤ t < end). Ako nijedan nije
 * tačno aktivan, vraća poslednji koji je počeo (ili 0 pre prvog cue-a).
 */
export function activeCueIndex(cues: SubtitleCue[], timeMs: number): number {
  if (cues.length === 0) {
    return -1;
  }
  let candidate = -1;
  for (let i = 0; i < cues.length; i += 1) {
    if (timeMs >= cues[i].startMs && timeMs < cues[i].endMs) {
      return i;
    }
    if (cues[i].startMs <= timeMs) {
      candidate = i;
    }
  }
  return candidate === -1 ? 0 : candidate;
}

/**
 * Traži cue-ove po ključnoj reči (tekst) ili po vremenu (`MM:SS`,
 * `HH:MM:SS`, opciono `,`/`.`/`:` + ms). Vraća indekse pogodaka.
 */
export function searchCues(cues: SubtitleCue[], query: string): number[] {
  const trimmed = query.trim();
  if (!trimmed) {
    return [];
  }

  const asTime = parseTimestamp(
    trimmed.replace(
      /^(\d{1,2}):(\d{2})(?::(\d{2}))?$/,
      (_all, a, b, c) =>
        c === undefined ? `00:${a}:${b}.000` : `${a}:${b}:${c}.000`,
    ),
  );
  if (asTime !== null) {
    const nearest = activeCueIndex(cues, asTime);
    return nearest >= 0 ? [nearest] : [];
  }

  const needle = trimmed.toLocaleLowerCase("sr-Latn-RS");
  return cues
    .filter((cue) =>
      cue.text.toLocaleLowerCase("sr-Latn-RS").includes(needle),
    )
    .map((cue) => cue.index);
}
