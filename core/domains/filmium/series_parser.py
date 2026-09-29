"""Parser sezona i epizoda iz naziva fajlova i foldera serija.

Podržani obrasci: ``S03E01``, ``1x02``, ``Season N`` / ``Sezona N`` /
``S01`` (folder), goli broj epizode (``2 - Naziv``), i ``E1``/``Episode 1``.
Naziv epizode se prepoznaje samo kada dolazi posle „ - " (da se release
oznake tipa ``HDTV.XviD`` ne bi pobrkale sa naslovom).
"""

import re
from dataclasses import dataclass

# ==========          REZULTAT          ==========

@dataclass(frozen=True)
class EpisodeInfo:
    """Prepoznati sezona/epizoda/naziv iz jednog naziva fajla."""

    season: int | None
    episode: int | None
    episode_title: str | None


# ==========          OZNAKE KOJE NISU NASLOV          ==========

_TAG_TOKENS = frozenset({
    "hdtv", "webrip", "web", "web-dl", "bluray", "brrip", "bdrip",
    "dvdrip", "xvid", "divx", "x264", "x265", "h264", "h265", "hevc",
    "avc", "aac", "ac3", "eac3", "dts", "ddp", "1080p", "720p", "2160p",
    "480p", "proper", "repack", "internal", "lol", "yify", "yts",
    "rarbg", "ettv", "eztv", "complete", "dubbed", "multi", "dual",
    "hdr", "uhd", "remux", "amzn", "nf", "dsnp", "hmax",
})


# ==========          REGEX OBRASCI          ==========

_SXXEXX = re.compile(r"s(\d{1,2})[\s._-]*e(\d{1,3})", re.IGNORECASE)
_NXNN = re.compile(r"(?<![\dx])(\d{1,2})x(\d{1,3})(?![\dx])", re.IGNORECASE)
_LEADING_NUM = re.compile(r"^\s*(\d{1,3})\s*[-–]\s*(.*)$")
_BARE_EPISODE = re.compile(
    r"(?:^|[\s._-])e(?:p(?:isode)?)?[\s._-]*(\d{1,3})(?![\dx])",
    re.IGNORECASE,
)
# Apsolutna numeracija posle naziva: „Bleach - 21 - Naslov", „FMA - 51 Naslov",
# „Iron Man S01 - 01 ( Sr )". Broj sledi posle „ - "; naslov je opcion.
_ABS_DASH = re.compile(
    r"[\s._][-–][\s._]*(\d{1,3})(?![\dxX])"
    r"(?:[\s._]*[-–][\s._]*(.+)|[\s._]+(.+))?\s*$"
)
_TRAILING_NUM = re.compile(r"(?:^|[\s._-])(\d{1,2})\s*$")
# „season(s/e)" toleriše česte tipografske greške (Seasone, Seasons).
_SEASON_WORD = re.compile(
    r"(?:seasons?e?|sezona)[\s._-]*(\d{1,2})",
    re.IGNORECASE,
)
_BARE_SEASON = re.compile(
    r"(?:^|[\s._-])s(\d{1,2})(?![\dEe])",
    re.IGNORECASE,
)
_TITLE_AFTER_MARKER = re.compile(r"^[\s._]*[-–][\s._]*(.+)$")
# Ime sezone posle broja i „ - ": „Sezona 2 - Avanture...", „S02 - Indigo Liga".
_SEASON_NAME_AFTER = re.compile(
    r"(?:(?:seasons?e?|sezona)[\s._-]*\d{1,2}"
    r"|(?:^|[\s._-])s\d{1,2}(?![\dEe]))"
    r"[\s._]*[-–][\s._]*(.+)$",
    re.IGNORECASE,
)


def _clean_title(text: str) -> str | None:
    """Čisti naziv epizode: tačke/donje crte → razmaci, bez release oznaka."""

    words: list[str] = []

    for word in re.split(r"[\s._]+", text.strip()):
        if not word:
            continue

        if word.casefold() in _TAG_TOKENS:
            break

        words.append(word)

    title = " ".join(words).strip(" -–")
    return title or None


def _title_after(rest: str) -> str | None:
    """Vraća naziv epizode ako posle markera stoji „ - naslov"."""

    match = _TITLE_AFTER_MARKER.match(rest.strip())

    if match is None:
        return None

    return _clean_title(match.group(1))


# ==========          JAVNE FUNKCIJE          ==========

def parse_episode(name: str) -> EpisodeInfo:
    """Prepoznaje sezonu, epizodu i naziv epizode iz naziva fajla."""

    text = name.strip()

    match = _SXXEXX.search(text)
    if match is not None:
        return EpisodeInfo(
            season=int(match.group(1)),
            episode=int(match.group(2)),
            episode_title=_title_after(text[match.end():]),
        )

    match = _NXNN.search(text)
    if match is not None:
        return EpisodeInfo(
            season=int(match.group(1)),
            episode=int(match.group(2)),
            episode_title=_title_after(text[match.end():]),
        )

    match = _LEADING_NUM.match(text)
    if match is not None:
        return EpisodeInfo(
            season=None,
            episode=int(match.group(1)),
            episode_title=_clean_title(match.group(2)),
        )

    match = _BARE_EPISODE.search(text)
    if match is not None:
        return EpisodeInfo(
            season=None,
            episode=int(match.group(1)),
            episode_title=_title_after(text[match.end():]),
        )

    # Apsolutna numeracija posle „ - " („Bleach - 21 - Naslov").
    match = _ABS_DASH.search(text)
    if match is not None:
        raw_title = match.group(2) or match.group(3)
        return EpisodeInfo(
            season=detect_season(text),
            episode=int(match.group(1)),
            episode_title=_clean_title(raw_title) if raw_title else None,
        )

    # Zadnja opcija: goli broj na kraju posle naziva serije
    # („His Dark Materials 1" → epizoda 1). Godine (4 cifre) se ne hvataju.
    match = _TRAILING_NUM.search(text)
    if match is not None:
        return EpisodeInfo(
            season=None,
            episode=int(match.group(1)),
            episode_title=None,
        )

    return EpisodeInfo(season=None, episode=None, episode_title=None)


