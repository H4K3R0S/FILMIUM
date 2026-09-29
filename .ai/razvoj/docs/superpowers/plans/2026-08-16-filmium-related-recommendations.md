---
id: filmium-2494624b-2026-08-16-filmium-related-recommendations-md
type: plan
domain: filmium
namespace: global
visibility: global
tier: domain
title: FILMIUM Related/Recommendations Implementation Plan
summary: '> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
  (recommended) or superpowers:executing-plans to implement this plan t'
keywords:
- filmium
- related
- recommendations
- implementation
- docs
- superpowers
- plans
tags:
- superpowers
- plans
source_path: docs/superpowers/plans/2026-08-16-filmium-related-recommendations.md
---

# FILMIUM Related/Recommendations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Zameniti dva reda preporuka na detalj-stranici sa tri odeljka — Povezani (TMDB recommendations), Preporučeni (naziv+žanr+ključne reči), Po žanru — sa owned/ne-owned karticama i kaskadnim dedupom.

**Architecture:** Backend čuva TMDB `recommendations` u novoj JSON koloni `related_tmdb` (migracija v30), puni je „samo unapred" kroz auto-update (Updatuj) putanju. Frontend ukršta related sa lokalnim katalogom; ne-owned kartice imaju crvenu ivicu i otvaraju „Dodaj" modal. Preporučeni/Po žanru su čiste frontend funkcije u izdvojenom, testiranom helper modulu.

**Tech Stack:** Python 3.14 + SQLite (`core_database_connection`), FastAPI/Pydantic v2, React + TypeScript + Vitest.

**Spec:** `docs/superpowers/specs/2026-08-16-filmium-related-recommendations-design.md`

## Global Constraints

- Kod, komentari, commit poruke = normalan srpski (latinica), prati postojeći stil fajla.
- Migracija: sledeća slobodna verzija je **30** (v29 je poslednja).
- Hard cap **20** related zapisa pri parsiranju; UI prikaz **10** po odeljku.
- Ne-owned poster baza: `https://image.tmdb.org/t/p/w500`.
- Kaskadni dedup: Povezani → Preporučeni → Po žanru.
- Poštuj kategoriju: `domestic`/`animated` preporuke samo iz iste kategorije; `regular` bez ograničenja.

---

### Task 1: Domenski model `RelatedTitle` + polje `related_tmdb`

**Files:**
- Modify: `core/domains/filmium/models.py`
- Test: `tests/test_filmium.py`

**Interfaces:**
- Produces: `RelatedTitle(tmdb_id: int, title: str, year: int | None, poster_path: str | None, media_type: MediaType)`; `MediaItem.related_tmdb: tuple[RelatedTitle, ...] = ()`; `MediaItemCreate.related_tmdb: tuple[RelatedTitle, ...] = ()`.

- [ ] **Step 1: Write the failing test**

```python
def test_related_title_defaults_and_media_item_field():
    from core.domains.filmium.models import MediaType, RelatedTitle

    related = RelatedTitle(
        tmdb_id=27205,
        title="Inception",
        year=2010,
        poster_path="/abc.jpg",
        media_type=MediaType.MOVIE,
    )
    assert related.tmdb_id == 27205
    assert related.media_type is MediaType.MOVIE
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_filmium.py::test_related_title_defaults_and_media_item_field -v`
Expected: FAIL — `ImportError: cannot import name 'RelatedTitle'`

- [ ] **Step 3: Write minimal implementation**

U `models.py`, uz ostale `@dataclass(frozen=True)`:

```python
@dataclass(frozen=True)
class RelatedTitle:
    """Lagani zapis TMDB povezanog naslova (recommendations)."""

    tmdb_id: int
    title: str
    year: int | None
    poster_path: str | None
    media_type: MediaType
```

Dodati polje na `MediaItem` i `MediaItemCreate` (uz `keywords`):

```python
    related_tmdb: tuple[RelatedTitle, ...] = ()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_filmium.py::test_related_title_defaults_and_media_item_field -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/domains/filmium/models.py tests/test_filmium.py
git commit -m "feat(filmium): RelatedTitle model + related_tmdb polje"
```

---

### Task 2: Migracija v30 — kolona `related_tmdb`

**Files:**
- Create: `core/domains/filmium/migration_v30.py`
- Modify: `core/domains/filmium/migrations.py`
- Test: `tests/test_filmium.py`

