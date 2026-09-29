// ==========          BOOT HOOK          ==========
import { useContext, useEffect, useState } from "react";

import { BootContext } from "./bootContext";


/**
 * Vraća `true` tek kada prođe `delayMs` od početka boot sekvence.
 *
 * Uzima u obzir vreme koje je već proteklo, pa se i komponente montirane
 * kasnije (npr. pri promeni rute) otkrivaju u ispravnom trenutku. Ako je
 * vreme već prošlo, otkriva se odmah.
 *
 * @param delayMs Koliko milisekundi nakon paljenja element treba da uđe.
 */
export function useBootReveal(delayMs: number): boolean {
  const context = useContext(BootContext);
  // Ako komponenta stoji van provajdera, početak je trenutak njenog prvog
  // crtanja — ali izmeren jednom, ne pri svakom crtanju.
  const [fallbackStartedAt] = useState<number>(() => Date.now());
  const startedAt = context?.startedAt ?? fallbackStartedAt;

  const [revealed, setRevealed] = useState<boolean>(
    () => Date.now() - startedAt >= delayMs,
  );

  useEffect(() => {
    if (revealed) {
      return;
    }

    const remaining = Math.max(0, delayMs - (Date.now() - startedAt));

    const timer = window.setTimeout(() => {
      setRevealed(true);
    }, remaining);

    return () => {
      window.clearTimeout(timer);
    };
  }, [delayMs, startedAt, revealed]);

  return revealed;
}
