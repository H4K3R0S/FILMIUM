import { useCallback, useEffect, useState } from "react";


// ==========          KONSTANTE          ==========

const STORAGE_KEY = "core.sidebar.pinned";

/** Odloženo pojavljivanje sidebar-a pri pokretanju aplikacije. */
const STARTUP_DELAY_MS = 2000;


// ==========          POMOĆNE FUNKCIJE          ==========

/**
 * Čita zapamćeno stanje zakačenosti sidebar-a. Podrazumevano je zakačen.
 */
function readPinned(): boolean {
  if (typeof window === "undefined") {
    return true;
  }

  const stored = window.localStorage.getItem(STORAGE_KEY);

  if (stored === null) {
    return true;
  }

  return stored === "true";
}


// ==========          VIDLJIVOST SIDEBAR-A          ==========

export type SidebarVisibility = {
  /** Da li je sidebar zakačen (zaključan i uvek vidljiv). */
  isPinned: boolean;
  /** Da li je sidebar trenutno prikazan na ekranu. */
  isVisible: boolean;
  /** Prebacuje zakačenost i pamti izbor u localStorage. */
  togglePinned: () => void;
  /** Otkriva sidebar kada miš priđe levoj ivici (samo ako nije zakačen). */
  reveal: () => void;
  /** Sakriva sidebar kada miš napusti oblast (samo ako nije zakačen). */
  hide: () => void;
};

/**
 * Upravlja zakačenošću, auto-skrivanjem i startnom animacijom sidebar-a.
 *
 * Pri pokretanju sidebar sačeka {@link STARTUP_DELAY_MS} pa se pojavi.
 * Kada nije zakačen, sidebar se skriva i otkriva na osnovu poziva
 * {@link reveal} i {@link hide}.
 */
export function useSidebarVisibility(): SidebarVisibility {
  const [isPinned, setIsPinned] = useState<boolean>(readPinned);
  const [isRevealed, setIsRevealed] = useState<boolean>(false);
  const [hasStarted, setHasStarted] = useState<boolean>(false);

  // ==========          STARTNA ANIMACIJA          ==========

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setHasStarted(true);
    }, STARTUP_DELAY_MS);

    return () => {
      window.clearTimeout(timer);
    };
  }, []);

  // ==========          AKCIJE          ==========

  const togglePinned = useCallback(() => {
    setIsPinned((previous) => {
      const next = !previous;

      if (typeof window !== "undefined") {
        window.localStorage.setItem(STORAGE_KEY, String(next));
      }

      // Prelazak na zakačeno poništava privremeno otkrivanje.
      if (next) {
        setIsRevealed(false);
      }

      return next;
    });
  }, []);

  const reveal = useCallback(() => {
    setIsRevealed(true);
  }, []);

  const hide = useCallback(() => {
    setIsRevealed(false);
  }, []);

  // ==========          IZVEDENO STANJE          ==========

  // Pre kraja startne pauze sidebar je skriven da bi mogao da sklizne unutra.
  const isVisible = hasStarted && (isPinned || isRevealed);

  return {
    isPinned,
    isVisible,
    togglePinned,
    reveal,
    hide,
  };
}
