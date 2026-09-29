import { useState } from "react";
import { ChevronDown, ChevronUp, Tag, X } from "lucide-react";


// ==========          KONSTANTE          ==========

/** Broj ključnih reči vidljivih pre „Prikaži sve" (da ne razvuku stranicu). */
const COLLAPSED_LIMIT = 5;


// ==========          SVOJSTVA KLJUČNIH REČI          ==========

type FilmiumKeywordsBoxProps = {
  imdbKeywords: string[];
  userKeywords: string[];
  busy?: boolean;
  onAddKeyword: (keyword: string) => void;
  onRemoveUserKeyword: (keyword: string) => void;
};


// ==========          BOX KLJUČNIH REČI          ==========

/**
 * Prikazuje ključne reči: IMDB/TMDB (plavo, samo za čitanje) i korisničke
 * (zeleno, mogu se dodati Enter-om i uklanjati). Nova reč se potvrđuje Enter-om.
 */
function FilmiumKeywordsBox({
  imdbKeywords,
  userKeywords,
  busy = false,
  onAddKeyword,
  onRemoveUserKeyword,
}: FilmiumKeywordsBoxProps) {
  const [draft, setDraft] = useState("");
  const [expanded, setExpanded] = useState(false);

  const known = new Set(
    [...imdbKeywords, ...userKeywords].map((keyword) =>
      keyword.toLowerCase(),
    ),
  );

  // Objedinjena lista (IMDB pa korisničke); po defaultu skraćena na 5.
  const allChips = [
    ...imdbKeywords.map((keyword) => ({ keyword, kind: "imdb" as const })),
    ...userKeywords.map((keyword) => ({ keyword, kind: "user" as const })),
  ];
  const hiddenCount = Math.max(0, allChips.length - COLLAPSED_LIMIT);
  const visibleChips =
    expanded || hiddenCount === 0
      ? allChips
      : allChips.slice(0, COLLAPSED_LIMIT);

  /**
   * Potvrđuje unetu ključnu reč (Enter): dodaje ako nije prazna/duplikat.
   */
  function commitDraft(): void {
    const keyword = draft.trim();
    if (keyword === "" || known.has(keyword.toLowerCase())) {
      setDraft("");
      return;
    }
    onAddKeyword(keyword);
    setDraft("");
  }

  return (
    <div className="filmium-keywords-box">
      <p className="filmium-keywords-box-label">
        <Tag size={14} />
        Ključne reči
      </p>

      <div className="filmium-keywords-chips">
        {visibleChips.map(({ keyword, kind }) =>
          kind === "imdb" ? (
            <span
              className="filmium-keyword-chip imdb"
              key={`imdb:${keyword}`}
            >
              {keyword}
            </span>
          ) : (
            <span
              className="filmium-keyword-chip user"
              key={`user:${keyword}`}
            >
              {keyword}
              <button
                aria-label={`Ukloni ${keyword}`}
                className="filmium-keyword-chip-remove"
                disabled={busy}
                onClick={() => onRemoveUserKeyword(keyword)}
                type="button"
              >
                <X size={12} />
              </button>
            </span>
          ),
        )}

        {allChips.length === 0 && (
          <span className="filmium-keywords-empty">
            Još nema ključnih reči.
          </span>
        )}

        {hiddenCount > 0 && (
          <button
            className="filmium-keywords-toggle"
            onClick={() => setExpanded((value) => !value)}
            type="button"
          >
            {expanded ? (
              <>
                <ChevronUp size={13} />
                Prikaži manje
              </>
            ) : (
              <>
                <ChevronDown size={13} />
                Prikaži sve ({hiddenCount})
              </>
            )}
          </button>
        )}
      </div>

      <input
        aria-label="Dodaj ključnu reč"
        className="filmium-keywords-input"
        disabled={busy}
        onChange={(event) => setDraft(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            event.preventDefault();
            commitDraft();
          }
        }}
        placeholder="Dodaj svoju ključnu reč pa Enter..."
        type="text"
        value={draft}
      />
    </div>
  );
}

export default FilmiumKeywordsBox;
