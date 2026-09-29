# ========== IZVRŠIOCI INTENATA ==========
# Čist sloj: intent + params → poziv postojećeg FILMIUM servisa. Upisi
# (edit_metadata/save) menjaju SAMO dozvoljena polja i čuvaju ostatak zapisa.
from __future__ import annotations

from collections.abc import Callable
from dataclasses import fields, replace
from typing import Any

from core.domains.filmium.models import MediaItem, MediaItemCreate

# Polja MediaItem-a koja Kurator sme da menja (podskup; bez id/timestamp/sistem).
EDITABLE_FIELDS = frozenset({
    "title", "original_title", "english_title", "release_year", "runtime_minutes",
    "watch_status", "rating", "notes", "english_description", "content_category",
    "studio", "director", "collection", "is_favorite",
})

MediaRoute = "/filmium/media/{media_id}"

# Prikazi (liste) na koje Kurator sme da prebaci prozor — mapa naziv/sinonim -> ruta.
# Ključne reči na srpskom i engleskom; sve rute su realne GUI rute (filmiumRoutes.tsx).
VIEW_ROUTES: dict[str, str] = {
    "animirano": "/filmium/animirano", "animirani": "/filmium/animirano",
    "crtani": "/filmium/animirano", "anime": "/filmium/animirano",
    "strano": "/filmium/strano", "strani": "/filmium/strano", "inostrano": "/filmium/strano",
    "domace": "/filmium/domace", "domaće": "/filmium/domace", "domaci": "/filmium/domace",
    "library": "/filmium/library", "biblioteka": "/filmium/library", "sve": "/filmium/library",
    # „Preporučeno" i „U trendu" nemaju još pravu stranicu (placeholder) — vodi
    # na biblioteku (prava lista, uvek ima sadržaja) da Kurator ne šalje korisnika
    # na prazan ekran. (top-rated je prazan dok naslovi nemaju ocene.) Kad se
    # naprave prave stranice, vrati ih ovde.
    "recommended": "/filmium/library", "preporuceno": "/filmium/library",
    "preporučeno": "/filmium/library", "preporuke": "/filmium/library",
    "trending": "/filmium/library", "popularno": "/filmium/library", "u-trendu": "/filmium/library",
    "top-rated": "/filmium/top-rated", "najbolje": "/filmium/top-rated", "najbolje-ocenjeno": "/filmium/top-rated",
    "upcoming": "/filmium/upcoming", "uskoro": "/filmium/upcoming",
    "favorites": "/filmium/favorites", "omiljeno": "/filmium/favorites", "favoriti": "/filmium/favorites",
    "collections": "/filmium/collections", "kolekcije": "/filmium/collections",
    "history": "/filmium/history", "istorija": "/filmium/history", "gledano": "/filmium/history",
}

# Filteri koje navigate/recommend mogu da prosledе GUI-ju (naziv/sinonim -> kanon).
_MEDIA_TYPES = {
    "movie": "movie", "film": "movie", "filmovi": "movie", "films": "movie",
    "series": "series", "serija": "series", "serije": "series", "serial": "series", "tv": "series",
}
_SORTS = {
    "rating": "rating", "ocena": "rating", "ocene": "rating",
    "year": "year", "godina": "year", "godine": "year",
    "title": "title", "naslov": "title", "added": "added", "dodato": "added", "novo": "added",
}


def _build_filters(params: dict) -> dict:
    """Izgradi filter-mapu (media_type/genre/sort) iz params; prazna ako nema ničega."""
    filters: dict = {}
    mt = str(params.get("media_type", "")).strip().lower()
    if mt:
        filters["media_type"] = _MEDIA_TYPES.get(mt, mt)
    genre = str(params.get("genre", "")).strip()
    if genre:
        filters["genre"] = genre
    sort = str(params.get("sort", "")).strip().lower()
    if sort:
        filters["sort"] = _SORTS.get(sort, sort)
    return filters


