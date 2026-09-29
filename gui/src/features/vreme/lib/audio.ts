// ==========          VREME AUDIO (UGRAĐENI TONOVI)          ==========

// Ugrađene melodije preko Web Audio (bez fajlova). Kasnije se lako dodaju
// .mp3 melodije preko istog interfejsa (playMelody / stopMelody).

export type MelodyDefinition = {
  id: string;
  name: string;
  /** Frekvencije nota (Hz) koje se sviraju u krug. */
  notes: number[];
  /** Trajanje jedne note u sekundama. */
  noteDuration: number;
  /** Pauza između ciklusa u sekundama. */
  gap: number;
  type: OscillatorType;
};

export const MELODIES: MelodyDefinition[] = [
  {
    id: "klasik",
    name: "Klasik",
    notes: [880, 880, 0, 880, 880, 0],
    noteDuration: 0.18,
    gap: 0.5,
    type: "sine",
  },
  {
    id: "zvono",
    name: "Zvono",
    notes: [1320, 990, 1320, 990],
    noteDuration: 0.22,
    gap: 0.35,
    type: "triangle",
  },
  {
    id: "digital",
    name: "Digital",
    notes: [660, 990, 1320, 990],
    noteDuration: 0.12,
    gap: 0.2,
    type: "square",
  },
  {
    id: "blago",
    name: "Blago",
    notes: [523, 659, 784, 659],
    noteDuration: 0.4,
    gap: 0.6,
    type: "sine",
  },
];

/**
 * Vraća melodiju po id-u ili prvu kao rezervu.
 */
export function getMelody(id: string): MelodyDefinition {
  return MELODIES.find((melody) => melody.id === id) ?? MELODIES[0];
}


// ==========          REPRODUKCIJA          ==========

let audioContext: AudioContext | null = null;
let loopTimer: number | null = null;

/**
 * Lenjo kreira (ili nastavlja) deljeni AudioContext.
 */
function ensureContext(): AudioContext | null {
  if (typeof window === "undefined") {
    return null;
  }

  const AudioCtor =
    window.AudioContext ??
    (window as unknown as { webkitAudioContext?: typeof AudioContext })
      .webkitAudioContext;

  if (!AudioCtor) {
    return null;
  }

  if (audioContext === null) {
    audioContext = new AudioCtor();
  }

  void audioContext.resume();

  return audioContext;
}

/**
 * Svira jedan ciklus nota melodije počev od datog trenutka.
 */
function scheduleCycle(
  context: AudioContext,
  melody: MelodyDefinition,
): number {
  let cursor = context.currentTime;

  for (const frequency of melody.notes) {
    if (frequency > 0) {
      const oscillator = context.createOscillator();
      const gain = context.createGain();

      oscillator.type = melody.type;
      oscillator.frequency.value = frequency;

      // Blaga anvelopa da ton ne "pucketa".
      gain.gain.setValueAtTime(0.0001, cursor);
      gain.gain.exponentialRampToValueAtTime(0.28, cursor + 0.02);
      gain.gain.exponentialRampToValueAtTime(
        0.0001,
        cursor + melody.noteDuration,
      );

      oscillator.connect(gain);
      gain.connect(context.destination);
      oscillator.start(cursor);
      oscillator.stop(cursor + melody.noteDuration);
    }

    cursor += melody.noteDuration;
  }

  const cycleMs = (cursor - context.currentTime + melody.gap) * 1000;

  return cycleMs;
}

/**
 * Pušta melodiju u petlji dok se ne pozove stopMelody.
 */
export function playMelody(id: string): void {
  stopMelody();

  const context = ensureContext();

  if (context === null) {
    return;
  }

  const melody = getMelody(id);

  const runCycle = () => {
    const cycleMs = scheduleCycle(context, melody);
    loopTimer = window.setTimeout(runCycle, cycleMs);
  };

  runCycle();
}

/**
 * Zaustavlja tekuću melodiju.
 */
export function stopMelody(): void {
  if (loopTimer !== null) {
    window.clearTimeout(loopTimer);
    loopTimer = null;
  }
}

/**
 * Kratko odsvira melodiju (za pregled pri izboru).
 */
export function previewMelody(id: string): void {
  const context = ensureContext();

  if (context === null) {
    return;
  }

  scheduleCycle(context, getMelody(id));
}
