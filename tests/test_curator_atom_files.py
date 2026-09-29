# ========== TESTOVI: uređivanje atom fajlova ==========
from __future__ import annotations

from pathlib import Path

import pytest

from core.domains.filmium.curator import atom_files


def _seed(root: Path) -> None:
    (root / "tools").mkdir(parents=True)
    (root / "commands").mkdir(parents=True)
    (root / "persona.md").write_text("Persona.\n", encoding="utf-8")
    (root / "tools" / "pretraga.md").write_text("Pretraga.\n", encoding="utf-8")
    (root / "commands" / "katalog.md").write_text("Katalog.\n", encoding="utf-8")


def test_list_vraca_sve_atome(tmp_path):
    _seed(tmp_path)
    putanje = {a.path for a in atom_files.list_atoms(tmp_path)}
    assert putanje == {"persona.md", "tools/pretraga.md", "commands/katalog.md"}


def test_read_vraca_sadrzaj(tmp_path):
    _seed(tmp_path)
    assert "Pretraga" in atom_files.read_atom(tmp_path, "tools/pretraga.md")


def test_write_menja_sadrzaj(tmp_path):
    _seed(tmp_path)
    atom_files.write_atom(tmp_path, "persona.md", "Novo.\n")
    assert atom_files.read_atom(tmp_path, "persona.md") == "Novo.\n"


def test_write_prazan_odbijen(tmp_path):
    _seed(tmp_path)
    with pytest.raises(ValueError):
        atom_files.write_atom(tmp_path, "persona.md", "   \n")


def test_izlazak_iz_korena_odbijen(tmp_path):
    _seed(tmp_path)
    with pytest.raises(ValueError):
        atom_files.read_atom(tmp_path, "../../secret.md")
    with pytest.raises(ValueError):
        atom_files.write_atom(tmp_path, "../evil.md", "x")


def test_ne_md_odbijen(tmp_path):
    _seed(tmp_path)
    with pytest.raises(ValueError):
        atom_files.write_atom(tmp_path, "tools/hack.py", "x")
