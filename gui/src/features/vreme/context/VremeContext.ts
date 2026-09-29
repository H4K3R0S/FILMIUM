import { createContext } from "react";

import type {
  Alarm,
  PopoverTab,
  Ringing,
  TimerPreset,
  VremeTool,
  WidgetState,
} from "../types";
import type { VremeActions } from "../lib/vremeApi";


// ==========          VREME KONTEKST          ==========

export type StopwatchView = {
  running: boolean;
  elapsedMs: number;
  /** Epoha poslednjeg pokretanja (za precizan sub-sekundni prikaz). */
  startedAt: number | null;
  /** Akumulirano vreme pre trenutnog pokretanja. */
  baseMs: number;
};

export type TimerView = {
  running: boolean;
  remainingMs: number;
  totalMs: number;
};

export type VremeContextValue = VremeActions & {
  now: Date;
  alarms: Alarm[];
  timerPresets: TimerPreset[];
  ringing: Ringing | null;
  popover: { open: boolean; tab: PopoverTab };
  widgets: Record<VremeTool, WidgetState>;
  stopwatch: StopwatchView;
  timer: TimerView;

  togglePopover: (tab?: PopoverTab) => void;
  setPopoverTab: (tab: PopoverTab) => void;
  moveWidget: (tool: VremeTool, x: number, y: number) => void;
  dismissRing: () => void;
  snoozeRing: (minutes?: number) => void;
};

export const VremeContext = createContext<VremeContextValue | null>(null);
