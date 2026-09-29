# F:\FILMIUM\core\domains\filmium\curator\intent_router.py
# ========== CURATOR AGENT (intent-router) ==========
# Jedan LLM prolaz (fmt=json) mapira poruku u nameru sa allowliste; kod
# deterministički izvršava. Upisi ne diraju bazu iz handle — samo predlog +
# token. Svaka interakcija ide u RAG-log.
from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field

from core.domains.filmium.curator.atoms import AtomLoader
from core.domains.filmium.curator.confirm import ConfirmStore
from core.domains.filmium.curator.executors import Executors
from core.domains.filmium.curator.intents import get_intent, validate_params
from core.domains.filmium.curator.interaction_log import InteractionLog
from core.domains.filmium.curator.media_resolver import MediaResolver

Generate = Callable[..., str]

_SYSTEM = (
    "Ti si FILMIUM Kurator. Iz korisnikove poruke prepoznaj TAČNO jednu nameru "
    "sa spiska i vrati ISKLJUČIVO JSON oblika "
    '{{"intent": "...", "params": {{...}}, "reply": "..."}}. '
    "Dozvoljene namere i primeri:\n{katalog}\n"
    "Ako ne razumeš, vrati intent \"unknown\". Ne izmišljaj namere van spiska."
)


def _je_media_id_ispravan(vrednost: object) -> bool:
    """Da li je `media_id` celobrojan (int ili string koji predstavlja ceo broj).

    Sprečava da nepostojeći/nenumerički `media_id` iz modela padne duboko u
    izvršioca (int() bi tamo bacio ValueError i isplivao kao 500 na API-ju).
    """

    if isinstance(vrednost, bool):
        return False
    if isinstance(vrednost, int):
        return True
    if isinstance(vrednost, str):
        try:
            int(vrednost)
        except ValueError:
            return False
        return True
    return False


@dataclass
class AgentResult:
    kind: str                       # answer | proposal | navigate
    intent: str
    params: dict = field(default_factory=dict)
    reply: str = ""
    preview: dict | None = None
    confirm_token: str | None = None
    sources: list[str] = field(default_factory=list)
    log_id: str | None = None


