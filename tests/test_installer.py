# tests/test_installer.py
# ========== TEST: OS-agnostičan auto-instalater (bug: powershell na Linuxu) ==========
# Regresija za bug u prozoru zavisnosti: dugme INSTALL je zvalo `powershell`
# (Windows-only) pa na Linux/Kali padalo sa "[Errno 2] ... 'powershell'".
# Ovde se NE pokreće pravi pip/npm — testiramo samo builder komande.
import sys

import pytest

from core.foundation import installer
from core.foundation.dependencies import (
    DOMAIN_DEPENDENCIES,
    Dependency,
    DependencyInstaller,
    DependencyKind,
    DependencySeverity,
)


def _dep(key: str) -> Dependency:
    return next(d for d in DOMAIN_DEPENDENCIES if d.key == key)


def test_pip_komanda_gadja_tekuci_interpreter_bez_powershell():
    command, _cwd = installer._command_for(_dep("keyring"))

    assert command[:4] == [sys.executable, "-m", "pip", "install"]
    assert command[4] == "keyring"
    # Nikad Windows-only alat na komandnoj liniji.
    assert "powershell" not in " ".join(command).lower()


def test_npm_komanda_bez_imena_paketa_u_gui_dir():
    command, cwd = installer._command_for(
        Dependency(
            key="monaco-editor",
            label="monaco",
            kind=DependencyKind.NPM,
            severity=DependencySeverity.OPTIONAL,
            probe="monaco-editor",
            purpose="x",
            install_hint="npm install",
            installer=DependencyInstaller.NPM,
        )
    )

    assert command == ["npm", "install"]
    assert cwd.name == "gui"


def test_nepodrzan_installer_baca_keyerror():
    winget_dep = Dependency(
        key="nešto",
        label="x",
        kind=DependencyKind.SYSTEM,
        severity=DependencySeverity.OPTIONAL,
        probe="x",
        purpose="x",
        install_hint="x",
        installer=DependencyInstaller.WINGET,
    )
    with pytest.raises(KeyError):
        installer._command_for(winget_dep)


def test_start_install_odbija_nepoznat_kljuc():
    with pytest.raises(KeyError):
        installer.start_install("ne-postoji-xyz")


def test_pip_hint_ne_koristi_goli_python():
    # Kopiranje hinta u terminal ne sme da padne na sistemski externally-managed.
    keyring = _dep("keyring")
    assert keyring.install_hint.startswith(f'"{sys.executable}"')
    assert "-m pip install keyring" in keyring.install_hint
