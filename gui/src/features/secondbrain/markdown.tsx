import { createElement, type ReactNode } from "react";

/**
 * Mali, bezbedan Markdown renderer (bez dangerouslySetInnerHTML, bez novih
 * zavisnosti) — dovoljno za CORE dokumente: naslovi, liste, code-fence, inline
 * kod, bold/italic, linkovi, blockquote, hr. Nepodrzano (npr. tabele) pada na
 * citljiv tekst. Gradi React elemente pa je XSS-otporno po konstrukciji.
 */

const INLINE = /(`[^`]+`)|(\*\*([^*]+)\*\*)|(\*([^*]+)\*)|(\[([^\]]+)\]\(([^)]+)\))/g;

/** Inline formatiranje jednog reda teksta u niz React cvorova. */
function renderInline(text: string, keyBase: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  let last = 0;
  let match: RegExpExecArray | null;
  let i = 0;
  INLINE.lastIndex = 0;
  while ((match = INLINE.exec(text)) !== null) {
    if (match.index > last) {
      nodes.push(text.slice(last, match.index));
    }
    const key = `${keyBase}-i${i}`;
    if (match[1]) {
      nodes.push(<code key={key} className="bm-code-inline">{match[1].slice(1, -1)}</code>);
    } else if (match[2]) {
      nodes.push(<strong key={key}>{match[3]}</strong>);
    } else if (match[4]) {
      nodes.push(<em key={key}>{match[5]}</em>);
    } else if (match[6]) {
      nodes.push(
        <a key={key} href={match[8]} target="_blank" rel="noreferrer">{match[7]}</a>,
      );
    }
    last = INLINE.lastIndex;
    i += 1;
  }
  if (last < text.length) {
    nodes.push(text.slice(last));
  }
  return nodes;
}

const BLOCK_START = /^(#{1,6})\s|^```|^>\s?|^\s*([-*+]|\d+\.)\s+|^(-{3,}|\*{3,}|_{3,})\s*$/;

/** Blok-parser: vraca niz React cvorova za dati Markdown izvor. */
export function renderMarkdown(src: string): ReactNode[] {
  const lines = src.replace(/\r\n/g, "\n").split("\n");
  const out: ReactNode[] = [];
  let i = 0;
  let key = 0;

  while (i < lines.length) {
    const line = lines[i];

    // Code fence: ```lang ... ```
    if (/^```/.test(line.trim())) {
      const lang = line.trim().slice(3).trim();
      const buf: string[] = [];
      i += 1;
      while (i < lines.length && !/^```/.test(lines[i].trim())) {
        buf.push(lines[i]);
        i += 1;
      }
      i += 1; // preskoci zatvarajuci ```
      out.push(
        <pre key={key++} className="bm-code-block" data-lang={lang || undefined}>
          <code>{buf.join("\n")}</code>
        </pre>,
      );
      continue;
    }

    // Naslovi #..######
    const heading = /^(#{1,6})\s+(.*)$/.exec(line);
    if (heading) {
      const level = heading[1].length;
      out.push(
        createElement(
          `h${Math.min(level, 4)}`,
          { key: key++, className: `bm-h bm-h${level}` },
          renderInline(heading[2], `h${key}`),
        ),
      );
      i += 1;
      continue;
    }

    // Horizontalna linija
    if (/^(-{3,}|\*{3,}|_{3,})\s*$/.test(line)) {
      out.push(<hr key={key++} className="bm-hr" />);
      i += 1;
      continue;
    }

    // Blockquote (rekurzivno)
    if (/^>\s?/.test(line)) {
      const buf: string[] = [];
      while (i < lines.length && /^>\s?/.test(lines[i])) {
        buf.push(lines[i].replace(/^>\s?/, ""));
        i += 1;
      }
      out.push(
        <blockquote key={key++} className="bm-quote">{renderMarkdown(buf.join("\n"))}</blockquote>,
      );
      continue;
    }

    // Liste (ul/ol) — jedan nivo
    if (/^\s*([-*+]|\d+\.)\s+/.test(line)) {
      const ordered = /^\s*\d+\.\s+/.test(line);
      const items: ReactNode[] = [];
      while (i < lines.length && /^\s*([-*+]|\d+\.)\s+/.test(lines[i])) {
        const item = lines[i].replace(/^\s*([-*+]|\d+\.)\s+/, "");
        items.push(<li key={items.length}>{renderInline(item, `li${key}-${items.length}`)}</li>);
        i += 1;
      }
      out.push(
        createElement(ordered ? "ol" : "ul", { key: key++, className: "bm-list" }, items),
      );
      continue;
    }

    // Prazan red
    if (line.trim() === "") {
      i += 1;
      continue;
    }

    // Paragraf: spoji do praznog reda ili pocetka novog bloka
    const buf: string[] = [line];
    i += 1;
    while (i < lines.length && lines[i].trim() !== "" && !BLOCK_START.test(lines[i])) {
      buf.push(lines[i]);
      i += 1;
    }
    out.push(<p key={key++} className="bm-p">{renderInline(buf.join(" "), `p${key}`)}</p>);
  }

  return out;
}
