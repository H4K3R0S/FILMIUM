import { useEffect, useState } from "react";

import { getFilmiumMediaCast } from "../../../services/filmiumActorsApi";
import type { FilmiumMediaCastMember } from "../../../types/filmiumActors";


// ==========          FILMIUM GLUMAČKA POSTAVA NASLOVA (HOOK)          ==========

/**
 * Učitava glumačku postavu jednog naslova (`mediaId`). Promena naslova
 * (navigacija na drugi film/seriju bez punog reload-a rute) ponovo
 * učitava postavu.
 *
 * Pozadinski posao obogaćivanja režisera upisuje u istu bazu — backend
 * čitanja imaju `busy_timeout` pa su tolerantna, ali prolazna greška
 * (npr. "database is locked") ovde samo prazni listu; sledeće učitavanje
 * (nov `mediaId` ili remount stranice) pokušava ponovo.
 */
export function useFilmiumMediaCast(mediaId: number | null) {
  const [cast, setCast] = useState<FilmiumMediaCastMember[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (mediaId === null) {
      setCast([]);
      setTotal(0);
      return;
    }

    let isMounted = true;
    setIsLoading(true);
    setErrorMessage(null);

    getFilmiumMediaCast(mediaId, 0)
      .then((response) => {
        if (!isMounted) {
          return;
        }
        setCast(response.cast);
        setTotal(response.total);
      })
      .catch((error: unknown) => {
        if (!isMounted) {
          return;
        }
        setErrorMessage(
          error instanceof Error
            ? error.message
            : "Učitavanje glumačke postave nije uspelo.",
        );
        setCast([]);
        setTotal(0);
      })
      .finally(() => {
        if (isMounted) {
          setIsLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [mediaId]);

  return { cast, total, isLoading, errorMessage };
}
