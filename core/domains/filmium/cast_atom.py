# core/domains/filmium/cast_atom.py
# ==========          CAST ENTITY: profesije + atom builder          ==========
#
# SR: Jedan izvor istine za (1) izvlačenje PROFESIJA glumca/osobe iz TMDB
#     biografije i (2) gradnju bogatog `cast_entity` atomskog fajla. Koriste ga
#     i standalone skripta (`ai_workplace/scripts/build_cast_atoms.py`) i job
#     `tmdb_people_import.py` (poziva se iz uploads/cron kad se skupljaju TMDB
#     podaci) — tako da isti algoritam radi svuda.
# EN: Single source of truth for (1) extracting a person's PROFESSIONS from the
#     TMDB biography and (2) building a rich `cast_entity` atom file. Used by
#     both the standalone script and the `tmdb_people_import` job (invoked from
#     uploads/cron whenever TMDB data is collected) so the same logic runs
#     everywhere.
#
# Zavisi SAMO od standardne biblioteke (uvozivo i iz standalone skripte).
# Depends ONLY on the standard library (importable from the standalone script).
from __future__ import annotations

import re
import unicodedata

# ----------  Kanonske profesije (fraza -> oznaka)  /  Canonical professions  ----------
# SR: Duže/specifičnije fraze MORAJU biti PRE kraćih — algoritam zauzima raspon
#     teksta pa "action choreographer" pobeđuje "choreographer" na istoj poziciji.
#     Uključene su i srpske reči (bio je obično engleski, ali radi robusnosti).
# EN: Longer/more specific phrases MUST come BEFORE shorter ones — the algorithm
#     occupies the matched span so "action choreographer" beats "choreographer"
#     at the same position. Serbian words are included too (bios are usually
#     English, but for robustness).
PROFESSION_MAP: list[tuple[str, str]] = [
    ("action choreographer", "Action Choreographer"),
    ("action director", "Action Director"),
    ("martial artist", "Martial Artist"),
    ("stunt performer", "Stunt Performer"),
    ("stunt coordinator", "Stunt Coordinator"),
    ("stunt double", "Stunt Performer"),
    ("voice actor", "Voice Actor"),
    ("voice actress", "Voice Actor"),
    ("film director", "Director"),
    ("film producer", "Producer"),
    ("record producer", "Record Producer"),
    ("television presenter", "Presenter"),
    ("television host", "Presenter"),
    ("talk show host", "Presenter"),
    ("fashion designer", "Fashion Designer"),
    ("costume designer", "Costume Designer"),
    ("makeup artist", "Makeup Artist"),
    ("visual effects", "Visual Effects Artist"),
    ("screenwriter", "Screenwriter"),
    ("songwriter", "Songwriter"),
    ("choreographer", "Choreographer"),
    ("cinematographer", "Cinematographer"),
    ("comedienne", "Comedian"),
    ("comedian", "Comedian"),
    ("filmmaker", "Filmmaker"),
    ("director", "Director"),
    ("producer", "Producer"),
    ("screenwriting", "Screenwriter"),
    ("writer", "Writer"),
    ("novelist", "Novelist"),
    ("author", "Author"),
    ("singer", "Singer"),
    ("musician", "Musician"),
    ("rapper", "Rapper"),
    ("dancer", "Dancer"),
    ("model", "Model"),
    ("entrepreneur", "Entrepreneur"),
    ("businessman", "Entrepreneur"),
    ("businesswoman", "Entrepreneur"),
    ("presenter", "Presenter"),
    ("politician", "Politician"),
    ("activist", "Activist"),
    ("philanthropist", "Philanthropist"),
    ("stuntman", "Stunt Performer"),
    ("stuntwoman", "Stunt Performer"),
    ("actor", "Actor"),
    ("actress", "Actor"),
    ("performer", "Performer"),
    # --- srpski / Serbian ---
    ("glumica", "Actor"),
    ("glumac", "Actor"),
    ("reditelj", "Director"),
    ("reziser", "Director"),
    ("producent", "Producer"),
    ("scenarista", "Screenwriter"),
    ("komicar", "Comedian"),
    ("pevacica", "Singer"),
    ("pevac", "Singer"),
    ("muzicar", "Musician"),
    ("plesac", "Dancer"),
    ("kaskader", "Stunt Performer"),
    ("koreograf", "Choreographer"),
    ("preduzetnik", "Entrepreneur"),
]


