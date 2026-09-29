import {
  useCallback,
  useEffect,
  useState,
  type ReactNode,
} from "react";

import {
  Outlet,
  useLocation,
  useNavigate,
} from "react-router";

import { INTRO_SESSION_KEY, markIntroDone } from "../hooks/introState";

import {
  getFilmiumAssetUrl,
  getFilmiumGenres,
} from "../../../services/filmiumApi";
import { refreshFilmiumLibrary } from "../../../services/filmiumSeriesApi";
import { CheckCircle2 } from "lucide-react";

import FilmiumTopBar from "../components/layout/FilmiumTopBar";
import FilmiumAcquireModal from "../components/uploads/FilmiumAcquireModal";
import FilmiumTorrentDropZone from "../components/torrents/FilmiumTorrentDropZone";
import {
  startFilmiumCron,
  stopFilmiumCron,
} from "../../../services/filmiumCronApi";
import { useFilmiumCatalog } from "../hooks/useFilmiumCatalog";
import { useFilmiumCollections } from "../hooks/useFilmiumCollections";
import { useFilmiumFilters } from "../hooks/useFilmiumFilters";
import { useFilmiumWishlist } from "../hooks/useFilmiumWishlist";
import { useCoreSetting } from "../../../lib/useCoreSetting";
import { FilmiumWorkspaceContext } from "./filmiumWorkspaceContext";


// ==========          WORKSPACE MODEL          ==========

/**
 * Jedna stavka poslednjeg skeniranja (Uploads → Film/Serija/Skeniraj folder).
 * Deli se sa „Podeli" ekranom kao podrazumevana lista za prenos.
 */
export type ShareScanEntry = {
  id: string;
  title: string;
  subtitle: string | null;
  mediaType: "movie" | "series";
  directory: string;
};

export type FilmiumWorkspaceContextValue = {
  catalog: ReturnType<typeof useFilmiumCatalog>;
  collections: ReturnType<typeof useFilmiumCollections>;
  filters: ReturnType<typeof useFilmiumFilters>;
  /** Lista naslova „za preuzeti" (Home red + brisanje). */
  wishlist: ReturnType<typeof useFilmiumWishlist>;
  filtersVisible: boolean;
  toggleFilters: () => void;
  allGenres: string[];
  setWorkspaceBackdropPath: (
    relativePath: string | null,
  ) => void;
  /** Rezultati poslednjeg skeniranja (za „Podeli"). */
  lastScan: ShareScanEntry[];
  setLastScan: (entries: ShareScanEntry[]) => void;
  /**
   * Da li je intro („paljenje") animacija već odigrana u ovom ulasku u domen.
   * Živi na nivou workspace-a (van remount-a stranice), pa se animacija ne
   * ponavlja na Home klik / prelazak pod-ruta; resetuje se izlaskom iz domena.
   *
   * Stanje, a ne ref: stranica ovo čita pri crtanju da bi znala da li da
   * animira, a ref se pri crtanju ne sme čitati.
   */
  introPlayed: boolean;
  /** Beleži da je animacija odigrana; zove je stranica kada je pokrene. */
  markIntroPlayed: () => void;
};

type FilmiumWorkspaceProviderProps = {
  children?: ReactNode;
};


// ==========          WORKSPACE CONTEXT          ==========



// ==========          WORKSPACE PROVIDER          ==========

/**
 * Čuva zajedničko FILMIUM stanje tokom navigacije između ekrana.
 *
 * Katalog, kolekcije i filteri ne učitavaju se ponovo pri svakom
 * prelasku sa Home ekrana na druge FILMIUM pod-rute.
 */
