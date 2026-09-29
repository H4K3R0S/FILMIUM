// ==========          PREVUČENI .torrent FAJLOVI          ==========
// Zajedničko za celu FILMIUM površinu: šta se prihvata pri prevlačenju i
// kako stranica Torrenti saznaje da je nešto novo sletelo.

/** Događaj na `window` posle uspešnog upisa prevučenog .torrent fajla. */
export const TORRENT_DROPPED_EVENT = "filmium:torrent-dropped";

const TORRENT_EXTENSION = ".torrent";

export function isTorrentFile(file: File): boolean {
  return file.name.toLowerCase().endsWith(TORRENT_EXTENSION);
}

/** Da li se u prevlačenju uopšte nose fajlovi (a ne, recimo, tekst). */
export function dragCarriesFiles(transfer: DataTransfer | null): boolean {
  return transfer !== null && Array.from(transfer.types).includes("Files");
}

/**
 * Deli prevučene fajlove na prihvaćene (.torrent) i odbijene.
 *
 * Sve osim .torrent se izričito odbija — FILMIUM na ovaj način prima samo
 * torrente, pa slika ili video prevučen preko prozora ništa ne pokreće.
 */
export function splitTorrentFiles(
  transfer: DataTransfer | null,
): { accepted: File[]; rejected: string[] } {
  const files = transfer === null ? [] : Array.from(transfer.files);

  return {
    accepted: files.filter(isTorrentFile),
    rejected: files.filter((file) => !isTorrentFile(file)).map((file) => file.name),
  };
}
