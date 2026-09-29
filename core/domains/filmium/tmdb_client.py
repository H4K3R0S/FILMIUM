"""TMDB klijent za obogaćivanje filmova i serija (opis, ocene, slike).

Zajednički modul za pregled poslije skeniranja i za stranicu detalja.
Namerno tolerantan: bez API ključa, bez mreže ili bez pogotka vraća
``None`` umesto greške — aplikacija radi i bez TMDB-a, a podaci se
prikazuju kada su dostupni.

Ključ se čita redom: env ``TMDB_ACCESS_TOKEN`` / ``TMDB_API_KEY``, pa
``config/tmdb.json`` u korenu projekta.
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from functools import lru_cache
from pathlib import Path

_API_BASE = "https://api.themoviedb.org/3"
_IMAGE_BASE = "https://image.tmdb.org/t/p"
_TIMEOUT = 12

# Redosled jezika za lokalizovana imena sezona/epizoda i opise.
# Prvi koji vrati neprazan naziv pobeđuje; na kraju je engleski kao rezerva.
_DEFAULT_LANGUAGES: tuple[str, ...] = ("sr-RS", "hr-HR", "bs-BA", "en-US")


# ==========          MODELI          ==========

from core.domains.filmium.tmdb_models import (  # noqa: F401 — re-export
    MediaTitleEnrichment,
    TmdbCredentials,
    TmdbEpisode,
    TmdbEpisodeMeta,
    TmdbMovie,
    TmdbSeason,
    TmdbSeries,
)
from core.domains.filmium.tmdb_parse import (  # noqa: F401 — re-export
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


def _project_root() -> Path:
    # core/domains/filmium/tmdb_client.py -> koren projekta
    return Path(__file__).resolve().parents[3]


@lru_cache(maxsize=1)
def load_credentials() -> TmdbCredentials:
    access = os.environ.get("TMDB_ACCESS_TOKEN") or None
    key = os.environ.get("TMDB_API_KEY") or None

    if not access and not key:
        config = _project_root() / "config" / "tmdb.json"
        try:
            data = json.loads(config.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        if isinstance(data, dict):
            access = data.get("access_token") or None
            key = data.get("api_key") or None

    return TmdbCredentials(access_token=access, api_key=key)


def is_tmdb_available() -> bool:
    return load_credentials().is_configured


@lru_cache(maxsize=1)
def preferred_languages() -> tuple[str, ...]:
    """Redosled jezika za lokalizaciju (config ``languages`` ili default)."""

    config = _project_root() / "config" / "tmdb.json"
    try:
        data = json.loads(config.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}

    if isinstance(data, dict):
        raw = data.get("languages")
        if isinstance(raw, list):
            languages = tuple(
                item for item in raw if isinstance(item, str) and item
            )
            if languages:
                return languages

    return _DEFAULT_LANGUAGES


# ==========          HTTP          ==========

def _image_url(path: object, size: str) -> str | None:
    if not isinstance(path, str) or not path:
        return None
    return f"{_IMAGE_BASE}/{size}{path}"


def download_image(url: str | None) -> bytes | None:
    """Preuzima binarni sadržaj slike sa TMDB CDN-a.

    Tolerantno: bez URL-a, bez mreže ili na grešku vraća ``None``.
    """

    if not url:
        return None

    request = urllib.request.Request(url, headers={"accept": "image/*"})
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
            content = response.read()
    except (urllib.error.URLError, OSError, TimeoutError):
        return None

    return content or None


def _request(
    path: str,
    params: dict[str, str] | None = None,
    language: str | None = None,
) -> dict | None:
    credentials = load_credentials()
    if not credentials.is_configured:
        return None

    query = dict(params or {})
    if language:
        query["language"] = language
    if not credentials.access_token and credentials.api_key:
        query["api_key"] = credentials.api_key

    url = f"{_API_BASE}/{path}"
    if query:
        url = f"{url}?{urllib.parse.urlencode(query)}"

    headers = {"accept": "application/json"}
    if credentials.access_token:
        headers["Authorization"] = f"Bearer {credentials.access_token}"

    request = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
            payload = response.read()
    except (urllib.error.URLError, OSError, TimeoutError):
        return None

    try:
        data = json.loads(payload)
    except (ValueError, TypeError):
        return None

    return data if isinstance(data, dict) else None


# ==========          PARSIRANJE (čisto, testabilno)          ==========

def _as_year(value: object) -> int | None:
    if isinstance(value, str) and len(value) >= 4 and value[:4].isdigit():
        return int(value[:4])
    return None


def _as_rating(value: object) -> float | None:
    if isinstance(value, (int, float)) and value > 0:
        return round(float(value), 1)
    return None


def parse_search_result(data: dict) -> int | None:
    """Vraća tmdb_id najboljeg pogotka iz search/tv odgovora."""

    results = data.get("results")
    if not isinstance(results, list) or not results:
        return None

    first = results[0]
    if not isinstance(first, dict):
        return None

    tmdb_id = first.get("id")
    return int(tmdb_id) if isinstance(tmdb_id, int) else None


def parse_tv_details(data: dict) -> TmdbSeries | None:
    tmdb_id = data.get("id")
    if not isinstance(tmdb_id, int):
        return None

    genres_raw = data.get("genres")
    genres: list[str] = []
    if isinstance(genres_raw, list):
        for item in genres_raw:
            if isinstance(item, dict) and isinstance(item.get("name"), str):
                genres.append(item["name"])

    overview = data.get("overview")
    season_count = data.get("number_of_seasons")

    original_name = data.get("original_name")

    return TmdbSeries(
        tmdb_id=tmdb_id,
        name=str(data.get("name") or data.get("original_name") or ""),
        original_name=(
            original_name
            if isinstance(original_name, str) and original_name
            else None
        ),
        year=_as_year(data.get("first_air_date")),
        genres=tuple(genres),
        overview=overview if isinstance(overview, str) and overview else None,
        rating=_as_rating(data.get("vote_average")),
        poster_url=_image_url(data.get("poster_path"), "w500"),
        backdrop_url=_image_url(data.get("backdrop_path"), "w780"),
        season_count=(
            season_count if isinstance(season_count, int) else None
        ),
    )


def parse_season_episodes(data: dict) -> list[TmdbEpisode]:
    episodes_raw = data.get("episodes")
    if not isinstance(episodes_raw, list):
        return []

    episodes: list[TmdbEpisode] = []
    for item in episodes_raw:
        if not isinstance(item, dict):
            continue
        number = item.get("episode_number")
        if not isinstance(number, int):
            continue
        name = item.get("name")
        overview = item.get("overview")
        air_date = item.get("air_date")
        episodes.append(
            TmdbEpisode(
                episode_number=number,
                name=name if isinstance(name, str) and name else None,
                overview=(
                    overview
                    if isinstance(overview, str) and overview
                    else None
                ),
                air_date=(
                    air_date
                    if isinstance(air_date, str) and air_date
                    else None
                ),
                rating=_as_rating(item.get("vote_average")),
                still_url=_image_url(item.get("still_path"), "w300"),
            )
        )

    return episodes


def _season_name(data: dict) -> str | None:
    """Naziv sezone; ignoriše generičko „Season N"/„Sezona N"."""

    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        return None
    number = data.get("season_number")
    if isinstance(number, int):
        generic = {f"season {number}", f"sezona {number}"}
        if name.strip().lower() in generic:
            return None
    return name.strip()


def parse_movie_details(data: dict) -> TmdbMovie | None:
    tmdb_id = data.get("id")
    if not isinstance(tmdb_id, int):
        return None

    genres_raw = data.get("genres")
    genres: list[str] = []
    if isinstance(genres_raw, list):
        for item in genres_raw:
            if isinstance(item, dict) and isinstance(item.get("name"), str):
                genres.append(item["name"])

    overview = data.get("overview")

    original_title = data.get("original_title")

    return TmdbMovie(
        tmdb_id=tmdb_id,
        title=str(data.get("title") or data.get("original_title") or ""),
        original_title=(
            original_title
            if isinstance(original_title, str) and original_title
            else None
        ),
        year=_as_year(data.get("release_date")),
        genres=tuple(genres),
        overview=overview if isinstance(overview, str) and overview else None,
        rating=_as_rating(data.get("vote_average")),
        poster_url=_image_url(data.get("poster_path"), "w500"),
        backdrop_url=_image_url(data.get("backdrop_path"), "w780"),
    )


# ==========          JAVNE FUNKCIJE (mreža)          ==========

def match_series(
    title: str,
    year: int | None = None,
    language: str | None = None,
) -> TmdbSeries | None:
    """Traži seriju po nazivu (+ godini) i vraća njene TMDB detalje."""

    params = {"query": title, "include_adult": "false"}
    if year is not None:
        params["first_air_date_year"] = str(year)

    search = _request("search/tv", params, language=language)
    if search is None:
        return None

    tmdb_id = parse_search_result(search)
    if tmdb_id is None:
        return None

    details = _request(f"tv/{tmdb_id}", language=language)
    return None if details is None else parse_tv_details(details)


def match_movie(
    title: str,
    year: int | None = None,
    language: str | None = None,
) -> TmdbMovie | None:
    """Traži film po nazivu (+ godini) i vraća njegove TMDB detalje."""

    params = {"query": title, "include_adult": "false"}
    if year is not None:
        params["year"] = str(year)

    search = _request("search/movie", params, language=language)
    if search is None:
        return None

    tmdb_id = parse_search_result(search)
    if tmdb_id is None:
        return None

    details = _request(f"movie/{tmdb_id}", language=language)
    return None if details is None else parse_movie_details(details)


def get_season_episodes(
    tmdb_id: int,
    season_number: int,
    language: str | None = None,
) -> list[TmdbEpisode]:
    """Vraća epizode sezone sa TMDB-a (naziv/opis/datum/ocena/still)."""

    data = _request(f"tv/{tmdb_id}/season/{season_number}", language=language)
    return [] if data is None else parse_season_episodes(data)


def _collect_local_episode_fields(tmdb_id: int, season_number: int,
                                  langs: tuple[str, ...]) -> tuple[dict, dict, dict]:
    """Skupi lokalne (ne-EN) nazive/opise/datume epizoda: prvi neprazan po
    jeziku pobeđuje. Vraća (local_overview, local_name, local_air)."""

    local_overview: dict[int, str] = {}
    local_name: dict[int, str] = {}
    local_air: dict[int, str] = {}

    for language in langs:
        if language.lower().startswith("en"):
            continue
        for episode in get_season_episodes(
            tmdb_id, season_number, language
        ):
            number = episode.episode_number
            if episode.overview and number not in local_overview:
                local_overview[number] = episode.overview
            if episode.name and number not in local_name:
                local_name[number] = episode.name
            if episode.air_date and number not in local_air:
                local_air[number] = episode.air_date
    return local_overview, local_name, local_air


def _merge_episode_meta(number: int, english_episode, local_overview: dict,
                        local_name: dict, local_air: dict) -> "TmdbEpisodeMeta":
    """Spoji EN i lokalne podatke jedne epizode (naziv/opis/datum: EN pa lokalno)."""

    return TmdbEpisodeMeta(
        episode_number=number,
        name=(
            (english_episode.name if english_episode else None)
            or local_name.get(number)
        ),
        overview_en=(
            english_episode.overview if english_episode else None
        ),
        overview_local=local_overview.get(number),
        air_date=(
            (english_episode.air_date if english_episode else None)
            or local_air.get(number)
        ),
        rating=(
            english_episode.rating if english_episode else None
        ),
        still_url=(
            english_episode.still_url if english_episode else None
        ),
    )


def season_episode_metadata(
    tmdb_id: int,
    season_number: int,
    languages: tuple[str, ...] | None = None,
) -> tuple[TmdbEpisodeMeta, ...]:
    """
    Metapodaci epizoda sezone: naziv/opis na engleskom i lokalni opis
    (prvi neprazan kroz lanac sr-RS → hr-HR → bs-BA). Naziv preferira
    lokalni ako postoji.
    """

    if not is_tmdb_available():
        return ()

    langs = languages or preferred_languages()

    english = {
        episode.episode_number: episode
        for episode in get_season_episodes(tmdb_id, season_number, "en-US")
    }

    local_overview, local_name, local_air = _collect_local_episode_fields(
        tmdb_id, season_number, langs
    )

    numbers = set(english) | set(local_overview) | set(local_name)

    result = [
        _merge_episode_meta(
            number, english.get(number), local_overview, local_name, local_air
        )
        for number in sorted(numbers)
    ]

    return tuple(result)


def get_localized_season(
    tmdb_id: int,
    season_number: int,
    languages: tuple[str, ...] | None = None,
) -> TmdbSeason | None:
    """
    Sezona sa lokalizovanim imenima (naziv sezone + naslovi epizoda).

    Prolazi kroz ``languages`` redom i po svakom polju uzima prvi
    neprazan lokalizovani naziv (sr → hr → bs → en). Vraća ``None``
    kada TMDB nije dostupan ili sezona ne postoji.
    """

    order = languages or preferred_languages()

    season_name: str | None = None
    episode_names: dict[int, str] = {}
    seen_numbers: set[int] = set()

    for language in order:
        data = _request(
            f"tv/{tmdb_id}/season/{season_number}", language=language
        )
        if data is None:
            continue

        if season_name is None:
            season_name = _season_name(data)

        for episode in parse_season_episodes(data):
            seen_numbers.add(episode.episode_number)
            if (
                episode.episode_number not in episode_names
                and episode.name
            ):
                episode_names[episode.episode_number] = episode.name

    if not seen_numbers:
        return None

    episodes = tuple(
        TmdbEpisode(
            episode_number=number,
            name=episode_names.get(number),
            overview=None,
            air_date=None,
            rating=None,
            still_url=None,
        )
        for number in sorted(seen_numbers)
    )
    return TmdbSeason(
        season_number=season_number,
        name=season_name,
        episodes=episodes,
    )




# ==========          VIŠEJEZIČNO OBOGAĆIVANJE (naslovi/opisi)          ==========

def _local_title_overview(
    detail_path: str,
    languages: tuple[str, ...],
    title_key: str,
) -> tuple[str | None, str | None]:
    """Prvi neprazan lokalni naslov/opis kroz lanac jezika (bez engleskog)."""

    local_title: str | None = None
    local_overview: str | None = None

    for language in languages:
        if language.lower().startswith("en"):
            continue
        data = _request(detail_path, language=language)
        if data is None:
            continue
        if local_title is None:
            value = data.get(title_key)
            if isinstance(value, str) and value:
                local_title = value
        if local_overview is None:
            overview = data.get("overview")
            if isinstance(overview, str) and overview:
                local_overview = overview
        if local_title and local_overview:
            break

    return local_title, local_overview




# Enrich-sloj je u tmdb_enrich.py (re-export radi postojećih tmdb_client.* poziva).
from core.domains.filmium.tmdb_enrich import (  # noqa: F401 — re-export
    enrich_best,
    enrich_by_id,
    enrich_movie,
    enrich_series,
    strip_franchise_prefix,
    strip_trailing_ordinal,
    title_variants,
)