class Executors:
    """Mapira nameru na postojeći servis."""

    def __init__(
        self,
        retriever: Any,
        repository: Any,
        launch_vlc: Callable[..., bool],
        resolve_video_path: Callable[[int], str | None],
        scan_library: Callable[[int | None], dict] | None = None,
        enrich_media: Callable[[int], dict] | None = None,
        wishlist_add: Callable[[str], dict] | None = None,
        wishlist_titles: Callable[[], list[str]] | None = None,
        tmdb_lookup: Callable[[str], dict | None] | None = None,
        recommender: Any = None,
    ) -> None:
        self._retriever = retriever
        self._repository = repository
        self._launch_vlc = launch_vlc
        self._resolve_video_path = resolve_video_path
        self._scan_library = scan_library
        self._enrich_media = enrich_media
        self._wishlist_add = wishlist_add
        self._wishlist_titles = wishlist_titles
        self._tmdb_lookup = tmdb_lookup
        self._recommender = recommender

    def info(self, params: dict) -> dict:
        """Info o naslovu: prvo iz baze; ako ga nema → TMDB (spoljni izvor)."""
        title = str(params.get("title", "")).strip()
        for m in self._repository.list_all():
            if (getattr(m, "title", "") or "").strip().lower() == title.lower():
                return {
                    "source": "library", "title": getattr(m, "title", title),
                    "year": getattr(m, "release_year", None),
                    "genres": list(getattr(m, "genres", ()) or ()),
                    "rating": getattr(m, "rating", None),
                    "overview": getattr(m, "english_description", None),
                }
        if self._tmdb_lookup is not None:
            data = self._tmdb_lookup(title)
            if data:
                return {"source": "tmdb", **data}
        return {"source": "none", "title": title}

    # ---------- wishlist (dodavanje željenog naslova uz proveru duplikata) ----------
    def _in_library(self, title: str) -> bool:
        t = title.strip().lower()
        try:
            return any((getattr(m, "title", "") or "").strip().lower() == t
                       for m in self._repository.list_all())
        except (AttributeError, TypeError):
            return False  # repo bez list_all (npr. minimalni) → tretiraj kao „nije u biblioteci"

    def _in_wishlist(self, title: str) -> bool:
        t = title.strip().lower()
        titles = self._wishlist_titles() if self._wishlist_titles else []
        return t in {(x or "").strip().lower() for x in titles}

    def _wishlist_preview(self, params: dict) -> dict:
        title = str(params.get("title", "")).strip()
        return {
            "action": "add_to_wishlist", "title": title,
            "in_library": self._in_library(title),
            "in_wishlist": self._in_wishlist(title),
        }

    def _wishlist_apply(self, params: dict) -> dict:
        title = str(params.get("title", "")).strip()
        if self._in_library(title) or self._in_wishlist(title):
            return {"added": False, "title": title, "reason": "already_present"}
        if self._wishlist_add is None:
            raise RuntimeError("Wishlist nije konfigurisan (wishlist_add servis nije uvezan).")
        result = self._wishlist_add(title)
        return {"added": True, "title": title, **(result if isinstance(result, dict) else {})}

    def scan_library(self, params: dict) -> dict:
        """AI skenira registrovanu biblioteku (dati root_id ili sve) za nove filmove/serije."""
        if self._scan_library is None:
            raise RuntimeError("Skeniranje nije konfigurisano (scan_library servis nije uvezan).")
        raw = params.get("root_id")
        root_id = int(raw) if raw not in (None, "") else None
        return {"kind": "scan", **self._scan_library(root_id)}

    def enrich(self, params: dict) -> dict:
        """AI povlači metapodatke sa TMDB + spoljnih provajdera (IMDb/RT/TVmaze/Jikan) za dati naslov."""
        if self._enrich_media is None:
            raise RuntimeError("Enrich nije konfigurisan (enrich_media servis nije uvezan).")
        media_id = int(params["media_id"])
        return {"kind": "enrich", **self._enrich_media(media_id)}

    def search(self, params: dict) -> dict:
        query = str(params.get("query", "")).strip()
        top_n = int(params.get("top_n", 10))
        items = self._retriever.retrieve(query, top_n=top_n)
        out: dict = {"titles": [m.get("title", "") for m in items]}
        # Top pogodak sa media_id → ruta ka stranici filma. Chat „nađi film X"
        # tako VIZUALNO otvara X (kao ručni klik), ne vraća samo listu naslova.
        for m in items:
            mid = m.get("media_id")
            if mid is not None:
                out["top"] = {
                    "media_id": int(mid),
                    "route": MediaRoute.format(media_id=int(mid)),
                }
                break
        return out

    def play(self, params: dict) -> dict:
        media_id = int(params["media_id"])
        return {
            "kind": "navigate",
            "media_id": media_id,
            "route": MediaRoute.format(media_id=media_id),
        }

    def navigate(self, params: dict) -> dict:
        """Prebaci prozor na prikaz + opcioni filteri (media_type/žanr/sort) koje GUI primeni."""
        view = str(params.get("view", "")).strip().lower()
        if view:
            route = VIEW_ROUTES.get(view)
            if not route:
                raise ValueError(f"Nepoznat prikaz: {view!r}")
        else:
            route = "/filmium/library"  # samo filteri, bez zadatog prikaza → cela biblioteka
        out = {"kind": "navigate", "route": route}
        filters = _build_filters(params)
        if filters:
            out["filters"] = filters
        return out

    def open_second_brain_map(self, params: dict) -> dict:
        """Otvori Second Brain MAPS mapu (podrazumevani pogled „Mapa" + sfere drugih sistema)."""
        return {"kind": "navigate", "route": "/second-brain?view=mapa"}

    def recommend(self, params: dict) -> dict:
        """Preporuka → kurirana lista (~20) naslova po UKUSU (favoriti/istorija) +
        AI izbor, prikazana kao baš ti naslovi na biblioteci (`?ids=...`). Bez
        recommendera / bez pogotka → cela biblioteka poređana po oceni (nikad
        placeholder /filmium/recommended ni prazan /filmium/top-rated)."""
        if self._recommender is not None:
            f = _build_filters(params)
            ids = self._recommender.recommend(
                genre=f.get("genre"), media_type=f.get("media_type"),
                mood=params.get("mood"), limit=20,
            )
            if ids:
                return {
                    "kind": "navigate", "route": "/filmium/library",
                    "filters": {"ids": ",".join(str(i) for i in ids)},
                    "count": len(ids),
                }
        filters = _build_filters(params)
        filters.setdefault("sort", "rating")  # fallback: cela biblioteka po oceni
        return {"kind": "navigate", "route": "/filmium/library", "filters": filters}

    def play_vlc(self, params: dict) -> dict:
        media_id = int(params["media_id"])
        path = self._resolve_video_path(media_id)
        if not path:
            raise LookupError(f"Nema video putanje za media_id={media_id}")
        return {"launched": bool(self._launch_vlc(path))}

    def _create_from(self, item: MediaItem) -> MediaItemCreate:
        names = {f.name for f in fields(MediaItemCreate)}
        values = {name: getattr(item, name) for name in names if hasattr(item, name)}
        return MediaItemCreate(**values)

    def preview_write(self, params: dict, intent: str = "edit_metadata") -> dict:
        if intent == "add_to_wishlist":
            return self._wishlist_preview(params)
        item = self._repository.get_by_id(int(params["media_id"]))
        if item is None:
            raise LookupError(f"Nema stavke media_id={params['media_id']}")
        changes = dict(params.get("changes", {}))
        self._check_fields(changes)
        return {"media_id": item.id, "title": item.title, "changes": changes}

    def apply_write(self, intent: str, params: dict) -> dict:
        if intent == "add_to_wishlist":
            return self._wishlist_apply(params)
        item = self._repository.get_by_id(int(params["media_id"]))
        if item is None:
            raise LookupError(f"Nema stavke media_id={params['media_id']}")
        changes = dict(params.get("changes", {}))
        self._check_fields(changes)
        create = replace(self._create_from(item), **changes)
        self._repository.update(item.id, create)
        return {"updated": True, "media_id": item.id}

    @staticmethod
    def _check_fields(changes: dict) -> None:
        nepoznata = set(changes) - EDITABLE_FIELDS
        if nepoznata:
            raise ValueError(f"Polja se ne smeju menjati: {sorted(nepoznata)}")
