import { AlarmClock, BellOff, Clock } from "lucide-react";

import { useVreme } from "../hooks/useVreme";
import { formatHourMinute } from "../lib/time";


// ==========          OVERLAY AKTIVACIJE          ==========

/**
 * Prikaz preko celog ekrana kada alarm ili tajmer zazvoni. Nudi odlaganje
 * (snooze) i gašenje.
 */
function AlarmRingOverlay() {
  const { ringing, now, dismissRing, snoozeRing } = useVreme();

  if (ringing === null) {
    return null;
  }

  const isTimer = ringing.source === "timer";

  return (
    <div className="alarm-ring-overlay" role="alertdialog">
      <div className="alarm-ring-card">
        <div className="alarm-ring-icon">
          {isTimer ? (
            <Clock size={48} strokeWidth={1.6} />
          ) : (
            <AlarmClock size={48} strokeWidth={1.6} />
          )}
        </div>

        <span className="alarm-ring-time">
          {formatHourMinute(now.getHours(), now.getMinutes())}
        </span>

        <p className="alarm-ring-message">{ringing.message}</p>

        <div className="alarm-ring-actions">
          {!isTimer && (
            <button
              className="alarm-ring-snooze"
              onClick={() => snoozeRing()}
              type="button"
            >
              Odloži 5 min
            </button>
          )}

          <button
            className="alarm-ring-dismiss"
            onClick={dismissRing}
            type="button"
          >
            <BellOff size={18} strokeWidth={2} />
            Ugasi
          </button>
        </div>
      </div>
    </div>
  );
}

export default AlarmRingOverlay;
