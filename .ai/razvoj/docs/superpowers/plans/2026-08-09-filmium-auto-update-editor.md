---
id: filmium-73c2feae-2026-08-09-filmium-auto-update-editor-md
type: plan
domain: filmium
namespace: global
visibility: global
tier: domain
title: FILMIUM Auto Update (Editor „Updatuj") Implementation Plan
summary: '> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
  (recommended) or superpowers:executing-plans to implement this plan t'
keywords:
- filmium
- auto
- update
- editor
- updatuj
- implementation
- docs
- superpowers
- plans
tags:
- superpowers
- plans
source_path: docs/superpowers/plans/2026-08-09-filmium-auto-update-editor.md
---

# FILMIUM Auto Update (Editor „Updatuj") Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Zameniti editor dugme „Dopuni preko TMDB" dugmetom „Updatuj" koje serverski dopuni jedan naslov iz TMDB-a, sredi domaći naslov i opis na srpsku latinicu (transliteracija ili prevod), popuni ključne reči i snimi sve u bazu; preimenovati „Mood tagovi" u „Ključne reči" vezane na bazu.

**Architecture:** Deljena serverska funkcija `auto_update_item` (jezgro) poziva se iz novog endpointa `POST /media/{id}/auto-update`. Koristi postojeći `tmdb_client` (prošireni matching), `TranslatorService` (novi `translate_pair`) i novi `transliteration` modul. Frontend dugme zove endpoint i osveži katalog.

**Tech Stack:** Python 3.14, FastAPI, SQLite; pytest (bez mreže, mock provajderi). Frontend React + TypeScript, Vitest.

## Global Constraints

- Komentari i UI tekst na srpskom (latinica), u stilu postojećeg koda (`# ====` sekcije).
- Bez mreže u testovima: TMDB `_request` i prevodilac se mock-uju/injektuju.
- Prevod na `sr` vraća ćirilicu → uvek propustiti kroz `cyrillic_to_latin` da izlaz bude latinica.
- Fill-empty: postojeća neprazna polja se ne gaze (osim ćirilica→latinica na opisu/naslovu).
- **Git nije inicijalizovan** u repou. Pre početka pokreni `git init` (jednom), ili preskoči „Commit" korake. Commit poruke ostaju u planu radi urednosti.
- Test komanda: `python -m pytest tests/<fajl> -v` (config: `testpaths=["tests"]`, `--basetemp=.pytest_tmp`).

---

### Task 1: Transliteracija ćirilica → latinica

**Files:**
- Create: `core/domains/filmium/transliteration.py`
- Test: `tests/test_filmium_transliteration.py`

**Interfaces:**
- Produces: `is_cyrillic(text: str) -> bool`, `cyrillic_to_latin(text: str) -> str`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_filmium_transliteration.py
from core.domains.filmium.transliteration import is_cyrillic, cyrillic_to_latin


def test_is_cyrillic():
    assert is_cyrillic("Џон Вик") is True
    assert is_cyrillic("John Wick") is False
    assert is_cyrillic("") is False


def test_basic_letters():
    assert cyrillic_to_latin("Ана воли море") == "Ana voli more"


def test_digraphs():
    assert cyrillic_to_latin("Џон Његош Љубав") == "Džon Njegoš Ljubav"
    assert cyrillic_to_latin("ђак жаба чачак ћирилица шума") \
        == "đak žaba čačak ćirilica šuma"


def test_uppercase_digraph_before_upper():
    # ЊЕ (oba velika) → NJE; Ње → Nje
    assert cyrillic_to_latin("ЊЕГА") == "NJEGA"
    assert cyrillic_to_latin("Ње") == "Nje"


def test_latin_passthrough():
    assert cyrillic_to_latin("John Wick 2014") == "John Wick 2014"
    assert cyrillic_to_latin("") == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_filmium_transliteration.py -v`
Expected: FAIL (ModuleNotFoundError / import error).

- [ ] **Step 3: Write minimal implementation**

```python
# core/domains/filmium/transliteration.py
# ==========          TRANSLITERACIJA ĆIRILICA → LATINICA          ==========
"""Deterministička srpska transliteracija, bez mreže."""

_MAP = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "ђ": "đ", "е": "e",
    "ж": "ž", "з": "z", "и": "i", "ј": "j", "к": "k", "л": "l", "љ": "lj",
    "м": "m", "н": "n", "њ": "nj", "о": "o", "п": "p", "р": "r", "с": "s",
    "т": "t", "ћ": "ć", "у": "u", "ф": "f", "х": "h", "ц": "c", "ч": "č",
    "џ": "dž", "ш": "š",
}


def is_cyrillic(text: str) -> bool:
    """Tačno ako tekst sadrži bar jedan ćirilični znak (U+0400–U+04FF)."""
    return any("Ѐ" <= ch <= "ӿ" for ch in text or "")


