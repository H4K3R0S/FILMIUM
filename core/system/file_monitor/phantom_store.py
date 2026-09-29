# ========== PHANTOM STORE ==========
# Čita/piše skriveni .core_phantom/ folder na disku: identity/structure/snapshot.
# Codec je pluggable (PlainJsonCodec sada; enkripcija je buduća nadogradnja).
from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import datetime
from pathlib import Path

from core.system.file_monitor.disk_snapshot_models import (
    DiskIdentity,
    DiskSnapshot,
    FileEntry,
    RelatedPartition,
    Sector,
    SectorKind,
)

PHANTOM_DIR = ".core_phantom"
_ISO = "%Y-%m-%dT%H:%M:%S.%f"


# ---------- codec ----------
class PlainJsonCodec:
    def encode(self, data: dict) -> bytes:
        return json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")

    def decode(self, raw: bytes) -> dict:
        return json.loads(raw.decode("utf-8"))


# ---------- potpis ----------
def sign_id(serial: str, created_at: datetime, key: bytes) -> str:
    msg = f"{serial}|{created_at.strftime(_ISO)}".encode()
    return hmac.new(key, msg, hashlib.sha256).hexdigest()


# ---------- serijalizacija ----------
def _identity_to_dict(i: DiskIdentity) -> dict:
    return {
        "disk_id": i.disk_id, "signed_id": i.signed_id, "owner": i.owner,
        "disk_type": i.disk_type, "purpose": i.purpose, "general_use": i.general_use,
        "serial": i.serial,
        "created_at": i.created_at.strftime(_ISO),
        "last_scan_at": i.last_scan_at.strftime(_ISO),
        "physical_disk_number": i.physical_disk_number,
        "physical_model": i.physical_model,
        "physical_serial": i.physical_serial,
        "bus_type": i.bus_type,
        "related_partitions": [
            {"mount": p.mount, "size_bytes": p.size_bytes}
            for p in i.related_partitions
        ],
        "phantom_location": i.phantom_location,
    }


def _identity_from_dict(d: dict) -> DiskIdentity:
    return DiskIdentity(
        disk_id=d["disk_id"], signed_id=d["signed_id"], owner=d.get("owner", "CORE"),
        disk_type=d.get("disk_type", ""), purpose=d.get("purpose", ""),
        general_use=d.get("general_use", ""), serial=d.get("serial", ""),
        created_at=datetime.strptime(d["created_at"], _ISO),  # noqa: DTZ007
        last_scan_at=datetime.strptime(d["last_scan_at"], _ISO),  # noqa: DTZ007
        physical_disk_number=d.get("physical_disk_number"),
        physical_model=d.get("physical_model", ""),
        physical_serial=d.get("physical_serial", ""),
        bus_type=d.get("bus_type", ""),
        related_partitions=tuple(
            RelatedPartition(mount=p["mount"], size_bytes=p.get("size_bytes"))
            for p in d.get("related_partitions", [])
        ),
        phantom_location=d.get("phantom_location", ""),
    )


def _sectors_to_list(sectors: tuple[Sector, ...]) -> list:
    return [
        {"name": s.name, "kind": s.kind.value, "root_relpath": s.root_relpath,
         "entry_count": s.entry_count, "detail": s.detail}
        for s in sectors
    ]


def _snapshot_to_dict(s: DiskSnapshot) -> dict:
    return {
        "mount": s.mount, "taken_at": s.taken_at.strftime(_ISO),
        "entries": [
            {"relpath": e.relpath, "size": e.size, "mtime": e.mtime, "is_dir": e.is_dir}
            for e in s.entries
        ],
    }


def _snapshot_from_dict(d: dict) -> DiskSnapshot:
    return DiskSnapshot(
        mount=d["mount"], taken_at=datetime.strptime(d["taken_at"], _ISO),  # noqa: DTZ007
        entries=tuple(
            FileEntry(e["relpath"], e["size"], e["mtime"], e["is_dir"])
            for e in d["entries"]
        ),
    )


# ---------- hidden atribut (best-effort) ----------
def _set_hidden(path: Path) -> None:
    if os.name != "nt":
        return
    try:
        import ctypes
        FILE_ATTRIBUTE_HIDDEN = 0x02
        FILE_ATTRIBUTE_SYSTEM = 0x04
        ctypes.windll.kernel32.SetFileAttributesW(
            str(path), FILE_ATTRIBUTE_HIDDEN | FILE_ATTRIBUTE_SYSTEM
        )
    except Exception:  # noqa: BLE001, S110
        pass  # degradacija bez pada


# ---------- API ----------
def save(mount, identity, sectors, snapshot, *,
         codec=None, phantom_dir_name: str = PHANTOM_DIR) -> bool:
    codec = codec or PlainJsonCodec()
    try:
        root = Path(mount) / phantom_dir_name
        root.mkdir(parents=True, exist_ok=True)
        _set_hidden(root)
        (root / "identity.json").write_bytes(codec.encode(_identity_to_dict(identity)))
        (root / "structure.json").write_bytes(codec.encode({"sectors": _sectors_to_list(sectors)}))
        (root / "snapshot.json").write_bytes(codec.encode(_snapshot_to_dict(snapshot)))
        return True
    except OSError:
        return False  # read-only medij i sl. — scan se ne obara


def load(mount, *, codec=None, phantom_dir_name: str = PHANTOM_DIR):
    codec = codec or PlainJsonCodec()
    root = Path(mount) / phantom_dir_name
    if not root.exists():
        return None, None
    ident = _read(root / "identity.json", codec, _identity_from_dict)
    snap = _read(root / "snapshot.json", codec, _snapshot_from_dict)
    return ident, snap


def load_peek(mount, *, codec=None, phantom_dir_name: str = PHANTOM_DIR):
    """Lagani uvid: identity + sektori iz structure.json (bez snapshot-a)."""
    codec = codec or PlainJsonCodec()
    root = Path(mount) / phantom_dir_name
    if not root.exists():
        return None, ()
    ident = _read(root / "identity.json", codec, _identity_from_dict)
    sectors = _read(root / "structure.json", codec, _sectors_from_dict) or ()
    return ident, sectors


def _sectors_from_dict(d: dict) -> tuple[Sector, ...]:
    return tuple(
        Sector(
            name=s["name"],
            kind=SectorKind(s["kind"]),
            root_relpath=s.get("root_relpath", ""),
            entry_count=s.get("entry_count", 0),
            detail=s.get("detail", {}),
        )
        for s in d.get("sectors", [])
    )


def _read(path: Path, codec, mapper):
    try:
        return mapper(codec.decode(path.read_bytes()))
    except (OSError, ValueError, KeyError):
        return None  # oštećeno/nepostojeće -> tretiraj kao da nema
