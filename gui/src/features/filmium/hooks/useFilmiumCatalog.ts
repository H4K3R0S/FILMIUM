import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  deleteFilmiumMediaItem,
  getFilmiumMedia,
  setFilmiumFavoriteStatus,
  updateFilmiumMediaItem,
} from "../../../services/filmiumApi";

import type { MediaItem, WatchStatus } from "../../../types/filmium";
import {
  FILMIUM_CATALOG_CHANGED_EVENT,
} from "../events/filmiumCatalogEvents";


// ==========          SVOJSTVA CATALOG HOOKA          ==========

type UseFilmiumCatalogOptions = {
  onMediaDeleted?: (itemId: number) => void;
};


// ==========          FILMIUM KATALOG          ==========

/**
 * Upravlja učitavanjem i akcijama FILMIUM media kataloga.
 */
export function useFilmiumCatalog({
  onMediaDeleted,
}: UseFilmiumCatalogOptions = {}) {
  const [items, setItems] = useState<MediaItem[]>([]);
  const [editingItem, setEditingItem] =
    useState<MediaItem | null>(null);

  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] =
    useState<string | null>(null);

  const [actionErrorMessage, setActionErrorMessage] =
    useState<string | null>(null);

  const [deletingItemId, setDeletingItemId] =
    useState<number | null>(null);

  const [updatingFavoriteItemId, setUpdatingFavoriteItemId] =
    useState<number | null>(null);

  const [updatingWatchStatusItemId, setUpdatingWatchStatusItemId] =
    useState<number | null>(null);

  // ==========          UČITAVANJE KATALOGA          ==========

  /**
   * Ponovo učitava filmove i serije sa FILMIUM API-ja.
   */
  const refreshCatalog = useCallback(async (
    josTraje: () => boolean = () => true,
  ): Promise<void> => {
    try {
      const catalog = await getFilmiumMedia();
      if (!josTraje()) {
        return;
      }
      setItems(catalog);
      setErrorMessage(null);
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : "Učitavanje FILMIUM kataloga nije uspelo.",
      );
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    function handleCatalogChanged(): void {
      void refreshCatalog();
    }

    let ziv = true;
    async function pokreni() {
      await refreshCatalog(() => ziv);
    }
    void pokreni();
    window.addEventListener(
      FILMIUM_CATALOG_CHANGED_EVENT,
      handleCatalogChanged,
    );

    return () => {
      ziv = false;
      window.removeEventListener(
        FILMIUM_CATALOG_CHANGED_EVENT,
        handleCatalogChanged,
      );
    };
  }, [refreshCatalog]);

  // ==========          STATISTIKA KATALOGA          ==========

  const movieCount = useMemo(
    () =>
      items.filter(
        (item) => item.media_type === "movie",
      ).length,
    [items],
  );

  const seriesCount = useMemo(
    () =>
      items.filter(
        (item) => item.media_type === "series",
      ).length,
    [items],
  );

  // ==========          KATALOG AKCIJE          ==========

  /**
   * Dodaje novi ili zamenjuje izmenjeni sadržaj.
   */
  function saveMediaItem(
    item: MediaItem,
    wasUpdated: boolean,
  ): void {
    setItems((currentItems) =>
      wasUpdated
        ? currentItems.map((currentItem) =>
            currentItem.id === item.id
              ? item
              : currentItem,
          )
        : [item, ...currentItems],
    );

    setEditingItem(null);
    setActionErrorMessage(null);
  }


  /**
   * Osvežava sadržaj bez zatvaranja trenutnog režima izmene.
   *
   * Koristi se nakon promene postera, backdropa i drugih akcija
   * koje nisu klasično čuvanje glavne forme.
   */
  function updateMediaItem(item: MediaItem): void {
    setItems((currentItems) =>
      currentItems.map((currentItem) =>
        currentItem.id === item.id
          ? item
          : currentItem,
      ),
    );

    setEditingItem((currentItem) =>
      currentItem?.id === item.id
        ? item
        : currentItem,
    );

    setActionErrorMessage(null);
  }


  /**
   * Otvara postojeći sadržaj u režimu izmene.
   */
  function editMediaItem(item: MediaItem): void {
    setEditingItem(item);
    setActionErrorMessage(null);

    window.requestAnimationFrame(() => {
      document.querySelector(".filmium-form")?.scrollIntoView({
        behavior: "smooth",
        block: "center",
      });
    });
  }

  /**
   * Zatvara režim izmene.
   */
  function cancelMediaEdit(): void {
    setEditingItem(null);
  }

  /**
   * Menja favorite status bez otvaranja forme.
   */
  async function toggleFavorite(
    item: MediaItem,
  ): Promise<void> {
    try {
      setUpdatingFavoriteItemId(item.id);
      setActionErrorMessage(null);

      const updatedItem = await setFilmiumFavoriteStatus(
        item.id,
        !item.is_favorite,
      );

      setItems((currentItems) =>
        currentItems.map((currentItem) =>
          currentItem.id === updatedItem.id
            ? updatedItem
            : currentItem,
        ),
      );

      setEditingItem((currentItem) =>
        currentItem?.id === updatedItem.id
          ? updatedItem
          : currentItem,
      );
    } catch (error) {
      setActionErrorMessage(
        error instanceof Error
          ? error.message
          : "Promena favorite statusa nije uspela.",
      );
    } finally {
      setUpdatingFavoriteItemId(null);
    }
  }

  /**
   * Menja status gledanja bez otvaranja forme.
   *
   * Šalje kompletan zapis kroz PUT (backend zamenjuje sadržaj), pa se
   * ostala polja prenose nepromenjena iz trenutne stavke.
   */
  async function updateWatchStatus(
    item: MediaItem,
    watchStatus: WatchStatus,
  ): Promise<void> {
    if (item.watch_status === watchStatus) {
      return;
    }

    try {
      setUpdatingWatchStatusItemId(item.id);
      setActionErrorMessage(null);

      const updatedItem = await updateFilmiumMediaItem(item.id, {
        title: item.title,
        media_type: item.media_type,
        original_title: item.original_title,
        release_year: item.release_year,
        runtime_minutes: item.runtime_minutes,
        watch_status: watchStatus,
        rating: item.rating,
        notes: item.notes,
        genres: item.genres,
        is_favorite: item.is_favorite,
      });

      setItems((currentItems) =>
        currentItems.map((currentItem) =>
          currentItem.id === updatedItem.id
            ? updatedItem
            : currentItem,
        ),
      );

      setEditingItem((currentItem) =>
        currentItem?.id === updatedItem.id
          ? updatedItem
          : currentItem,
      );
    } catch (error) {
      setActionErrorMessage(
        error instanceof Error
          ? error.message
          : "Promena statusa gledanja nije uspela.",
      );
    } finally {
      setUpdatingWatchStatusItemId(null);
    }
  }

  /**
   * Traži potvrdu i briše sadržaj iz kataloga.
   */
  async function deleteMediaItem(
    item: MediaItem,
  ): Promise<void> {
    const shouldDelete = window.confirm(
      `Da li sigurno želiš da obrišeš "${item.title}"?`,
    );

    if (!shouldDelete) {
      return;
    }

    try {
      setDeletingItemId(item.id);
      setActionErrorMessage(null);

      await deleteFilmiumMediaItem(item.id);

      setItems((currentItems) =>
        currentItems.filter(
          (currentItem) => currentItem.id !== item.id,
        ),
      );

      onMediaDeleted?.(item.id);

      setEditingItem((currentItem) =>
        currentItem?.id === item.id
          ? null
          : currentItem,
      );
    } catch (error) {
      setActionErrorMessage(
        error instanceof Error
          ? error.message
          : "Brisanje FILMIUM sadržaja nije uspelo.",
      );
    } finally {
      setDeletingItemId(null);
    }
  }

  return {
    actionErrorMessage,
    cancelMediaEdit,
    deleteMediaItem,
    deletingItemId,
    editingItem,
    editMediaItem,
    errorMessage,
    isLoading,
    items,
    movieCount,
    refreshCatalog,
    saveMediaItem,
    seriesCount,
    toggleFavorite,
    updateMediaItem,
    updateWatchStatus,
    updatingFavoriteItemId,
    updatingWatchStatusItemId,

  };
}
