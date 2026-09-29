import { useEffect, useState, type ReactNode } from "react";

import AmbientBackground from "../features/theme/AmbientBackground";
import TitleBar from "../components/layout/TitleBar";
import CellSidebar from "./CellSidebar";
import { useSidebarVisibility } from "../components/layout/useSidebarVisibility";
import { type CellNav } from "./cellNav";
import { getCellStatus } from "./cellApi";


// ==========          SVOJSTVA          ==========

type CellShellProps = {
  /** Domen-agnostičan opis navigacije. */
  nav: CellNav;
  /** Identifikator domena (za CSS klasu radnog prostora, npr. "kalima"). */
  domainId: string;
  children: ReactNode;
};


// ==========          OKVIR ĆELIJE (generički)          ==========

/**
 * Trajni raspored samostalne ćelije. Koristi iste App.css klase kao CORE
 * `AppShell` (isti izgled), ali bez CORE-only delova (TitleBar, boot/ignition,
 * screenshot, sistem widgeti) — ćelija ih ne nosi. Sidebar je `CellSidebar`
 * (brend iz `nav`). Verzija dolazi iz `/cell/status`; veza sa CORE-om je za
 * sada offline (spajanje sa CORE-om dolazi kasnije). Nijedno domensko ime nije
 * zakucano.
 */
function CellShell({ nav, domainId, children }: CellShellProps) {
  const { isPinned, isVisible, togglePinned, reveal, hide } =
    useSidebarVisibility();

  const [version, setVersion] = useState("0.1.0");

  // Verzija ćelije iz sopstvenog API-ja (ne CORE). Greška je bezopasna —
  // ostaje podrazumevana verzija.
  useEffect(() => {
    let active = true;

    void getCellStatus()
      .then((status) => {
        if (active) {
          setVersion(status.domain_version);
        }
      })
      .catch(() => {
        /* API još nije spreman — zadrži podrazumevanu verziju. */
      });

    return () => {
      active = false;
    };
  }, []);

  const layoutClassName = [
    "core-layout",
    isPinned ? "sidebar-pinned" : "sidebar-unpinned",
    isVisible ? "sidebar-visible" : "sidebar-collapsed",
    "boot-ready",
  ].join(" ");

  return (
    <div className={layoutClassName}>
      {/* Providni seamless titlebar (min/max/close) */}
      <TitleBar />
      {/* Ambient pozadina (dekorativna, ne hvata pokazivač) — iza svega. */}
      <AmbientBackground />

      {/* Zona uz levu ivicu koja otkriva sidebar kada nije zakačen. */}
      {!isPinned && (
        <div
          aria-hidden="true"
          className="sidebar-hotzone"
          onMouseEnter={reveal}
        />
      )}

      <CellSidebar
        nav={nav}
        isPinned={isPinned}
        onPointerEnter={reveal}
        onPointerLeave={hide}
        onTogglePinned={togglePinned}
        version={version}
      />

      <div className="workspace">
        <main className={`workspace-content ${domainId}-workspace-content`}>
          {children}
        </main>
        {nav.AgentDock ? <nav.AgentDock /> : null}
      </div>
    </div>
  );
}

export default CellShell;
