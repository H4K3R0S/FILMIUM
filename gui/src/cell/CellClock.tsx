import { useEffect, useState } from "react";
import { Clock } from "lucide-react";

import { useVreme } from "../features/vreme/hooks/useVreme";
import ClockPopover from "../features/vreme/components/ClockPopover";

// ==========          SAT ĆELIJE (kompaktan, u sidebaru)          ==========
/*
 * Ćelija nema CORE top-bar (gde stoji veliki `HeaderClock`), pa sistemski sat
 * ovde stoji kao mali dugme-sat u sidebaru: HH:MM + klik otvara `ClockPopover`
 * (alarm/tajmer/štoperica). Sve iz `features/vreme` (bez nativnih zavisnosti).
 */

function pad(value: number): string {
  return value < 10 ? `0${value}` : `${value}`;
}

function CellClock() {
  const { togglePopover } = useVreme();
  const [now, setNow] = useState<Date>(() => new Date());

  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  return (
    <div className="cell-clock">
      <button
        type="button"
        // `header-clock-face` je nužno: `ClockPopover` se sidri baš na taj
        // selektor (računa poziciju panela ispod sata).
        className="cell-clock-face header-clock-face"
        onClick={() => togglePopover()}
        aria-haspopup="dialog"
        aria-label="Vreme — alarm, tajmer, štoperica"
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 8,
          padding: "6px 10px",
          width: "100%",
          border: "1px solid rgba(255,255,255,0.10)",
          borderRadius: 8,
          background: "rgba(255,255,255,0.03)",
          color: "inherit",
          cursor: "pointer",
          font: "600 0.95rem ui-monospace, \"JetBrains Mono\", Consolas, monospace",
          letterSpacing: "0.04em",
        }}
      >
        <Clock size={15} aria-hidden="true" />
        <span>{pad(now.getHours())}:{pad(now.getMinutes())}</span>
      </button>
      <ClockPopover />
    </div>
  );
}

export default CellClock;