def _deaccent(text: str) -> str:
    norm = unicodedata.normalize("NFKD", text)
    return "".join(c for c in norm if not unicodedata.combining(c))


def extract_professions(
    bio: str | None,
    *,
    is_actor: bool = True,
    is_director: bool = False,
) -> list[str]:
    """
    SR: Izvlači listu profesija iz TMDB biografije. Traži UVODNU rečenicu oblika
        „... is/was a/an <nacionalnost> <profesija>, <profesija> ... and
        <profesija>." (klasičan Wikipedia/TMDB obrazac) i mapira svaku reč na
        kanonsku oznaku. Ako uvoda nema — skenira prvih 400 znakova. Redosled
        pojave se čuva; preklapanja (npr. „choreographer" unutar „action
        choreographer") se izbacuju.
    EN: Extracts the profession list from the TMDB biography. Looks for the
        INTRO sentence "... is/was a/an <nationality> <profession>, ... and
        <profession>." (the classic Wikipedia/TMDB pattern) and maps each word
        to a canonical label. Falls back to the first 400 chars when no intro is
        present. Order of appearance is preserved; overlaps (e.g.
        "choreographer" inside "action choreographer") are dropped.
    """
    professions: list[str] = []
    if bio:
        text = _deaccent(bio)
        # SR: opseg posle "is/was a/an/the" do prve tačke+razmaka ILI novog reda.
        # EN: span after "is/was a/an/the" up to first period+space OR newline.
        match = re.search(
            r"\b(?:is|was)\s+(?:an?|the)\s+(.+?)(?:\.\s|\.\n|\n|$)", text, re.DOTALL
        )
        scope = match.group(1) if match else text[:400]
        scope_l = scope.lower().replace("-", " ")

        hits: list[tuple[int, int, str]] = []
        for phrase, canon in PROFESSION_MAP:
            found = re.search(r"\b" + re.escape(phrase) + r"\b", scope_l)
            if found:
                hits.append((found.start(), len(phrase), canon))

        # SR: sortiraj po poziciji, pa DUŽA fraza prvo; zauzmi raspon.
        # EN: sort by position, then LONGER phrase first; occupy the span.
        hits.sort(key=lambda h: (h[0], -h[1]))
        occupied: list[tuple[int, int]] = []
        seen: set[str] = set()
        for start, length, canon in hits:
            end = start + length
            if any(s < end and start < e for s, e in occupied):
                continue
            if canon in seen:
                continue
            occupied.append((start, end))
            seen.add(canon)
            professions.append(canon)

    # SR: ako bio ništa nije dao, garantuj bar iz kredita (glumac/reditelj).
    # EN: if the bio yielded nothing, guarantee at least from credits.
    if not professions:
        if is_actor:
            professions.append("Actor")
        if is_director and "Director" not in professions:
            professions.append("Director")
    # SR: ako je poznat kao reditelj ali bio to ne pominje — dodaj na kraj.
    # EN: if known as a director but the bio omits it — append at the end.
    elif is_director and "Director" not in professions and "Filmmaker" not in professions:
        professions.append("Director")

    return professions


def extract_native_name(bio: str | None) -> str | None:
    """
    SR: Izvorno/maternje ime iz zagrade na početku bio-a: „(Chinese: 成龍; ...)",
        „(Korean: 봉준호)", „(Japanese: 三船 敏郎)". Vraća deo posle „<jezik>:".
    EN: Native name from the leading parenthetical: "(Chinese: 成龍; ...)",
        "(Korean: 봉준호)". Returns the text after "<language>:".
    """
    if not bio:
        return None
    match = re.search(r"\(([A-Za-z][A-Za-z .]+):\s*([^;,)]+)", bio[:220])
    if match:
        value = match.group(2).strip()
        # SR: preskoči ako je to samo latinica identična imenu (nije „izvorno").
        # EN: skip if it's just latin identical to the name (not "native").
        if value:
            return value
    return None


