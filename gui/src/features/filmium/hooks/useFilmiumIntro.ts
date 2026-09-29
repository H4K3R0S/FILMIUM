import { useEffect, useState } from "react";


// ==========          FILMIUM PALJENJE          ==========

/**
 * Redosled ulaska elemenata FILMIUM ekrana (ms od montiranja stranice).
 * Sidebar (2s) vodi AppShell; ostalo je u nadležnosti ove stranice.
 */
const CAROUSEL_DELAY_MS = 2500;
const SHELVES_DELAY_MS = 2500;
const SEARCH_DELAY_MS = 3000;

export type FilmiumIntroStage = {
  /** Search/toolbar traka — spušta se odozgo. */
  searchReady: boolean;
  /** Featured carousel — sliduje sa desne strane. */
  carouselReady: boolean;
  /** Kartice (FILMOVI redovi) — podižu se odozdo. */
  shelvesReady: boolean;
};

const ALL_READY: FilmiumIntroStage = {
  searchReady: true,
  carouselReady: true,
  shelvesReady: true,
};

const ALL_HIDDEN: FilmiumIntroStage = {
  searchReady: false,
  carouselReady: false,
  shelvesReady: false,
};

/**
 * Postepeno otkriva delove FILMIUM ekrana — ali samo jednom po ulasku u domen.
 *
 * `alreadyPlayed` (čuvano na nivou workspace-a, van remount-a stranice) znači
 * da je animacija već odigrana pri ulasku u domen; tada se sve odmah prikaže
 * bez ponavljanja (npr. na klik Home dugmeta ili prelazak pod-ruta). Pri prvom
 * ulasku animira i pozove `onPlayed` da to zabeleži.
 *
 * Vreme se meri od montiranja, pa se elementi pojavljuju u zadatom trenutku
 * bez obzira kada im stigne sadržaj (katalog, filteri).
 */
export function useFilmiumIntro(
  alreadyPlayed: boolean,
  onPlayed: () => void,
): FilmiumIntroStage {
  const [stage, setStage] = useState<FilmiumIntroStage>(
    alreadyPlayed ? ALL_READY : ALL_HIDDEN,
  );

  useEffect(() => {
    if (alreadyPlayed) {
      return;
    }

    onPlayed();

    const timers = [
      window.setTimeout(
        () =>
          setStage((previous) => ({
            ...previous,
            carouselReady: true,
          })),
        CAROUSEL_DELAY_MS,
      ),
      window.setTimeout(
        () =>
          setStage((previous) => ({
            ...previous,
            shelvesReady: true,
          })),
        SHELVES_DELAY_MS,
      ),
      window.setTimeout(
        () =>
          setStage((previous) => ({
            ...previous,
            searchReady: true,
          })),
        SEARCH_DELAY_MS,
      ),
    ];

    return () => {
      timers.forEach((timer) => window.clearTimeout(timer));
    };
    // Prazne zavisnosti su namerne: animacija se pušta jednom po montiranju
    // stranice. Da `alreadyPlayed` uđe u zavisnosti, `onPlayed` bi ga promenio
    // i efekat bi se odmah ponovo pokrenuo — animacija bi se prekinula u pola.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return stage;
}
