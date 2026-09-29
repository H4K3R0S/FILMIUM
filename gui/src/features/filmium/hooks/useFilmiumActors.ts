import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

import { getFilmiumActors } from "../../../services/filmiumActorsApi";
import type { FilmiumActorListItem } from "../../../types/filmiumActors";

const PAGE_SIZE = 60;
// Pretraga čeka da korisnik prestane da kuca (izbegava zahtev po slovu).
const SEARCH_DEBOUNCE_MS = 300;


// ==========          FILMIUM GLUMCI — LISTA (HOOK)          ==========

/**
 * Upravlja učitavanjem liste glumaca: pretraga po imenu (debounced) i
 * progresivna paginacija (limit/offset) — „učitaj još" dodaje sledeću
 * stranicu umesto da zameni celu listu.
 */
export function useFilmiumActors() {
  const [searchInput, setSearchInput] = useState("");
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<FilmiumActorListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Debounce: pretraga se šalje tek kad korisnik stane sa kucanjem.
  useEffect(() => {
    const timer = window.setTimeout(() => {
      setQuery(searchInput.trim());
    }, SEARCH_DEBOUNCE_MS);

    return () => window.clearTimeout(timer);
  }, [searchInput]);

  // Redni broj zahteva — kasni odgovor prethodne pretrage ne sme da
  // prepiše rezultat novije.
  const requestId = useRef(0);

  const loadFirstPage = useCallback(async (search: string): Promise<void> => {
    const currentRequest = ++requestId.current;
    setIsLoading(true);
    setErrorMessage(null);

    try {
      const response = await getFilmiumActors({
        q: search,
        limit: PAGE_SIZE,
        offset: 0,
      });

      if (requestId.current !== currentRequest) {
        return;
      }
      setItems(response.items);
      setTotal(response.total);
    } catch (error) {
      if (requestId.current !== currentRequest) {
        return;
      }
      setErrorMessage(
        error instanceof Error
          ? error.message
          : "Učitavanje glumaca nije uspelo.",
      );
      setItems([]);
      setTotal(0);
    } finally {
      if (requestId.current === currentRequest) {
        setIsLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    void loadFirstPage(query);
  }, [query, loadFirstPage]);

  /** Dodaje sledeću stranicu (limit/offset) na već prikazanu listu. */
  const loadMore = useCallback(async (): Promise<void> => {
    if (isLoading || isLoadingMore || items.length >= total) {
      return;
    }

    const currentRequest = requestId.current;
    setIsLoadingMore(true);

    try {
      const response = await getFilmiumActors({
        q: query,
        limit: PAGE_SIZE,
        offset: items.length,
      });

      if (requestId.current !== currentRequest) {
        return;
      }
      setItems((current) => [...current, ...response.items]);
      setTotal(response.total);
    } catch (error) {
      if (requestId.current !== currentRequest) {
        return;
      }
      setErrorMessage(
        error instanceof Error
          ? error.message
          : "Učitavanje dodatnih glumaca nije uspelo.",
      );
    } finally {
      if (requestId.current === currentRequest) {
        setIsLoadingMore(false);
      }
    }
  }, [isLoading, isLoadingMore, items.length, total, query]);

  return {
    searchInput,
    setSearchInput,
    items,
    total,
    isLoading,
    isLoadingMore,
    errorMessage,
    hasMore: items.length < total,
    loadMore,
  };
}
