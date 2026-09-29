import {
  useCallback,
  useEffect,
  useState,
} from "react";

import { getFilmiumActivity } from "../../../services/filmiumApi";
import type { FilmiumActivityItem } from "../../../types/filmium";


// ==========          FILMIUM ACTIVITY HOOK          ==========

/**
 * Upravlja učitavanjem i osvežavanjem FILMIUM istorije.
 */
export function useFilmiumActivity() {
  const [activityItems, setActivityItems] =
    useState<FilmiumActivityItem[]>([]);

  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] =
    useState<string | null>(null);

  /**
   * Učitava najnovije FILMIUM događaje.
   */
  const loadActivity = useCallback(async (
    josTraje: () => boolean = () => true,
  ): Promise<void> => {
    try {
      setIsLoading(true);

      const loadedItems = await getFilmiumActivity();

      if (!josTraje()) {
        return;
      }
      setActivityItems(loadedItems);
      setErrorMessage(null);
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : "Učitavanje FILMIUM istorije nije uspelo.",
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
      await loadActivity(() => ziv);
    }
    void pokreni();
    return () => {
      ziv = false;
    };
  }, [loadActivity]);

  return {
    activityItems,
    errorMessage,
    isLoading,
    refreshActivity: loadActivity,
  };
}