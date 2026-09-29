import { openPathDialog } from "../../../lib/pathPicker";

import { replaceFilmiumFile } from "../../../services/filmiumLibraryApi";


type PickFilter = { name: string; extensions: string[] };


/**
 * Otvara birač fajlova i zamenjuje postojeći fajl izabranim (kopira ga
 * preko postojećeg). Vraća ``true`` ako je zamena izvršena.
 */
export async function pickAndReplaceFile(
  rootId: number,
  relativePath: string,
  filter: PickFilter,
  title: string,
): Promise<boolean> {
  const selected = await openPathDialog({
    multiple: false,
    title,
    filters: [filter],
  });

  if (typeof selected !== "string") {
    return false;
  }

  const result = await replaceFilmiumFile(rootId, relativePath, selected);
  return result.replaced;
}


/** Zamena slike (poster/backdrop/wallpaper/fanart). */
export function pickAndReplaceArtwork(
  rootId: number,
  relativePath: string,
): Promise<boolean> {
  return pickAndReplaceFile(
    rootId,
    relativePath,
    { name: "Slike", extensions: ["jpg", "jpeg", "png", "webp", "bmp"] },
    "Izaberi novu sliku",
  );
}


/** Zamena prevoda (.srt / .sub / .ass / .vtt / .idx). */
export function pickAndReplaceSubtitle(
  rootId: number,
  relativePath: string,
): Promise<boolean> {
  return pickAndReplaceFile(
    rootId,
    relativePath,
    { name: "Prevodi", extensions: ["srt", "sub", "ass", "ssa", "vtt", "idx"] },
    "Izaberi novi prevod",
  );
}
