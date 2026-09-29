// ==========          INTRO („PALJENJE") — JEDNOM PO POKRETANJU          ==========
// Jedini izvor istine za: (1) da li je intro već odigran u OVOM pokretanju
// aplikacije (sessionStorage — preživi navigaciju/remount, resetuje se pri novom
// startu) i (2) da li je intro ugašen u Podešavanjima (localStorage).

export const INTRO_SESSION_KEY = "filmium.intro.played";
export const INTRO_SETTING_KEY = "core.filmium.introAnimation";

/** true = intro NE treba puštati (već odigran u ovoj sesiji ILI ugašen u podešavanjima). */
export function introAlreadyDone(): boolean {
  try {
    if (window.localStorage.getItem(INTRO_SETTING_KEY) === "false") return true;
  } catch { /* privatni režim */ }
  try {
    return window.sessionStorage.getItem(INTRO_SESSION_KEY) === "1";
  } catch {
    return false;
  }
}

/** Zabeleži da je intro odigran u ovom pokretanju aplikacije. */
export function markIntroDone(): void {
  try { window.sessionStorage.setItem(INTRO_SESSION_KEY, "1"); } catch { /* privatni režim */ }
}
