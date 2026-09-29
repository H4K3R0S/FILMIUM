import { useEffect } from "react";
import { createPortal } from "react-dom";

import FilmiumSubtitleTerminator, {
  type TerminatorAdHocFile,
} from "../uploads/FilmiumSubtitleTerminator";
import { useFilmiumSubtitleRepairs } from "../../hooks/useFilmiumSubtitleRepairs";


/**
 * Otvara „Terminator prevoda" ad-hoc, nad prevodima jednog filma (dugme
 * „Edit Prevoda" na filmskoj strani). Controller (i njegov polling reda) se
 * montira samo dok je overlay otvoren.
 */
export default function FilmiumSubtitleEditorOverlay({
  files,
  currentTimeMs = 0,
  onClose,
}: {
  files: TerminatorAdHocFile[];
  /** Trenutak inline plejera (ms) — Editor skače na tu liniju prevoda. */
  currentTimeMs?: number;
  onClose: () => void;
}) {
  const controller = useFilmiumSubtitleRepairs();
  const { openFile } = controller;

  // Otvori primarni prevod pri montiranju.
  useEffect(() => {
    if (files.length > 0) {
      void openFile(files[0].path);
    }
  }, [files, openFile]);

  // Portal na document.body: predak na filmskoj strani ima backdrop-filter,
  // koji pravi „containing block" za position:fixed, pa bi okvir bio veći od
  // prozora. Portal vraća fiksiranje na viewport.
  return createPortal(
    <FilmiumSubtitleTerminator
      adHocFiles={files}
      controller={controller}
      currentTimeMs={currentTimeMs}
      onBack={onClose}
    />,
    document.body,
  );
}
