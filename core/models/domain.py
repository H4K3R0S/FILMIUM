from dataclasses import dataclass

# ==========          MANIFEST DOMENA          ==========

@dataclass(frozen=True)
class DomainManifest:
    """
    Definiše trajni identitet i osnovni opis jednog CORE domena.

    Manifest ne sadrži runtime stanje, aktivnost niti poslovnu logiku.
    Svaki domen mora da izloži jednu instancu ovog modela.
    """

    id: str
    name: str
    description: str


# ==========          JAVNI MODEL DOMENA          ==========

@dataclass(frozen=True)
class DomainView:
    """
    Javni prikaz domena koji CORE može da pošalje API-ju ili GUI-ju.

    Ovaj model ne sadrži internu logiku domena.
    Služi kao stabilan oblik podataka za prikaz i komunikaciju između slojeva.
    """

    id: str
    name: str
    description: str
    enabled: bool
    active: bool