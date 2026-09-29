# ==========          RED ODOBRENJA (APPROVALS)          ==========
# Generalizacija CODIUM obrasca (core/domains/codium/audit/approvals.py +
# tabela `codium_approvals`, video ih F5-analiza) na DELJENI cell-nivo: bilo
# koji domen sme da trazi odobrenje za HIGH/CRITICAL akciju, ne samo
# agent-petlja CODIUM-a. Ovaj fajl je identican u sva 4 domena
# (core/cell/ je deljeni sloj — v. core/cell/database.py za isti obrazac).
#
# FAIL-CLOSED svuda:
#   - nepoznat/pogresan token -> NIKAD odobreno.
#   - istekla molba -> NIKAD odobrena, makar token bio tacan.
#   - vec odlucena molba (approved/rejected/expired) -> druga odluka je no-op
#     (isto pravilo kao CODIUM: `WHERE status='pending'` u UPDATE-u).
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from pathlib import Path

from core.database.connection import core_database_connection

# ----------          STATUSI          ----------
PENDING = "pending"
APPROVED = "approved"
REJECTED = "rejected"
EXPIRED = "expired"

_VALID_STATUS = (PENDING, APPROVED, REJECTED, EXPIRED)
_VALID_RISK = ("LOW", "MEDIUM", "HIGH", "CRITICAL")

# Podrazumevani rok za odobrenje (v. 01-ARHITEKTURA/05-approval-gates.md
# primer JSON-a: "expires_in_s": 120).
DEFAULT_EXPIRES_IN_S = 120

_SCHEMA = """
CREATE TABLE IF NOT EXISTS approvals (
    id           TEXT PRIMARY KEY,
    tool         TEXT NOT NULL,
    args_json    TEXT NOT NULL DEFAULT '{}',
    risk         TEXT NOT NULL CHECK (risk IN ('LOW','MEDIUM','HIGH','CRITICAL')),
    reason       TEXT NOT NULL DEFAULT '',
    actor        TEXT NOT NULL DEFAULT '',
    scope_ref    TEXT NOT NULL DEFAULT '',
    token_hash   TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'pending'
                 CHECK (status IN ('pending','approved','rejected','expired')),
    note         TEXT NOT NULL DEFAULT '',
    requested_at REAL NOT NULL,
    expires_at   REAL NOT NULL,
    decided_at   REAL
)
"""

_INDEX = (
    "CREATE INDEX IF NOT EXISTS idx_approvals_status "
    "ON approvals (status, requested_at)"
)


def _domain_root() -> Path:
    """Koren domena. Ovaj fajl uvek zivi na `<domen>/core/cell/approvals.py`,
    pa je `parents[2]` uvek koren — bez obzira u kom je domenu kopija."""

    return Path(__file__).resolve().parents[2]


def _default_database_path() -> Path:
    """Zaseban fajl (`data/approvals.db`), ne glavna domenska baza — molbe
    ne zavise od domenskih migracija (v. 10-mcp-tool-executor.md [FaN])."""

    return _domain_root() / "data" / "approvals.db"


@dataclass(frozen=True)
class Gate:
    """Jedna molba za odobrenje HIGH/CRITICAL akcije ("odobrena akcija" kad
    je `status == 'approved'` — sadrzi tacno ono sto treba izvrsiti)."""

    id: str
    tool: str
    args: dict
    risk: str
    reason: str
    actor: str
    scope_ref: str
    status: str
    note: str
    requested_at: float
    expires_at: float
    decided_at: float | None

    @property
    def expired(self) -> bool:
        return time.time() > self.expires_at


def _row_to_gate(row) -> Gate:
    return Gate(
        id=row["id"],
        tool=row["tool"],
        args=json.loads(row["args_json"] or "{}"),
        risk=row["risk"],
        reason=row["reason"],
        actor=row["actor"],
        scope_ref=row["scope_ref"],
        status=row["status"],
        note=row["note"],
        requested_at=row["requested_at"],
        expires_at=row["expires_at"],
        decided_at=row["decided_at"],
    )


def _new_gate_id(risk: str) -> str:
    return f"gate_{secrets.token_hex(8)}_{risk.lower()}"


