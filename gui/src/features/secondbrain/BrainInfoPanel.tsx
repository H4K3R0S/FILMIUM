import { createElement } from "react";
import { ExternalLink, X } from "lucide-react";

import type { BrainNode } from "../../types/secondBrain";
import { groupColor, iconFor } from "./brainColors";

type BrainInfoPanelProps = {
  node: BrainNode | null;
  neighbors: BrainNode[];
  onOpen: (node: BrainNode) => void;
  onClose: () => void;
};

/** Bocni panel sa detaljima izabranog cvora i listom povezanih cvorova. */
function BrainInfoPanel({ node, neighbors, onOpen, onClose }: BrainInfoPanelProps) {
  if (node === null) {
    return null;
  }

  const color = groupColor(node.group);

  return (
    <aside className="brain-info-panel" data-testid="brain-info-panel" aria-label="Detalji cvora">
      <button
        className="brain-info-close"
        type="button"
        aria-label="Zatvori"
        onClick={onClose}
      >
        <X size={16} />
      </button>

      <div className="brain-info-head">
        <span className="brain-info-icon" style={{ color }}>
          {createElement(iconFor(node.icon), { size: 22 })}
        </span>
        <h2 className="brain-info-title">{node.label}</h2>
      </div>

      <dl className="brain-info-meta">
        <div>
          <dt>Tip</dt>
          <dd>{node.kind}</dd>
        </div>
        {node.group && (
          <div>
            <dt>Grupa</dt>
            <dd style={{ color }}>{node.group}</dd>
          </div>
        )}
        {node.path && (
          <div>
            <dt>Putanja</dt>
            <dd className="brain-info-path">{node.path}</dd>
          </div>
        )}
      </dl>

      {neighbors.length > 0 && (
        <div className="brain-info-links">
          <p className="brain-info-links-label">Povezano ({neighbors.length})</p>
          <ul>
            {neighbors.map((item) => (
              <li key={item.id}>{item.label}</li>
            ))}
          </ul>
        </div>
      )}

      <button className="brain-info-open" type="button" onClick={() => onOpen(node)}>
        <ExternalLink size={15} />
        Otvori
      </button>
    </aside>
  );
}

export default BrainInfoPanel;
