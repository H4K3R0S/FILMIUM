import { CloudSun } from "lucide-react";


// ==========          TAB PROGNOZA          ==========

/**
 * Placeholder za vremensku prognozu. Kasnije se povezuje sa stvarnim
 * servisom prognoze (lokacija + izvor podataka).
 */
function ForecastTab() {
  return (
    <div className="forecast-tab">
      <CloudSun size={54} strokeWidth={1.4} />

      <p className="forecast-tab-title">Vremenska prognoza</p>

      <p className="forecast-tab-note">
        Prognoza stiže kada povežemo servis vremena i lokaciju.
      </p>
    </div>
  );
}

export default ForecastTab;