def extract_nicknames(bio: str | None) -> list[str]:
    """
    SR: Nadimci: „nicknamed X", „(also) known as X". Vraća do 3.
    EN: Nicknames: "nicknamed X", "(also) known as X". Returns up to 3.
    """
    out: list[str] = []
    if not bio:
        return out
    patterns = [
        r"nicknamed\s+[\"“']?([A-Z][\w'’-]+(?:\s+[A-Z][\w'’-]+)?)",
        r"(?:also\s+)?known\s+as\s+[\"“']?([A-Z][\w'’ -]{2,30})",
    ]
    for pat in patterns:
        for match in re.finditer(pat, bio):
            value = match.group(1).strip(" \"'“’")
            if value and value not in out:
                out.append(value)
    return out[:3]


def extract_signature_traits(bio: str | None) -> list[str]:
    """
    SR: Prepoznatljive odlike: „known for his/her/their <a>, <b>, and <c>".
        Npr. za Jackie Chana: acrobatic fighting style, comic timing, ...
    EN: Signature traits: "known for his/her/their <a>, <b>, and <c>".
    """
    if not bio:
        return []
    match = re.search(
        r"known for (?:his|her|their|its)\s+(.+?)(?:\.\s|\.\n|\n|$)", bio, re.DOTALL
    )
    if not match:
        return []
    segment = match.group(1)
    parts = re.split(r",\s*|\s+and\s+", segment)
    traits = []
    for part in parts:
        # SR: skini vodece "and"/"&" (npr. ", and innovative stunts").
        # EN: strip a leading "and"/"&" (e.g. ", and innovative stunts").
        clean = re.sub(r"^(?:and|&)\s+", "", part.strip(), flags=re.IGNORECASE).strip()
        if len(clean) > 2:
            traits.append(clean)
    return traits[:6]


def derive_nationality(place_of_birth: str | None, bio: str | None) -> str | None:
    """
    SR: Nacionalnost iz uvoda bio-a: reč(i) između „is/was a/an" i prve
        profesije (npr. „American", „Hong Kong", „British"). Ako toga nema —
        poslednji segment mesta rođenja (zemlja).
    EN: Nationality from the bio intro: the word(s) between "is/was a/an" and the
        first profession (e.g. "American", "Hong Kong"). Falls back to the last
        segment of the place of birth (the country).
    """
    if bio:
        text = _deaccent(bio)
        match = re.search(r"\b(?:is|was)\s+(?:an?|the)\s+(.+?)(?:\.\s|\n|$)", text, re.DOTALL)
        if match:
            scope = match.group(1)
            scope_l = scope.lower().replace("-", " ")
            first = None
            for phrase, _canon in PROFESSION_MAP:
                found = re.search(r"\b" + re.escape(phrase) + r"\b", scope_l)
                if found and (first is None or found.start() < first):
                    first = found.start()
            if first:
                prefix = scope[:first].strip()
                # SR: skini pridev/članove tipa „former", „retired", „professional".
                # EN: strip adjectives/articles like "former", "retired".
                prefix = re.sub(
                    r"\b(former|retired|professional|semi[- ]?retired|the)\b",
                    "", prefix, flags=re.IGNORECASE,
                ).strip(" ,-")
                # SR: uzmi do 3 reči (npr. „Hong Kong", „South Korean").
                # EN: keep up to 3 words (e.g. "Hong Kong", "South Korean").
                words = prefix.split()
                if 1 <= len(words) <= 3 and all(w[:1].isupper() for w in words):
                    return " ".join(words)
    if place_of_birth:
        country = place_of_birth.split(",")[-1].strip()
        if country:
            return country
    return None


# ----------          YAML helper          ----------

def _y(value: object) -> str:
    """SR: bezbedno YAML-kvotovanje skalara. / EN: safe YAML scalar quoting."""
    s = "" if value is None else str(value)
    if s == "":
        return '""'
    if re.search(r'[:#\[\]{}",\'\n]|^\s|\s$', s):
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return s


