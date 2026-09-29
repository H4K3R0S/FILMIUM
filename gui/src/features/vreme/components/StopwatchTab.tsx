import { Pause, Play, RotateCcw } from "lucide-react";

import { useVreme } from "../hooks/useVreme";
import { usePreciseElapsed } from "../hooks/usePreciseElapsed";
import { formatCentiseconds, formatDuration } from "../lib/time";


// ==========          TAB STOPERICA          ==========

/**
 * Prikaz vremena u formatu HH:MM:SS sa sitnim milisekundama i dugmadima za
 * pokretanje/pauzu i resetovanje.
 */
function StopwatchTab() {
  const { stopwatch, startStopwatch, pauseStopwatch, resetStopwatch } =
    useVreme();
  const elapsed = usePreciseElapsed();

  return (
    <div className="stopwatch-tab">
      <div className="stopwatch-display">
        {formatDuration(elapsed)}
        <span className="stopwatch-millis">
          .{formatCentiseconds(elapsed)}
        </span>
      </div>

      <div className="stopwatch-controls">
        {stopwatch.elapsedMs > 0 && !stopwatch.running && (
          <button
            aria-label="Resetuj stopericu"
            className="vreme-control-button"
            onClick={resetStopwatch}
            type="button"
          >
            <RotateCcw size={22} strokeWidth={2} />
          </button>
        )}

        <button
          aria-label={
            stopwatch.running ? "Pauziraj stopericu" : "Pokreni stopericu"
          }
          className="vreme-control-button is-primary"
          onClick={stopwatch.running ? pauseStopwatch : startStopwatch}
          type="button"
        >
          {stopwatch.running ? (
            <Pause size={26} strokeWidth={2} />
          ) : (
            <Play size={26} strokeWidth={2} />
          )}
        </button>
      </div>
    </div>
  );
}

export default StopwatchTab;
