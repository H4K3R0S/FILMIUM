# ========== KLASIFIKATOR SEKTORA ==========
# Prepoznaje "sektore" diska po top-level strukturi i boot markerima.
# Pravila su podaci (DEFAULT_RULES); imena su case-insensitive.
from __future__ import annotations

from core.system.file_monitor.disk_snapshot_models import (
    DiskSnapshot,
    Sector,
    SectorKind,
)

# marker-tip: "dir" (top-level folder po imenu) ili "file" (fajl bilo gde na top-levelu)
DEFAULT_RULES: list[tuple[SectorKind, str, set[str]]] = [
    (SectorKind.BOOT, "dir", {"boot", "efi", "sources"}),
    (SectorKind.BOOT, "file", {"bootmgr", "bootmgr.efi", "setup.exe"}),
    (SectorKind.SOFTWARE, "dir", {"software"}),
    (SectorKind.SHARING, "dir", {"deki"}),
    (SectorKind.PRINT, "dir", {"stampa"}),
    (SectorKind.VIDEO, "dir", {"video", "filmovi", "crtani", "treileri",
                               "records", "shorts", "serije"}),
    (SectorKind.FILMOTEKA, "dir", {"animirano", "domace", "ostalo", "strano"}),
]


def _top_level(snapshot: DiskSnapshot):
    """Vrati (dirs_lower, files_lower) na top-levelu diska."""
    dirs, files = set(), set()
    for e in snapshot.entries:
        parts = e.relpath.split("/")
        if len(parts) != 1:
            continue
        (dirs if e.is_dir else files).add(parts[0].lower())
    return dirs, files


def classify(snapshot: DiskSnapshot) -> tuple[Sector, ...]:
    dirs, files = _top_level(snapshot)
    counts = _counts_by_top(snapshot)

    found: dict[SectorKind, set[str]] = {}
    for kind, marker, names in DEFAULT_RULES:
        pool = dirs if marker == "dir" else files
        hit = pool & names
        if hit:
            found.setdefault(kind, set()).update(hit)

    sectors: list[Sector] = []
    recognized_dirs: set[str] = set()
    for kind, matched in found.items():
        recognized_dirs |= {m for m in matched if m in dirs}
        entry_count = sum(counts.get(m, 0) for m in matched)
        sectors.append(Sector(
            name=kind.value.capitalize(),
            kind=kind,
            root_relpath="",
            entry_count=entry_count,
            detail={"markers": sorted(matched)},
        ))

    leftover = dirs - recognized_dirs
    if leftover or (not sectors and not dirs):
        sectors.append(Sector(
            name="Ostalo", kind=SectorKind.OTHER, root_relpath="",
            entry_count=sum(counts.get(m, 0) for m in leftover),
            detail={"dirs": sorted(leftover)},
        ))
    return tuple(sectors)


def _counts_by_top(snapshot: DiskSnapshot) -> dict[str, int]:
    counts: dict[str, int] = {}
    for e in snapshot.entries:
        top = e.relpath.split("/")[0].lower()
        counts[top] = counts.get(top, 0) + 1
    return counts


def derive_disk_type(sectors: tuple[Sector, ...]) -> str:
    kinds = {s.kind for s in sectors} - {SectorKind.OTHER}
    if not kinds:
        return "unknown"
    if kinds == {SectorKind.FILMOTEKA} or kinds == {SectorKind.VIDEO}:
        return "filmoteka"
    if kinds <= {SectorKind.BOOT, SectorKind.SOFTWARE}:
        return "bootable-usb"
    return "mixed"
