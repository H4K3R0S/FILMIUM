import { useEffect, useState } from "react";


// ==========          ODLOŽENO OTKRIVANJE          ==========

/**
 * Vraća `true` tek kada prođe `delayMs` od montiranja komponente.
 *
 * Koristi se za postepeni ulazak FILMIUM elemenata (search traka, carousel,
 * kartice). Meri se od montiranja, pa se elementi pojavljuju u zadatom
 * trenutku bez obzira kada im stigne sadržaj.
 */
export function useRevealAfter(delayMs: number): boolean {
  const [revealed, setRevealed] = useState<boolean>(delayMs <= 0);

  useEffect(() => {
    if (revealed) {
      return;
    }

    const timer = window.setTimeout(() => {
      setRevealed(true);
    }, delayMs);

    return () => {
      window.clearTimeout(timer);
    };
  }, [delayMs, revealed]);

  return revealed;
}
