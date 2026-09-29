"""Prepoznavanje jezika prevoda iz naziva fajla i iz sadržaja.

Najpouzdaniji signal je poslednji segment posle tačke — ISO 639-2 (B)
troslovni kod, npr. ``Français (France).fre`` → ``fre``. Podržani su i
goli troslovni/dvoslovni kodovi (``dan``, ``sv``) i uobičajena imena
jezika. Kada naziv ne otkriva jezik, čita se sadržaj titla i jezik se
prepoznaje po pismu i po učestalim rečima.
"""

import re
from pathlib import Path

# ==========          ISO 639-2 (B) KODOVI          ==========

# Ključ je kod iz naziva fajla; vrednost je kanonski (B) oblik.
_CANONICAL_CODES: dict[str, str] = {
    "eng": "eng",
    "fre": "fre", "fra": "fre",
    "ger": "ger", "deu": "ger",
    "spa": "spa",
    "ita": "ita",
    "por": "por",
    "rus": "rus",
    "ukr": "ukr",
    "pol": "pol",
    "cze": "cze", "ces": "cze",
    "slo": "slo", "slk": "slo",
    "slv": "slv",
    "hun": "hun",
    "rum": "rum", "ron": "rum",
    "gre": "gre", "ell": "gre",
    "tur": "tur",
    "dut": "dut", "nld": "dut",
    "dan": "dan",
    "nor": "nor", "nob": "nor", "nno": "nor",
    "swe": "swe",
    "fin": "fin",
    "est": "est",
    "lav": "lav",
    "lit": "lit",
    "bul": "bul",
    "hrv": "hrv",
    "srp": "srp",
    "bos": "bos",
    "mac": "mac", "mkd": "mac",
    "alb": "alb", "sqi": "alb",
    "ara": "ara",
    "heb": "heb",
    "hin": "hin",
    "tha": "tha",
    "vie": "vie",
    "kor": "kor",
    "chi": "chi", "zho": "chi",
    "jpn": "jpn",
    "ind": "ind",
    "may": "may", "msa": "may",
    "ice": "ice", "isl": "ice",
    "cat": "cat",
    "gle": "gle",
}


# ==========          ISO 639-1 (dvoslovni) → 639-2 (B)          ==========

_TWO_LETTER_CODES: dict[str, str] = {
    "fr": "fre", "de": "ger", "es": "spa", "it": "ita", "pt": "por",
    "ru": "rus", "uk": "ukr", "pl": "pol", "cs": "cze", "sk": "slo",
    "sl": "slv", "hu": "hun", "ro": "rum", "el": "gre", "tr": "tur",
    "nl": "dut", "da": "dan", "no": "nor", "sv": "swe", "fi": "fin",
    "et": "est", "lv": "lav", "lt": "lit", "bg": "bul", "hr": "hrv",
    "bs": "bos", "mk": "mac", "sq": "alb", "ar": "ara", "he": "heb",
    "hi": "hin", "th": "tha", "vi": "vie", "ko": "kor", "zh": "chi",
    "ja": "jpn", "id": "ind", "ms": "may", "is": "ice",
}


# ==========          IMENA JEZIKA → KOD          ==========

