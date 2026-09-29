# ========== REGISTAR INTENATA (allowlist) ==========
# Model sme da predloži SAMO ovde nabrojane namere. Sve van ovoga se odbija
# pre bilo kakvog izvršenja — brana protiv izmišljene/opasne komande.
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IntentSpec:
    """Jedna dozvoljena namera i njena pravila."""

    name: str
    is_write: bool          # traži potvrdu pre izvršenja
    is_navigate: bool       # GUI ga izvršava (otvori stranicu + web plejer)
    needs_media: bool       # traži konkretan film (media_id ili naslov za razrešavanje)
    tool: str | None        # ime `tools/<tool>.md` uputstva, ako ga ima
    required_params: tuple[str, ...]


# `media_id` NIJE u required_params za film-namere: model obično da naslov
# ("pusti Matriks"), a agent ga razreši u id (MediaResolver). `needs_media`
# govori agentu da posle razrešavanja mora postojati validan media_id.
INTENTS: dict[str, IntentSpec] = {
    "search": IntentSpec(
        "search", is_write=False, is_navigate=False, needs_media=False,
        tool="pretraga", required_params=(),
    ),
    "navigate": IntentSpec(
        "navigate", is_write=False, is_navigate=True, needs_media=False,
        tool=None, required_params=(),
    ),
    "recommend": IntentSpec(
        "recommend", is_write=False, is_navigate=True, needs_media=False,
        tool=None, required_params=(),
    ),
    # ZAKON domenski agenti §5: agent mora umeti da otvori GUI ekran (Second Brain MAPS).
    "open_second_brain_map": IntentSpec(
        "open_second_brain_map", is_write=False, is_navigate=True, needs_media=False,
        tool=None, required_params=(),
    ),
    "scan_library": IntentSpec(
        "scan_library", is_write=False, is_navigate=False, needs_media=False,
        tool=None, required_params=(),
    ),
    "enrich": IntentSpec(
        "enrich", is_write=False, is_navigate=False, needs_media=True,
        tool=None, required_params=(),
    ),
    "add_to_wishlist": IntentSpec(
        "add_to_wishlist", is_write=True, is_navigate=False, needs_media=False,
        tool=None, required_params=("title",),
    ),
    "info": IntentSpec(
        "info", is_write=False, is_navigate=False, needs_media=False,
        tool=None, required_params=("title",),
    ),
    "play": IntentSpec(
        "play", is_write=False, is_navigate=True, needs_media=True,
        tool="plejer", required_params=(),
    ),
    "play_vlc": IntentSpec(
        "play_vlc", is_write=False, is_navigate=False, needs_media=True,
        tool="plejer", required_params=(),
    ),
    "edit_metadata": IntentSpec(
        "edit_metadata", is_write=True, is_navigate=False, needs_media=True,
        tool="izmena-info", required_params=("changes",),
    ),
    "save": IntentSpec(
        "save", is_write=True, is_navigate=False, needs_media=True,
        tool="izmena-info", required_params=("changes",),
    ),
}


def get_intent(name: str) -> IntentSpec | None:
    """Spec namere po imenu, ili None ako nije na allowlisti."""

    return INTENTS.get(name)


def validate_params(spec: IntentSpec, params: dict) -> list[str]:
    """Imena obaveznih polja kojih nema (prazna lista = validno)."""

    return [key for key in spec.required_params if key not in params]
