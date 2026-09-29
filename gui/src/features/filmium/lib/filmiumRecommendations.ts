// ==========          FILMIUM PREPORUKE (ČISTA LOGIKA)          ==========
//
// Skoreri i kaskadni dedup za tri odeljka detalj-stranice:
// Povezani (TMDB), Preporučeni (naziv+žanr+ključne reči), Po žanru.
// Izdvojeno iz stranice radi testiranja bez React-a.

import type { MediaItem, RelatedTitle } from "../../../types/filmium";


// Ponderi: ključne reči najjači signal, pa žanr, pa naziv (tiebreak).
const W_KEYWORD = 5;
const W_GENRE = 3;
const W_TITLE = 1;

// Tokeni naziva kraći od ovoga se ignorišu (štite od lažnih pogodaka
// tipa „Walking Tall" ↔ „Chaos Walking").
const MIN_TITLE_TOKEN = 4;


/** Domaće/Anime preporuke samo iz iste kategorije; regular bez granice. */
function categoryAllows(current: MediaItem, candidate: MediaItem): boolean {
  const category = current.content_category ?? "regular";
  if (category !== "domestic" && category !== "animated") {
    return true;
  }
  return (candidate.content_category ?? "regular") === category;
}

function overlap(first: string[] = [], second: string[] = []): number {
  const set = new Set(first);
  return second.filter((value) => set.has(value)).length;
}

function titleTokens(title: string): Set<string> {
  return new Set(
    title
      .toLocaleLowerCase("sr-Latn-RS")
      .split(/\s+/)
      .filter((token) => token.length >= MIN_TITLE_TOKEN),
  );
}


/**
 * Preporučeni: ponderisano poklapanje po ključnim rečima + žanru + nazivu.
 * Isključuje trenutni naslov, poštuje kategoriju, sortira opadajuće.
 */
export function scoreRecommended(
  current: MediaItem,
  candidates: MediaItem[],
): MediaItem[] {
  const currentTokens = titleTokens(current.title);

  return candidates
    .filter(
      (candidate) =>
        candidate.id !== current.id && categoryAllows(current, candidate),
    )
    .map((candidate) => {
      const keywordScore =
        overlap(current.keywords, candidate.keywords) * W_KEYWORD;
      const genreScore = overlap(current.genres, candidate.genres) * W_GENRE;

      const candidateTokens = titleTokens(candidate.title);
      let titleScore = 0;
      currentTokens.forEach((token) => {
        if (candidateTokens.has(token)) {
          titleScore += 1;
        }
      });

      return {
        candidate,
        score: keywordScore + genreScore + titleScore * W_TITLE,
      };
    })
    .filter((entry) => entry.score > 0)
    .sort((first, second) => second.score - first.score)
    .map((entry) => entry.candidate);
}


/** Po žanru: skor = broj zajedničkih žanrova. */
export function scoreByGenre(
  current: MediaItem,
  candidates: MediaItem[],
): MediaItem[] {
  return candidates
    .filter(
      (candidate) =>
        candidate.id !== current.id && categoryAllows(current, candidate),
    )
    .map((candidate) => ({
      candidate,
      score: overlap(current.genres, candidate.genres),
    }))
    .filter((entry) => entry.score > 0)
    .sort((first, second) => second.score - first.score)
    .map((entry) => entry.candidate);
}


export type RelatedCard = {
  related: RelatedTitle;
  owned: MediaItem | null;
};

/**
 * Ukršta TMDB related sa lokalnim katalogom po tmdb_id.
 * Vraća owned kartice prvo, pa ne-owned.
 */
export function splitRelated(
  related: RelatedTitle[],
  catalog: MediaItem[],
): RelatedCard[] {
  const byTmdb = new Map<number, MediaItem>();
  for (const item of catalog) {
    if (item.tmdb_id != null) {
      byTmdb.set(item.tmdb_id, item);
    }
  }

  const cards = related.map((entry) => ({
    related: entry,
    owned: byTmdb.get(entry.tmdb_id) ?? null,
  }));

  return [
    ...cards.filter((card) => card.owned),
    ...cards.filter((card) => !card.owned),
  ];
}


/**
 * Kaskadni dedup: Povezani → Preporučeni → Po žanru. Svaki odeljak izbacuje
 * već viđene naslove i seče na `limit`.
 */
export function cascadeDedupe(
  relatedCards: RelatedCard[],
  recommended: MediaItem[],
  genre: MediaItem[],
  limit = 10,
): {
  relatedCards: RelatedCard[];
  recommended: MediaItem[];
  genre: MediaItem[];
} {
  const seen = new Set<number>();

  const relatedCapped = relatedCards.slice(0, limit);
  for (const card of relatedCapped) {
    if (card.owned) {
      seen.add(card.owned.id);
    }
  }

  const recommendedCapped = recommended
    .filter((item) => !seen.has(item.id))
    .slice(0, limit);
  for (const item of recommendedCapped) {
    seen.add(item.id);
  }

  const genreCapped = genre
    .filter((item) => !seen.has(item.id))
    .slice(0, limit);

  return {
    relatedCards: relatedCapped,
    recommended: recommendedCapped,
    genre: genreCapped,
  };
}