def cyrillic_to_latin(text: str) -> str:
    """Pretvara srpsku ćirilicu u latinicu, uz pravilne digrafe i velika slova."""
    if not text:
        return text

    result: list[str] = []
    for index, ch in enumerate(text):
        lower = ch.lower()
        latin = _MAP.get(lower)
        if latin is None:
            result.append(ch)
            continue
        if ch.isupper():
            # Digraf: drugo slovo veliko samo ako je sledeći znak takođe veliko.
            if len(latin) > 1:
                nxt = text[index + 1] if index + 1 < len(text) else ""
                latin = latin.upper() if nxt.isupper() else latin.capitalize()
            else:
                latin = latin.upper()
        result.append(latin)
    return "".join(result)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_filmium_transliteration.py -v`
Expected: PASS (5 prošlo).

- [ ] **Step 5: Commit**

```bash
git add core/domains/filmium/transliteration.py tests/test_filmium_transliteration.py
git commit -m "feat(filmium): dodaj ćirilica→latinica transliteraciju"
```

---

### Task 2: Prevodilac — naslov+opis u jednom pozivu

**Files:**
- Modify: `integrations/translator/service.py`
- Test: `tests/test_translator_pair.py`

**Interfaces:**
- Consumes: `TranslatorService` (postojeći, sa injektabilnim provajderom).
- Produces: `TranslatorService.translate_pair(title: str, overview: str, *, target: str = "sr") -> tuple[str, str]`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_translator_pair.py
from integrations.translator.base import TranslatorProvider
from integrations.translator.rate_limiter import RateLimiter
from integrations.translator.service import TranslatorService


class JoinProvider(TranslatorProvider):
    """Lažni prevodilac: dodaje prefiks, čuva strukturu (delimiter ostaje)."""
    def __init__(self):
        self.calls = 0

    def translate(self, text, source, target):
        self.calls += 1
        return "\n".join(f"[{target}] {line}" for line in text.split("\n"))


def _service(provider):
    return TranslatorService(
        provider=provider,
        rate_limiter=RateLimiter(min_interval=0.0, max_retries=0,
                                 sleep=lambda _s: None),
    )


def test_translate_pair_jedan_poziv():
    provider = JoinProvider()
    title, overview = _service(provider).translate_pair("Ballerina", "A killer.")
    assert provider.calls == 1
    assert title == "[sr] Ballerina"
    assert overview == "[sr] A killer."


def test_translate_pair_prazan_opis():
    provider = JoinProvider()
    title, overview = _service(provider).translate_pair("Ballerina", "")
    assert title == "[sr] Ballerina"
    assert overview == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_translator_pair.py -v`
Expected: FAIL (`AttributeError: translate_pair`). Ako `RateLimiter` ne prima `sleep`, proveri postojeći potpis i uskladi test sa njim (pogledaj `tests/test_translator.py`).

- [ ] **Step 3: Write minimal implementation**

Dodaj metodu u `TranslatorService` (posle `translate_batch`):

```python
    # ==========          NASLOV + OPIS (JEDAN POZIV)          ==========

    _PAIR_DELIM = "\n⟐⟐⟐\n"

    def translate_pair(
        self,
        title: str,
        overview: str,
        *,
        target: str | None = None,
    ) -> tuple[str, str]:
        """Prevede naslov i opis jednim pozivom. Prazni delovi ostaju prazni."""
        target = target or "sr"
        if not (title or "").strip() and not (overview or "").strip():
            return title, overview

        joined = f"{title}{self._PAIR_DELIM}{overview}"
        translated = self.translate(joined, target=target)
        parts = translated.split(self._PAIR_DELIM.strip())
        if len(parts) == 2:
            return parts[0].strip(), parts[1].strip()

        # Fallback: dva odvojena poziva ako split ne uspe.
        new_title = self.translate(title, target=target) if title.strip() else title
        new_overview = (
            self.translate(overview, target=target) if overview.strip() else overview
        )
        return new_title, new_overview
```

