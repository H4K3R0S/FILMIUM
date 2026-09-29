import {
  useBackgroundControl,
  type ThemeBackground,
} from "../../lib/backgroundControl";
import { useAmbientSettings } from "../theme/ambientEffect";
import "./themePanel.css";


// ==========          PODEŠAVANJA: TEMA I POZADINA          ==========
/*
 * Kontrola izgleda prozora: pozadinska slika (paljenje/gašenje, izbor kad ih
 * ima više) i ambijentalni efekat „Povezane tačke". Sve se primenjuje odmah i
 * pamti u localStorage ovog uređaja. Samostalan stil (themePanel.css) — isti
 * panel radi u svakom domenu i u Workplace-u bez oslanjanja na njihov CSS.
 */

type ThemePanelProps = {
  /** Ponuđene pozadine domena; prazno = domen nema svoju sliku (sekcija se krije). */
  backgrounds: ThemeBackground[];
  subtitle?: string;
};

function Switch({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  label: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      className={`tp-switch ${checked ? "on" : ""}`}
      onClick={() => onChange(!checked)}
    >
      <span aria-hidden="true" className="tp-switch-knob" />
    </button>
  );
}

function ThemePanel({ backgrounds, subtitle }: ThemePanelProps) {
  const { settings, setAll, setKeepImage } = useAmbientSettings();
  const bg = useBackgroundControl(backgrounds);
  const dots = settings.all;

  return (
    <section className="tp-panel">
      <header className="tp-head">
        <h2 className="tp-title">Tema i pozadina</h2>
        <p className="tp-sub">
          {subtitle ??
            "Izbor pozadine i ambijentalnog efekta. Menja se odmah i pamti na ovom uređaju."}
        </p>
      </header>

      {backgrounds.length > 0 && (
        <div className="tp-group">
          <p className="tp-group-title">Pozadinska slika</p>
          <div className="tp-row">
            <span className="tp-row-label">Prikaži pozadinsku sliku</span>
            <Switch
              checked={!bg.hidden}
              onChange={(next) => bg.setHidden(!next)}
              label="Prikaži pozadinsku sliku"
            />
          </div>
          {backgrounds.length > 1 && !bg.hidden && (
            <div className="tp-swatches">
              {backgrounds.map((b) => (
                <button
                  key={b.id}
                  type="button"
                  title={b.label}
                  className={`tp-swatch ${bg.choice === b.url ? "is-active" : ""}`}
                  style={{ backgroundImage: `url("${b.url}")` }}
                  onClick={() => bg.setChoice(b.url)}
                >
                  <span className="tp-swatch-label">{b.label}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="tp-group">
        <p className="tp-group-title">Ambijentalni efekat — Povezane tačke</p>
        <div className="tp-row">
          <span className="tp-row-label">Uključi efekat povezanih tačaka</span>
          <Switch
            checked={dots}
            onChange={setAll}
            label="Efekat povezanih tačaka"
          />
        </div>
        <div className="tp-row">
          <span className="tp-row-label">
            Zadrži pozadinsku sliku ispod tačaka
          </span>
          <Switch
            checked={settings.keepImage}
            onChange={setKeepImage}
            label="Pozadinska slika ispod tačaka"
          />
        </div>
        <p className="tp-note">
          Kad je efekat uključen bez ove opcije, tačke stoje na crnoj podlozi pa
          se pozadinska slika ne vidi. Isključi efekat da bi se videla slika.
        </p>
      </div>
    </section>
  );
}

export default ThemePanel;
