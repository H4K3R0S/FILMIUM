/**
 * Prekidač tipa sadržaja: FILM / ANIME / DOMAĆE. Aktivna opcija je zelena.
 * - FILM (regular): standardno rutiranje (Filmovi/Serije po žanru).
 * - ANIME (animated): <koren>/Animirano/(Filmovi|Serije).
 * - DOMAĆE (domestic): <koren>/Domaci/(Filmovi|Serije).
 */

export type FilmiumContentMode = "regular" | "animated" | "domestic";

const OPTIONS: [FilmiumContentMode, string][] = [
  ["regular", "FILM"],
  ["animated", "ANIME"],
  ["domestic", "DOMAĆE"],
];

export default function ContentModeToggle({
  mode,
  onChange,
}: {
  mode: FilmiumContentMode;
  onChange: (mode: FilmiumContentMode) => void;
}) {
  return (
    <div
      aria-label="Tip sadržaja za čuvanje"
      className="filmium-content-mode-toggle"
      role="group"
    >
      {OPTIONS.map(([value, label]) => (
        <button
          aria-pressed={mode === value}
          className={`filmium-content-mode-option${
            mode === value ? " active" : ""
          }`}
          key={value}
          onClick={() => onChange(value)}
          type="button"
        >
          {label}
        </button>
      ))}
    </div>
  );
}
