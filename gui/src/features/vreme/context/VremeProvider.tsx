import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import type {
  Alarm,
  PopoverTab,
  Ringing,
  TimerPreset,
  VremeTool,
  WidgetState,
} from "../types";
import {
  alarmMatchesNow,
  minuteKey,
} from "../lib/time";
import { playMelody, stopMelody } from "../lib/audio";
import {
  bindVremeApi,
  unbindVremeApi,
  type NewAlarmInput,
  type TimerInput,
  type VremeActions,
} from "../lib/vremeApi";
import {
  VremeContext,
  type VremeContextValue,
} from "./VremeContext";


// ==========          PERZISTENCIJA          ==========

const ALARMS_KEY = "core.vreme.alarms";
const PRESETS_KEY = "core.vreme.timerPresets";
const WIDGETS_KEY = "core.vreme.widgets";

/** Podrazumevane pozicije lebdećih widgeta (kaskadno). */
const DEFAULT_WIDGETS: Record<VremeTool, WidgetState> = {
  alarm: { open: false, x: 48, y: 150 },
  stopwatch: { open: false, x: 48, y: 330 },
  timer: { open: false, x: 48, y: 510 },
};

/**
 * Čita i parsira vrednost iz localStorage; vraća rezervu pri grešci.
 */
function readStored<Value>(key: string, fallback: Value): Value {
  if (typeof window === "undefined") {
    return fallback;
  }

  try {
    const raw = window.localStorage.getItem(key);

    if (raw === null) {
      return fallback;
    }

    return JSON.parse(raw) as Value;
  } catch {
    return fallback;
  }
}

/**
 * Generiše jedinstveni id.
 */
function createId(): string {
  if (
    typeof crypto !== "undefined" &&
    typeof crypto.randomUUID === "function"
  ) {
    return crypto.randomUUID();
  }

  return Math.random().toString(36).slice(2);
}

const DEFAULT_MELODY = "klasik";
const DEFAULT_SNOOZE_MINUTES = 5;


// ==========          STANJE STOPERICE / TAJMERA          ==========

type StopwatchState = {
  running: boolean;
  startedAt: number | null;
  baseMs: number;
};

type TimerState = {
  running: boolean;
  endsAt: number | null;
  remainingMs: number;
  totalMs: number;
};

type SnoozeState = {
  at: number;
  message: string;
  melody: string;
};


// ==========          VREME PROVIDER          ==========

type VremeProviderProps = {
  children: ReactNode;
};

/**
 * Globalno stanje i engine VREME alata. Vrti sekundni tik koji pali alarme
 * i tajmer nezavisno od toga da li je popover otvoren, perzistuje alarme i
 * tajmer presete, i registruje imperativni API za pozivanje iz drugih delova.
 */
