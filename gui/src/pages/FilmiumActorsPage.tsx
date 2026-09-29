import { useEffect, useRef, useState } from "react";
import { LoaderCircle, Search, Users } from "lucide-react";
import { useNavigate } from "react-router";

import { useFilmiumActors } from "../features/filmium/hooks/useFilmiumActors";
import { getFilmiumActorImageUrl } from "../services/filmiumActorsApi";
import type { FilmiumActorListItem } from "../types/filmiumActors";
import "../features/filmium/styles/filmium-actors.css";


// ==========          INICIJALI (REZERVNA SLIKA)          ==========

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) {
    return "?";
  }
  if (parts.length === 1) {
    return parts[0].slice(0, 2).toUpperCase();
  }
  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
}


// ==========          JEDNA KARTICA GLUMCA          ==========

function FilmiumActorCard({
  actor,
  onOpen,
}: {
  actor: FilmiumActorListItem;
  onOpen: (slug: string) => void;
}) {
  const [imageFailed, setImageFailed] = useState(false);
  const imageUrl = actor.image_path ? getFilmiumActorImageUrl(actor.slug) : null;

  return (
    <button
      className="filmium-actor-card"
      onClick={() => onOpen(actor.slug)}
      type="button"
    >
      <div className="filmium-actor-card-visual">
        {imageUrl && !imageFailed ? (
          <img
            alt=""
            decoding="async"
            loading="lazy"
            onError={() => setImageFailed(true)}
            src={imageUrl}
          />
        ) : (
          <div className="filmium-actor-card-fallback">
            <span>{initials(actor.name)}</span>
          </div>
        )}

        <div className="filmium-actor-card-shade" />

        {Boolean(actor.is_director) && (
          <span className="filmium-actor-badge">Reditelj</span>
        )}
      </div>

      <div className="filmium-actor-card-content">
        <strong>{actor.name}</strong>
        <span>
          {actor.film_count > 0
            ? `${actor.film_count} ${actor.film_count === 1 ? "film" : "filmova"}`
            : "Bez naslova u biblioteci"}
        </span>
      </div>
    </button>
  );
}


// ==========          FILMIUM GLUMCI EKRAN (LISTA)          ==========

/**
 * Lista svih glumaca i reditelja iz FILMIUM biblioteke: pretraga po imenu i
 * progresivno učitavanje (limit/offset). Klik na karticu otvara detalje.
 */
function FilmiumActorsPage() {
  const navigate = useNavigate();

  const {
    searchInput,
    setSearchInput,
    items,
    total,
    isLoading,
    isLoadingMore,
    errorMessage,
    hasMore,
    loadMore,
  } = useFilmiumActors();

  function handleOpen(slug: string): void {
    navigate(`/filmium/actors/${slug}`);
  }

  // ==========          UČITAJ JOŠ NA SKROL          ==========

  const sentinelRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!hasMore) {
      return;
    }

    const sentinel = sentinelRef.current;
    if (!sentinel) {
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) {
          void loadMore();
        }
      },
      { rootMargin: "800px 0px" },
    );

    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [hasMore, loadMore]);

  return (
    <section className="filmium-section filmium-actors-page">
      <div className="section-heading">
        <p className="eyebrow">
          FILMIUM Glumci
          {total > 0 && (
            <span className="filmium-library-count">{total}</span>
          )}
        </p>
        <h2>Glumci</h2>

        <p className="filmium-page-description">
          Pregled glumaca i reditelja iz biblioteke — biografija, filmografija
          i galerija fotografija.
        </p>
      </div>

      <div className="filmium-actors-toolbar">
        <label className="filmium-search">
          <span>Pretraga po imenu</span>
          <div className="filmium-actors-search-field">
            <Search aria-hidden="true" size={16} />
            <input
              onChange={(event) => setSearchInput(event.target.value)}
              placeholder="Pretraži glumce i reditelje..."
              type="search"
              value={searchInput}
            />
          </div>
        </label>
      </div>

      {errorMessage && (
        <p className="system-message error">{errorMessage}</p>
      )}

      {isLoading && (
        <p className="system-message">
          <LoaderCircle className="spinning" size={16} />
          {" "}Učitavam glumce...
        </p>
      )}

      {!isLoading && !errorMessage && items.length === 0 && (
        <p className="system-message">
          <Users aria-hidden="true" size={16} />
          {" "}Nijedan glumac ne odgovara pretrazi.
        </p>
      )}

      {items.length > 0 && (
        <>
          <div className="filmium-actors-grid">
            {items.map((actor) => (
              <FilmiumActorCard
                actor={actor}
                key={actor.slug}
                onOpen={handleOpen}
              />
            ))}
          </div>

          {hasMore && (
            <div className="filmium-actors-load-more" ref={sentinelRef}>
              {isLoadingMore && (
                <span className="filmium-actors-loading-more">
                  <LoaderCircle className="spinning" size={16} />
                  Učitavam još...
                </span>
              )}
            </div>
          )}
        </>
      )}
    </section>
  );
}

export default FilmiumActorsPage;
