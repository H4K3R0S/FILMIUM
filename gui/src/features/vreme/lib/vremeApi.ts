import type { Alarm, PopoverTab, TimerPreset, VremeTool } from "../types";


// ==========          VREME IMPERATIVNI API          ==========

// Modul-level singleton preko kojeg bilo koji deo programa (i van React
// stabla) može da pozove VREME akcije. VremeProvider pri montiranju registruje
// svoje akcije; dok provider nije montiran, pozivi su bezbedan no-op.

/** Ulaz za kreiranje alarma — id i tehnička polja se popunjavaju automatski. */
export type NewAlarmInput = {
  hour: number;
  minute: number;
  label?: string;
  message?: string;
  enabled?: boolean;
  repeat?: Alarm["repeat"];
  melody?: string;
};

/** Ulaz za pokretanje tajmera. */
export type TimerInput = {
  hours?: number;
  minutes?: number;
  seconds?: number;
};

export type VremeActions = {
  addAlarm: (input: NewAlarmInput) => string;
  updateAlarm: (id: string, patch: Partial<Alarm>) => void;
  removeAlarm: (id: string) => void;
  toggleAlarm: (id: string, enabled?: boolean) => void;

  startStopwatch: () => void;
  pauseStopwatch: () => void;
  resetStopwatch: () => void;

  startTimer: (input: TimerInput) => void;
  resumeTimer: () => void;
  pauseTimer: () => void;
  stopTimer: () => void;
  resetTimer: () => void;
  saveTimerPreset: (preset: TimerPreset) => void;

  openPopover: (tab?: PopoverTab) => void;
  closePopover: () => void;
  openWidget: (tool: VremeTool) => void;
  closeWidget: (tool: VremeTool) => void;
};

const NOOP_RESULT = "";

let bound: VremeActions | null = null;

/**
 * Registruje stvarne akcije (poziva VremeProvider pri montiranju).
 */
export function bindVremeApi(actions: VremeActions): void {
  bound = actions;
}

/**
 * Uklanja registrovane akcije (poziva VremeProvider pri demontiranju).
 */
export function unbindVremeApi(actions: VremeActions): void {
  if (bound === actions) {
    bound = null;
  }
}

/**
 * Poziva akciju ako je provider montiran; u suprotnom je bezbedan no-op.
 */
function call<Key extends keyof VremeActions>(
  key: Key,
  ...args: Parameters<VremeActions[Key]>
): ReturnType<VremeActions[Key]> | undefined {
  if (bound === null) {
    return undefined;
  }

  // @ts-expect-error — argumenti su tipizovani na pozivnom mestu ispod.
  return bound[key](...args);
}

/**
 * Javni singleton za pozivanje VREME akcija iz bilo kog dela programa.
 */
export const vremeApi: VremeActions = {
  addAlarm: (input) => call("addAlarm", input) ?? NOOP_RESULT,
  updateAlarm: (id, patch) => {
    call("updateAlarm", id, patch);
  },
  removeAlarm: (id) => {
    call("removeAlarm", id);
  },
  toggleAlarm: (id, enabled) => {
    call("toggleAlarm", id, enabled);
  },

  startStopwatch: () => {
    call("startStopwatch");
  },
  pauseStopwatch: () => {
    call("pauseStopwatch");
  },
  resetStopwatch: () => {
    call("resetStopwatch");
  },

  startTimer: (input) => {
    call("startTimer", input);
  },
  resumeTimer: () => {
    call("resumeTimer");
  },
  pauseTimer: () => {
    call("pauseTimer");
  },
  stopTimer: () => {
    call("stopTimer");
  },
  resetTimer: () => {
    call("resetTimer");
  },
  saveTimerPreset: (preset) => {
    call("saveTimerPreset", preset);
  },

  openPopover: (tab) => {
    call("openPopover", tab);
  },
  closePopover: () => {
    call("closePopover");
  },
  openWidget: (tool) => {
    call("openWidget", tool);
  },
  closeWidget: (tool) => {
    call("closeWidget", tool);
  },
};
