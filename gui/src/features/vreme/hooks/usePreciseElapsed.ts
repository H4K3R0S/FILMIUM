import { useEffect, useState } from "react";

import { useVreme } from "./useVreme";


/**
 * Vraća precizno (sub-sekundno) proteklo vreme stoperice u ms. Dok stoperica
 * radi, osvežava se svakim frejmom radi glatkog prikaza milisekundi.
 */
export function usePreciseElapsed(): number {
  const { stopwatch } = useVreme();
  // Vreme se ČITA u petlji frejmova, ne pri crtanju. `Date.now()` u telu
  // komponente znači da isti render dva puta daje različit rezultat — React to
  // ne garantuje, a i sam prikaz bi zavisio od toga koliko puta se crtalo.
  const [tickMs, setTickMs] = useState<number | null>(null);

  useEffect(() => {
    if (!stopwatch.running) {
      return;
    }

    let frame = 0;

    const loop = () => {
      setTickMs(Date.now());
      frame = window.requestAnimationFrame(loop);
    };

    frame = window.requestAnimationFrame(loop);

    return () => {
      window.cancelAnimationFrame(frame);
    };
  }, [stopwatch.running]);

  if (stopwatch.running && stopwatch.startedAt !== null) {
    // Pre prvog frejma nema merenja, pa je proteklo tačno nula.
    const sada = tickMs ?? stopwatch.startedAt;
    return stopwatch.baseMs + Math.max(0, sada - stopwatch.startedAt);
  }

  return stopwatch.baseMs;
}
