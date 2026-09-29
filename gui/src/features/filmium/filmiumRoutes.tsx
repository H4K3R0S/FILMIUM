import type { ReactElement } from "react";
import { Navigate, Route } from "react-router";

// FILMIUM stilski barrel (catalog, home, layout/top-bar, intro, navigation…).
// Uvozi se eager ovde da svi FILMIUM stilovi uđu u bundle bez obzira na to
// koja se stranica prva otvori.
import "./styles/filmium.css";

// Uvozi FILMIUM stranica premešteni iz App.tsx — iste putanje, relativne
// na ovaj fajl (npr. "../../pages/FilmiumPage").
import FilmiumPage from "../../pages/FilmiumPage";
import FilmiumPlaceholderPage from "../../pages/FilmiumPlaceholderPage";
import { FilmiumWorkspaceProvider } from "./context/FilmiumWorkspace";
import FilmiumUploadsPage from "../../pages/FilmiumUploadsPage";
import FilmiumTorrentsPage from "../../pages/FilmiumTorrentsPage";

import FilmiumLibraryPage from "../../pages/FilmiumLibraryPage";
import FilmiumCollectionsPage from "../../pages/FilmiumCollectionsPage";
import FilmiumHistoryPage from "../../pages/FilmiumHistoryPage";

import FilmiumMediaDetailsPage from "../../pages/FilmiumMediaDetailsPage";
import FilmiumMediaEditorPage from "../../pages/FilmiumMediaEditorPage";
import FilmiumSharePage from "../../pages/FilmiumSharePage";
import FilmiumSettingsPage from "../../pages/FilmiumSettingsPage";
import FilmiumActorsPage from "../../pages/FilmiumActorsPage";
import FilmiumActorDetailPage from "../../pages/FilmiumActorDetailPage";

// ==========          FILMIUM RUTE          ==========

/**
 * Sve FILMIUM rute kao jedan `<Route>` element.
 *
 * Deli ih CORE (`App.tsx`) i FILMIUM ćelija (`cell/CellApp.tsx`), da isti
 * skup stranica ne postoji u dve kopije. Poziva se kao `{filmiumRoutes()}`.
 */
export function filmiumRoutes(): ReactElement {
  return (
    <Route
      path="/filmium"
      element={<FilmiumWorkspaceProvider />}
    >
      <Route
        index
        element={<FilmiumPage />}
      />

      <Route
        path="media/:itemId"
        element={<FilmiumMediaDetailsPage />}
      />

      <Route
        path="media/new"
        element={<FilmiumMediaEditorPage />}
      />

      <Route
        path="media/:itemId/edit"
        element={<FilmiumMediaEditorPage />}
      />

      <Route
        path="uploads"
        element={<FilmiumUploadsPage />}
      />

      <Route
        path="torrents"
        element={<FilmiumTorrentsPage />}
      />

      <Route
        path="library"
        element={<FilmiumLibraryPage view="all" />}
      />

      <Route
        path="strano"
        element={<FilmiumLibraryPage view="strano" />}
      />

      <Route
        path="domace"
        element={<FilmiumLibraryPage view="domace" />}
      />

      <Route
        path="animirano"
        element={<FilmiumLibraryPage view="animirano" />}
      />

      <Route
        path="favorites"
        element={<FilmiumLibraryPage view="favorites" />}
      />

      <Route
        path="collections"
        element={<FilmiumCollectionsPage />}
      />

      <Route
        path="actors"
        element={<FilmiumActorsPage />}
      />

      <Route
        path="actors/:slug"
        element={<FilmiumActorDetailPage />}
      />

      <Route
        path="history"
        element={<FilmiumHistoryPage />}
      />

      <Route path="share" element={<FilmiumSharePage />} />

      <Route
        path="recommended"
        element={
          <FilmiumPlaceholderPage
            description="Budući sistem personalizovanih preporuka."
            eyebrow="FILMIUM Discovery"
            title="Preporučeno"
          />
        }
      />

      <Route
        path="trending"
        element={
          <FilmiumPlaceholderPage
            description="Budući pregled trenutno popularnog sadržaja."
            eyebrow="FILMIUM Discovery"
            title="U trendu"
          />
        }
      />

      <Route
        path="top-rated"
        element={
          <FilmiumLibraryPage view="top-rated" />
        }
      />

      <Route
        path="upcoming"
        element={
          <FilmiumLibraryPage view="upcoming" />
        }
      />

      <Route
        path="settings"
        element={<FilmiumSettingsPage />}
      />

      <Route  
        path="*"
        element={<Navigate to="/filmium" replace />}
      />
    </Route>
  );
}