def _actor_url(slug: str) -> str:
    """Link ka FILMIUM stranici glumca (#/filmium/actors/<slug>); lenj import da
    se izbegne kružna zavisnost sa atom_factory."""
    try:
        from core.domains.filmium.atom_factory import actor_page_url
        return actor_page_url(slug)
    except Exception:  # noqa: BLE001
        return f"http://127.0.0.1:4801/#/filmium/actors/{slug}"


def _cast_derive(d: dict) -> dict:
    """Izvedeni podaci glumca iz bio/filmografije (native/nationality/status/godine)."""
    d["native"] = d.get("native_name") or extract_native_name(d.get("bio"))
    d["nationality"] = derive_nationality(d.get("place_of_birth"), d.get("bio"))
    d["nicknames"] = extract_nicknames(d.get("bio"))
    d["signature"] = extract_signature_traits(d.get("bio"))
    d["status"] = "deceased" if d.get("deathday") else "active"
    years = []
    for f in d["filmography"]:
        yy = str(f.get("year") or "")
        if yy.isdigit():
            years.append(int(yy))
    d["year_from"] = min(years) if years else None
    d["year_to"] = max(years) if years else None
    return d


def _cast_frontmatter(d: dict) -> list[str]:
    fm: list[str] = [
        f"id: {d['slug']}", "type: cast_entity", "domain: filmium",
        f"title: {_y(d['name'])}", f"name: {_y(d['name'])}",
    ]
    if d["native"]:
        fm.append(f"native_name: {_y(d['native'])}")
    if d["birthday"]:
        fm.append(f"birth_date: {_y(d['birthday'])}")
    if d["deathday"]:
        fm.append(f"death_date: {_y(d['deathday'])}")
    if d["place_of_birth"]:
        fm.append(f"birth_place: {_y(d['place_of_birth'])}")
    if d["nationality"]:
        fm.append(f"nationality: {_y(d['nationality'])}")
    fm.append(f"status: {d['status']}")
    if d["tmdb_id"]:
        fm.append(f"tmdb_id: {d['tmdb_id']}")
    if d["imdb_id"]:
        fm.append(f"imdb_id: {_y(d['imdb_id'])}")
    fm.append(f"filmium_url: {_actor_url(d['slug'])}")
    if d["known_for"]:
        fm.append(f"known_for: {_y(d['known_for'])}")
    fm.append(f"gallery_count: {int(d['gallery_count'] or 0)}")
    if d["image_rel"]:
        fm.append(f"image_local: {_y(d['image_rel'])}")
    if d["professions"]:
        fm.append("professions:")
        fm.extend(f"  - {_y(p)}" for p in d["professions"])
    if d["signature"]:
        fm.append("signature_traits:")
        fm.extend(f"  - {_y(s)}" for s in d["signature"])
    fm.append("source: tmdb")
    fm.append("tags: [osoba, cast_entity, tmdb]")
    return fm


def _cast_profile_lines(d: dict) -> list[str]:
    """PROFIL sekcija (rođen/preminuo/izvorno ime/nacionalnost/… /naslova)."""

    lines: list[str] = []
    if d["birthday"] or d["place_of_birth"]:
        rodjen = d["birthday"] or "?"
        if d["place_of_birth"]:
            rodjen += f", {d['place_of_birth']}"
        lines.append(f"- **Rođen:** {rodjen}")
    if d["deathday"]:
        lines.append(f"- **Preminuo:** {d['deathday']}")
    if d["native"]:
        lines.append(f"- **Izvorno ime:** {d['native']}")
    if d["nationality"]:
        lines.append(f"- **Nacionalnost:** {d['nationality']}")
    if d["nicknames"]:
        lines.append(f"- **Nadimci:** {', '.join(d['nicknames'])}")
    lines.append(f"- **Status:** {'preminuo' if d['deathday'] else 'aktivan'}")
    if d["known_for"]:
        lines.append(f"- **Primarno polje (TMDB):** {d['known_for']}")
    if d["year_from"] and d["year_to"]:
        raspon = f"{d['year_from']}" if d["year_from"] == d["year_to"] else f"{d['year_from']} – {d['year_to']}"
        lines.append(f"- **Aktivan (po filmografiji):** {raspon}")
    if d["professions"]:
        lines.append(f"- **Profesije:** {', '.join(d['professions'])}")
    lines.append(
        f"- **Naslova (biblioteka / TMDB ukupno):** {d['lib_film_count']} / {len(d['filmography'])}"
    )
    return lines