**Interfaces:**
- Produces: kolona `related_tmdb TEXT` na `filmium_media_items`; `FILMIUM_MIGRATION_V30` registrovan u `FILMIUM_MIGRATIONS`.

- [ ] **Step 1: Write the failing test**

```python
def test_media_items_has_related_tmdb_column(tmp_path):
    from core.database import core_database_connection, run_core_migrations

    db = tmp_path / "core.sqlite3"
    run_core_migrations(db)
    with core_database_connection(db) as connection:
        cols = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(filmium_media_items)"
            )
        }
    assert "related_tmdb" in cols
```

(Ako helper za migracije ima drugo ime, uskladi sa postojećim testom migracija u `tests/test_filmium.py`.)

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_filmium.py::test_media_items_has_related_tmdb_column -v`
Expected: FAIL — kolona ne postoji.

- [ ] **Step 3: Write minimal implementation**

`migration_v30.py`:

```python
from core.database import DatabaseMigration


# ==========          TMDB RELATED NA KATALOGU          ==========
#
# Čuva TMDB „recommendations" (povezani naslovi) kao JSON tekst uz sadržaj,
# da detalj-stranica prikaže „Povezani filmovi/serije". Postojeći redovi
# ostaju NULL dok se ne dopune (uvoz/auto-update) — puni se samo unapred.

FILMIUM_MIGRATION_V30 = DatabaseMigration(
    scope="filmium",
    version=30,
    name="add_media_related_tmdb",
    statements=(
        """
        ALTER TABLE filmium_media_items
        ADD COLUMN related_tmdb TEXT
        """,
    ),
)
```

U `migrations.py`: dodati import uz ostale i ubaciti u `FILMIUM_MIGRATIONS` tuple posle `FILMIUM_MIGRATION_V29`:

```python
from core.domains.filmium.migration_v30 import (
    FILMIUM_MIGRATION_V30,
)
```
```python
    FILMIUM_MIGRATION_V29,
    FILMIUM_MIGRATION_V30,
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_filmium.py::test_media_items_has_related_tmdb_column -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/domains/filmium/migration_v30.py core/domains/filmium/migrations.py tests/test_filmium.py
git commit -m "feat(filmium): migracija v30 — related_tmdb kolona"
```

---

### Task 3: Repository — serijalizacija/parsiranje `related_tmdb` (round-trip)

**Files:**
- Modify: `core/domains/filmium/repository.py` (INSERT ~60-108, UPDATE ~155-203, `_row_to_media_item` ~577-610, helperi ~15-38)
- Test: `tests/test_filmium.py`

**Interfaces:**
- Consumes: `RelatedTitle`, `MediaItemCreate.related_tmdb` (Task 1); kolona (Task 2).
- Produces: `MediaRepository.create`/`update` upisuju `related_tmdb`; `_row_to_media_item` vraća `related_tmdb` tuple. Helperi `_serialize_related(items)` i `_parse_related(value)`.

- [ ] **Step 1: Write the failing test**

```python
def test_repository_round_trips_related_tmdb(tmp_path):
    from core.domains.filmium.models import (
        MediaItemCreate, MediaType, RelatedTitle, WatchStatus,
    )
    from core.domains.filmium.repository import MediaRepository
    from core.database import run_core_migrations

    db = tmp_path / "core.sqlite3"
    run_core_migrations(db)
    repo = MediaRepository(db)

    related = (
        RelatedTitle(1, "A", 2001, "/a.jpg", MediaType.MOVIE),
        RelatedTitle(2, "B", None, None, MediaType.MOVIE),
    )
    created = repo.create(MediaItemCreate(
        title="Film", media_type=MediaType.MOVIE,
        watch_status=WatchStatus.PLANNED, related_tmdb=related,
    ))
    loaded = repo.get(created.id)
    assert loaded.related_tmdb == related
```

(Uskladi ime `repo.get`/`get_by_id` sa postojećim u repozitorijumu.)

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_filmium.py::test_repository_round_trips_related_tmdb -v`
Expected: FAIL — `related_tmdb` je `()` (ne upisuje se/ne čita).

- [ ] **Step 3: Write minimal implementation**

Helperi uz `_parse_cast_names`:

