import { useEffect, useState } from "react";
import {
  AlertTriangle,
  Bell,
  CheckCircle2,
  ChevronRight,
  FolderOpen,
  Languages,
  RefreshCw,
  WifiOff,
  type LucideIcon,
} from "lucide-react";
import { Link } from "react-router";

import type {
  FilmiumLibraryRoot,
} from "../../../../types/filmiumLibrary";
import type {
  FilmiumLibraryStatisticsValue,
} from "./libraryStatistics";


type NotificationItem = {
  key: string;
  icon: LucideIcon;
  text: string;
  title: string;
  tone: string;
};


function Notification({
  icon: Icon,
  text,
  title,
  tone,
}: Omit<NotificationItem, "key">) {
  return (
    <article className={`filmium-library-notification tone-${tone}`}>
      <span className="filmium-library-notification-icon">
        <Icon size={17} />
      </span>
      <div>
        <strong>{title}</strong>
        <p>{text}</p>
      </div>
      <span className="filmium-library-notification-dot" />
    </article>
  );
}


/**
 * Prati da li je prozor toliko uzak da bi se okvir notifikacija
 * priljubio uz informacije o skeniranju (isti prelom kao raspored).
 */
function useCompactNotifications(): boolean {
  const query = "(max-width: 1180px)";
  const [isCompact, setIsCompact] = useState(() =>
    typeof window !== "undefined" &&
    window.matchMedia(query).matches,
  );

  useEffect(() => {
    const media = window.matchMedia(query);
    const handleChange = (): void => setIsCompact(media.matches);

    handleChange();
    media.addEventListener("change", handleChange);
    return () => media.removeEventListener("change", handleChange);
  }, []);

  return isCompact;
}


type FilmiumLibraryNotificationsProps = {
  onRefresh: () => void;
  roots: FilmiumLibraryRoot[];
  statistics: FilmiumLibraryStatisticsValue;
};


/**
 * Prikazuje izvedena obaveštenja o diskovima i poslednjem skeniranju.
 *
 * Na širokom rasporedu prikazuje pun okvir u bočnoj traci. Kada se
 * prozor suzi (isti prelom kao raspored), notifikacije se skupe u
 * ikonice u gornjem desnom uglu; klik na njih otvori panel koji
 * klizne s desne strane, a izlazak miša ga sklizne nazad.
 */
export default function FilmiumLibraryNotifications({
  onRefresh,
  roots,
  statistics,
}: FilmiumLibraryNotificationsProps) {
  const isCompact = useCompactNotifications();
  const [panelTrazen, setIsPanelOpen] = useState(false);

  const offlineRoots = roots.filter(
    (root) => root.last_scan_status === "offline",
  );

  const items: NotificationItem[] = [
    ...offlineRoots.map((root) => ({
      key: `offline:${root.id}`,
      icon: WifiOff,
      text: `${root.name} trenutno nije dostupan.`,
      title: "Disk ili folder nije povezan",
      tone: "yellow",
    })),
    ...(statistics.total > 0
      ? [{
          key: "total",
          icon: CheckCircle2,
          text: `${statistics.total} sadržaja u poslednjem skeniranju.`,
          title: "Skeniranje završeno",
          tone: "green",
        }]
      : []),
    ...(statistics.newContent > 0
      ? [{
          key: "new",
          icon: FolderOpen,
          text:
            `${statistics.newContent} novih stavki spremno je za pregled.`,
          title: "Otkriven je novi sadržaj",
          tone: "purple",
        }]
      : []),
    ...(statistics.attention > 0
      ? [{
          key: "attention",
          icon: AlertTriangle,
          text: `${statistics.attention} stavki traži ručnu proveru.`,
          title: "Potrebna pažnja",
          tone: "orange",
        }]
      : []),
    ...(statistics.subtitleRepairs > 0
      ? [{
          key: "subtitles",
          icon: Languages,
          text:
            `${statistics.subtitleRepairs} prevoda prosleđeno je na proveru.`,
          title: "Pronađeni problematični prevodi",
          tone: "blue",
        }]
      : []),
  ];

  const hasNotifications = items.length > 0;

  // Klizni panel postoji samo u uskom prozoru: u širokom se ne prikazuje, pa se
  // to IZVODI pri crtanju umesto da efekat gasi zastavicu.
  const isPanelOpen = isCompact && panelTrazen;

  const heading = (
    <div className="filmium-library-aside-heading">
      <h3>Notifikacije</h3>
      <button
        aria-label="Osveži lokacije"
        className="filmium-library-icon-button"
        onClick={onRefresh}
        type="button"
      >
        <RefreshCw size={16} />
      </button>
    </div>
  );

  const notificationList = hasNotifications ? (
    items.map((item) => (
      <Notification
        icon={item.icon}
        key={item.key}
        text={item.text}
        title={item.title}
        tone={item.tone}
      />
    ))
  ) : (
    <p className="filmium-library-aside-empty">
      Notifikacije će se pojaviti kada dodaš ili skeniraš lokaciju.
    </p>
  );

  const allNotificationsLink = hasNotifications && (
    <Link
      className="filmium-library-notifications-all"
      to="/filmium/history"
    >
      Prikaži sve notifikacije
      <ChevronRight size={15} />
    </Link>
  );

  if (!isCompact) {
    return (
      <aside className="filmium-library-notifications">
        {heading}
        {notificationList}
        {allNotificationsLink}
      </aside>
    );
  }

  // Uzak prozor: ikonice u gornjem desnom uglu + klizni panel.
  return (
    <div className="filmium-library-notifications-compact">
      <div className="filmium-library-notifications-cluster">
        <button
          aria-expanded={isPanelOpen}
          aria-label="Prikaži notifikacije"
          className="filmium-library-notifications-bell"
          onClick={() => setIsPanelOpen((open) => !open)}
          type="button"
        >
          <Bell size={18} />
          {hasNotifications && (
            <span className="filmium-library-notifications-badge">
              {items.length}
            </span>
          )}
        </button>
        {items.map((item) => (
          <button
            aria-label={item.title}
            className={
              `filmium-library-notifications-chip tone-${item.tone}`
            }
            key={item.key}
            onClick={() => setIsPanelOpen(true)}
            title={item.title}
            type="button"
          >
            <item.icon size={15} />
          </button>
        ))}
      </div>

      <aside
        className={
          `filmium-library-notifications filmium-library-notifications-panel${
            isPanelOpen ? " open" : ""
          }`
        }
        onMouseLeave={() => setIsPanelOpen(false)}
      >
        {heading}
        {notificationList}
        {allNotificationsLink}
      </aside>
    </div>
  );
}