Napomena: `self.translate(...)` već postoji i prima `target`. Ako `_PAIR_DELIM.strip()` ukloni novi red i to pokvari split, koristi ceo `self._PAIR_DELIM` u `split`. Uskladi sa ponašanjem lažnog provajdera u testu (JoinProvider čuva `\n`).

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_translator_pair.py -v`
Expected: PASS (2 prošlo).

- [ ] **Step 5: Commit**

```bash
git add integrations/translator/service.py tests/test_translator_pair.py
git commit -m "feat(translator): translate_pair za naslov+opis u jednom pozivu"
```

---

### Task 3: Varijante naziva (čisti helperi za matching)

**Files:**
- Modify: `core/domains/filmium/tmdb_client.py` (dodaj čiste helpere na kraj)
- Test: `tests/test_tmdb_title_variants.py`

**Interfaces:**
- Produces: `strip_trailing_ordinal(title: str) -> str`, `strip_franchise_prefix(title: str) -> str`, `title_variants(title: str) -> tuple[str, ...]`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tmdb_title_variants.py
from core.domains.filmium.tmdb_client import (
    strip_trailing_ordinal,
    strip_franchise_prefix,
    title_variants,
)


def test_strip_trailing_ordinal():
    assert strip_trailing_ordinal("John Wick 5") == "John Wick"
    assert strip_trailing_ordinal("John Wick") == "John Wick"
    assert strip_trailing_ordinal("Ocean's 11") == "Ocean's 11"[:len("Ocean's 11")]  # ostaje


def test_strip_franchise_prefix():
    assert strip_franchise_prefix("John Wict 5 - Balerina") == "Balerina"
    assert strip_franchise_prefix("John Wick") == "John Wick"


def test_title_variants_ordered_unique():
    v = title_variants("John Wict 5 - Balerina")
    assert v[0] == "John Wict 5 - Balerina"
    assert "Balerina" in v
    assert "John Wict 5" in v or "John Wict" in v
    assert len(v) == len(set(v))
```

Napomena: „Ocean's 11" pokazuje da uklanjamo redni broj samo kad je razdvojen razmakom na kraju i naziv pre njega nije prazan; „11" ostaje ako je jedini token. Prilagodi regex tako da `"John Wick 5" → "John Wick"` ali `"11" → "11"`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_tmdb_title_variants.py -v`
Expected: FAIL (import error).

- [ ] **Step 3: Write minimal implementation**

```python
# na kraj tmdb_client.py
import re as _re

_ORDINAL_RE = _re.compile(r"^(?P<base>.+\S)\s+\d{1,3}$")
_PREFIX_RE = _re.compile(r"^.+?\s+\d{1,3}\s+-\s+(?P<rest>.+)$")


def strip_trailing_ordinal(title: str) -> str:
    """„John Wick 5" → „John Wick"; ostavlja naziv ako je broj jedini token."""
    match = _ORDINAL_RE.match((title or "").strip())
    return match.group("base") if match else (title or "").strip()


def strip_franchise_prefix(title: str) -> str:
    """„John Wict 5 - Balerina" → „Balerina"; inače vraća original."""
    match = _PREFIX_RE.match((title or "").strip())
    return match.group("rest").strip() if match else (title or "").strip()


def title_variants(title: str) -> tuple[str, ...]:
    """Redosled pokušaja naziva; bez duplikata, čuva prvi (originalni)."""
    base = (title or "").strip()
    candidates = [
        base,
        strip_trailing_ordinal(base),
        strip_franchise_prefix(base),
        strip_trailing_ordinal(strip_franchise_prefix(base)),
    ]
    seen: dict[str, None] = {}
    for cand in candidates:
        if cand and cand not in seen:
            seen[cand] = None
    return tuple(seen)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_tmdb_title_variants.py -v`
Expected: PASS (3 prošlo). Ako `title_variants` red ne odgovara asertima, prilagodi test ili redosled (originalni uvek `v[0]`).

- [ ] **Step 5: Commit**

```bash
git add core/domains/filmium/tmdb_client.py tests/test_tmdb_title_variants.py
git commit -m "feat(tmdb): helperi za varijante naziva (redni broj, franšiza)"
```

---

### Task 4: `enrich_best` — robusni matching (varijante + kolekcija + ID)

**Files:**
- Modify: `core/domains/filmium/tmdb_client.py`
- Test: `tests/test_tmdb_enrich_best.py`

**Interfaces:**
- Consumes: `enrich_movie(title, year)`, `enrich_series(title, year)` (postojeći), `title_variants` (Task 3), `Enrichment` dataklasa (postojeća, polja uklj. `year`, `collection`, `tmdb_id`).
- Produces: `enrich_best(query_title: str, year: int | None, media_type: str, *, tmdb_id: int | None = None, override_title: str | None = None, collection_hint: str | None = None) -> Enrichment | None`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tmdb_enrich_best.py
from core.domains.filmium import tmdb_client as t


def test_enrich_best_prva_varijanta(monkeypatch):
    calls = []

    def fake_enrich_movie(title, year):
        calls.append((title, year))
        return t.Enrichment(tmdb_id=1, original_title=title, english_title=title,
                            english_overview=None, local_title=None,
                            local_overview=None, year=year, genres=(), rating=None,
                            cast_names=(), studio=None, director=None,
                            vote_count=None) if title == "Ballerina" else None

    monkeypatch.setattr(t, "enrich_movie", fake_enrich_movie)
    out = t.enrich_best("John Wict 5 - Balerina", 2026, "movie")
    assert out is not None
    assert out.original_title == "Ballerina"
    # dokaz da je probao varijante dok nije pogodio „Balerina"/„Ballerina"
    assert ("Ballerina", 2026) in calls or ("Ballerina", None) in calls \
        or ("Balerina", 2026) in calls


