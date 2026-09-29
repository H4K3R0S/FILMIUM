"""TMDB people: slug/JSON util + builderi media atoma — izdvojeno radi veličine."""

import json
import re
import unicodedata

from core.domains.filmium import atom_factory as _AF


def slugify(text: object) -> str:
    """Identično `atom_lint.slugify` / `fallthrough.slugify` (NFKD, skini
    akcente, mala slova, sve što nije [a-z0-9] -> '-', trim, max 80)."""
    norm = unicodedata.normalize("NFKD", str(text))
    norm = "".join(c for c in norm if not unicodedata.combining(c))
    norm = re.sub(r"[^a-z0-9]+", "-", norm.lower()).strip("-")[:80]
    return norm or "atom"


def _jarr(raw: object) -> list:
    """Tolerantno parsira JSON listu iz kolone (`cast_names`/`keywords`);
    prihvata i zarezom-odvojen string ako JSON ne uspe."""
    if not raw:
        return []
    try:
        value = json.loads(raw)
        return value if isinstance(value, list) else []
    except (TypeError, ValueError):
        return [x.strip() for x in str(raw).split(",") if x.strip()]


def _atom_compact_meta(con, m: dict, *, is_series: bool, title: str,
                       cast: list) -> dict:
    """Kompaktni metapodaci atoma: kategorija/teritorija/prevod/status.

    SR: kompaktni bogati metapodaci (kategorija/teritorij/prevod/status).
    EN: rich compact metadata for the atom (category/territory/subs/status).
    """

    _cat = (m.get("content_category") or "regular")
    _kws_low = [k.lower() for k in _jarr(m.get("keywords"))]
    _anime = ("anime" in _kws_low) or ("anime" in (title or "").lower())
    teritorij = "Domaće" if _cat == "domestic" else "Strano"
    if _anime:
        kategorija = "ANIME serija" if is_series else "ANIME film"
    elif _cat == "animated":
        kategorija = "Animirano (serija)" if is_series else "Animirano (film)"
    else:
        kategorija = "Serija" if is_series else "Film"
    try:
        _subrows = con.execute(
            "SELECT DISTINCT f.language FROM filmium_media_files f "
            "JOIN filmium_media_sources sx ON sx.id=f.source_id "
            "WHERE sx.media_id=? AND f.role='subtitle' AND f.language IS NOT NULL AND f.language!=''",
            (m["id"],)).fetchall()
    except Exception:  # noqa: BLE001
        _subrows = []
    _LL = {"sr":"srpski","sr-latn":"srpski","srp":"srpski","hr":"hrvatski","bs":"bosanski","en":"engleski","eng":"engleski"}
    subs: list[str] = []
    for _r in _subrows:
        _l = _LL.get(str(_r[0]).lower(), str(_r[0]))
        if _l not in subs: subs.append(_l)
    prevod = subs[0] if subs else "NN"
    problems = []
    if not subs: problems.append("fali prevod")
    if not cast: problems.append("bez glumaca")
    status = ", ".join(problems) if problems else "OK"
    return {"teritorij": teritorij, "kategorija": kategorija,
            "subs": subs, "prevod": prevod, "status": status}


def _atom_frontmatter(m: dict, *, mslug: str, title: str, year, is_series: bool,
                      meta: dict) -> list:
    """YAML frontmatter media_entry atoma (id/naslov/tip + kompaktni meta)."""

    fm = [
        f"id: {mslug}",
        f"title: {title} ({year})" if year else f"title: {title}",
        "type: media_entry",
        f"media_type: {'tv_show' if is_series else 'movie'}",
        "domain: filmium",
        "status: verified",
        "source: tmdb",
    ]
    if m.get("tmdb_id"):
        fm.append(f"tmdb_id: {m['tmdb_id']}")
    fm.append("status_videa: Film")
    fm.append(f"tip_videa: {'serija' if is_series else 'film'}")
    fm.append(f"teritorijalni_status: {meta['teritorij']}")
    kat = meta["kategorija"]
    _kq = kat if not any(c in kat for c in "()") else f'"{kat}"'
    fm.append(f"kategorija: {_kq}")
    fm.append("jezik_videa: NN")
    fm.append(f"prevod_videa: {meta['prevod']}")
    st = meta["status"]
    _aq = st if st == "OK" else f'"{st}"'
    fm.append(f"problem: {_aq}")
    if year:
        fm.append(f"release_year: {year}")
    if m.get("poster_path"):
        fm.append(f"poster_orig: {m['poster_path']}")
    if m.get("backdrop_path"):
        fm.append(f"backdrop_orig: {m['backdrop_path']}")
    if m.get("runtime_minutes"):
        fm.append(f"runtime_minutes: {m['runtime_minutes']}")
    tags = ["serija" if is_series else "film", "tmdb"]
    fm.append(f"tags: [{', '.join(tags)}]")
    return fm