class CuratorAgent:
    """Prepoznavanje komandi i deterministično izvršenje."""

    def __init__(
        self,
        atoms: AtomLoader,
        executors: Executors,
        confirm: ConfirmStore,
        log: InteractionLog,
        generate: Generate,
        model: str,
        resolver: MediaResolver | None = None,
        retrieve=None,
    ) -> None:
        self._atoms = atoms
        self._executors = executors
        self._confirm = confirm
        self._log = log
        self._generate = generate
        self._model = model
        self._resolver = resolver
        self._retrieve = retrieve

    def handle(self, message: str) -> AgentResult:
        self._log.settle_silent()  # zatvori stare pending pre nove interakcije
        parsed = self._ask_model(message)
        intent_name = parsed.get("intent", "unknown")
        params = parsed.get("params") or {}
        reply = parsed.get("reply") or ""

        spec = get_intent(intent_name)
        if spec is None or validate_params(spec, params):
            return AgentResult(
                kind="answer", intent="unknown",
                reply=reply or "Ne razumem komandu.",
            )

        if spec.needs_media and not _je_media_id_ispravan(params.get("media_id")):
            # Model obično da naslov, ne id — razreši naslov u media_id.
            razresen = self._razresi_media_id(params)
            if razresen is not None:
                params["media_id"] = razresen
            else:
                naslov = params.get("title") or params.get("naslov") or params.get("query")
                # Više jednakih pogodaka (npr. „hunger games" → svi delovi) →
                # ne pogađaj nasumično: prikaži FILTRIRANO baš te naslove da korisnik
                # izabere (isti ?ids= mehanizam kao preporuka).
                kandidati = self._kandidati_media(params)
                if len(kandidati) >= 2:
                    log_id = self._log.record(message, intent_name, params, spec.tool, reply)
                    return AgentResult(
                        kind="navigate", intent="navigate", params={"ids": kandidati},
                        reply=f"Imam više naslova za '{naslov}' — evo ih, izaberi koji:",
                        preview={
                            "route": "/filmium/library",
                            "filters": {"ids": ",".join(str(i) for i in kandidati)},
                        },
                        log_id=log_id,
                    )
                # Naslov nije u biblioteci: za „gledanje" (play) ponudi dodavanje u listu želja.
                if intent_name in ("play", "play_vlc") and naslov:
                    wl = {"title": str(naslov)}
                    preview = self._executors.preview_write(wl, "add_to_wishlist")
                    log_id = self._log.record(message, intent_name, params, spec.tool, reply)
                    if preview.get("in_wishlist"):
                        return AgentResult(
                            kind="answer", intent=intent_name, params=wl, log_id=log_id,
                            reply=f"'{naslov}' je već u tvojoj listi želja.",
                        )
                    token = self._confirm.issue("add_to_wishlist", wl)
                    return AgentResult(
                        kind="proposal", intent="add_to_wishlist", params=wl, reply=(
                            f"Nemam '{naslov}' u biblioteci. Da ga dodam u listu želja?"
                        ),
                        preview=preview, confirm_token=token, log_id=log_id,
                    )
                log_id = self._log.record(
                    message, intent_name, params, spec.tool, reply
                )
                return AgentResult(
                    kind="answer", intent="unknown",
                    reply="Ne razumem tačno koji film — reci naslov jasnije.",
                    log_id=log_id,
                )

        if spec.is_write:
            preview = self._executors.preview_write(params, intent_name)
            token = self._confirm.issue(intent_name, params)
            log_id = self._log.record(message, intent_name, params, spec.tool, reply)
            return AgentResult(
                kind="proposal", intent=intent_name, params=params, reply=reply,
                preview=preview, confirm_token=token, log_id=log_id,
            )

        if spec.is_navigate:
            if intent_name == "navigate":
                out = self._executors.navigate(params)
            elif intent_name == "recommend":
                out = self._executors.recommend(params)
            elif intent_name == "open_second_brain_map":
                out = self._executors.open_second_brain_map(params)
            else:
                out = self._executors.play(params)
            log_id = self._log.record(message, intent_name, params, spec.tool, reply)
            return AgentResult(
                kind="navigate", intent=intent_name, params=params, reply=reply,
                preview=out, log_id=log_id,
            )

        # info — odgovor sa podacima (iz baze ili TMDB) u preview
        if intent_name == "info":
            out = self._executors.info(params)
            log_id = self._log.record(message, intent_name, params, spec.tool, reply)
            return AgentResult(
                kind="answer", intent=intent_name, params=params, reply=reply,
                preview=out, log_id=log_id,
            )

        # search / play_vlc / scan_library — izvrši odmah
        if intent_name == "play_vlc":
            out = self._executors.play_vlc(params)
            sources: list[str] = []
        elif intent_name == "scan_library":
            out = self._executors.scan_library(params)
            sources = []
        elif intent_name == "enrich":
            out = self._executors.enrich(params)
            sources = []
        else:
            out = self._executors.search(params)
            top = out.get("top")
            if top:
                # Jasan top-pogodak → otvori stranicu filma (kao ručni klik).
                # Model zna samo da je „pretraga" pa bi rekao „pretražujem..." —
                # a mi smo zapravo OTVORILI film; zato reply potvrđuje naslov.
                naslov = (out.get("titles") or [""])[0] or str(params.get("query", ""))
                nav_reply = f"Otvaram: {naslov}." if naslov else "Otvaram…"
                log_id = self._log.record(message, intent_name, params, spec.tool, reply)
                return AgentResult(
                    kind="navigate", intent=intent_name, params=params, reply=nav_reply,
                    preview=top, sources=out.get("titles", []), log_id=log_id,
                )
            sources = out.get("titles", [])
        log_id = self._log.record(message, intent_name, params, spec.tool, reply)
        return AgentResult(
            kind="answer", intent=intent_name, params=params, reply=reply,
            sources=sources, log_id=log_id,
        )

    def confirm(self, token: str) -> dict:
        intent_name, params = self._confirm.take(token)
        return self._executors.apply_write(intent_name, params)

    def refute(self, log_id: str | None = None) -> bool:
        return self._log.refute(log_id)

    def _razresi_media_id(self, params: dict) -> int | None:
        """Naslov iz params (`title`/`naslov`/`query`) -> media_id preko resolvera."""

        if self._resolver is None:
            return None
        for kljuc in ("title", "naslov", "query"):
            naslov = params.get(kljuc)
            if isinstance(naslov, str) and naslov.strip():
                nadjen = self._resolver.resolve(naslov)
                if nadjen is not None:
                    return nadjen
        return None

    def _kandidati_media(self, params: dict) -> list[int]:
        """Svi jednako-najbolji pogoci naslova iz params — za filtriran prikaz
        kad je dvosmisleno. Prazno ako resolver nema `candidates` ili nema pogodaka."""

        candidates = getattr(self._resolver, "candidates", None)
        if candidates is None:
            return []
        for kljuc in ("title", "naslov", "query"):
            naslov = params.get(kljuc)
            if isinstance(naslov, str) and naslov.strip():
                nadjeni = list(candidates(naslov))
                if nadjeni:
                    return nadjeni
        return []

    def _ask_model(self, message: str) -> dict:
        system = _SYSTEM.format(katalog=self._atoms.command_catalog())
        system = self._sa_personom(system)
        system = self._sa_kontekstom(system, message)
        try:
            raw = self._generate(self._model, message, system=system, fmt="json")
            return json.loads(raw)
        except (json.JSONDecodeError, ValueError, TypeError):
            return {"intent": "unknown", "params": {}, "reply": ""}

    def _sa_kontekstom(self, system: str, message: str) -> str:
        """Doda blok relevantnog konteksta iz RAG-a ako retriever postoji.
        Greška/nedostupnost retrievera je bezopasna — vrati prompt kao pre."""
        if self._retrieve is None:
            return system
        try:
            fn = getattr(self._retrieve, "retrieve", self._retrieve)
            isecci = fn(message) or []
        except Exception:  # noqa: BLE001
            return system
        if not isecci:
            return system
        blok = "\n".join(f"- {s}" for s in isecci)
        return f"{system}\n\nRelevantan kontekst iz memorije:\n{blok}"

    def _sa_personom(self, system: str) -> str:
        """Prefiksuje sistemski prompt tekstom aktivne persone (ton/rezon).
        Persona oblikuje glas `reply` polja; instrukcija za JSON ostaje ispod.
        Nedostatak persona.md je bezopasan — vrati prompt kao pre."""
        try:
            persona = self._atoms.persona().body.strip()
        except Exception:  # noqa: BLE001
            persona = ""
        if not persona:
            return system
        return f"{persona}\n\n{system}"