def test_enrich_best_bez_pogotka(monkeypatch):
    monkeypatch.setattr(t, "enrich_movie", lambda *_: None)
    assert t.enrich_best("Nepostojece", 1999, "movie") is None
```

Napomena: `Enrichment` konstruktor koristi tačna imena polja iz `tmdb_client.py` — proveri postojeću dataklasu i uskladi kwargs (neka polja imaju default). Test „Balerina" pokazuje da kod probava i varijante naziva; ako TMDB ne mapira „Balerina"→„Ballerina", to je zadatak kolekcije/override (van ovog čistog testa).

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_tmdb_enrich_best.py -v`
Expected: FAIL (`AttributeError: enrich_best`).

- [ ] **Step 3: Write minimal implementation**

```python
# tmdb_client.py — dodaj enrich_best i by-id + kolekciju
def _enrich_by_title(title, year, media_type):
    return (enrich_series(title, year) if media_type == "series"
            else enrich_movie(title, year))


def enrich_best(
    query_title,
    year,
    media_type,
    *,
    tmdb_id=None,
    override_title=None,
    collection_hint=None,
):
    """Pronalazi najbolji TMDB pogodak kroz varijante naziva; None ako nema."""
    if tmdb_id is not None:
        by_id = enrich_by_id(tmdb_id, media_type)
        if by_id is not None:
            return by_id

    primary = (override_title or query_title or "").strip()
    for variant in title_variants(primary):
        for yr in (year, None):
            hit = _enrich_by_title(variant, yr, media_type)
            if hit is not None:
                return hit

    # Franšiza/kolekcija: pronađi pravi (moguće preimenovan) nastavak po godini.
    hit = _enrich_via_collection(primary, year, media_type, collection_hint)
    if hit is not None:
        return hit
    return None
```

Dodaj i:

```python
def enrich_by_id(tmdb_id, media_type):
    """Enrich direktno po TMDB ID-u (movie/tv) + credits/keywords/collection."""
    endpoint = f"tv/{tmdb_id}" if media_type == "series" else f"movie/{tmdb_id}"
    data = _request(endpoint, {"append_to_response": "credits,keywords"})
    if not data:
        return None
    return _enrichment_from_details(data, media_type)  # vidi napomenu


def _enrich_via_collection(title, year, media_type, collection_hint):
    """Best-effort: nađi kolekciju, izaberi deo po godini (ili N-tom mestu)."""
    if media_type != "movie":
        return None
    base = strip_trailing_ordinal(title)
    # 1) probaj po hintu ili preko belongs_to_collection baznog pogotka
    seed = _enrich_by_title(base, None, "movie")
    collection_id = _lookup_collection_id(collection_hint) \
        or getattr(seed, "collection_id", None)
    if collection_id is None:
        return None
    parts = _collection_parts(collection_id)  # [(tmdb_id, release_year), ...]
    if not parts:
        return None
    parts.sort(key=lambda p: (p[1] or 0))
    chosen = None
    if year is not None:
        chosen = min(parts, key=lambda p: abs((p[1] or 0) - year))
    else:
        ordinal = _trailing_ordinal_number(title)
        if ordinal and ordinal <= len(parts):
            chosen = parts[ordinal - 1]
    if chosen is None:
        return None
    return enrich_by_id(chosen[0], "movie")
```