def _cast_links_lines(d: dict) -> list[str]:
    """VEZE sekcija (FILMIUM link + režirao/glumio ili poruka da veza nema)."""

    lines = [f"- **FILMIUM:** [Otvori glumca u FILMIUM-u]({_actor_url(d['slug'])})"]
    if d["directed_slugs"]:
        lines.append("- **Režirao:** " + ", ".join(f"[[{s}]]" for s in d["directed_slugs"]))
    if d["acted_slugs"]:
        lines.append("- **Glumio u:** " + ", ".join(f"[[{s}]]" for s in d["acted_slugs"]))
    if not d["directed_slugs"] and not d["acted_slugs"]:
        lines.append("- (još nema povezanih naslova u biblioteci)")
    return lines


def _cast_filmography_lines(d: dict) -> list[str]:
    """FILMOGRAFIJA (TMDB): do 12 naslova, najnoviji prvi."""

    if not d["filmography"]:
        return []
    lines = ["", "## 🎬 FILMOGRAFIJA (TMDB)",
             f"Ukupno {len(d['filmography'])} naslova u TMDB filmografiji."]

    def _yr(f: dict) -> int:
        y = str(f.get("year") or "")
        return int(y) if y.isdigit() else 0
    for f in sorted(d["filmography"], key=_yr, reverse=True)[:12]:
        lines.append(f"- {f.get('title') or '?'} ({f.get('year') or '—'})")
    return lines


def _cast_body(d: dict, fm: list[str]) -> list[str]:
    prof_line = ", ".join(d["professions"]) if d["professions"] else (
        "reditelj" if d["is_director"] else "glumac")
    body: list[str] = [
        "---", "\n".join(fm), "---", "",
        "## 🎯 KONTEKST",
        f"{d['name']} — {prof_line} (FILMIUM biblioteka).",
        "", "## 🧬 PROFIL",
    ]
    body += _cast_profile_lines(d)
    if d["bio"]:
        body += ["", "## 📋 BIOGRAFIJA (DOSIJE)", d["bio"].strip()]
    if d["signature"]:
        body += ["", "## 🥋 PREPOZNATLJIV STIL"]
        body += [f"- {s}" for s in d["signature"]]
    body += ["", "## 🔀 VEZE"]
    body += _cast_links_lines(d)
    body += _cast_filmography_lines(d)
    return body


def build_cast_entity_atom(
    *,
    slug: str,
    name: str,
    bio: str | None = None,
    birthday: str | None = None,
    deathday: str | None = None,
    place_of_birth: str | None = None,
    known_for: str | None = None,
    tmdb_id: object = None,
    imdb_id: str | None = None,
    native_name: str | None = None,
    professions: list[str] | None = None,
    is_director: bool = False,
    image_rel: str | None = None,
    gallery_count: int = 0,
    directed_slugs: list[str] | None = None,
    acted_slugs: list[str] | None = None,
    filmography: list[dict] | None = None,
    lib_film_count: int = 0,
) -> str:
    """Gradi bogat `cast_entity` atom (YAML frontmatter + telo). `id` OSTAJE slug
    (npr. `jackie-chan`) da postojeći [[linkovi]] iz media atoma i dalje rade.
    Sve što fali graciozno se izostavlja."""
    d = _cast_derive({
        "slug": slug, "name": name, "bio": bio, "birthday": birthday, "deathday": deathday,
        "place_of_birth": place_of_birth, "known_for": known_for, "tmdb_id": tmdb_id,
        "imdb_id": imdb_id, "native_name": native_name, "is_director": is_director,
        "image_rel": image_rel, "gallery_count": gallery_count,
        "professions": professions or [],
        "directed_slugs": sorted(set(directed_slugs or [])),
        "acted_slugs": sorted(set(acted_slugs or [])),
        "filmography": filmography or [], "lib_film_count": lib_film_count,
    })
    return "\n".join(_cast_body(d, _cast_frontmatter(d))) + "\n"
