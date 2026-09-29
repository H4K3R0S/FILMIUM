// ==========          PAMETNA PRETRAGA FILMIUM KATALOGA          ==========
/*
 * Tolerantno poklapanje naslova/polja bez obzira na dijakritiku i redosled
 * reči. Upit se „foldује" (svodi na ASCII: Duša -> dusa) i cepa na reči; bilo
 * koja reč koja se nađe u tekstu stavke donosi poene. Naslov nosi veći bonus
 * od sporednih polja, a tačan neprekidan naslov najveći — tako najbolji
 * pogodak isplivava na vrh (rangirane pretpostavke).
 *
 * Sve je čisto (bez stanja/mreže) da bude lako testirati i da radi na već
 * učitanom katalogu u pregledaču.
 */

/** Polja stavke po kojima se pretražuje. */
export interface SearchableFields {
  /** Primarni naslov (najveći bonus pri pogotku). */
  title: string;
  /** Ostala polja (original/engleski naslov, opis, žanr, glumci, keyword-i). */
  secondary?: string[];
}

/** Najkraći token koji se uzima u obzir (kraći bi izlistao previše). */
const MIN_TOKEN_LENGTH = 2;

const TITLE_TOKEN_WEIGHT = 2;
const SECONDARY_TOKEN_WEIGHT = 1;
const EXACT_TITLE_BONUS = 5;

/**
 * Svodi tekst na malu ASCII latinicu: NFD + uklanjanje akcenata pokriva
 * š/ž/č/ć i strane akcente (é…); đ nema dekompoziciju pa se maplja posebno
 * na „dj".
 */
export function foldDiacritics(text: string): string {
  return (text ?? "")
    .toLowerCase()
    .replace(/đ/g, "dj")
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "");
}

/** Cepa foldovan upit na tokene dužine >= MIN_TOKEN_LENGTH. */
function tokenize(folded: string): string[] {
  return folded.split(/\s+/).filter((token) => token.length >= MIN_TOKEN_LENGTH);
}

/**
 * Vraća skor poklapanja upita nad poljima stavke. 0 znači „nema pogotka".
 * Veći skor = bolji pogodak (koristi se za rangiranje rezultata).
 */
export function scoreSearch(query: string, fields: SearchableFields): number {
  const foldedQuery = foldDiacritics(query).trim();
  if (foldedQuery === "") {
    return 0;
  }

  const foldedTitle = foldDiacritics(fields.title);
  const foldedSecondary = (fields.secondary ?? [])
    .map((value) => foldDiacritics(value))
    .join(" ");

  const tokens = tokenize(foldedQuery);
  if (tokens.length === 0) {
    return 0;
  }

  let score = 0;
  for (const token of tokens) {
    if (foldedTitle.includes(token)) {
      score += TITLE_TOKEN_WEIGHT;
    } else if (foldedSecondary.includes(token)) {
      score += SECONDARY_TOKEN_WEIGHT;
    }
  }

  // Tačan, neprekidan pun upit u naslovu — najjači signal.
  if (foldedTitle === foldedQuery) {
    score += EXACT_TITLE_BONUS;
  }

  return score;
}