**Napomena za implementatora (obavezno pre pisanja):** pročitaj postojeći
`tmdb_client.py` u celini. `_enrichment_from_details`, `_lookup_collection_id`,
`_collection_parts`, `_trailing_ordinal_number` i `collection_id` na
`Enrichment` verovatno NE postoje — dodaj minimalne verzije koristeći postojeći
`_request` i postojeće parsere (`_parse_keywords`, `_parse_collection`,
`_parse_cast`). Ako je refaktor postojeće `enrich_movie` da izloži
`_enrichment_from_details` prevelik za ovaj task, ograniči `enrich_best` na
varijante naziva + `enrich_by_id`, a kolekciju uradi u zasebnom sledećem tasku.
YAGNI: ne dodaji polja koja test ne traži.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_tmdb_enrich_best.py -v`
Expected: PASS (2 prošlo).

- [ ] **Step 5: Commit**

```bash
git add core/domains/filmium/tmdb_client.py tests/test_tmdb_enrich_best.py
git commit -m "feat(tmdb): enrich_best (varijante + kolekcija + ID)"
```

---

### Task 5: Pipeline `auto_update_item`

**Files:**
- Create: `core/domains/filmium/auto_update_service.py`
- Test: `tests/test_filmium_auto_update.py`

**Interfaces:**
- Consumes: `FilmiumService` (`get_media_item`, `update_media_item`, `update_keywords`), `tmdb_client.enrich_best`, `TranslatorService.translate_pair`, `transliteration.{is_cyrillic,cyrillic_to_latin}`.
- Produces: `auto_update_item(item_id: int, service, translator, *, tmdb_id=None, override_title=None) -> AutoUpdateResult` gde je `AutoUpdateResult` dataklasa `{matched: bool, changed_fields: tuple[str,...], message: str}`. TMDB klijent i njegove funkcije se pozivaju kroz modul `tmdb_client` (monkeypatch u testu).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_filmium_auto_update.py
from core.domains.filmium import auto_update_service as aus
from core.domains.filmium import tmdb_client as t


class FakeItem:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class FakeService:
    def __init__(self, item):
        self._item = item
        self.saved = None
        self.saved_keywords = None

    def get_media_item(self, _id):
        return self._item

    def update_media_item(self, _id, payload):
        self.saved = payload
        return self._item

    def update_keywords(self, _id, keywords):
        self.saved_keywords = tuple(keywords)
        return self._item


class FakeTranslator:
    def translate_pair(self, title, overview, *, target="sr"):
        return (f"СРБ {title}", f"СРБ {overview}")  # ćirilica namerno


def _enr(**kw):
    base = dict(tmdb_id=1, original_title="John Wick", english_title="John Wick",
                english_overview="A hitman.", local_title=None, local_overview=None,
                year=2014, genres=("Action",), rating=7.4, cast_names=("Keanu",),
                studio="87Eleven", director="Chad", vote_count=100,
                keywords=("hitman", "dog"), collection="John Wick Collection")
    base.update(kw)
    return t.Enrichment(**base)


def test_prazan_opis_prevod_i_latinica(monkeypatch):
    item = FakeItem(id=1, title="John Wick", original_title="John Wick",
                    media_type=_MT("movie"), release_year=2014, notes=None,
                    english_description=None, genres=(), cast_names=(),
                    studio=None, director=None, keywords=(), rating=None,
                    watch_status=_WS(), is_favorite=False, content_category="regular",
                    is_synchronized=False, editor_settings={}, english_title=None,
                    runtime_minutes=None)
    monkeypatch.setattr(t, "enrich_best", lambda *a, **k: _enr())
    svc = FakeService(item)
    res = aus.auto_update_item(1, svc, FakeTranslator())
    assert res.matched is True
    # opis preveden pa transliterisan u latinicu (nema ćirilice)
    from core.domains.filmium.transliteration import is_cyrillic
    assert svc.saved.notes and not is_cyrillic(svc.saved.notes)
    assert "hitman" in svc.saved.keywords


def test_ciriličan_opis_se_transliteruje(monkeypatch):
    item = FakeItem(id=1, title="John Wick", original_title="John Wick",
                    media_type=_MT("movie"), release_year=2014,
                    notes="Џон Вик убија", english_description=None, genres=(),
                    cast_names=(), studio=None, director=None, keywords=(),
                    rating=None, watch_status=_WS(), is_favorite=False,
                    content_category="regular", is_synchronized=False,
                    editor_settings={}, english_title=None, runtime_minutes=None)
    monkeypatch.setattr(t, "enrich_best", lambda *a, **k: _enr(local_overview=None))
    svc = FakeService(item)
    aus.auto_update_item(1, svc, FakeTranslator())
    assert svc.saved.notes == "Džon Vik ubija"


def test_bez_pogotka_ne_menja(monkeypatch):
    item = FakeItem(id=1, title="X", original_title=None, media_type=_MT("movie"),
                    release_year=None, notes=None, english_description=None,
                    genres=(), cast_names=(), studio=None, director=None,
                    keywords=(), rating=None, watch_status=_WS(), is_favorite=False,
                    content_category="regular", is_synchronized=False,
                    editor_settings={}, english_title=None, runtime_minutes=None)
    monkeypatch.setattr(t, "enrich_best", lambda *a, **k: None)
    svc = FakeService(item)
    res = aus.auto_update_item(1, svc, FakeTranslator())
    assert res.matched is False
    assert svc.saved is None
```

**Napomena:** `_MT`/`_WS` su pomoćnici koji vraćaju objekte sa `.value`
(MediaType/WatchStatus) — implementiraj ih na vrhu test fajla prema stvarnim
enumima (`from core.domains.filmium.models import MediaType, WatchStatus`).
Uskladi polja `FakeItem` i payload sa `MediaItemCreate`/`update_media_item`
potpisom (pročitaj `service.py` i `repository.update`).

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_filmium_auto_update.py -v`
Expected: FAIL (modul ne postoji).

- [ ] **Step 3: Write minimal implementation**

```python
# core/domains/filmium/auto_update_service.py
# ==========          AUTO UPDATE — PIPELINE JEDNOG NASLOVA          ==========
"""TMDB dopuna + srpska latinica (transliteracija/prevod) + ključne reči,
pa snimanje u bazu. Bez UI-ja; deljeno između editora i bulk cron-a."""

