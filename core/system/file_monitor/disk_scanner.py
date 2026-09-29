# ========== DISK SCANNER (deep scan) ==========
# Prolazi mount i pravi DiskSnapshot. Walker i clock injektabilni radi testova.
from __future__ import annotations

import os
from collections.abc import Callable, Iterable
from datetime import datetime

from core.system.file_monitor.disk_snapshot_models import DiskSnapshot, FileEntry

WalkRow = tuple[str, int, float, bool]   # (abspath, size, mtime, is_dir)
Walker = Callable[[str], Iterable[WalkRow]]


def _default_walker(mount: str) -> Iterable[WalkRow]:
    for root, dirs, files in os.walk(mount):
        for d in dirs:
            p = os.path.join(root, d)
            try:
                st = os.stat(p)
                yield (p, 0, st.st_mtime, True)
            except OSError:
                continue
        for f in files:
            p = os.path.join(root, f)
            try:
                st = os.stat(p)
                yield (p, st.st_size, st.st_mtime, False)
            except OSError:
                continue


def _to_relpath(mount: str, abspath: str) -> str:
    rel = os.path.relpath(abspath, mount)
    return rel.replace(os.sep, "/").replace("\\", "/")


def scan(
    mount: str,
    *,
    walker: Walker | None = None,
    clock: Callable[[], datetime] | None = None,
    phantom_dir_name: str = ".core_phantom",
) -> DiskSnapshot:
    walk = walker or _default_walker
    now = (clock or datetime.now)()

    entries: list[FileEntry] = []
    for abspath, size, mtime, is_dir in walk(mount):
        rel = _to_relpath(mount, abspath)
        parts = rel.split("/")
        if phantom_dir_name in parts:
            continue
        entries.append(FileEntry(relpath=rel, size=size, mtime=mtime, is_dir=is_dir))

    return DiskSnapshot(mount=mount, taken_at=now, entries=tuple(entries))
