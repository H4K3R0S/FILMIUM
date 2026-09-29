// ==========          VREME TIPOVI          ==========

/** Način ponavljanja alarma. */
export type RepeatMode = "once" | "daily" | "custom";

/** Pravilo ponavljanja: mod + izabrani dani (0 = nedelja .. 6 = subota). */
export type AlarmRepeat = {
  mode: RepeatMode;
  days: number[];
};

/** Jedan alarm. */
export type Alarm = {
  id: string;
  hour: number; // 0–23
  minute: number; // 0–59
  label: string;
  message: string;
  enabled: boolean;
  repeat: AlarmRepeat;
  melody: string;
  /** "YYYY-MM-DDTHH:MM" poslednje okinute minute — sprečava dvostruko okidanje. */
  lastRungMinute: string | null;
};

/** Sačuvano tajmer vreme za brzo pozivanje. */
export type TimerPreset = {
  hours: number;
  minutes: number;
  seconds: number;
};

/** Alat u okviru VREME sistema. */
export type VremeTool = "alarm" | "stopwatch" | "timer";

/** Stanje lebdećeg widgeta: da li je otvoren i pozicija na ekranu. */
export type WidgetState = {
  open: boolean;
  x: number;
  y: number;
};

/** Tab u popover-u sata (uključuje i prognozu koja nema widget). */
export type PopoverTab = VremeTool | "forecast";

/** Podatak o alarmu koji trenutno zvoni. */
export type Ringing = {
  source: "alarm" | "timer";
  message: string;
  melody: string;
};
