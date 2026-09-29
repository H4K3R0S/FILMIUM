import { useState } from "react";
import { Pause, Play, Square } from "lucide-react";

import { useVreme } from "../hooks/useVreme";
import { formatDuration, formatPreset } from "../lib/time";
import NumberWheel from "./NumberWheel";


// ==========          TAB TAJMER          ==========

/**
 * Tri brojčanika (sat, minut, sekunda) za unos, dugme za pokretanje i mreža
 * sačuvanih preseta. Tokom rada prikazuje odbrojavanje sa pauzom i stopom.
 */
function TimerTab() {
  const {
    timer,
    timerPresets,
    startTimer,
    resumeTimer,
    pauseTimer,
    stopTimer,
  } = useVreme();

  const [hours, setHours] = useState(0);
  const [minutes, setMinutes] = useState(5);
  const [seconds, setSeconds] = useState(0);

  const isActive =
    timer.running || (timer.remainingMs > 0 && timer.totalMs > 0);

  const canStart = hours > 0 || minutes > 0 || seconds > 0;

  // ==========          AKTIVNO ODBROJAVANJE          ==========

  if (isActive) {
    const progress =
      timer.totalMs > 0
        ? 1 - timer.remainingMs / timer.totalMs
        : 0;

    return (
      <div className="timer-tab is-running">
        <div className="timer-countdown">
          {formatDuration(timer.remainingMs)}
        </div>

        <div className="timer-progress">
          <span style={{ width: `${Math.min(100, progress * 100)}%` }} />
        </div>

        <div className="timer-controls">
          <button
            aria-label="Zaustavi tajmer"
            className="vreme-control-button"
            onClick={stopTimer}
            type="button"
          >
            <Square size={22} strokeWidth={2} />
          </button>

          <button
            aria-label={
              timer.running ? "Pauziraj tajmer" : "Nastavi tajmer"
            }
            className="vreme-control-button is-primary"
            onClick={timer.running ? pauseTimer : resumeTimer}
            type="button"
          >
            {timer.running ? (
              <Pause size={26} strokeWidth={2} />
            ) : (
              <Play size={26} strokeWidth={2} />
            )}
          </button>
        </div>
      </div>
    );
  }

  // ==========          UNOS VREMENA          ==========

  return (
    <div className="timer-tab">
      <div className="timer-wheels">
        <div className="timer-wheel-column">
          <span className="timer-wheel-label">SAT</span>
          <NumberWheel
            ariaLabel="Sat"
            max={23}
            min={0}
            onChange={setHours}
            value={hours}
          />
        </div>

        <span className="timer-wheel-colon">:</span>

        <div className="timer-wheel-column">
          <span className="timer-wheel-label">MIN</span>
          <NumberWheel
            ariaLabel="Minut"
            max={59}
            min={0}
            onChange={setMinutes}
            value={minutes}
          />
        </div>

        <span className="timer-wheel-colon">:</span>

        <div className="timer-wheel-column">
          <span className="timer-wheel-label">SEK</span>
          <NumberWheel
            ariaLabel="Sekunda"
            max={59}
            min={0}
            onChange={setSeconds}
            value={seconds}
          />
        </div>
      </div>

      <button
        aria-label="Pokreni tajmer"
        className="timer-start"
        disabled={!canStart}
        onClick={() => startTimer({ hours, minutes, seconds })}
        type="button"
      >
        <Play size={22} strokeWidth={2.2} />
        Pokreni
      </button>

      {/* ==========          PRESETI          ========== */}

      {timerPresets.length > 0 && (
        <div className="timer-presets">
          {timerPresets.map((preset, index) => (
            <button
              className="timer-preset"
              key={`${preset.hours}-${preset.minutes}-${preset.seconds}-${index}`}
              onClick={() => {
                setHours(preset.hours);
                setMinutes(preset.minutes);
                setSeconds(preset.seconds);
              }}
              type="button"
            >
              {formatPreset(
                preset.hours,
                preset.minutes,
                preset.seconds,
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default TimerTab;
