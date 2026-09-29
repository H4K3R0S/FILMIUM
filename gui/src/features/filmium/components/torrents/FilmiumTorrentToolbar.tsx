import { useRef, useState } from "react";

import { FilePlus2, Magnet, Pause, Play } from "lucide-react";


// ==========          GORNJA TRAKA STRANICE TORRENTI          ==========

type Props = {
  isBusy: boolean;
  /** Magnet link iz polja. */
  onAddMagnet: (source: string) => Promise<void>;
  /** Izabrani .torrent fajlovi sa diska. */
  onAddFiles: (files: File[]) => Promise<void>;
  /** Pokreće sve torrente koji mogu da krenu. */
  onStartAll: () => void;
  /** Pauzira sve torrente koji se skidaju. */
  onStopAll: () => void;
  /** Ima li uopšte torrenta koji „Start" može da pokrene. */
  canStartAll: boolean;
  /** Ima li torrenta u toku koji „Stop" može da zaustavi. */
  canStopAll: boolean;
};

/**
 * Unos i grupne radnje: magnet link, izbor .torrent fajla, start i stop
 * nad SVIM torrentima odjednom.
 *
 * „Dodaj torrent" otvara sistemski izbor fajla; isti put kojim ide i
 * prevučen fajl, pa oba završavaju u nadziranom folderu kao kartica.
 */
function FilmiumTorrentToolbar({
  isBusy,
  onAddMagnet,
  onAddFiles,
  onStartAll,
  onStopAll,
  canStartAll,
  canStopAll,
}: Props) {
  const [magnet, setMagnet] = useState("");
  const fileInput = useRef<HTMLInputElement | null>(null);

  const submitMagnet = async () => {
    const cleaned = magnet.trim();

    if (!cleaned || isBusy) {
      return;
    }

    await onAddMagnet(cleaned);
    setMagnet("");
  };

  return (
    <div className="filmium-torrent-toolbar">
      <div className="filmium-torrent-addbar">
        <input
          className="filmium-torrent-addbar-input"
          onChange={(event) => setMagnet(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              void submitMagnet();
            }
          }}
          placeholder="Nalepi magnet link"
          type="text"
          value={magnet}
        />

        <button
          className="filmium-button primary"
          disabled={magnet.trim().length === 0 || isBusy}
          onClick={() => void submitMagnet()}
          type="button"
        >
          <Magnet size={15} />
          Dodaj magnet
        </button>
      </div>

      <div className="filmium-torrent-toolbar-actions">
        <button
          className="filmium-button"
          disabled={isBusy}
          onClick={() => fileInput.current?.click()}
          type="button"
        >
          <FilePlus2 size={15} />
          Dodaj torrent
        </button>

        {/* Polje je skriveno: izbor fajla otvara dugme iznad, da traka
            ostane u istom stilu kao ostatak FILMIUM-a. */}
        <input
          accept=".torrent"
          className="filmium-torrent-file-input"
          multiple
          onChange={(event) => {
            const chosen = Array.from(event.target.files ?? []);
            event.target.value = "";

            if (chosen.length > 0) {
              void onAddFiles(chosen);
            }
          }}
          ref={fileInput}
          type="file"
        />

        <span aria-hidden="true" className="filmium-torrent-toolbar-divider" />

        {/* Dugme je ugašeno kad nema na šta da deluje — inače klik izgleda
            kao da ništa ne radi. „Start" pokreće SVE: pauzirane nastavlja,
            a pronađene i one koji čekaju izbor pušta sa podrazumevanim
            izborom fajlova (ekstenzije iz filtera ostaju neštiklirane). */}
        <button
          className="filmium-button"
          disabled={isBusy || !canStartAll}
          onClick={onStartAll}
          title={
            canStartAll
              ? "Pokreni sve torrente (podrazumevani izbor fajlova)"
              : "Nema torrenta koji bi se pokrenuo"
          }
          type="button"
        >
          <Play size={15} />
          Start
        </button>

        <button
          className="filmium-button"
          disabled={isBusy || !canStopAll}
          onClick={onStopAll}
          title={
            canStopAll
              ? "Pauziraj sve torrente koji se skidaju"
              : "Nema torrenta u toku koji bi se pauzirao"
          }
          type="button"
        >
          <Pause size={15} />
          Stop
        </button>
      </div>
    </div>
  );
}

export default FilmiumTorrentToolbar;
