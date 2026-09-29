import { useMemo } from "react";
import { Play } from "lucide-react";

import { getFilmiumAssetUrl } from "../../../../services/filmiumApi";
import type { MediaItem } from "../../../../types/filmium";


// ==========          SVOJSTVA KOMPONENTE          ==========

type FilmiumHomeShelvesProps = {
  items: MediaItem[];
  onOpenDetails: (item: MediaItem) => void;
};


// ==========          FILMIUM HOME REDOVI          ==========

/**
 * Prikazuje glavne horizontalne redove FILMIUM početnog ekrana.
 */
function FilmiumHomeShelves({
  items,
  onOpenDetails,
}: FilmiumHomeShelvesProps) {
  const continueWatchingItems = useMemo(
    () =>
      items.filter(
        (item) =>
          item.watch_status === "watching"
          || item.watch_status === "paused",
      ),
    [items],
  );

  const topRatedItems = useMemo(
    () =>
      [...items]
        .filter((item) => item.rating !== null)
        .sort(
          (firstItem, secondItem) =>
            (secondItem.rating ?? 0)
            - (firstItem.rating ?? 0),
        ),
    [items],
  );

  /*
   * Odeljci po kategorijama iz baze. Kategorija koja nedostaje tretira se
   * kao „regular" (stariji sadržaj bez oznake).
   */

  const movieItems = useMemo(
    () =>
      items.filter(
        (item) =>
          item.media_type === "movie"
          && (item.content_category ?? "regular") === "regular",
      ),
    [items],
  );

  const seriesItems = useMemo(
    () =>
      items.filter(
        (item) =>
          item.media_type === "series"
          && (item.content_category ?? "regular") === "regular",
      ),
    [items],
  );

  const animatedItems = useMemo(
    () =>
      items.filter(
        (item) => item.content_category === "animated",
      ),
    [items],
  );

  const domesticItems = useMemo(
    () =>
      items.filter(
        (item) => item.content_category === "domestic",
      ),
    [items],
  );

  const upcomingMovies = useMemo(() => {
    const currentYear = new Date().getFullYear();

    return items
      .filter(
        (item) =>
          item.media_type === "movie"
          && item.release_year !== null
          && item.release_year > currentYear,
      )
      .sort(
        (firstItem, secondItem) =>
          (firstItem.release_year ?? 0)
          - (secondItem.release_year ?? 0),
      );
  }, [items]);

  return (
    <div className="filmium-home-shelves">
      {continueWatchingItems.length > 0 && (
        <MediaShelf
          items={continueWatchingItems}
          title="NASTAVI GLEDANJE"
          variant="landscape"
          onOpenDetails={onOpenDetails}
        />
      )}

      {topRatedItems.length > 0 && (
        <MediaShelf
          items={topRatedItems}
          title="NAJBOLJE OCENJENI"
          variant="poster"
          onOpenDetails={onOpenDetails}
        />
      )}

      {movieItems.length > 0 && (
        <MediaShelf
          items={movieItems}
          title="FILMOVI"
          variant="poster"
          onOpenDetails={onOpenDetails}
        />
      )}

      {seriesItems.length > 0 && (
        <MediaShelf
          items={seriesItems}
          title="SERIJE"
          variant="poster"
          onOpenDetails={onOpenDetails}
        />
      )}

      {animatedItems.length > 0 && (
        <MediaShelf
          items={animatedItems}
          title="ANIMIRANO"
          variant="poster"
          onOpenDetails={onOpenDetails}
        />
      )}

      {domesticItems.length > 0 && (
        <MediaShelf
          items={domesticItems}
          title="DOMAĆI FILMOVI"
          variant="poster"
          onOpenDetails={onOpenDetails}
        />
      )}

      {upcomingMovies.length > 0 && (
        <MediaShelf
          items={upcomingMovies}
          title="NADOLAZEĆI FILMOVI"
          variant="landscape"
          onOpenDetails={onOpenDetails}
        />
      )}
    </div>
  );
}


// ==========          MEDIA SHELF          ==========

type MediaShelfProps = {
  items: MediaItem[];
  title: string;
  variant: "landscape" | "poster";
  onOpenDetails: (item: MediaItem) => void;
};

/**
 * Prikazuje jedan horizontalni red FILMIUM kartica.
 */
function MediaShelf({
  items,
  title,
  variant,
  onOpenDetails,
}: MediaShelfProps) {
  // Zaglavlje prikazuje stvaran ukupan broj; traka renderuje najviše 12.
  const visibleItems = items.slice(0, 12);

  return (
    <section className="filmium-home-shelf">
      <div className="filmium-home-shelf-heading">
        <h2>{title}</h2>
        <span>{items.length} sadržaja</span>
      </div>

      <div className="filmium-home-shelf-track">
        {visibleItems.map((item) => {
          const visualPath =
            variant === "landscape"
              ? item.backdrop_path ?? item.poster_path
              : item.poster_path ?? item.backdrop_path;

          const visualUrl = getFilmiumAssetUrl(visualPath);

          return (
            <button
              className={`filmium-shelf-card ${variant}`}
              key={item.id}
              onClick={() => onOpenDetails(item)}
              type="button"
            >
              <div className="filmium-shelf-card-visual">
                {visualUrl ? (
                  <img
                    alt=""
                    loading="lazy"
                    src={visualUrl}
                  />
                ) : (
                  <div className="filmium-shelf-card-fallback">
                    <span>
                      {item.media_type === "movie"
                        ? "FILM"
                        : "SERIJA"}
                    </span>
                  </div>
                )}

                <div className="filmium-shelf-card-shade" />

                {variant === "landscape" && (
                  <span className="filmium-shelf-play">
                    <Play fill="currentColor" size={15} />
                  </span>
                )}

                {item.rating !== null && (
                  <span className="filmium-shelf-rating">
                    ★ {item.rating}
                  </span>
                )}

                <span
                  className={`filmium-shelf-audio ${
                    item.is_synchronized ? "sinh" : "titl"
                  }`}
                >
                  {item.is_synchronized ? "SINH" : "TITL"}
                </span>
              </div>

              <div className="filmium-shelf-card-content">
                <strong>{item.title}</strong>

                <span>
                  {item.release_year ?? "Godina nije uneta"}
                  {" · "}
                  {item.media_type === "movie"
                    ? "Film"
                    : "Serija"}
                </span>
              </div>
            </button>
          );
        })}
      </div>
    </section>
  );
}

export default FilmiumHomeShelves;