"""Parsiranje TMDB JSON odgovora (cast/keywords/…) — izdvojeno iz tmdb_client."""


def _parse_cast(data: dict | None, limit: int | None = None) -> tuple[str, ...]:
    """Imena glumaca iz TMDB ``credits.cast``.

    ``limit=None`` (podrazumevano) vraća SVE glumce; ceo broj ograničava
    na toliko glavnih.
    """

    if not isinstance(data, dict):
        return ()
    credits = data.get("credits")
    if not isinstance(credits, dict):
        return ()
    cast = credits.get("cast")
    if not isinstance(cast, list):
        return ()

    names: list[str] = []
    for member in cast:
        if not isinstance(member, dict):
            continue
        name = member.get("name")
        if isinstance(name, str) and name and name not in names:
            names.append(name)
        if limit is not None and len(names) >= limit:
            break
    return tuple(names)


def _parse_keywords(data: dict | None) -> tuple[str, ...]:
    """Ključne reči iz TMDB ``keywords`` (film: ``keywords``, serija: ``results``)."""

    if not isinstance(data, dict):
        return ()
    block = data.get("keywords")
    if not isinstance(block, dict):
        return ()
    items = block.get("keywords")
    if not isinstance(items, list):
        items = block.get("results")
    if not isinstance(items, list):
        return ()

    names: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if isinstance(name, str) and name and name not in names:
            names.append(name)
    return tuple(names)


def _parse_recommendations(data, fallback_type):
    """TMDB ``recommendations.results`` → torka RelatedTitle (cap 20)."""

    from core.domains.filmium.models import MediaType, RelatedTitle

    if not isinstance(data, dict):
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


def _parse_collection(data: dict | None) -> str | None:
    """Naziv kolekcije iz TMDB ``belongs_to_collection`` (samo filmovi)."""

    if not isinstance(data, dict):
        return None
    collection = data.get("belongs_to_collection")
    if not isinstance(collection, dict):
        return None
    name = collection.get("name")
    return name if isinstance(name, str) and name else None


def _parse_language(data: dict | None) -> str | None:
    """Originalni jezik iz TMDB ``original_language`` (npr. „hi")."""

    if not isinstance(data, dict):
        return None
    value = data.get("original_language")
    return value if isinstance(value, str) and value else None


def _parse_country(data: dict | None) -> str | None:
    """Zemlja porekla iz ``production_countries`` ili ``origin_country``."""

    if not isinstance(data, dict):
        return None

    countries = data.get("production_countries")
    if isinstance(countries, list):
        for country in countries:
            if isinstance(country, dict):
                name = country.get("name")
                if isinstance(name, str) and name:
                    return name

    origin = data.get("origin_country")
    if isinstance(origin, list):
        for code in origin:
            if isinstance(code, str) and code:
                return code

    return None


def _parse_vote_count(data: dict | None) -> int | None:
    """Broj glasova iz TMDB ``vote_count``."""

    if not isinstance(data, dict):
        return None
    value = data.get("vote_count")
    return int(value) if isinstance(value, int) and value > 0 else None


def _parse_studio(data: dict | None) -> str | None:
    """Prvi studio iz TMDB ``production_companies``."""

    if not isinstance(data, dict):
        return None
    companies = data.get("production_companies")
    if not isinstance(companies, list):
        return None
    for company in companies:
        if isinstance(company, dict):
            name = company.get("name")
            if isinstance(name, str) and name:
                return name
    return None


def _parse_director(data: dict | None) -> str | None:
    """Režiser iz ``credits.crew`` (film) ili ``created_by`` (serija)."""

    if not isinstance(data, dict):
        return None

    credits = data.get("credits")
    if isinstance(credits, dict):
        crew = credits.get("crew")
        if isinstance(crew, list):
            for member in crew:
                if (
                    isinstance(member, dict)
                    and member.get("job") == "Director"
                ):
                    name = member.get("name")
                    if isinstance(name, str) and name:
                        return name

    created_by = data.get("created_by")
    if isinstance(created_by, list):
        for creator in created_by:
            if isinstance(creator, dict):
                name = creator.get("name")
                if isinstance(name, str) and name:
                    return name

    return None
