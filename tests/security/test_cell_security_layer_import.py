"""F5 — regresija: deljeni sloj (`core/cell/executor.py` + `approvals.py`)
mora da se uveze bez greske i u FILMIUM-u (identican fajl kao u ostala 3
domena). Puna scenario-pokrivenost (LOW/CRITICAL/gate/approve) je u KALIMA
(`~/ai/domains/kalima/tests/security/test_approval_gate_executor.py`) — ovde
je namerno samo uvoz + jedno bezopasno LOW izvrsenje, da FILMIUM ne dobije
duplirane testove bez dodatne vrednosti.

Pokrece se direktno: `.venv-linux/bin/python3 tests/security/test_cell_security_layer_import.py -v`
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

_DOMAIN_ROOT = Path(__file__).resolve().parents[2]
if str(_DOMAIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_DOMAIN_ROOT))


class RegressionImportTest(unittest.TestCase):
    def test_uvoz_ne_puca(self) -> None:
        import core.cell.approvals
        import core.cell.executor  # noqa: F401

    def test_low_risk_izvrsava_se_autonomno(self) -> None:
        from core.cell.approvals import Approvals
        from core.cell.executor import EXECUTED, Executor

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            allow_path = tmp_path / "tools.allow.json"
            allow_path.write_text(json.dumps({
                "domain": "filmium",
                "tools": {"echo": {"binary": "/bin/echo", "risk": "LOW",
                                    "targets_network": False, "timeout_s": 10,
                                    "action": "filmium.echo"}},
            }), encoding="utf-8")
            executor = Executor(
                domain="filmium", allow_path=allow_path,
                logs_dir=tmp_path / "logs",
                approvals=Approvals(database_path=tmp_path / "approvals.db"),
                emit=lambda evt: None,
            )
            rezultat = executor.run("echo", args={"argv": ["filmium-test"]})
            self.assertEqual(rezultat.status, EXECUTED)
            self.assertIn("filmium-test", rezultat.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
