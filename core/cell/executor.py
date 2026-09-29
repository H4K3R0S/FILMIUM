# ==========          TOOL EXECUTOR          ==========
# Jedina tacka gde domen "dodiruje" sistem — v. 01-ARHITEKTURA/10-mcp-tool-executor.md
# i 01-ARHITEKTURA/05-approval-gates.md (matrica rizika + gate JSON).
#
# Agent/persona NIKAD ne zove `subprocess` direktno. Zove
# `Executor.run(tool, args, ctx)`, koji:
#   (a) proverava allowlist (`config/tools.allow.json`) — nepoznat alat -> greska.
#   (b) klasifikuje rizik LOW/MEDIUM/HIGH/CRITICAL iz allowlist-a.
#   (c) za alate koji ciljaju metu (nmap/nuclei/sqlmap/ffuf/...): proverava da
#       meta ima `authorized:true` + `authorization_ref` + `scope` -> ako ne,
#       AUTO-REJECT, bez gate-a, bez mrezе.
#   (d) LOW -> izvrsava autonomno + audit. MEDIUM -> izvrsava + audit + emit.
#       HIGH/CRITICAL -> NE izvrsava; pravi gate zahtev (core.cell.approvals),
#       best-effort SSE emit `type:"gate"` (token stize covekovom GUI-ju —
#       v. F7a apps/api/routers/<domen>_approvals.py) i vraca AWAITING_APPROVAL.
#   (e) posle SVAKOG izvrsenja: audit atom (`type: log`) u `.ai/atomi/logs/`
#       + best-effort SSE emit (Second Brain `/api/events`).
#
# FAIL-CLOSED svuda: nepoznat alat, nejasna klasifikacija rizika, meta bez
# validnog scope-a, ili bilo kakva nedoumica u proveri -> NE izvrsava se.
# Nejasan/nepoznat rizik iz konfiguracije se tretira kao CRITICAL (najstrozi
# nivo), nikad kao nesto slabije.
#
# Ovaj fajl je DELJEN — identican u sva 4 domena (core/cell/ konvencija, isto
# kao core/cell/database.py). Domenska razlika je ISKLJUCIVO
# `config/tools.allow.json`, ne ovaj kod.
#
# [CAVEAT — namerno NIJE ozicen u ovoj fazi] Postojeci domenski alati
# (core/domains/kalima/security/*, itd.) jos uvek NE prolaze kroz ovaj
# Executor — to je pazljiv per-domen follow-up. Ova faza dokazuje MASINERIJU
# (allowlist, klasifikacija, scope-brana, gate, audit) bezopasnom komandom.
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import time
import unicodedata
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from core.cell.approvals import Approvals, Gate

# ----------          STATUSI          ----------
EXECUTED = "EXECUTED"
AWAITING_APPROVAL = "AWAITING_APPROVAL"
REJECTED = "REJECTED"

_RISK_LEVELS = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
_GATED_RISK = ("HIGH", "CRITICAL")

_DEFAULT_TIMEOUT_S = 30
_MAX_OUTPUT_CHARS = 4000


def _domain_root() -> Path:
    """Koren domena. Ovaj fajl uvek zivi na `<domen>/core/cell/executor.py`."""

    return Path(__file__).resolve().parents[2]


def _default_allowlist_path() -> Path:
    return _domain_root() / "config" / "tools.allow.json"


def _default_logs_dir() -> Path:
    # `.ai/atomi/` je "sigurna putanja" (v. F0-engagement-i-scope.md [CAVEAT])
    # — build_cell je ne prepisuje.
    return _domain_root() / ".ai" / "atomi" / "logs" / "executor"


def _slugify(text: str) -> str:
    """`id = slugify(title)`, tacno pravilo iz 01-atomski-standard-v2.md:
    NFKD + ukloni akcente, mala slova, [^a-z0-9]+ -> "-", trim, max 80."""

    normalized = unicodedata.normalize("NFKD", text)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_only.lower()).strip("-")
    return slug[:80] or "log"


def _describe_command(tool: str, entry: dict | None, args: dict) -> str:
    """Citljiv prikaz komande za covekov pregled u Approval Card-u (F7b).
    Best-effort: ako `args['argv']` nije (jos) lista niski (npr. gate za
    HIGH/CRITICAL nastaje PRE provere oblika u `_execute()`), vraca opis bez
    pucanja — nikad ne baca."""

    argv = args.get("argv")
    if isinstance(argv, list) and all(isinstance(a, str) for a in argv):
        binary = (entry or {}).get("binary") or tool
        return " ".join([str(binary), *argv])
    return f"alat `{tool}` (opis komande nedostupan — args['argv'] nije lista niski)"


