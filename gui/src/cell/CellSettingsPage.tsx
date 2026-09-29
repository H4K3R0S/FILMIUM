import { useEffect, useState, type ReactNode } from "react";
import { Bot, Clock, Download, FileCode, Mic, Palette, Sparkles, UserRound } from "lucide-react";

import FilmiumTorrentSettingsPanel from "../features/filmium/components/torrents/FilmiumTorrentSettingsPanel";
import SettingsShell, { type SettingsCategory } from "../features/settings/SettingsShell";
import ThemePanel from "../features/settings/ThemePanel";
import VoicePanel from "../features/settings/VoicePanel";
import { useAmbientSettings } from "../features/theme/ambientEffect";
import { clockSettingKey, defaultClockVisible } from "../lib/domainTheme";
import { useCoreSetting } from "../lib/useCoreSetting";
import {
  getCellAiConfig,
  listCellAtoms,
  listCellPersonas,
  saveCellAiConfig,
  saveCellAtom,
  saveCellPersona,
  type CellAiConfig,
  type CellAtom,
  type CellPersona,
  listCellJobs,
  runCellJob,
  type CellJob,
} from "./cellApi";


// ==========          FILMIUM ĆELIJA — PODEŠAVANJA          ==========
// Zamena za CORE-ov FilmiumSettingsPage. Ćelija ne nosi API ključeve, izbor
// modela ni CORE chat podešavanja (spec §5.1, §15.1): Kurator radi nad lokalnom
// Ollamom čiji su model i adresa upisani u cell.json.

function ToggleRow({
  title,
  on,
  onToggle,
  children,
}: {
  title: string;
  on: boolean;
  onToggle: () => void;
  children: ReactNode;
}) {
  return (
    <div className="core-settings-row">
      <div className="core-settings-copy">
        <strong>{title}</strong>
        <span>{children}</span>
      </div>
      <button
        aria-checked={on}
        aria-label={title}
        className={`core-settings-toggle ${on ? "on" : ""}`}
        onClick={onToggle}
        role="switch"
        type="button"
      >
        <span aria-hidden="true" className="core-settings-toggle-knob" />
      </button>
    </div>
  );
}

function KuratorPanel() {
  const [config, setConfig] = useState<CellAiConfig | null>(null);
  const [model, setModel] = useState("");
  const [adresa, setAdresa] = useState("");
  const [poruka, setPoruka] = useState<string | null>(null);

  useEffect(() => {
    getCellAiConfig()
      .then((cfg) => {
        setConfig(cfg);
        setModel(cfg.curator_model ?? "");
        setAdresa(cfg.endpoint);
      })
      .catch(() => setPoruka("Podešavanja nisu dostupna."));
  }, []);

  async function sacuvaj(): Promise<void> {
    try {
      const cfg = await saveCellAiConfig(model.trim() || null, adresa.trim() || null);
      setConfig(cfg);
      setModel(cfg.curator_model ?? "");
      setAdresa(cfg.endpoint);
      setPoruka("Sačuvano u cell.json. Ponovo pokreni ćeliju da bi se primenilo.");
    } catch {
      setPoruka("Čuvanje nije uspelo.");
    }
  }

  // Ponuđeni modeli: instalirani (Ollama) + trenutni ako nije na listi.
  const modeli = config
    ? Array.from(new Set([...config.available_models, ...(model ? [model] : [])]))
    : [];

  return (
    <section className="cset-panel">
      <header className="cset-panel-head">
        <div>
          <h2 className="cset-panel-title">Kurator</h2>
          <p className="cset-panel-sub">
            Kurator radi nad lokalnom Ollamom. Izaberi model i adresu; upisuje se
            u cell.json i primenjuje po ponovnom pokretanju ćelije.
          </p>
        </div>
      </header>
      {config && (
        <div className="cset-field-group">
          <label className="cset-field">
            <span>Model</span>
            {modeli.length > 0 ? (
              <select value={model} onChange={(event) => setModel(event.target.value)}>
                <option value="">— nije izabran —</option>
                {modeli.map((ime) => (
                  <option key={ime} value={ime}>
                    {ime}
                  </option>
                ))}
              </select>
            ) : (
              <input
                onChange={(event) => setModel(event.target.value)}
                placeholder="npr. qwen2.5"
                value={model}
              />
            )}
            {config.available_models.length === 0 && (
              <small>Ollama nije dostupna na datoj adresi — upiši ime modela ručno.</small>
            )}
          </label>
          <label className="cset-field">
            <span>Ollama adresa</span>
            <input
              onChange={(event) => setAdresa(event.target.value)}
              placeholder={config.default_endpoint}
              value={adresa}
            />
            <small>Prazno = podrazumevano ({config.default_endpoint}).</small>
          </label>
          <button onClick={() => void sacuvaj()} type="button">
            Sačuvaj
          </button>
        </div>
      )}
      {poruka && <p>{poruka}</p>}
    </section>
  );
}

