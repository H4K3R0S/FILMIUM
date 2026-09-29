import {
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  ChevronRight,
  Heart,
  Info,
} from "lucide-react";

import { getFilmiumAssetUrl } from "../../../../services/filmiumApi";
import type { MediaItem } from "../../../../types/filmium";


// ==========          SVOJSTVA KOMPONENTE          ==========

type FilmiumFeaturedCarouselProps = {
  items: MediaItem[];
  updatingFavoriteItemId: number | null;
  onActiveBackdropChange: (
    relativePath: string | null,
  ) => void;
  onOpenDetails: (item: MediaItem) => void;
  onToggleFavorite: (item: MediaItem) => Promise<void>;
};


// ==========          FEATURED CAROUSEL          ==========

/**
 * Prikazuje izdvojene FILMIUM sadržaje sa backdrop slikama.
 *
 * Glavna kartica nalazi se iznad dve naredne kartice koje
 * predstavljaju vizuelnu najavu sledećih sadržaja.
 */
function FilmiumFeaturedCarousel({
  items,
  updatingFavoriteItemId,
  onActiveBackdropChange,
  onOpenDetails,
  onToggleFavorite,
}: FilmiumFeaturedCarouselProps) {
  const [activeIndex, setActiveIndex] = useState(0);
  const [isRotationPaused, setIsRotationPaused] =
    useState(false);
  const [prefersReducedMotion, setPrefersReducedMotion] =
    useState(false);

  const featuredItems = useMemo(() => {
    /*
     * Backdrop sadržaji imaju prednost, ali ne smeju da izbace
     * ostale kartice iz carousel-a. Stavke bez backdropa nastavljaju
     * da koriste poster kao rezervnu vizuelnu sliku.
     */
    return [...items]
      .sort((firstItem, secondItem) =>
        Number(secondItem.backdrop_path !== null)
        - Number(firstItem.backdrop_path !== null)
      )
      .slice(0, 5);
  }, [items]);

  const safeActiveIndex =
    activeIndex < featuredItems.length
      ? activeIndex
      : 0;

  const activeVisualPath =
    featuredItems[safeActiveIndex]?.backdrop_path
    ?? featuredItems[safeActiveIndex]?.poster_path
    ?? null;

  // Kada se spisak skrati (npr. posle filtriranja), zapamćena pozicija ume da
  // ispadne iz opsega. To hvata `safeActiveIndex` gore, pri crtanju — upisivati
  // nulu iz efekta značilo bi još jedan crtež i jedan kadar praznog mesta.

  // ==========          GLOBALNA POZADINA          ==========

  useEffect(() => {
    onActiveBackdropChange(activeVisualPath);

    return () => {
      onActiveBackdropChange(null);
    };
  }, [
    activeVisualPath,
    onActiveBackdropChange,
  ]);

  // ==========          PODEŠAVANJE ANIMACIJE          ==========

  useEffect(() => {
    if (typeof window.matchMedia !== "function") {
      return undefined;
    }

    const motionQuery = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    );

    function updateMotionPreference(): void {
      setPrefersReducedMotion(motionQuery.matches);
    }

    updateMotionPreference();

    motionQuery.addEventListener(
      "change",
      updateMotionPreference,
    );

    return () => {
      motionQuery.removeEventListener(
        "change",
        updateMotionPreference,
      );
    };
  }, []);

  // ==========          AUTOMATSKA ROTACIJA          ==========

  useEffect(() => {
    if (
      featuredItems.length <= 1
      || isRotationPaused
      || prefersReducedMotion
    ) {
      return undefined;
    }

    const intervalId = window.setInterval(() => {
      setActiveIndex((currentIndex) =>
        (currentIndex + 1) % featuredItems.length
      );
    }, 8_000);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [
    featuredItems.length,
    isRotationPaused,
    prefersReducedMotion,
  ]);

  if (featuredItems.length === 0) {
    return (
      <section className="filmium-featured empty">
        <div className="filmium-featured-empty-content">
          <p className="eyebrow">FILMIUM v0.1</p>

          <h2>Tvoja filmska biblioteka počinje ovde</h2>

          <p>
            Dodaj prvi film ili seriju, a zatim mu poveži poster
            i backdrop sliku.
          </p>
        </div>
      </section>
    );
  }

  const activeItem = featuredItems[safeActiveIndex];
  const nextIndex =
    (safeActiveIndex + 1) % featuredItems.length;
  const upcomingIndex =
    (safeActiveIndex + 2) % featuredItems.length;

  const nextItem =
    featuredItems.length > 1
      ? featuredItems[nextIndex]
      : null;

  const upcomingItem =
    featuredItems.length > 2
      ? featuredItems[upcomingIndex]
      : null;

  const activeBackdropUrl = getFilmiumAssetUrl(
    activeVisualPath,
  );

  const nextBackdropUrl = getFilmiumAssetUrl(
    nextItem?.backdrop_path
      ?? nextItem?.poster_path
      ?? null,
  );

  const upcomingBackdropUrl = getFilmiumAssetUrl(
    upcomingItem?.backdrop_path
      ?? upcomingItem?.poster_path
      ?? null,
  );

  /**
   * Prikazuje sledeću izdvojenu karticu.
   */
  function showNextItem(): void {
    setActiveIndex(nextIndex);
  }

  return (
    <section
      className="filmium-featured"
      onBlurCapture={(event) => {
        const nextFocusedElement = event.relatedTarget;

        if (
          !(nextFocusedElement instanceof Node)
          || !event.currentTarget.contains(nextFocusedElement)
        ) {
          setIsRotationPaused(false);
        }
      }}
      onFocusCapture={() => setIsRotationPaused(true)}
      onMouseEnter={() => setIsRotationPaused(true)}
      onMouseLeave={() => setIsRotationPaused(false)}
    >
      {/* ==========          CAROUSEL PROZOR          ========== */}

      <div className="filmium-featured-window">
        <article
          className="filmium-featured-card active"
          key={activeItem.id}
          style={{
            backgroundImage: activeBackdropUrl
              ? `url("${activeBackdropUrl}")`
              : undefined,
          }}
        >
          <div className="filmium-featured-overlay" />

          <div className="filmium-featured-content">
            <p className="eyebrow">
              {activeItem.media_type === "movie"
                ? "Preporučeni film"
                : "Preporučena serija"}
            </p>

            <h2>{activeItem.title}</h2>

            <div className="filmium-featured-meta">
              {activeItem.release_year && (
                <span>{activeItem.release_year}</span>
              )}

              {activeItem.genres.slice(0, 3).map((genre) => (
                <span key={genre}>{genre}</span>
              ))}
            </div>

            {activeItem.notes && (
              <p className="filmium-featured-description">
                {activeItem.notes}
              </p>
            )}

            <div className="filmium-featured-actions">
              <button
                className="primary-button"
                onClick={() => onOpenDetails(activeItem)}
                type="button"
              >
                <Info size={17} />
                Detalji
              </button>

              <button
                className="secondary-button"
                disabled={
                  updatingFavoriteItemId === activeItem.id
                }
                onClick={() => void onToggleFavorite(activeItem)}
                type="button"
              >
                <Heart
                  fill={
                    activeItem.is_favorite
                      ? "currentColor"
                      : "none"
                  }
                  size={17}
                />

                {activeItem.is_favorite
                  ? "U omiljenima"
                  : "Dodaj u omiljene"}
              </button>
            </div>
          </div>

          {activeItem.rating !== null && (
            <div className="filmium-featured-corner-rating">
              <span>★ {activeItem.rating}/10</span>
            </div>
          )}

          {featuredItems.length > 1 && (
            <div
              aria-label="Featured sadržaji"
              className="filmium-featured-dots"
            >
              {featuredItems.map((item, index) => (
                <button
                  aria-label={`Prikaži ${item.title}`}
                  className={
                    index === safeActiveIndex ? "active" : ""
                  }
                  key={item.id}
                  onClick={() => setActiveIndex(index)}
                  type="button"
                />
              ))}
            </div>
          )}
        </article>

        {/* ==========          NAREDNE KARTICE          ========== */}

        {nextItem && (
          <div className="filmium-featured-preview-stack">
            <button
              aria-label={`Prikaži ${nextItem.title}`}
              className="filmium-featured-card next"
              key={`next-${nextItem.id}`}
              onClick={showNextItem}
              style={{
                backgroundImage: nextBackdropUrl
                  ? `url("${nextBackdropUrl}")`
                  : undefined,
              }}
              type="button"
            >
              <span>{nextItem.title}</span>
              <ChevronRight size={24} />
            </button>

            {upcomingItem && (
              <button
                aria-label={`Prikaži ${upcomingItem.title}`}
                className="filmium-featured-card upcoming"
                key={`upcoming-${upcomingItem.id}`}
                onClick={() => setActiveIndex(upcomingIndex)}
                style={{
                  backgroundImage: upcomingBackdropUrl
                    ? `url("${upcomingBackdropUrl}")`
                    : undefined,
                }}
                type="button"
              >
                <span>{upcomingItem.title}</span>
              </button>
            )}

            <div
              aria-hidden="true"
              className="filmium-featured-preview-fade"
            />
          </div>
        )}
      </div>
    </section>
  );
}

export default FilmiumFeaturedCarousel;