from dataclasses import dataclass

from core.domains.filmium import tmdb_client
from core.domains.filmium.transliteration import cyrillic_to_latin, is_cyrillic


@dataclass(frozen=True)
class AutoUpdateResult:
    matched: bool
    changed_fields: tuple[str, ...]
    message: str


def _to_latin(text):
    if not text:
        return text
    return cyrillic_to_latin(text) if is_cyrillic(text) else text


def auto_update_item(item_id, service, translator, *, tmdb_id=None,
                     override_title=None):
    """Dopuni jedan naslov i snimi. Vraća AutoUpdateResult."""
    item = service.get_media_item(item_id)
    media_type = item.media_type.value
    query = (item.original_title or item.title or "").strip()

    enr = tmdb_client.enrich_best(query, item.release_year, media_type,
                                  tmdb_id=tmdb_id, override_title=override_title,
                                  collection_hint=getattr(item, "collection", None))
    if enr is None:
        return AutoUpdateResult(False, (), "TMDB nije pronašao ovaj naslov.")

    changed: list[str] = []

    def fill(attr, value):
        if value is not None and str(value).strip() != "" \
                and not (getattr(item, attr, None) or ""):
            setattr(item, attr, value)
            changed.append(attr)

    fill("original_title", enr.original_title)
    fill("english_title", enr.english_title)
    fill("english_description", enr.english_overview)
    fill("studio", enr.studio)
    fill("director", enr.director)
    if not item.release_year and enr.year:
        item.release_year = enr.year
        changed.append("release_year")

    genres = tuple(dict.fromkeys((*item.genres, *enr.genres)))
    cast = tuple(dict.fromkeys((*(item.cast_names or ()), *enr.cast_names)))
    keywords = tuple(dict.fromkeys((*(item.keywords or ()), *enr.keywords)))

    # Domaći naslov: TMDB lokalni (latinica) ili prevod EN naslova.
    local_title = _to_latin(enr.local_title) if enr.local_title else None
    # Opis: postojeći ćirilični → latinica; prazan → lokalni ili prevod EN.
    notes = item.notes
    if notes:
        notes = _to_latin(notes)
    elif enr.local_overview:
        notes = _to_latin(enr.local_overview)
        if not local_title and enr.local_title:
            local_title = _to_latin(enr.local_title)
    elif enr.english_overview or enr.english_title:
        tr_title, tr_overview = translator.translate_pair(
            enr.english_title or enr.original_title or "",
            enr.english_overview or "",
        )
        notes = _to_latin(tr_overview) or None
        if not local_title:
            local_title = _to_latin(tr_title) or None

    if notes and notes != item.notes:
        item.notes = notes
        changed.append("notes")

    # Domaći naslov ide u editor_settings.basic.local_title_sr.
    settings = dict(getattr(item, "editor_settings", None) or {})
    basic = dict(settings.get("basic") or {})
    if local_title and not basic.get("local_title_sr"):
        basic["local_title_sr"] = local_title
        settings["basic"] = basic
        item.editor_settings = settings
        changed.append("local_title_sr")

    payload = _build_payload(item, genres=genres, cast=cast, keywords=keywords,
                             rating_hint=enr.rating)
    service.update_media_item(item_id, payload)
    return AutoUpdateResult(True, tuple(changed), "Ažurirano i snimljeno.")
```

Dodaj `_build_payload` koji sklapa `MediaItemCreate` (ili dict koji
`update_media_item` očekuje) iz `item` + spojenih polja. **Pročitaj
`service.update_media_item` i `MediaItemCreate` pre pisanja** i uskladi imena
polja tačno (uklj. `content_category`, `is_favorite`, `is_synchronized`,
`watch_status`, `english_description`, `collection`).

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_filmium_auto_update.py -v`
Expected: PASS (3 prošlo).

- [ ] **Step 5: Commit**

```bash
git add core/domains/filmium/auto_update_service.py tests/test_filmium_auto_update.py
git commit -m "feat(filmium): auto_update_item pipeline (TMDB+latinica+keywords+snimanje)"
```

---

### Task 6: API endpoint `POST /media/{id}/auto-update`

**Files:**
- Modify: `apps/api/routers/filmium.py`
- Modify: `apps/api/schemas/filmium.py` (dodaj `AutoUpdateRequest`, `AutoUpdateResponse`)
- Test: `tests/test_api_auto_update.py`

