"""
Bazni CORE izuzeci (Foundation errors sloj).

Ovaj modul definiše zajedničku hijerarhiju grešaka koju svi slojevi (domeni,
servisi, API) mogu da koriste umesto da svako izmišlja svoje. API sloj mapira
ove izuzetke na jedinstven HTTP error ugovor.
"""


# ==========          BAZNA GREŠKA          ==========

class CoreError(Exception):
    """
    Zajednička osnova za sve CORE greške.

    Nosi tehnički ``code`` (stabilan identifikator za API/logove) i ljudsku
    poruku. Konkretni podtipovi postavljaju podrazumevani kod.
    """

    code: str = "core_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


# ==========          DOMEN GREŠKE          ==========

class DomainNotFoundError(CoreError):
    """Traženi domen ne postoji u registru."""

    code = "domain_not_found"

    def __init__(self, domain_id: str) -> None:
        super().__init__(f"Domen ne postoji: {domain_id}")
        self.domain_id = domain_id


class DomainDisabledError(CoreError):
    """Domen postoji ali je trenutno onemogućen."""

    code = "domain_disabled"

    def __init__(self, domain_id: str) -> None:
        super().__init__(f"Domen je onemogućen: {domain_id}")
        self.domain_id = domain_id


# ==========          VALIDACIJA          ==========

class InvalidValueError(CoreError):
    """Prosleđena vrednost nije prihvatljiva (prazan string, nepodržan format)."""

    code = "invalid_value"