function PersonaEditor() {
  const [persona, setPersona] = useState<CellPersona | null>(null);
  const [tekst, setTekst] = useState("");
  const [poruka, setPoruka] = useState<string | null>(null);

  useEffect(() => {
    listCellPersonas()
      .then((lista) => {
        const prva = lista[0] ?? null;
        setPersona(prva);
        setTekst(prva?.markdown ?? "");
      })
      .catch(() => setPoruka("Persone nisu dostupne."));
  }, []);

  async function sacuvaj(): Promise<void> {
    if (!persona) {
      return;
    }
    try {
      const nova = await saveCellPersona(persona.id, tekst);
      setPersona(nova);
      setPoruka("Sačuvano. Važi od sledeće poruke.");
    } catch {
      setPoruka("Čuvanje nije uspelo.");
    }
  }

  return (
    <section className="cset-panel">
      <header className="cset-panel-head">
        <div>
          <h2 className="cset-panel-title">Persona</h2>
          <p className="cset-panel-sub">
            Sistemski prompt Kuratora. Prvi naslov (# ...) je naziv profila.
          </p>
        </div>
      </header>
      <textarea
        aria-label="Tekst persone"
        onChange={(event) => setTekst(event.target.value)}
        rows={14}
        value={tekst}
      />
      <button onClick={() => void sacuvaj()} type="button">
        Sačuvaj
      </button>
      {poruka && <p>{poruka}</p>}
    </section>
  );
}

function AtomiEditor() {
  const [atomi, setAtomi] = useState<CellAtom[]>([]);
  const [izabran, setIzabran] = useState<string | null>(null);
  const [tekst, setTekst] = useState("");
  const [poruka, setPoruka] = useState<string | null>(null);

  useEffect(() => {
    listCellAtoms()
      .then((lista) => {
        setAtomi(lista);
        const prvi = lista[0] ?? null;
        setIzabran(prvi?.path ?? null);
        setTekst(prvi?.content ?? "");
      })
      .catch(() => setPoruka("Atomi nisu dostupni."));
  }, []);

  function izaberi(path: string): void {
    const atom = atomi.find((a) => a.path === path) ?? null;
    setIzabran(atom?.path ?? null);
    setTekst(atom?.content ?? "");
    setPoruka(null);
  }

  async function sacuvaj(): Promise<void> {
    if (!izabran) {
      return;
    }
    try {
      const nov = await saveCellAtom(izabran, tekst);
      setAtomi((prethodni) => prethodni.map((a) => (a.path === nov.path ? nov : a)));
      setPoruka("Sačuvano. Važi od sledeće komande Kuratoru.");
    } catch {
      setPoruka("Čuvanje nije uspelo (prazan tekst ili nedozvoljena putanja).");
    }
  }

  return (
    <section className="cset-panel">
      <header className="cset-panel-head">
        <div>
          <h2 className="cset-panel-title">Atomi</h2>
          <p className="cset-panel-sub">
            Uputstva i komande Kuratora — persona, alati (pretraga, plejer,
            izmena) i katalog komandi. Uredi i sačuvaj po fajlu.
          </p>
        </div>
      </header>
      {atomi.length > 0 && (
        <label className="cset-field">
          <span>Fajl</span>
          <select value={izabran ?? ""} onChange={(event) => izaberi(event.target.value)}>
            {atomi.map((a) => (
              <option key={a.path} value={a.path}>
                {a.path}
              </option>
            ))}
          </select>
        </label>
      )}
      <textarea
        aria-label="Sadržaj atoma"
        onChange={(event) => setTekst(event.target.value)}
        rows={16}
        value={tekst}
      />
      <button disabled={!izabran} onClick={() => void sacuvaj()} type="button">
        Sačuvaj
      </button>
      {poruka && <p>{poruka}</p>}
    </section>
  );
}

function PosloviPanel() {
  const [jobs, setJobs] = useState<CellJob[]>([]);
  const [poruka, setPoruka] = useState<string | null>(null);

  const ucitaj = () => {
    listCellJobs()
      .then(setJobs)
      .catch(() => setPoruka("Ne mogu da učitam poslove."));
  };
  useEffect(() => {
    ucitaj();
  }, []);

  const pokreni = async (id: string) => {
    setPoruka(`Pokrećem „${id}"…`);
    try {
      await runCellJob(id);
      setPoruka(`Pokrenuto: ${id} (radi u pozadini).`);
      window.setTimeout(ucitaj, 1000);
    } catch {
      setPoruka(`Greška pri pokretanju: ${id}`);
    }
  };

  return (
    <section className="cset-panel">
      <div className="cset-content">
        <h2 className="cset-panel-title">Poslovi (Cron)</h2>
        <p className="cset-eyebrow">
          Registrovani pozadinski poslovi ćelije — pokreni jednokratno.
        </p>
        {poruka && <p className="cset-item-note">{poruka}</p>}
        <div className="cset-list">
          {jobs.length === 0 && (
            <p className="cset-empty">Nema registrovanih poslova.</p>
          )}
          {jobs.map((j) => (
            <div className="cset-item" key={j.id}>
              <div className="cset-item-main">
                <p className="cset-item-title">{j.id}</p>
                <p className="cset-item-note">{j.opis ?? ""}</p>
                <p className="cset-item-meta">
                  {(j.raspored ?? "on-demand") + " · status: " + (j.status ?? "idle")}
                </p>
              </div>
              <div className="cset-item-actions">
                <button
                  className="cset-ghost"
                  onClick={() => pokreni(j.id)}
                  type="button"
                >
                  Pokreni
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}


function CellSettingsPage() {
  const [showPageTitle, setShowPageTitle] = useCoreSetting("core.filmium.showPageTitle", false);
  const [clockVisible, setClockVisible] = useCoreSetting(
    clockSettingKey("filmium"),
    defaultClockVisible("filmium"),
  );
  const { settings: ambient, setDomain: setAmbientDomain } = useAmbientSettings();
  const [introAnimation, setIntroAnimation] = useCoreSetting("core.filmium.introAnimation", true);

  const kategorije: SettingsCategory[] = [
    {
      id: "tema",
      label: "Tema",
      icon: Palette,
      render: () => (
        <ThemePanel
          backgrounds={[]}
          subtitle="Ambijentalni efekat „Povezane tačke“ za FILMIUM. Menja se odmah i pamti na ovom uređaju."
        />
      ),
    },
    { id: "kurator", label: "Kurator", icon: Bot, render: () => <KuratorPanel /> },
    { id: "glas", label: "Glas", icon: Mic, render: () => <VoicePanel /> },
    { id: "atomi", label: "Atomi", icon: FileCode, render: () => <AtomiEditor /> },
    { id: "poslovi", label: "Poslovi", icon: Clock, render: () => <PosloviPanel /> },
    { id: "persona", label: "Persona", icon: UserRound, render: () => <PersonaEditor /> },
    {
      id: "prikaz",
      label: "Prikaz",
      icon: Sparkles,
      render: () => (
        <section className="cset-panel">
          <header className="cset-panel-head">
            <div>
              <h2 className="cset-panel-title">Prikaz</h2>
              <p className="cset-panel-sub">Naslovi, sat, pozadinski efekat i startup animacija.</p>
            </div>
          </header>
          <ToggleRow
            title="Naslov programa"
            on={showPageTitle}
            onToggle={() => setShowPageTitle(!showPageTitle)}
          >
            Prikaži naslov trenutnog prikaza iznad kataloga.
          </ToggleRow>
          <ToggleRow
            title="Sat"
            on={clockVisible}
            onToggle={() => setClockVisible(!clockVisible)}
          >
            {clockVisible ? "Sat je prikazan na vrhu." : "Sat je sakriven."}
          </ToggleRow>
          <ToggleRow
            title="Pozadinski efekat"
            on={ambient.all || ambient.domains.filmium}
            onToggle={() => setAmbientDomain("filmium", !ambient.domains.filmium)}
          >
            Povezane tačke i glow spotovi u boji FILMIUM-a.
          </ToggleRow>
          <ToggleRow
            title="Startup animacija"
            on={introAnimation}
            onToggle={() => setIntroAnimation(!introAnimation)}
          >
            {introAnimation
              ? "Paljenje FILMIUM ekrana se prikazuje samo pri pokretanju aplikacije (ne pri povratku na Home)."
              : "Paljenje je isključeno — ekran se prikazuje odmah."}
          </ToggleRow>
        </section>
      ),
    },
    { id: "torrenti", label: "Torrenti", icon: Download, render: () => <FilmiumTorrentSettingsPanel /> },
  ];

  return (
    <SettingsShell
      eyebrow="FILMIUM Ćelija"
      title="FILMIUM — Podešavanja"
      note="Podešavanja samostalne FILMIUM ćelije. Lokalni model, adresa i atomi Kuratora uređuju se ovde; CORE API ključevi ostaju u CORE-u."
      categories={kategorije}
    />
  );
}

export default CellSettingsPage;
