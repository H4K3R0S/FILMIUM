# ========== RAG-LOG: učenje kroz upotrebu ==========
# Za svaku komandu beleži šta je čuo, šta razumeo, koji alat i ishod. Ako u
# roku (silence_seconds) niko ne opovrgne akciju → correct; opovrgavanje →
# wrong. `wrong` unosi su najvredniji za budući RAG (razlika rečeno vs hteo).
# Zapis je JSONL po danu; čitanje spaja sve fajlove hronološki.
from __future__ import annotations

import json
import secrets
import time
from collections.abc import Callable
from pathlib import Path


class InteractionLog:
    """RAG-log interakcija Kuratora (append-only JSONL)."""

    def __init__(
        self,
        root: Path,
        silence_seconds: float = 180.0,
        now: Callable[[], float] = time.time,
    ) -> None:
        self._root = root
        self._silence = silence_seconds
        self._now = now
        self._root.mkdir(parents=True, exist_ok=True)

    def _file(self, ts: float) -> Path:
        day = time.strftime("%Y-%m-%d", time.gmtime(ts))
        return self._root / f"{day}.jsonl"

    def _rewrite(self, entries: list[dict]) -> None:
        # Grupiši po danu i prepiši (mali obim; jednostavno i pouzdano).
        by_day: dict[Path, list[dict]] = {}
        for entry in entries:
            by_day.setdefault(self._file(entry["timestamp"]), []).append(entry)
        for path, day_entries in by_day.items():
            path.write_text(
                "\n".join(json.dumps(e, ensure_ascii=False) for e in day_entries) + "\n",
                encoding="utf-8",
            )

    def record(
        self,
        heard: str,
        intent: str,
        params: dict,
        tool: str | None,
        reply: str,
    ) -> str:
        ts = self._now()
        log_id = secrets.token_hex(8)
        entry = {
            "log_id": log_id,
            "timestamp": ts,
            "heard": heard,
            "understood": {"intent": intent, "params": params},
            "tool": tool,
            "reply": reply,
            "status": "pending",
            "resolved_at": None,
            "resolved_by": None,
        }
        with self._file(ts).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return log_id

    def entries(self) -> list[dict]:
        out: list[dict] = []
        for path in sorted(self._root.glob("*.jsonl")):
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    out.append(json.loads(line))
        out.sort(key=lambda e: e["timestamp"])
        return out

    def refute(self, log_id: str | None = None) -> bool:
        entries = self.entries()
        target = None
        for entry in reversed(entries):
            if entry["status"] != "pending":
                continue
            if log_id is None or entry["log_id"] == log_id:
                target = entry
                break
        if target is None:
            return False
        target["status"] = "wrong"
        target["resolved_at"] = self._now()
        target["resolved_by"] = "user"
        self._rewrite(entries)
        return True

    def settle_silent(self) -> int:
        entries = self.entries()
        now = self._now()
        changed = 0
        for entry in entries:
            if entry["status"] == "pending" and now - entry["timestamp"] > self._silence:
                entry["status"] = "correct"
                entry["resolved_at"] = now
                entry["resolved_by"] = "silence"
                changed += 1
        if changed:
            self._rewrite(entries)
        return changed
