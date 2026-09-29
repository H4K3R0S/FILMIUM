from collections.abc import Iterable

# ==========          KANONSKI ŽANROVI          ==========

# Jedinstveni izvor istine za nazive žanrova. Mora se poklapati sa seed-om
# u migracijama (filmium_genres tabela). Sve u sistemu (GUI, baza, TMDB
# obogaćivanje) koristi isključivo ove kanonske srpske nazive.
CANONICAL_GENRES: tuple[str, ...] = (
    "Akcija",
    "Animacija",
    "Anime",
    "Avantura",
    "Biografski",
    "Dokumentarni",
    "Drama",
    "Fantazija",
    "Horor",
    "Istorijski",
    "Katastrofa",
    "Komedija",
    "Kratki film",
    "Kriminalistički",
    "Mračna komedija",
    "Misterija",
    "Muzički",
    "Naučna fantastika",
    "Noar",
    "Porodični",
    "Post-apokalipsa",
    "Psihološki",
    "Ratni",
    "Rijaliti",
    "Romansa",
    "Sapunica",
    "Slešer",
    "Sportski",
    "Superheroj",
    "Špijunski",
    "Triler",
    "TV film",
    "Vestern",
    "Vesti",
)

_CANONICAL_BY_KEY: dict[str, str] = {
    genre.casefold(): genre for genre in CANONICAL_GENRES
}


# ==========          ALIASI ŽANROVA (EN + SR)          ==========

# Preslikava engleske (TMDB) i srpske varijante (sa/bez dijakritike) na
# kanonski naziv. Vrednosti MORAJU biti u CANONICAL_GENRES.
GENRE_ALIASES: dict[str, str] = {
    # --- Akcija ---
    "action": "Akcija",
    "action & adventure": "Akcija",
    "akcioni": "Akcija",
    # --- Animacija ---
    "animation": "Animacija",
    "animated": "Animacija",
    "animirani": "Animacija",
    "crtani": "Animacija",
    # --- Anime ---
    "anime": "Anime",
    # --- Avantura ---
    "adventure": "Avantura",
    "avanturisticki": "Avantura",
    "avanturistički": "Avantura",
    # --- Biografski ---
    "biography": "Biografski",
    "biographical": "Biografski",
    "biografija": "Biografski",
    # --- Dokumentarni ---
    "documentary": "Dokumentarni",
    "dokumentarac": "Dokumentarni",
    # --- Drama ---
    "drama": "Drama",
    # --- Fantazija ---
    "fantasy": "Fantazija",
    "fantastika": "Fantazija",
    # --- Horor ---
    "horror": "Horor",
    # --- Istorijski ---
    "history": "Istorijski",
    "historical": "Istorijski",
    "istorija": "Istorijski",
    # --- Katastrofa ---
    "disaster": "Katastrofa",
    "catastrophe": "Katastrofa",
    "katastrofa": "Katastrofa",
    # --- Komedija ---
    "comedy": "Komedija",
    # --- Kratki film ---
    "short": "Kratki film",
    "short film": "Kratki film",
    "kratkometražni": "Kratki film",
    "kratkometrazni": "Kratki film",
    # --- Kriminalistički ---
    "crime": "Kriminalistički",
    "kriminalisticki": "Kriminalistički",
    "krimi": "Kriminalistički",
    # --- Mračna komedija ---
    "dark comedy": "Mračna komedija",
    "black comedy": "Mračna komedija",
    "crna komedija": "Mračna komedija",
    "mracna komedija": "Mračna komedija",
    # --- Misterija ---
    "mystery": "Misterija",
    # --- Muzički ---
    "music": "Muzički",
    "musical": "Muzički",
    "muzicki": "Muzički",
    "mjuzikl": "Muzički",
    # --- Naučna fantastika ---
    "sci-fi": "Naučna fantastika",
    "sci fi": "Naučna fantastika",
    "scifi": "Naučna fantastika",
    "science fiction": "Naučna fantastika",
    "science-fiction": "Naučna fantastika",
    "sci-fi & fantasy": "Naučna fantastika",
    "sf": "Naučna fantastika",
    "naucna fantastika": "Naučna fantastika",
    "naučno-fantastični": "Naučna fantastika",
    # --- Noar ---
    "noir": "Noar",
    "film noir": "Noar",
    "film-noir": "Noar",
    "noar": "Noar",
    # --- Porodični ---
    "family": "Porodični",
    "kids": "Porodični",
    "porodicni": "Porodični",
    # --- Post-apokalipsa ---
    "post-apocalyptic": "Post-apokalipsa",
    "post apocalyptic": "Post-apokalipsa",
    "postapocalypse": "Post-apokalipsa",
    "postapokalipsa": "Post-apokalipsa",
    # --- Psihološki ---
    "psychological": "Psihološki",
    "psychological thriller": "Psihološki",
    "psiholoski": "Psihološki",
    # --- Ratni ---
    "war": "Ratni",
    "war & politics": "Ratni",
    "ratni film": "Ratni",
    # --- Rijaliti ---
    "reality": "Rijaliti",
    "reality-tv": "Rijaliti",
    "reality tv": "Rijaliti",
    "rijaliti": "Rijaliti",
    # --- Romansa ---
    "romance": "Romansa",
    "romantic": "Romansa",
    "romantika": "Romansa",
    "ljubavni": "Romansa",
    # --- Sapunica ---
    "soap": "Sapunica",
    "soap opera": "Sapunica",
    "sapunica": "Sapunica",
    # --- Slešer ---
    "slasher": "Slešer",
    "sleser": "Slešer",
    # --- Sportski ---
    "sport": "Sportski",
    "sports": "Sportski",
    # --- Superheroj ---
    "superhero": "Superheroj",
    "super hero": "Superheroj",
    "superheroj": "Superheroj",
    # --- Špijunski ---
    "spy": "Špijunski",
    "espionage": "Špijunski",
    "spijunski": "Špijunski",
    # --- Triler ---
    "thriller": "Triler",
    # --- TV film ---
    "tv movie": "TV film",
    "tv-movie": "TV film",
    "televizijski film": "TV film",
    "tv film": "TV film",
    # --- Vestern ---
    "western": "Vestern",
    # --- Vesti ---
    "news": "Vesti",
    "vesti": "Vesti",
}