export function VremeProvider({ children }: VremeProviderProps) {
  const [now, setNow] = useState<Date>(() => new Date());

  const [alarms, setAlarms] = useState<Alarm[]>(() =>
    readStored<Alarm[]>(ALARMS_KEY, []),
  );

  const [timerPresets, setTimerPresets] = useState<TimerPreset[]>(() =>
    readStored<TimerPreset[]>(PRESETS_KEY, []),
  );

  const [ringing, setRinging] = useState<Ringing | null>(null);

  const [popover, setPopover] = useState<{
    open: boolean;
    tab: PopoverTab;
  }>({ open: false, tab: "alarm" });

  const [widgets, setWidgets] = useState<Record<VremeTool, WidgetState>>(
    () => {
      const stored = readStored<Partial<Record<VremeTool, WidgetState>>>(
        WIDGETS_KEY,
        {},
      );

      return {
        alarm: { ...DEFAULT_WIDGETS.alarm, ...stored.alarm },
        stopwatch: { ...DEFAULT_WIDGETS.stopwatch, ...stored.stopwatch },
        timer: { ...DEFAULT_WIDGETS.timer, ...stored.timer },
      };
    },
  );

  const [stopwatch, setStopwatch] = useState<StopwatchState>({
    running: false,
    startedAt: null,
    baseMs: 0,
  });

  const [timer, setTimer] = useState<TimerState>({
    running: false,
    endsAt: null,
    remainingMs: 0,
    totalMs: 0,
  });

  const snoozeRef = useRef<SnoozeState | null>(null);
  const ringingRef = useRef<Ringing | null>(null);
  // Ref se osvežava u efektu, ne u telu crtanja (vidi VremeWidgetShell).
  useEffect(() => {
    ringingRef.current = ringing;
  }, [ringing]);

  // ==========          PERZISTENCIJA          ==========

  useEffect(() => {
    window.localStorage.setItem(ALARMS_KEY, JSON.stringify(alarms));
  }, [alarms]);

  useEffect(() => {
    window.localStorage.setItem(
      PRESETS_KEY,
      JSON.stringify(timerPresets),
    );
  }, [timerPresets]);

  useEffect(() => {
    window.localStorage.setItem(WIDGETS_KEY, JSON.stringify(widgets));
  }, [widgets]);

  // ==========          SEKUNDNI TIK          ==========

  useEffect(() => {
    const interval = window.setInterval(() => {
      setNow(new Date());
    }, 1000);

    return () => {
      window.clearInterval(interval);
    };
  }, []);

  // ==========          POKRETANJE ZVONA          ==========

  const startRing = useCallback((next: Ringing) => {
    setRinging(next);
    playMelody(next.melody);
  }, []);

  // ==========          ENGINE (obrada na svaki tik)          ==========

  useEffect(() => {
    // 1) Snooze koji je stigao na red.
    const snooze = snoozeRef.current;

    if (
      snooze !== null &&
      now.getTime() >= snooze.at &&
      ringingRef.current === null
    ) {
      snoozeRef.current = null;
      startRing({
        source: "alarm",
        message: snooze.message,
        melody: snooze.melody,
      });
    }

    // 2) Tajmer istekao.
    if (
      timer.running &&
      timer.endsAt !== null &&
      now.getTime() >= timer.endsAt
    ) {
      setTimer((prev) => ({
        ...prev,
        running: false,
        endsAt: null,
        remainingMs: 0,
      }));

      if (ringingRef.current === null) {
        startRing({
          source: "timer",
          message: "Tajmer je istekao",
          melody: DEFAULT_MELODY,
        });
      }
    }

    // 3) Alarmi koji se poklapaju sa tekućom minutom.
    const key = minuteKey(now);

    setAlarms((previous) => {
      let changed = false;

      const updated = previous.map((alarm) => {
        if (!alarmMatchesNow(alarm, now)) {
          return alarm;
        }

        if (alarm.lastRungMinute === key) {
          return alarm;
        }

        changed = true;

        // Zabeleži okidanje; jednokratni alarm se gasi.
        const rung: Alarm = {
          ...alarm,
          lastRungMinute: key,
          enabled: alarm.repeat.mode === "once" ? false : alarm.enabled,
        };

        if (ringingRef.current === null && snoozeRef.current === null) {
          startRing({
            source: "alarm",
            message: alarm.message || alarm.label || "Alarm",
            melody: alarm.melody,
          });
        }

        return rung;
      });

      return changed ? updated : previous;
    });
  }, [now, timer.running, timer.endsAt, startRing]);

  // ==========          AKCIJE: ALARM          ==========

  const addAlarm = useCallback((input: NewAlarmInput): string => {
    const id = createId();

    const alarm: Alarm = {
      id,
      hour: input.hour,
      minute: input.minute,
      label: input.label ?? "",
      message: input.message ?? "",
      enabled: input.enabled ?? true,
      repeat: input.repeat ?? { mode: "once", days: [] },
      melody: input.melody ?? DEFAULT_MELODY,
      lastRungMinute: null,
    };

    setAlarms((previous) => [...previous, alarm]);

    return id;
  }, []);

  const updateAlarm = useCallback(
    (id: string, patch: Partial<Alarm>) => {
      setAlarms((previous) =>
        previous.map((alarm) =>
          alarm.id === id ? { ...alarm, ...patch } : alarm,
        ),
      );
    },
    [],
  );

  const removeAlarm = useCallback((id: string) => {
    setAlarms((previous) =>
      previous.filter((alarm) => alarm.id !== id),
    );
  }, []);

  const toggleAlarm = useCallback(
    (id: string, enabled?: boolean) => {
      setAlarms((previous) =>
        previous.map((alarm) =>
          alarm.id === id
            ? {
                ...alarm,
                enabled: enabled ?? !alarm.enabled,
                lastRungMinute: null,
              }
            : alarm,
        ),
      );
    },
    [],
  );

  // ==========          AKCIJE: STOPERICA          ==========

  const startStopwatch = useCallback(() => {
    setStopwatch((prev) =>
      prev.running ? prev : { ...prev, running: true, startedAt: Date.now() },
    );
  }, []);

  const pauseStopwatch = useCallback(() => {
    setStopwatch((prev) => {
      if (!prev.running || prev.startedAt === null) {
        return prev;
      }

      return {
        running: false,
        startedAt: null,
        baseMs: prev.baseMs + (Date.now() - prev.startedAt),
      };
    });
  }, []);

  const resetStopwatch = useCallback(() => {
    setStopwatch({ running: false, startedAt: null, baseMs: 0 });
  }, []);

  // ==========          AKCIJE: TAJMER          ==========

  const saveTimerPreset = useCallback((preset: TimerPreset) => {
    if (
      preset.hours === 0 &&
      preset.minutes === 0 &&
      preset.seconds === 0
    ) {
      return;
    }

    setTimerPresets((previous) => {
      const withoutDuplicate = previous.filter(
        (item) =>
          item.hours !== preset.hours ||
          item.minutes !== preset.minutes ||
          item.seconds !== preset.seconds,
      );

      return [preset, ...withoutDuplicate].slice(0, 6);
    });
  }, []);

  const startTimer = useCallback(
    (input: TimerInput) => {
      const hours = input.hours ?? 0;
      const minutes = input.minutes ?? 0;
      const seconds = input.seconds ?? 0;
      const totalMs = (hours * 3600 + minutes * 60 + seconds) * 1000;

      if (totalMs <= 0) {
        return;
      }

      saveTimerPreset({ hours, minutes, seconds });

      setTimer({
        running: true,
        endsAt: Date.now() + totalMs,
        remainingMs: totalMs,
        totalMs,
      });
    },
    [saveTimerPreset],
  );

  const resumeTimer = useCallback(() => {
    setTimer((prev) => {
      if (prev.running || prev.remainingMs <= 0) {
        return prev;
      }

      return {
        ...prev,
        running: true,
        endsAt: Date.now() + prev.remainingMs,
      };
    });
  }, []);

  const pauseTimer = useCallback(() => {
    setTimer((prev) => {
      if (!prev.running || prev.endsAt === null) {
        return prev;
      }

      return {
        ...prev,
        running: false,
        endsAt: null,
        remainingMs: Math.max(0, prev.endsAt - Date.now()),
      };
    });
  }, []);

  const stopTimer = useCallback(() => {
    setTimer({
      running: false,
      endsAt: null,
      remainingMs: 0,
      totalMs: 0,
    });
  }, []);

  const resetTimer = useCallback(() => {
    setTimer((prev) => ({
      ...prev,
      running: false,
      endsAt: null,
      remainingMs: prev.totalMs,
    }));
  }, []);

  // ==========          AKCIJE: POPOVER / WIDGETI          ==========

  const openPopover = useCallback((tab?: PopoverTab) => {
    setPopover((prev) => ({ open: true, tab: tab ?? prev.tab }));
  }, []);

  const closePopover = useCallback(() => {
    setPopover((prev) => ({ ...prev, open: false }));
  }, []);

  const togglePopover = useCallback((tab?: PopoverTab) => {
    setPopover((prev) => ({
      open: !prev.open,
      tab: tab ?? prev.tab,
    }));
  }, []);

  const setPopoverTab = useCallback((tab: PopoverTab) => {
    setPopover((prev) => ({ ...prev, tab }));
  }, []);

  const openWidget = useCallback((tool: VremeTool) => {
    setWidgets((prev) => ({
      ...prev,
      [tool]: { ...prev[tool], open: true },
    }));
  }, []);

  const closeWidget = useCallback((tool: VremeTool) => {
    setWidgets((prev) => ({
      ...prev,
      [tool]: { ...prev[tool], open: false },
    }));
  }, []);

  const moveWidget = useCallback(
    (tool: VremeTool, x: number, y: number) => {
      setWidgets((prev) => ({
        ...prev,
        [tool]: { ...prev[tool], x, y },
      }));
    },
    [],
  );

  // ==========          AKCIJE: ZVONO          ==========

  const dismissRing = useCallback(() => {
    stopMelody();
    setRinging(null);
  }, []);

  const snoozeRing = useCallback(
    (minutes: number = DEFAULT_SNOOZE_MINUTES) => {
      const current = ringingRef.current;

      if (current !== null) {
        snoozeRef.current = {
          at: Date.now() + minutes * 60000,
          message: current.message,
          melody: current.melody,
        };
      }

      stopMelody();
      setRinging(null);
    },
    [],
  );

  // ==========          IMPERATIVNI API          ==========

  const actions = useMemo<VremeActions>(
    () => ({
      addAlarm,
      updateAlarm,
      removeAlarm,
      toggleAlarm,
      startStopwatch,
      pauseStopwatch,
      resetStopwatch,
      startTimer,
      resumeTimer,
      pauseTimer,
      stopTimer,
      resetTimer,
      saveTimerPreset,
      openPopover,
      closePopover,
      openWidget,
      closeWidget,
    }),
    [
      addAlarm,
      updateAlarm,
      removeAlarm,
      toggleAlarm,
      startStopwatch,
      pauseStopwatch,
      resetStopwatch,
      startTimer,
      resumeTimer,
      pauseTimer,
      stopTimer,
      resetTimer,
      saveTimerPreset,
      openPopover,
      closePopover,
      openWidget,
      closeWidget,
    ],
  );

  useEffect(() => {
    bindVremeApi(actions);

    return () => {
      unbindVremeApi(actions);
    };
  }, [actions]);

  // ==========          IZVEDENI PRIKAZ          ==========

  const stopwatchView = useMemo(
    () => ({
      running: stopwatch.running,
      startedAt: stopwatch.startedAt,
      baseMs: stopwatch.baseMs,
      elapsedMs:
        stopwatch.running && stopwatch.startedAt !== null
          ? stopwatch.baseMs + (now.getTime() - stopwatch.startedAt)
          : stopwatch.baseMs,
    }),
    [stopwatch, now],
  );

  const timerView = useMemo(
    () => ({
      running: timer.running,
      totalMs: timer.totalMs,
      remainingMs:
        timer.running && timer.endsAt !== null
          ? Math.max(0, timer.endsAt - now.getTime())
          : timer.remainingMs,
    }),
    [timer, now],
  );

  const value = useMemo<VremeContextValue>(
    () => ({
      ...actions,
      now,
      alarms,
      timerPresets,
      ringing,
      popover,
      widgets,
      stopwatch: stopwatchView,
      timer: timerView,
      togglePopover,
      setPopoverTab,
      moveWidget,
      dismissRing,
      snoozeRing,
    }),
    [
      actions,
      now,
      alarms,
      timerPresets,
      ringing,
      popover,
      widgets,
      stopwatchView,
      timerView,
      togglePopover,
      setPopoverTab,
      moveWidget,
      dismissRing,
      snoozeRing,
    ],
  );

  return (
    <VremeContext.Provider value={value}>
      {children}
    </VremeContext.Provider>
  );
}