```python
def _serialize_related(items: tuple) -> str:
    return json.dumps([
        {
            "tmdb_id": r.tmdb_id,
            "title": r.title,
            "year": r.year,
            "poster_path": r.poster_path,
            "media_type": r.media_type.value,
        }
        for r in items
    ])


def _parse_related(value: object) -> tuple:
    from core.domains.filmium.models import MediaType, RelatedTitle

    if not value:
        return ()
    try:
        data = json.loads(value)  # type: ignore[arg-type]
    except (ValueError, TypeError):
        return ()
    if not isinstance(data, list):
        return ()
    result = []
    for entry in data:
        if not isinstance(entry, dict) or "tmdb_id" not in entry:
            continue
        try:
            result.append(RelatedTitle(
                tmdb_id=int(entry["tmdb_id"]),
                title=str(entry.get("title") or ""),
                year=entry.get("year"),
                poster_path=entry.get("poster_path"),
                media_type=MediaType(entry.get("media_type", "movie")),
            ))
        except (ValueError, TypeError):
            continue
    return tuple(result)
```

INSERT: dodati `related_tmdb` u listu kolona, `?` u VALUES, i `_serialize_related(item.related_tmdb)` u tuple vrednosti.
UPDATE: dodati `related_tmdb = ?` u SET i istu vrednost u tuple (pre `item_id`).
`_row_to_media_item`: dodati `related_tmdb=_parse_related(row["related_tmdb"])`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_filmium.py::test_repository_round_trips_related_tmdb -v`
Expected: PASS. Zatim ceo fajl: `python -m pytest tests/test_filmium.py -q`

- [ ] **Step 5: Commit**

```bash
git add core/domains/filmium/repository.py tests/test_filmium.py
git commit -m "feat(filmium): repository upisuje/čita related_tmdb"
```

---

### Task 4: TMDB client — parsiranje `recommendations`

**Files:**
- Modify: `core/domains/filmium/tmdb_client.py` (enrichment dataclass ~99-116, tri fetch putanje `append_to_response` ~794/850/945, novi parser)
- Test: `tests/test_filmium.py` (ili postojeći tmdb test modul ako ga ima)

**Interfaces:**
- Consumes: `RelatedTitle`, `MediaType`.
- Produces: enrichment dataclass polje `recommendations: tuple[RelatedTitle, ...] = ()`; funkcija `_parse_recommendations(data: dict | None, fallback_type: MediaType) -> tuple[RelatedTitle, ...]` (cap 20).

- [ ] **Step 1: Write the failing test**

```python
def test_parse_recommendations_caps_and_maps():
    from core.domains.filmium.models import MediaType
    from core.domains.filmium.tmdb_client import _parse_recommendations

    data = {"recommendations": {"results": [
        {"id": 10, "title": "X", "release_date": "1999-03-31",
         "poster_path": "/x.jpg", "media_type": "movie"},
        {"id": 11, "name": "Y", "first_air_date": "2015-01-01",
         "poster_path": None, "media_type": "tv"},
    ]}}
    out = _parse_recommendations(data, MediaType.MOVIE)
    assert out[0].tmdb_id == 10 and out[0].year == 1999
    assert out[1].title == "Y" and out[1].media_type is MediaType.SERIES
    assert len(out) <= 20
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_filmium.py::test_parse_recommendations_caps_and_maps -v`
Expected: FAIL — funkcija ne postoji.

- [ ] **Step 3: Write minimal implementation**

```python
def _parse_recommendations(data, fallback_type):
    from core.domains.filmium.models import MediaType, RelatedTitle

    if not data:
        return ()
    block = data.get("recommendations")
    results = block.get("results") if isinstance(block, dict) else None
    if not isinstance(results, list):
        return ()

    out = []
    for entry in results[:20]:
        if not isinstance(entry, dict) or "id" not in entry:
            continue
        raw_date = entry.get("release_date") or entry.get("first_air_date") or ""
        year = int(raw_date[:4]) if raw_date[:4].isdigit() else None
        raw_type = entry.get("media_type")
        media_type = (
            MediaType.SERIES if raw_type == "tv"
            else MediaType.MOVIE if raw_type == "movie"
            else fallback_type
        )
        out.append(RelatedTitle(
            tmdb_id=int(entry["id"]),
            title=str(entry.get("title") or entry.get("name") or ""),
            year=year,
            poster_path=entry.get("poster_path"),
            media_type=media_type,
        ))
    return tuple(out)