# ==========          KANONIZACIJA (samostalna)          ==========

def canonical_genre(name: str) -> str | None:
    """
    Vraća kanonski srpski naziv žanra za dati unos (EN ili SR), ili
    ``None`` ako naziv nije poznat. Ne zavisi od baze.
    """

    key = name.strip().casefold()
    if not key:
        return None

    direct = _CANONICAL_BY_KEY.get(key)
    if direct is not None:
        return direct

    alias_target = GENRE_ALIASES.get(key)
    if alias_target is not None:
        return _CANONICAL_BY_KEY.get(alias_target.casefold())

    return None


def canonicalize_genres(names: Iterable[str]) -> tuple[str, ...]:
    """
    Preslikava listu naziva (EN/SR) na kanonske žanrove, izbacuje
    nepoznate i duplikate (čuva redosled prvog pojavljivanja).
    """

    canonical: dict[str, str] = {}
    for name in names:
        resolved = canonical_genre(name)
        if resolved is not None:
            canonical.setdefault(resolved.casefold(), resolved)
    return tuple(canonical.values())


# ==========          NORMALIZACIJA ŽANROVA (baza)          ==========

def normalize_genres(
    requested_genres: Iterable[str],
    active_genres: Iterable[str],
) -> tuple[str, ...]:
    """
    Pretvara izabrane žanrove u kanonske vrednosti registra.

    Raises:
        ValueError: Ako naziv nije aktivan žanr niti poznati alias.
    """

    active_genres_by_key = {
        genre.casefold(): genre
        for genre in active_genres
    }
    normalized_genres: dict[str, str] = {}

    for genre in requested_genres:
        normalized_genre = genre.strip()

        if not normalized_genre:
            continue

        if len(normalized_genre) > 50:
            raise ValueError(
                "Naziv žanra ne može imati više od 50 karaktera."
            )

        genre_key = normalized_genre.casefold()
        canonical_genre_name = active_genres_by_key.get(genre_key)

        if canonical_genre_name is None:
            alias_target = GENRE_ALIASES.get(genre_key)

            if alias_target is not None:
                canonical_genre_name = active_genres_by_key.get(
                    alias_target.casefold()
                )

        if canonical_genre_name is None:
            raise ValueError(
                f"FILMIUM žanr nije dozvoljen: {normalized_genre}"
            )

        normalized_genres.setdefault(
            canonical_genre_name.casefold(),
            canonical_genre_name,
        )

    return tuple(normalized_genres.values())
