from __future__ import annotations

from core.domains.filmium.curator.atoms import parse_atom
from core.domains.filmium.curator.scaffold import scaffold_persona, scaffold_tool_atom


def test_scaffold_tool_napravi_fajl_sa_frontmatterom(tmp_path):
    root = tmp_path / "kurator"
    (root / "tools").mkdir(parents=True)
    path = scaffold_tool_atom(root, "torrenti", title="Torrenti", opis="Kako torrenti.")
    assert path.is_file()
    atom = parse_atom(path.read_text(encoding="utf-8"))
    assert atom.meta["type"] == "tool"
    assert atom.meta["id"] == "kurator-tool-torrenti"
    assert "Kako torrenti." in atom.body


def test_scaffold_tool_ne_pregazi_postojeci(tmp_path):
    root = tmp_path / "kurator"
    (root / "tools").mkdir(parents=True)
    scaffold_tool_atom(root, "torrenti", title="Torrenti", opis="Prvo.")
    scaffold_tool_atom(root, "torrenti", title="Torrenti", opis="Drugo.")
    body = (root / "tools" / "torrenti.md").read_text(encoding="utf-8")
    assert "Prvo." in body and "Drugo." not in body


def test_scaffold_persona_napravi_strukturu(tmp_path):
    persona_dir = scaffold_persona(tmp_path, "bezbednjak", name="Bezbednjak")
    assert (persona_dir / "persona.md").is_file()
    assert (persona_dir / "tools").is_dir()
    assert (persona_dir / "commands").is_dir()
    assert (persona_dir / "consult").is_dir()
    atom = parse_atom((persona_dir / "persona.md").read_text(encoding="utf-8"))
    assert atom.meta["type"] == "persona"