```

- Dodati `recommendations` u sva tri `append_to_response`: `"credits,keywords"` → `"credits,keywords,recommendations"`.
- Dodati `recommendations: tuple[RelatedTitle, ...] = ()` na enrichment dataclass (~99-116).
- U svakoj fetch funkciji (movie/series/enrich), popuniti `recommendations=_parse_recommendations(english_raw, <MediaType za tu putanju>)` — koristi isti `*_raw` dict iz kog se već čita `keywords` (vidi `keywords=_parse_keywords(english_raw)` na ~821/877/982).

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_filmium.py::test_parse_recommendations_caps_and_maps -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/domains/filmium/tmdb_client.py tests/test_filmium.py
git commit -m "feat(filmium): TMDB client parsira recommendations"
```

---

### Task 5: Auto-update (Updatuj) upisuje `related_tmdb`

**Files:**
- Modify: `core/domains/filmium/auto_update_service.py` (payload `MediaItemCreate` ~198-220)
- Test: `tests/test_filmium_auto_update.py`

**Interfaces:**
- Consumes: `enrichment.recommendations` (Task 4), `MediaItemCreate.related_tmdb` (Task 1).
- Produces: posle Updatuj, `item.related_tmdb` = TMDB recommendations.

- [ ] **Step 1: Write the failing test**

Prati postojeći obrazac testova u `tests/test_filmium_auto_update.py` (fake enrichment sa `recommendations=(RelatedTitle(...),)`), pozovi `auto_update_item`, pa učitaj stavku i proveri:

```python
    assert updated.related_tmdb[0].tmdb_id == 555
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_filmium_auto_update.py -k related -v`
Expected: FAIL — `related_tmdb` prazan.

- [ ] **Step 3: Write minimal implementation**

U `MediaItemCreate(...)` payload-u dodati:

```python
        related_tmdb=enrichment.recommendations,
```

