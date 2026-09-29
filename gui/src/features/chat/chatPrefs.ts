import { useCallback, useState } from "react";


// ==========          CHAT OKVIR: JEDNO MESTO ZA SVE          ==========
/*
 * Chat je jedna konstrukcija za ceo sistem; domen dobija isti okvir sa svojim
 * izgledom, nikad svoju kopiju.
 *
 * Delovi (i gde su):
 *   - `ChatDock`          — položaj okvira, sklapanje, zaseban prozor, prelaz
 *                           između položaja  (features/chat/ChatDock.tsx)
 *   - `CoreChat`          — razgovor: poruke, unos, fajlovi, brze akcije
 *                           (components/chat/CoreChat.tsx)
 *   - `CoreAssistantChat` — chat spojen na CORE asistenta; prima `scope`,
 *                           `variant` i `suggestions`
 *   - `useSmartLayout`    — raspored ekrana oko chata (skupljanje, preview,
 *                           mesto za panel desno)
 *   - `ChatPanel`         — ekran podešavanja, isti za CORE i za svaki domen
 *   - `chatPrefs.ts`      — OVAJ fajl: ključevi, podrazumevane vrednosti,
 *                           nasleđivanje CORE → domen
 *
 * Novi domen — dva fajla, ništa više:
 *   1. `features/<domen>/<Domen>HubChat.tsx` — sve što je kod tog chata
 *      drugačije: brze akcije, klasa izgleda i (ako domen ima svoj backend)
 *      `assistant` adapter. Renderuje `CoreAssistantChat`:
 *
 *        <CoreAssistantChat scope="<domen>" variant="is-<domen>" title="…"
 *          suggestions={…} assistant={…}
 *          onEngaged={layout.changeTuck}
 *          onPosChange={layout.handlePosChange} />
 *
 *      Bez `assistant` chat razgovara sa CORE asistentom pod svojim opsegom.
 *   2. `styles/<domen>-hub-chat.css` — izgled: `.cdock.is-<domen>`,
 *      `.core-chat.is-<domen>` (primer: styles/codium-hub-chat.css).
 *
 * Uz to `<ChatPanel scope="<domen>" />` u podešavanjima domena. Postavke,
 * položaji, prelazi i raspored oko chata već rade.
 */


// ==========          PODEŠAVANJA CHAT OKVIRA (po opsegu)          ==========
/*
 * Chat okvir je isti u CORE-u i u domenima, ali podešavanja nisu zajednička.
 * CORE drži glavnu postavku; domen je nasleđuje dok sam ne odluči drugačije.
 *
 * Zato se čita u dva koraka: prvo ključ domena, pa CORE-ov. Domen koji ništa
 * nije menjao prati CORE i posle svake kasnije izmene CORE-a — kopiranje
 * vrednosti u domen na prvom otvaranju bi tu vezu prekinulo odmah.
 *
 * Brisanjem domenskog ključa („Vrati na CORE") domen se vraća pod CORE.
 */

export const CORE_SCOPE = "core";


// ==========          SPISAK PODEŠAVANJA (jedini izvor)          ==========
/*
 * Sve što chat okvir ume da zapamti stoji ovde: ključ, tip, podrazumevana
 * vrednost i tekst koji ide u podešavanja. Ranije su isti ključevi i iste
 * podrazumevane vrednosti stajali prepisani u chat komponentama i u ekranu
 * podešavanja — dodavanje postavke je značilo tri izmene, a razilaženje je bilo
 * pitanje vremena.
 *
 * Domen ne dodaje svoje postavke: dobija iste ove pod svojim opsegom i nasleđuje
 * CORE dok ih sam ne promeni.
 */

export type ChatSettingId =
  | "persona"
  | "model"
  | "pos"
  | "suggestions"
  | "cost"
  | "voice"
  | "sttModel"
  | "understandLang"
  | "replyLang"
  | "speakLang"
  | "speakVoice";

