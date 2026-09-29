import { useEffect, useState } from "react";

import { getFilmiumAssetUrl } from "../../../../services/filmiumApi";
import type { MediaItem } from "../../../../types/filmium";


// ==========          SVOJSTVA POSTER MREZE          ==========

type FilmiumMediaPosterGridProps = {
  emptyMessage: string;
  items: MediaItem[];
  onOpenDetails: (item: MediaItem) => void;
};

// Koliko kartica se prikaže odmah, i koliko se dodaje kad se približi dnu.
const INITIAL_COUNT = 40;
const BATCH_COUNT = 40;


// ==========          JEDNA KARTICA          ==========

function FilmiumPosterCard({
  item,
  onOpenDetails,
}: {
  item: MediaItem;
  onOpenDetails: (item: MediaItem) => void;
}) {
  const visualPath = item.poster_path ?? item.backdrop_path;
  const visualUrl = getFilmiumAssetUrl(visualPath);

  return (
    <button
      className="filmium-shelf-card poster"
      onClick={() => onOpenDetails(item)}
      type="button"
    >
      <div className="filmium-shelf-card-visual">
        {visualUrl ? (
          <img alt="" decoding="async" loading="lazy" src={visualUrl} />
        ) : (
          <div className="filmium-shelf-card-fallback">
            <span>{item.media_type === "movie" ? "FILM" : "SERIJA"}</span>
          </div>
        )}

        <div className="filmium-shelf-card-shade" />

        {item.rating !== null && (
          <span className="filmium-shelf-rating">★ {item.rating}</span>
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
          {item.media_type === "movie" ? "Film" : "Serija"}
        </span>
      </div>
    </button>
  );
}


// ==========          FILMIUM POSTER MREZA (progresivna)          ==========

/**
 * Prikazuje biblioteku sa progresivnim učitavanjem: odmah ~40 kartica blizu
 * vidnog polja, a ostatak se dodaje čim se skrol približi dnu (Intersection
 * Observer sa širokom preload zonom). Uz `content-visibility: auto` u CSS-u
 * offscreen kartice se ne renderuju/layout-uju, pa je skrol gladak i za
 * biblioteke sa 900+ naslova — bez oslanjanja na merenje veličine kartice.
 */
function FilmiumMediaPosterGrid({
  emptyMessage,
  items,
  onOpenDetails,
}: FilmiumMediaPosterGridProps) {
  const [visibleCount, setVisibleCount] = useState(INITIAL_COUNT);

  // Reset na promenu liste (npr. filter/pretraga/kategorija).
  useEffect(() => {
    setVisibleCount(INITIAL_COUNT);
  }, [items]);

  // Dodaj sledeću grupu kada se skrol približi dnu. Scroll se hvata u CAPTURE
  // fazi na dokumentu, pa radi bez obzira koji element zapravo skroluje.
  // Početna provera popunjava kratku stranicu (kad je viewport veći od sadržaja).
  useEffect(() => {
    if (visibleCount >= items.length) {
      return;
    }

    const nearBottom = (): boolean => {
      const scroller = document.scrollingElement || document.documentElement;
      const remaining =
        scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight;
      return remaining < 1400;
    };

    const maybeLoadMore = () => {
      if (nearBottom()) {
        setVisibleCount((current) =>
          Math.min(items.length, current + BATCH_COUNT),
        );
      }
    };

    maybeLoadMore(); // popuni ako je stranica kraća od vidnog polja
    document.addEventListener("scroll", maybeLoadMore, {
      passive: true,
      capture: true,
    });
    window.addEventListener("resize", maybeLoadMore);

    return () => {
      document.removeEventListener("scroll", maybeLoadMore, {
        capture: true,
      } as EventListenerOptions);
      window.removeEventListener("resize", maybeLoadMore);
    };
  }, [items.length, visibleCount]);

  if (items.length === 0) {
    return <p className="system-message">{emptyMessage}</p>;
  }

  const shown = items.slice(0, visibleCount);

  return (
    <div className="filmium-poster-grid">
      {shown.map((item) => (
        <FilmiumPosterCard
          item={item}
          key={item.id}
          onOpenDetails={onOpenDetails}
        />
      ))}
    </div>
  );
}

export default FilmiumMediaPosterGrid;