# ----------          META (SCOPE)          ----------

@dataclass(frozen=True)
class TargetAsset:
    """Ono sto scope-provera cita — odgovara frontmatter-u `type: target_asset`
    atoma (v. 07-SABLONI/atom-domenski-primeri.md, F0-engagement-i-scope.md).
    Namerno NIJE vezano za fajl-sistem ovde: `asset_lookup` (ubrizgano u
    Executor) je taj koji zna da procita pravi atom. Ovo drzi Executor
    testabilnim bez ijednog fajla na disku, isto kao ScopeGate."""

    id: str
    authorized: bool
    authorization_ref: str = ""
    scope: str = ""
    out_of_scope: tuple[str, ...] = ()


AssetLookup = Callable[[str], "TargetAsset | None"]
Emit = Callable[[dict], None]


def _http_emit(event: dict) -> None:
    """Best-effort SSE emit ka Second Brain (`POST /api/events`, v.
    ~/ai/core-infrastructure/second-brain/server.mjs). Nikad ne puca i nikad
    ne blokira izvrsavanje — GUI ne mora da radi da bi Executor radio.
    Kratak timeout (0.3s) da odsustvo Second Brain-a (npr. u testovima) ne
    uspori nista primetno.
    """
    url = os.environ.get(
        "SECOND_BRAIN_EVENTS_URL", "http://127.0.0.1:4901/api/events"
    )
    try:
        data = json.dumps(event, ensure_ascii=False, default=str).encode("utf-8")
        request = urllib.request.Request(
            url, data=data, headers={"content-type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(request, timeout=0.3).close()
    except Exception:  # noqa: BLE001, S110
        pass


@dataclass(frozen=True)
class Result:
    """Ishod poziva `Executor.run()` / `Executor.execute_approved()`."""

    status: str
    tool: str
    risk: str | None = None
    stdout: str = ""
    stderr: str = ""
    returncode: int | None = None
    gate_id: str | None = None
    token: str | None = None
    reason: str = ""
    audit_path: str | None = None


class Executor:
    """Jedina tacka gde domen "dodiruje" sistem. V. modul-docstring gore."""

    def __init__(
        self,
        *,
        domain: str = "",
        allow_path: Path | None = None,
        logs_dir: Path | None = None,
        approvals: Approvals | None = None,
        asset_lookup: AssetLookup | None = None,
        emit: Emit | None = None,
    ) -> None:
        self._domain = domain
        self._allow_path = allow_path or _default_allowlist_path()
        self._logs_dir = logs_dir or _default_logs_dir()
        self._approvals = approvals if approvals is not None else Approvals()
        self._asset_lookup = asset_lookup
        self._emit = emit if emit is not None else _http_emit

    # ----------          ALLOWLIST + KLASIFIKACIJA          ----------

    def _load_allowlist(self) -> dict:
        """Cita `config/tools.allow.json" iznova svaki put (fajl je mali;
        svezina > brzina — admin moze da promeni allowlist bez restarta).
        Bilo kakva greska u citanju/parsiranju -> prazna allowlist-a
        (FAIL-CLOSED: nista se ne izvrsava dok se konfiguracija ne popravi).
        """
        try:
            raw = self._allow_path.read_text(encoding="utf-8")
        except OSError:
            return {}
        try:
            data = json.loads(raw)
        except ValueError:
            return {}
        tools = data.get("tools") if isinstance(data, dict) else None
        return tools if isinstance(tools, dict) else {}

    def _entry(self, tool: str) -> dict | None:
        entry = self._load_allowlist().get(tool)
        return entry if isinstance(entry, dict) else None

    def classify(self, tool: str) -> tuple[str | None, dict | None, str]:
        """Vraca `(rizik, allowlist-unos, razlog)`.

        `rizik is None` znaci "alat nije na allowlisti" — pozivalac NE SME
        da izvrsi nista u tom slucaju. Nejasan/nepoznat `risk` u konfiguraciji
        se ne odbija tiho — tretira se kao CRITICAL (fail-closed).
        """
        entry = self._entry(tool)
        if entry is None:
            return None, None, f"alat `{tool}` nije na allowlisti (config/tools.allow.json)"

        risk = entry.get("risk")
        if risk not in _RISK_LEVELS:
            return (
                "CRITICAL", entry,
                ("nejasan/nepoznat rizik u konfiguraciji — tretirano kao "
                "CRITICAL (fail-closed)"),
            )
        return risk, entry, ""

    # ----------          SCOPE BRANA          ----------

    def _check_scope(self, entry: dict, args: dict) -> tuple[bool, str]:
        """`(u_scope-u, razlog)`. Vazi SAMO za alate koji ciljaju metu
        (`entry["targets_network"]` istinito) — v. `config/tools.allow.json`.
        Alat bez mete (npr. `sha256sum`, `rg` nad lokalnim uzorkom) prolazi
        bez provere.
        """
        if not entry.get("targets_network"):
            return True, ""

        asset = args.get("target_asset")
        if isinstance(asset, str):
            if self._asset_lookup is None:
                return (
                    False,
                    ("meta je data kao ID ali nema ubrizganog asset_lookup-a "
                    "da je razresi — fail-closed auto-reject"),
                )
            asset = self._asset_lookup(asset)

        if not isinstance(asset, TargetAsset):
            return False, "meta nije pronadjena/nije prepoznata — auto-reject"

        if not asset.authorized or not asset.authorization_ref or not asset.scope:
            return (
                False,
                ("meta nije u autorizovanom scope-u (nedostaje authorized/"
                "authorization_ref/scope) — auto-reject"),
            )

        target = str(args.get("target") or "")
        for oos in asset.out_of_scope:
            if target and (target == oos or (oos.endswith("*") and target.startswith(oos[:-1]))):
                return False, f"meta `{target}` je eksplicitno na out_of_scope listi"

        return True, ""

    # ----------          GLAVNI ULAZ          ----------

    def run(self, tool: str, args: dict | None = None, ctx: dict | None = None) -> Result:
        args = dict(args or {})
        ctx = dict(ctx or {})

        risk, entry, razlog = self.classify(tool)
        if risk is None:
            return Result(status=REJECTED, tool=tool, reason=razlog)

        in_scope, scope_razlog = self._check_scope(entry, args)
        if not in_scope:
            return Result(status=REJECTED, tool=tool, risk=risk, reason=scope_razlog)

        if risk in _GATED_RISK:
            asset = args.get("target_asset")
            scope_ref = asset.id if isinstance(asset, TargetAsset) else str(asset or "")
            gate, token = self._approvals.create_gate(
                tool=tool,
                args=args,
                risk=risk,
                reason=razlog or f"alat rizika {risk} zahteva odobrenje coveka",
                actor=str(ctx.get("actor", "")),
                scope_ref=scope_ref,
            )
            # Best-effort SSE emit ka Second Brain (covekov GUI, poseban
            # proces od onog sto je pozvao run()) — token ide i u ovaj
            # dogadjaj, ne samo u Result ispod. GUI ga cita ovde (SSE), ne iz
            # in-process Result-a, i vraca ga u `POST /{gate_id}/approve`
            # (F7a approvals ruter). To sto agent-pozivalac VEC dobija token
            # u Result-u (nepromenjeno, postojece ponasanje) ne otvara
            # zaobilaznicu — jedini put do izvrsenja je Approvals.approve()
            # sa tacnim tokenom (hmac.compare_digest, fail-closed), a covek
            # je taj koji preko GUI-ja salje approve/reject.
            self._emit({
                "type": "gate",
                "domain": self._domain,
                "gate_id": gate.id,
                "tool": tool,
                "risk": risk,
                "reason": gate.reason,
                "raw_command": _describe_command(tool, entry, args),
                "token": token,
                "expires_in_s": round(gate.expires_at - gate.requested_at),
            })
            return Result(
                status=AWAITING_APPROVAL, tool=tool, risk=risk,
                gate_id=gate.id, token=token, reason=gate.reason,
            )

        return self._execute(
            tool, entry, args, risk,
            actor=str(ctx.get("actor", "")), detail="izvrseno autonomno (LOW/MEDIUM)",
        )

    def execute_approved(self, gate: Gate) -> Result:
        """Izvrsava akciju cija je molba VEC odobrena (`gate.status ==
        'approved'`, dobijeno iz `Approvals.approve()`).

        FAIL-CLOSED: bilo sta drugo osim `approved` -> odbijeno, ne izvrsava
        se nista. Alat se ponovo trazi na allowlisti (mogla je da se promeni
        dok se cekalo covekovu odluku) — nestanak sa allowlist-e posle
        podnosenja molbe ne sme da otvori zaobilaznicu.
        """
        if gate.status != "approved":
            return Result(
                status=REJECTED, tool=gate.tool, risk=gate.risk,
                reason=f"molba nije odobrena (status={gate.status})",
            )

        entry = self._entry(gate.tool)
        if entry is None:
            return Result(
                status=REJECTED, tool=gate.tool, risk=gate.risk,
                reason="alat vise nije na allowlisti — odobrenje ne vazi",
            )

        return self._execute(
            gate.tool, entry, gate.args, gate.risk,
            actor=gate.actor, detail=f"odobreno molbom {gate.id}",
        )

    # ----------          STVARNO IZVRSENJE          ----------

    def _execute(
        self, tool: str, entry: dict, args: dict, risk: str, *, actor: str, detail: str,
    ) -> Result:
        argv = args.get("argv") or []
        if not isinstance(argv, list) or not all(isinstance(a, str) for a in argv):
            return Result(
                status=REJECTED, tool=tool, risk=risk,
                reason="`args['argv']` mora biti lista niski",
            )

        binary = entry.get("binary") or tool
        timeout_s = entry.get("timeout_s")
        if not isinstance(timeout_s, (int, float)) or timeout_s <= 0:
            timeout_s = _DEFAULT_TIMEOUT_S
        command = [str(binary), *argv]

        started = time.time()
        error = None
        try:
            # shell=False je namerno tvrdo — bez interpolacije shell-a nema
            # injekcije kroz argumente alata.
            completed = subprocess.run(
                command, capture_output=True, text=True, timeout=timeout_s, shell=False,
                check=False,
            )
            stdout = completed.stdout[-_MAX_OUTPUT_CHARS:]
            stderr = completed.stderr[-_MAX_OUTPUT_CHARS:]
            returncode = completed.returncode
        except subprocess.TimeoutExpired:
            stdout, stderr, returncode = "", f"istekao timeout od {timeout_s}s", None
            error = "timeout"
        except OSError as greska:
            stdout, stderr, returncode = "", str(greska), None
            error = "os_error"
        duration = time.time() - started

        audit_path = self._write_audit(
            tool=tool, command=command, risk=risk, actor=actor, detail=detail,
            returncode=returncode, duration=duration, error=error,
            stdout=stdout, stderr=stderr,
        )
        self._emit({
            "type": "log", "domain": self._domain, "tool": tool, "risk": risk,
            "status": EXECUTED, "returncode": returncode, "detail": detail,
        })
        return Result(
            status=EXECUTED, tool=tool, risk=risk, stdout=stdout, stderr=stderr,
            returncode=returncode, reason=detail, audit_path=audit_path,
        )

    # ----------          AUDIT ATOM          ----------

    def _write_audit(
        self, *, tool, command, risk, actor, detail, returncode, duration,
        error, stdout, stderr,
    ) -> str:
        """Upisuje `type: log` atom po 01-atomski-standard-v2.md (frontmatter
        + zone tela). `id == slugify(title)` — zlatno pravilo standarda."""

        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        short = hashlib.sha256(f"{tool}{time.time()}".encode()).hexdigest()[:8]
        title = f"Izvrsenje {tool} {short}"
        atom_id = _slugify(title)
        ishod = "greska" if error else "ok"

        telo = (
            "---\n"
            f"id: {atom_id}\n"
            f"title: {title}\n"
            "type: log\n"
            f"domain: {self._domain}\n"
            f"tags: [executor, audit, {risk.lower()}]\n"
            "status: verified\n"
            "source: executor\n"
            f"created: {now}\n"
            "---\n"
            "## 🎯 KONTEKST\n"
            f"Izvrsenje alata `{tool}` (rizik {risk}) preko `core/cell/executor.py`. "
            f"{detail}.\n"
            "## 💻 SADRŽAJ\n"
            f"- komanda: `{' '.join(command)}`\n"
            f"- akter: {actor or '(nepoznat)'}\n"
            f"- povratni kod: {returncode}\n"
            f"- trajanje: {duration:.3f}s\n"
            f"- ishod: {ishod}\n"
            f"- stdout (poslednjih {_MAX_OUTPUT_CHARS} znakova):\n```\n{stdout}\n```\n"
            f"- stderr:\n```\n{stderr}\n```\n"
        )

        self._logs_dir.mkdir(parents=True, exist_ok=True)
        path = self._logs_dir / f"{atom_id}.md"
        path.write_text(telo, encoding="utf-8")
        return str(path)
