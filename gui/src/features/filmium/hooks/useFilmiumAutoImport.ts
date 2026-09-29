import { useCallback, useEffect, useState } from "react";

import {
  addMonitoredFolder,
  confirmDetectedImport,
  listDetectedFiles,
  listMonitoredFolders,
  rejectDetectedImport,
  removeMonitoredFolder,
} from "../../../services/filmiumAutoImportApi";
import type {
  AutoImportRuleRequest,
  DetectedFile,
  MonitoredFolder,
} from "../../../types/filmiumAutoImport";


// ==========          FILMIUM AUTO-IMPORT (praćenje foldera)          ==========

/**
 * Učitava praćene foldere i detektovane fajlove i nudi akcije nad njima.
 *
 * Detektovane fajlove backend puni preko `watchdog`-a kad se u praćenom
 * folderu pojavi nov video; ovde ih samo prikazujemo i potvrđujemo/odbacujemo.
 */
export function useFilmiumAutoImport() {
  const [folders, setFolders] = useState<MonitoredFolder[]>([]);
  const [detected, setDetected] = useState<DetectedFile[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const refresh = useCallback(async (
    josTraje: () => boolean = () => true,
  ): Promise<void> => {
    try {
      const [loadedFolders, loadedDetected] = await Promise.all([
        listMonitoredFolders(),
        listDetectedFiles(),
      ]);
      if (!josTraje()) {
        return;
      }
      setFolders(loadedFolders);
      setDetected(loadedDetected);
      setErrorMessage(null);
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : "Učitavanje praćenih foldera nije uspelo.",
      );
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Prvo učitavanje pamti da li je ekran još tu, pa odgovor koji kasni
  // ne upisuje ništa u komponentu koje više nema.
  useEffect(() => {
    let ziv = true;
    async function pokreni() {
      await refresh(() => ziv);
    }
    void pokreni();
    return () => {
      ziv = false;
    };
  }, [refresh]);

  const addFolder = useCallback(
    async (rule: AutoImportRuleRequest): Promise<void> => {
      await addMonitoredFolder(rule);
      await refresh();
    },
    [refresh],
  );

  const removeFolder = useCallback(
    async (path: string): Promise<void> => {
      await removeMonitoredFolder(path);
      setFolders((current) =>
        current.filter((folder) => folder.folder_path !== path),
      );
    },
    [],
  );

  const confirmFile = useCallback(
    async (fileId: number): Promise<void> => {
      const updated = await confirmDetectedImport(fileId);
      setDetected((current) =>
        current.map((file) => (file.id === fileId ? updated : file)),
      );
    },
    [],
  );

  const rejectFile = useCallback(
    async (fileId: number): Promise<void> => {
      const updated = await rejectDetectedImport(fileId);
      setDetected((current) =>
        current.map((file) => (file.id === fileId ? updated : file)),
      );
    },
    [],
  );

  return {
    folders,
    detected,
    isLoading,
    errorMessage,
    refresh,
    addFolder,
    removeFolder,
    confirmFile,
    rejectFile,
  };
}
