import { useEffect, useState } from "react";

import {
  addMediaToFilmiumCollection,
  createFilmiumCollection,
  deleteFilmiumCollection,
  getFilmiumCollections,
  removeMediaFromFilmiumCollection,
} from "../../../services/filmiumApi";

import type {
  CollectionCreateRequest,
  MediaCollection,
} from "../../../types/filmium";


// ==========          FILMIUM KOLEKCIJE          ==========

/**
 * Upravlja FILMIUM kolekcijama i članstvom sadržaja.
 */
export function useFilmiumCollections() {
  const [collections, setCollections] =
    useState<MediaCollection[]>([]);

  const [isLoadingCollections, setIsLoadingCollections] =
    useState(true);

  const [collectionErrorMessage, setCollectionErrorMessage] =
    useState<string | null>(null);

  const [membershipErrorMessage, setMembershipErrorMessage] =
    useState<string | null>(null);

  const [deletingCollectionId, setDeletingCollectionId] =
    useState<number | null>(null);

  const [busyMembershipKey, setBusyMembershipKey] =
    useState<string | null>(null);

  // ==========          UČITAVANJE KOLEKCIJA          ==========

  useEffect(() => {
    let isMounted = true;

    /**
     * Učitava sve FILMIUM kolekcije.
     */
    async function loadCollections(): Promise<void> {
      try {
        const loadedCollections =
          await getFilmiumCollections();

        if (isMounted) {
          setCollections(loadedCollections);
          setCollectionErrorMessage(null);
        }
      } catch (error) {
        if (isMounted) {
          setCollectionErrorMessage(
            error instanceof Error
              ? error.message
              : "Učitavanje FILMIUM kolekcija nije uspelo.",
          );
        }
      } finally {
        if (isMounted) {
          setIsLoadingCollections(false);
        }
      }
    }

    void loadCollections();

    return () => {
      isMounted = false;
    };
  }, []);

  // ==========          ČLANSTVO KOLEKCIJA          ==========

  /**
   * Dodaje FILMIUM sadržaj u izabranu kolekciju.
   */
  async function addToCollection(
    collectionId: number,
    itemId: number,
  ): Promise<void> {
    const membershipKey = `${collectionId}:${itemId}`;

    try {
      setBusyMembershipKey(membershipKey);
      setMembershipErrorMessage(null);

      const updatedCollection =
        await addMediaToFilmiumCollection(
          collectionId,
          itemId,
        );

      setCollections((currentCollections) =>
        currentCollections.map((collection) =>
          collection.id === updatedCollection.id
            ? updatedCollection
            : collection,
        ),
      );
    } catch (error) {
      setMembershipErrorMessage(
        error instanceof Error
          ? error.message
          : "Dodavanje sadržaja u kolekciju nije uspelo.",
      );
    } finally {
      setBusyMembershipKey(null);
    }
  }

  /**
   * Uklanja FILMIUM sadržaj iz izabrane kolekcije.
   */
  async function removeFromCollection(
    collectionId: number,
    itemId: number,
  ): Promise<void> {
    const membershipKey = `${collectionId}:${itemId}`;

    try {
      setBusyMembershipKey(membershipKey);
      setMembershipErrorMessage(null);

      const updatedCollection =
        await removeMediaFromFilmiumCollection(
          collectionId,
          itemId,
        );

      setCollections((currentCollections) =>
        currentCollections.map((collection) =>
          collection.id === updatedCollection.id
            ? updatedCollection
            : collection,
        ),
      );
    } catch (error) {
      setMembershipErrorMessage(
        error instanceof Error
          ? error.message
          : "Uklanjanje sadržaja iz kolekcije nije uspelo.",
      );
    } finally {
      setBusyMembershipKey(null);
    }
  }

  // ==========          COLLECTION AKCIJE          ==========

  /**
   * Kreira novu FILMIUM kolekciju.
   */
  async function createCollection(
    request: CollectionCreateRequest,
  ): Promise<void> {
    setCollectionErrorMessage(null);

    const createdCollection =
      await createFilmiumCollection(request);

    setCollections((currentCollections) =>
      [...currentCollections, createdCollection].sort(
        (firstCollection, secondCollection) =>
          firstCollection.name.localeCompare(
            secondCollection.name,
          ),
      ),
    );
  }

  /**
   * Traži potvrdu i briše FILMIUM kolekciju.
   */
  async function deleteCollection(
    collection: MediaCollection,
  ): Promise<void> {
    const shouldDelete = window.confirm(
      `Da li sigurno želiš da obrišeš kolekciju "${collection.name}"?`,
    );

    if (!shouldDelete) {
      return;
    }

    try {
      setDeletingCollectionId(collection.id);
      setCollectionErrorMessage(null);

      await deleteFilmiumCollection(collection.id);

      setCollections((currentCollections) =>
        currentCollections.filter(
          (currentCollection) =>
            currentCollection.id !== collection.id,
        ),
      );
    } catch (error) {
      setCollectionErrorMessage(
        error instanceof Error
          ? error.message
          : "Brisanje FILMIUM kolekcije nije uspelo.",
      );
    } finally {
      setDeletingCollectionId(null);
    }
  }

  /**
   * Uklanja obrisani sadržaj iz lokalnog stanja kolekcija.
   */
  function removeMediaReferences(itemId: number): void {
    setCollections((currentCollections) =>
      currentCollections.map((collection) => ({
        ...collection,
        item_ids: collection.item_ids.filter(
          (currentItemId) => currentItemId !== itemId,
        ),
      })),
    );
  }

  return {
    addToCollection,
    busyMembershipKey,
    collectionErrorMessage,
    collections,
    createCollection,
    deleteCollection,
    deletingCollectionId,
    isLoadingCollections,
    membershipErrorMessage,
    removeFromCollection,
    removeMediaReferences,
  };
}