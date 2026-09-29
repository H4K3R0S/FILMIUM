import { createElement, useEffect, useState } from "react";
import { ExternalLink, X } from "lucide-react";

import type { BrainFile, BrainNode } from "../types/secondBrain";
import { getBrainFile } from "../services/secondBrainApi";
import { groupColor, iconFor } from "../features/secondbrain/brainColors";
import { renderMarkdown } from "../features/secondbrain/markdown";

type CellBrainContentPanelProps = {
  node: BrainNode | null;
  onOpen: (node: BrainNode) => void;
  onClose: () => void;
};

function baseName(path: string): string {
  return path.split("/").pop() ?? path;
}

function extOf(path: string): string {
  return path.split(".").pop()?.toLowerCase() ?? "";
}

/*
 * NIJE mrtav kod u CORE-u: ovo je izvor `pre`-varijante koji direktna isporuka
 * (scripts/cell/deliver_second_brain — tj. delivery skript reforme) kopira u
 * ćelije koje NE treba da nose Monaco (FILMIUM/IMPERIUM), uz prepis uvoza u
 * `CellSecondBrain` sa `../features/secondbrain/BrainContentPanel` na
 * `./CellBrainContentPanel`. Ćelije sa Monaco-om (CODIUM/KALIMA) je ne koriste.
 */

/**
 * Levi panel sa sadržajem izabranog fajla — verzija ćelije BEZ Monaco editora.
 * Markdown se renderuje formatirano; kod se prikazuje u prostom read-only
 * `<pre>` bloku (bez `@monaco-editor` zavisnosti). Ista svojstva i klase kao
 * `features/secondbrain/BrainContentPanel`, pa `CellSecondBrain` bira jedan od
 * dva po ćeliji (Monaco tamo gde je poželjan, `<pre>` gde nije).
 */
function CellBrainContentPanel({ node, onOpen, onClose }: CellBrainContentPanelProps) {
  const [file, setFile] = useState<BrainFile | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const path = node?.path ?? null;

  useEffect(() => {
    if (!path) {
      return;
    }
    let alive = true;
    void (async () => {
      setIsLoading(true);
      setErrorMessage(null);
      setFile(null);
      try {
        const data = await getBrainFile(path);
        if (alive) {
          setFile(data);
        }
      } catch (error) {
        if (alive) {
          setErrorMessage(error instanceof Error ? error.message : "Citanje fajla nije uspelo.");
        }
      } finally {
        if (alive) {
          setIsLoading(false);
        }
      }
    })();
    return () => {
      alive = false;
    };
  }, [path]);

  if (node === null || path === null) {
    return null;
  }

  const color = groupColor(node.group);
  const ext = extOf(path);
  const isMarkdown = ext === "md" || ext === "markdown";

  return (
    <aside className="brain-content-panel" data-testid="brain-content-panel" aria-label="Sadrzaj fajla">
      <header className="brain-content-head">
        <span className="brain-content-icon" style={{ color }}>
          {createElement(iconFor(node.icon), { size: 18 })}
        </span>
        <div className="brain-content-titles">
          <h2 className="brain-content-title">{baseName(path)}</h2>
          <p className="brain-content-path">{path}</p>
        </div>
        {node.route && (
          <button
            className="brain-content-open"
            type="button"
            onClick={() => onOpen(node)}
            title="Otvori u domenu"
          >
            <ExternalLink size={14} />
          </button>
        )}
        <button className="brain-content-close" type="button" aria-label="Zatvori" onClick={onClose}>
          <X size={16} />
        </button>
      </header>

      <div className="brain-content-body">
        {isLoading && <p className="brain-content-note">Ucitavam…</p>}
        {errorMessage && <p className="brain-content-note error">{errorMessage}</p>}
        {file && file.binary && <p className="brain-content-note">Binarni fajl — nema pregleda.</p>}
        {file && file.truncated && <p className="brain-content-note">Fajl je prevelik za pregled.</p>}
        {file && !file.binary && !file.truncated && isMarkdown && (
          <div className="bm" data-testid="brain-markdown">{renderMarkdown(file.content)}</div>
        )}
        {file && !file.binary && !file.truncated && !isMarkdown && (
          <div className="brain-content-code">
            <pre className="brain-content-pre"><code>{file.content}</code></pre>
          </div>
        )}
      </div>
    </aside>
  );
}

export default CellBrainContentPanel;
