import {
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type DragEvent,
} from "react";
import {
  ChevronLeft,
  Languages,
  Loader2,
  Search,
  UploadCloud,
  X,
} from "lucide-react";

import {
  createWishlistEntry,
  fetchWishlistTmdbPreview,
  saveWishlistTmdbImage,
  translateWishlistText,
  uploadWishlistAsset,
} from "../../../../services/filmiumWishlistApi";
import type {
  WishlistAssetKind,
  WishlistCategory,
  WishlistMediaType,
} from "../../../../types/filmiumWishlist";
import "../../styles/filmium-acquire.css";


// ==========          TRAJANJE FADE EFEKTA          ==========

/** Fade in/out — srednje spor. Mora odgovarati CSS trajanju. */
const FADE_MS = 300;


// ==========          SVOJSTVA          ==========

/** Početne vrednosti forme (npr. iz „Povezani" ne-owned kartice). */
export type FilmiumAcquirePrefill = {
  title: string;
  year: number | null;
  media_type: WishlistMediaType;
  tmdb_id: number | null;
};

type FilmiumAcquireModalProps = {
  open: boolean;
  onClose: () => void;
  /** Poziva se posle uspešnog „Dodaj" (Home osvežava listu). */
  onAdded: () => void;
  /** Popuni formu pri otvaranju (naslov/godina/tip/tmdb_id). */
  prefill?: FilmiumAcquirePrefill | null;
};


// ==========          KATEGORIJE          ==========

const CATEGORY_OPTIONS: [WishlistCategory, string][] = [
  ["regular", "STRANO"],
  ["domestic", "DOMAĆE"],
  ["animated", "ANIMIRANO"],
];


// ==========          MODAL „ZA PREUZETI"          ==========

/**
 * Centralni prozor za dodavanje filma/serije u listu za preuzimanje.
 * Otvara se sa fade-in, gasi sa fade-out (klik van okvira ili „nazad").
 */
