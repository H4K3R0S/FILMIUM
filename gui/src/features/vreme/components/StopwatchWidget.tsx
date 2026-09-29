import { Pause, Play, RotateCcw, Square, Timer } from "lucide-react";

import { useVreme } from "../hooks/useVreme";
import { usePreciseElapsed } from "../hooks/usePreciseElapsed";
import { formatCentiseconds, formatDuration } from "../lib/time";
import VremeWidgetShell from "./VremeWidgetShell";


// ==========          STOPERICA WIDGET          ==========

/**
 * Lebdeći prikaz stoperice sa kontrolama play, pauza, stop i reset.
 */
function StopwatchWidget() {
  const { stopwatch, startStopwatch, pauseStopwatch, resetStopwatch } =
    useVreme();
  const elapsed = usePreciseElapsed();

  return (
    <VremeWidgetShell
      icon={<Timer size={14} strokeWidth={2} />}
      title="Stoperica"
      tool="stopwatch"
    >
      <div className="widget-time">
        {formatDuration(elapsed)}
        <span className="widget-millis">
          .{formatCentiseconds(elapsed)}
        </span>
      </div>

      <div className="widget-controls">
        <button
          aria-label="Pokreni"
          className="vreme-control-button is-mini"
          disabled={stopwatch.running}
          onClick={startStopwatch}
          type="button"
        >
          <Play size={16} strokeWidth={2.2} />
        </button>

        <button
          aria-label="Pauziraj"
          className="vreme-control-button is-mini"
          disabled={!stopwatch.running}
          onClick={pauseStopwatch}
          type="button"
        >
          <Pause size={16} strokeWidth={2.2} />
        </button>

        <button
          aria-label="Zaustavi"
          className="vreme-control-button is-mini"
          disabled={!stopwatch.running}
          onClick={pauseStopwatch}
          type="button"
        >
          <Square size={16} strokeWidth={2.2} />
        </button>

        <button
          aria-label="Resetuj"
          className="vreme-control-button is-mini"
          disabled={stopwatch.elapsedMs === 0}
          onClick={resetStopwatch}
          type="button"
        >
          <RotateCcw size={16} strokeWidth={2.2} />
        </button>
      </div>
    </VremeWidgetShell>
  );
}

export default StopwatchWidget;
