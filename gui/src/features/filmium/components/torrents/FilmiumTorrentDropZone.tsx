import { useCallback, useEffect, useRef, useState } from "react";

import { FileDown } from "lucide-react";

import {
  TORRENT_DROPPED_EVENT,
  dragCarriesFiles,
  splitTorrentFiles,
} from "../../torrentDrop";
import { uploadTorrentFile } from "../../../../services/filmiumTorrentsApi";


// ==========          PREVLAČENJE .torrent FAJLOVA          ==========

// Koliko poruka o ishodu stoji na ekranu pre nego što nestane.
const NOTICE_MS = 6000;

type Notice = {
  tone: "ok" | "error";
  text: string;
};

/**
 * Prijem prevučenih .torrent fajlova na celoj FILMIUM površini.
 *
 * Osluškuje se `window`, a ne jedan `div`: prevlačenje treba da radi i
 * iznad chata, modala i bilo koje FILMIUM stranice. Sve što nije .torrent
 * se odbija sa porukom — drugi fajlovi se ovim putem ne uvoze.
 */
function FilmiumTorrentDropZone() {
  const [isOver, setIsOver] = useState(false);
  const [notice, setNotice] = useState<Notice | null>(null);

  // Ulazak/izlazak stiže i za svaki ugnežđen element, pa se broji dubina —
  // bez toga bi prelazak preko deteta ugasio prekrivač.
  const depth = useRef(0);

  const show = useCallback((next: Notice) => setNotice(next), []);

  useEffect(() => {
    if (notice === null) {
      return;
    }

    const timer = window.setTimeout(() => setNotice(null), NOTICE_MS);
    return () => window.clearTimeout(timer);
  }, [notice]);

  const receive = useCallback(
    async (transfer: DataTransfer | null) => {
      const { accepted, rejected } = splitTorrentFiles(transfer);

      if (accepted.length === 0) {
        show({
          tone: "error",
          text:
            rejected.length === 0
              ? "Prevuci .torrent fajl."
              : `FILMIUM prima samo .torrent fajlove — odbijeno: ${rejected.join(", ")}`,
        });
        return;
      }

      const added: string[] = [];
      const failed: string[] = [];

      for (const file of accepted) {
        try {
          const found = await uploadTorrentFile(file);
          added.push(found.name);
        } catch (cause) {
          failed.push(
            `${file.name} (${cause instanceof Error ? cause.message : String(cause)})`,
          );
        }
      }

      if (added.length > 0) {
        window.dispatchEvent(new CustomEvent(TORRENT_DROPPED_EVENT));
      }

      if (failed.length > 0) {
        show({ tone: "error", text: `Nije primljeno: ${failed.join("; ")}` });
        return;
      }

      show({
        tone: "ok",
        text:
          added.length === 1
            ? `Torrent „${added[0]}” je spreman za izbor fajlova.`
            : `${added.length} torrenta je spremno za izbor fajlova.`,
      });
    },
    [show],
  );

  useEffect(() => {
    const onDragEnter = (event: DragEvent) => {
      if (!dragCarriesFiles(event.dataTransfer)) {
        return;
      }

      event.preventDefault();
      depth.current += 1;
      setIsOver(true);
    };

    const onDragOver = (event: DragEvent) => {
      if (!dragCarriesFiles(event.dataTransfer)) {
        return;
      }

      // Bez ovoga browser otvori prevučeni fajl umesto da ga preda stranici.
      event.preventDefault();

      if (event.dataTransfer !== null) {
        event.dataTransfer.dropEffect = "copy";
      }
    };

    const onDragLeave = (event: DragEvent) => {
      if (!dragCarriesFiles(event.dataTransfer)) {
        return;
      }

      depth.current = Math.max(0, depth.current - 1);
      if (depth.current === 0) {
        setIsOver(false);
      }
    };

    const onDrop = (event: DragEvent) => {
      if (!dragCarriesFiles(event.dataTransfer)) {
        return;
      }

      event.preventDefault();
      depth.current = 0;
      setIsOver(false);
      void receive(event.dataTransfer);
    };

    window.addEventListener("dragenter", onDragEnter);
    window.addEventListener("dragover", onDragOver);
    window.addEventListener("dragleave", onDragLeave);
    window.addEventListener("drop", onDrop);

    return () => {
      window.removeEventListener("dragenter", onDragEnter);
      window.removeEventListener("dragover", onDragOver);
      window.removeEventListener("dragleave", onDragLeave);
      window.removeEventListener("drop", onDrop);
    };
  }, [receive]);

  return (
    <>
      {isOver && (
        <div aria-hidden="true" className="filmium-torrent-dropzone">
          <div className="filmium-torrent-dropzone-card">
            <FileDown size={28} />
            <strong>Pusti .torrent fajl</strong>
            <span>Ostali fajlovi se ne primaju.</span>
          </div>
        </div>
      )}

      {notice !== null && (
        <div
          aria-live="polite"
          className="filmium-torrent-drop-notice"
          data-tone={notice.tone}
          role="status"
        >
          {notice.text}
        </div>
      )}
    </>
  );
}

export default FilmiumTorrentDropZone;
