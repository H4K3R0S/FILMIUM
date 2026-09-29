import { useEffect, useState } from "react";

import { Plus, X } from "lucide-react";

import {
  getTorrentHealth,
  getTorrentSettings,
  saveTorrentSettings,
} from "../../../../services/filmiumTorrentsApi";

import type {
  TorrentHealth,
  TorrentSettings,
} from "../../../../types/filmiumTorrents";


// ==========          PODEŠAVANJA TORRENT MODULA          ==========

/**
 * Četiri grupe: veza sa qBittorrent-om, putanje, ograničenja i ponašanje,
 * plus filter ekstenzija koje su unapred odštiklirane u pickeru.
 *
 * Lozinka se nikad ne čita nazad sa servera — prazno polje znači „ne diraj".
 */
function FilmiumTorrentSettingsPanel() {
  const [settings, setSettings] = useState<TorrentSettings | null>(null);
  const [password, setPassword] = useState("");
  const [health, setHealth] = useState<TorrentHealth | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  // Brojčana polja se drže kao tekst dok korisnik kuca, da prazno polje ne
  // upiše 0 u stanje (i time tiho u zahtev). Parsiraju se i validiraju tek
  // pri čuvanju.
  const [portText, setPortText] = useState("");

  // Nova putanja u polju „dodaj folder"; u podešavanja ulazi tek na „Dodaj".
  const [folderDraft, setFolderDraft] = useState("");
  const [maxDownloadText, setMaxDownloadText] = useState("");
  const [maxUploadText, setMaxUploadText] = useState("");
  const [maxActiveText, setMaxActiveText] = useState("");

  useEffect(() => {
    void getTorrentSettings()
      .then((loaded) => {
        setSettings(loaded);
        setPortText(String(loaded.port));
        setMaxDownloadText(String(loaded.max_download_kbs));
        setMaxUploadText(String(loaded.max_upload_kbs));
        setMaxActiveText(String(loaded.max_active));
      })
      .catch(() => setSettings(null));
    void getTorrentHealth().then(setHealth).catch(() => setHealth(null));
  }, []);

  if (settings === null) {
    return (
      <section className="cset-panel">
        <p className="cset-panel-sub">Podešavanja torrenta nisu dostupna.</p>
      </section>
    );
  }

  const update = <K extends keyof TorrentSettings>(
    key: K,
    value: TorrentSettings[K],
  ) => {
    setSettings({ ...settings, [key]: value });
  };

  /** Zajednički deo tela zahteva; `password` se dodaje samo kad se menja. */
  const requestBody = (parsed: {
    port: number;
    maxDownload: number;
    maxUpload: number;
    maxActive: number;
  }) => {
    const { has_password: _ignored, ...rest } = settings;
    return {
      ...rest,
      port: parsed.port,
      max_download_kbs: parsed.maxDownload,
      max_upload_kbs: parsed.maxUpload,
      max_active: parsed.maxActive,
    };
  };

  /** Dodaje putanju na spisak nadziranih foldera (bez duplikata). */
  const addFolder = () => {
    const cleaned = folderDraft.trim();

    if (cleaned === "" || settings.watch_folders.includes(cleaned)) {
      setFolderDraft("");
      return;
    }

    update("watch_folders", [...settings.watch_folders, cleaned]);
    setFolderDraft("");
  };

  /**
   * Brisanje sačuvane lozinke.
   *
   * Prazno polje znači „ne diraj", pa bez ove radnje korisnik nema način
   * da ukloni lozinku — zato se ovde šalje izričit prazan string.
   */
  const clearPassword = async () => {
    setNotice(null);

    try {
      const saved = await saveTorrentSettings({
        ...requestBody({
          port: settings.port,
          maxDownload: settings.max_download_kbs,
          maxUpload: settings.max_upload_kbs,
          maxActive: settings.max_active,
        }),
        password: "",
      });
      setSettings(saved);
      setPassword("");
      setNotice("Lozinka je obrisana.");
      setHealth(await getTorrentHealth());
    } catch (cause) {
      setNotice(cause instanceof Error ? cause.message : String(cause));
    }
  };

  const save = async () => {
    setNotice(null);

    const parsedPort = Number(portText);
    const parsedMaxDownload = Number(maxDownloadText);
    const parsedMaxUpload = Number(maxUploadText);
    const parsedMaxActive = Number(maxActiveText);

    if (
      portText.trim() === ""
      || !Number.isInteger(parsedPort)
      || parsedPort < 1
      || parsedPort > 65535
    ) {
      setNotice("Port mora biti ceo broj između 1 i 65535.");
      return;
    }

    if (
      maxActiveText.trim() === ""
      || !Number.isInteger(parsedMaxActive)
      || parsedMaxActive < 1
    ) {
      setNotice("Maksimalno aktivnih torrenta mora biti ceo broj, najmanje 1.");
      return;
    }

    if (
      maxDownloadText.trim() === ""
      || Number.isNaN(parsedMaxDownload)
      || parsedMaxDownload < 0
    ) {
      setNotice(
        "Maksimalna brzina preuzimanja ne sme biti negativna (0 = bez ograničenja).",
      );
      return;
    }

    if (
      maxUploadText.trim() === ""
      || Number.isNaN(parsedMaxUpload)
      || parsedMaxUpload < 0
    ) {
      setNotice(
        "Maksimalna brzina slanja ne sme biti negativna (0 = bez ograničenja).",
      );
      return;
    }

    try {
      const base = requestBody({
        port: parsedPort,
        maxDownload: parsedMaxDownload,
        maxUpload: parsedMaxUpload,
        maxActive: parsedMaxActive,
      });
      const saved = await saveTorrentSettings(
        password ? { ...base, password } : base,
      );
      setSettings(saved);
      setPortText(String(saved.port));
      setMaxDownloadText(String(saved.max_download_kbs));
      setMaxUploadText(String(saved.max_upload_kbs));
      setMaxActiveText(String(saved.max_active));
      setPassword("");
      setNotice("Sačuvano.");
      setHealth(await getTorrentHealth());
    } catch (cause) {
      setNotice(cause instanceof Error ? cause.message : String(cause));
    }
  };

  return (
    <section className="cset-panel">
      <header className="cset-panel-head">
        <div>
          <h2 className="cset-panel-title">Torrenti</h2>
          <p className="cset-panel-sub">
            Veza sa qBittorrent-om, putanje i ograničenja preuzimanja.
            Torrent se uvek dodaje pauziran i čeka tvoje odobrenje.
          </p>
        </div>
      </header>

      {health !== null && (
        <p className="cset-panel-sub">
          {health.engine_available
            ? `Veza radi (qBittorrent ${health.version ?? "nepoznata verzija"}).`
            : (health.message ?? "qBittorrent nije dostupan.")}
        </p>
      )}

      <div className="core-settings-row">
        <div className="core-settings-copy">
          <strong>qBittorrent Web UI</strong>
          <span>
            Preporuka: u qBittorrent-u uključi „Bypass authentication for
            clients on localhost" pa korisničko ime i lozinka nisu potrebni.
            Ako ih upišeš, čuvaju se u lokalnoj bazi u čistom tekstu.
          </span>
        </div>
      </div>

      <label className="cset-field">
        Host
        <input
          onChange={(event) => update("host", event.target.value)}
          type="text"
          value={settings.host}
        />
      </label>

      <label className="cset-field">
        Port
        <input
          onChange={(event) => setPortText(event.target.value)}
          type="number"
          value={portText}
        />
      </label>

      <label className="cset-field">
        Korisničko ime
        <input
          onChange={(event) => update("username", event.target.value)}
          type="text"
          value={settings.username}
        />
      </label>

      <label className="cset-field">
        Lozinka
        <input
          onChange={(event) => setPassword(event.target.value)}
          placeholder={settings.has_password ? "Sačuvana — ostavi prazno da ne menjaš" : ""}
          type="password"
          value={password}
        />
      </label>

      {settings.has_password && (
        <button
          className="filmium-button"
          onClick={() => void clearPassword()}
          type="button"
        >
          Obriši sačuvanu lozinku
        </button>
      )}

      {/* ---------- nadzirani folderi ---------- */}

      <div className="cset-field">
        Nadzirani folderi za .torrent fajlove
        <span className="cset-panel-sub">
          Svaki .torrent iz ovih foldera pojavljuje se kao kartica na
          stranici Torrenti. Prevučeni fajlovi idu u prvi folder sa spiska.
        </span>

        {settings.watch_folders.length === 0 ? (
          <p className="cset-panel-sub">Nijedan folder nije dodat.</p>
        ) : (
          <ul className="filmium-watch-folders">
            {settings.watch_folders.map((folder) => (
              <li key={folder}>
                <span>{folder}</span>

                <button
                  aria-label={`Ukloni ${folder}`}
                  className="filmium-icon-button danger"
                  onClick={() =>
                    update(
                      "watch_folders",
                      settings.watch_folders.filter((item) => item !== folder),
                    )}
                  type="button"
                >
                  <X size={14} />
                </button>
              </li>
            ))}
          </ul>
        )}

        <div className="filmium-watch-folder-add">
          <input
            onChange={(event) => setFolderDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                addFolder();
              }
            }}
            placeholder="Putanja do foldera, npr. C:\Users\Ime\Downloads"
            type="text"
            value={folderDraft}
          />

          <button
            className="filmium-button"
            disabled={folderDraft.trim().length === 0}
            onClick={addFolder}
            type="button"
          >
            <Plus size={14} />
            Dodaj
          </button>
        </div>
      </div>

      <label className="cset-field">
        Odredište preuzimanja
        <input
          onChange={(event) => update("download_path", event.target.value)}
          type="text"
          value={settings.download_path}
        />
      </label>

      <label className="cset-field">
        Maksimalna brzina preuzimanja (kB/s, 0 = bez ograničenja)
        <input
          onChange={(event) => setMaxDownloadText(event.target.value)}
          type="number"
          value={maxDownloadText}
        />
      </label>

      <label className="cset-field">
        Maksimalna brzina slanja (kB/s, 0 = bez ograničenja)
        <input
          onChange={(event) => setMaxUploadText(event.target.value)}
          type="number"
          value={maxUploadText}
        />
      </label>

      <label className="cset-field">
        Maksimalno aktivnih torrenta
        <input
          onChange={(event) => setMaxActiveText(event.target.value)}
          type="number"
          value={maxActiveText}
        />
      </label>

      <label className="cset-field">
        <input
          checked={settings.auto_start}
          onChange={(event) => update("auto_start", event.target.checked)}
          type="checkbox"
        />
        Automatski start posle odobrenja
      </label>

      <label className="cset-field">
        <input
          checked={settings.seed_after_complete}
          onChange={(event) =>
            update("seed_after_complete", event.target.checked)
          }
          type="checkbox"
        />
        Nastavi seed posle završetka
      </label>

      <label className="cset-field">
        <input
          checked={settings.delete_source_torrent}
          onChange={(event) =>
            update("delete_source_torrent", event.target.checked)
          }
          type="checkbox"
        />
        Obriši izvorni .torrent fajl po dodavanju
      </label>

      <label className="cset-field">
        Ekstenzije koje se podrazumevano ne štikliraju
        <input
          onChange={(event) =>
            update(
              "unselected_extensions",
              event.target.value
                .split(",")
                .map((part) => part.trim().toLowerCase())
                .filter((part) => part.length > 0)
                .map((part) => (part.startsWith(".") ? part : `.${part}`)),
            )
          }
          type="text"
          value={settings.unselected_extensions.join(", ")}
        />
      </label>

      <button className="filmium-button primary" onClick={() => void save()} type="button">
        Sačuvaj
      </button>

      {notice !== null && <p className="cset-panel-sub">{notice}</p>}
    </section>
  );
}

export default FilmiumTorrentSettingsPanel;
