import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";
import { createPortal } from "react-dom";
import {
  ArrowLeft,
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Images,
  LoaderCircle,
  MapPin,
  Plus,
  X,
} from "lucide-react";
import { useNavigate, useParams } from "react-router";

import {
  getFilmiumActorDetail,
  getFilmiumActorGalleryUrl,
  getFilmiumActorImageUrl,
  normalizeActorMediaType,
} from "../services/filmiumActorsApi";
import { getFilmiumAssetUrl } from "../services/filmiumApi";
import FilmiumAcquireModal, {
  type FilmiumAcquirePrefill,
} from "../features/filmium/components/uploads/FilmiumAcquireModal";
import type {
  FilmiumActorDetail,
  FilmiumActorFilmCard,
} from "../types/filmiumActors";
import "../features/filmium/styles/filmium-actors.css";


// ==========          POMOĆNE FUNKCIJE          ==========

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

function formatDate(value: string | null): string | null {
  if (!value) {
    return null;
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return null;
  }
  return new Intl.DateTimeFormat("sr-Latn-RS", { dateStyle: "medium" }).format(
    parsed,
  );
}

/**
 * Spaja `library_films` (u biblioteci) i `filmography` (puna TMDB lista) u
 * jedinstven skup kartica, dedupujući po `tmdb_id`. Poster stiže samo iz
 * `library_films` (filmografija ga nema) — poveže se preko `media_id`/`tmdb_id`.
 */
function buildFilmCards(detail: FilmiumActorDetail): FilmiumActorFilmCard[] {
  const libByTmdb = new Map<number, FilmiumActorDetail["library_films"][number]>();
  const libByMediaId = new Map<number, FilmiumActorDetail["library_films"][number]>();

  for (const lib of detail.library_films) {
    if (lib.tmdb_id !== null) {
      libByTmdb.set(lib.tmdb_id, lib);
    }
    libByMediaId.set(lib.media_id, lib);
  }

  const seenTmdb = new Set<number>();
  const cards: FilmiumActorFilmCard[] = [];

  for (const entry of detail.filmography) {
    if (seenTmdb.has(entry.tmdb_id)) {
      continue;
    }
    seenTmdb.add(entry.tmdb_id);

    const libMatch =
      (entry.media_id !== null ? libByMediaId.get(entry.media_id) : undefined)
      ?? libByTmdb.get(entry.tmdb_id);

    cards.push({
      key: `tmdb-${entry.tmdb_id}`,
      tmdb_id: entry.tmdb_id,
      title: entry.title ?? libMatch?.title ?? "Nepoznat naslov",
      year: entry.year ?? libMatch?.year ?? null,
      media_type:
        libMatch?.media_type ?? normalizeActorMediaType(entry.media_type),
      character: entry.character ?? libMatch?.character ?? null,
      in_library: entry.in_library,
      media_id: entry.media_id,
      poster_path: libMatch?.poster_path ?? null,
    });
  }

  // Naslovi iz biblioteke koji (retko) nisu u TMDB filmografiji — i dalje ih
  // treba prikazati, spisak mora da obuhvati SVE iz oba izvora.
  for (const lib of detail.library_films) {
    if (lib.tmdb_id !== null && seenTmdb.has(lib.tmdb_id)) {
      continue;
    }
    if (lib.tmdb_id !== null) {
      seenTmdb.add(lib.tmdb_id);
    }

    cards.push({
      key: `media-${lib.media_id}`,
      tmdb_id: lib.tmdb_id,
      title: lib.title,
      year: lib.year,
      media_type: lib.media_type,
      character: lib.character,
      in_library: true,
      media_id: lib.media_id,
      poster_path: lib.poster_path,
    });
  }

  return cards.sort((firstCard, secondCard) => {
    // Prvo naslovi koji su u biblioteci, pa tek onda oni „za dodavanje".
    if (firstCard.in_library !== secondCard.in_library) {
      return firstCard.in_library ? -1 : 1;
    }
    const yearDelta = (secondCard.year ?? 0) - (firstCard.year ?? 0);
    if (yearDelta !== 0) {
      return yearDelta;
    }
    return firstCard.title.localeCompare(secondCard.title);
  });
}


// ==========          FILMIUM GLUMAC — DETALJI          ==========