(Ako fake enrichment u postojećim testovima nema `recommendations`, dodati default `()` na fake — ili se oslanja na dataclass default iz Task 4.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_filmium_auto_update.py -q`
Expected: PASS (svi)

- [ ] **Step 5: Commit**

```bash
git add core/domains/filmium/auto_update_service.py tests/test_filmium_auto_update.py
git commit -m "feat(filmium): Updatuj snima related_tmdb"
```

---

### Task 6: API schema izlaže `related_tmdb`

**Files:**
- Modify: `apps/api/schemas/filmium.py` (`MediaItemResponse` ~305-368)
- Test: `tests/test_filmium.py` (ili API test modul)

**Interfaces:**
- Consumes: `MediaItem.related_tmdb`.
- Produces: `RelatedTitleSchema{tmdb_id,title,year,poster_path,media_type}`; `MediaItemResponse.related_tmdb: list[RelatedTitleSchema]`.

- [ ] **Step 1: Write the failing test**

```python
def test_media_response_serializes_related():
    from apps.api.schemas.filmium import MediaItemResponse
    # napravi MediaItem sa related_tmdb=(RelatedTitle(1,"A",2001,"/a.jpg",MOVIE),)
    resp = MediaItemResponse.from_domain(item)
    assert resp.related_tmdb[0].tmdb_id == 1
    assert resp.related_tmdb[0].media_type == "movie"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_filmium.py::test_media_response_serializes_related -v`
Expected: FAIL — polje ne postoji.

- [ ] **Step 3: Write minimal implementation**

```python
class RelatedTitleSchema(BaseModel):
    tmdb_id: int
    title: str
    year: int | None = None
    poster_path: str | None = None
    media_type: str
```

Na `MediaItemResponse`: `related_tmdb: list[RelatedTitleSchema] = []`. U `from_domain`:

```python
            related_tmdb=[
                RelatedTitleSchema(
                    tmdb_id=r.tmdb_id, title=r.title, year=r.year,
                    poster_path=r.poster_path, media_type=r.media_type.value,
                )
                for r in item.related_tmdb
            ],
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_filmium.py::test_media_response_serializes_related -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/api/schemas/filmium.py tests/test_filmium.py
git commit -m "feat(filmium): API izlaže related_tmdb"
```

---

### Task 7: GUI tip `RelatedTitle` + `related_tmdb`

**Files:**
- Modify: tip `MediaItem` (naći sa `grep -rn "media_type:" apps/gui/src/features/filmium/types` ili gde je `MediaItem` definisan)
- Test: none (samo tip) — pokriveno kompilacijom.

**Interfaces:**
- Produces: TS tip `RelatedTitle { tmdb_id; title; year; poster_path; media_type }`; `MediaItem.related_tmdb: RelatedTitle[]`.

- [ ] **Step 1: Add type**

```ts
export type RelatedTitle = {
  tmdb_id: number;
  title: string;
  year: number | null;
  poster_path: string | null;
  media_type: "movie" | "series";
};
```

Dodati `related_tmdb: RelatedTitle[];` na `MediaItem` tip (sa `?` ako API možda ne vraća, radi bezbednosti: `related_tmdb?: RelatedTitle[]`).

- [ ] **Step 2: Typecheck**

Run: `cd apps/gui && npm run typecheck` (ili `tsc --noEmit`)
Expected: prolazi.

- [ ] **Step 3: Commit**

```bash
git add apps/gui/src
git commit -m "feat(filmium): GUI tip related_tmdb"
```

---

### Task 8: Čist helper modul — scorer + kaskadni dedup (izdvojeno, testirano)

**Files:**
- Create: `apps/gui/src/features/filmium/lib/filmiumRecommendations.ts`
- Test: `apps/gui/src/features/filmium/lib/filmiumRecommendations.test.ts`

**Interfaces:**
- Produces:
  - `scoreRecommended(current: MediaItem, candidates: MediaItem[]): MediaItem[]` — ponderisano naziv+žanr+ključne reči, poštuje kategoriju, isključuje `current.id`, sort opadajuće, filter score>0.
  - `scoreByGenre(current: MediaItem, candidates: MediaItem[]): MediaItem[]` — po broju istih žanrova.
  - `splitRelated(current, related: RelatedTitle[], catalog: MediaItem[]): { owned: MediaItem; related: RelatedTitle }[] ordered owned-first` → vraća `RelatedCard[]` gde je `owned: MediaItem | null`.
  - `cascadeDedupe(sections: {relatedCards, recommended, genre}, limit=10)` → izbacuje već viđene, seče na `limit`.

- [ ] **Step 1: Write the failing test**

```ts
import { describe, expect, it } from "vitest";
import { scoreRecommended, scoreByGenre } from "./filmiumRecommendations";

const base = (over: Partial<MediaItem>): MediaItem => ({
  id: 0, title: "", media_type: "movie", genres: [], keywords: [],
  cast_names: [], content_category: "regular", release_year: null,
  poster_path: null, backdrop_path: null, related_tmdb: [], ...over,
} as MediaItem);

describe("scoreRecommended", () => {
  it("keywords težina veća od žanra; tiebreak naziv (token >=4)", () => {
    const current = base({ id: 1, title: "Space War",
      genres: ["Sci-Fi"], keywords: ["robot", "mars"] });
    const kw = base({ id: 2, title: "Zzz", keywords: ["robot", "mars"] });
    const genre = base({ id: 3, title: "Yyy", genres: ["Sci-Fi"] });
    const out = scoreRecommended(current, [kw, genre]);
    expect(out[0].id).toBe(2); // keywords jače
  });

  it("kratki tokeni ne prave lažan pogodak", () => {
    const current = base({ id: 1, title: "The War" });
    const other = base({ id: 2, title: "The Sun" }); // 'the' <4, 'war' vs 'sun'
    expect(scoreRecommended(current, [other])).toHaveLength(0);
  });

  it("poštuje kategoriju domestic", () => {
    const current = base({ id: 1, genres: ["Drama"],
      content_category: "domestic" });
    const foreign = base({ id: 2, genres: ["Drama"],
      content_category: "regular" });
    expect(scoreByGenre(current, [foreign])).toHaveLength(0);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/gui && npx vitest run src/features/filmium/lib/filmiumRecommendations.test.ts`
Expected: FAIL — modul ne postoji.

- [ ] **Step 3: Write minimal implementation**

```ts
import type { MediaItem, RelatedTitle } from "...";

const W_KEYWORD = 5;
const W_GENRE = 3;
const W_TITLE = 1;

function categoryAllows(current: MediaItem, cand: MediaItem): boolean {
  const cat = current.content_category ?? "regular";
  if (cat !== "domestic" && cat !== "animated") return true;
  return (cand.content_category ?? "regular") === cat;
}

function overlap(a: string[] = [], b: string[] = []): number {
  const set = new Set(a);
  return b.filter((x) => set.has(x)).length;
}

function titleTokens(title: string): Set<string> {
  return new Set(
    title.toLocaleLowerCase("sr-Latn-RS").split(/\s+/).filter((t) => t.length >= 4),
  );
}

export function scoreRecommended(
  current: MediaItem, candidates: MediaItem[],
): MediaItem[] {
  const curTokens = titleTokens(current.title);
  return candidates
    .filter((c) => c.id !== current.id && categoryAllows(current, c))
    .map((c) => {
      const kw = overlap(current.keywords, c.keywords) * W_KEYWORD;
      const gn = overlap(current.genres, c.genres) * W_GENRE;
      const candTokens = titleTokens(c.title);
      let tt = 0;
      curTokens.forEach((t) => { if (candTokens.has(t)) tt += 1; });
      return { c, score: kw + gn + tt * W_TITLE };
    })
    .filter((e) => e.score > 0)
    .sort((a, b) => b.score - a.score)
    .map((e) => e.c);
}

export function scoreByGenre(
  current: MediaItem, candidates: MediaItem[],
): MediaItem[] {
  return candidates
    .filter((c) => c.id !== current.id && categoryAllows(current, c))
    .map((c) => ({ c, score: overlap(current.genres, c.genres) }))
    .filter((e) => e.score > 0)
    .sort((a, b) => b.score - a.score)
    .map((e) => e.c);
}

export type RelatedCard = { related: RelatedTitle; owned: MediaItem | null };

export function splitRelated(
  related: RelatedTitle[], catalog: MediaItem[],
): RelatedCard[] {
  const byTmdb = new Map(catalog.filter((i) => i.tmdb_id != null)
    .map((i) => [i.tmdb_id, i]));
  const cards = related.map((r) => ({ related: r, owned: byTmdb.get(r.tmdb_id) ?? null }));
  return [...cards.filter((c) => c.owned), ...cards.filter((c) => !c.owned)];
}

export function cascadeDedupe(
  relatedCards: RelatedCard[], recommended: MediaItem[], genre: MediaItem[],
  limit = 10,
): { relatedCards: RelatedCard[]; recommended: MediaItem[]; genre: MediaItem[] } {
  const seen = new Set<number>();
  const rel = relatedCards.slice(0, limit);
  rel.forEach((c) => { if (c.owned) seen.add(c.owned.id); });
  const rec = recommended.filter((i) => !seen.has(i.id)).slice(0, limit);
  rec.forEach((i) => seen.add(i.id));
  const gen = genre.filter((i) => !seen.has(i.id)).slice(0, limit);
  return { relatedCards: rel, recommended: rec, genre: gen };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/gui && npx vitest run src/features/filmium/lib/filmiumRecommendations.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/gui/src/features/filmium/lib/filmiumRecommendations.ts apps/gui/src/features/filmium/lib/filmiumRecommendations.test.ts
git commit -m "feat(filmium): helper scorer + kaskadni dedup"
```

---

### Task 9: `RecommendationRow` — owned + ne-owned (crvena ivica) kartice

**Files:**
- Modify: `apps/gui/src/pages/FilmiumMediaDetailsPage.tsx` (`RecommendationRow` ~1553-1641)
- Modify: `apps/gui/src/features/filmium/styles/filmium-pages.css`
- Test: none (vizuelno; logika je u Task 8)

**Interfaces:**
- Consumes: `RelatedCard` (Task 8).
- Produces: `RecommendationRow` prihvata `cards: RelatedCard[]` (za Povezani) ILI `items: MediaItem[]` (za druga dva); callbacks `onOpen(item)` i `onAcquire(related)`. Ne-owned kartica ima klasu `is-wishlist`.

- [ ] **Step 1: Implement**

Proširiti `RecommendationRow` da renderuje karticu iz `RelatedCard`: ako `owned` → `onClick=onOpen(owned)`, normalna kartica; ako `null` → klasa `filmium-details-poster-card is-wishlist`, poster `https://image.tmdb.org/t/p/w500${related.poster_path}` (ili fallback blok ako je null), `onClick=onAcquire(related)`. Za Preporučene/Po žanru zadržati postojeći `items: MediaItem[]` render.

CSS:

```css
.filmium-details-poster-card.is-wishlist {
  border: 2px solid var(--filmium-danger, #e5484d);
}
```

- [ ] **Step 2: Typecheck + build**

Run: `cd apps/gui && npm run typecheck`
Expected: prolazi.

- [ ] **Step 3: Commit**

```bash
git add apps/gui/src/pages/FilmiumMediaDetailsPage.tsx apps/gui/src/features/filmium/styles/filmium-pages.css
git commit -m "feat(filmium): kartice povezanih (owned + wishlist crvena ivica)"
```

---

### Task 10: Detalj-stranica — tri odeljka + otvaranje modala za ne-owned

**Files:**
- Modify: `apps/gui/src/pages/FilmiumMediaDetailsPage.tsx` (memo blokovi ~965-1021, render ~1385-1409)
- Modify: `apps/gui/src/features/filmium/components/uploads/FilmiumAcquireModal.tsx` (prefill prop)
- Test: none direktno (logika Task 8); ručna verifikacija u preview-u.

**Interfaces:**
- Consumes: `scoreRecommended`, `scoreByGenre`, `splitRelated`, `cascadeDedupe` (Task 8).
- Produces: `FilmiumAcquireModal` prihvata `prefill?: { title: string; year: number | null; media_type: "movie" | "series"; tmdb_id: number | null }`.

- [ ] **Step 1: Implement memo + render**

Zameniti `genreMatches`/`actorMatches` sa:

```tsx
const relatedCards = useMemo(
  () => splitRelated(item.related_tmdb ?? [], items),
  [item.related_tmdb, items],
);
const recommendedRaw = useMemo(
  () => scoreRecommended(item, items), [item, items],
);
const genreRaw = useMemo(() => scoreByGenre(item, items), [item, items]);
const sections = useMemo(
  () => cascadeDedupe(relatedCards, recommendedRaw, genreRaw, 10),
  [relatedCards, recommendedRaw, genreRaw],
);
```

Render (redosled: Povezani → Preporučeni → Po žanru), naslovi po `media_type` (film/serija). Ne-owned klik → `setAcquirePrefill({title, year, media_type, tmdb_id})` + `setAcquireOpen(true)`.

- [ ] **Step 2: Modal prefill**

Dodati `prefill` prop; u `useEffect` na `open`, ako `prefill` postoji popuniti `title`/`year`/`mediaType` i sačuvati `tmdb_id` za `createWishlistEntry`.

- [ ] **Step 3: Verifikacija u preview-u**

Pokrenuti dev server (preview_start po `.claude/launch.json`), otvoriti detalj filma sa TMDB podacima, potvrditi tri odeljka, crvenu ivicu na ne-owned, i da klik otvara popunjen „Dodaj" modal. Screenshot.

- [ ] **Step 4: Commit**

```bash
git add apps/gui/src/pages/FilmiumMediaDetailsPage.tsx apps/gui/src/features/filmium/components/uploads/FilmiumAcquireModal.tsx
git commit -m "feat(filmium): tri odeljka preporuka + acquire prefill"
```

---

## Self-Review (popunjeno)

- **Spec coverage:** Povezani=Task 4/5/8/9/10; Preporučeni=Task 8/10; Po žanru=Task 8/10; čuvanje=Task 1/2/3; „samo unapred"=Task 5 (Updatuj); schema=Task 6; ne-owned wishlist=Task 9/10; kapa 10=Task 8; kaskadni dedup=Task 8. Novi-importi punjenje: pokriveno preko istog `MediaItemCreate.related_tmdb` polja — ako import putanja koristi TMDB enrichment, dovoljno je proslediti `recommendations`; ako ne dohvata TMDB u trenutku importa, Updatuj popunjava (prihvaćeno „samo unapred").
- **Placeholder scan:** ime `repo.get` i tip `MediaItem` import putanje uskladiti sa stварним (naznačeno u koracima).
- **Type consistency:** `RelatedTitle` isti u modelu/schemi/TS; `RelatedCard.owned: MediaItem | null` dosledno.

## Van opsega
„Prikaži još", backfill starih, TMDB `similar`, lokalno keširanje ne-owned postera.