export type ChatSettingSpec = {
  id: ChatSettingId;
  kind: "text" | "flag";
  /** Podrazumevana vrednost dok je niko nije promenio (ni CORE ni domen). */
  fallback: string;
  title: string;
  meta: string;
};

export const CHAT_SETTINGS: ChatSettingSpec[] = [
  {
    id: "persona",
    kind: "text",
    fallback: "global",
    title: "Persona",
    meta: "Režim razgovora sa kojim chat počinje.",
  },
  {
    id: "model",
    kind: "text",
    fallback: "",
    title: "Podrazumevani model",
    meta: "Prazno znači „odluči po registru“ — lokalan i besplatan model.",
  },
  {
    id: "pos",
    kind: "text",
    fallback: "bottom",
    title: "Položaj okvira",
    meta: "Dole u toku stranice ili kao panel uz desnu ivicu radnog prostora.",
  },
  {
    id: "suggestions",
    kind: "flag",
    fallback: "true",
    title: "Brze akcije",
    meta: "Predlog-kartice u praznom chatu (plan, analiza, tekst…).",
  },
  {
    id: "cost",
    kind: "flag",
    fallback: "true",
    title: "Prikaz troška",
    meta: "Model, trajanje i cena poslednjeg odgovora ispod razgovora.",
  },
  {
    id: "voice",
    kind: "flag",
    fallback: "false",
    title: "Glasovni odgovori (TTS)",
    meta: "Chat naglas izgovara odgovor asistenta (Piper). Unos glasom je zasebno dugme uz polje.",
  },
  {
    id: "sttModel",
    kind: "text",
    fallback: "medium",
    title: "Model prepoznavanja govora (STT)",
    meta: "Model bira GLAS servis (:4809); ovo se više ne koristi po pozivu.",
  },
  {
    id: "understandLang",
    kind: "text",
    fallback: "auto",
    title: "Jezik razumevanja (govor → tekst)",
    meta: "auto (srpski+engleski), sr ili en. GLAS prepoznaje govor.",
  },
  {
    id: "replyLang",
    kind: "text",
    fallback: "en",
    title: "Jezik odgovora asistenta",
    meta: "Na kom jeziku asistent odgovara (en podrazumevano, sr).",
  },
  {
    id: "speakLang",
    kind: "text",
    fallback: "auto",
    title: "Jezik izgovora (TTS)",
    meta: "auto (po tekstu), sr ili en. Bira glas za naglas izgovor.",
  },
  {
    id: "speakVoice",
    kind: "text",
    fallback: "",
    title: "Glas (TTS)",
    meta: "Konkretan glas iz GLAS /voices, ili prazno = automatski po jeziku.",
  },
];

// ==========          WHISPER MODELI (za STT izbor)          ==========
/*
 * Modeli koji stoje u `models/whisper/` kao `ggml-<id>.bin`. Izbor je ime; Rust
 * (`voice.rs`) sklapa punu putanju. Dodavanje modela ovde + fajla u folder.
 */
export const WHISPER_MODELS: { id: string; label: string }[] = [
  { id: "base", label: "base — najbrži, manje tačan" },
  { id: "medium", label: "medium — balans (podrazumevano)" },
  { id: "large-v1", label: "large-v1 — najtačniji, najsporiji" },
];

/** Podrazumevana vrednost jedne postavke. */
export function chatFallback(id: ChatSettingId): string {
  const spec = CHAT_SETTINGS.find((s) => s.id === id);
  return spec === undefined ? "" : spec.fallback;
}

/** Isto, za prekidače. */
export function chatFlagFallback(id: ChatSettingId): boolean {
  return chatFallback(id) === "true";
}

/**
 * Gde stoji chat okvir.
 *
 * Dva polozaja, ne tri: „u toku stranice" i „traka na dnu" su bili isti prikaz
 * pod dva imena — chat na dashboard-u vec stoji uz dno, centriran u radnom
 * prostoru. Prebacivanje izmedju njih nije menjalo nista sto se vidi, a
 * izgledalo je kao dva razlicita ekrana.
 */
