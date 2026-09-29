# ========== FIZIČKA TOPOLOGIJA DISKOVA ==========
# Mapira logičke particije na fizički disk (npr. jedan USB sa dve particije).
# Upit ka OS-u je lenj i injektabilan radi testova:
#   * Windows -> PowerShell (Get-Partition / Get-Disk)
#   * Linux   -> lsblk -J (JSON stablo blok-uređaja)
# Van podržanog OS-a ili pri grešci degradira (vraća [] / None) bez pada.
from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Callable, Iterator
from dataclasses import dataclass


@dataclass(frozen=True)
class Partition:
    mount: str            # Windows "E:\\" ili Linux putanja "/run/media/.../X"
    disk_number: int
    size_bytes: int | None = None


@dataclass(frozen=True)
class PhysicalDisk:
    number: int
    model: str = ""
    serial: str = ""
    bus_type: str = ""
    size_bytes: int | None = None


@dataclass(frozen=True)
class DiskGroup:
    physical: PhysicalDisk
    partitions: tuple[Partition, ...]

    def sibling_mounts(self, mount: str) -> tuple[str, ...]:
        """Ostale particije istog fizičkog diska (bez zadatog mount-a)."""
        m = _norm(mount)
        return tuple(p.mount for p in self.partitions if p.mount != m)


# ---------- normalizacija ----------
def _norm(mount: str) -> str:
    letter = mount.strip().rstrip(":\\/").rstrip(":")
    if len(letter) == 1:
        return f"{letter.upper()}:\\"
    return mount


def _part_mount(part: dict) -> str | None:
    """Ujednači mount particije iz oba backend-a.

    Windows daje golo slovo pod ``DriveLetter`` ("E") -> "E:\\".
    Linux daje punu tačku montiranja pod ``Mount`` ("/run/media/.../X"),
    koju ``_norm`` ostavlja netaknutu.
    """
    if part.get("Mount"):
        return _norm(str(part["Mount"]))
    letter = part.get("DriveLetter")
    if letter:
        return _norm(f"{letter}:")
    return None


# ---------- OS dispečer ----------
def _default_query() -> tuple[list[dict], list[dict]]:
    if sys.platform.startswith("win"):
        return _windows_query()
    if sys.platform.startswith("linux"):
        return _linux_query()
    return [], []  # nepodržan OS -> degradacija bez pada


# ---------- Windows: PowerShell ----------
def _windows_query() -> tuple[list[dict], list[dict]]:
    parts = _run_ps(
        "Get-Partition | Where-Object DriveLetter | ForEach-Object { "
        "[pscustomobject]@{ DriveLetter=$_.DriveLetter; DiskNumber=$_.DiskNumber; "
        "Size=$_.Size } } | ConvertTo-Json -Compress"
    )
    disks = _run_ps(
        "Get-Disk | ForEach-Object { [pscustomobject]@{ Number=$_.Number; "
        "Model=$_.FriendlyName; Serial=$_.SerialNumber; BusType=[string]$_.BusType; "
        "Size=$_.Size } } | ConvertTo-Json -Compress"
    )
    return _as_list(parts), _as_list(disks)


def _run_ps(script: str) -> object:
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True, text=True, timeout=20, check=False,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return []
        return json.loads(result.stdout)
    except Exception:  # noqa: BLE001
        return []  # degradacija bez pada


# ---------- Linux: lsblk -J ----------
def _linux_query() -> tuple[list[dict], list[dict]]:
    raw = _run_lsblk()
    devices = raw.get("blockdevices", []) if isinstance(raw, dict) else []

    parts: list[dict] = []
    disks: list[dict] = []
    # Fizički disk nema "broj" na Linux-u -> stabilan indeks po redosledu lsblk
    # (sda, sdb, nvme0n1, ...). Dovoljno da se sestrinske particije grupišu.
    for number, device in enumerate(d for d in devices if isinstance(d, dict)):
        disks.append({
            "Number": number,
            "Model": str(device.get("model") or "").strip(),
            "Serial": str(device.get("serial") or "").strip(),
            "BusType": str(device.get("tran") or "").strip(),
            "Size": device.get("size"),
        })
        # Sve tačke montiranja BILO GDE ispod ovog fizičkog uređaja
        # (particije, pa i ugnežđeni slojevi: crypt/lvm) pripadaju njemu.
        for mount, size in _iter_mountpoints(device):
            parts.append({
                "Mount": mount,
                "DiskNumber": number,
                "Size": size,
            })
    return parts, disks


