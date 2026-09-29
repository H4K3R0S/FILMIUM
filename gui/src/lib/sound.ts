// ==========          CORE ZVUČNI EFEKTI          ==========

// Kratki UI zvuci iz public/sounds. Isti interfejs koristi ceo program:
// `playSound("startup")`. Autoplay pre interakcije korisnika može biti blokiran
// u pregledaču — u tom slučaju je poziv tih no-op (greška se guta).

export type SoundName =
  | "startup"
  | "menuSlide"
  | "popup"
  | "notification"
  | "error"
  | "completed";

const SOUND_FILES: Record<SoundName, string> = {
  startup: "/sounds/startup-sound-var_1.mp3",
  menuSlide: "/sounds/menu-slide-out.mp3",
  popup: "/sounds/popup_sound.mp3",
  notification: "/sounds/notification_sound.mp3",
  error: "/sounds/error-pop.mp3",
  completed: "/sounds/completed-notify-starting-alert.mp3",
};

let enabled = true;

/** Keš osnovnih audio elemenata (kloniraju se radi preklapanja zvukova). */
const cache = new Map<SoundName, HTMLAudioElement>();

/**
 * Lenjo pravi i kešira osnovni audio element za dati zvuk.
 */
function getBaseAudio(name: SoundName): HTMLAudioElement {
  let base = cache.get(name);

  if (base === undefined) {
    base = new Audio(SOUND_FILES[name]);
    base.preload = "auto";
    cache.set(name, base);
  }

  return base;
}

/**
 * Pušta zvučni efekat. Bezbedno je pozvati i kada autoplay nije dozvoljen.
 */
export function playSound(name: SoundName, volume = 0.6): void {
  if (typeof window === "undefined" || !enabled) {
    return;
  }

  try {
    const node = getBaseAudio(name).cloneNode(true) as HTMLAudioElement;
    node.volume = volume;
    void node.play().catch(() => {
      // Autoplay blokiran ili resurs nedostupan — tiho ignoriši.
    });
  } catch {
    // Nema Audio podrške — ignoriši.
  }
}

/**
 * Uključuje/isključuje sve zvučne efekte (za buduće podešavanje).
 */
export function setSoundEnabled(value: boolean): void {
  enabled = value;
}
