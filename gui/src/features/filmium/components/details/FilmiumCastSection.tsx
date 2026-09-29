import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { CSSProperties } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { useNavigate } from "react-router";

import { getFilmiumActorImageUrl } from "../../../../services/filmiumActorsApi";
import { useFilmiumMediaCast } from "../../hooks/useFilmiumMediaCast";


// ==========          INICIJALI (REZERVNA SLIKA)          ==========

function castInitials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) {
    return "?";
  }
  if (parts.length === 1) {
    return parts[0].slice(0, 2).toUpperCase();
  }
  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
}


// ==========          SVOJSTVA          ==========

type FilmiumCastSectionProps = {
  mediaId: number;
};


// ==========          SEKCIJA „GLUMCI"          ==========

/**
 * Glumačka postava naslova — u istom stilu kao odeljak „Preporuke" na ovoj
 * stranici. Prvi red glavnih glumaca je uvek vidljiv (onoliko kartica
 * koliko STVARNO stane u red — mereno u DOM-u, ne fiksni broj). Dugme
 * „Pokaži više" animirano otkriva ostale redove (fade/slide-in, stagger po
 * kartici); „Pokaži manje" ih animirano skuplja nazad na jedan red.
 * Sekcija je sakrivena ako naslov nema postavu.
 */
function FilmiumCastSection({ mediaId }: FilmiumCastSectionProps) {
  const navigate = useNavigate();
  const { cast, total, errorMessage } = useFilmiumMediaCast(mediaId);

  const [expanded, setExpanded] = useState(false);
  const [rowCount, setRowCount] = useState<number | null>(null);
  const [collapsedHeight, setCollapsedHeight] = useState<number | null>(null);
  const [fullHeight, setFullHeight] = useState<number | null>(null);

  const gridRef = useRef<HTMLDivElement | null>(null);
  const cardRefs = useRef<Array<HTMLButtonElement | null>>([]);

  // Nov naslov (drugi `mediaId`) — vrati sekciju na skupljeno stanje umesto
  // da nasledi "otvoreno" sa prethodne stranice (stranica se ne remontira
  // pri navigaciji na drugi naslov).
  useEffect(() => {
    setExpanded(false);
  }, [mediaId]);

  // Meri STVARNU DOM širinu (ne CSS proračun): koliko kartica stane u prvi
  // red i kolika je njegova visina/ukupna visina svih redova. Prati i
  // promenu veličine prozora — broj kartica po redu je responsive.
  useLayoutEffect(() => {
    const grid = gridRef.current;
    if (!grid || cast.length === 0) {
      return;
    }

    function measure(): void {
      if (!grid) {
        return;
      }
      const cards = cardRefs.current.filter(
        (node): node is HTMLButtonElement => node !== null,
      );
      if (cards.length === 0) {
        return;
      }

      const firstTop = cards[0].offsetTop;
      let count = 0;
      for (const card of cards) {
        if (card.offsetTop !== firstTop) {
          break;
        }
        count += 1;
      }

      setRowCount(count);
      setCollapsedHeight(cards[0].offsetHeight);
      setFullHeight(grid.scrollHeight);
    }

    measure();

    const observer = new ResizeObserver(() => measure());
    observer.observe(grid);
    return () => observer.disconnect();
  }, [cast]);

  if (total === 0 || errorMessage) {
    return null;
  }

  const hiddenCount = rowCount !== null
    ? Math.max(0, cast.length - rowCount)
    : 0;
  const canExpand = hiddenCount > 0;

  return (
    <section className="filmium-details-cast">
      <div className="filmium-details-cast-heading">
        <h2>Glumci</h2>
        <span>{total}</span>
      </div>

      <div
        className="filmium-details-cast-wrap"
        style={
          collapsedHeight === null
            ? undefined
            : {
                maxHeight:
                  expanded && fullHeight !== null
                    ? fullHeight
                    : collapsedHeight,
              }
        }
      >
        <div
          className={`filmium-details-cast-grid${
            expanded ? " is-expanded" : ""
          }`}
          ref={gridRef}
        >
          {cast.map((member, index) => {
            const isExtra = rowCount !== null && index >= rowCount;
            const imageUrl = member.image_path
              ? getFilmiumActorImageUrl(member.slug)
              : null;

            return (
              <button
                className={`filmium-details-cast-card${
                  isExtra ? " is-extra" : ""
                }`}
                key={member.slug}
                onClick={() => navigate(`/filmium/actors/${member.slug}`)}
                ref={(node) => {
                  cardRefs.current[index] = node;
                }}
                style={
                  isExtra
                    ? ({
                        "--filmium-cast-stagger": index - (rowCount ?? 0),
                      } as CSSProperties)
                    : undefined
                }
                title={member.name}
                type="button"
              >
                <div className="filmium-details-cast-card-visual">
                  {imageUrl ? (
                    <img alt="" loading="lazy" src={imageUrl} />
                  ) : (
                    <div className="filmium-details-cast-card-fallback">
                      <span>{castInitials(member.name)}</span>
                    </div>
                  )}
                  {Boolean(member.is_director) && (
                    <span className="filmium-details-cast-badge">
                      Reditelj
                    </span>
                  )}
                </div>

                <div className="filmium-details-cast-card-copy">
                  <strong>{member.name}</strong>
                  {member.character && <span>{member.character}</span>}
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {canExpand && (
        <button
          className="filmium-details-cast-toggle"
          onClick={() => setExpanded((value) => !value)}
          type="button"
        >
          {expanded ? (
            <>
              <ChevronUp size={15} />
              Pokaži manje
            </>
          ) : (
            <>
              <ChevronDown size={15} />
              {`Pokaži više (${hiddenCount})`}
            </>
          )}
        </button>
      )}
    </section>
  );
}

export default FilmiumCastSection;
