import { useState } from "react";

import type { Alarm, AlarmRepeat } from "../types";
import { WEEKDAY_LABELS } from "../lib/time";
import { MELODIES, previewMelody } from "../lib/audio";
import NumberWheel from "./NumberWheel";


// ==========          PODACI EDITORA          ==========

export type AlarmDraft = {
  hour: number;
  minute: number;
  label: string;
  message: string;
  repeat: AlarmRepeat;
  melody: string;
};

type AlarmEditorProps = {
  initial?: Alarm;
  onSave: (draft: AlarmDraft) => void;
  onCancel: () => void;
};

/** Redosled dana za prikaz: ponedeljak prvi. */
const DAY_ORDER = [1, 2, 3, 4, 5, 6, 0];


// ==========          EDITOR ALARMA          ==========

/**
 * Uređivanje alarma: dva (ili više) brojčanika za vreme, GOTOVO za brzo
 * snimanje i DODATNO za proširena podešavanja (melodija, ponavljanje, oznaka).
 */
function AlarmEditor({ initial, onSave, onCancel }: AlarmEditorProps) {
  const [hour, setHour] = useState(initial?.hour ?? 7);
  const [minute, setMinute] = useState(initial?.minute ?? 0);
  const [label, setLabel] = useState(initial?.label ?? "");
  const [message, setMessage] = useState(initial?.message ?? "");
  const [melody, setMelody] = useState(initial?.melody ?? MELODIES[0].id);

  const [everyday, setEveryday] = useState(
    initial?.repeat.mode === "daily",
  );
  const [days, setDays] = useState<number[]>(
    initial?.repeat.mode === "custom" ? initial.repeat.days : [],
  );

  const [showAdvanced, setShowAdvanced] = useState(
    initial !== undefined,
  );

  const deriveRepeat = (): AlarmRepeat => {
    if (everyday) {
      return { mode: "daily", days: [] };
    }

    if (days.length > 0) {
      return { mode: "custom", days: [...days].sort((a, b) => a - b) };
    }

    return { mode: "once", days: [] };
  };

  const save = () => {
    onSave({
      hour,
      minute,
      label: label.trim(),
      message: message.trim(),
      repeat: deriveRepeat(),
      melody,
    });
  };

  const toggleDay = (day: number) => {
    setEveryday(false);
    setDays((previous) =>
      previous.includes(day)
        ? previous.filter((item) => item !== day)
        : [...previous, day],
    );
  };

  return (
    <div className="alarm-editor">
      {/* ==========          BROJČANICI VREMENA          ========== */}

      <div className="alarm-editor-wheels">
        <div className="alarm-editor-wheel-column">
          <span className="alarm-editor-wheel-label">SAT</span>
          <NumberWheel
            ariaLabel="Sat"
            max={23}
            min={0}
            onChange={setHour}
            value={hour}
          />
        </div>

        <span className="alarm-editor-wheel-colon">:</span>

        <div className="alarm-editor-wheel-column">
          <span className="alarm-editor-wheel-label">MINUT</span>
          <NumberWheel
            ariaLabel="Minut"
            max={59}
            min={0}
            onChange={setMinute}
            value={minute}
          />
        </div>
      </div>

      {/* ==========          PROŠIRENO          ========== */}

      {showAdvanced && (
        <div className="alarm-editor-advanced">
          <label className="alarm-editor-field">
            <span>Melodija</span>
            <select
              onChange={(event) => {
                setMelody(event.target.value);
                previewMelody(event.target.value);
              }}
              value={melody}
            >
              {MELODIES.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>

          <div className="alarm-editor-field">
            <span>Ponavljanje</span>

            <div className="alarm-editor-repeat">
              <button
                aria-pressed={everyday}
                className={`alarm-day-chip everyday ${
                  everyday ? "is-active" : ""
                }`}
                onClick={() => {
                  setEveryday((prev) => !prev);
                  setDays([]);
                }}
                type="button"
              >
                Svaki dan
              </button>

              {DAY_ORDER.map((day) => (
                <button
                  aria-pressed={days.includes(day)}
                  className={`alarm-day-chip ${
                    days.includes(day) ? "is-active" : ""
                  }`}
                  key={day}
                  onClick={() => toggleDay(day)}
                  type="button"
                >
                  {WEEKDAY_LABELS[day]}
                </button>
              ))}
            </div>
          </div>

          <label className="alarm-editor-field">
            <span>Oznaka</span>
            <input
              maxLength={40}
              onChange={(event) => setLabel(event.target.value)}
              placeholder="npr. Buđenje"
              type="text"
              value={label}
            />
          </label>

          <label className="alarm-editor-field">
            <span>Poruka</span>
            <input
              maxLength={80}
              onChange={(event) => setMessage(event.target.value)}
              placeholder="Poruka pri aktivaciji"
              type="text"
              value={message}
            />
          </label>
        </div>
      )}

      {/* ==========          DUGMAD          ========== */}

      <div className="alarm-editor-actions">
        <button
          className="alarm-editor-cancel"
          onClick={onCancel}
          type="button"
        >
          Otkaži
        </button>

        {showAdvanced ? (
          <button
            className="alarm-editor-primary"
            onClick={save}
            type="button"
          >
            OK
          </button>
        ) : (
          <>
            <button
              className="alarm-editor-secondary"
              onClick={() => setShowAdvanced(true)}
              type="button"
            >
              DODATNO
            </button>

            <button
              className="alarm-editor-primary"
              onClick={save}
              type="button"
            >
              GOTOVO
            </button>
          </>
        )}
      </div>
    </div>
  );
}

export default AlarmEditor;