**Interfaces:**
- Consumes: `auto_update_service.auto_update_item`, `FilmiumServiceDependency`, `TranslatorService`, `MediaItemResponse.from_domain`.
- Produces: HTTP `POST /api/v1/filmium/media/{item_id}/auto-update` body `{tmdb_id?: int|null, override_title?: str|null}` → `{matched, changed_fields, message, item}`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_api_auto_update.py
from fastapi.testclient import TestClient
from apps.api.main import app
from core.domains.filmium import auto_update_service as aus

client = TestClient(app)


def test_auto_update_endpoint(monkeypatch):
    def fake(item_id, service, translator, *, tmdb_id=None, override_title=None):
        return aus.AutoUpdateResult(True, ("notes",), "ok")
    monkeypatch.setattr(aus, "auto_update_item", fake)
    # koristi postojeći id iz baze (npr. 1154) ili mock servisa po uzoru na
    # tests/test_filmium.py; ovde proveravamo samo oblik odgovora i status.
    resp = client.post("/api/v1/filmium/media/1154/auto-update", json={})
    assert resp.status_code == 200
    body = resp.json()
    assert body["matched"] is True
    assert "item" in body
```

**Napomena:** pogledaj `tests/test_filmium.py` kako se rukuje bazom/DI u API
testovima (verovatno postoji fixture ili se koristi realna `core.db`). Uskladi
setup (dependency override) sa postojećim obrascem umesto tvrdog id-a ako je
tako urađeno drugde.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_api_auto_update.py -v`
Expected: FAIL (404 — ruta ne postoji).

- [ ] **Step 3: Write minimal implementation**

Schema (`apps/api/schemas/filmium.py`):

```python
class AutoUpdateRequest(BaseModel):
    tmdb_id: int | None = None
    override_title: str | None = Field(default=None, max_length=300)


class AutoUpdateResponse(BaseModel):
    matched: bool
    changed_fields: tuple[str, ...] = ()
    message: str
    item: MediaItemResponse
```

Ruter (`apps/api/routers/filmium.py`, pored `enrich_media_from_tmdb`):

```python
@router.post("/media/{item_id}/auto-update", response_model=AutoUpdateResponse)
def auto_update_media(
    item_id: int,
    service: FilmiumServiceDependency,
    request: AutoUpdateRequest | None = None,
) -> AutoUpdateResponse:
    """Kompletno dopuni jedan naslov iz TMDB-a i snimi u bazu."""
    from core.domains.filmium.auto_update_service import auto_update_item
    from integrations.translator.service import TranslatorService

    req = request or AutoUpdateRequest()
    try:
        result = auto_update_item(
            item_id, service, TranslatorService(),
            tmdb_id=req.tmdb_id, override_title=req.override_title,
        )
    except MediaItemNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=str(error)) from error
    item = service.get_media_item(item_id)
    return AutoUpdateResponse(
        matched=result.matched, changed_fields=result.changed_fields,
        message=result.message, item=MediaItemResponse.from_domain(item),
    )
```

Dodaj `AutoUpdateRequest, AutoUpdateResponse` u import iz schema na vrhu rutera.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_api_auto_update.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/routers/filmium.py apps/api/schemas/filmium.py tests/test_api_auto_update.py
git commit -m "feat(api): POST /media/{id}/auto-update"
```

---

### Task 7: Frontend — dugme „Updatuj" (poziv + reload)

**Files:**
- Modify: `apps/gui/src/services/filmiumMediaSourceApi.ts` (dodaj poziv + tip)
- Modify: `apps/gui/src/features/filmium/components/details/FilmiumEditorPanel.tsx`
- Test: `apps/gui/src/features/filmium/components/details/FilmiumEditorPanel.autoupdate.test.tsx` (ili dopuni postojeći test ako postoji)

**Interfaces:**
- Consumes: `POST /media/{id}/auto-update` (Task 6).
- Produces: `autoUpdateFilmiumMedia(id: number, body?: {tmdb_id?: number; override_title?: string}): Promise<AutoUpdateResponse>`; dugme header-a „Updatuj".

- [ ] **Step 1: Write the failing test**

```tsx
// FilmiumEditorPanel.autoupdate.test.tsx
import { render, screen } from "@testing-library/react";
import FilmiumEditorPanel from "./FilmiumEditorPanel";
// mock-uj servise po uzoru na postojeće editor testove (vi.mock)

