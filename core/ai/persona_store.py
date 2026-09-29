# ========== PERSONE NA DISKU (uređive .md datoteke) ==========
# Persona je do sada bila tvrdo upisana u kod, pa se nije mogla menjati bez
# izmene programa. Ovde ista persona postaje .md datoteka koju korisnik uređuje
# iz podešavanja.
#
# Podrazumevani tekst i dalje živi u kodu; datoteka nastaje tek kad se persona
# izmeni. Tako „vrati na podrazumevano" znači samo brisanje datoteke, a nova
# verzija programa donosi bolje podrazumevane tekstove svima koji ih nisu menjali.
#
# Svaki opseg ima svoju „global" personu: opšteg pomoćnika tog dela sistema.
# Ista je uloga (podrazumevani sagovornik), ali ne i isti tekst — CORE-ov opšti
# pomoćnik govori o sistemu, CODIUM-ov o razvoju. Jedan zajednički tekst bi u
# CODIUM chatu bio prazna priča, a u CORE-u nepotrebno razvojni.
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from core.ai.personas import PERSONAS as CORE_PERSONAS
from core.ai.personas import Persona
from core.ai.personas import persona_ids as core_persona_ids
from core.foundation.paths import core_paths

# Podrazumevani režim razgovora u svakom opsegu: opšti pomoćnik.
GLOBAL_PERSONA = "global"

# Id sme da bude samo ime datoteke — bez separatora i bez „..".
_ID = re.compile(r"^[a-z0-9][a-z0-9_-]*$")

# Naziv persone je prvi „# naslov" u datoteci; ostatak je sistemski prompt.
_NASLOV = re.compile(r"^\s*#\s+(.+?)\s*$")

_CORE_GLOBAL = Persona(
    id=GLOBAL_PERSONA,
    name="Opšti pomoćnik",
    system=(
        "Ti si opšti pomoćnik CORE jezgra — sagovornik unutar CORE platforme. "
        "Odgovaraj na srpskom jeziku, sažeto i konkretno, bez suvišnog uvoda.\n\n"
        "Uloga: opšti razgovor o sistemu i o svemu ostalom. Poznaješ CORE i "
        "njegove domene (CODIUM, FILMIUM, IMPERIUM, KALIMA), podešavanja, "
        "fajlove i planove, ali pričaj i o temama van sistema kad se to traži. "
        "Ako nešto ne znaš ili nisi siguran, reci to umesto da izmišljaš."
    ),
)

_CODIUM_GLOBAL = Persona(
    id=GLOBAL_PERSONA,
    name="Opšti pomoćnik",
    system=(
        "Ti si opšti razvojni pomoćnik CODIUM domena. Odgovaraj na srpskom "
        "jeziku, sažeto i konkretno, bez suvišnog uvoda. Kod i identifikatore "
        "piši na engleskom; komentare i objašnjenja na srpskom.\n\n"
        "Uloga: široka pomoć u razvoju — kod, arhitektura, greške, alati, "
        "biblioteke, planiranje rada. Ne drži se jedne uske uloge nego pređi "
        "na ono što pitanje traži. Ako nešto nije jasno ili ne znaš, reci to "
        "umesto da izmišljaš."
    ),
)

# FILMIUM ima tačno jedan profil — Kurator. To je „opšti pomoćnik" tog domena
# (podrazumevani i jedini režim razgovora), pa nosi id `global`, a ime „Kurator".
_FILMIUM_KURATOR = Persona(
    id=GLOBAL_PERSONA,
    name="Kurator",
    system=(
        "Ti si Kurator — filmski sagovornik unutar FILMIUM domena CORE "
        "platforme. Odgovaraj na srpskom jeziku, sažeto i konkretno, bez "
        "suvišnog uvoda.\n\n"
        "Uloga: pomoć oko filmske i serijske biblioteke. Preporučuješ naslove "
        "prema ukusu i raspoloženju, objašnjavaš radnju, glumce, režiju i "
        "kontekst, praviš liste i kolekcije, pomažeš oko žanrova, metapodataka, "
        "prevoda i kvaliteta izvora. Govoriš toplo i sa merom, kao dobar "
        "poznavalac filma — bez spojlera osim ako se izričito traže. Ako nešto "
        "ne znaš ili nisi siguran, reci to umesto da izmišljaš."
    ),
)


@lru_cache(maxsize=1)
def _defaults() -> dict[str, dict[str, Persona]]:
    """Podrazumevane persone po opsegu; redosled je i redosled prikaza.

    Domenske persone se uvoze ovde, a ne na vrhu modula: `core.ai` je sloj
    ispod domena, pa bi uvoz na vrhu zatvorio krug (domen → core.ai → domen).
    """

    # Globalna persona je prva u svakom opsegu — i po redosledu i kao izbor.
    return {
        "core": {
            GLOBAL_PERSONA: _CORE_GLOBAL,
            **{pid: CORE_PERSONAS[pid] for pid in core_persona_ids()},
        },
        # FILMIUM: jedan profil (Kurator), pa opseg ima samo globalnu personu.
        "filmium": {
            GLOBAL_PERSONA: _FILMIUM_KURATOR,
        },
    }


