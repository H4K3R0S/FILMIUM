import {
  deleteRequest,
  getJson,
  postFormData,
  postJson,
} from "./httpClient";
import { postRequest } from "./httpClient";
import type {
  WishlistAssetKind,
  WishlistEntry,
  WishlistEntryCreateRequest,
  WishlistReconcileResult,
  WishlistTmdbPreview,
  WishlistTmdbPreviewRequest,
  WishlistTranslateRequest,
  WishlistTranslateResult,
} from "../types/filmiumWishlist";


const BASE = "/api/v1/filmium/wishlist";


// ==========          LISTA „ZA PREUZETI" API          ==========

/** Učitava sve naslove iz liste za preuzimanje. */
export function getWishlist(): Promise<WishlistEntry[]> {
  return getJson<WishlistEntry[]>(BASE);
}

/** Dodaje novi naslov u listu za preuzimanje. */
export function createWishlistEntry(
  request: WishlistEntryCreateRequest,
): Promise<WishlistEntry> {
  return postJson<WishlistEntry, WishlistEntryCreateRequest>(
    BASE,
    request,
  );
}

/** Briše naslov iz liste za preuzimanje. */
export function deleteWishlistEntry(entryId: number): Promise<void> {
  return deleteRequest(`${BASE}/${entryId}`);
}

/** Otprema jednu datoteku (slika ili titl) uz stavku. */
export function uploadWishlistAsset(
  entryId: number,
  kind: WishlistAssetKind,
  file: File | Blob,
  filename?: string,
): Promise<WishlistEntry> {
  const formData = new FormData();
  formData.append("kind", kind);
  formData.append(
    "file",
    file,
    filename ?? (file instanceof File ? file.name : "asset"),
  );

  return postFormData<WishlistEntry>(
    `${BASE}/${entryId}/asset`,
    formData,
  );
}

/** Usklađuje listu sa bibliotekom — uklanja naslove koji su već ušli. */
export function reconcileWishlist(): Promise<WishlistReconcileResult> {
  return postRequest<WishlistReconcileResult>(`${BASE}/reconcile`);
}

/** Server preuzima TMDB sliku (poster/backdrop) i beleži je uz stavku. */
export function saveWishlistTmdbImage(
  entryId: number,
  kind: "poster" | "backdrop",
  url: string,
): Promise<WishlistEntry> {
  return postJson<WishlistEntry, { kind: "poster" | "backdrop"; url: string }>(
    `${BASE}/${entryId}/tmdb-image`,
    { kind, url },
  );
}

/** Traži naslov na TMDB-u radi popune forme (bez upisa). */
export function fetchWishlistTmdbPreview(
  request: WishlistTmdbPreviewRequest,
): Promise<WishlistTmdbPreview> {
  return postJson<WishlistTmdbPreview, WishlistTmdbPreviewRequest>(
    `${BASE}/tmdb-preview`,
    request,
  );
}

/** Prevodi naslov + opis na domaći (bosanski) preko servera. */
export function translateWishlistText(
  request: WishlistTranslateRequest,
): Promise<WishlistTranslateResult> {
  return postJson<WishlistTranslateResult, WishlistTranslateRequest>(
    `${BASE}/translate`,
    request,
  );
}
