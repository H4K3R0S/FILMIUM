import { useEffect, useState } from "react";
import { CloudSun } from "lucide-react";

import { useVreme } from "../../features/vreme/hooks/useVreme";
import { useBootReveal } from "../../features/boot/useBootReveal";
import ClockPopover from "../../features/vreme/components/ClockPopover";


// ==========          LOKALIZACIJA          ==========

/** Skraćeni nazivi dana u nedelji (nedelja = indeks 0). */
const WEEKDAY_LABELS = [
  "NED",
  "PON",
  "UTO",
  "SRE",
  "ČET",
  "PET",
  "SUB",
];

/** Skraćeni nazivi meseci (januar = indeks 0). */
const MONTH_LABELS = [
  "JAN",
  "FEB",
  "MAR",
  "APR",
  "MAJ",
  "JUN",
  "JUL",
  "AVG",
  "SEP",
  "OKT",
  "NOV",
  "DEC",
];


// ==========          POMOĆNE FUNKCIJE          ==========

/**
 * Dopunjava broj vodećom nulom do dve cifre.
 */
function padTwoDigits(value: number): string {
  return value < 10 ? `0${value}` : `${value}`;
}


// ==========          HEADER SAT          ==========

/**
 * Prikazuje tačno vreme u centru CORE zaglavlja: dan u nedelji, veliki
 * sat i minute, male sekunde sa datumom i ikonicu vremenske prognoze.
 */
function HeaderClock() {
  const { togglePopover } = useVreme();
  const [now, setNow] = useState<Date>(() => new Date());

  // Sat je sakriven prve 3 sekunde paljenja, pa sklizne odozgo na poziciju.
  const revealed = useBootReveal(3000);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setNow(new Date());
    }, 1000);

    return () => {
      window.clearInterval(timer);
    };
  }, []);

  const hours = padTwoDigits(now.getHours());
  const minutes = padTwoDigits(now.getMinutes());
  const seconds = padTwoDigits(now.getSeconds());
  const weekday = WEEKDAY_LABELS[now.getDay()];
  const date = `${now.getDate()}. ${MONTH_LABELS[now.getMonth()]}`;

  return (
    <div className={`header-clock ${revealed ? "revealed" : "pre-reveal"}`}>
      <button
        aria-haspopup="dialog"
        aria-label="Trenutno vreme — otvori alate za vreme"
        className="header-clock-face"
        onClick={() => togglePopover()}
        type="button"
      >
        <span className="header-clock-weekday">{weekday}</span>

        <span className="header-clock-time">
          {hours}
          <span className="header-clock-colon">:</span>
          {minutes}
        </span>

        <span className="header-clock-side">
          <span className="header-clock-seconds">{seconds}</span>
          <span className="header-clock-date">{date}</span>
        </span>

        <CloudSun
          aria-hidden="true"
          className="header-clock-weather"
          size={52}
          strokeWidth={1.6}
        />
      </button>

      <ClockPopover />
    </div>
  );
}

export default HeaderClock;
