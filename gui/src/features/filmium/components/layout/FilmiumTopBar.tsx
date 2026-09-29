import { useMemo, useState, type KeyboardEvent } from "react";
import {
  Bell,
  CornerDownLeft,
  Funnel,
  Home,
  Layers,
  Play,
  Plus,
  RefreshCw,
  Search,
  SlidersHorizontal,
  Square,
  Upload,
} from "lucide-react";

import type { MediaTypeFilter } from "../../../../types/filmium";
import { introAlreadyDone } from "../../hooks/introState";
import { useRevealAfter } from "../../hooks/useRevealAfter";
import "./filmium-command.css";


// ==========          PALJENJE          ==========

/** Search traka se spušta odozgo tek 3s po ulasku u FILMIUM. */
const SEARCH_REVEAL_MS = 3000;


// ==========          DOSTUPNE KOMANDE (SLASH)          ==========

type SlashCommand = {
  command: string;
  label: string;
  icon: "play" | "stop";
};

const SLASH_COMMANDS: SlashCommand[] = [
  {
    command: "/update-filmium",
    label: "Auto-update cele biblioteke (pozadinski)",
    icon: "play",
  },
  {
    command: "/update-filmium stop",
    label: "Zaustavi auto-update",
    icon: "stop",
  },
];


// ==========          SVOJSTVA GORNJE TRAKE          ==========

type FilmiumTopBarProps = {
  searchQuery: string;
  isRefreshing?: boolean;
  mediaTypeFilter: MediaTypeFilter;
  /** Broj naslova koje trenutni prikaz (kategorija + filteri) sadrži. */
  displayCount?: number;
  onHomeClick: () => void;
  onSearchChange: (value: string) => void;
  /** Presreće komande iz searcha (npr. „/update-filmium"). Vraća true ako je
   * unos obrađen kao komanda (pa se ne tretira kao pretraga). */
  onCommand?: (raw: string) => boolean;
  /** Nazivi postojećih kolekcija — za „#" preporuke. */
  collectionNames?: string[];
  /** Bira kolekciju iz „#" pretrage (primeni filter). */
  onSelectCollection?: (name: string) => void;
  onAddClick: () => void;
  onFilterClick: () => void;
  onRefreshClick?: () => void;
  onToggleMovie: () => void;
  onToggleSeries: () => void;
  onUploadClick: () => void;
  onSettingsClick: () => void;
};


// ==========          FILMIUM GORNJA TRAKA          ==========

/**
 * Prikazuje naslov, pretragu i brze FILMIUM akcije.
 */
