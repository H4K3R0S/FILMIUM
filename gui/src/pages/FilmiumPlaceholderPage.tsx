// ==========          SVOJSTVA STRANICE          ==========

type FilmiumPlaceholderPageProps = {
  eyebrow: string;
  title: string;
  description: string;
};


// ==========          PRIVREMENI FILMIUM EKRAN          ==========

/**
 * Čuva mesto za FILMIUM ekran dok njegova funkcionalnost ne bude
 * premeštena iz početne stranice.
 */
function FilmiumPlaceholderPage({
  eyebrow,
  title,
  description,
}: FilmiumPlaceholderPageProps) {
  return (
    <section className="filmium-section filmium-placeholder-page">
      <div className="section-heading">
        <p className="eyebrow">{eyebrow}</p>
        <h2>{title}</h2>
      </div>

      <p className="filmium-placeholder-description">
        {description}
      </p>

      <span className="filmium-placeholder-status">
        Ekran je pripremljen za sledeću fazu razvoja.
      </span>
    </section>
  );
}

export default FilmiumPlaceholderPage;