def _run_lsblk() -> dict:
    try:
        result = subprocess.run(
            # -b: veličine u bajtovima; stabilne kolone (bez MOUNTPOINTS koji
            # postoji tek od util-linux 2.37) -> radi i na starijim sistemima.
            ["lsblk", "-J", "-b", "-o", "NAME,MOUNTPOINT,SIZE,MODEL,SERIAL,TRAN,TYPE"],
            capture_output=True, text=True, timeout=20, check=False,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return {}
        parsed = json.loads(result.stdout)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:  # noqa: BLE001
        return {}  # degradacija bez pada


def _iter_mountpoints(node: dict) -> Iterator[tuple[str, int | None]]:
    """Prinosi (mount, size) za čvor i sve potomke koji su montirani."""
    size = _int_or_none(node.get("size"))
    for mount in _node_mounts(node):
        yield mount, size
    for child in node.get("children") or []:
        if isinstance(child, dict):
            yield from _iter_mountpoints(child)


def _node_mounts(node: dict) -> list[str]:
    """Tačke montiranja čvora: podržava i skalar ``mountpoint`` i listu
    ``mountpoints`` (noviji lsblk); prazne/swap vrednosti se ignorišu."""
    found: list[str] = []
    single = node.get("mountpoint")
    if isinstance(single, str) and single and single != "[SWAP]":
        found.append(single)
    for mount in node.get("mountpoints") or []:
        if isinstance(mount, str) and mount and mount != "[SWAP]" and mount not in found:
            found.append(mount)
    return found


def _as_list(value: object) -> list[dict]:
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [v for v in value if isinstance(v, dict)]
    return []


# ---------- javni API ----------
Query = Callable[[], tuple[list[dict], list[dict]]]


def disk_group_for(mount: str, *, query: Query | None = None) -> DiskGroup | None:
    """Vrati fizički disk i sve njegove particije za dati mount (ili None)."""
    q = query or _default_query
    parts_raw, disks_raw = q()

    partitions = [
        Partition(mount=part_mount,
                  disk_number=int(p["DiskNumber"]),
                  size_bytes=_int_or_none(p.get("Size")))
        for p in parts_raw
        if (part_mount := _part_mount(p)) and p.get("DiskNumber") is not None
    ]

    target = _norm(mount)
    match = next((p for p in partitions if p.mount == target), None)
    if match is None:
        return None

    number = match.disk_number
    siblings = tuple(p for p in partitions if p.disk_number == number)
    disk_meta = next((d for d in disks_raw if int(d.get("Number", -1)) == number), {})
    physical = PhysicalDisk(
        number=number,
        model=str(disk_meta.get("Model", "") or ""),
        serial=str(disk_meta.get("Serial", "") or "").strip(),
        bus_type=str(disk_meta.get("BusType", "") or ""),
        size_bytes=_int_or_none(disk_meta.get("Size")),
    )
    return DiskGroup(physical=physical, partitions=siblings)


def physical_map(*, query: Query | None = None) -> dict[str, PhysicalDisk]:
    """Mapa svih mountova -> fizički disk kojem particija pripada."""
    q = query or _default_query
    parts_raw, disks_raw = q()

    disks: dict[int, PhysicalDisk] = {}
    for d in disks_raw:
        try:
            num = int(d.get("Number"))
        except (TypeError, ValueError):
            continue
        disks[num] = PhysicalDisk(
            number=num,
            model=str(d.get("Model", "") or ""),
            serial=str(d.get("Serial", "") or "").strip(),
            bus_type=str(d.get("BusType", "") or ""),
            size_bytes=_int_or_none(d.get("Size")),
        )

    result: dict[str, PhysicalDisk] = {}
    for p in parts_raw:
        mount = _part_mount(p)
        num = p.get("DiskNumber")
        if not mount or num is None:
            continue
        num = int(num)
        result[mount] = disks.get(num, PhysicalDisk(number=num))
    return result


def _int_or_none(value: object) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
