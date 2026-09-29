"""TMDB obogaćivanje (naslovi/opisi/žanrovi) — izdvojeno iz tmdb_client."""

import re

from core.domains.filmium.genre_rules import canonicalize_genres
from core.domains.filmium.models import MediaType
from core.domains.filmium.tmdb_client import (
    _local_title_overview,
    _request,
    is_tmdb_available,
    parse_movie_details,
    parse_search_result,
    parse_tv_details,
    preferred_languages,
)
from core.domains.filmium.tmdb_models import MediaTitleEnrichment
from core.domains.filmium.tmdb_parse import (
    _parse_cast,
    _parse_collection,
    _parse_country,
    _parse_director,
    _parse_keywords,
    _parse_language,
    _parse_recommendations,
    _parse_studio,
    _parse_vote_count,
)


def enrich_movie(
    title: str,
    year: int | None = None,
    languages: tuple[str, ...] | None = None,
) -> MediaTitleEnrichment | None:
    """
    Nalazi film na TMDB-u (ime+godina) i vraća naslove/opise u tri
    varijante: izvorni, engleski i lokalni (sr→hr→bs). Tolerantno.
    """

    if not is_tmdb_available():
        return None

    langs = languages or preferred_languages()

    params = {"query": title, "include_adult": "false"}
    if year is not None:
        params["year"] = str(year)
    search = _request("search/movie", params, language="en-US")
    if search is None:
        return None
    tmdb_id = parse_search_result(search)
    if tmdb_id is None:
        return None

    english_raw = _request(
        f"movie/{tmdb_id}",
        {"append_to_response": "credits,keywords,recommendations"},
        language="en-US",
    )
    english = parse_movie_details(english_raw) if english_raw else None

    local_title, local_overview = _local_title_overview(
        f"movie/{tmdb_id}", langs, "title"
    )

    return MediaTitleEnrichment(
        tmdb_id=tmdb_id,
        original_title=english.original_title if english else None,
        recommendations=_parse_recommendations(english_raw, MediaType.MOVIE),
        english_title=english.title if english else None,
        english_overview=english.overview if english else None,
        local_title=local_title,
        local_overview=local_overview,
        year=english.year if english else None,
        genres=canonicalize_genres(english.genres) if english else (),
        rating=english.rating if english else None,
        poster_url=english.poster_url if english else None,
        backdrop_url=english.backdrop_url if english else None,
        cast_names=_parse_cast(english_raw),
        studio=_parse_studio(english_raw),
        director=_parse_director(english_raw),
        vote_count=_parse_vote_count(english_raw),
        original_language=_parse_language(english_raw),
        country=_parse_country(english_raw),
        keywords=_parse_keywords(english_raw),
        collection=_parse_collection(english_raw),
    )


def enrich_series(
    title: str,
    year: int | None = None,
    languages: tuple[str, ...] | None = None,
) -> MediaTitleEnrichment | None:
    """Kao ``enrich_movie``, ali za serije (search/tv, tv/{id})."""

    if not is_tmdb_available():
        return None

    langs = languages or preferred_languages()

    params = {"query": title, "include_adult": "false"}
    if year is not None:
        params["first_air_date_year"] = str(year)
    search = _request("search/tv", params, language="en-US")
    if search is None:
        return None
    tmdb_id = parse_search_result(search)
    if tmdb_id is None:
        return None

    english_raw = _request(
        f"tv/{tmdb_id}",
        {"append_to_response": "credits,keywords,recommendations"},
        language="en-US",
    )
    english = parse_tv_details(english_raw) if english_raw else None

    local_title, local_overview = _local_title_overview(
        f"tv/{tmdb_id}", langs, "name"
    )

    return MediaTitleEnrichment(
        tmdb_id=tmdb_id,
        original_title=english.original_name if english else None,
        recommendations=_parse_recommendations(english_raw, MediaType.SERIES),
        english_title=english.name if english else None,
        english_overview=english.overview if english else None,
        local_title=local_title,
        local_overview=local_overview,
        year=english.year if english else None,
        genres=canonicalize_genres(english.genres) if english else (),
        rating=english.rating if english else None,
        poster_url=english.poster_url if english else None,
        backdrop_url=english.backdrop_url if english else None,
        cast_names=_parse_cast(english_raw),
        studio=_parse_studio(english_raw),
        director=_parse_director(english_raw),
        vote_count=_parse_vote_count(english_raw),
        original_language=_parse_language(english_raw),
        country=_parse_country(english_raw),
        keywords=_parse_keywords(english_raw),
        collection=_parse_collection(english_raw),
    )


# ==========          VARIJANTE NAZIVA (ROBUSNI MATCHING)          ==========

_ORDINAL_RE = re.compile(r"^(?P<base>.+\S)\s+\d{1,3}$")
_PREFIX_RE = re.compile(r"^.+?\s+\d{1,3}\s+-\s+(?P<rest>.+)$")


def _trailing_ordinal_number(title: str) -> int | None:
    """Redni broj na kraju naziva (npr. „John Wick 5" → 5), inače None."""

    match = re.search(r"\s(\d{1,3})$", (title or "").strip())
    return int(match.group(1)) if match else None


def strip_trailing_ordinal(title: str) -> str:
    """„John Wick 5" → „John Wick"; naziv bez rednog broja ostaje isti."""

    match = _ORDINAL_RE.match((title or "").strip())
    return match.group("base") if match else (title or "").strip()


