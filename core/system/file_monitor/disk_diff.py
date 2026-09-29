# ========== DISK DIFF ==========
# Čista funkcija: poredi dva DiskSnapshot-a po relpath, kriterijum (size, mtime).
from __future__ import annotations

from core.system.file_monitor.disk_snapshot_models import (
    DiskSnapshot,
    FileEntry,
    ScanDiff,
)


def diff(old: DiskSnapshot, new: DiskSnapshot) -> ScanDiff:
    old_map = {e.relpath: e for e in old.entries}
    new_map = {e.relpath: e for e in new.entries}

    added = [e for p, e in new_map.items() if p not in old_map]
    removed = [e for p, e in old_map.items() if p not in new_map]
    changed = [
        n for p, n in new_map.items()
        if p in old_map and _differs(old_map[p], n)
    ]

    def key(e: FileEntry) -> str:
        return e.relpath

    return ScanDiff(
        added=tuple(sorted(added, key=key)),
        removed=tuple(sorted(removed, key=key)),
        changed=tuple(sorted(changed, key=key)),
    )


def _differs(a: FileEntry, b: FileEntry) -> bool:
    return a.size != b.size or a.mtime != b.mtime
