import { Star } from "lucide-react";

import type { MediaItem } from "../../../../types/filmium";


// ==========          SVOJSTVA          ==========

type FilmiumExternalRatingsProps = {
  item: MediaItem;
};


// ==========          POMOĆNO FORMATIRANJE          ==========

/** Kompaktan broj glasova: 1_240_000 → „1.2M", 8_530 → „8.5K". */
function formatVotes(value: number): string {
  if (value >= 1_000_000) {
    return `${(value / 1_000_000).toFixed(1).replace(/\.0$/, "")}M`;
  }
  if (value >= 1_000) {
    return `${(value / 1_000).toFixed(1).replace(/\.0$/, "")}K`;
  }
  return String(value);
}

/** Ocena na jednu decimalu (npr. 8 → „8.0"). */
function fmtScore(value: number): string {
  return value.toFixed(1);
}


// ==========          SEKCIJA „SPOLJNE OCENE"          ==========

/**
 * Kompaktne značke spoljnih ocena (IMDb / Rotten Tomatoes / TVmaze / MAL)
 * u domenskom akcentu, u istom stilu kao značke glumaca/zanimanja. Čita
 * `item.editor_settings.ratings.external` (perzistirano sa backenda) i
 * prikazuje SAMO izvore koji imaju podatke — ako nijedan nema, ništa se ne
 * renderuje.
 */
function FilmiumExternalRatings({ item }: FilmiumExternalRatingsProps) {
  const ratings = item.editor_settings?.ratings;
  const external = ratings?.external;
  if (!external) {
    return null;
  }

  const votes = ratings?.votes;
  const imdb = external["IMDb"];
  const rt = external["Rotten Tomatoes"];
  const tvmaze = external["TVmaze"];
  const mal = external["MAL"];

  const imdbVotes = votes?.["IMDb"];

  const hasImdb = imdb != null && typeof imdb.score === "number";
  const hasRt =
    rt != null
    && (typeof rt.tomatometer === "number" || typeof rt.audience === "number");
  const hasTvmaze = tvmaze != null && typeof tvmaze.score === "number";
  const hasMal = mal != null && typeof mal.score === "number";

  if (!hasImdb && !hasRt && !hasTvmaze && !hasMal) {
    return null;
  }

  return (
    <div className="filmium-external-ratings">
      <p className="filmium-external-ratings-label">
        <Star size={14} />
        Spoljne ocene
      </p>

      <div className="filmium-external-ratings-list">
        {hasImdb && (
          <div className="filmium-external-rating" title="IMDb">
            <span className="filmium-external-rating-icon">⭐</span>
            <div className="filmium-external-rating-body">
              <span className="filmium-external-rating-source">IMDb</span>
              <span className="filmium-external-rating-score">
                {fmtScore(imdb!.score as number)}
                <em> / 10</em>
              </span>
              {typeof imdbVotes === "number" && (
                <span className="filmium-external-rating-meta">
                  {formatVotes(imdbVotes)} glasova
                </span>
              )}
            </div>
          </div>
        )}

        {hasRt && (
          <div className="filmium-external-rating" title="Rotten Tomatoes">
            <span className="filmium-external-rating-icon">🍅</span>
            <div className="filmium-external-rating-body">
              <span className="filmium-external-rating-source">
                Rotten Tomatoes
              </span>
              <span className="filmium-external-rating-score">
                {typeof rt!.tomatometer === "number"
                  ? `${Math.round(rt!.tomatometer)}%`
                  : "—"}
                {typeof rt!.audience === "number" && (
                  <em>{` · 👥 ${Math.round(rt!.audience)}%`}</em>
                )}
              </span>
            </div>
          </div>
        )}

        {hasTvmaze && (
          <div className="filmium-external-rating" title="TVmaze">
            <span className="filmium-external-rating-icon">📺</span>
            <div className="filmium-external-rating-body">
              <span className="filmium-external-rating-source">TVmaze</span>
              <span className="filmium-external-rating-score">
                {fmtScore(tvmaze!.score as number)}
                <em> / 10</em>
              </span>
              {tvmaze!.network && (
                <span className="filmium-external-rating-meta">
                  {tvmaze!.network}
                </span>
              )}
            </div>
          </div>
        )}

        {hasMal && (
          <div className="filmium-external-rating" title="MyAnimeList">
            <span className="filmium-external-rating-icon">🎌</span>
            <div className="filmium-external-rating-body">
              <span className="filmium-external-rating-source">MAL</span>
              <span className="filmium-external-rating-score">
                {fmtScore(mal!.score as number)}
                <em> / 10</em>
              </span>
              {mal!.studio && (
                <span className="filmium-external-rating-meta">
                  {mal!.studio}
                </span>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default FilmiumExternalRatings;