/**
 * Prikazuje detalje jednog glumca/reditelja: sliku (uvodna animacija),
 * biografiju, datum/mesto rođenja, filmografiju (u biblioteci ili „za
 * dodavanje") i galeriju fotografija (carousel + lightbox).
 */
function FilmiumActorDetailPage() {
  const navigate = useNavigate();
  const { slug } = useParams();

  const [detail, setDetail] = useState<FilmiumActorDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [portraitFailed, setPortraitFailed] = useState(false);
  const [bioExpanded, setBioExpanded] = useState(false);

  const [acquireOpen, setAcquireOpen] = useState(false);
  const [acquirePrefill, setAcquirePrefill] =
    useState<FilmiumAcquirePrefill | null>(null);
  const [wishlistMessage, setWishlistMessage] = useState<string | null>(null);

  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null);

  useEffect(() => {
    if (!slug) {
      return;
    }

    let isMounted = true;
    setIsLoading(true);
    setErrorMessage(null);
    setPortraitFailed(false);
    setBioExpanded(false);

    getFilmiumActorDetail(slug)
      .then((loaded) => {
        if (isMounted) {
          setDetail(loaded);
        }
      })
      .catch((error: unknown) => {
        if (isMounted) {
          setErrorMessage(
            error instanceof Error
              ? error.message
              : "Učitavanje glumca nije uspelo.",
          );
        }
      })
      .finally(() => {
        if (isMounted) {
          setIsLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [slug]);

  const filmCards = useMemo(
    () => (detail ? buildFilmCards(detail) : []),
    [detail],
  );

  function handleBack(): void {
    if (window.history.length > 1) {
      navigate(-1);
      return;
    }
    navigate("/filmium/actors");
  }

  function handleOpenLibraryFilm(mediaId: number): void {
    navigate(`/filmium/media/${mediaId}`);
  }

  function handleOpenAcquire(card: FilmiumActorFilmCard): void {
    setAcquirePrefill({
      title: card.title,
      year: card.year,
      media_type: card.media_type,
      tmdb_id: card.tmdb_id,
    });
    setAcquireOpen(true);
  }

  if (isLoading) {
    return (
      <p className="system-message">
        <LoaderCircle className="spinning" size={16} />
        {" "}Učitavam glumca...
      </p>
    );
  }

  if (errorMessage) {
    return (
      <p className="system-message error">
        FILMIUM API nije dostupan: {errorMessage}
      </p>
    );
  }

  if (!detail) {
    return (
      <section className="filmium-section">
        <div className="section-heading">
          <p className="eyebrow">FILMIUM Glumci</p>
          <h2>Glumac nije pronađen</h2>
        </div>

        <button
          className="secondary-button"
          onClick={() => navigate("/filmium/actors")}
          type="button"
        >
          Vrati se na listu glumaca
        </button>
      </section>
    );
  }

  const { person } = detail;
  const BIO_LIMIT = 280;
  const bioIsLong = Boolean(person.bio && person.bio.length > BIO_LIMIT);
  const portraitUrl = getFilmiumActorImageUrl(person.slug);
  const birthdayLabel = formatDate(person.birthday);
  const deathdayLabel = formatDate(person.deathday);
  const galleryIndexes = Array.from(
    { length: Math.max(0, person.gallery_count) },
    (_, index) => index,
  );

  return (
    <>
    <article className="filmium-actor-detail" key={person.slug}>
      <div className="filmium-media-details-nav">
        <button
          className="filmium-details-back-button"
          onClick={handleBack}
          type="button"
        >
          <ArrowLeft size={17} />
          Nazad
        </button>

        <div className="filmium-details-breadcrumb">
          <span>
            Glumci {'>'} {person.is_director ? "Reditelj" : "Glumac"}
          </span>
        </div>
      </div>

      <div className="filmium-actor-detail-body">
        <div className="filmium-actor-portrait-wrap">
          <div className="filmium-actor-portrait">
            {portraitUrl && !portraitFailed ? (
              <img
                alt={person.name}
                onError={() => setPortraitFailed(true)}
                src={portraitUrl}
              />
            ) : (
              <div className="filmium-actor-portrait-fallback">
                <span>{initials(person.name)}</span>
              </div>
            )}
          </div>

          {Boolean(person.is_director) && (
            <span className="filmium-actor-badge standalone">Reditelj</span>
          )}

          {person.professions && person.professions.length > 0 && (
            <ul className="filmium-actor-professions">
              {person.professions.map((profession) => (
                <li className="filmium-actor-profession" key={profession}>
                  {profession}
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="filmium-actor-detail-content">
          <h1>{person.name}</h1>

          {person.bio ? (
            <div className="filmium-actor-bio-wrap">
              <p
                className={`filmium-actor-bio${
                  bioIsLong && !bioExpanded ? " clamped" : ""
                }`}
              >
                {person.bio}
              </p>
              {bioIsLong && (
                <button
                  className="filmium-actor-bio-toggle"
                  onClick={() => setBioExpanded((value) => !value)}
                  type="button"
                >
                  {bioExpanded ? "Pokaži manje" : "Pokaži više"}
                </button>
              )}
            </div>
          ) : (
            <p className="filmium-actor-bio muted">
              Biografija još nije dostupna.
            </p>
          )}

          <dl className="filmium-actor-facts">
            {birthdayLabel && (
              <div className="filmium-actor-fact">
                <dt>
                  <CalendarDays size={15} />
                  Datum rođenja
                </dt>
                <dd>{birthdayLabel}</dd>
              </div>
            )}

            {deathdayLabel && (
              <div className="filmium-actor-fact">
                <dt>
                  <CalendarDays size={15} />
                  Datum smrti
                </dt>
                <dd>{deathdayLabel}</dd>
              </div>
            )}

            {person.place_of_birth && (
              <div className="filmium-actor-fact">
                <dt>
                  <MapPin size={15} />
                  Mesto rođenja
                </dt>
                <dd>{person.place_of_birth}</dd>
              </div>
            )}
          </dl>
        </div>
      </div>

      {/* ==========          FILMOVI I SERIJE          ========== */}

      <section className="filmium-actor-films">
        <div className="filmium-actor-section-heading">
          <h2>Filmovi i serije</h2>
          <span>{filmCards.length} naslova</span>
        </div>

        {wishlistMessage && (
          <p className="system-message">{wishlistMessage}</p>
        )}

        {filmCards.length === 0 ? (
          <p className="system-message muted">
            Za ovog glumca još nema poznate filmografije.
          </p>
        ) : (
          <div className="filmium-actor-films-grid">
            {filmCards.map((card) => {
              const posterUrl = getFilmiumAssetUrl(card.poster_path);

              if (card.in_library && card.media_id !== null) {
                return (
                  <button
                    className="filmium-actor-film-card"
                    key={card.key}
                    onClick={() => handleOpenLibraryFilm(card.media_id as number)}
                    title={card.title}
                    type="button"
                  >
                    <div className="filmium-actor-film-visual">
                      {posterUrl ? (
                        <img alt="" loading="lazy" src={posterUrl} />
                      ) : (
                        <div className="filmium-actor-film-fallback">
                          <span>
                            {card.media_type === "movie" ? "FILM" : "SERIJA"}
                          </span>
                        </div>
                      )}
                    </div>
                    <div className="filmium-actor-film-copy">
                      <strong>{card.title}</strong>
                      <span>{card.year ?? "—"}</span>
                    </div>
                  </button>
                );
              }

              return (
                <button
                  className="filmium-actor-film-card is-add"
                  key={card.key}
                  onClick={() => handleOpenAcquire(card)}
                  title={`${card.title} — dodaj u listu za preuzimanje`}
                  type="button"
                >
                  <div className="filmium-actor-film-visual">
                    <Plus aria-hidden="true" size={34} />
                  </div>
                  <div className="filmium-actor-film-copy">
                    <strong>{card.title}</strong>
                    <span>{card.year ?? "—"}</span>
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </section>

      {/* ==========          GALERIJA          ========== */}

      {galleryIndexes.length > 0 && (
        <section className="filmium-actor-gallery">
          <div className="filmium-actor-section-heading">
            <h2>Galerija</h2>
            <button
              className="secondary-button"
              onClick={() => setLightboxIndex(0)}
              type="button"
            >
              <Images aria-hidden="true" size={16} />
              Galerija ({galleryIndexes.length})
            </button>
          </div>

          <div className="filmium-actor-gallery-track">
            {galleryIndexes.map((index) => (
              <button
                className="filmium-actor-gallery-thumb"
                key={index}
                onClick={() => setLightboxIndex(index)}
                type="button"
              >
                <img
                  alt={`${person.name} — slika ${index + 1}`}
                  loading="lazy"
                  src={getFilmiumActorGalleryUrl(person.slug, index)}
                />
              </button>
            ))}
          </div>
        </section>
      )}

    </article>

    {/* Portal na `document.body` NAMERNO: ceo ruter shell obavija stranicu u
        `.filmium-route-stage` sa `filter: blur(...)` (tranzicija rute), a i
        `.filmium-actor-detail` ima `backdrop-filter`. Po CSS spec-u OBOJE
        pravi containing block za `position: fixed` potomke — bez portala bi
        se modal/lightbox centrirali unutar te (visoke, skrolabilne) sekcije
        umesto u viewport-u i ostali nevidljivi van trenutnog skrola. */}

    {lightboxIndex !== null && createPortal(
      <FilmiumActorGalleryLightbox
        count={galleryIndexes.length}
        index={lightboxIndex}
        name={person.name}
        slug={person.slug}
        onChangeIndex={setLightboxIndex}
        onClose={() => setLightboxIndex(null)}
      />,
      document.body,
    )}

    {createPortal(
    <FilmiumAcquireModal
      open={acquireOpen}
      prefill={acquirePrefill}
      onAdded={() => {
        setAcquireOpen(false);
        setWishlistMessage(
          `„${acquirePrefill?.title ?? ""}" je dodat u listu za preuzimanje.`,
        );
      }}
      onClose={() => setAcquireOpen(false)}
    />,
    document.body,
    )}
    </>
  );
}


// ==========          LIGHTBOX GALERIJE          ==========

type FilmiumActorGalleryLightboxProps = {
  slug: string;
  name: string;
  count: number;
  index: number;
  onChangeIndex: (index: number) => void;
  onClose: () => void;
};

/**
 * Pun ekran pregled svih slika iz galerije — strelice, tastatura (levo/desno,
 * Escape) i klik van slike zatvaraju prikaz.
 */
function FilmiumActorGalleryLightbox({
  slug,
  name,
  count,
  index,
  onChangeIndex,
  onClose,
}: FilmiumActorGalleryLightboxProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    containerRef.current?.focus();
  }, []);

  function showPrevious(): void {
    onChangeIndex((index - 1 + count) % count);
  }

  function showNext(): void {
    onChangeIndex((index + 1) % count);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>): void {
    if (event.key === "Escape") {
      onClose();
    } else if (event.key === "ArrowLeft") {
      showPrevious();
    } else if (event.key === "ArrowRight") {
      showNext();
    }
  }

  return (
    <div
      aria-label={`Galerija — ${name}`}
      aria-modal="true"
      className="filmium-actor-lightbox-overlay"
      onClick={onClose}
      onKeyDown={handleKeyDown}
      ref={containerRef}
      role="dialog"
      tabIndex={-1}
    >
      <button
        aria-label="Zatvori galeriju"
        className="filmium-actor-lightbox-close"
        onClick={onClose}
        type="button"
      >
        <X aria-hidden="true" size={20} />
      </button>

      <div
        className="filmium-actor-lightbox-stage"
        onClick={(event) => event.stopPropagation()}
      >
        {count > 1 && (
          <button
            aria-label="Prethodna slika"
            className="filmium-actor-lightbox-nav prev"
            onClick={showPrevious}
            type="button"
          >
            <ChevronLeft aria-hidden="true" size={28} />
          </button>
        )}

        <img
          alt={`${name} — slika ${index + 1}`}
          className="filmium-actor-lightbox-image"
          src={getFilmiumActorGalleryUrl(slug, index)}
        />

        {count > 1 && (
          <button
            aria-label="Sledeća slika"
            className="filmium-actor-lightbox-nav next"
            onClick={showNext}
            type="button"
          >
            <ChevronRight aria-hidden="true" size={28} />
          </button>
        )}
      </div>

      <span className="filmium-actor-lightbox-counter">
        {index + 1} / {count}
      </span>
    </div>
  );
}

export default FilmiumActorDetailPage;
