import { open, type OpenDialogOptions } from "@tauri-apps/plugin-dialog";

import { isTauriRuntime } from "./tauriRuntime";

export { isTauriRuntime } from "./tauriRuntime";


// ==========          BIRANJE PUTANJE          ==========

/**
 * Otvara dijalog za izbor putanje.
 *
 * U Tauri prozoru je to pravi sistemski dijalog. U browseru (FILMIUM ćelija)
 * sistemski dijalog ne postoji, pa se putanja upisuje ručno. Prazan unos ili
 * odustajanje vraćaju `null`, isto kao zatvoren Tauri dijalog.
 */
export async function openPathDialog(
  options: OpenDialogOptions = {},
): Promise<string | string[] | null> {
  if (isTauriRuntime()) {
    return open(options);
  }

  const vrsta = options.directory ? "folder" : "fajl";
  const naslov = options.title ?? `Upiši punu putanju (${vrsta})`;
  const pocetna =
    typeof options.defaultPath === "string" ? options.defaultPath : "";

  const unos = window.prompt(naslov, pocetna)?.trim();

  if (!unos) {
    return null;
  }

  return options.multiple ? [unos] : unos;
}