def _new_token() -> str:
    """"SHA256 token" — heksa otisak slucajne 256-bitne tajne.

    Vraca se pozivaocu TACNO JEDNOM (pri kreiranju). U bazi se cuva samo
    `sha256(token)` (dupli otisak) — kompromitovana baza sama po sebi ne daje
    upotrebljiv token, isto kao hash lozinke.
    """
    return hashlib.sha256(secrets.token_bytes(32)).hexdigest()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class Approvals:
    """Red cekanja za HIGH/CRITICAL akcije. SQLite u `data/approvals.db`."""

    def __init__(self, database_path: Path | None = None) -> None:
        self._database_path = database_path or _default_database_path()
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with core_database_connection(self._database_path) as connection:
            connection.execute(_SCHEMA)
            connection.execute(_INDEX)

    # ----------          PISANJE          ----------

    def create_gate(
        self,
        *,
        tool: str,
        args: dict,
        risk: str,
        reason: str,
        actor: str = "",
        scope_ref: str = "",
        expires_in_s: int = DEFAULT_EXPIRES_IN_S,
    ) -> tuple[Gate, str]:
        """Pravi molbu; vraca `(Gate, token)`.

        Token se NIGDE vise ne moze procitati iz ove klase — pozivalac (GUI/
        test) mora da ga sacuva sam, isto kao API kljuc.
        """
        if risk not in _VALID_RISK:
            raise ValueError(f"nepoznat nivo rizika: {risk!r}")

        gate_id = _new_gate_id(risk)
        token = _new_token()
        now = time.time()

        with core_database_connection(self._database_path) as connection:
            connection.execute(
                "INSERT INTO approvals "
                "(id, tool, args_json, risk, reason, actor, scope_ref, "
                " token_hash, status, requested_at, expires_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)",
                (
                    gate_id, tool, json.dumps(args, ensure_ascii=False, default=str),
                    risk, reason, actor, scope_ref, _hash_token(token),
                    now, now + expires_in_s,
                ),
            )
        return self.get(gate_id), token

    # ----------          CITANJE          ----------

    def get(self, gate_id: str) -> Gate | None:
        with core_database_connection(self._database_path) as connection:
            row = connection.execute(
                "SELECT * FROM approvals WHERE id = ?", (gate_id,)
            ).fetchone()
        return _row_to_gate(row) if row else None

    def list_pending(self) -> list[Gate]:
        with core_database_connection(self._database_path) as connection:
            rows = connection.execute(
                "SELECT * FROM approvals WHERE status = 'pending' "
                "ORDER BY requested_at"
            ).fetchall()
        return [_row_to_gate(row) for row in rows]

    # ----------          ODLUKA          ----------

    def approve(self, gate_id: str, token: str, note: str = "") -> Gate | None:
        """Odobrava molbu SAMO ako je token tacan i molba jos vazi (nije
        istekla, nije vec odluceno o njoj). Vraca odobrenu `Gate` (akciju za
        izvrsenje) ili `None`.

        FAIL-CLOSED: pogresan token ne menja stanje molbe (sme se pokusati
        ponovo sa tacnim tokenom); istekla molba se trajno oznaci `expired`
        makar token bio tacan, da ne visi kao "pending" zauvek.
        """
        gate = self.get(gate_id)
        if gate is None or gate.status != PENDING:
            return None
        if gate.expired:
            self._mark(gate_id, EXPIRED, "istekao rok za odobrenje")
            return None
        if not hmac.compare_digest(_hash_token(token), self._token_hash(gate_id)):
            return None
        return self._mark(gate_id, APPROVED, note)

    def reject(self, gate_id: str, note: str = "") -> Gate | None:
        gate = self.get(gate_id)
        if gate is None or gate.status != PENDING:
            return None
        return self._mark(gate_id, REJECTED, note)

    def _token_hash(self, gate_id: str) -> str:
        with core_database_connection(self._database_path) as connection:
            row = connection.execute(
                "SELECT token_hash FROM approvals WHERE id = ?", (gate_id,)
            ).fetchone()
        return row["token_hash"] if row else ""

    def _mark(self, gate_id: str, status: str, note: str) -> Gate | None:
        assert status in _VALID_STATUS
        with core_database_connection(self._database_path) as connection:
            cursor = connection.execute(
                "UPDATE approvals SET status = ?, note = ?, decided_at = ? "
                "WHERE id = ? AND status = 'pending'",
                (status, note, time.time(), gate_id),
            )
            changed = cursor.rowcount
        return self.get(gate_id) if changed else None
