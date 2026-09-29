import { useCallback, useLayoutEffect, useRef } from "react";


// ==========          UKLAPANJE TEKSTA U N REDOVA          ==========

type FitOptions = {
  /** Najveći font (px) — polazna, „lepa" veličina. */
  maxFontPx: number;
  /** Najmanji font (px) — dokle sme da se smanji da bi stalo. */
  minFontPx: number;
  /** Maksimalan broj redova (podrazumevano 2). */
  maxLines?: number;
};


/**
 * Smanjuje font elementa dok njegov sadržaj ne stane u `maxLines` redova.
 *
 * Naslovi filmova umeju da se preliju u 3–4 reda iako po širini ima mesta za
 * manje. Umesto sečenja, biramo najveći font (između min i max) pri kome tekst
 * staje u dozvoljen broj redova. Reaguje na promenu teksta i širine kontejnera.
 */
export function useFitToLines<T extends HTMLElement>(
  text: string,
  { maxFontPx, minFontPx, maxLines = 2 }: FitOptions,
) {
  const ref = useRef<T | null>(null);

  const fit = useCallback(() => {
    const element = ref.current;
    if (!element) {
      return;
    }

    // Ratio je odnos visine reda i fonta (npr. line-height: 0.92) — konstantan
    // dok menjamo font, pa dozvoljena visina = maxLines * ratio * font.
    element.style.fontSize = `${maxFontPx}px`;
    const computed = window.getComputedStyle(element);
    const lineHeightPx = Number.parseFloat(computed.lineHeight);
    const ratio =
      Number.isFinite(lineHeightPx) && lineHeightPx > 0
        ? lineHeightPx / maxFontPx
        : 1.2;

    for (let fontPx = maxFontPx; fontPx >= minFontPx; fontPx -= 1) {
      element.style.fontSize = `${fontPx}px`;
      const allowed = Math.ceil(ratio * fontPx * maxLines) + 1;
      if (element.scrollHeight <= allowed) {
        break;
      }
    }
  }, [maxFontPx, minFontPx, maxLines]);

  useLayoutEffect(() => {
    fit();

    const element = ref.current;
    if (!element || typeof ResizeObserver === "undefined") {
      return;
    }

    // Prati promenu širine kontejnera (npr. otvaranje panela, resize prozora).
    const observer = new ResizeObserver(() => fit());
    if (element.parentElement) {
      observer.observe(element.parentElement);
    }
    return () => observer.disconnect();
  }, [fit, text]);

  return ref;
}
