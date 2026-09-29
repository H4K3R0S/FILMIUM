import { Pin, PinOff } from "lucide-react";
import { NavLink } from "react-router";

import { type CellNav } from "./cellNav";
import CellClock from "./CellClock";
import CellHealthIndicator from "./CellHealthIndicator";
import SystemHealthIndicator from "../components/system/SystemHealthIndicator";


// ==========          SVOJSTVA          ==========

type CellSidebarProps = {
  /** Domen-agnostičan opis navigacije (brend, prečice, sekcije). */
  nav: CellNav;
  version: string;
  isPinned: boolean;
  onTogglePinned: () => void;
  onPointerEnter: () => void;
  onPointerLeave: () => void;
};


// ==========          SIDEBAR ĆELIJE (generički)          ==========

/**
 * Sidebar samostalne ćelije. Isti okvir i klase kao CORE `Sidebar` (App.css),
 * ali brendiran po domenu iz `nav`: gornji rail nosi samo domenske prečice
 * (bez CORE Dashboard/Domains/Second Brain), srednji pojas je domenska
 * navigacija, a dno pokazuje vezu sa CORE-om — offline dok se ćelija ne spoji.
 * Nijedno domensko ime nije zakucano — sve stiže kroz `nav` (vidi `cellNav`).
 */
function CellSidebar({
  nav,
  version,
  isPinned,
  onTogglePinned,
  onPointerEnter,
  onPointerLeave,
}: CellSidebarProps) {
  return (
    <aside
      className="sidebar"
      onMouseEnter={onPointerEnter}
      onMouseLeave={onPointerLeave}
    >
      {/* ==========          DOMENSKI IDENTITET          ========== */}

      <div className="sidebar-header">
        <NavLink className="sidebar-brand" to={nav.homePath}>
          <strong>{nav.brand}</strong>
          <span>v{version}</span>
        </NavLink>

        <button
          aria-label={
            isPinned
              ? "Otkači sidebar (auto-skrivanje)"
              : "Zakači sidebar (uvek vidljiv)"
          }
          aria-pressed={isPinned}
          className={`sidebar-pin ${isPinned ? "pinned" : ""}`}
          data-tooltip={isPinned ? "Otkači" : "Zakači"}
          onClick={onTogglePinned}
          type="button"
        >
          {isPinned ? (
            <Pin aria-hidden="true" size={14} strokeWidth={2} />
          ) : (
            <PinOff aria-hidden="true" size={14} strokeWidth={2} />
          )}
        </button>
      </div>

      {/* Sat (sistemski alat): kompaktan sat + popover (alarm/tajmer/štoperica).
          CORE ga nosi u top-baru; ćelija ga nema, pa stoji u sidebaru. */}
      <div className="cell-sidebar-clock" style={{ padding: "0 12px 6px" }}>
        <CellClock />
      </div>

      {/* ==========          IKONSKI RED (samo domen)          ========== */}

      <div
        className="sidebar-icon-rail"
        role="group"
        aria-label={`${nav.brand} prečice`}
      >
        {nav.railItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              aria-label={item.label}
              className={({ isActive }) => `rail-icon ${isActive ? "active" : ""}`}
              data-tooltip={item.label}
              end={item.end}
              key={item.path}
              to={item.path}
            >
              <Icon aria-hidden="true" size={19} strokeWidth={1.8} />
            </NavLink>
          );
        })}
      </div>

      {/* Separator ispod ikonskog reda — stalno svetli (nema drop menija). */}
      <div className="glow-separator is-glowing" />

      {/* ==========          DOMENSKA NAVIGACIJA          ========== */}

      <nav className="sidebar-navigation" aria-label="Glavna navigacija">
        {nav.sections.map((section) => (
          <section className="navigation-section" key={section.label}>
            <p className="navigation-section-label">{section.label}</p>

            {section.items.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  className={({ isActive }) =>
                    `navigation-item ${isActive ? "active" : ""}`
                  }
                  end={item.path === nav.homePath}
                  key={item.id}
                  to={item.path}
                >
                  <Icon
                    aria-hidden="true"
                    className="navigation-icon"
                    size={19}
                    strokeWidth={1.8}
                  />
                  <span>{item.label}</span>
                </NavLink>
              );
            })}
          </section>
        ))}

        {/* Second Brain i Podešavanja su u gornjem ikonskom redu (railItems) — ne dole. */}
      </nav>

      {/* Separator iznad statusa — stalno svetli. */}
      <div className="glow-separator is-glowing" />

      {/* ==========          ZDRAVLJE ĆELIJE          ========== */}
      {/* Samostalna ćelija ne zavisi od CORE-a — footer pokazuje zdravlje
          sopstvenih podsistema (API/Ollama/RAG), ne „CORE Online/Offline". */}

      <div className="sidebar-footer">
        <CellHealthIndicator />
        <SystemHealthIndicator />
      </div>
    </aside>
  );
}

export default CellSidebar;
