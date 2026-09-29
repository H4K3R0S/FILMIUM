# tests/test_cell_build.py
# ========== TEST: cell-swap (zamena/oporavak) + import-provere build.py ==========
# Mreža/npm se ne diraju. Swap/rollback/recover rade nad pravim tmp folderima;
# `generated_on_update` se lažira na mali skup da test kontroliše šta se seli.
# Ovi testovi su MREŽA za razdvajanje build.py (build_common/import-checks).
import pytest

from core.cell import build, build_common, build_import_checks

# ----------          move / guard / prune / backup          ----------

def test_guard_not_data_blokira_data_i_config():
    build._guard_not_data("core/x.py")  # sme
    for bad in ("data/filmium.db", "config/tmdb.json"):
        with pytest.raises(ValueError):
            build._guard_not_data(bad)


def test_move_child_premesta_i_odbija_postojece(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    (src / "sub").mkdir(parents=True)
    (src / "sub" / "f.txt").write_text("x", encoding="utf-8")

    build._move_child(src, "sub", dst)
    assert (dst / "sub" / "f.txt").read_text(encoding="utf-8") == "x"
    assert not (src / "sub").exists()

    # odredište već postoji -> FileExistsError (ne sme da ugnezdi)
    (src / "sub").mkdir(parents=True)
    with pytest.raises(FileExistsError):
        build._move_child(src, "sub", dst)


def test_move_child_cuva_data(tmp_path):
    (tmp_path / "src" / "data").mkdir(parents=True)
    with pytest.raises(ValueError):
        build._move_child(tmp_path / "src", "data", tmp_path / "dst")


def test_try_move_child_vraca_none_ili_repr(tmp_path):
    src = tmp_path / "s"
    (src).mkdir()
    (src / "a.txt").write_text("1", encoding="utf-8")
    assert build._try_move_child(src, "a.txt", tmp_path / "d") is None
    # ponovni pokušaj (izvor više ne postoji) -> string sa greškom
    err = build._try_move_child(src, "a.txt", tmp_path / "d")
    assert isinstance(err, str) and err


def test_prune_empty_dirs(tmp_path):
    (tmp_path / "prazan" / "dublje").mkdir(parents=True)
    (tmp_path / "pun").mkdir()
    (tmp_path / "pun" / "f.txt").write_text("x", encoding="utf-8")
    build._prune_empty_dirs(tmp_path)
    assert not (tmp_path / "prazan").exists()
    assert (tmp_path / "pun" / "f.txt").exists()


def test_backup_dir_for(tmp_path):
    target = tmp_path / "FILMIUM"
    assert build._backup_dir_for(target) == tmp_path / ".FILMIUM.old"


# ----------          swap (kritično)          ----------

def _make_cell(root, files: dict[str, str]):
    for rel, content in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")


def test_swap_uspesna_zamena(tmp_path, monkeypatch):
    monkeypatch.setattr(build, "generated_on_update", lambda exe: ("pkg", "top.txt"))
    target = tmp_path / "cell"
    staging = tmp_path / "staging"
    _make_cell(target, {"pkg/m.py": "staro", "top.txt": "staro", "data/db": "KORISNIK"})
    _make_cell(staging, {"pkg/m.py": "novo", "top.txt": "novo"})

    build._swap_staged_cell(target, staging, "FILMIUM.exe")

    assert (target / "pkg" / "m.py").read_text(encoding="utf-8") == "novo"
    assert (target / "top.txt").read_text(encoding="utf-8") == "novo"
    assert (target / "data" / "db").read_text(encoding="utf-8") == "KORISNIK"  # netaknuto
    assert not build._backup_dir_for(target).exists()  # backup uklonjen
    assert not staging.exists()  # staging uklonjen


def test_swap_rollback_pri_gresci(tmp_path, monkeypatch):
    monkeypatch.setattr(build, "generated_on_update", lambda exe: ("pkg", "top.txt"))

    def boom(_root):
        raise RuntimeError("simulirana greška posle premeštanja")

    monkeypatch.setattr(build, "_ensure_cell_user_space", boom)
    target = tmp_path / "cell"
    staging = tmp_path / "staging"
    _make_cell(target, {"pkg/m.py": "staro", "top.txt": "staro"})
    _make_cell(staging, {"pkg/m.py": "novo", "top.txt": "novo"})

    with pytest.raises(RuntimeError):
        build._swap_staged_cell(target, staging, "FILMIUM.exe")

    # target vraćen na staro, staging vraćen; ništa izgubljeno
    assert (target / "pkg" / "m.py").read_text(encoding="utf-8") == "staro"
    assert (target / "top.txt").read_text(encoding="utf-8") == "staro"
    assert (staging / "pkg" / "m.py").read_text(encoding="utf-8") == "novo"


def test_swap_odbija_postojeci_backup(tmp_path, monkeypatch):
    monkeypatch.setattr(build, "generated_on_update", lambda exe: ("top.txt",))
    target = tmp_path / "cell"
    _make_cell(target, {"top.txt": "x"})
    build._backup_dir_for(target).mkdir(parents=True)  # zaostali backup
    with pytest.raises(RuntimeError):
        build._swap_staged_cell(target, tmp_path / "staging", "FILMIUM.exe")


# ----------          recover (oporavak)          ----------

def test_recover_bez_backupa_je_noop(tmp_path):
    build._recover_backup_before_update(tmp_path / "cell", "FILMIUM.exe")  # ne sme da pukne


def test_recover_zavrsen_marker_brise_backup(tmp_path):
    target = tmp_path / "cell"
    target.mkdir()
    backup = build._backup_dir_for(target)
    backup.mkdir(parents=True)
    (backup / "ostatak.txt").write_text("x", encoding="utf-8")
    (backup / build.SWAP_COMPLETE_MARKER).write_text("done", encoding="utf-8")
    build._recover_backup_before_update(target, "FILMIUM.exe")
    assert not backup.exists()


def test_recover_vraca_bez_markera(tmp_path, monkeypatch):
    monkeypatch.setattr(build, "generated_on_update", lambda exe: ("cell.json", "pkg"))
    target = tmp_path / "cell"
    target.mkdir()
    backup = build._backup_dir_for(target)
    _make_cell(backup, {"cell.json": "{}", "pkg/m.py": "kod"})
    build._recover_backup_before_update(target, "FILMIUM.exe")
    assert (target / "cell.json").read_text(encoding="utf-8") == "{}"
    assert (target / "pkg" / "m.py").read_text(encoding="utf-8") == "kod"
    assert not backup.exists()


def test_recover_konflikt_die(tmp_path, monkeypatch):
    monkeypatch.setattr(build, "generated_on_update", lambda exe: ("cell.json",))
    target = tmp_path / "cell"
    _make_cell(target, {"cell.json": "target"})
    backup = build._backup_dir_for(target)
    _make_cell(backup, {"cell.json": "backup"})
    with pytest.raises(RuntimeError):
        build._recover_backup_before_update(target, "FILMIUM.exe")


def test_remove_completed_backup(tmp_path):
    backup = tmp_path / ".c.old"
    _make_cell(backup, {"a.txt": "1", "sub/b.txt": "2"})
    (backup / build.SWAP_COMPLETE_MARKER).write_text("done", encoding="utf-8")
    build._remove_completed_backup(backup)
    assert not backup.exists()


# ----------          import-provere (biće u build_import_checks)          ----------

def test_is_forbidden():
    assert build_common._is_forbidden("core.integrations")
    assert build_common._is_forbidden("core.integrations.translator")  # podmodul
    assert not build_common._is_forbidden("core.domains.filmium")


def test_find_forbidden_module_imports(tmp_path):
    cell = tmp_path / "cell"
    (cell / "core").mkdir(parents=True)
    (cell / "core" / "x.py").write_text(
        "import core.integrations.translator\n", encoding="utf-8"
    )
    found = build_import_checks.find_forbidden_module_imports(cell)
    assert any("core.integrations" in f for f in found)


def test_find_foreign_domain_imports(tmp_path):
    cell = tmp_path / "cell"
    (cell / "core" / "domains" / "filmium").mkdir(parents=True)
    (cell / "core" / "domains" / "filmium" / "svoj.py").write_text(
        "from core.domains.filmium import x\n", encoding="utf-8"
    )
    (cell / "core" / "domains" / "filmium" / "tudj.py").write_text(
        "from core.domains.codium import y\n", encoding="utf-8"
    )
    found = build_import_checks.find_foreign_domain_imports(cell, "filmium")
    joined = " ".join(found)
    assert "codium" in joined
    assert "core.domains.filmium" not in joined
