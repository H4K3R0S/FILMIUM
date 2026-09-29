from dataclasses import dataclass

# ==========          JEZIK          ==========

@dataclass(frozen=True)
class LanguageOption:
    """Jedna kontrolisana opcija koju FILMIUM prikazuje u izboru jezika."""

    code: str
    name: str


# ==========          KATALOG JEZIKA          ==========

FILMIUM_LANGUAGE_OPTIONS = (
    LanguageOption("sr", "Srpski"),
    LanguageOption("sr-Latn", "Srpski - latinica"),
    LanguageOption("sr-Cyrl", "Srpski - ćirilica"),
    LanguageOption("en", "Engleski"),
    LanguageOption("hr", "Hrvatski"),
    LanguageOption("bs", "Bosanski"),
    LanguageOption("sl", "Slovenački"),
    LanguageOption("mk", "Makedonski"),
    LanguageOption("bg", "Bugarski"),
    LanguageOption("de", "Nemački"),
    LanguageOption("fr", "Francuski"),
    LanguageOption("it", "Italijanski"),
    LanguageOption("es", "Španski"),
    LanguageOption("pt", "Portugalski"),
    LanguageOption("ru", "Ruski"),
    LanguageOption("uk", "Ukrajinski"),
    LanguageOption("pl", "Poljski"),
    LanguageOption("cs", "Češki"),
    LanguageOption("sk", "Slovački"),
    LanguageOption("hu", "Mađarski"),
    LanguageOption("ro", "Rumunski"),
    LanguageOption("el", "Grčki"),
    LanguageOption("tr", "Turski"),
    LanguageOption("ja", "Japanski"),
    LanguageOption("ko", "Korejski"),
    LanguageOption("zh", "Kineski"),
    LanguageOption("ar", "Arapski"),
)