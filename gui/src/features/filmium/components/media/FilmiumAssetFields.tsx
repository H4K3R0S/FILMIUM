import { useState, type ChangeEvent } from "react";

import {
  deleteFilmiumMediaAsset,
  getFilmiumAssetUrl,
  uploadFilmiumMediaAsset,
} from "../../../../services/filmiumApi";

import type {
  MediaAssetType,
  MediaItem,
} from "../../../../types/filmium";


// ==========          SVOJSTVA KOMPONENTE          ==========

type FilmiumAssetFieldsProps = {
  item: MediaItem;
  onUpdated: (item: MediaItem) => void;
};


// ==========          FILMIUM ASSET POLJE          ==========

/**
 * Omogućava pregled, upload, zamenu i uklanjanje FILMIUM slika.
 */
function FilmiumAssetFields({
  item,
  onUpdated,
}: FilmiumAssetFieldsProps) {
  const [busyAssetType, setBusyAssetType] =
    useState<MediaAssetType | null>(null);

  const [errorMessage, setErrorMessage] =
    useState<string | null>(null);

  const posterUrl = getFilmiumAssetUrl(item.poster_path);
  const backdropUrl = getFilmiumAssetUrl(item.backdrop_path);

  /**
   * Uploaduje izabranu sliku i prosleđuje ažurirani sadržaj roditelju.
   */
  async function handleFileChange(
    assetType: MediaAssetType,
    event: ChangeEvent<HTMLInputElement>,
  ): Promise<void> {
    const file = event.target.files?.[0];

    if (!file) {
      return;
    }

    try {
      setBusyAssetType(assetType);
      setErrorMessage(null);

      const updatedItem = await uploadFilmiumMediaAsset(
        item.id,
        assetType,
        file,
      );

      onUpdated(updatedItem);
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : "Čuvanje FILMIUM slike nije uspelo.",
      );
    } finally {
      setBusyAssetType(null);

      // Omogućava ponovni izbor iste datoteke.
      event.target.value = "";
    }
  }

  /**
   * Uklanja izabrani asset nakon potvrde korisnika.
   */
  async function handleDelete(
    assetType: MediaAssetType,
  ): Promise<void> {
    const assetLabel =
      assetType === "poster" ? "poster" : "backdrop";

    const shouldDelete = window.confirm(
      `Da li sigurno želiš da ukloniš ${assetLabel} sliku?`,
    );

    if (!shouldDelete) {
      return;
    }

    try {
      setBusyAssetType(assetType);
      setErrorMessage(null);

      const updatedItem = await deleteFilmiumMediaAsset(
        item.id,
        assetType,
      );

      onUpdated(updatedItem);
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : "Uklanjanje FILMIUM slike nije uspelo.",
      );
    } finally {
      setBusyAssetType(null);
    }
  }

  return (
    <section className="filmium-asset-fields">
      {/* ==========          NASLOV SEKCIJE          ========== */}

      <div className="filmium-asset-fields-heading">
        <div>
          <span>Vizuelni asseti</span>
          <p>
            Dodaj poster za kartice i backdrop za istaknuti prikaz.
          </p>
        </div>
      </div>

      {/* ==========          ASSET POLJA          ========== */}

      <div className="filmium-asset-fields-grid">
        <article className="filmium-asset-field">
          <div className="filmium-asset-preview poster">
            {posterUrl ? (
              <img
                alt={`Poster za ${item.title}`}
                src={posterUrl}
              />
            ) : (
              <span>Poster nije dodat</span>
            )}
          </div>

          <div className="filmium-asset-field-content">
            <div>
              <strong>Poster</strong>
              <span>JPEG, PNG ili WebP · najviše 20 MB</span>
            </div>

            <div className="filmium-asset-actions">
              <label className="secondary-button">
                <input
                  accept="image/jpeg,image/png,image/webp"
                  disabled={busyAssetType !== null}
                  onChange={(event) =>
                    void handleFileChange("poster", event)
                  }
                  type="file"
                />

                {busyAssetType === "poster"
                  ? "Čuvanje..."
                  : posterUrl
                    ? "Zameni"
                    : "Izaberi poster"}
              </label>

              {posterUrl && (
                <button
                  className="danger-button"
                  disabled={busyAssetType !== null}
                  onClick={() => void handleDelete("poster")}
                  type="button"
                >
                  Ukloni
                </button>
              )}
            </div>
          </div>
        </article>

        <article className="filmium-asset-field">
          <div className="filmium-asset-preview backdrop">
            {backdropUrl ? (
              <img
                alt={`Backdrop za ${item.title}`}
                src={backdropUrl}
              />
            ) : (
              <span>Backdrop nije dodat</span>
            )}
          </div>

          <div className="filmium-asset-field-content">
            <div>
              <strong>Backdrop</strong>
              <span>JPEG, PNG ili WebP · najviše 20 MB</span>
            </div>

            <div className="filmium-asset-actions">
              <label className="secondary-button">
                <input
                  accept="image/jpeg,image/png,image/webp"
                  disabled={busyAssetType !== null}
                  onChange={(event) =>
                    void handleFileChange("backdrop", event)
                  }
                  type="file"
                />

                {busyAssetType === "backdrop"
                  ? "Čuvanje..."
                  : backdropUrl
                    ? "Zameni"
                    : "Izaberi backdrop"}
              </label>

              {backdropUrl && (
                <button
                  className="danger-button"
                  disabled={busyAssetType !== null}
                  onClick={() => void handleDelete("backdrop")}
                  type="button"
                >
                  Ukloni
                </button>
              )}
            </div>
          </div>
        </article>
      </div>

      {errorMessage && (
        <p className="system-message error">{errorMessage}</p>
      )}
    </section>
  );
}

export default FilmiumAssetFields;