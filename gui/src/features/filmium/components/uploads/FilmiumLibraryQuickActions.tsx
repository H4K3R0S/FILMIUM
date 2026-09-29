import {
  Clapperboard,
  Film,
  LoaderCircle,
  ScanSearch,
  Share2,
} from "lucide-react";


type FilmiumLibraryQuickActionsProps = {
  isBusy: boolean;
  onScanBoth: () => void;
  onScanMovies: () => void;
  onScanSeries: () => void;
  onShare: () => void;
};


/**
 * Prikazuje glavne ulazne akcije FILMIUM Uploads stranice.
 */
export default function FilmiumLibraryQuickActions({
  isBusy,
  onScanBoth,
  onScanMovies,
  onScanSeries,
  onShare,
}: FilmiumLibraryQuickActionsProps) {
  return (
    <div className="filmium-library-quick-actions">
      <button
        className="filmium-library-action"
        disabled={isBusy}
        onClick={onScanMovies}
        type="button"
      >
        <span className="filmium-library-action-icon">
          <Film size={22} />
        </span>
        <span className="filmium-library-action-copy">
          <strong>+ FILM</strong>
        </span>
      </button>
      <button
        className="filmium-library-action"
        disabled={isBusy}
        onClick={onScanSeries}
        type="button"
      >
        <span className="filmium-library-action-icon">
          <Clapperboard size={22} />
        </span>
        <span className="filmium-library-action-copy">
          <strong>+ SERIJE</strong>
        </span>
      </button>
      <button
        className="filmium-library-action primary"
        disabled={isBusy}
        onClick={onScanBoth}
        type="button"
      >
        <span className="filmium-library-action-icon">
          {isBusy
            ? <LoaderCircle className="spinning" size={22} />
            : <ScanSearch size={22} />}
        </span>
        <span className="filmium-library-action-copy">
          <strong>Skeniraj DIR</strong>
        </span>
      </button>
      <button
        className="filmium-library-action"
        onClick={onShare}
        type="button"
      >
        <span className="filmium-library-action-icon">
          <Share2 size={22} />
        </span>
        <span className="filmium-library-action-copy">
          <strong>Podeli</strong>
        </span>
      </button>
    </div>
  );
}