function FilmiumTopBar({
  searchQuery,
  isRefreshing = false,
  mediaTypeFilter,
  displayCount,
  onHomeClick,
  onSearchChange,
  onCommand,
  collectionNames,
  onSelectCollection,
  onAddClick,
  onFilterClick,
  onRefreshClick,
  onToggleMovie,
  onToggleSeries,
  onUploadClick,
  onSettingsClick,
}: FilmiumTopBarProps) {
  const [activeIndex, setActiveIndex] = useState(0);

  // Paljenje: traka se spušta odozgo posle 3s — ali SAMO pri prvom pokretanju
  // aplikacije. Ako je intro već odigran u ovoj sesiji (ili ugašen u
  // Podešavanjima), traka je odmah tu (bez ponovnog spuštanja pri povratku na Home).
  const searchReady = useRevealAfter(introAlreadyDone() ? 0 : SEARCH_REVEAL_MS);

  // Režim: „/" komande, „#" kolekcije, inače obična pretraga.
  const paletteMode: "command" | "collection" | null =
    searchQuery.startsWith("/")
      ? "command"
      : searchQuery.startsWith("#")
        ? "collection"
        : null;

  type Suggestion = {
    key: string;
    completion: string; // šta CTRL+→ upiše
    primary: string; // glavni tekst
    label: string; // opis
    icon: "play" | "stop" | "collection";
    apply: () => boolean; // vrati true ako je obrađeno
  };

  const suggestions = useMemo<Suggestion[]>(() => {
    if (paletteMode === "command") {
      const query = searchQuery.trim().toLowerCase();
      return SLASH_COMMANDS.filter((entry) =>
        entry.command.startsWith(query),
      ).map((entry) => ({
        key: entry.command,
        completion: entry.command,
        primary: entry.command,
        label: entry.label,
        icon: entry.icon,
        apply: () => (onCommand ? onCommand(entry.command) : false),
      }));
    }
    if (paletteMode === "collection") {
      const query = searchQuery.slice(1).trim().toLowerCase();
      return (collectionNames ?? [])
        .filter((name) => query === "" || name.toLowerCase().includes(query))
        .slice(0, 8)
        .map((name) => ({
          key: name,
          completion: `#${name}`,
          primary: name,
          label: "Kolekcija",
          icon: "collection" as const,
          apply: () => {
            if (onSelectCollection) {
              onSelectCollection(name);
              return true;
            }
            return false;
          },
        }));
    }
    return [];
  }, [paletteMode, searchQuery, collectionNames, onCommand, onSelectCollection]);

  const safeIndex =
    suggestions.length > 0 ? activeIndex % suggestions.length : 0;
  const active = suggestions[safeIndex];
  // Fantomski nastavak — samo kad preporuka počinje ukucanim tekstom (prefiks).
  const ghostSuffix =
    active
    && active.completion.toLowerCase().startsWith(searchQuery.toLowerCase())
    && active.completion.length > searchQuery.length
      ? active.completion.slice(searchQuery.length)
      : "";

  function applyActive(): void {
    if (active && active.apply()) {
      onSearchChange("");
      setActiveIndex(0);
    }
  }

  function handleSearchKeyDown(
    event: KeyboardEvent<HTMLInputElement>,
  ): void {
    if (!paletteMode || suggestions.length === 0) {
      return;
    }

    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((index) => (index + 1) % suggestions.length);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex(
        (index) => (index - 1 + suggestions.length) % suggestions.length,
      );
    } else if (event.key === "ArrowRight" && event.ctrlKey) {
      // CTRL + → dopuni trenutno preporučenu stavku.
      event.preventDefault();
      if (active) {
        onSearchChange(active.completion);
      }
    } else if (event.key === "Enter") {
      event.preventDefault();
      applyActive();
    } else if (event.key === "Escape") {
      onSearchChange("");
      setActiveIndex(0);
    }
  }

  return (
    <header
      className={`filmium-top-bar filmium-intro-drop ${
        searchReady ? "is-in" : ""
      }`}
    >

      {/* ==========          LEVA GRUPA: HOME + FILM/SERIJE          ========== */}

      <div className="filmium-top-left">
        <button
          aria-label="Vrati se na FILMIUM Home"
          className="filmium-home-button"
          onClick={onHomeClick}
          title="FILMIUM Home"
          type="button"
        >
          <Home aria-hidden="true" size={20} />
        </button>

        <div className="filmium-type-toggles">
          <button
            aria-pressed={mediaTypeFilter === "movie"}
            className={`filmium-type-toggle ${
              mediaTypeFilter === "movie" ? "active" : ""
            }`}
            onClick={onToggleMovie}
            type="button"
          >
            FILM
          </button>

          <button
            aria-pressed={mediaTypeFilter === "series"}
            className={`filmium-type-toggle ${
              mediaTypeFilter === "series" ? "active" : ""
            }`}
            onClick={onToggleSeries}
            type="button"
          >
            SERIJE
          </button>
        </div>

        {typeof displayCount === "number" && (
          <span
            className="filmium-type-counter"
            title="Broj naslova u trenutnom prikazu"
          >
            {displayCount}
          </span>
        )}
      </div>


      <div className="filmium-command-wrap">
        <label className="filmium-top-search">
          <Search
            aria-hidden="true"
            size={18}
            strokeWidth={1.8}
          />

          <span className="filmium-input-stack">
            {ghostSuffix && (
              <span aria-hidden="true" className="filmium-ghost">
                <span className="filmium-ghost-typed">{searchQuery}</span>
                <span className="filmium-ghost-suffix">{ghostSuffix}</span>
              </span>
            )}
            <input
              aria-label="Pretraga FILMIUM kataloga"
              onChange={(event) => {
                onSearchChange(event.target.value);
                setActiveIndex(0);
              }}
              onKeyDown={handleSearchKeyDown}
              placeholder="Pretraži… / za komande, # za kolekcije"
              type="search"
              value={searchQuery}
            />
          </span>
        </label>

        {paletteMode && suggestions.length > 0 && (
          <ul className="filmium-command-menu" role="listbox">
            <li className="filmium-command-hint">
              {paletteMode === "collection"
                ? "CTRL + → dopuni · ↑↓ biraj · Enter prikaži kolekciju"
                : "CTRL + → dopuni · ↑↓ biraj · Enter pokreni"}
            </li>
            {suggestions.map((entry, index) => (
              <li key={entry.key}>
                <button
                  className={`filmium-command-item${
                    index === safeIndex ? " active" : ""
                  }`}
                  onClick={() => {
                    if (entry.apply()) {
                      onSearchChange("");
                      setActiveIndex(0);
                    }
                  }}
                  onMouseEnter={() => setActiveIndex(index)}
                  role="option"
                  aria-selected={index === safeIndex}
                  type="button"
                >
                  {entry.icon === "stop" ? (
                    <Square size={14} />
                  ) : entry.icon === "collection" ? (
                    <Layers size={14} />
                  ) : (
                    <Play size={14} />
                  )}
                  <span className="filmium-command-code">{entry.primary}</span>
                  <span className="filmium-command-label">{entry.label}</span>
                  {index === safeIndex && (
                    <CornerDownLeft
                      aria-hidden="true"
                      className="filmium-command-enter"
                      size={14}
                    />
                  )}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="filmium-top-actions">
        <button
          aria-label="Dodaj u listu za preuzeti"
          className="filmium-add-button"
          onClick={onAddClick}
          title="Dodaj novi film ili seriju u listu za preuzeti"
          type="button"
        >
          <Plus aria-hidden="true" size={22} strokeWidth={2.4} />
        </button>

        <button
          aria-label="Prikaži filtere"
          onClick={onFilterClick}
          title="Filteri"
          type="button"
        >
          <Funnel aria-hidden="true" size={18} />
        </button>

        <button
          aria-label="Osveži biblioteku"
          className={isRefreshing ? "is-refreshing" : undefined}
          disabled={isRefreshing}
          onClick={onRefreshClick}
          title="Osveži biblioteku (skenira nove slike, prevode i serije)"
          type="button"
        >
          <RefreshCw aria-hidden="true" size={18} />
        </button>

        <button
          aria-label="Dodaj novi sadržaj"
          onClick={onUploadClick}
          title="Uploads"
          type="button"
        >
          <Upload aria-hidden="true" size={18} />
        </button>

        <button
          aria-label="FILMIUM podešavanja"
          onClick={onSettingsClick}
          title="FILMIUM podešavanja"
          type="button"
        >
          <SlidersHorizontal aria-hidden="true" size={18} />
        </button>

        <button
          aria-label="Obaveštenja"
          className="notification-button"
          disabled
          title="Obaveštenja — uskoro"
          type="button"
        >
          <Bell aria-hidden="true" size={18} />
          <span aria-hidden="true" className="notification-dot" />
        </button>
      </div>
    </header>
  );
}

export default FilmiumTopBar;