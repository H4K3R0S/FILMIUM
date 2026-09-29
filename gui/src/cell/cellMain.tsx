import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { HashRouter } from "react-router";

import CellApp from "./CellApp";
import "../index.css";


// ==========          ĆELIJA — ULAZ (generički)          ==========

const rootElement = document.getElementById("root");

if (!rootElement) {
  throw new Error("Ćelija: root element nije pronađen.");
}

createRoot(rootElement).render(
  <StrictMode>
    <HashRouter>
      <CellApp />
    </HashRouter>
  </StrictMode>,
);
