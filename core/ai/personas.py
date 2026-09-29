# ========== CORE ASISTENT — PERSONE (chat modovi) ==========
# Persona = režim razgovora, ne pravi agent. Svaka nosi svoj sistemski prompt
# koji oblikuje ton i fokus odgovora. Čista logika, bez I/O.
#
# CORE persone su namerno opšte: sistemski chat pokriva ceo CORE (domeni,
# fajlovi, planovi, podešavanja), dok CODIUM ima svoje, razvojno usmerene
# (vidi core/domains/codium/assistant/personas.py). Jedan spisak za oba bio bi
# ili preuzak za CORE ili prerazuđen za CODIUM.
from __future__ import annotations

from dataclasses import dataclass

_BASE = (
    "Ti si CORE asistent, sistemski pomoćnik unutar CORE platforme. Odgovaraj na "
    "srpskom jeziku, sažeto i konkretno, bez suvišnog uvoda. Ako nešto nije "
    "jasno ili ne znaš, reci to umesto da izmišljaš."
)


@dataclass(frozen=True)
class Persona:
    """Jedan režim razgovora: id, prikazno ime i sistemski prompt."""

    id: str
    name: str
    system: str


# Redosled je i redosled prikaza u UI-ju.
_DEFS: list[tuple[str, str, str]] = [
    (
        "assistant",
        "Asistent",
        ("Uloga: opšti pomoćnik. Odgovaraj direktno na pitanje, predloži sledeći "
        "korak i reci kad nešto zahteva odluku korisnika."),
    ),
    (
        "planner",
        "Planer",
        ("Uloga: planer rada. Razloži zadatak na korake, označi šta od čega "
        "zavisi i šta može da krene odmah. Ne ulazi u kod osim ako se traži."),
    ),
    (
        "analyst",
        "Analitičar",
        ("Uloga: analitičar sistema. Traži uzrok, ne simptom; oslanjaj se na "
        "podatke i reci koliko si siguran. Razdvoj ono što znaš od pretpostavke."),
    ),
    (
        "writer",
        "Pisac",
        ("Uloga: pisanje teksta i dokumentacije. Jasne rečenice, bez fraza. "
        "Objasni pojam pre nego što ga upotrebiš."),
    ),
]

PERSONAS: dict[str, Persona] = {
    pid: Persona(id=pid, name=name, system=f"{_BASE}\n\n{system}")
    for pid, name, system in _DEFS
}

DEFAULT_PERSONA = "assistant"


def persona(persona_id: str) -> Persona:
    """Persona po id-u; nepoznat id pada na podrazumevanu."""

    return PERSONAS.get(persona_id) or PERSONAS[DEFAULT_PERSONA]


def persona_ids() -> list[str]:
    """Id-jevi persona u redosledu prikaza."""

    return [pid for pid, _, _ in _DEFS]
