#!/usr/bin/env python3
"""FILMIUM Atom Factory — JEDINI izvor istine za sve atome ćelije.

SR: Jedan napredni alat koji pravi SVE FILMIUM atome (film/serija, lična
    kolekcija, TMDB franšiza, alat, veština, problem-detalj). Job, upload i
    skripte pozivaju OVDE umesto da kopiraju proces. Svaki atom kroz `write_atom`
    dobija `atom_kreiran` (očuvano pri regeneraciji) i `atom_azuriran`.

    Media atom (kompaktan): status/tip videa, teritorijalni status (domaće/strano),
    kategorija (film/serija/animirano/ANIME), jezik (audio), prevod (glavni titl),
    glavni akteri (baza ili NN), VAŽNA INFO (beleške/scan), problem-status u par
    reči (npr. „fali prevod") sa [[linkom]] ka detaljnom problem-atomu, bidirekcione
    veze glumac↔film, prevodi po sezonama. Slug = slugify('Naslov Godina').
EN: Single source of truth for all FILMIUM atoms; timestamped via write_atom.
"""
from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
from datetime import datetime
from pathlib import Path

# ==========================================================================
#  Osnovni helper-i
# ==========================================================================

def now_iso() -> str:
    """Lokalno vreme, ISO-8601, bez mikrosekundi (npr. 2026-09-19T07:41:12+02:00)."""
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def slugify(text: object) -> str:
    norm = unicodedata.normalize("NFKD", str(text))
    norm = "".join(c for c in norm if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", norm.lower()).strip("-")[:80] or "atom"


def media_slug(title: object, year: object) -> str:
    return slugify(f"{title} {year}" if year else title)


def filmium_base_url() -> str:
    """Bazni URL FILMIUM aplikacije (port iz cell.json ćelije; rezervno 4801).
    Koristi se za klikabilne linkove iz atoma ka stranici filma/glumca."""
    port = 4801
    try:
        cell = Path(__file__).resolve().parents[3] / "cell.json"
        port = int(json.loads(cell.read_text(encoding="utf-8")).get("port") or port)
    except Exception:  # noqa: BLE001, S110
        pass
    return f"http://127.0.0.1:{port}"


def media_page_url(media_id: object) -> str:
    return f"{filmium_base_url()}/#/filmium/media/{media_id}"


def actor_page_url(slug: str) -> str:
    return f"{filmium_base_url()}/#/filmium/actors/{slug}"


def y(v: object) -> str:
    """YAML-bezbedan skalar (citira po potrebi)."""
    s = "" if v is None else str(v)
    if s == "":
        return '""'
    if re.search(r'[:#\[\]{}",\'\n]|^\s|\s$', s):
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return s


def jarr(raw: object) -> list:
    if not raw:
        return []
    try:
        v = json.loads(raw)
        return v if isinstance(v, list) else []
    except Exception:  # noqa: BLE001
        return [x.strip() for x in str(raw).split(",") if x.strip()]


LANG_LABEL = {
    "sr": "srpski", "sr-latn": "srpski", "srp": "srpski", "hr": "hrvatski",
    "bs": "bosanski", "en": "engleski", "eng": "engleski", "und": "nepoznat",
}


def lang_label(code: object) -> str | None:
    if not code:
        return None
    return LANG_LABEL.get(str(code).lower(), str(code))


# ==========================================================================
#  DB upiti (rade sa prosleđenim `con`, row_factory=sqlite3.Row)
# ==========================================================================

def subtitles_for(con: sqlite3.Connection, media_id: int) -> list[str]:
    rows = con.execute(
        "SELECT DISTINCT f.language FROM filmium_media_files f "
        "JOIN filmium_media_sources s ON s.id=f.source_id "
        "WHERE s.media_id=? AND f.role='subtitle' AND f.language IS NOT NULL AND f.language!=''",
        (media_id,)).fetchall()
    labs: list[str] = []
    for r in rows:
        lab = lang_label(r[0])
        if lab and lab not in labs:
            labs.append(lab)
    return labs


def cast_for(con: sqlite3.Connection, media_id: int) -> tuple[list, list]:
    rows = con.execute(
        "SELECT p.slug, p.name, mp.role, mp.sort_order FROM filmium_media_people mp "
        "JOIN filmium_people p ON p.id=mp.person_id WHERE mp.media_id=? "
        "ORDER BY (mp.role='reditelj') DESC, COALESCE(mp.sort_order,999)", (media_id,)).fetchall()
    directors = [(r["slug"], r["name"]) for r in rows if r["role"] == "reditelj"]
    actors = [(r["slug"], r["name"]) for r in rows if r["role"] == "glumac"]
    return directors, actors


def seasons_for(con: sqlite3.Connection, media_id: int) -> list[dict]:
    try:
        rows = con.execute(
            "SELECT s.season_number, COUNT(e.id) AS eps FROM filmium_seasons s "
            "LEFT JOIN filmium_episodes e ON e.season_id=s.id "
            "WHERE s.media_id=? GROUP BY s.id ORDER BY s.season_number", (media_id,)).fetchall()
        return [{"n": r["season_number"], "eps": r["eps"]} for r in rows]
    except sqlite3.Error:
        return []


def repair_issues(con: sqlite3.Connection, media_id: int) -> int:
    try:
        row = con.execute(
            "SELECT COUNT(*) FROM filmium_subtitle_repair_queue WHERE media_id=? AND issue_count>0",
            (media_id,)).fetchone()
        return int(row[0]) if row else 0
    except sqlite3.Error:
        return 0


# ==========================================================================
#  PROBLEM-detalj atomi (svaki problem u par reči linkuje ka OVOME)
# ==========================================================================

# ključ = slug problema; vrednost = (naziv, kratko, kako se rešava)
PROBLEM_DEFS: dict[str, tuple[str, str, str]] = {
    "fali-prevod": (
        "Fali prevod",
        "Za naslov ne postoji nijedan titl u biblioteci (nema `subtitle` fajla).",
        "Pronaći/generisati srpski titl (Prevodilac alat ili spoljni izvor) i uvesti ga uz izvor naslova.",
    ),
    "losi-titlovi": (
        "Loši titlovi",
        ("Titl postoji ali je u redu za popravku (`filmium_subtitle_repair_queue`, issue_count>0): "
        "loš encoding, pogrešan jezik ili oštećenja."),
        "Otvoriti red za popravku titlova, ispraviti encoding/jezik i potvrditi (reviewed).",
    ),
    "bez-glumaca": (
        "Bez glumaca",
        "Naslov nema povezanih glumaca ni u bazi (`filmium_media_people`) ni u `cast_names`.",
        "Obogatiti preko TMDB/IMDB (skill (Prikupljanje info)) pa regenerisati atom.",
    ),
}
# mapiranje kratkog statusa (u media atomu) -> problem slug
PROBLEM_SLUG = {
    "fali prevod": "fali-prevod",
    "loši titlovi": "losi-titlovi",
    "bez glumaca": "bez-glumaca",
}


def problem_atoms() -> dict[str, str]:
    """slug(bez prefiksa) -> sadržaj detaljnog problem-atoma (region `problemi`)."""
    out: dict[str, str] = {}
    for slug, (name, sta, fix) in PROBLEM_DEFS.items():
        aslug = f"problem-{slug}"
        body = [
            "---",
            f"id: {aslug}",
            "type: problem",
            "domain: filmium",
            f'title: "{name}"',
            "tags: [problem, filmium]",
            "---",
            "",
            "## 🎯 ŠTA JE",
            sta,
            "",
            "## 🛠️ KAKO SE REŠAVA",
            fix,
            "",
        ]
        out[aslug] = "\n".join(body).rstrip() + "\n"
    return out


# ==========================================================================
#  MEDIA atom (film / serija) — kompaktan
# ==========================================================================

def _media_kategorija(cat: str, title: str, keywords, is_series: bool) -> str:
    """Kategorija atoma: ANIME / Animirano / obično, serija vs film."""

    kws = [k.lower() for k in jarr(keywords)]
    is_anime = ("anime" in kws) or ("anime" in (title or "").lower())
    if is_anime:
        return "ANIME serija" if is_series else "ANIME film"
    if cat == "animated":
        return "Animirano (serija)" if is_series else "Animirano (film)"
    return "Serija" if is_series else "Film"


def _media_actors(con: sqlite3.Connection, m: dict) -> tuple[list, list]:
    """(reditelji, glumci) iz baze; ako baza nema glumce → fallback na
    cast_names iz reda (top 10)."""

    directors, actors = cast_for(con, m["id"])
    if not actors:
        for nm in jarr(m["cast_names"])[:10]:
            actors.append((slugify(nm), nm))
    return directors, actors


def _media_problems(con: sqlite3.Connection, m: dict, subs: list,
                    actors: list) -> list[str]:
    """Lista problema naslova (fali prevod / loši titlovi / bez glumaca)."""

    problems: list[str] = []
    if not subs:
        problems.append("fali prevod")
    if repair_issues(con, m["id"]):
        problems.append("loši titlovi")
    if not actors:
        problems.append("bez glumaca")
    return problems


def _media_note(m: dict) -> str:
    """Lična „važna info" beleška iz editor_settings.basic.personal_note."""

    vazna = "—"
    try:
        es = json.loads(m["editor_settings"] or "{}")
        note = ((es.get("basic") or {}).get("personal_note") or "").strip()
        if note:
            vazna = note
    except Exception:  # noqa: BLE001, S110
        pass
    return vazna


def _media_derive(con: sqlite3.Connection, m: dict) -> dict:
    """Izvučeni metapodaci filma/serije (kategorija, cast, problemi, note)."""
    title = m["title"]
    year = m["release_year"] or ""
    is_series = m["media_type"] == "series"
    cat = (m["content_category"] or "regular")
    teritorij = "Domaće" if cat == "domestic" else "Strano"
    kategorija = _media_kategorija(cat, title, m["keywords"], is_series)
    jezik = lang_label(m["original_language_code"]) or "NN"
    subs = subtitles_for(con, m["id"])
    directors, actors = _media_actors(con, m)
    problems = _media_problems(con, m, subs, actors)
    vazna = _media_note(m)
    return {
        "title": title, "year": year, "slug": media_slug(title, year),
        "is_series": is_series, "kategorija": kategorija,
        "tip": "serija" if is_series else "film", "teritorij": teritorij,
        "jezik": jezik, "subs": subs, "prevod": subs[0] if subs else "NN",
        "directors": directors, "actors": actors,
        "akteri_names": [n for _, n in actors[:6]],
        "status": ", ".join(problems) if problems else "OK",
        "problem_links": " ".join(
            f"[[problem-{PROBLEM_SLUG[p]}|{p}]]" for p in problems if p in PROBLEM_SLUG
        ),
        "vazna": vazna, "coll": (m["collection"] or "").strip(),
    }


def _media_body(con: sqlite3.Connection, m: dict, d: dict) -> list[str]:
    """Zone tela atoma filma/serije (KONTEKST/INFO/VEZE/SADRŽAJ/sezone)."""
    b = [
        "## 🎯 KONTEKST",
        f"{d['kategorija']} — {d['teritorij']}. Audio: {d['jezik']}, prevod: {d['prevod']}.",
        "", "## 📋 INFO", "- **Status videa:** Film",
        f"- **Tip:** {'Serija' if d['is_series'] else 'Film'}",
        f"- **Teritorijalno:** {d['teritorij']}",
        f"- **Kategorija:** {d['kategorija']}",
        f"- **Jezik (audio):** {d['jezik']}",
        f"- **Prevod:** {(', '.join(d['subs'])) if d['subs'] else 'NN'}",
        "- **Glavni akteri:** " + (", ".join(f"[[{s}]]" for s, _ in d['actors'][:6]) if d['actors'] else "NN"),
        f"- **Status:** {d['status']}" + (f" — {d['problem_links']}" if d['problem_links'] else ""),
        "", "## ⚠️ VAŽNA INFO", d['vazna'], "", "## 🔀 VEZE",
        f"- **FILMIUM:** [Otvori film u FILMIUM-u]({media_page_url(m['id'])})",
    ]
    if d['directors']:
        b.append("- **Režija:** " + ", ".join(f"[[{s}]]" for s, _ in d['directors']))
    if d['actors']:
        b.append("- **Glumci:** " + ", ".join(f"[[{s}]]" for s, _ in d['actors']))
    if d['coll']:
        b.append(f"- **Kolekcija:** [[{slugify(d['coll'])}]]")
    kws_raw = list(dict.fromkeys(jarr(m["keywords"])))[:12]
    if kws_raw:
        b += ["", "## 💻 SADRŽAJ", "Ključne reči: " + ", ".join(kws_raw)]
    try:
        from core.domains.filmium.media_external import build_ratings_section
        rs = build_ratings_section(con, m["id"])
        if rs:
            b += ["", rs.rstrip()]
    except Exception:  # noqa: BLE001, S110
        pass
    if d['is_series']:
        seasons = seasons_for(con, m["id"])
        if seasons:
            b += ["", "## 🎬 PREVODI PO SEZONAMA"]
            subs_lab = ", ".join(d['subs']) if d['subs'] else "NN"
            for s in seasons:
                eps = f" · {s['eps']} ep." if s["eps"] else ""
                b.append(f"- Sezona {s['n']}{eps}: {subs_lab}")
    return b


def build_media_atom(con: sqlite3.Connection, m: dict) -> tuple[str, str, str]:
    """Vrati (podfolder, slug, sadržaj) za jedan film/seriju. `m` = red iz
    filmium_media_items kao dict."""
    d = _media_derive(con, m)
    naslov = f"{d['title']} ({d['year']})" if d['year'] else d['title']
    fm = [
        f"id: {d['slug']}", "type: media_entry", "domain: filmium",
        f"title: {y(naslov)}",
        f"media_type: {'tv_show' if d['is_series'] else 'movie'}",
    ]
    if m["tmdb_id"]:
        fm.append(f"tmdb_id: {m['tmdb_id']}")
    fm.append(f"filmium_url: {media_page_url(m['id'])}")
    fm += [
        "status_videa: Film", f"tip_videa: {d['tip']}",
        f"teritorijalni_status: {d['teritorij']}", f"kategorija: {y(d['kategorija'])}",
        f"jezik_videa: {y(d['jezik'])}", f"prevod_videa: {y(d['prevod'])}",
    ]
    fm.append("glavni_akteri: " + ("[" + ", ".join(y(n) for n in d['akteri_names']) + "]" if d['akteri_names'] else "NN"))
    fm.append(f"problem: {y(d['status'])}")
    fm.append(f"tags: [{'serija' if d['is_series'] else 'film'}, tmdb]")
    b = ["---", "\n".join(fm), "---", ""] + _media_body(con, m, d)
    sub = "serije" if d['is_series'] else "filmovi"
    return sub, d['slug'], "\n".join(b) + "\n"


# ==========================================================================
#  KOLEKCIJE (lične) + FRANŠIZE (TMDB)
# ==========================================================================

def build_personal_collection_atoms(con: sqlite3.Connection) -> dict[str, str]:
    """slug -> sadržaj atoma za svaku ličnu kolekciju (filmium_collections)."""
    out: dict[str, str] = {}
    try:
        cols = con.execute(
            "SELECT id, name, description FROM filmium_collections ORDER BY id").fetchall()
    except sqlite3.Error:
        return out
    for row in cols:
        cid, name = row["id"], row["name"]
        desc = (row["description"] or "").strip()
        rows = con.execute(
            "SELECT m.title, m.release_year, m.media_type "
            "FROM filmium_collection_items ci "
            "JOIN filmium_media_items m ON m.id = ci.media_id "
            "WHERE ci.collection_id = ? "
            "ORDER BY m.media_type, m.release_year, m.title", (cid,)).fetchall()
        films = [(r["title"], r["release_year"]) for r in rows if r["media_type"] != "series"]
        series = [(r["title"], r["release_year"]) for r in rows if r["media_type"] == "series"]
        slug = slugify(name)
        L = [
            "---", f"id: {slug}", "type: collection", "domain: filmium",
            f'title: {y(name)}', f'kolekcija: {y(name)}',
            (f'opis: {y(desc)}' if desc else 'opis: ""'),
            f"broj_stavki: {len(rows)}", f"filmova: {len(films)}", f"serija: {len(series)}",
            "tags: [kolekcija, filmium, licna-kolekcija]", "---", "",
            "## 🎯 KONTEKST",
            (f"Lična kolekcija **{name}** — {len(rows)} naslova "
            f"({len(films)} filmova, {len(series)} serija)."),
        ]
        if desc:
            L.append(f"> {desc}")
        L.append("")
        if films:
            L.append(f"## 🎬 FILMOVI ({len(films)})")
            for tt, yy in films:
                L.append(f"- [[{media_slug(tt, yy)}]] — {tt} ({yy or '?'})")
            L.append("")
        if series:
            L.append(f"## 📺 SERIJE ({len(series)})")
            for tt, yy in series:
                L.append(f"- [[{media_slug(tt, yy)}]] — {tt} ({yy or '?'})")
            L.append("")
        out[slug] = "\n".join(L).rstrip() + "\n"
    return out


def build_franchise_atom(cslug: str, coll: dict) -> str:
    """TMDB franšiza (region `franshize`). `coll` = {name, films:set(slugova)}."""
    films = sorted(coll.get("films", []))
    L = [
        "---", f"id: {cslug}", "type: collection", "domain: filmium",
        f"title: {y(coll['name'])}", "status: verified", "source: tmdb",
        f"broj_filmova: {len(films)}", "tags: [franshiza, tmdb]", "---", "",
        "## 🎯 KONTEKST", f"TMDB franšiza „{coll['name']}“ — {len(films)} naslova.", "",
        "## 🔀 VEZE",
        "- Filmovi: " + ", ".join(f"[[{f}]]" for f in films),
    ]
    return "\n".join(L).rstrip() + "\n"


# ==========================================================================
#  ALATI / VEŠTINE (AI-namenjeni) — kurirani sadržaj
# ==========================================================================

_TOOLS = {
    "Skener": ("Otkrivanje novih ili izmenjenih fajlova u biblioteci.",
        "Kada treba osvežiti biblioteku posle dodavanja fajlova, ili pre uvoza.",
        "Ulaz: koren biblioteke (F:). Izlaz: lista media fajlova (novi/izmenjeni) -> uvoz.",
        ["batch-uvoz-u-biblioteku", "nadzor-direktorijuma", "upload-filmova-serija"]),
    "TMDB": ("Primarni izvor metapodataka i slika (naziv, godina, žanr, poster, cast, kolekcija).",
        "Za SVAKI novi naslov — prvi izvor istine za metapodatke i postere.",
        "Ulaz: naslov+godina (ili tmdb_id). Izlaz: metapodaci+slike. Zahteva API ključ u config/tmdb.json (dodaje korisnik).",
        ["prikupljanje-info-tmdb-imdb", "imdb", "region-filmovi"]),
    "IMDB": ("Ocene i broj glasova (Cinemagoer).",
        "Za dopunu ocena kada TMDB ocena nije dovoljna; keyless.",
        "Ulaz: naslov/imdb_id. Izlaz: imdb_rating, broj glasova.",
        ["tmdb", "rotten-tomatoes", "prikupljanje-info-tmdb-imdb"]),
    "Jikan": ("Anime/MAL podaci (Jikan API); keyless.",
        "Samo za ANIME naslove — MAL score, epizode, žanr, status.",
        "Ulaz: naslov anime. Izlaz: mal_score, epizode, tip.",
        ["region-anime", "prikupljanje-info-tmdb-imdb"]),
    "Rotten Tomatoes": ("Tomatometer (kritika) i Audience score (publika); keyless.",
        "Za dodatni ugao ocene (kritika vs publika).",
        "Ulaz: naslov+godina. Izlaz: rt_tomatometer, rt_audience_score.",
        ["imdb", "prikupljanje-info-tmdb-imdb"]),
    "TVmaze": ("Serije: epizode, mreža, raspored, ocena; keyless.",
        "Za SERIJE — struktura sezona/epizoda i podaci o emitovanju.",
        "Ulaz: naslov serije. Izlaz: sezone, epizode, mreža, tvmaze_rating.",
        ["region-serije", "prikupljanje-info-tmdb-imdb"]),
    "Torenti": ("Preuzimanje sadržaja preko qBittorrent-a.",
        "Kada naslov postoji u planu a fali fajl. OPREZ: samo autorizovan sadržaj.",
        "Ulaz: magnet/torrent. Izlaz: preuzet fajl -> uvoz.",
        ["upload-filmova-serija", "batch-uvoz-u-biblioteku"]),
    "mpv": ("Ugrađeni plejer sa overlay-om.",
        "Za puštanje naslova sa titlom unutar aplikacije.",
        "Ulaz: putanja fajla + titl. Izlaz: reprodukcija.",
        ["vlc", "prevodilac"]),
    "VLC": ("Spoljni plejer — rezerva za egzotične kodeke.",
        "Kada mpv ne može da dekodira format.",
        "Ulaz: putanja fajla. Izlaz: reprodukcija u VLC-u.",
        ["mpv"]),
    "Prevodilac": ("Prevod titlova i opisa (na srpski).",
        "Kada fali srpski titl ili je opis na stranom jeziku.",
        "Ulaz: .srt / tekst opisa. Izlaz: prevedeni titl/opis.",
        ["mpv", "region-filmovi"]),
}
_SKILLS = {
    "Upload filmova/serija": ("Ubacivanje pojedinačnog naslova u biblioteku (fajl + metapodaci).",
        "Kada korisnik doda jedan film/seriju koji treba registrovati.",
        "Ulaz: fajl(ovi). Izlaz: unos u bazi + atomi + metapodaci.",
        ["batch-uvoz-u-biblioteku", "skener", "prikupljanje-info-tmdb-imdb"]),
    "Batch uvoz u biblioteku": ("Masovni uvoz više naslova odjednom.",
        "Kada ima mnogo novih fajlova (npr. posle skeniranja).",
        "Ulaz: lista fajlova/folder. Izlaz: masovni unos + obogaćivanje.",
        ["upload-filmova-serija", "skener", "prikupljanje-info-tmdb-imdb"]),
    "Prikupljanje info (TMDB/IMDB/…)": ("Orkestracija info-alata radi obogaćivanja metapodataka.",
        "Posle uvoza — ocene, cast, posteri, kolekcije, žanrovi.",
        "Ulaz: naslov(i). Izlaz: kompletni metapodaci. Redosled: TMDB -> IMDB/RT/TVmaze/Jikan.",
        ["tmdb", "imdb", "rotten-tomatoes", "tvmaze", "jikan"]),
    "Kontrola cron poslova": ("Zakazivanje i nadzor periodičnih poslova.",
        "Za automatsko skeniranje/obogaćivanje po rasporedu.",
        "Ulaz: raspored (cron). Izlaz: zakazani/pokrenuti poslovi + status.",
        ["skener", "prikupljanje-info-tmdb-imdb"]),
    "Pretraga fajlova u direktorijumu": ("Traženje fajlova po imenu/tipu u folderu.",
        "Kada treba naći fajl ili proveriti šta postoji na disku.",
        "Ulaz: folder + obrazac. Izlaz: lista pogodaka.",
        ["nadzor-direktorijuma", "skener"]),
    "Nadzor direktorijuma": ("Praćenje foldera i reagovanje na nove fajlove (watch).",
        "Kada želimo automatski uvoz čim se fajl pojavi.",
        "Ulaz: folder za nadzor. Izlaz: dogadjaj (novi fajl) -> uvoz.",
        ["upload-filmova-serija", "pretraga-fajlova-u-direktorijumu"]),
    "FILMIUM Search (filmovi/serije/glumci)": ("Hibridna pretraga baze i atoma.",
        "Kada AI ili korisnik traži naslov, glumca ili vezu.",
        "Ulaz: upit. Izlaz: rangirani pogoci + veze ka atomima.",
        ["region-filmovi", "region-serije", "region-glumci"]),
}


def _agent_atom(kind: str, name: str, icon: str, desc: str, cur: dict) -> tuple[str, str]:
    slug = slugify(name)
    sta, kada, kako, veze = cur.get(name, (desc or name, "Po potrebi domena.",
                                           "Ulaz/izlaz zavise od konteksta.", []))
    kat = "Alat" if kind == "tool" else "Veština"
    ttag = "alat" if kind == "tool" else "vestina"
    L = [
        "---", f"id: {slug}", f"type: {kind}", "domain: filmium",
        f"title: {y(name)}", f"kategorija: {kat}", f"ikona: {y(icon)}",
        f"namena: {y(desc or sta)}", f"tags: [{ttag}, filmium]", "---", "",
        "## 🎯 ŠTA JE", sta, "",
        "## 🤖 KADA AI OVO KORISTI", kada, "",
        "## 🛠️ KAKO (ulaz -> izlaz)", kako, "",
    ]
    if veze:
        L.append("## 🔀 VEZE")
        L += [f"- [[{v}]]" for v in veze]
        L.append("")
    return slug, "\n".join(L).rstrip() + "\n"


def build_tool_skill_atoms(tools: list[dict], skills: list[dict]) -> tuple[dict, dict, list, list]:
    """Vrati (tool_atoms{slug:content}, skill_atoms{slug:content}, tools+slug, skills+slug)."""
    ta, sa = {}, {}
    for t in tools:
        slug, content = _agent_atom("tool", t["name"], t.get("icon", "wrench"), t.get("description", ""), _TOOLS)
        t["slug"] = slug
        ta[slug] = content
    for s in skills:
        slug, content = _agent_atom("skill", s["name"], s.get("icon", "sparkles"), s.get("description", ""), _SKILLS)
        s["slug"] = slug
        sa[slug] = content
    return ta, sa, tools, skills


# ==========================================================================
#  finalize (vreme kreiranja) + upis
# ==========================================================================

_CREATED_RE = re.compile(r'^atom_kreiran:\s*(.+)$', re.MULTILINE)


def _existing_created(path: Path) -> str | None:
    try:
        txt = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    m = _CREATED_RE.search(txt)
    return m.group(1).strip() if m else None


def finalize(content: str, path: Path, ts: str | None = None) -> str:
    """Ubaci `atom_kreiran` (očuvano ako fajl već ima) + `atom_azuriran` u frontmatter."""
    if _CREATED_RE.search(content):
        return content
    ts = ts or now_iso()
    created = _existing_created(path) or ts
    inject = f"atom_kreiran: {created}\natom_azuriran: {ts}\n"
    if content.startswith("---\n"):
        return "---\n" + inject + content[4:]
    return "---\n" + inject + "---\n\n" + content



def _v3_source_path(head, path):
    import re as _re
    from pathlib import Path as _P
    if _re.search(r"^source_path:", head, _re.MULTILINE):
        return None
    sp = str(path)
    for mark in (".ai/atomi", "Actors", ".ai/"):
        i = sp.find(mark)
        if i >= 0:
            sp = sp[i:]
            break
    else:
        sp = _P(path).name
    return "source_path: " + sp


def _v3_summary(head, body):
    import json as _json
    import re as _re
    if _re.search(r"^summary:", head, _re.MULTILINE):
        return None
    first = ""
    for ln in body.splitlines():
        s = ln.strip()
        if s and s[0] not in "#[|`":
            s = _re.sub(r"^[-*>]\s*", "", s)
            s = _re.sub(r"\*\*([^*]+)\*\*", r"\1", s)
            if len(s) >= 12:
                first = s[:140]
                break
    tm = _re.search(r"^title:\s*(.+)$", head, _re.MULTILINE)
    summ = first or (tm.group(1).strip().strip("'\"") if tm else "")
    return ("summary: " + _json.dumps(summ, ensure_ascii=False)) if summ else None


def _v3_keywords(head):
    import re as _re
    if _re.search(r"^keywords:", head, _re.MULTILINE):
        return None
    words = []
    tm = _re.search(r"^title:\s*(.+)$", head, _re.MULTILINE)
    if tm:
        words += [w for w in _re.sub(r"[^a-z0-9 ]", " ", tm.group(1).lower()).split() if len(w) > 2]
    ga = _re.search(r"^glavni_akteri:\s*\[(.*?)\]", head, _re.MULTILINE)
    if ga:
        words += [x.strip().lower() for x in ga.group(1).split(",") if x.strip()]
    for fld in ("kategorija", "media_type", "status_videa", "profesije"):
        fm2 = _re.search(r"^" + fld + r":\s*(.+)$", head, _re.MULTILINE)
        if fm2:
            words.append(fm2.group(1).strip().strip("[]'\"").lower())
    seen = []
    for w in words:
        w = w.strip()
        if w and w not in seen:
            seen.append(w)
    return ("keywords: [" + ", ".join(seen[:12]) + "]") if seen else None


def _v3_edges(head, body):
    import re as _re
    if _re.search(r"^edges:", head, _re.MULTILINE):
        return None
    tgts = []
    for lt in _re.findall(r"\[\[([^\]]+)\]\]", body):
        t = _re.sub(r"[^a-z0-9]+", "-", lt.lower()).strip("-")
        if t and t not in tgts:
            tgts.append(t)
    if not tgts:
        return None
    return "edges:\n" + "\n".join(
        "- {type: references, target: " + t + ", weight: 0.5}" for t in tgts[:20]
    )


def _ensure_v3(content: str, path) -> str:
    """Best-effort v3 dopuna (summary/keywords/source_path/edges). Nikad ne baca."""
    try:
        if not content.startswith("---\n"):
            return content
        head = content.split("\n---", 1)[0]
        body = content.split("\n---", 1)[1] if "\n---" in content else ""
        ins = [x for x in (_v3_source_path(head, path), _v3_summary(head, body),
                           _v3_keywords(head), _v3_edges(head, body)) if x]
        if not ins:
            return content
        return content.replace("---\n", "---\n" + "\n".join(ins) + "\n", 1)
    except Exception:  # noqa: BLE001
        return content


def write_atom(path: Path, content: str, ts: str | None = None) -> None:
    """Upis atoma sa vremenom kreiranja/ažuriranja (idempotentno za `atom_kreiran`)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_ensure_v3(finalize(content, path, ts), path), encoding="utf-8")


# ==========================================================================
#  Orkestracija (za skripte / job / upload)
# ==========================================================================

def open_db(db_path: str) -> sqlite3.Connection:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout=10000")
    return con


def _regen_one_atom(con, r, atoms_root: Path, ts: str) -> bool:
    """Izgradi i upisi jedan media atom; greska na jednom ne rusi regeneraciju."""

    try:
        sub, slug, content = build_media_atom(con, dict(r))
        write_atom(atoms_root / sub / f"{slug}.md", content, ts)
        return True
    except Exception:  # noqa: BLE001
        return False


def regenerate_media(con: sqlite3.Connection, atoms_root: Path, ids: list[int] | None = None) -> int:
    if ids:
        qs = ",".join("?" * len(ids))
        rows = con.execute(f"SELECT * FROM filmium_media_items WHERE id IN ({qs}) ORDER BY id", ids).fetchall()
    else:
        rows = con.execute("SELECT * FROM filmium_media_items ORDER BY id").fetchall()
    ts = now_iso()
    ok = 0
    for r in rows:
        if _regen_one_atom(con, r, atoms_root, ts):
            ok += 1
    return ok


def regenerate_collections(con: sqlite3.Connection, atoms_root: Path) -> int:
    ts = now_iso()
    n = 0
    for slug, content in build_personal_collection_atoms(con).items():
        write_atom(atoms_root / "kolekcije" / f"{slug}.md", content, ts)
        n += 1
    return n


def regenerate_problems(atoms_root: Path) -> int:
    ts = now_iso()
    n = 0
    for slug, content in problem_atoms().items():
        write_atom(atoms_root / "problemi" / f"{slug}.md", content, ts)
        n += 1
    return n
