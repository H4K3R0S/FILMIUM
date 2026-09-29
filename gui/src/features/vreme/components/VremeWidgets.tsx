import { useVreme } from "../hooks/useVreme";
import AlarmWidget from "./AlarmWidget";
import StopwatchWidget from "./StopwatchWidget";
import TimerWidget from "./TimerWidget";


// ==========          KONTEJNER LEBDEĆIH WIDGETA          ==========

/**
 * Renderuje otvorene VREME widgete na app rootu. Svaki radi nezavisno.
 */
function VremeWidgets() {
  const { widgets } = useVreme();

  return (
    <>
      {widgets.alarm.open && <AlarmWidget />}
      {widgets.stopwatch.open && <StopwatchWidget />}
      {widgets.timer.open && <TimerWidget />}
    </>
  );
}

export default VremeWidgets;
