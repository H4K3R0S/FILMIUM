import { useCallback, useEffect, useState } from "react";

import {
  deleteWishlistEntry,
  getWishlist,
  reconcileWishlist,
} from "../../../services/filmiumWishlistApi";
import type {
  WishlistEntry,
  WishlistRemovedEntry,
} from "../../../types/filmiumWishlist";
import { FILMIUM_CATALOG_CHANGED_EVENT } from "../events/filmiumCatalogEvents";


// ==========          FILMIUM LISTA „ZA PREUZETI"          ==========

/**
 * Učitava, usklađuje i osvežava listu naslova koje korisnik planira da nabavi.
 *
 * Usklađivanje (reconcile) uklanja naslov iz liste čim isti sadržaj uđe u
 * biblioteku (poklapanje po TMDB ID-u ili naslovu+godini), pa ga ne treba
 * ručno brisati.
 */
export function useFilmiumWishlist() {
  const [entries, setEntries] = useState<WishlistEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Poslednje automatski uklonjene stavke — za kratko obaveštenje.
  const [removedNotice, setRemovedNotice] = useState<WishlistRemovedEntry[]>(
    [],
  );

  const refresh = useCallback(async (): Promise<void> => {
    try {
      const loaded = await getWishlist();
      setEntries(loaded);
      setErrorMessage(null);
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : "Učitavanje liste za preuzimanje nije uspelo.",
      );
    } finally {
      setIsLoading(false);
    }
  }, []);

  const reconcile = useCallback(async (): Promise<void> => {
    try {
      const result = await reconcileWishlist();
      if (result.removed.length > 0) {
        setRemovedNotice(result.removed);
        await refresh();
      }
    } catch {
      // Usklađivanje je pomoćno — tiho ignoriši grešku.
    }
  }, [refresh]);

  // Prvo učitavanje + usklađivanje pri ulasku u domen.
  useEffect(() => {
    void (async () => {
      await refresh();
      await reconcile();
    })();
  }, [refresh, reconcile]);

  // Kad se katalog promeni (uvoz, ručni unos) — ponovo uskladi.
  useEffect(() => {
    function handleCatalogChanged(): void {
      void reconcile();
    }

    window.addEventListener(
      FILMIUM_CATALOG_CHANGED_EVENT,
      handleCatalogChanged,
    );
    return () => {
      window.removeEventListener(
        FILMIUM_CATALOG_CHANGED_EVENT,
        handleCatalogChanged,
      );
    };
  }, [reconcile]);

  const removeEntry = useCallback(
    async (entryId: number): Promise<void> => {
      await deleteWishlistEntry(entryId);
      setEntries((current) =>
        current.filter((entry) => entry.id !== entryId),
      );
    },
    [],
  );

  const clearRemovedNotice = useCallback((): void => {
    setRemovedNotice([]);
  }, []);

  return {
    entries,
    isLoading,
    errorMessage,
    refresh,
    reconcile,
    removeEntry,
    removedNotice,
    clearRemovedNotice,
  };
}
