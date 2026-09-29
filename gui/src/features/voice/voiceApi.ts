// ==========          GLAS API (STT/TTS preko backend proxy-ja → GLAS :4809)          ==========
/*
 * Glas ide preko domenskog backend proxy-ja `/api/v1/voice/*` do deljenog GLAS
 * servisa (:4809). GUI ne zove GLAS direktno (Tauri CORS). Browser radi snimanje
 * mikrofona (16 kHz WAV) i reprodukciju; STT/TTS računa GLAS.
 *
 *   - `snimiMikrofon()`  otvara mikrofon i vraća kontrolu (stop → WAV 16 kHz)
 *   - `transkribuj()`    WAV → tekst (Whisper, auto sr/en); `lang` opciono forsira
 *   - `sintetizuj()`     tekst → WAV bajtovi (Piper), auto glas po jeziku
 *   - `pustiWav()`       pušta WAV kroz <audio>
 */

import { getApiUrl } from "../../services/httpClient";

/** Glas radi svuda gde ima mikrofona i backend proxy-ja (web i desktop). */
export function glasDostupan(): boolean {
  return typeof navigator !== "undefined" && !!navigator.mediaDevices;
}


// ==========          STT: govor → tekst          ==========

/** WAV (16 kHz mono) → prepoznat tekst preko GLAS proxy-ja. `lang`: auto|sr|en. */
export async function transkribuj(wav: Uint8Array, lang?: string): Promise<string> {
  const fd = new FormData();
  fd.append("file", new Blob([wav as BlobPart], { type: "audio/wav" }), "snimak.wav");
  const q = lang && lang.trim() !== "" ? `?lang=${encodeURIComponent(lang)}` : "";
  const r = await fetch(getApiUrl(`/api/v1/voice/transcribe${q}`), { method: "POST", body: fd });
  if (!r.ok) {
    throw new Error(`GLAS transkripcija nedostupna (HTTP ${r.status})`);
  }
  const j = (await r.json()) as { text?: string };
  return j.text ?? "";
}


// ==========          TTS: tekst → govor          ==========

/** Tekst → WAV bajtovi preko GLAS proxy-ja. `lang`/`voice` opcioni (auto po jeziku). */
export async function sintetizuj(text: string, lang?: string, voice?: string): Promise<Uint8Array> {
  const r = await fetch(getApiUrl("/api/v1/voice/speak"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, lang: lang || null, voice: voice || null }),
  });
  if (!r.ok) {
    throw new Error(`GLAS govor nedostupan (HTTP ${r.status})`);
  }
  return new Uint8Array(await r.arrayBuffer());
}


// ==========          SNIMANJE MIKROFONA          ==========

export type Snimak = {
  /** Zaustavlja snimanje i vraća audio kao WAV 16 kHz mono bajtove. */
  stop: () => Promise<Uint8Array>;
  /** Prekida snimanje bez transkripcije (npr. korisnik odustao). */
  otkazi: () => void;
};

/**
 * Otvara mikrofon i počinje snimanje. Vraća kontrolu; `stop()` daje WAV spreman
 * za Whisper. Baca ako korisnik ne da pristup mikrofonu.
 */
export async function snimiMikrofon(): Promise<Snimak> {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const recorder = new MediaRecorder(stream);
  const chunks: BlobPart[] = [];

  recorder.ondataavailable = (e) => {
    if (e.data.size) {
      chunks.push(e.data);
    }
  };
  recorder.start();

  const ugasiStream = () => stream.getTracks().forEach((t) => t.stop());

  return {
    stop: () =>
      new Promise<Uint8Array>((resolve, reject) => {
        recorder.onstop = () => {
          ugasiStream();
          const blob = new Blob(chunks, { type: "audio/webm" });
          blobUWav16k(blob).then(resolve).catch(reject);
        };
        recorder.stop();
      }),
    otkazi: () => {
      recorder.onstop = () => ugasiStream();
      if (recorder.state !== "inactive") {
        recorder.stop();
      } else {
        ugasiStream();
      }
    },
  };
}


// ==========          REPRODUKCIJA          ==========

let tekuciAudio: HTMLAudioElement | null = null;

/** Pušta WAV bajtove. Prethodni izgovor prekida (jedan glas u datom trenutku). */
export function pustiWav(bytes: Uint8Array): HTMLAudioElement {
  zaustaviGovor();
  const blob = new Blob([bytes as BlobPart], { type: "audio/wav" });
  const url = URL.createObjectURL(blob);
  const audio = new Audio(url);
  tekuciAudio = audio;
  audio.onended = () => {
    URL.revokeObjectURL(url);
    if (tekuciAudio === audio) {
      tekuciAudio = null;
    }
  };
  void audio.play().catch(() => {});
  return audio;
}

/** Prekida tekući izgovor ako ga ima. */
export function zaustaviGovor(): void {
  if (tekuciAudio) {
    tekuciAudio.pause();
    tekuciAudio = null;
  }
}


// ==========          KONVERZIJA U 16 kHz MONO WAV          ==========

/** Dekodira snimak i resample-uje na 16 kHz mono (format koji Whisper očekuje). */
async function blobUWav16k(blob: Blob): Promise<Uint8Array> {
  const arrayBuffer = await blob.arrayBuffer();
  const AudioCtx =
    window.AudioContext ||
    (window as unknown as { webkitAudioContext: typeof AudioContext })
      .webkitAudioContext;
  const ctx = new AudioCtx();
  const decoded = await ctx.decodeAudioData(arrayBuffer);
  void ctx.close();

  const targetRate = 16000;
  const length = Math.max(1, Math.ceil(decoded.duration * targetRate));
  const offline = new OfflineAudioContext(1, length, targetRate);
  const src = offline.createBufferSource();
  src.buffer = decoded;
  src.connect(offline.destination);
  src.start();
  const rendered = await offline.startRendering();
  return kodirajWav(rendered.getChannelData(0), targetRate);
}

/** Piše 16-bit PCM WAV zaglavlje + podatke iz uzoraka [-1, 1]. */
function kodirajWav(samples: Float32Array, sampleRate: number): Uint8Array {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  const upisiTekst = (o: number, s: string) => {
    for (let i = 0; i < s.length; i++) {
      view.setUint8(o + i, s.charCodeAt(i));
    }
  };

  upisiTekst(0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  upisiTekst(8, "WAVE");
  upisiTekst(12, "fmt ");
  view.setUint32(16, 16, true); // PCM chunk size
  view.setUint16(20, 1, true); // format = PCM
  view.setUint16(22, 1, true); // mono
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true); // byte rate
  view.setUint16(32, 2, true); // block align
  view.setUint16(34, 16, true); // bits per sample
  upisiTekst(36, "data");
  view.setUint32(40, samples.length * 2, true);

  let off = 44;
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(off, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    off += 2;
  }
  return new Uint8Array(buffer);
}
