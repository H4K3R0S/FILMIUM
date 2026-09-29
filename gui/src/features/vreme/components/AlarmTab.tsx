import { useMemo, useState } from "react";
import { Plus } from "lucide-react";

import type { AlarmRepeat } from "../types";
import { useVreme } from "../hooks/useVreme";
import {
  formatCountdown,
  formatHourMinute,
  nextEnabledAlarm,
  WEEKDAY_LABELS,
} from "../lib/time";
import AlarmEditor, { type AlarmDraft } from "./AlarmEditor";


// ==========          POMOĆNI PRIKAZ          ==========

/** Redosled dana za sažetak: ponedeljak prvi. */
const DAY_ORDER = [1, 2, 3, 4, 5, 6, 0];

/**
 * Kratak opis ponavljanja za karticu alarma.
 */
function describeRepeat(repeat: AlarmRepeat): string {
  if (repeat.mode === "daily") {
    return "Svaki dan";
  }

  if (repeat.mode === "custom" && repeat.days.length > 0) {
    return DAY_ORDER.filter((day) => repeat.days.includes(day))
      .map((day) => WEEKDAY_LABELS[day])
      .join(" ");
  }

  return "Jednom";
}

/** Koliko alarma je vidljivo pre „prikaži još". */
const VISIBLE_LIMIT = 5;


// ==========          TAB ALARM          ==========

/**
 * Prikazuje listu alarma, odbrojavanje do prvog i editor za kreiranje/izmenu.
 */
function AlarmTab() {
  const {
    now,
    alarms,
    addAlarm,
    updateAlarm,
    removeAlarm,
    toggleAlarm,
  } = useVreme();

  const [editorMode, setEditorMode] = useState<
    "closed" | "create" | { editId: string }
  >("closed");

  const [showAll, setShowAll] = useState(false);

  const sortedAlarms = useMemo(
    () =>
      [...alarms].sort(
        (a, b) => a.hour * 60 + a.minute - (b.hour * 60 + b.minute),
      ),
    [alarms],
  );

  const upcoming = useMemo(
    () => nextEnabledAlarm(alarms, now),
    [alarms, now],
  );

  const visibleAlarms = showAll
    ? sortedAlarms
    : sortedAlarms.slice(0, VISIBLE_LIMIT);

  const editingAlarm =
    typeof editorMode === "object"
      ? alarms.find((alarm) => alarm.id === editorMode.editId)
      : undefined;

  const handleSave = (draft: AlarmDraft) => {
    if (typeof editorMode === "object" && editingAlarm) {
      updateAlarm(editingAlarm.id, {
        hour: draft.hour,
        minute: draft.minute,
        label: draft.label,
        message: draft.message,
        repeat: draft.repeat,
        melody: draft.melody,
        lastRungMinute: null,
      });
    } else {
      addAlarm({
        hour: draft.hour,
        minute: draft.minute,
        label: draft.label,
        message: draft.message,
        repeat: draft.repeat,
        melody: draft.melody,
      });
    }

    setEditorMode("closed");
  };

  return (
    <div className="alarm-tab">
      {/* ==========          ODBROJAVANJE          ========== */}

      <div className="alarm-tab-header">
        {upcoming ? (
          <>
            <span className="alarm-tab-header-label">
              Sledeći alarm
            </span>
            <strong>{formatCountdown(upcoming.ms)}</strong>
            <span className="alarm-tab-header-time">
              {formatHourMinute(
                upcoming.alarm.hour,
                upcoming.alarm.minute,
              )}
            </span>
          </>
        ) : (
          <span className="alarm-tab-header-label">
            Nema aktivnih alarma
          </span>
        )}
      </div>

      {/* ==========          LISTA ALARMA          ========== */}

      <div className="alarm-list">
        {visibleAlarms.length === 0 && editorMode === "closed" && (
          <p className="alarm-list-empty">
            Dodaj prvi alarm dugmetom +.
          </p>
        )}

        {visibleAlarms.map((alarm) => {
          const isEditing =
            typeof editorMode === "object" &&
            editorMode.editId === alarm.id;

          return (
            <div
              className={`alarm-card ${alarm.enabled ? "" : "is-off"}`}
              key={alarm.id}
            >
              <div className="alarm-card-row">
                <button
                  className="alarm-card-main"
                  onClick={() =>
                    setEditorMode(
                      isEditing ? "closed" : { editId: alarm.id },
                    )
                  }
                  type="button"
                >
                  <span className="alarm-card-time">
                    {formatHourMinute(alarm.hour, alarm.minute)}
                  </span>

                  <span className="alarm-card-meta">
                    {alarm.label && (
                      <span className="alarm-card-label">
                        {alarm.label}
                      </span>
                    )}
                    <span className="alarm-card-repeat">
                      {describeRepeat(alarm.repeat)}
                    </span>
                  </span>
                </button>

                <button
                  aria-label={
                    alarm.enabled
                      ? "Isključi alarm"
                      : "Uključi alarm"
                  }
                  aria-pressed={alarm.enabled}
                  className={`alarm-toggle ${
                    alarm.enabled ? "is-on" : ""
                  }`}
                  onClick={() => toggleAlarm(alarm.id)}
                  type="button"
                >
                  <span className="alarm-toggle-knob" />
                </button>
              </div>

              {isEditing && editingAlarm && (
                <AlarmEditor
                  initial={editingAlarm}
                  onCancel={() => setEditorMode("closed")}
                  onSave={handleSave}
                />
              )}

              {isEditing && editingAlarm && (
                <button
                  className="alarm-card-delete"
                  onClick={() => {
                    removeAlarm(editingAlarm.id);
                    setEditorMode("closed");
                  }}
                  type="button"
                >
                  Obriši alarm
                </button>
              )}
            </div>
          );
        })}

        {!showAll && sortedAlarms.length > VISIBLE_LIMIT && (
          <button
            className="alarm-list-more"
            onClick={() => setShowAll(true)}
            type="button"
          >
            Prikaži još ({sortedAlarms.length - VISIBLE_LIMIT})
          </button>
        )}

        {showAll && sortedAlarms.length > VISIBLE_LIMIT && (
          <button
            className="alarm-list-more"
            onClick={() => setShowAll(false)}
            type="button"
          >
            Prikaži manje
          </button>
        )}
      </div>

      {/* ==========          KREIRANJE          ========== */}

      {editorMode === "create" && (
        <div className="alarm-create">
          <AlarmEditor
            onCancel={() => setEditorMode("closed")}
            onSave={handleSave}
          />
        </div>
      )}

      <button
        aria-label="Dodaj alarm"
        className="alarm-add-button"
        onClick={() => setEditorMode("create")}
        type="button"
      >
        <Plus size={26} strokeWidth={2.4} />
      </button>
    </div>
  );
}

export default AlarmTab;
