# ========== SCAN NOTIFICATION ==========
# Formatiranje ScanReport-a u kratku poruku + notifikatori (null/callback/OS-toast).
from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from core.system.file_monitor.disk_snapshot_models import (
    PhantomPeek,
    ScanReport,
    SectorKind,
)


def format_report(report: ScanReport) -> tuple[str, str]:
    ident = report.identity
    sec_names = ", ".join(s.name for s in report.sectors) or "nepoznato"
    if report.is_first_scan:
        title = f"CORE: nov disk ({ident.disk_type})"
        msg = (f"Prvi put skeniran. Sektori: {sec_names}. "
               f"Fajlova: {len(report.diff.added)}.")
    else:
        d = report.diff
        title = f"CORE: disk skeniran ({ident.disk_type})"
        if d.is_empty:
            msg = f"Nema promena. Sektori: {sec_names}."
        else:
            msg = (f"Promene: +{len(d.added)} novih, "
                   f"~{len(d.changed)} izmenjenih, -{len(d.removed)} obrisanih.")
    films = film_count(report)
    if films > 0:
        msg += f" 🎬 Nađeno {films} video/film stavki."
    if not report.phantom_written:
        msg += " (Fantom NIJE upisan — medij zaštićen od pisanja.)"
    return title, msg


def film_count(report: ScanReport) -> int:
    """Broj stavki u VIDEO i FILMOTEKA sektorima (film/video nalaz)."""
    return sum(
        s.entry_count for s in report.sectors
        if s.kind in (SectorKind.VIDEO, SectorKind.FILMOTEKA)
    )


def format_peek(peek: PhantomPeek) -> tuple[str, str]:
    """Poruka pri priključenju: šta CORE već zna o disku (bez dubokog skena)."""
    sec_names = ", ".join(s.name for s in peek.sectors) or "nepoznato"
    if not peek.is_known or peek.identity is None:
        return ("CORE: nepoznat disk",
                "Nema CORE fantoma. Pokreni pun scan za identifikaciju.")
    ident = peek.identity
    title = f"CORE: poznat disk ({ident.disk_type or 'nepoznat tip'})"
    purpose = f" — {ident.purpose}" if ident.purpose else ""
    msg = (f"Vlasnik: {ident.owner}{purpose}. Sektori: {sec_names}. "
           f"Zadnji scan: {ident.last_scan_at:%Y-%m-%d %H:%M}.")
    return title, msg


class Notifier(Protocol):
    def notify(self, title: str, message: str) -> None: ...


class NullNotifier:
    def notify(self, title: str, message: str) -> None:
        return None


class CallbackNotifier:
    def __init__(self, fn: Callable[[str, str], None]) -> None:
        self._fn = fn

    def notify(self, title: str, message: str) -> None:
        self._fn(title, message)


class OsToastNotifier:
    """OS toast; backend lazy. Degradira bez pada ako backend nedostupan."""

    def __init__(self, backend_factory: Callable[[], object] | None = None) -> None:
        self._backend_factory = backend_factory or _default_backend

    def notify(self, title: str, message: str) -> None:
        try:
            backend = self._backend_factory()
            backend(title, message)  # backend je callable(title, message)
        except Exception:  # noqa: BLE001, S110
            pass  # degradacija bez pada


def _default_backend() -> Callable[[str, str], None]:
    # win10toast ako postoji; inače PowerShell; inače baci (OsToastNotifier hvata).
    try:
        from win10toast import ToastNotifier  # type: ignore
        toaster = ToastNotifier()

        def _toast(title: str, message: str) -> None:
            toaster.show_toast(title, message, duration=5, threaded=True)

        return _toast
    except Exception:  # noqa: BLE001, S110
        pass

    import shutil
    if shutil.which("powershell"):
        import subprocess

        def _ps(title: str, message: str) -> None:
            safe_title = title.replace("'", "''")
            safe_msg = message.replace("'", "''")
            script = (
                "$ErrorActionPreference='SilentlyContinue';"
                "[void][Windows.UI.Notifications.ToastNotificationManager,"
                "Windows.UI.Notifications,ContentType=WindowsRuntime];"
                "$t=[Windows.UI.Notifications.ToastNotificationManager]::"
                "GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02);"
                "$n=$t.GetElementsByTagName('text');"
                f"$n.Item(0).AppendChild($t.CreateTextNode('{safe_title}'))|Out-Null;"
                f"$n.Item(1).AppendChild($t.CreateTextNode('{safe_msg}'))|Out-Null;"
                "[Windows.UI.Notifications.ToastNotificationManager]::"
                "CreateToastNotifier('CORE').Show("
                "[Windows.UI.Notifications.ToastNotification]::new($t))"
            )
            subprocess.run(["powershell", "-NoProfile", "-Command", script],
                           capture_output=True, timeout=10, check=False)

        return _ps

    raise RuntimeError("nema toast backend-a")
