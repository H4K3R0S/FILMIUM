import type { Alarm } from "../types";


// ==========          LOKALIZACIJA          ==========

/** Skraćeni dani u nedelji (0 = nedelja .. 6 = subota). */
export const WEEKDAY_LABELS = [
  "NED",
  "PON",
  "UTO",
  "SRE",
  "ČET",
  "PET",
  "SUB",
];


// ==========          FORMATIRANJE          ==========

/**
 * Dopunjava broj vodećom nulom do dve cifre.
 */
export function padTwo(value: number): string {
  return value < 10 ? `0${value}` : `${value}`;
}

/**
 * Formatira sat i minut u "HH:MM".
 */
export function formatHourMinute(hour: number, minute: number): string {
  return `${padTwo(hour)}:${padTwo(minute)}`;
}

/**
 * Formatira trajanje (ms) u "HH:MM:SS".
 */
export function formatDuration(totalMs: number): string {
  const totalSeconds = Math.max(0, Math.floor(totalMs / 1000));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  return `${padTwo(hours)}:${padTwo(minutes)}:${padTwo(seconds)}`;
}

/**
 * Dvocifrene stotinke sekunde iz trajanja (ms), za sitan prikaz stoperice.
 */
export function formatCentiseconds(totalMs: number): string {
  return padTwo(Math.floor((Math.max(0, totalMs) % 1000) / 10));
}

/**
 * Kompaktna oznaka tajmer preseta: "M:SS" ili "H:MM:SS".
 */
export function formatPreset(
  hours: number,
  minutes: number,
  seconds: number,
): string {
  if (hours > 0) {
    return `${hours}:${padTwo(minutes)}:${padTwo(seconds)}`;
  }

  return `${padTwo(minutes)}:${padTwo(seconds)}`;
}

/**
 * Kratak opis preostalog vremena, npr. "za 2 h 15 min" ili "za 40 s".
 */
export function formatCountdown(ms: number): string {
  if (ms <= 0) {
    return "sada";
  }

  const totalMinutes = Math.floor(ms / 60000);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;

  if (hours > 0) {
    return `za ${hours} h ${padTwo(minutes)} min`;
  }

  if (minutes > 0) {
    return `za ${minutes} min`;
  }

  return `za ${Math.ceil(ms / 1000)} s`;
}


// ==========          ALARM LOGIKA          ==========

/**
 * Ključ minute za dati datum: "YYYY-MM-DDTHH:MM".
 */
export function minuteKey(date: Date): string {
  return (
    `${date.getFullYear()}-${padTwo(date.getMonth() + 1)}-` +
    `${padTwo(date.getDate())}T${padTwo(date.getHours())}:` +
    `${padTwo(date.getMinutes())}`
  );
}

/**
 * Da li pravilo ponavljanja dozvoljava okidanje na dati dan u nedelji.
 */
function repeatAllowsDay(alarm: Alarm, weekday: number): boolean {
  switch (alarm.repeat.mode) {
    case "daily":
      return true;
    case "custom":
      return alarm.repeat.days.includes(weekday);
    case "once":
    default:
      // Jednokratni alarm sme na bilo koji dan (prvi naredni termin).
      return true;
  }
}

/**
 * Računa naredni termin okidanja alarma posle datog trenutka.
 * Vraća null ako alarm nema važeći termin (npr. custom bez dana).
 */
export function nextAlarmOccurrence(
  alarm: Alarm,
  from: Date,
): Date | null {
  if (alarm.repeat.mode === "custom" && alarm.repeat.days.length === 0) {
    return null;
  }

  for (let offset = 0; offset <= 7; offset += 1) {
    const candidate = new Date(from);
    candidate.setDate(from.getDate() + offset);
    candidate.setHours(alarm.hour, alarm.minute, 0, 0);

    if (candidate.getTime() <= from.getTime()) {
      // Termin je već prošao za taj dan.
      continue;
    }

    if (repeatAllowsDay(alarm, candidate.getDay())) {
      return candidate;
    }
  }

  return null;
}

/**
 * Najbliži uključeni alarm i vreme (ms) do njega, posle datog trenutka.
 */
export function nextEnabledAlarm(
  alarms: Alarm[],
  from: Date,
): { alarm: Alarm; at: Date; ms: number } | null {
  let best: { alarm: Alarm; at: Date; ms: number } | null = null;

  for (const alarm of alarms) {
    if (!alarm.enabled) {
      continue;
    }

    const at = nextAlarmOccurrence(alarm, from);

    if (at === null) {
      continue;
    }

    const ms = at.getTime() - from.getTime();

    if (best === null || ms < best.ms) {
      best = { alarm, at, ms };
    }
  }

  return best;
}

/**
 * Da li alarm treba da okine tačno u datom trenutku (poklapanje HH:MM,
 * sekunda 0 i dozvoljen dan). Zaštita od ponovnog okidanja u istoj minuti
 * je odgovornost pozivaoca (preko lastRungMinute).
 */
export function alarmMatchesNow(alarm: Alarm, now: Date): boolean {
  if (!alarm.enabled) {
    return false;
  }

  if (now.getHours() !== alarm.hour || now.getMinutes() !== alarm.minute) {
    return false;
  }

  return repeatAllowsDay(alarm, now.getDay());
}