# Engleski i srpski se zadržavaju u sistemskom obliku (``en``), dok ostali
# koriste troslovni kod radi doslednosti sa nazivima fajlova.
_LANGUAGE_NAMES: dict[str, str] = {
    "english": "en",
    "serbian": "sr", "srpski": "sr", "српски": "sr",
    "français": "fre", "francais": "fre", "french": "fre",
    "español": "spa", "espanol": "spa", "spanish": "spa",
    "deutsch": "ger", "german": "ger",
    "italiano": "ita", "italian": "ita",
    "português": "por", "portugues": "por", "portuguese": "por",
    "русский": "rus", "russian": "rus",
    "українська": "ukr", "ukrainian": "ukr",
    "polski": "pol", "polish": "pol",
    "čeština": "cze", "cestina": "cze", "czech": "cze",
    "slovenčina": "slo", "slovencina": "slo", "slovak": "slo",
    "slovenščina": "slv", "slovenscina": "slv", "slovenian": "slv",
    "magyar": "hun", "hungarian": "hun",
    "română": "rum", "romana": "rum", "romanian": "rum",
    "ελληνικά": "gre", "greek": "gre",
    "türkçe": "tur", "turkce": "tur", "turkish": "tur",
    "nederlands": "dut", "dutch": "dut",
    "dansk": "dan", "danish": "dan",
    "norsk": "nor", "norwegian": "nor",
    "svenska": "swe", "swedish": "swe",
    "suomi": "fin", "finnish": "fin",
    "eesti": "est", "estonian": "est",
    "latviešu": "lav", "latviesu": "lav", "latvian": "lav",
    "lietuvių": "lit", "lietuviu": "lit", "lithuanian": "lit",
    "български": "bul", "bulgarian": "bul",
    "hrvatski": "hrv", "croatian": "hrv",
    "bosanski": "bos", "bosnian": "bos",
    "العربية": "ara", "arabic": "ara",
    "עברית": "heb", "hebrew": "heb",
    "हिन्दी": "hin", "hindi": "hin",
    "ไทย": "tha", "thai": "tha",
    "tiếng việt": "vie", "vietnamese": "vie",
    "한국어": "kor", "korean": "kor",
    "中文（简体）": "chi", "中文（繁體）": "chi", "chinese": "chi",
    "bahasa indonesia": "ind", "indonesian": "ind",
    "bahasa melayu": "may", "malay": "may",
}


def _resolve_token(token: str) -> str | None:
    token = token.strip().casefold()

    if not token:
        return None

    if token in _CANONICAL_CODES:
        return _CANONICAL_CODES[token]

    if token in _TWO_LETTER_CODES:
        return _TWO_LETTER_CODES[token]

    if token in _LANGUAGE_NAMES:
        return _LANGUAGE_NAMES[token]

    return None


# Kodovi u nazivu fajla koji se drže u sistemskom obliku (en / sr / sr-Latn).
_FILENAME_ALIASES: dict[str, str] = {
    "en": "en",
    "eng": "en",
    "rs": "sr",
    "sr": "sr",
    "srb": "sr",
    "sr-latn": "sr-Latn",
    "sr-latin": "sr-Latn",
    "und": "und",
}

_FILENAME_SUFFIX = re.compile(
    r"(?:^|[.\- ])(sr-latn|sr-latin|srb|sr|rs|eng|en|und)$",
)


def resolve_subtitle_language(path: Path) -> str | None:
    """Jedinstveno prepoznavanje jezika prevoda (naziv → ISO → sadržaj).

    Isti postupak koriste i filmski i serijski skener:
    1) sufiks naziva (``.eng`` → ``en``, ``.sr`` → ``sr``, ``.sr-latn``);
    2) ISO 639 kod ili ime jezika iz naziva;
    3) prepoznavanje iz sadržaja titla kada naziv ne pomaže.
    """

    normalized_stem = path.stem.casefold().replace("_", "-")
    match = _FILENAME_SUFFIX.search(normalized_stem)
    if match is not None:
        return _FILENAME_ALIASES[match.group(1)]

    from_name = detect_subtitle_language(path.stem)
    if from_name is not None:
        return from_name

    return read_subtitle_language(path)


