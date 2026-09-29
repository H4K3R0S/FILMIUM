import { useCallback, useEffect, useState } from "react";

import {
  confirmFilmiumLibraryImportStream,
  createFilmiumLibraryRoot,
  deleteFilmiumLibraryRoot,
  getFilmiumLibraryRoots,
  ignoreFilmiumLibraryDirectory,
  previewFilmiumLibraryImport,
  scanFilmiumLibraryRoot,
  setMainFilmiumLibrary,
  updateFilmiumLibraryRoot,
} from "../../../services/filmiumLibraryApi";
import type { SseProgress } from "../../../services/httpClient";
import { type FilmiumContentMode } from "../components/uploads/ContentModeToggle";
import type {
  FilmiumImportOverrides,
  FilmiumLibraryImportCommitResult,
  FilmiumLibraryImportPreview,
  FilmiumLibraryRoot,
  FilmiumLibraryRootRequest,
  FilmiumLibraryScanResult,
} from "../../../types/filmiumLibrary";
import {
  notifyFilmiumCatalogChanged,
} from "../events/filmiumCatalogEvents";


function importKey(
  rootId: number,
  relativeDirectory: string,
): string {
  return `${rootId}:${relativeDirectory}`;
}


function withoutRootEntries<T>(
  current: Record<string, T>,
  rootId: number,
): Record<string, T> {
  return Object.fromEntries(
    Object.entries(current).filter(
      ([key]) => !key.startsWith(`${rootId}:`),
    ),
  );
}


function pathIdentity(value: string): string {
  return value
    .trim()
    .replace(/[\\/]+/g, "/")
    .replace(/\/+$/, "")
    .toLocaleLowerCase("sr");
}


