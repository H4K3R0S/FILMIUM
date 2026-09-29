import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  clearSubtitleRepairScanResults,
  editPreviewSubtitle,
  getSubtitleRepairQueue,
  previewSubtitleRepair,
  repairSubtitle,
  saveEditedSubtitle,
  updateSubtitleRepairStatus,
} from "../../../services/filmiumSubtitlesApi";
import type {
  SubtitleInspectionResult,
  SubtitleRepairQueueItem,
  SubtitleRepairQueueStatus,
} from "../../../types/filmiumSubtitles";

export const SUBTITLE_QUEUE_CHANGED_EVENT =
  "filmium:subtitle-queue-changed";

export function useFilmiumSubtitleRepairs() {
  const [items, setItems] = useState<SubtitleRepairQueueItem[]>([]);
  const [inspection, setInspection] =
    useState<SubtitleInspectionResult | null>(null);
  const [selectedItemId, setSelectedItemId] =
    useState<number | null>(null);
  const [busyItemId, setBusyItemId] = useState<number | null>(null);
  const [isSavingEdit, setIsSavingEdit] = useState(false);
  const [isClearing, setIsClearing] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(
    null,
  );
  const [successMessage, setSuccessMessage] = useState<string | null>(
    null,
  );

  const activeItems = useMemo(
    () => items.filter(
      (item) =>
        item.status === "pending" ||
        item.status === "reviewed",
    ),
    [items],
  );

  const refreshQueue = useCallback(async (
    josTraje: () => boolean = () => true,
  ): Promise<void> => {
    setIsLoading(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      const red = await getSubtitleRepairQueue();
      if (!josTraje()) {
        return;
      }
      setItems(red);
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : "Prevodi za proveru nisu učitani.",
      );
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    let ziv = true;
    async function pokreni() {
      await refreshQueue(() => ziv);
    }
    void pokreni();
    const refreshInterval = window.setInterval(
      () => void refreshQueue(),
      5000,
    );

    function handleQueueChange(): void {
      void refreshQueue();
    }

    window.addEventListener(
      SUBTITLE_QUEUE_CHANGED_EVENT,
      handleQueueChange,
    );

    return () => {
      ziv = false;
      window.clearInterval(refreshInterval);
      window.removeEventListener(
        SUBTITLE_QUEUE_CHANGED_EVENT,
        handleQueueChange,
      );
    };
  }, [refreshQueue]);

  function closeInspection(): void {
    setInspection(null);
    setSelectedItemId(null);
  }

  async function previewItem(itemId: number): Promise<boolean> {
    setBusyItemId(itemId);
    setErrorMessage(null);

    try {
      const result = await previewSubtitleRepair(itemId);
      setInspection(result);
      setSelectedItemId(itemId);
      setItems((current) =>
        current.map((item) =>
          item.id === itemId
            ? { ...item, status: "reviewed" }
            : item,
        ),
      );
      return true;
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : "Pregled prevoda nije napravljen.",
      );
      return false;
    } finally {
      setBusyItemId(null);
    }
  }

  async function setItemStatus(
    itemId: number,
    status: SubtitleRepairQueueStatus,
  ): Promise<void> {
    setBusyItemId(itemId);
    setErrorMessage(null);

    try {
      await updateSubtitleRepairStatus(itemId, { status });
      if (selectedItemId === itemId) {
        closeInspection();
      }
      await refreshQueue();
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : "Status prevoda nije promenjen.",
      );
    } finally {
      setBusyItemId(null);
    }
  }

  async function confirmRepair(itemId: number): Promise<boolean> {
    setBusyItemId(itemId);
    setErrorMessage(null);

    try {
      await repairSubtitle(itemId, { confirmed: true });
      closeInspection();
      await refreshQueue();
      return true;
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : "Popravka prevoda nije uspela.",
      );
      return false;
    } finally {
      setBusyItemId(null);
    }
  }

  // ----- Editor mod (ad-hoc fajl po putanji) -----

  async function openFile(filePath: string): Promise<boolean> {
    setErrorMessage(null);

    try {
      const result = await editPreviewSubtitle(filePath);
      setInspection(result);
      // Ad-hoc fajl nije stavka reda popravke.
      setSelectedItemId(null);
      return true;
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : "Prevod nije moguće otvoriti.",
      );
      return false;
    }
  }

  async function saveManualEdit(content: string): Promise<boolean> {
    if (!inspection) {
      return false;
    }
    setIsSavingEdit(true);
    setErrorMessage(null);

    try {
      await saveEditedSubtitle({
        file_path: inspection.file_path,
        source_sha256: inspection.source_sha256,
        content,
        confirmed: true,
      });
      // Ponovo učitaj (nov sha) da dalje editovanje ostane moguće.
      await openFile(inspection.file_path);
      void refreshQueue();
      return true;
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : "Izmena prevoda nije sačuvana.",
      );
      return false;
    } finally {
      setIsSavingEdit(false);
    }
  }

  async function clearScanResults(): Promise<boolean> {
    setIsClearing(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      const result = await clearSubtitleRepairScanResults();
      closeInspection();
      setItems((current) =>
        current.filter(
          (item) =>
            item.status === "ignored" ||
            item.status === "repaired",
        ),
      );
      setSuccessMessage(
        result.deleted_count === 1
          ? "Obrisan je 1 rezultat skeniranja."
          : `Obrisano je ${result.deleted_count} rezultata skeniranja.`,
      );
      return true;
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : "Rezultati skeniranja nisu obrisani.",
      );
      return false;
    } finally {
      setIsClearing(false);
    }
  }

  return {
    activeItems,
    busyItemId,
    clearScanResults,
    closeInspection,
    confirmRepair,
    errorMessage,
    inspection,
    isClearing,
    isLoading,
    isSavingEdit,
    openFile,
    previewItem,
    refreshQueue,
    saveManualEdit,
    selectedItemId,
    setItemStatus,
    successMessage,
  };
}