test("header prikazuje dugme Updatuj", () => {
  // render sa minimalnim item/sources/seasons props (vidi postojeće testove)
  // ...
  expect(screen.getByRole("button", { name: /Updatuj/i })).toBeInTheDocument();
});
```

**Napomena:** pogledaj postojeće `FilmiumMediaForm.test.tsx` /
`FilmiumToolbar.test.tsx` za obrazac renderovanja i mock-a servisa; napravi
minimalne validne `MediaItem` props.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/gui && npx vitest run FilmiumEditorPanel.autoupdate.test.tsx`
Expected: FAIL (dugme se zove „Dopuni preko TMDB").

- [ ] **Step 3: Write minimal implementation**

U `filmiumMediaSourceApi.ts` dodaj:

```ts
export interface AutoUpdateResponse {
  matched: boolean;
  changed_fields: string[];
  message: string;
  item: MediaItem;
}

export function autoUpdateFilmiumMedia(
  mediaId: number,
  body: { tmdb_id?: number; override_title?: string } = {},
): Promise<AutoUpdateResponse> {
  return postRequest<AutoUpdateResponse>(
    `/api/v1/filmium/media/${mediaId}/auto-update`,
    body,
  );
}
```

U `FilmiumEditorPanel.tsx` header dugme — zameni tekst i akciju:

```tsx
<button className="filmium-editor-button tmdb" disabled={isEnriching}
        onClick={() => void runAutoUpdate()} type="button">
  <Sparkles size={16} />
  {isEnriching ? "Ažuriram…" : "Updatuj"}
</button>
```

I `runAutoUpdate` (zameni/uz `runTmdbEnrich`):

```tsx
async function runAutoUpdate(): Promise<void> {
  if (isEnriching) return;
  setIsEnriching(true);
  setEnrichMessage(null);
  try {
    const res = await autoUpdateFilmiumMedia(item.id, overrideTmdb);
    setEnrichMessage(res.matched ? res.message
      : "TMDB nije pronašao — unesi TMDB naziv ili ID ispod.");
    onSaved?.();               // osveži katalog → item se ponovo učita
  } catch (error) {
    setEnrichMessage(error instanceof Error ? error.message : "Ažuriranje nije uspelo.");
  } finally {
    setIsEnriching(false);
  }
}
```

Gde je `overrideTmdb` opciono stanje (`{}` po defaultu; polje se prikazuje kad
`matched=false`). Uvezi `autoUpdateFilmiumMedia`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/gui && npx vitest run FilmiumEditorPanel.autoupdate.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/gui/src/services/filmiumMediaSourceApi.ts apps/gui/src/features/filmium/components/details/FilmiumEditorPanel.tsx apps/gui/src/features/filmium/components/details/FilmiumEditorPanel.autoupdate.test.tsx
git commit -m "feat(gui): Updatuj dugme zove auto-update i osvezi katalog"
```

---

### Task 8: Frontend — „Mood tagovi" → „Ključne reči" (iz baze)

**Files:**
- Modify: `apps/gui/src/features/filmium/components/details/FilmiumEditorPanel.tsx`
- Test: dopuni `FilmiumEditorPanel.autoupdate.test.tsx` novim testom

**Interfaces:**
- Consumes: `item.keywords` (postojeće polje `MediaItem`), `updateFilmiumMediaKeywords` (postojeći) ili keywords endpoint.
- Produces: sekcija „Ključne reči" vezana na bazu umesto mock „Mood tagovi".

- [ ] **Step 1: Write the failing test**

```tsx
test("prikazuje 'Ključne reči' sa vrednostima iz item.keywords", () => {
  // render editor sa item.keywords = ["hitman", "dog"]
  expect(screen.getByText("Ključne reči")).toBeInTheDocument();
  expect(screen.getByText("hitman")).toBeInTheDocument();
  expect(screen.queryByText("Mood tagovi")).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/gui && npx vitest run FilmiumEditorPanel.autoupdate.test.tsx`
Expected: FAIL (label „Mood tagovi", state prazan).

- [ ] **Step 3: Write minimal implementation**

U `FilmiumEditorPanel.tsx`:
- Inicijalizuj stanje iz baze: `const [keywords, setKeywords] = useState<string[]>(Array.from(item.keywords ?? []));`
- Zameni `<Field label="Mood tagovi">` sa `<Field label="Ključne reči">` i
  `<TagList values={keywords} onChange={setKeywords} />`.
- Ukloni stari `moodTags` state.
- U `persistChanges` (postojeći „Sačuvaj") uključi `keywords` u payload
  (`updateFilmiumMediaItem` već šalje ceo zapis; dodaj `keywords` polje u
  `MediaItemCreateRequest` payload — proveri da tip to podržava, inače snimaj
  preko `updateFilmiumMediaKeywords`).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/gui && npx vitest run FilmiumEditorPanel.autoupdate.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/gui/src/features/filmium/components/details/FilmiumEditorPanel.tsx apps/gui/src/features/filmium/components/details/FilmiumEditorPanel.autoupdate.test.tsx
git commit -m "feat(gui): 'Kljucne reci' iz baze umesto 'Mood tagovi'"
```

---

## Sledeća faza (poseban plan)

Bulk cron (`/update-filmium`), zaseban proces, resume na startu, CORE indikator
u donjem desnom uglu — spec moduli M7–M11. Napraviti
`docs/superpowers/plans/2026-08-09-filmium-auto-update-cron.md` posle Faze A.