export function useFilmiumLibraries() {
  const [roots, setRoots] = useState<FilmiumLibraryRoot[]>([]);
  const [scanResults, setScanResults] = useState<
    Record<number, FilmiumLibraryScanResult>
  >({});
  const [importPreviews, setImportPreviews] = useState<
    Record<string, FilmiumLibraryImportPreview>
  >({});
  const [importResults, setImportResults] = useState<
    Record<string, FilmiumLibraryImportCommitResult>
  >({});
  const [isLoading, setIsLoading] = useState(true);
  const [busyRootId, setBusyRootId] = useState<number | null>(null);
  const [busyImportKey, setBusyImportKey] = useState<string | null>(
    null,
  );
  const [isCreating, setIsCreating] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const refreshRoots = useCallback(async (
    josTraje: () => boolean = () => true,
  ): Promise<void> => {
    setIsLoading(true);
    setErrorMessage(null);

    try {
      setRoots(await getFilmiumLibraryRoots());
    } catch (error) {
      if (!josTraje()) {
        return;
      }
      setErrorMessage(
        error instanceof Error ? error.message : "Biblioteke nisu učitane.",
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
      await refreshRoots(() => ziv);
    }
    void pokreni();
    return () => {
      ziv = false;
    };
  }, [refreshRoots]);

  async function createRoot(
    request: FilmiumLibraryRootRequest,
  ): Promise<boolean> {
    setIsCreating(true);
    setErrorMessage(null);

    try {
      const created = await createFilmiumLibraryRoot(request);
      setRoots((current) =>
        [...current, created].sort((first, second) =>
          first.name.localeCompare(second.name, "sr"),
        ),
      );
      return true;
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Biblioteka nije dodata.",
      );
      return false;
    } finally {
      setIsCreating(false);
    }
  }

  async function scanRoot(
    rootId: number,
    scanSubtitles = true,
    onlyNew = false,
  ): Promise<FilmiumLibraryScanResult | null> {
    setBusyRootId(rootId);
    setErrorMessage(null);

    try {
      const result = await scanFilmiumLibraryRoot(
        rootId,
        scanSubtitles,
        onlyNew,
      );
      setScanResults((current) => ({ ...current, [rootId]: result }));
      setImportPreviews((current) =>
        withoutRootEntries(current, rootId),
      );
      setImportResults((current) =>
        withoutRootEntries(current, rootId),
      );
      await refreshRoots();
      return result;
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Skeniranje nije uspelo.",
      );
      return null;
    } finally {
      setBusyRootId(null);
    }
  }

  async function previewImport(
    rootId: number,
    relativeDirectory: string,
    includeTmdb = false,
  ): Promise<boolean> {
    const preview = await fetchImportPreview(
      rootId,
      relativeDirectory,
      includeTmdb,
    );
    return preview !== null;
  }

  /**
   * Učitava import preview i VRAĆA ga (uz upis u keš). „Prebaci sve"
   * koristi ovo da pokupi TMDB-obogaćen preview za red uvoza.
   */
  async function fetchImportPreview(
    rootId: number,
    relativeDirectory: string,
    includeTmdb = false,
  ): Promise<FilmiumLibraryImportPreview | null> {
    const key = importKey(rootId, relativeDirectory);
    setBusyImportKey(key);
    setErrorMessage(null);

    try {
      const preview = await previewFilmiumLibraryImport(
        rootId,
        relativeDirectory,
        includeTmdb,
      );
      setImportPreviews((current) => ({
        ...current,
        [key]: preview,
      }));
      return preview;
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : "Import preview nije učitan.",
      );
      return null;
    } finally {
      setBusyImportKey(null);
    }
  }

  async function confirmImport(
    rootId: number,
    relativeDirectory: string,
    targetMediaId: number | null = null,
    overrides: FilmiumImportOverrides | null = null,
    onProgress?: (progress: SseProgress) => void,
    conflictMode: "fail" | "skip" | "overwrite" = "fail",
    contentMode: FilmiumContentMode = "regular",
    synchronized: boolean = false,
  ): Promise<FilmiumLibraryImportCommitResult | null> {
    const key = importKey(rootId, relativeDirectory);
    setBusyImportKey(key);
    setErrorMessage(null);

    try {
      const result = await confirmFilmiumLibraryImportStream(
        rootId,
        {
          relative_directory: relativeDirectory,
          confirmed: true,
          target_media_id: targetMediaId,
          // Polja se šalju samo kad ih korisnik zaista izmeni.
          ...(overrides?.title !== undefined
            ? { title: overrides.title }
            : {}),
          ...(overrides?.release_year !== undefined
            ? { release_year: overrides.release_year }
            : {}),
          ...(overrides?.genres !== undefined
            ? { genres: overrides.genres }
            : {}),
          ...(overrides?.target_library_root_id != null
            ? {
                target_library_root_id:
                  overrides.target_library_root_id,
              }
            : {}),
          conflict_mode: conflictMode,
          content_mode: contentMode,
          synchronized,
        },
        onProgress ?? (() => {}),
      );
      setImportResults((current) => ({
        ...current,
        [key]: result,
      }));
      setImportPreviews((current) => {
        const next = { ...current };
        delete next[key];
        return next;
      });
      notifyFilmiumCatalogChanged();
      return result;
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : "Potvrđeni uvoz nije uspeo.",
      );
      return null;
    } finally {
      setBusyImportKey(null);
    }
  }

  /**
   * Označava disk kao glavni i osvežava listu lokacija.
   */
  async function setMainLibrary(rootId: number): Promise<void> {
    try {
      await setMainFilmiumLibrary(rootId);
      await refreshRoots();
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : "Postavljanje glavnog diska nije uspelo.",
      );
    }
  }

  /**
   * Uklanja jednu stavku iz trenutnih rezultata (bez upisa u bazu).
   */
  function dismissEntry(
    rootId: number,
    relativeDirectory: string,
  ): void {
    setScanResults((current) => {
      const result = current[rootId];

      if (!result) {
        return current;
      }

      const entries = result.entries.filter(
        (entry) => entry.directory !== relativeDirectory,
      );

      if (entries.length === result.entries.length) {
        return current;
      }

      const importable = entries.filter(
        (entry) => entry.can_import,
      ).length;

      return {
        ...current,
        [rootId]: {
          ...result,
          entries,
          discovered_count: entries.length,
          importable_count: importable,
          problem_count: entries.length - importable,
        },
      };
    });

    const key = importKey(rootId, relativeDirectory);
    setImportPreviews((current) => {
      const next = { ...current };
      delete next[key];
      return next;
    });
  }

  /**
   * Trajno izuzima folder iz budućih skeniranja i sklanja ga iz prikaza.
   */
  async function ignoreDirectory(
    rootId: number,
    relativeDirectory: string,
  ): Promise<void> {
    try {
      await ignoreFilmiumLibraryDirectory(rootId, relativeDirectory);
      dismissEntry(rootId, relativeDirectory);
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : "Trajno izuzimanje foldera nije uspelo.",
      );
    }
  }

  function clearImportPreview(
    rootId: number,
    relativeDirectory: string,
  ): void {
    const key = importKey(rootId, relativeDirectory);
    setImportPreviews((current) => {
      const next = { ...current };
      delete next[key];
      return next;
    });
  }

  /**
   * Registruje izabrani folder ako je nov i odmah ga skenira.
   * Vec registrovana putanja se samo ponovo skenira.
   */
  async function addAndScanDirectory(
    path: string,
    name: string,
    isPersistent = true,
    scanSubtitles = true,
    onlyNew = false,
  ): Promise<{ rootId: number; result: FilmiumLibraryScanResult } | null> {
    setIsCreating(true);
    setErrorMessage(null);

    let selectedRoot = roots.find(
      (root) => pathIdentity(root.path) === pathIdentity(path),
    );

    try {
      if (!selectedRoot) {
        selectedRoot = await createFilmiumLibraryRoot({
          name,
          path,
          ...(isPersistent
            ? {}
            : { is_persistent: false }),
        });
        const createdRoot = selectedRoot;
        setRoots((current) =>
          [...current, createdRoot].sort((first, second) =>
            first.name.localeCompare(second.name, "sr"),
          ),
        );
      }

      if (
        isPersistent &&
        selectedRoot.is_persistent === false
      ) {
        selectedRoot = await updateFilmiumLibraryRoot(
          selectedRoot.id,
          {
            name: selectedRoot.name,
            path: selectedRoot.path,
            volume_id: selectedRoot.volume_id,
            volume_label: selectedRoot.volume_label,
            is_enabled: selectedRoot.is_enabled,
            is_persistent: isPersistent,
          },
        );
        const updatedRoot = selectedRoot;
        setRoots((current) =>
          current.map((root) =>
            root.id === updatedRoot.id ? updatedRoot : root
          ),
        );
      }

      const rootToScan = selectedRoot;
      setBusyRootId(rootToScan.id);
      const result = await scanFilmiumLibraryRoot(
        rootToScan.id,
        scanSubtitles,
        onlyNew,
      );
      setScanResults((current) => ({
        ...current,
        [rootToScan.id]: result,
      }));
      setImportPreviews((current) =>
        withoutRootEntries(current, rootToScan.id),
      );
      setImportResults((current) =>
        withoutRootEntries(current, rootToScan.id),
      );
      await refreshRoots();
      return { rootId: rootToScan.id, result };
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : "Izabrani folder nije dodat i skeniran.",
      );
      return null;
    } finally {
      setBusyRootId(null);
      setIsCreating(false);
    }
  }

  /**
   * Uklanja rezultate skeniranja jednog root-a iz GUI stanja.
   * Koristi se kada kombinovani režim pređe sa filmskog na serijsko.
   */
  function clearRootScanResult(rootId: number): void {
    setScanResults((current) => {
      const next = { ...current };
      delete next[rootId];
      return next;
    });
    setImportPreviews((current) => withoutRootEntries(current, rootId));
    setImportResults((current) => withoutRootEntries(current, rootId));
  }

  async function setRootPersistence(
    rootId: number,
    isPersistent: boolean,
  ): Promise<boolean> {
    const root = roots.find((item) => item.id === rootId);

    if (!root) {
      setErrorMessage("Izabrana lokacija više ne postoji.");
      return false;
    }

    setBusyRootId(rootId);
    setErrorMessage(null);

    try {
      const updated = await updateFilmiumLibraryRoot(rootId, {
        name: root.name,
        path: root.path,
        volume_id: root.volume_id,
        volume_label: root.volume_label,
        is_enabled: root.is_enabled,
        is_persistent: isPersistent,
      });
      setRoots((current) =>
        current.map((item) => item.id === rootId ? updated : item),
      );
      return true;
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : "Vrsta lokacije nije promenjena.",
      );
      return false;
    } finally {
      setBusyRootId(null);
    }
  }

  async function scanAllRoots(): Promise<void> {
    for (const root of roots) {
      if (root.is_enabled) {
        await scanRoot(root.id);
      }
    }
  }

  /**
   * Uklanja samo rezultate trenutnog skeniranja iz GUI stanja.
   *
   * Registrovane biblioteke, baza i fajlovi na diskovima ostaju
   * potpuno nepromenjeni.
   */
  function clearScanResults(): void {
    setScanResults({});
    setImportPreviews({});
    setImportResults({});
    setErrorMessage(null);
  }

  async function removeRoot(rootId: number): Promise<void> {
    setBusyRootId(rootId);
    setErrorMessage(null);

    try {
      await deleteFilmiumLibraryRoot(rootId);
      setRoots((current) => current.filter((root) => root.id !== rootId));
      setScanResults((current) => {
        const next = { ...current };
        delete next[rootId];
        return next;
      });
      setImportPreviews((current) =>
        withoutRootEntries(current, rootId),
      );
      setImportResults((current) =>
        withoutRootEntries(current, rootId),
      );
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Biblioteka nije uklonjena.",
      );
    } finally {
      setBusyRootId(null);
    }
  }

  return {
    addAndScanDirectory,
    busyImportKey,
    busyRootId,
    clearImportPreview,
    clearRootScanResult,
    clearScanResults,
    confirmImport,
    createRoot,
    dismissEntry,
    errorMessage,
    fetchImportPreview,
    ignoreDirectory,
    importPreviews,
    importResults,
    isCreating,
    isLoading,
    previewImport,
    refreshRoots,
    removeRoot,
    roots,
    scanResults,
    scanAllRoots,
    scanRoot,
    setMainLibrary,
    setRootPersistence,
  };
}