function FilmiumAcquireModal({
  open,
  onClose,
  onAdded,
  prefill,
}: FilmiumAcquireModalProps) {
  // Odloženo demontiranje da fade-out stigne da se odigra.
  const [mounted, setMounted] = useState(open);
  const [visible, setVisible] = useState(false);

  // Polja forme.
  const [category, setCategory] = useState<WishlistCategory | null>(null);
  const [mediaType, setMediaType] = useState<WishlistMediaType>("movie");
  const [isSubtitled, setIsSubtitled] = useState(false);
  const [isSynchronized, setIsSynchronized] = useState(false);
  const [title, setTitle] = useState("");
  const [originalTitle, setOriginalTitle] = useState("");
  const [localTitle, setLocalTitle] = useState("");
  const [year, setYear] = useState("");
  const [englishOverview, setEnglishOverview] = useState("");
  const [localOverview, setLocalOverview] = useState("");
  const [isTranslating, setIsTranslating] = useState(false);
  const [tmdbId, setTmdbId] = useState<number | null>(null);

  // Datoteke (slike / titlovi / dodatno).
  const [poster, setPoster] = useState<File | null>(null);
  const [backdrop, setBackdrop] = useState<File | null>(null);
  const [wallpaper, setWallpaper] = useState<File | null>(null);
  const [originalSub, setOriginalSub] = useState<File | null>(null);
  const [domesticSub, setDomesticSub] = useState<File | null>(null);
  const [englishSub, setEnglishSub] = useState<File | null>(null);
  const [extras, setExtras] = useState<File[]>([]);

  // TMDB slike (URL) — koriste se kao fallback poster/backdrop pri „Dodaj".
  const [tmdbPosterUrl, setTmdbPosterUrl] = useState<string | null>(null);
  const [tmdbBackdropUrl, setTmdbBackdropUrl] = useState<string | null>(null);

  const [isSearching, setIsSearching] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Indikator prevlačenja preko celog prozora. Brojač dubine sprečava
  // treperenje dok kursor prelazi preko dece (polja).
  const [isFileDragging, setIsFileDragging] = useState(false);
  const dragDepth = useRef(0);

  const closeTimer = useRef<number | null>(null);

  // Sinhronizacija prop-a otvorenosti sa fade stanjem.
  //
  // Ovde se stanje NAMERNO menja iz efekta. Prozor mora da ostane u stablu dok
  // traje fade-out, a to znači da mu treba prethodna vrednost `open` — jedini
  // način da se sazna da je otvoren prozor upravo počeo da se zatvara. Izvesti
  // se ne može: prikaz zavisi od promene, ne od trenutne vrednosti.
  useEffect(() => {
    if (open) {
      if (closeTimer.current !== null) {
        window.clearTimeout(closeTimer.current);
        closeTimer.current = null;
      }
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setMounted(true);
      // Sledeći frame pali is-open klasu (pokreće fade-in).
      const frame = window.requestAnimationFrame(() => setVisible(true));
      return () => window.cancelAnimationFrame(frame);
    }

    setVisible(false);
    closeTimer.current = window.setTimeout(() => {
      setMounted(false);
    }, FADE_MS);

    return () => {
      if (closeTimer.current !== null) {
        window.clearTimeout(closeTimer.current);
        closeTimer.current = null;
      }
    };
  }, [open]);

  // Reset forme svaki put kad se prozor ponovo otvori.
  //
  // I ovde je promena, a ne trenutna vrednost, ono što nosi odluku: prazna
  // polja traži OTVARANJE prozora. Isto bi se dobilo `key`-em na formi, ali to
  // traži razdvajanje ovog prozora na ljusku i formu — zaseban posao.
  useEffect(() => {
    if (!open) {
      return;
    }

    // eslint-disable-next-line react-hooks/set-state-in-effect
    setCategory(null);
    setMediaType(prefill?.media_type ?? "movie");
    setIsSubtitled(false);
    setIsSynchronized(false);
    setTitle(prefill?.title ?? "");
    setOriginalTitle("");
    setLocalTitle("");
    setYear(prefill?.year != null ? String(prefill.year) : "");
    setEnglishOverview("");
    setLocalOverview("");
    setIsTranslating(false);
    setTmdbId(prefill?.tmdb_id ?? null);
    setPoster(null);
    setBackdrop(null);
    setWallpaper(null);
    setOriginalSub(null);
    setDomesticSub(null);
    setEnglishSub(null);
    setExtras([]);
    setTmdbPosterUrl(null);
    setTmdbBackdropUrl(null);
    setStatusMessage(null);
    setErrorMessage(null);
    setIsSearching(false);
    setIsSaving(false);
    dragDepth.current = 0;
    setIsFileDragging(false);
  }, [open, prefill]);

  // Escape zatvara prozor.
  useEffect(() => {
    if (!open) {
      return;
    }

    function handleKey(event: KeyboardEvent): void {
      if (event.key === "Escape") {
        onClose();
      }
    }

    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [open, onClose]);

  if (!mounted) {
    return null;
  }

  const parsedYear = year.trim() === "" ? null : Number.parseInt(year, 10);

  // ==========          TMDB PRETRAGA          ==========

  async function handleTmdbSearch(): Promise<void> {
    if (title.trim() === "") {
      setErrorMessage("Prvo upiši ime filma ili serije.");
      return;
    }

    setIsSearching(true);
    setErrorMessage(null);
    setStatusMessage(null);

    try {
      const preview = await fetchWishlistTmdbPreview({
        title: title.trim(),
        year: parsedYear,
        media_type: mediaType,
      });

      if (!preview.available) {
        setErrorMessage("TMDB nije dostupan (nema API ključa).");
        return;
      }

      if (!preview.matched) {
        setStatusMessage("TMDB nije našao poklapanje za taj naslov.");
        return;
      }

      // Popuni polja koja korisnik nije popunio.
      const bestTitle =
        preview.local_title || preview.english_title || preview.original_title;
      if (bestTitle) {
        setTitle(bestTitle);
      }
      if (preview.original_title) {
        setOriginalTitle(preview.original_title);
      }
      if (preview.local_title) {
        setLocalTitle(preview.local_title);
      }
      if (preview.year !== null) {
        setYear(String(preview.year));
      }
      if (preview.english_overview) {
        setEnglishOverview(preview.english_overview);
      }
      if (preview.local_overview) {
        setLocalOverview(preview.local_overview);
      }
      setTmdbId(preview.tmdb_id);
      setTmdbPosterUrl(preview.poster_url);
      setTmdbBackdropUrl(preview.backdrop_url);
      setStatusMessage("TMDB podaci popunjeni.");
    } catch {
      setErrorMessage("TMDB pretraga nije uspela.");
    } finally {
      setIsSearching(false);
    }
  }

  // ==========          PREVOD OPISA (EN → BOSANSKI)          ==========

  async function handleTranslateLocal(): Promise<void> {
    const sourceTitle = (originalTitle || title).trim();
    const sourceOverview = englishOverview.trim();
    if (sourceTitle === "" && sourceOverview === "") {
      setErrorMessage("Nema engleskog opisa ni naslova za prevod.");
      return;
    }

    setIsTranslating(true);
    setErrorMessage(null);
    setStatusMessage(null);

    try {
      const result = await translateWishlistText({
        title: sourceTitle,
        overview: sourceOverview,
      });

      if (!result.available) {
        setErrorMessage("Prevodilac trenutno ne radi.");
        return;
      }

      if (result.overview) {
        setLocalOverview(result.overview);
      }
      // Domaći naslov popuni samo ako je prazan (ne gazi ručni unos).
      if (result.title && localTitle.trim() === "") {
        setLocalTitle(result.title);
      }
      setStatusMessage("Prevedeno na bosanski.");
    } catch {
      setErrorMessage("Prevod nije uspeo.");
    } finally {
      setIsTranslating(false);
    }
  }

  // ==========          DODAJ (ČUVANJE)          ==========

  async function uploadOptional(
    entryId: number,
    kind: WishlistAssetKind,
    file: File | null,
  ): Promise<void> {
    if (!file) {
      return;
    }
    try {
      await uploadWishlistAsset(entryId, kind, file);
    } catch {
      // Asseti su pomoćni — ne rušimo dodavanje zbog jedne datoteke.
    }
  }

  async function saveTmdbImage(
    entryId: number,
    kind: "poster" | "backdrop",
    url: string | null,
  ): Promise<void> {
    if (!url) {
      return;
    }
    try {
      // Server preuzima sliku (izbegava CORS na image.tmdb.org).
      await saveWishlistTmdbImage(entryId, kind, url);
    } catch {
      // TMDB slika je opciona.
    }
  }

  async function handleAdd(): Promise<void> {
    if (title.trim() === "") {
      setErrorMessage("Ime filma ili serije je obavezno.");
      return;
    }

    setIsSaving(true);
    setErrorMessage(null);
    setStatusMessage("Čuvam...");

    try {
      const entry = await createWishlistEntry({
        title: title.trim(),
        release_year: parsedYear,
        media_type: mediaType,
        content_category: category ?? "regular",
        is_subtitled: isSubtitled,
        is_synchronized: isSynchronized,
        tmdb_id: tmdbId,
        english_overview: englishOverview.trim() || null,
        local_overview: localOverview.trim() || null,
        original_title: originalTitle.trim() || null,
        local_title: localTitle.trim() || null,
      });

      // Slike: prednost ima ono što je korisnik ubacio, pa TMDB fallback.
      if (poster) {
        await uploadOptional(entry.id, "poster", poster);
      } else {
        await saveTmdbImage(entry.id, "poster", tmdbPosterUrl);
      }

      if (backdrop) {
        await uploadOptional(entry.id, "backdrop", backdrop);
      } else {
        await saveTmdbImage(entry.id, "backdrop", tmdbBackdropUrl);
      }

      await uploadOptional(entry.id, "wallpaper", wallpaper);
      await uploadOptional(entry.id, "original_subtitle", originalSub);
      await uploadOptional(entry.id, "domestic_subtitle", domesticSub);
      await uploadOptional(entry.id, "english_subtitle", englishSub);

      for (const extra of extras) {
        await uploadOptional(entry.id, "extra", extra);
      }

      onAdded();
      onClose();
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Dodavanje nije uspelo.";
      setErrorMessage(message);
      setStatusMessage(null);
    } finally {
      setIsSaving(false);
    }
  }

  // ==========          RENDER          ==========

  // Da li „drag" nosi datoteku (a ne npr. tekst/izbor)?
  function isFileDrag(event: DragEvent<HTMLDivElement>): boolean {
    return Array.from(event.dataTransfer.types).includes("Files");
  }

  function handlePanelDragEnter(event: DragEvent<HTMLDivElement>): void {
    if (!isFileDrag(event)) {
      return;
    }
    dragDepth.current += 1;
    setIsFileDragging(true);
  }

  function handlePanelDragOver(event: DragEvent<HTMLDivElement>): void {
    if (isFileDrag(event)) {
      event.preventDefault();
    }
  }

  function handlePanelDragLeave(event: DragEvent<HTMLDivElement>): void {
    if (!isFileDrag(event)) {
      return;
    }
    dragDepth.current = Math.max(0, dragDepth.current - 1);
    if (dragDepth.current === 0) {
      setIsFileDragging(false);
    }
  }

  function handlePanelDrop(): void {
    dragDepth.current = 0;
    setIsFileDragging(false);
  }

  return (
    <div
      className={`filmium-acquire-overlay${visible ? " is-open" : ""}`}
      onClick={onClose}
      role="presentation"
    >
      <div
        aria-label="Dodaj u listu za preuzeti"
        aria-modal="true"
        className={
          "filmium-acquire-panel"
          + (isFileDragging ? " is-file-dragging" : "")
        }
        onClick={(event) => event.stopPropagation()}
        onDragEnter={handlePanelDragEnter}
        onDragLeave={handlePanelDragLeave}
        onDragOver={handlePanelDragOver}
        onDrop={handlePanelDrop}
        role="dialog"
      >
        {isFileDragging && (
          <div className="filmium-acquire-drag-banner">
            Režim prevlačenja — otpusti sliku na Poster, Backdrop ili Wallpaper
          </div>
        )}
        {/* ==========          ZAGLAVLJE          ========== */}

        <div className="filmium-acquire-header">
          <button
            aria-label="Nazad (zatvori)"
            className="filmium-acquire-back"
            onClick={onClose}
            title="Nazad"
            type="button"
          >
            <ChevronLeft aria-hidden="true" size={20} />
            <span>Nazad</span>
          </button>

          <h2>Dodaj za preuzeti</h2>

          <button
            aria-label="Zatvori"
            className="filmium-acquire-close"
            onClick={onClose}
            title="Zatvori"
            type="button"
          >
            <X aria-hidden="true" size={18} />
          </button>
        </div>

        {/* ==========          TELO          ========== */}

        <div className="filmium-acquire-body">
          {/* Kategorije */}
          <div className="filmium-acquire-toggle-row">
            {CATEGORY_OPTIONS.map(([value, label]) => (
              <button
                aria-pressed={category === value}
                className={`filmium-acquire-chip${
                  category === value ? " active" : ""
                }`}
                key={value}
                onClick={() =>
                  setCategory((current) =>
                    current === value ? null : value,
                  )
                }
                type="button"
              >
                {label}
              </button>
            ))}

            <span className="filmium-acquire-divider" />

            <button
              aria-pressed={isSubtitled}
              className={`filmium-acquire-chip${isSubtitled ? " active" : ""}`}
              onClick={() => setIsSubtitled((value) => !value)}
              type="button"
            >
              TITL
            </button>

            <button
              aria-pressed={isSynchronized}
              className={`filmium-acquire-chip${
                isSynchronized ? " active" : ""
              }`}
              onClick={() => setIsSynchronized((value) => !value)}
              type="button"
            >
              SINH
            </button>
          </div>

          {/* Tip (film/serija) */}
          <div className="filmium-acquire-toggle-row">
            <button
              aria-pressed={mediaType === "movie"}
              className={`filmium-acquire-chip${
                mediaType === "movie" ? " active" : ""
              }`}
              onClick={() => setMediaType("movie")}
              type="button"
            >
              FILM
            </button>

            <button
              aria-pressed={mediaType === "series"}
              className={`filmium-acquire-chip${
                mediaType === "series" ? " active" : ""
              }`}
              onClick={() => setMediaType("series")}
              type="button"
            >
              SERIJA
            </button>
          </div>

          {/* Ime + godina + TMDB */}
          <div className="filmium-acquire-fields">
            <label className="filmium-acquire-field grow">
              <span>Ime</span>
              <input
                onChange={(event) => setTitle(event.target.value)}
                placeholder="Ime filma ili serije"
                type="text"
                value={title}
              />
            </label>

            <label className="filmium-acquire-field narrow">
              <span>Godina</span>
              <input
                inputMode="numeric"
                onChange={(event) => setYear(event.target.value)}
                placeholder="npr. 2021"
                type="text"
                value={year}
              />
            </label>

            <button
              className="filmium-acquire-tmdb"
              disabled={isSearching}
              onClick={handleTmdbSearch}
              type="button"
            >
              {isSearching ? (
                <Loader2 className="spin" aria-hidden="true" size={16} />
              ) : (
                <Search aria-hidden="true" size={16} />
              )}
              Pretraži TMDB
            </button>
          </div>

          {/* Originalni + domaći naslov */}
          <div className="filmium-acquire-fields">
            <label className="filmium-acquire-field grow">
              <span>Originalni naslov</span>
              <input
                onChange={(event) => setOriginalTitle(event.target.value)}
                placeholder="Originalni naslov (izvorni jezik)"
                type="text"
                value={originalTitle}
              />
            </label>

            <label className="filmium-acquire-field grow">
              <span>Domaći naslov</span>
              <input
                onChange={(event) => setLocalTitle(event.target.value)}
                placeholder="Domaći naslov"
                type="text"
                value={localTitle}
              />
            </label>
          </div>

          {/* Slike */}
          <div className="filmium-acquire-drops">
            <FileDropField
              accept="image/*"
              file={poster}
              label="Poster"
              previewUrl={tmdbPosterUrl}
              onSelect={setPoster}
            />
            <FileDropField
              accept="image/*"
              file={backdrop}
              label="Backdrop"
              previewUrl={tmdbBackdropUrl}
              onSelect={setBackdrop}
            />
            <FileDropField
              accept="image/*"
              file={wallpaper}
              label="Wallpaper"
              onSelect={setWallpaper}
            />
          </div>

          {/* Dodatni sadržaj */}
          <MultiFileField files={extras} onChange={setExtras} />

          {/* Prevodi (titlovi) */}
          <div className="filmium-acquire-subs">
            <SubtitleField
              file={originalSub}
              label="Originalni Prevod"
              onSelect={setOriginalSub}
            />
            <SubtitleField
              file={domesticSub}
              label="Domaći Prevod"
              onSelect={setDomesticSub}
            />
            <SubtitleField
              file={englishSub}
              label="Engleski Prevod"
              onSelect={setEnglishSub}
            />
          </div>

          {/* Opisi */}
          <div className="filmium-acquire-overviews">
            <label className="filmium-acquire-field">
              <span>Engleski opis</span>
              <textarea
                onChange={(event) => setEnglishOverview(event.target.value)}
                placeholder="English description"
                rows={3}
                value={englishOverview}
              />
            </label>

            <label className="filmium-acquire-field">
              <span className="filmium-acquire-field-head">
                Domaći opis
                <button
                  className="filmium-acquire-translate"
                  disabled={isTranslating}
                  onClick={handleTranslateLocal}
                  title="Prevedi engleski opis na bosanski"
                  type="button"
                >
                  {isTranslating ? (
                    <Loader2 className="spin" aria-hidden="true" size={14} />
                  ) : (
                    <Languages aria-hidden="true" size={14} />
                  )}
                  Prevedi (BS)
                </button>
              </span>
              <textarea
                onChange={(event) => setLocalOverview(event.target.value)}
                placeholder="Domaći opis"
                rows={3}
                value={localOverview}
              />
            </label>
          </div>

          {(statusMessage || errorMessage) && (
            <p
              className={`filmium-acquire-status${
                errorMessage ? " error" : ""
              }`}
            >
              {errorMessage ?? statusMessage}
            </p>
          )}
        </div>

        {/* ==========          PODNOŽJE          ========== */}

        <div className="filmium-acquire-footer">
          <button
            className="filmium-acquire-add"
            disabled={isSaving}
            onClick={handleAdd}
            type="button"
          >
            {isSaving ? (
              <Loader2 className="spin" aria-hidden="true" size={18} />
            ) : null}
            Dodaj
          </button>
        </div>
      </div>
    </div>
  );
}


// ==========          DROP POLJE ZA SLIKU          ==========

type FileDropFieldProps = {
  accept: string;
  file: File | null;
  label: string;
  previewUrl?: string | null;
  onSelect: (file: File | null) => void;
};

/** Polje za sliku: klik za izbor ili prevlačenje datoteke. */
function FileDropField({
  accept,
  file,
  label,
  previewUrl,
  onSelect,
}: FileDropFieldProps) {
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const localPreview = file ? URL.createObjectURL(file) : null;

  useEffect(() => {
    return () => {
      if (localPreview) {
        URL.revokeObjectURL(localPreview);
      }
    };
  }, [localPreview]);

  const shownPreview = localPreview ?? previewUrl ?? null;

  function handleDrop(event: DragEvent<HTMLButtonElement>): void {
    event.preventDefault();
    setDragOver(false);
    const dropped = event.dataTransfer.files[0];
    if (dropped) {
      onSelect(dropped);
    }
  }

  function handleChange(event: ChangeEvent<HTMLInputElement>): void {
    const selected = event.target.files?.[0] ?? null;
    onSelect(selected);
  }

  return (
    <button
      className={`filmium-acquire-drop${dragOver ? " drag" : ""}${
        shownPreview ? " has-image" : ""
      }`}
      onClick={() => inputRef.current?.click()}
      onDragLeave={() => setDragOver(false)}
      onDragOver={(event) => {
        event.preventDefault();
        setDragOver(true);
      }}
      onDrop={handleDrop}
      type="button"
    >
      {shownPreview ? (
        <img alt="" src={shownPreview} />
      ) : (
        <>
          <UploadCloud aria-hidden="true" size={22} />
          <span>{label}</span>
        </>
      )}

      <input
        accept={accept}
        hidden
        onChange={handleChange}
        ref={inputRef}
        type="file"
      />

      {shownPreview && (
        <span className="filmium-acquire-drop-label">{label}</span>
      )}
    </button>
  );
}


// ==========          POLJE ZA TITL          ==========

type SubtitleFieldProps = {
  file: File | null;
  label: string;
  onSelect: (file: File | null) => void;
};

/** Polje za titl datoteku (.srt/.sub...). */
function SubtitleField({ file, label, onSelect }: SubtitleFieldProps) {
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);

  function handleDrop(event: DragEvent<HTMLButtonElement>): void {
    event.preventDefault();
    setDragOver(false);
    const dropped = event.dataTransfer.files[0];
    if (dropped) {
      onSelect(dropped);
    }
  }

  return (
    <button
      className={`filmium-acquire-sub${dragOver ? " drag" : ""}${
        file ? " has-file" : ""
      }`}
      onClick={() => inputRef.current?.click()}
      onDragLeave={() => setDragOver(false)}
      onDragOver={(event) => {
        event.preventDefault();
        setDragOver(true);
      }}
      onDrop={handleDrop}
      type="button"
    >
      <span className="filmium-acquire-sub-label">{label}</span>
      <span className="filmium-acquire-sub-file">
        {file ? file.name : "Prevuci ili klikni za titl"}
      </span>

      <input
        accept=".srt,.sub,.ass,.ssa,.vtt"
        hidden
        onChange={(event) => onSelect(event.target.files?.[0] ?? null)}
        ref={inputRef}
        type="file"
      />
    </button>
  );
}