def _atom_seasons_section(con, m: dict) -> list:
    """STRUKTURA SEZONA (samo serije): sezona → broj epizoda. Best-effort:
    nedostajuća kolona/tabela (stari DB) NIKAD ne obara generisanje atoma."""

    out: list[str] = []
    try:
        seasons = con.execute(
            "SELECT season_number FROM filmium_seasons WHERE media_id=? ORDER BY season_number",
            (m["id"],),
        ).fetchall()
    except Exception:  # noqa: BLE001
        seasons = []
    if seasons:
        out.append("")
        out.append("## 📺 STRUKTURA SEZONA")
        for season in seasons:
            try:
                ep_count = con.execute(
                    "SELECT COUNT(*) c FROM filmium_episodes WHERE media_id=? AND season_number=?",
                    (m["id"], season["season_number"]),
                ).fetchone()["c"]
            except Exception:  # noqa: BLE001
                ep_count = "?"
            out.append(f"- Sezona {season['season_number']}: {ep_count} epizoda")
    return out


def _atom_body(con, m: dict, fm: list, *, is_series: bool, meta: dict,
               dslug, cslugs: list, coll: str, kws: list) -> list:
    """Telo atoma: KONTEKST/INFO/VEZE/SADRŽAJ (+ sezone + spoljne ocene)."""

    body = [
        "---", "\n".join(fm), "---", "",
        "## 🎯 KONTEKST",
        (f"{'Serija' if is_series else 'Film'} iz FILMIUM biblioteke (TMDB {m.get('tmdb_id', '?')}). "
        "Metapodaci uvezeni iz baze; glumci/režiser su povezani kao entiteti (`person` atomi)."),
        "",
    ]
    body.append("## 📋 INFO")
    body.append(f"- **Tip:** {'Serija' if is_series else 'Film'}")
    body.append(f"- **Teritorijalno:** {meta['teritorij']}")
    body.append(f"- **Kategorija:** {meta['kategorija']}")
    body.append(f"- **Prevod:** {(', '.join(meta['subs'])) if meta['subs'] else 'NN'}")
    body.append(f"- **Status:** {meta['status']}")
    body.append("")
    body.append("## 🔀 VEZE")
    if dslug:
        body.append(f"- Režija: [[{dslug}]]")
    if cslugs:
        names = ", ".join(f"[[{c}]]" for c in cslugs if c)
        body.append(f"- Glavne uloge (top {len(cslugs)}): {names}")
    if coll:
        body.append(f"- Kolekcija: [[{slugify(coll)}]]")
    if kws:
        body.append("")
        body.append("## 💻 SADRŽAJ")
        body.append("Ključne reči (TMDB): " + ", ".join(kws))

    if is_series:
        body.extend(_atom_seasons_section(con, m))

    # SR: dodaj spoljne ocene (IMDb/RT/TVmaze/MAL) na kraj tela atoma —
    # posle VEZE/SADRŽAJ/STRUKTURA sekcija. Guard: nedostajuća kolona
    # (stari DB) NIKAD ne sme da obori generisanje atoma.
    # EN: append external ratings (IMDb/RT/TVmaze/MAL) to the atom body —
    # after the VEZE/SADRŽAJ/season sections. Guarded so a missing column
    # never breaks atom generation.
    try:
        from core.domains.filmium.media_external import build_ratings_section

        ratings_section = build_ratings_section(con, m["id"])
        if ratings_section:
            body.append("")
            body.append(ratings_section.rstrip())
    except Exception:  # noqa: BLE001, S110
        pass
    return body


# ----------          POSAO          ----------

def _write_atom_or_error(atoms_root, sub: str, slug: str, content: str) -> str | None:
    """Upisi jedan atom; OSError -> poruka (ne rusi regeneraciju)."""

    try:
        _AF.write_atom(atoms_root / sub / f"{slug}.md", content)
        return None
    except OSError as error:
        return f"ne mogu da upišem atom '{slug}': {error}"
