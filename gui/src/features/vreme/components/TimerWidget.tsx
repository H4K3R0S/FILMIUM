import { Hourglass, Pause, Play, RotateCcw, Square } from "lucide-react";

import { useVreme } from "../hooks/useVreme";
import { formatDuration } from "../lib/time";
import VremeWidgetShell from "./VremeWidgetShell";


// ==========          TAJMER WIDGET          ==========

/**
 * Lebdeći prikaz tajmera sa kontrolama play (nastavi), pauza, stop i reset.
 */
function TimerWidget() {
  const { timer, resumeTimer, pauseTimer, stopTimer, resetTimer } =
    useVreme();

  const isActive =
    timer.running || (timer.remainingMs > 0 && timer.totalMs > 0);

  const displayMs =
    timer.remainingMs > 0 ? timer.remainingMs : timer.totalMs;

  return (
    <VremeWidgetShell
      icon={<Hourglass size={14} strokeWidth={2} />}
      title="Tajmer"
      tool="timer"
    >
      <div className="widget-time">{formatDuration(displayMs)}</div>

      <div className="widget-controls">
        <button
          aria-label="Nastavi"
          className="vreme-control-button is-mini"
          disabled={timer.running || timer.remainingMs <= 0}
          onClick={resumeTimer}
          type="button"
        >
          <Play size={16} strokeWidth={2.2} />
        </button>

        <button
          aria-label="Pauziraj"
          className="vreme-control-button is-mini"
          disabled={!timer.running}
          onClick={pauseTimer}
          type="button"
        >
          <Pause size={16} strokeWidth={2.2} />
        </button>

        <button
          aria-label="Zaustavi"
          className="vreme-control-button is-mini"
          disabled={!isActive}
          onClick={stopTimer}
          type="button"
        >
          <Square size={16} strokeWidth={2.2} />
        </button>

        <button
          aria-label="Resetuj"
          className="vreme-control-button is-mini"
          disabled={timer.totalMs === 0}
          onClick={resetTimer}
          type="button"
        >
          <RotateCcw size={16} strokeWidth={2.2} />
        </button>
      </div>
    </VremeWidgetShell>
  );
}

export default TimerWidget;
