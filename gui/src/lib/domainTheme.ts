// ==========          DOMAIN THEME REZOLUCIJA          ==========

/** Poznati domeni; 'core' je podrazumevani interfejs. */
export const KNOWN_DOMAINS = [
  "core",
  "codium",
  "filmium",
  "imperium",
  "kalima",
] as const;

export type DomainId = (typeof KNOWN_DOMAINS)[number];

/**
 * Određuje aktivni domen za temu. FILMIUM radni prostor ima prednost
 * po ruti; inače se koristi domen iz CORE konteksta. Nepoznato → 'core'.
 */
export function resolveDomainId(
  pathname: string,
  activeDomainId: string | null,
): DomainId {
  // Domenske rute imaju prednost nad kontekstom (tema prati ekran).
  const routeMatch = pathname.match(
    /^\/(codium|filmium|imperium|kalima)/,
  );

  if (routeMatch) {
    return routeMatch[1] as DomainId;
  }

  const normalized = (activeDomainId ?? "").toLowerCase();

  return (KNOWN_DOMAINS as readonly string[]).includes(normalized)
    ? (normalized as DomainId)
    : "core";
}


// ==========          VIDLJIVOST SATA PO DOMENU          ==========

/** localStorage ključ za vidljivost sata datog domena. */
export function clockSettingKey(domainId: string): string {
  return `core.clock.${domainId}`;
}

/**
 * Podrazumevana vidljivost sata po domenu. CODIUM je razvojno okruženje —
 * sat je podrazumevano isključen; ostali domeni ga prikazuju.
 */
export function defaultClockVisible(domainId: string): boolean {
  return domainId !== "codium";
}

/** Čita trenutnu vidljivost sata za domen (localStorage → default). */
export function readClockVisible(domainId: string): boolean {
  if (typeof window === "undefined") {
    return defaultClockVisible(domainId);
  }
  const stored = window.localStorage.getItem(clockSettingKey(domainId));
  if (stored === null) {
    return defaultClockVisible(domainId);
  }
  return stored === "true";
}
