import { Download, Trash2 } from "lucide-react";

import { getFilmiumAssetUrl } from "../../../../services/filmiumApi";
import type { WishlistEntry } from "../../../../types/filmiumWishlist";


// ==========          SVOJSTVA          ==========

type FilmiumWishlistShelfProps = {
  entries: WishlistEntry[];
  onRemove: (entryId: number) => void;
};


// ==========          OZNAKA KATEGORIJE          ==========

const CATEGORY_LABEL: Record<string, string> = {
  regular: "STRANO",
  domestic: "DOMAĆE",
  animated: "ANIMIRANO",
};


// ==========          HOME RED „ZA PREUZETI"          ==========

/**
 * Prikazuje predloge filmova/serija koje korisnik planira da preuzme.
 */
function FilmiumWishlistShelf({
  entries,
  onRemove,
}: FilmiumWishlistShelfProps) {
  if (entries.length === 0) {
    return null;
  }

  return (
    <section className="filmium-home-shelf filmium-wishlist-shelf">
      <div className="filmium-home-shelf-heading">
        <h2>
          <Download aria-hidden="true" size={16} />
          FILMOVI ZA PREUZETI
        </h2>
        <span>{entries.length} naslova</span>
      </div>

      <div className="filmium-home-shelf-track">
        {entries.map((entry) => {
          const posterUrl = getFilmiumAssetUrl(
            entry.poster_path ?? entry.backdrop_path,
          );

          return (
            <article
              className="filmium-shelf-card poster filmium-wishlist-card"
              key={entry.id}
            >
              <div className="filmium-shelf-card-visual">
                {posterUrl ? (
                  <img alt="" loading="lazy" src={posterUrl} />
                ) : (
                  <div className="filmium-shelf-card-fallback">
                    <span>
                      {entry.media_type === "movie" ? "FILM" : "SERIJA"}
                    </span>
                  </div>
                )}

                <div className="filmium-shelf-card-shade" />

                <span className="filmium-wishlist-badge">
                  {CATEGORY_LABEL[entry.content_category] ?? "STRANO"}
                </span>

                {(entry.is_subtitled || entry.is_synchronized) && (
                  <span className="filmium-wishlist-audio">
                    {entry.is_subtitled ? "TITL" : ""}
                    {entry.is_subtitled && entry.is_synchronized ? " · " : ""}
                    {entry.is_synchronized ? "SINH" : ""}
                  </span>
                )}

                <button
                  aria-label={`Ukloni ${entry.title} iz liste za preuzimanje`}
                  className="filmium-wishlist-remove"
                  onClick={() => onRemove(entry.id)}
                  title="Ukloni iz liste"
                  type="button"
                >
                  <Trash2 aria-hidden="true" size={15} />
                </button>
              </div>

              <div className="filmium-shelf-card-content">
                <strong>{entry.title}</strong>
                <span>
                  {entry.release_year ?? "Godina nije uneta"}
                  {" · "}
                  {entry.media_type === "movie" ? "Film" : "Serija"}
                </span>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}

export default FilmiumWishlistShelf;