export type ChatPos = "bottom" | "right";

export const CHAT_POSITIONS: { id: ChatPos; label: string }[] = [
  { id: "bottom", label: "Dole (u toku stranice)" },
  { id: "right", label: "Panel desno" },
];

/** Nepoznat ili stari zapis („inline") znaci podrazumevani polozaj. */
export function chatPos(raw: string): ChatPos {
  return raw === "right" ? "right" : "bottom";
}

/** Ključ podešavanja: `chat.<opseg>.<ime>`. */
export function chatKey(scope: string, name: string): string {
  return `chat.${scope}.${name}`;
}

// Persona i model su ranije stajali pod `core.chat.*`. Stari ključ se čita kad
// novog nema, da izbor korisnika ne nestane pri prelasku na opsege.
const STARI_KLJUCEVI: Record<string, string> = {
  "chat.core.persona": "core.chat.persona",
  "chat.core.model": "core.chat.model",
};

function procitaj(key: string): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    const vrednost = window.localStorage.getItem(key);
    if (vrednost !== null) {
      return vrednost;
    }
    const stari = STARI_KLJUCEVI[key];
    return stari === undefined ? null : window.localStorage.getItem(stari);
  } catch {
    // Storage nedostupan (privatni prozor, zabrana) — vredi podrazumevano.
    return null;
  }
}

function upisi(key: string, value: string): void {
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // Pamćenje je pogodnost, ne uslov za rad chata.
  }
}

function obrisi(key: string): void {
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.localStorage.removeItem(key);
  } catch {
    // Isto — brisanje koje ne uspe ne sme da sruši ekran podešavanja.
  }
}

export type ChatSettingState = {
  /** True kad opseg nema svoju vrednost, pa prati CORE. */
  inherited: boolean;
  /** Briše vrednost opsega i vraća ga pod CORE. */
  clear: () => void;
};

/** Vrednost podešavanja za opseg, uz naznaku da li je nasleđena od CORE-a. */
export function readChatSetting(
  scope: string,
  name: string,
  fallback: string,
): { value: string; inherited: boolean } {
  const svoja = procitaj(chatKey(scope, name));
  if (svoja !== null) {
    return { value: svoja, inherited: false };
  }
  if (scope !== CORE_SCOPE) {
    const core = procitaj(chatKey(CORE_SCOPE, name));
    return { value: core ?? fallback, inherited: true };
  }
  return { value: fallback, inherited: false };
}

/**
 * Jedno string podešavanje chata za dati opseg.
 *
 * Bez `fallback` uzima podrazumevanu vrednost iz `CHAT_SETTINGS` — pozivaocu
 * nije posao da je zna napamet.
 */
export function useChatSetting(
  scope: string,
  name: string,
  fallback: string = chatFallback(name as ChatSettingId),
): [string, (next: string) => void, ChatSettingState] {
  const [stanje, setStanje] = useState(() =>
    readChatSetting(scope, name, fallback),
  );

  const postavi = useCallback(
    (next: string) => {
      upisi(chatKey(scope, name), next);
      setStanje({ value: next, inherited: false });
    },
    [scope, name],
  );

  const clear = useCallback(() => {
    obrisi(chatKey(scope, name));
    setStanje(readChatSetting(scope, name, fallback));
  }, [scope, name, fallback]);

  return [stanje.value, postavi, { inherited: stanje.inherited, clear }];
}

/** Isto, za prekidače (true/false). */
export function useChatFlag(
  scope: string,
  name: string,
  fallback: boolean = chatFlagFallback(name as ChatSettingId),
): [boolean, (next: boolean) => void, ChatSettingState] {
  const [tekst, postaviTekst, stanje] = useChatSetting(
    scope,
    name,
    String(fallback),
  );
  const postavi = useCallback(
    (next: boolean) => postaviTekst(String(next)),
    [postaviTekst],
  );
  return [tekst === "true", postavi, stanje];
}