@dataclass(frozen=True)
class PersonaDoc:
    """Persona onako kako je vidi ekran podešavanja."""

    id: str
    scope: str
    name: str
    markdown: str
    # True kad postoji datoteka, tj. kad je tekst izmenjen u odnosu na kod.
    customized: bool


def render_markdown(persona: Persona) -> str:
    """Persona kao .md tekst: naslov je naziv, telo je sistemski prompt."""

    return f"# {persona.name}\n\n{persona.system.strip()}\n"


def parse_markdown(persona_id: str, text: str, *, fallback_name: str) -> Persona:
    """Persona iz .md teksta; bez naslova ostaje podrazumevani naziv."""

    linije = text.splitlines()
    naziv = fallback_name
    telo = linije

    for index, linija in enumerate(linije):
        if not linija.strip():
            continue
        poklapanje = _NASLOV.match(linija)
        if poklapanje is not None:
            naziv = poklapanje.group(1)
            telo = linije[index + 1:]
        break

    return Persona(id=persona_id, name=naziv, system="\n".join(telo).strip())


class PersonaStore:
    """Čita i piše persone; podrazumevane vrednosti dolaze iz koda."""

    def __init__(self, root: Path | None = None) -> None:
        self._root = root or (core_paths.config / "personas")

    # ---------- čitanje ----------

    def scopes(self) -> list[str]:
        """Opsezi koji uopšte imaju persone."""

        return list(_defaults())

    def list(self, scope: str) -> list[PersonaDoc]:
        """Persone opsega, počev od globalne (opšti pomoćnik tog opsega)."""

        return [self.get(scope, pid) for pid in _defaults().get(scope, {})]

    def get(self, scope: str, persona_id: str) -> PersonaDoc:
        """Jedna persona sa tekstom; nepoznat par diže KeyError."""

        podrazumevana = self._default(scope, persona_id)
        putanja = self._path(scope, persona_id)

        if putanja.exists():
            tekst = putanja.read_text(encoding="utf-8")
            izmenjena = parse_markdown(
                persona_id, tekst, fallback_name=podrazumevana.name,
            )
            return PersonaDoc(id=persona_id, scope=scope, name=izmenjena.name,
                              markdown=tekst, customized=True)

        return PersonaDoc(id=persona_id, scope=scope, name=podrazumevana.name,
                          markdown=render_markdown(podrazumevana),
                          customized=False)

    def persona(self, scope: str, persona_id: str) -> Persona:
        """Persona za razgovor; nepoznat id pada na opšteg pomoćnika opsega."""

        if persona_id in _defaults().get(scope, {}):
            return self._resolve(scope, persona_id)
        return self._resolve(scope, GLOBAL_PERSONA)

    # ---------- pisanje ----------

    def save(self, scope: str, persona_id: str, markdown: str) -> PersonaDoc:
        """Upisuje izmenjeni tekst persone. Prazan tekst se odbija."""

        podrazumevana = self._default(scope, persona_id)
        if not markdown.strip():
            raise ValueError("Tekst persone ne sme biti prazan.")

        putanja = self._path(scope, persona_id)
        putanja.parent.mkdir(parents=True, exist_ok=True)
        putanja.write_text(markdown, encoding="utf-8")

        izmenjena = parse_markdown(
            persona_id, markdown, fallback_name=podrazumevana.name,
        )
        return PersonaDoc(id=persona_id, scope=scope, name=izmenjena.name,
                          markdown=markdown, customized=True)

    def reset(self, scope: str, persona_id: str) -> PersonaDoc:
        """Briše izmenu i vraća personu na tekst iz koda."""

        self._default(scope, persona_id)
        self._path(scope, persona_id).unlink(missing_ok=True)
        return self.get(scope, persona_id)

    # ---------- interno ----------

    def _default(self, scope: str, persona_id: str) -> Persona:
        opseg = _defaults().get(scope)
        if opseg is None or persona_id not in opseg:
            raise KeyError(f"Nepoznata persona: {scope}/{persona_id}")
        return opseg[persona_id]

    def _resolve(self, scope: str, persona_id: str) -> Persona:
        doc = self.get(scope, persona_id)
        if not doc.customized:
            return self._default(scope, persona_id)
        return parse_markdown(persona_id, doc.markdown, fallback_name=doc.name)

    def _path(self, scope: str, persona_id: str) -> Path:
        # Id i opseg dolaze iz zahteva; bez ove provere bi „../" izašao iz
        # direktorijuma persona i pisao bilo gde.
        if _ID.match(scope) is None or _ID.match(persona_id) is None:
            raise KeyError(f"Nepoznata persona: {scope}/{persona_id}")
        return self._root / scope / f"{persona_id}.md"
