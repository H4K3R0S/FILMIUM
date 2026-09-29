import { useCallback, type WheelEvent } from "react";

import { padTwo } from "../lib/time";


// ==========          BROJČANIK (SCROLL WHEEL)          ==========

type NumberWheelProps = {
  value: number;
  min: number;
  max: number;
  onChange: (value: number) => void;
  ariaLabel: string;
};

/** Broj vidljivih vrednosti iznad/ispod selektovane. */
const VISIBLE_RADIUS = 2;

/**
 * Obmotava vrednost u opsegu [min, max] (vrti se u krug).
 */
function wrap(value: number, min: number, max: number): number {
  const range = max - min + 1;

  return ((((value - min) % range) + range) % range) + min;
}

/**
 * Vertikalni brojčanik: 5 vrednosti, sredina selektovana, menja se scroll-om
 * miša, klikom na vrednost i strelicama; vrti se u krug.
 */
function NumberWheel({
  value,
  min,
  max,
  onChange,
  ariaLabel,
}: NumberWheelProps) {
  const step = useCallback(
    (delta: number) => {
      onChange(wrap(value + delta, min, max));
    },
    [value, min, max, onChange],
  );

  const handleWheel = useCallback(
    (event: WheelEvent<HTMLDivElement>) => {
      event.preventDefault();
      step(event.deltaY > 0 ? 1 : -1);
    },
    [step],
  );

  const offsets = [];

  for (let offset = -VISIBLE_RADIUS; offset <= VISIBLE_RADIUS; offset += 1) {
    offsets.push(offset);
  }

  return (
    <div
      aria-label={ariaLabel}
      aria-valuemax={max}
      aria-valuemin={min}
      aria-valuenow={value}
      className="number-wheel"
      onKeyDown={(event) => {
        if (event.key === "ArrowUp") {
          event.preventDefault();
          step(-1);
        } else if (event.key === "ArrowDown") {
          event.preventDefault();
          step(1);
        }
      }}
      onWheel={handleWheel}
      role="spinbutton"
      tabIndex={0}
    >
      <button
        aria-label={`${ariaLabel} — gore`}
        className="number-wheel-arrow"
        onClick={() => step(-1)}
        tabIndex={-1}
        type="button"
      >
        ‹
      </button>

      <div className="number-wheel-values" key={value}>
        {offsets.map((offset) => {
          const itemValue = wrap(value + offset, min, max);
          const isCenter = offset === 0;

          return (
            <button
              aria-hidden={isCenter ? undefined : "true"}
              className={`number-wheel-value distance-${Math.abs(offset)} ${
                isCenter ? "is-selected" : ""
              }`}
              key={offset}
              onClick={() => step(offset)}
              tabIndex={-1}
              type="button"
            >
              {padTwo(itemValue)}
            </button>
          );
        })}
      </div>

      <button
        aria-label={`${ariaLabel} — dole`}
        className="number-wheel-arrow"
        onClick={() => step(1)}
        tabIndex={-1}
        type="button"
      >
        ›
      </button>
    </div>
  );
}

export default NumberWheel;
