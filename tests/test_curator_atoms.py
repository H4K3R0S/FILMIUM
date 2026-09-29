from __future__ import annotations

from pathlib import Path

import pytest

from core.domains.filmium.curator.atoms import AtomLoader, parse_atom


def test_parse_atom_deli_frontmatter_i_telo():
    text = "---\nid: x\ntype: tool\ntags: [a, b]\n---\nTelo uputstva.\n"
    atom = parse_atom(text)
    assert atom.meta["id"] == "x"
    assert atom.meta["type"] == "tool"
    assert atom.meta["tags"] == ["a", "b"]
    assert atom.body.strip() == "Telo uputstva."


def test_parse_atom_bez_frontmatera_je_celo_telo():
    atom = parse_atom("Samo telo.")
    assert atom.meta == {}
    assert atom.body.strip() == "Samo telo."


def test_parse_atom_nezatvoren_frontmatter_je_celo_telo():
    text = "---\nid: x\nbez zatvaranja telo"
    atom = parse_atom(text)
    assert atom.meta == {}
    assert atom.body == text


def _seed(root: Path) -> None:
    (root / "tools").mkdir(parents=True)
    (root / "commands").mkdir(parents=True)
    (root / "persona.md").write_text(
        "---\nid: kurator\ntype: persona\n---\nJa sam Kurator.\n", encoding="utf-8"
    )
    (root / "tools" / "pretraga.md").write_text(
        "---\nid: t-pretraga\ntype: tool\n---\nKako pretraga.\n", encoding="utf-8"
    )
    (root / "commands" / "katalog.md").write_text(
        "---\nid: katalog\ntype: command\n---\nsearch: nadji film\n", encoding="utf-8"
    )


def test_atom_loader_cita_personu_alat_i_katalog(tmp_path):
    _seed(tmp_path)
    loader = AtomLoader(tmp_path)
    assert "Kurator" in loader.persona().body
    assert "Kako pretraga" in loader.tool("pretraga").body
    assert "nadji film" in loader.command_catalog()


def test_atom_loader_nepoznat_alat_dize_gresku(tmp_path):
    _seed(tmp_path)
    with pytest.raises(FileNotFoundError):
        AtomLoader(tmp_path).tool("nepostoji")