def detect_season(folder_name: str) -> int | None:
    """Prepoznaje broj sezone iz naziva foldera (Season N / SNN / Sezona N)."""

    match = _SEASON_WORD.search(folder_name)
    if match is not None:
        return int(match.group(1))

    match = _BARE_SEASON.search(folder_name)
    if match is not None:
        return int(match.group(1))

    return None


def detect_season_name(folder_name: str) -> str | None:
    """Ime sezone iz naziva foldera posle broja i „ - ".

    „Sezona 2 - Avanture na Narandžastim ostrvima" → „Avanture na
    Narandžastim ostrvima". Vraća ``None`` kada nema imena posle crtice ili
    je posle crtice samo broj (raspon sezona „Sezona 1-2", ne ime).
    """

    match = _SEASON_NAME_AFTER.search(folder_name)
    if match is None:
        return None

    name = _clean_title(match.group(1))
    if name is None or name.isdigit():
        return None

    return name


def is_season_only_folder(name: str) -> bool:
    """True ako folder predstavlja SAMO sezonu (Sezona 1 / Season 2 / S01),
    bez naziva serije. Koristi se da se razlikuje sezonski podfolder unutar
    serije od zasebnog serijskog foldera unutar biblioteke."""

    if detect_season(name) is None:
        return False

    text = re.sub(
        r"(?:seasons?e?|sezona)[\s._-]*\d{1,2}(?:\s*[-–]\s*\d{1,2})?",
        " ",
        name,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"(?:^|[\s._-])s\d{1,2}(?![\dEe])",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    # Ukloni zagrade/tačke/donje crte (npr. „(2016 - 720p)") pa tokenizuj.
    text = re.sub(r"[()\[\]._]+", " ", text)

    for raw in text.split():
        # Gole crtice/spojnice između tokena se preskaču („2016 - 720p").
        word = raw.strip("-–")
        if not word:
            continue
        if word.casefold() in _TAG_TOKENS:
            continue
        # Godina ili raspon godina: 2014, 2014-15, 2019-2023.
        if re.fullmatch(
            r"(?:19|20)\d{2}(?:[-–](?:19|20)?\d{2})?",
            word,
        ):
            continue
        return False  # ostao je pravi naziv → nije čist sezonski folder

    return True


def clean_series_title(folder_name: str) -> str:
    """Izvlači čist naziv serije iz naziva foldera.

    Ako postoji sezonski marker („Season N", „Sezona N", „SNN"), naziv
    serije je deo PRE njega — sve posle (ime sezone, „Ep(1-20)", oznake)
    se odbacuje. Tako se sve sezone iste serije svode na isti naziv.
    """

    text = folder_name

    # Skrati na deo pre prvog sezonskog markera (ako nije na samom početku).
    cut_positions: list[int] = []
    season_word = re.search(
        r"(?:seasons?e?|sezona)[\s._-]*\d",
        text,
        re.IGNORECASE,
    )
    if season_word is not None and season_word.start() > 0:
        cut_positions.append(season_word.start())
    bare_season = re.search(
        r"(?:^|[\s._-])(s\d{1,2})(?![\dEe])",
        text,
        re.IGNORECASE,
    )
    if bare_season is not None and bare_season.start(1) > 0:
        cut_positions.append(bare_season.start(1))
    if cut_positions:
        text = text[: min(cut_positions)]

    text = _SXXEXX.sub(" ", text)
    text = _NXNN.sub(" ", text)
    text = re.sub(
        r"\b(?:seasons?e?|sezona)[\s._-]*\d{1,2}"
        r"(?:\s*[-–]\s*\d{1,2})?\b",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"(?:^|[\s._-])s\d{1,2}(?![\dEe])",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    # Godina ili raspon godina, sa ili bez zagrada: (2024), (2019-2023), 2024
    text = re.sub(
        r"[(\[]?\b(?:19|20)\d{2}"
        r"(?:\s*[-–]\s*(?:19|20)?\d{2})?\b[)\]]?",
        " ",
        text,
    )
    text = re.sub(r"[._]+", " ", text)
    # Uklanja zaostale prazne zagrade.
    text = re.sub(r"[(\[]\s*[)\]]", " ", text)

    words: list[str] = []
    for word in text.split():
        if word.casefold() in _TAG_TOKENS:
            break
        words.append(word)

    cleaned = " ".join(words).strip(" -–()[]")
    return cleaned or folder_name.strip()