def detect_subtitle_language(stem: str) -> str | None:
    """Vraća jezik prevoda iz naziva (bez ekstenzije) ili ``None``."""

    lowered = stem.strip().casefold()

    if not lowered:
        return None

    # 1) Poslednji segment posle tačke je najčešće ISO kod ("...(France).fre").
    if "." in lowered:
        code = _resolve_token(lowered.rsplit(".", 1)[-1])
        if code is not None:
            return code

    # 2) Ceo naziv je kod ili ime jezika ("dan", "swe", "English", "dansk").
    code = _resolve_token(lowered)
    if code is not None:
        return code

    # 3) Poslednji token u nazivu ("2_English" → en, "17_nor" → nor,
    #    "22_slo" → slo). Gleda se samo poslednji token da se ne bi pobrkao
    #    sa nazivom epizode ("1 - Out of Time").
    tokens = [token for token in re.split(r"[\s._\-]+", lowered) if token]
    if tokens:
        return _resolve_token(tokens[-1])

    return None


# ==========          DETEKCIJA IZ SADRŽAJA          ==========

# Uobičajene reči po jeziku (latinično pismo). Namerno kratke i česte
# liste — dovoljne za razlikovanje jezika po učestalosti.
_STOPWORDS: dict[str, frozenset[str]] = {
    "en": frozenset({
        "the", "and", "you", "that", "was", "for", "are", "with",
        "his", "they", "this", "have", "from", "not", "but", "what",
        "all", "were", "when", "your", "can", "said", "there", "been",
        "would", "him", "her", "she", "how", "out", "get", "just",
        "know", "like", "yeah", "okay", "here", "now", "who", "will",
        "did", "got", "them", "then", "come", "want", "one",
    }),
    "fre": frozenset({
        "le", "la", "les", "de", "un", "une", "et", "est", "que",
        "qui", "ne", "pas", "vous", "je", "tu", "il", "elle", "nous",
        "pour", "dans", "ce", "des", "du", "au", "avec", "sur", "mais",
        "comme", "ils", "son", "sa", "ses", "tout", "plus", "bien",
        "oui", "non", "moi", "fait", "être", "avez",
    }),
    "ger": frozenset({
        "der", "die", "das", "und", "ist", "ich", "nicht", "sie",
        "den", "ein", "eine", "mit", "auf", "für", "war", "aber",
        "wie", "wir", "was", "haben", "sind", "dass", "auch", "noch",
        "nur", "hier", "ja", "nein", "mir", "mich", "dir", "sich",
    }),
    "spa": frozenset({
        "que", "de", "la", "el", "en", "los", "las", "un", "una",
        "por", "con", "no", "se", "su", "para", "es", "al", "lo",
        "como", "más", "pero", "sus", "le", "ya", "si", "porque",
        "esta", "son", "está", "bien", "sí", "aquí", "yo", "muy",
    }),
    "ita": frozenset({
        "che", "di", "la", "il", "un", "una", "per", "con", "non",
        "sono", "mi", "ti", "ci", "lo", "le", "gli", "questo", "come",
        "più", "ma", "se", "io", "tu", "lei", "noi", "voi", "sì",
        "bene", "qui", "cosa", "fare", "hai", "sei",
    }),
    "por": frozenset({
        "que", "de", "não", "um", "uma", "os", "as", "para", "com",
        "por", "como", "mais", "mas", "seu", "sua", "ele", "ela",
        "você", "isso", "aqui", "sim", "bem", "está", "são", "tudo",
        "nada", "meu", "minha", "vamos",
    }),
    "dut": frozenset({
        "de", "het", "een", "en", "van", "ik", "je", "niet", "dat",
        "is", "op", "te", "dan", "zijn", "er", "maar", "wat", "hier",
        "voor", "met", "als", "ook", "nog", "naar", "wel", "heb",
        "heeft", "moet", "kan", "gaan",
    }),
    "swe": frozenset({
        "och", "att", "det", "som", "en", "är", "på", "för", "med",
        "inte", "jag", "du", "han", "hon", "vi", "har", "kan", "här",
        "men", "om", "vad", "så", "ett", "till", "när", "vill",
    }),
    "pol": frozenset({
        "nie", "to", "się", "na", "że", "jest", "co", "tak", "jak",
        "ale", "mnie", "cię", "tego", "jestem", "tu", "ja", "ty",
        "my", "dla", "przez", "już", "tylko", "może", "jego",
    }),
    "sr-Latn": frozenset({
        "ne", "je", "da", "se", "na", "ti", "to", "za", "od", "ali",
        "ako", "što", "kao", "sam", "smo", "ste", "su", "me", "mi",
        "mu", "ga", "sve", "već", "hoću", "gde", "dobro", "treba",
        "ima", "nije", "koji", "ovo", "ovde", "jesi", "biće",
    }),
}


