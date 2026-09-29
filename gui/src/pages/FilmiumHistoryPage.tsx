import {
  Clock3,
  RefreshCw,
} from "lucide-react";

import { useFilmiumActivity } from "../features/filmium/hooks/useFilmiumActivity";
import type { ActivityEventType } from "../types/filmium";


// ==========          ACTIVITY OZNAKE          ==========

const activityLabels: Record<ActivityEventType, string> = {
  media_created: "Sadržaj dodat",
  media_updated: "Sadržaj izmenjen",
  media_deleted: "Sadržaj obrisan",
  favorite_added: "Dodato u favorite",
  favorite_removed: "Uklonjeno iz favorita",
  collection_created: "Kolekcija kreirana",
  collection_deleted: "Kolekcija obrisana",
  collection_media_added: "Dodato u kolekciju",
  collection_media_removed: "Uklonjeno iz kolekcije",
};

const activityDateFormatter = new Intl.DateTimeFormat(
  "sr-Latn-RS",
  {
    dateStyle: "medium",
    timeStyle: "short",
  },
);


// ==========          FILMIUM HISTORY EKRAN          ==========

/**
 * Prikazuje trajno zabeleženu istoriju FILMIUM aktivnosti.
 */
function FilmiumHistoryPage() {
  const {
    activityItems,
    errorMessage,
    isLoading,
    refreshActivity,
  } = useFilmiumActivity();

  return (
    <section className="filmium-section filmium-history-page">
      <div className="filmium-history-heading">
        <div className="section-heading">
          <p className="eyebrow">FILMIUM Activity</p>
          <h2>Istorija</h2>

          <p className="filmium-page-description">
            Pregled promena sadržaja, favorita i kolekcija.
          </p>
        </div>

        <button
          className="secondary-button"
          disabled={isLoading}
          onClick={() => void refreshActivity()}
          type="button"
        >
          <RefreshCw
            className={isLoading ? "rotating" : ""}
            size={17}
          />

          {isLoading ? "Osvežavanje..." : "Osveži"}
        </button>
      </div>

      {errorMessage && (
        <p className="system-message error">
          {errorMessage}
        </p>
      )}

      {!isLoading && !errorMessage
        && activityItems.length === 0 && (
          <p className="system-message">
            FILMIUM istorija je trenutno prazna.
          </p>
        )}

      {activityItems.length > 0 && (
        <div className="filmium-activity-list">
          {activityItems.map((activity) => (
            <article
              className="filmium-activity-item"
              key={activity.id}
            >
              <span
                className={`filmium-activity-icon ${activity.entity_type}`}
              >
                <Clock3 size={17} />
              </span>

              <div className="filmium-activity-content">
                <strong>{activity.title}</strong>

                <span>
                  {activityLabels[activity.event_type]}
                </span>
              </div>

              <time dateTime={activity.created_at}>
                {activityDateFormatter.format(
                  new Date(activity.created_at),
                )}
              </time>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

export default FilmiumHistoryPage;