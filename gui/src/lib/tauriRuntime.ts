// ==========          DETEKCIJA TAURI RUNTIME-A          ==========

/**
 * Da li GUI radi u Tauri prozoru.
 *
 * Izdvojeno iz `window/windowManager.ts` u sopstveni modul bez ijednog
 * uvoza: i `pathPicker.ts`, i `features/voice/voiceApi.ts` moraju da rade i u
 * FILMIUM ćeliji, koja nema CORE window sistem, pa ne smeju da uvoze
 * window manager samo zbog ove jedne provere.
 */
export function isTauriRuntime(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}