def _script_of_char(character: str, point: int) -> str | None:
    """Pismo jednog znaka (Unicode raspon) ili None za nebitno."""

    if 0x0370 <= point <= 0x03FF:
        return "gre"
    if 0x0400 <= point <= 0x04FF:
        return "cyr"
    if 0x0590 <= point <= 0x05FF:
        return "heb"
    if 0x0600 <= point <= 0x06FF:
        return "ara"
    if 0x0E00 <= point <= 0x0E7F:
        return "tha"
    if 0xAC00 <= point <= 0xD7A3:
        return "kor"
    if 0x3040 <= point <= 0x30FF:
        return "jpn"
    if 0x4E00 <= point <= 0x9FFF:
        return "han"
    if character.isascii() and character.isalpha():
        return "lat"
    return None


def _cyrillic_language(text: str) -> str:
    """Razlikuje srpsku i ukrajinsku ćirilicu od ruske po specifičnim slovima."""

    if any(character in text for character in "ђћџњљјЂЋЏЊЉЈ"):
        return "sr"
    if any(character in text for character in "їієґІЇЄҐ"):
        return "ukr"
    return "rus"


def _script_language(text: str) -> str | None:
    """Vraća jezik na osnovu preovlađujućeg pisma (za ne-latinična)."""

    counts: dict[str, int] = {}

    for character in text:
        key = _script_of_char(character, ord(character))
        if key:
            counts[key] = counts.get(key, 0) + 1

    if not counts:
        return None

    dominant = max(counts, key=lambda key: counts[key])

    if dominant == "lat" or counts[dominant] < 12:
        return None

    if dominant == "cyr":
        return _cyrillic_language(text)

    if dominant == "jpn":
        return "jpn"

    if dominant == "han":
        return "chi"

    return dominant


def detect_language_from_text(text: str) -> str | None:
    """Prepoznaje jezik prevoda iz samog teksta (kad naziv ne pomaže)."""

    script = _script_language(text)
    if script is not None:
        return script

    words = re.findall(r"[a-zàáâäćčđèéêëìíîïñòóôöšùúûüýžœ]+", text.lower())

    if len(words) < 15:
        return None

    unique_sample = set(words[:1500])
    best_language: str | None = None
    best_score = 0

    for language, stopwords in _STOPWORDS.items():
        score = sum(1 for word in unique_sample if word in stopwords)

        if score > best_score:
            best_score = score
            best_language = language

    # Bar nekoliko pogodaka da bismo bili sigurni.
    return best_language if best_score >= 4 else None


def _attempt_decode(raw: bytes, encoding: str) -> str | None:
    """Pokusaj dekodiranja jednim kodiranjem; None ako ne uspe."""

    try:
        return raw.decode(encoding)
    except UnicodeDecodeError:
        return None


def _decode_subtitle(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1252"):
        decoded = _attempt_decode(raw, encoding)
        if decoded is not None:
            return decoded

    return raw.decode("latin-1", errors="replace")


def read_subtitle_language(path: Path) -> str | None:
    """Čita početak titla i prepoznaje jezik iz sadržaja (ili ``None``)."""

    try:
        with path.open("rb") as handle:
            raw = handle.read(200_000)
    except OSError:
        return None

    if not raw:
        return None

    return detect_language_from_text(_decode_subtitle(raw))
