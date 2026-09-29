import { openPathDialog } from "../../../lib/pathPicker";
import { useState } from "react";

import { createFilmiumLibraryRoot } from "../../../services/filmiumLibraryApi";
import {
  confirmFilmiumSeriesStream,
  previewFilmiumSeries,
} from "../../../services/filmiumSeriesApi";
import type { SseProgress } from "../../../services/httpClient";
import { type FilmiumContentMode } from "../components/uploads/ContentModeToggle";
import type {
  FilmiumSeriesImportResult,
  FilmiumSeriesScan,
} from "../../../types/filmiumSeries";


type SeriesPreviewState = {
  rootId: number;
  series: FilmiumSeriesScan[];
};


/**
 * Vodi tok uvoza serija: izbor foldera → pregled (jedna ili više serija)
 * → potvrda po pojedinačnoj seriji.
 */
export function useFilmiumSeriesImport() {
  const [preview, setPreview] = useState<SeriesPreviewState | null>(
    null,
  );
  const [results, setResults] = useState<
    Record<string, FilmiumSeriesImportResult>
  >({});
  const [isBusy, setIsBusy] = useState(false);
  const [busyDirectory, setBusyDirectory] = useState<string | null>(
    null,
  );
  const [errorMessage, setErrorMessage] =
    useState<string | null>(null);

  async function chooseFolder(): Promise<void> {
    setIsBusy(true);
    setErrorMessage(null);
    setResults({});

    try {
      const selected = await openPathDialog({
        directory: true,
        multiple: false,
        title: "Izaberi folder serije ili biblioteke serija",
      });

      if (typeof selected !== "string") {
        return;
      }

      const name =
        selected.split(/[\\/]/).filter(Boolean).at(-1) ?? "Serije";
      const root = await createFilmiumLibraryRoot({
        name,
        path: selected,
        is_persistent: false,
      });
      const found = await runSeriesScan(root.id);

      if (!found) {
        setErrorMessage(
          "U izabranom folderu nije prepoznata nijedna serija.",
        );
      }
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : "Skeniranje serije nije uspelo.",
      );
    } finally {
      setIsBusy(false);
    }
  }

  /**
   * Skenira serije u već registrovanoj lokaciji (bez biranja foldera).
   * Koristi se u kombinovanom režimu „Skeniraj folder" kao rezerva
   * kada filmsko skeniranje ne pronađe filmove.
   */
  async function runSeriesScan(rootId: number): Promise<boolean> {
    const scan = await previewFilmiumSeries(rootId, ".");

    if (scan.series.length === 0) {
      setPreview(null);
      return false;
    }

    setResults({});
    setPreview({ rootId, series: scan.series });
    return true;
  }

  async function scanExistingRoot(rootId: number): Promise<boolean> {
    setIsBusy(true);
    setErrorMessage(null);

    try {
      return await runSeriesScan(rootId);
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : "Skeniranje serije nije uspelo.",
      );
      return false;
    } finally {
      setIsBusy(false);
    }
  }

  async function confirmImport(
    relativeDirectory: string,
    targetLibraryRootId?: number | null,
    onProgress?: (progress: SseProgress) => void,
    contentMode: FilmiumContentMode = "regular",
    synchronized: boolean = false,
  ): Promise<void> {
    if (!preview) {
      return;
    }

    setIsBusy(true);
    setBusyDirectory(relativeDirectory);
    setErrorMessage(null);

    try {
      const imported = await confirmFilmiumSeriesStream(
        preview.rootId,
        relativeDirectory,
        targetLibraryRootId ?? null,
        onProgress ?? (() => {}),
        contentMode,
        synchronized,
      );
      setResults((current) => ({
        ...current,
        [relativeDirectory]: imported,
      }));
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : "Uvoz serije nije uspeo.",
      );
    } finally {
      setIsBusy(false);
      setBusyDirectory(null);
    }
  }

  function reset(): void {
    setPreview(null);
    setResults({});
    setErrorMessage(null);
  }

  return {
    busyDirectory,
    chooseFolder,
    confirmImport,
    errorMessage,
    isBusy,
    preview,
    reset,
    results,
    scanExistingRoot,
  };
}


export type FilmiumSeriesImportController = ReturnType<
  typeof useFilmiumSeriesImport
>;
