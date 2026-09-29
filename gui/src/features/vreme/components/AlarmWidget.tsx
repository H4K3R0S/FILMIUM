import { AlarmClock } from "lucide-react";

import { useVreme } from "../hooks/useVreme";
import {
  formatCountdown,
  formatHourMinute,
  nextEnabledAlarm,
} from "../lib/time";
import VremeWidgetShell from "./VremeWidgetShell";


// ==========          ALARM WIDGET          ==========

/**
 * Minimalan lebdeći prikaz sledećeg alarma i odbrojavanja do njega.
 */
function AlarmWidget() {
  const { alarms, now } = useVreme();
  const next = nextEnabledAlarm(alarms, now);

  return (
    <VremeWidgetShell
      icon={<AlarmClock size={14} strokeWidth={2} />}
      title="Alarm"
      tool="alarm"
    >
      {next ? (
        <div className="widget-alarm">
          <span className="widget-alarm-time">
            {formatHourMinute(next.alarm.hour, next.alarm.minute)}
          </span>
          <span className="widget-alarm-countdown">
            {formatCountdown(next.ms)}
          </span>
        </div>
      ) : (
        <p className="widget-alarm-empty">Nema aktivnih alarma</p>
      )}
    </VremeWidgetShell>
  );
}

export default AlarmWidget;
