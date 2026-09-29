import { Fragment, useEffect, type ReactNode } from "react";
import { Navigate, Route, Routes, useNavigate } from "react-router";

import AmbientBackground from "../features/theme/AmbientBackground";
import CellSecondBrain from "./CellSecondBrain";
import CellShell from "./CellShell";
import { cellNav, cellRoutes, CELL_DOMAIN } from "./cellDomain";
import { serializeCellNav } from "./cellNav";
import { VremeProvider } from "../features/vreme/context/VremeProvider";
import "../App.css";


// Ambient pozadina je u ćeliji uključena po defaultu (CORE je opt-in). Seed ide
// PRE prvog renderovanja (na uvoz modula) da ga `useAmbientSettings` uhvati već
// pri prvom čitanju; korisnik ga kasnije može ugasiti kad Settings prekidač dođe.
try {
  if (window.localStorage.getItem("core.theme.ambient.all") === null) {
    window.localStorage.setItem("core.theme.ambient.all", "true");
  }
} catch {
  /* storage nedostupan — ambient ostaje na svom defaultu */
}


// ==========          APLIKACIJA ĆELIJE (generička)          ==========
// Rute aktivnog domena u okviru ćelije. Domen i njegove rute/navigacija stižu
// iz `cellDomain` (koji `build_cell` regeneriše po domenu). Bez CORE domena i
// bez ijednog zakucanog domenskog imena.
//
// Dva moda:
//  - standalone (podrazumevan): pun `CellShell` (sopstveni sidebar) — Tauri exe;
//  - chromeless (`?chrome=off`): samo domenski sadržaj, bez ćelijskog shell-a —
//    za embed u CORE, koji obezbeđuje svoj sidebar. Chromeless ćelija šalje svoj
//    nav parentu (CORE) i sluša CORE navigaciju.

function isChromeless(): boolean {
  try {
    return new URLSearchParams(window.location.search).get("chrome") === "off";
  } catch {
    return false;
  }
}


/**
 * Domenski sadržaj bez ćelijskog shell-a — za embed u CORE. Po montiranju šalje
 * serijalizovan nav parentu i sluša `cell-navigate` da vodi ruter bez reload-a.
 */
function ChromelessContent() {
  const navigate = useNavigate();

  useEffect(() => {
    // Nav CORE-u (parent). Origin proverava CORE strana pre prihvatanja.
    window.parent?.postMessage({ type: "cell-nav", nav: serializeCellNav(cellNav) }, "*");

    function onMessage(event: MessageEvent) {
      const data = event.data as { type?: string; path?: string } | null;
      if (data && data.type === "cell-navigate" && typeof data.path === "string") {
        navigate(data.path);
      }
    }

    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [navigate]);

  return (
    <>
      <AmbientBackground />
      <main className={`workspace-content cell-chromeless ${CELL_DOMAIN}-workspace-content`}>
        <Routes>
          {cellRoutes()}
          <Route path="/second-brain" element={<CellSecondBrain />} />
          <Route path="*" element={<Navigate replace to={cellNav.homePath} />} />
        </Routes>
      </main>
      {cellNav.AgentDock ? <cellNav.AgentDock /> : null}
    </>
  );
}


function CellApp() {
  const Wrapper: React.ComponentType<{ children: ReactNode }> =
    cellNav.Wrapper ?? Fragment;

  // Tema domena: `data-domain` na <html> aktivira `[data-domain="..."]` boje iz
  // CORE `themes/core.css` PREKO CORE `:root` osnove — CORE stil kao osnovna
  // tema, domenska iznad (kao u CORE App-u). Ambient i akcenti prate domen.
  useEffect(() => {
    document.documentElement.setAttribute("data-domain", CELL_DOMAIN);
    return () => document.documentElement.removeAttribute("data-domain");
  }, []);

  // `VremeProvider` obavija ceo shell (sat/alarm/tajmer/štoperica su sistemski
  // alat ćelije; `HeaderClock` u sidebaru ga koristi).
  const inner = isChromeless() ? (
    <Wrapper>
      <ChromelessContent />
    </Wrapper>
  ) : (
    <Wrapper>
      <CellShell nav={cellNav} domainId={CELL_DOMAIN}>
        <Routes>
          {cellRoutes()}
          <Route path="/second-brain" element={<CellSecondBrain />} />
          <Route path="*" element={<Navigate replace to={cellNav.homePath} />} />
        </Routes>
      </CellShell>
    </Wrapper>
  );

  return <VremeProvider>{inner}</VremeProvider>;
}

export default CellApp;