export function FilmiumWorkspaceProvider({
  children,
}: FilmiumWorkspaceProviderProps) {
  const location = useLocation();
  const navigate = useNavigate();

  const [
    workspaceBackdropPath,
    setWorkspaceBackdropPath,
  ] = useState<string | null>(null);

  const collections = useFilmiumCollections();

  const catalog = useFilmiumCatalog({
    onMediaDeleted: collections.removeMediaReferences,
  });

  const filters = useFilmiumFilters(catalog.items);

  const wishlist = useFilmiumWishlist();

  // Filteri (žanrovi + ostale opcije) su skriveni dok se ne klikne na ikonicu.
  const [filtersVisible, setFiltersVisible] = useState(false);

  // Prozor „Dodaj za preuzeti" (veliki „+" u gornjoj traci).
  const [acquireOpen, setAcquireOpen] = useState(false);

  // Toast „uklonjeno iz liste za preuzeti" — sam nestane posle par sekundi.
  // Polja se izdvajaju iz `wishlist` pre efekta: efekat zavisi baš od njih, a
  // ne od celog objekta koji se menja i kad se promeni nešto sasvim drugo.
  const { removedNotice, clearRemovedNotice } = wishlist;
  useEffect(() => {
    if (removedNotice.length === 0) {
      return;
    }
    const timer = window.setTimeout(() => {
      clearRemovedNotice();
    }, 6000);
    return () => window.clearTimeout(timer);
  }, [removedNotice, clearRemovedNotice]);

  // Poslednje skeniranje iz Uploads-a — deli se sa „Podeli" ekranom.
  const [lastScan, setLastScan] = useState<ShareScanEntry[]>([]);

  // Svi kanonski žanrovi iz registra (za polje sa žanrovima).
  const [allGenres, setAllGenres] = useState<string[]>([]);
  useEffect(() => {
    let active = true;
    getFilmiumGenres()
      .then((list) => active && setAllGenres(list))
      .catch(() => {
        /* tolerantno */
      });
    return () => {
      active = false;
    };
  }, []);

  const workspaceBackdropUrl = getFilmiumAssetUrl(
    workspaceBackdropPath,
  );

  // Intro („paljenje") se pušta SAMO JEDNOM PO POKRETANJU APLIKACIJE. Ranije je
  // stanje živelo samo u ovom provideru, pa se pri odlasku na Second Brain
  // (van providera) i povratku na Home animacija ponavljala. Sada se „odigrano"
  // čuva u sessionStorage (preživi navigaciju/remount, resetuje se pri novom
  // pokretanju aplikacije). Opcija `core.filmium.introAnimation` (Podešavanja →
  // Prikaz) može da ugasi animaciju u potpunosti.
  const [introEnabled] = useCoreSetting("core.filmium.introAnimation", true);
  const [introPlayed, setIntroPlayed] = useState(() => {
    if (!introEnabled) return true;
    try { return window.sessionStorage.getItem(INTRO_SESSION_KEY) === "1"; } catch { return false; }
  });
  const markIntroPlayed = useCallback(() => {
    setIntroPlayed(true);
    markIntroDone();
  }, []);

  // Naslov programa (.section-heading) je skriven po defaultu; prekidač u
  // CORE Settings ga pali. Atribut kontroliše CSS (skrivanje + sticky).
  const [showPageTitle] = useCoreSetting(
    "core.filmium.showPageTitle",
    false,
  );

  // ==========          WORKSPACE NAVIGACIJA          ==========

  /**
   * Vraća korisnika na početni FILMIUM ekran.
   *
   * Filteri se resetuju kako Home ne bi nasledio zaključan tip iz
   * Serije/Filmovi (npr. prikaz samo serija na početnoj strani).
   */
  function handleHomeClick(): void {
    filters.clearFilters();
    setFiltersVisible(false);
    navigate("/filmium");
  }

  /**
   * Presreće komande iz glavnog searcha. „/update-filmium" pokreće bulk
   * auto-update; „/update-filmium stop" ga zaustavlja. Vraća true ako je
   * unos obrađen kao komanda.
   */
  function handleCommand(raw: string): boolean {
    const command = raw.trim().toLowerCase();
    if (command === "/update-filmium") {
      void startFilmiumCron();
      return true;
    }
    if (command === "/update-filmium stop") {
      void stopFilmiumCron();
      return true;
    }
    return false;
  }

  /**
   * Primenjuje filter po kolekciji (iz „#" pretrage) i otvara biblioteku
   * da se odmah vide samo filmovi/serije iz te kolekcije.
   */
  function handleSelectCollection(name: string): void {
    const target = (collections.collections ?? []).find(
      (entry) => entry.name === name,
    );
    if (!target) {
      return;
    }
    filters.setCollectionFilter(name, target.item_ids);
    filters.setSearchQuery("");
    if (location.pathname !== "/filmium/library") {
      navigate("/filmium/library");
    }
  }

  /**
   * Ažurira pretragu i po potrebi otvara katalog.
   */
  function handleSearchChange(value: string): void {
    filters.setSearchQuery(value);

    const isLibraryRoute = [
      "/filmium/library",
      "/filmium/movies",
      "/filmium/series",
      "/filmium/favorites",
      "/filmium/top-rated",
      "/filmium/upcoming",
    ].includes(location.pathname);

    if (value.trim() !== "" && !isLibraryRoute) {
      navigate("/filmium/library");
    }
  }

  /**
   * Prikazuje/sakriva filtere (žanrovi + ostale opcije) na tekućoj stranici.
   */
  function handleFilterClick(): void {
    setFiltersVisible((visible) => !visible);
  }

  /**
   * Otvara prozor „Dodaj za preuzeti" (veliki „+").
   */
  function handleAddClick(): void {
    setAcquireOpen(true);
  }

  /**
   * Uključuje/isključuje prikaz samo filmova (isključivo sa serijama).
   */
  function handleToggleMovie(): void {
    filters.setMediaTypeFilter(
      filters.mediaTypeFilter === "movie" ? "all" : "movie",
    );
  }

  /**
   * Uključuje/isključuje prikaz samo serija (isključivo sa filmovima).
   */
  function handleToggleSeries(): void {
    filters.setMediaTypeFilter(
      filters.mediaTypeFilter === "series" ? "all" : "series",
    );
  }

  // Osvežavanje biblioteke: skenira registrovane lokacije i dopuni bazu.
  const [isRefreshing, setIsRefreshing] = useState(false);

  /**
   * Skenira sve biblioteke i dopunjava bazu (slike, epizode, nove serije).
   */
  async function handleRefreshLibrary(): Promise<void> {
    if (isRefreshing) {
      return;
    }

    setIsRefreshing(true);

    try {
      const summary = await refreshFilmiumLibrary();
      await catalog.refreshCatalog();

      // Pokreni pozadinski bulk auto-update: dopunjava naslove kojima nedostaju
      // podaci (uklj. TMDB ID) da bi lista „za preuzeti" mogla da ih prepozna.
      // Best-effort — ne prekida osvežavanje ako posao ne krene.
      try {
        await startFilmiumCron();
      } catch {
        /* pozadinski posao je pomoćni */
      }

      // Uskladi listu „za preuzeti" sa novim stanjem biblioteke.
      void wishlist.reconcile();

      const added =
        summary.posters_added
        + summary.backdrops_added
        + summary.season_posters_added
        + summary.season_backdrops_added;

      window.alert(
        "FILMIUM osvežavanje završeno:\n"
        + `• Serija skenirano: ${summary.scanned_series}\n`
        + `• Novih serija: ${summary.new_series}\n`
        + `• Uklonjeno (nema na disku): ${summary.removed_series}\n`
        + `• Novih sezona/epizoda: ${summary.seasons_added}`
        + `/${summary.episodes_added}\n`
        + `• Slika dodato: ${added}\n`
        + `• Foldera filmova skenirano: ${summary.movie_folders_scanned}\n`
        + `• Izvora filmova registrovano: ${summary.movie_sources_added}\n`
        + `• JSON manifesta upisano: ${summary.manifests_written}`,
      );
    } catch {
      window.alert(
        "Osvežavanje biblioteke nije uspelo. Proveri da li je "
        + "API dostupan.",
      );
    } finally {
      setIsRefreshing(false);
    }
  }

  /**
   * Otvara praznu formu za dodavanje novog sadržaja.
   */
  function handleUploadClick(): void {
    catalog.cancelMediaEdit();
    navigate("/filmium/uploads");
  }

  /**
   * Otvara podešavanja FILMIUM domena.
   */
  function handleSettingsClick(): void {
    navigate("/filmium/settings");
  }

  return (
    <FilmiumWorkspaceContext.Provider
      value={{
        catalog,
        collections,
        filters,
        wishlist,
        filtersVisible,
        toggleFilters: handleFilterClick,
        allGenres,
        setWorkspaceBackdropPath,
        lastScan,
        setLastScan,
        introPlayed,
        markIntroPlayed,
      }}
    >
      <div
        className="filmium-domain-workspace"
        data-page-title={showPageTitle ? "on" : "off"}
      >
        {/* ==========          GLOBALNI BACKDROP          ========== */}

        {workspaceBackdropUrl && (
          <div
            aria-hidden="true"
            className="filmium-domain-background"
          >
            <div
              className="filmium-domain-background-image"
              style={{
                backgroundImage:
                  `url("${workspaceBackdropUrl}")`,
              }}
            />

            <div className="filmium-domain-background-shade" />
          </div>
        )}

        {/* ==========          FILMIUM SADRŽAJ          ========== */}

        <div className="filmium-domain-content">
          <FilmiumTopBar
            isRefreshing={isRefreshing}
            mediaTypeFilter={filters.mediaTypeFilter}
            displayCount={filters.filteredItems.length}
            searchQuery={filters.searchQuery}
            onFilterClick={handleFilterClick}
            onHomeClick={handleHomeClick}
            onRefreshClick={handleRefreshLibrary}
            onSearchChange={handleSearchChange}
            onCommand={handleCommand}
            onSelectCollection={handleSelectCollection}
            collectionNames={(collections.collections ?? []).map(
              (entry) => entry.name,
            )}
            onAddClick={handleAddClick}
            onSettingsClick={handleSettingsClick}
            onToggleMovie={handleToggleMovie}
            onToggleSeries={handleToggleSeries}
            onUploadClick={handleUploadClick}
          />

          {/* ==========          PROGRES OSVEŽAVANJA          ========== */}

          {isRefreshing && (
            <div
              aria-label="Osvežavanje biblioteke u toku"
              className="filmium-refresh-progress"
              role="progressbar"
            >
              <div className="filmium-refresh-progress-track">
                <div className="filmium-refresh-progress-bar" />
              </div>

              <span className="filmium-refresh-progress-label">
                Osvežavam biblioteku — skeniram nove slike, prevode i
                serije...
              </span>
            </div>
          )}

          {/* ==========          FILMIUM ROUTE SADRŽAJ          ========== */}

          <div
            className="filmium-route-stage"
            key={location.pathname}
          >
            {children ?? <Outlet />}
          </div>
        </div>

        <FilmiumAcquireModal
          open={acquireOpen}
          onAdded={() => {
            void wishlist.refresh();
          }}
          onClose={() => setAcquireOpen(false)}
        />

        {wishlist.removedNotice.length > 0 && (
          <div
            aria-live="polite"
            className="filmium-wishlist-toast"
            role="status"
          >
            <div className="filmium-wishlist-toast-title">
              <CheckCircle2 aria-hidden="true" size={16} />
              Uklonjeno iz liste za preuzeti — sada je u biblioteci
            </div>
            <ul>
              {wishlist.removedNotice.map((entry) => (
                <li key={entry.id}>{entry.title}</li>
              ))}
            </ul>
          </div>
        )}

        {/* ==========          PREVLAČENJE TORRENTA          ========== */}
        {/* Ceo FILMIUM prima .torrent fajlove prevlačenjem; sve ostalo se
            odbija sa porukom. */}
        <FilmiumTorrentDropZone />

        {/* Kurator sada dolazi kroz globalni dock (shell slot, dole-centar) —
            ne montira se ovde. Videti `FilmiumKuratorDock` u `filmiumNav`. */}
      </div>
    </FilmiumWorkspaceContext.Provider>
  );
}