def strip_franchise_prefix(title: str) -> str:
    """„John Wict 5 - Balerina" → „Balerina"; inače vraća original."""

    match = _PREFIX_RE.match((title or "").strip())
    return match.group("rest").strip() if match else (title or "").strip()


def title_variants(title: str) -> tuple[str, ...]:
    """Redosled pokušaja naziva; bez duplikata, originalni je uvek prvi."""

    base = (title or "").strip()
    candidates = (
        base,
        strip_trailing_ordinal(base),
        strip_franchise_prefix(base),
        strip_trailing_ordinal(strip_franchise_prefix(base)),
    )
    ordered: dict[str, None] = {}
    for candidate in candidates:
        if candidate and candidate not in ordered:
            ordered[candidate] = None
    return tuple(ordered)


# ==========          ENRICH BY ID + NAJBOLJI POGODAK          ==========

def enrich_by_id(
    tmdb_id: int,
    media_type: str,
    languages: tuple[str, ...] | None = None,
) -> MediaTitleEnrichment | None:
    """Enrich direktno po TMDB ID-u (movie/tv), bez pretrage. Tolerantno."""

    if not is_tmdb_available():
        return None

    langs = languages or preferred_languages()
    is_series = media_type == "series"
    detail_path = f"tv/{tmdb_id}" if is_series else f"movie/{tmdb_id}"
    title_key = "name" if is_series else "title"

    english_raw = _request(
        detail_path,
        {"append_to_response": "credits,keywords,recommendations"},
        language="en-US",
    )
    if english_raw is None:
        return None
    english = (
        parse_tv_details(english_raw)
        if is_series
        else parse_movie_details(english_raw)
    )

    local_title, local_overview = _local_title_overview(
        detail_path, langs, title_key
    )

    return MediaTitleEnrichment(
        tmdb_id=tmdb_id,
        original_title=(english.original_name if is_series else english.original_title)
        if english
        else None,
        recommendations=_parse_recommendations(
            english_raw,
            MediaType.SERIES if is_series else MediaType.MOVIE,
        ),
        english_title=(english.name if is_series else english.title)
        if english
        else None,
        english_overview=english.overview if english else None,
        local_title=local_title,
        local_overview=local_overview,
        year=english.year if english else None,
        genres=canonicalize_genres(english.genres) if english else (),
        rating=english.rating if english else None,
        poster_url=english.poster_url if english else None,
        backdrop_url=english.backdrop_url if english else None,
        cast_names=_parse_cast(english_raw),
        studio=_parse_studio(english_raw),
        director=_parse_director(english_raw),
        vote_count=_parse_vote_count(english_raw),
        original_language=_parse_language(english_raw),
        country=_parse_country(english_raw),
        keywords=_parse_keywords(english_raw),
        collection=_parse_collection(english_raw),
    )


def enrich_best(
    query_title: str,
    year: int | None,
    media_type: str,
    *,
    tmdb_id: int | None = None,
    override_title: str | None = None,
    collection_hint: str | None = None,
    title_hint: str | None = None,
) -> MediaTitleEnrichment | None:
    """Najbolji TMDB pogodak kroz varijante naziva; None ako nema.

    Redosled: (1) direktno po ``tmdb_id`` ako je zadat; (2) varijante naziva
    (originalni, bez rednog broja, bez franšiznog prefiksa), svaka sa godinom
    pa bez godine. ``override_title`` (ručni unos) ima prednost nad
    ``query_title``. ``collection_hint`` je rezervisan za buduću franšiznu
    pretragu.

    ``title_hint`` je vidljivi Naslov (koji korisnik uređuje). Ako njegov redni
    broj (npr. „Prica o Igrackama 4" → 4) ne odgovara broju u ``query_title``
    (npr. stari „Toy Story 3"), pretraga prvo pokuša ispravljen broj
    („Toy Story 4") i odbija pogotke pogrešnog nastavka. Time preimenovanje
    filma u drugi deo više ne vraća podatke starog dela.
    """

    if tmdb_id is not None:
        by_id = enrich_by_id(tmdb_id, media_type)
        if by_id is not None:
            return by_id

    primary = (override_title or query_title or "").strip()

    # Redni broj iz vidljivog Naslova — vodilja za tačan nastavak franšize.
    # Ručni override je eksplicitan pa gazi ovu heuristiku.
    hint_number = (
        None if override_title else _trailing_ordinal_number(title_hint or "")
    )
    primary_number = _trailing_ordinal_number(primary)

    variants = list(title_variants(primary))
    # Naslov ima drugi broj nego original (npr. korisnik ispravio 3 → 4):
    # ubaci ispravljenu varijantu prvu, sa engleskom osnovom originala.
    if (
        hint_number is not None
        and primary_number is not None
        and hint_number != primary_number
    ):
        corrected = f"{strip_trailing_ordinal(primary)} {hint_number}"
        variants.insert(0, corrected)

    for variant in dict.fromkeys(variants):
        for candidate_year in (year, None):
            hit = (
                enrich_series(variant, candidate_year)
                if media_type == "series"
                else enrich_movie(variant, candidate_year)
            )
            if hit is None:
                continue
            # Odbij pogrešan nastavak: ako Naslov traži broj N, a pogodak nosi
            # drugi broj, preskoči (npr. ne vraćaj „Toy Story 3" za „…4").
            if hint_number is not None:
                got = _trailing_ordinal_number(
                    hit.english_title or ""
                ) or _trailing_ordinal_number(hit.original_title or "")
                if got is not None and got != hint_number:
                    continue
            return hit
    return None
