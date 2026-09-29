import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { PictureInPicture2 } from "lucide-react";

import type { PopoverTab, VremeTool } from "../types";
import { useVreme } from "../hooks/useVreme";
import { playSound } from "../../../lib/sound";
import AlarmTab from "./AlarmTab";
import StopwatchTab from "./StopwatchTab";
import TimerTab from "./TimerTab";
import ForecastTab from "./ForecastTab";


// ==========          TABOVI          ==========

const TABS: { id: PopoverTab; label: string }[] = [
  { id: "alarm", label: "ALARM" },
  { id: "stopwatch", label: "STOPERICA" },
  { id: "timer", label: "TAJMER" },
  { id: "forecast", label: "PROGNOZA" },
];

/** Tabovi koji mogu da se otkinu kao lebdeći widget. */
const WIDGET_TABS: PopoverTab[] = ["alarm", "stopwatch", "timer"];

type Anchor = { left: number; top: number };


// ==========          POPOVER SATA          ==========

/**
 * Panel ispod sata sa četiri taba (Alarm, Stoperica, Tajmer, Prognoza).
 * Renderuje se kroz portal na <body> sa fiksnim pozicioniranjem tako da uvek
 * stoji iznad svih ostalih elemenata (izvan stacking konteksta zaglavlja).
 * Zatvara se klikom van panela (osim na sam sat).
 */
function ClockPopover() {
  const { popover, setPopoverTab, closePopover, openWidget } = useVreme();
  const panelRef = useRef<HTMLDivElement>(null);
  const [anchor, setAnchor] = useState<Anchor | null>(null);

  // Zvuk pri otvaranju popup prozora.
  useEffect(() => {
    if (popover.open) {
      playSound("popup");
    }
  }, [popover.open]);

  // Izračunaj poziciju ispod sata i prati promene veličine/skrola.
  useEffect(() => {
    if (!popover.open) {
      return;
    }

    const updateAnchor = () => {
      const face = document.querySelector(".header-clock-face");

      if (face === null) {
        return;
      }

      const rect = face.getBoundingClientRect();
      setAnchor({
        left: rect.left + rect.width / 2,
        top: rect.bottom + 12,
      });
    };

    updateAnchor();
    window.addEventListener("resize", updateAnchor);
    window.addEventListener("scroll", updateAnchor, true);

    return () => {
      window.removeEventListener("resize", updateAnchor);
      window.removeEventListener("scroll", updateAnchor, true);
    };
  }, [popover.open]);

  // Zatvaranje klikom van panela (osim na sam sat).
  useEffect(() => {
    if (!popover.open) {
      return;
    }

    const handlePointerDown = (event: MouseEvent) => {
      const target = event.target as HTMLElement;

      if (panelRef.current?.contains(target)) {
        return;
      }

      if (target.closest(".header-clock-face")) {
        return;
      }

      closePopover();
    };

    document.addEventListener("mousedown", handlePointerDown);

    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
    };
  }, [popover.open, closePopover]);

  if (!popover.open || anchor === null) {
    return null;
  }

  const canPopOut = WIDGET_TABS.includes(popover.tab);

  return createPortal(
    <div
      className="clock-popover"
      ref={panelRef}
      role="dialog"
      style={{ left: `${anchor.left}px`, top: `${anchor.top}px` }}
    >
      {canPopOut && (
        <button
          aria-label="Otkini kao lebdeći widget"
          className="clock-popover-popout"
          onClick={() => {
            openWidget(popover.tab as VremeTool);
            closePopover();
          }}
          title="Otkini kao widget"
          type="button"
        >
          <PictureInPicture2 size={15} strokeWidth={2} />
        </button>
      )}

      <div className="clock-popover-tabs" role="tablist">
        {TABS.map((tab) => (
          <button
            aria-selected={popover.tab === tab.id}
            className={`clock-popover-tab ${
              popover.tab === tab.id ? "is-active" : ""
            }`}
            key={tab.id}
            onClick={() => setPopoverTab(tab.id)}
            role="tab"
            type="button"
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="clock-popover-body">
        {popover.tab === "alarm" && <AlarmTab />}
        {popover.tab === "stopwatch" && <StopwatchTab />}
        {popover.tab === "timer" && <TimerTab />}
        {popover.tab === "forecast" && <ForecastTab />}
      </div>
    </div>,
    document.body,
  );
}

export default ClockPopover;
