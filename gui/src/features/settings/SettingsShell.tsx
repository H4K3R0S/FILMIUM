import { useState, type ComponentType, type ReactNode } from "react";

import "../../styles/settings.css";


// ==========          LJUSKA STRANICE PODEŠAVANJA          ==========
// Isti raspored za CORE i za domene: naslov, kategorije sa leve strane, sadržaj
// desno. Jedna ljuska umesto dve — inače se dva ekrana podešavanja vremenom
// raziđu u izgledu i u ponašanju.

export type SettingsCategory = {
  id: string;
  label: string;
  icon: ComponentType<{ size?: number }>;
  /** Sadržaj kategorije. Funkcija, da se panel ne montira dok nije izabran. */
  render: () => ReactNode;
};

type SettingsShellProps = {
  eyebrow: string;
  title: string;
  categories: SettingsCategory[];
  /** Kratko objašnjenje ispod naslova (npr. šta ovaj nivo podešavanja pokriva). */
  note?: string;
};

function SettingsShell({ eyebrow, title, categories, note }: SettingsShellProps) {
  const [aktivna, setAktivna] = useState(categories[0]?.id ?? "");

  const izabrana =
    categories.find((k) => k.id === aktivna) ?? categories[0];

  return (
    <div className="cset">
      <header className="cset-head">
        <p className="cset-eyebrow">{eyebrow}</p>
        <h1 className="cset-title">{title}</h1>
        {note !== undefined && <p className="cset-note">{note}</p>}
      </header>

      <div className="cset-body">
        <nav className="cset-nav" aria-label="Kategorije podešavanja">
          {categories.map((kategorija) => {
            const Icon = kategorija.icon;
            return (
              <button
                key={kategorija.id}
                type="button"
                className={`cset-nav-item ${
                  kategorija.id === aktivna ? "is-active" : ""
                }`}
                onClick={() => setAktivna(kategorija.id)}
              >
                <Icon size={15} />
                {kategorija.label}
              </button>
            );
          })}
        </nav>

        <div className="cset-content">{izabrana?.render()}</div>
      </div>
    </div>
  );
}

export default SettingsShell;