// ==========          DODATNI SADRŽAJ (VIŠE FAJLOVA)          ==========

type MultiFileFieldProps = {
  files: File[];
  onChange: (files: File[]) => void;
};

/** Polje za dodatni sadržaj — više slika/titlova. */
function MultiFileField({ files, onChange }: MultiFileFieldProps) {
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);

  function addFiles(incoming: FileList | null): void {
    if (!incoming || incoming.length === 0) {
      return;
    }
    onChange([...files, ...Array.from(incoming)]);
  }

  function handleDrop(event: DragEvent<HTMLButtonElement>): void {
    event.preventDefault();
    setDragOver(false);
    addFiles(event.dataTransfer.files);
  }

  return (
    <div className="filmium-acquire-extra">
      <button
        className={`filmium-acquire-extra-drop${dragOver ? " drag" : ""}`}
        onClick={() => inputRef.current?.click()}
        onDragLeave={() => setDragOver(false)}
        onDragOver={(event) => {
          event.preventDefault();
          setDragOver(true);
        }}
        onDrop={handleDrop}
        type="button"
      >
        <UploadCloud aria-hidden="true" size={18} />
        <span>Dodatni sadržaj (prevuci ili klikni)</span>
        <input
          hidden
          multiple
          onChange={(event) => addFiles(event.target.files)}
          ref={inputRef}
          type="file"
        />
      </button>

      {files.length > 0 && (
        <ul className="filmium-acquire-extra-list">
          {files.map((file, index) => (
            <li key={`${file.name}-${index}`}>
              <span>{file.name}</span>
              <button
                aria-label={`Ukloni ${file.name}`}
                onClick={() =>
                  onChange(files.filter((_, position) => position !== index))
                }
                type="button"
              >
                <X aria-hidden="true" size={14} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default FilmiumAcquireModal;
