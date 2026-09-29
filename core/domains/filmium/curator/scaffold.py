# ========== GENERATORI ATOMA ==========
# Kad se doda nov alat ili nova persona, automatski se napravi atom fajl da
# model ima šta da pročita. Idempotentno: postojeći fajl se ne pregazi.
from __future__ import annotations

from pathlib import Path


def _slug(name: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in name.lower()).strip("-")


def scaffold_tool_atom(
    persona_root: Path, name: str, *, title: str, opis: str = ""
) -> Path:
    """Napravi `tools/<name>.md` skelet; ne pregazi postojeći."""

    tools = persona_root / "tools"
    tools.mkdir(parents=True, exist_ok=True)
    path = tools / f"{name}.md"
    if path.is_file():
        return path

    persona_id = persona_root.name
    body = opis or "Uputstvo za ovaj alat — dopuniti."
    path.write_text(
        f"---\nid: {persona_id}-tool-{name}\ntype: tool\n"
        f"title: {title}\ntags: []\n---\n{body}\n",
        encoding="utf-8",
    )
    return path


def scaffold_persona(atomi_root: Path, persona_id: str, *, name: str) -> Path:
    """Napravi `personas/<id>/` sa persona.md i praznim poddirektorijumima."""

    persona_dir = atomi_root / "personas" / persona_id
    for sub in ("tools", "commands", "consult"):
        (persona_dir / sub).mkdir(parents=True, exist_ok=True)

    persona_md = persona_dir / "persona.md"
    if not persona_md.is_file():
        persona_md.write_text(
            f"---\nid: {persona_id}\ntype: persona\ntitle: {name}\n"
            f"related: []\n---\nPersona {name} — dopuniti identitet i povezave.\n",
            encoding="utf-8",
        )
    return persona_dir
