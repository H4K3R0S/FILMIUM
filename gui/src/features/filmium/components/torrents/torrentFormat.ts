// ==========          FORMATIRANJE: TORRENTI          ==========

const UNITS = ["B", "KB", "MB", "GB", "TB"];

/** Veličina fajla u čitljivom obliku, sa zarezom kao decimalnim znakom. */
export function formatBytes(value: number): string {
  if (value <= 0) {
    return "0 B";
  }

  let size = value;
  let unit = 0;

  while (size >= 1024 && unit < UNITS.length - 1) {
    size /= 1024;
    unit += 1;
  }

  const rounded = unit === 0 ? String(Math.round(size)) : size.toFixed(1);
  return `${rounded.replace(".", ",")} ${UNITS[unit]}`;
}

/** Preostalo vreme u obliku `1h 05m` ili `45s`; bez podatka daje crticu. */
export function formatEta(seconds: number | null): string {
  if (seconds === null || seconds <= 0) {
    return "—";
  }

  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);

  if (hours > 0) {
    return `${hours}h ${String(minutes).padStart(2, "0")}m`;
  }

  if (minutes > 0) {
    return `${minutes}m`;
  }

  return `${seconds}s`;
}


/**
 * Ishod grupne radnje (Start/Stop) u srpskom obliku: „1 torrent",
 * „2 torrenta", „5 torrenta".
 *
 * Nula nije greška — znači da nijedan torrent nije bio u stanju na koje ta
 * radnja deluje, pa poruka to i kaže.
 */
export function bulkNotice(
  verb: "Pokrenut" | "Pauziran",
  count: number,
): string {
  if (count === 0) {
    return verb === "Pokrenut"
      ? "Nema torrenta koji bi se pokrenuo."
      : "Nema torrenta u toku koji bi se pauzirao.";
  }

  if (count === 1) {
    return `${verb} 1 torrent.`;
  }

  if (count < 5) {
    return `${verb}a su ${count} torrenta.`;
  }

  return `${verb}o je ${count} torrenta.`;
}
