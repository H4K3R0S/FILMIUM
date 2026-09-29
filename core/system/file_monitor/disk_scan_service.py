# ========== DISK SCAN SERVICE (orkestrator) ==========
# scan -> classify -> topologija -> load fantom -> diff -> save fantom -> ScanReport.
# Ako je skenirani mount write-protected (npr. mala boot particija), fantom se
# upisuje na upisivu sestrinsku particiju istog fizičkog USB-a; povezane
# particije se beleže u identitetu.
from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime

from core.system.file_monitor import (
    content_classifier,
    disk_diff,
    disk_scanner,
    phantom_store,
    physical_disk,
)
from core.system.file_monitor.disk_snapshot_models import (
    DiskIdentity,
    DiskSnapshot,
    PhantomPeek,
    RelatedPartition,
    ScanReport,
)

ReportCallback = Callable[[ScanReport], None]
DEFAULT_KEY = b"core-local-phantom-key"


class DiskScanService:
    def __init__(self, *, scanner=None, classifier=None, store=None, differ=None,
                 clock=None, key: bytes = DEFAULT_KEY, id_factory=None, topology=None) -> None:
        self._scan = scanner or disk_scanner.scan
        self._classify = classifier or content_classifier.classify
        self._store = store or phantom_store
        self._diff = differ or disk_diff.diff
        self._clock = clock or datetime.now
        self._key = key
        self._new_id = id_factory or (lambda: uuid.uuid4().hex)
        self._topology = topology or physical_disk.disk_group_for
        self._callbacks: list[ReportCallback] = []

    def register_callback(self, cb: ReportCallback) -> None:
        self._callbacks.append(cb)

    def peek(self, mount: str) -> PhantomPeek:
        """Lagani uvid u fantom bez dubokog skena i bez upisa."""
        identity, sectors = self._store.load_peek(mount)
        if identity is None:
            # Fantom može biti na sestrinskoj (upisivoj) particiji istog USB-a.
            for sib in self._siblings(mount):
                identity, sectors = self._store.load_peek(sib)
                if identity is not None:
                    break
        return PhantomPeek(
            is_known=identity is not None,
            identity=identity,
            sectors=sectors,
        )

    def scan(self, mount: str, *, purpose: str = "", general_use: str = "") -> ScanReport:
        now = self._clock()
        new_snap: DiskSnapshot = self._scan(mount)
        sectors = self._classify(new_snap)
        disk_type = content_classifier.derive_disk_type(sectors)

        group = self._safe_group(mount)
        candidates = self._save_candidates(mount, group)

        # Prethodni fantom traži i na sestrinskim particijama (fantom-on-sibling).
        old_ident, old_snap = self._load_prior(candidates)
        is_first = old_snap is None
        base_snap = old_snap if not is_first else DiskSnapshot(mount=mount, taken_at=now, entries=())
        diff = self._diff(base_snap, new_snap)

        identity = self._build_identity(old_ident, disk_type, purpose, general_use, now, mount, group)
        identity, written = self._save_with_fallback(identity, sectors, new_snap, candidates)

        report = ScanReport(identity=identity, sectors=sectors, diff=diff,
                            is_first_scan=is_first, phantom_written=written)
        for cb in self._callbacks:
            cb(report)
        return report

    # ---------- topologija / kandidati ----------
    def _safe_group(self, mount):
        try:
            return self._topology(mount)
        except Exception:  # noqa: BLE001
            return None

    def _siblings(self, mount) -> tuple[str, ...]:
        group = self._safe_group(mount)
        return group.sibling_mounts(mount) if group else ()

    def _save_candidates(self, mount, group) -> tuple[str, ...]:
        # Skenirani mount prvi; pa sestrinske particije (fallback za write-protected).
        sibs = group.sibling_mounts(mount) if group else ()
        return (mount, *sibs)

    def _load_prior(self, candidates):
        for cand in candidates:
            ident, snap = self._store.load(cand)
            if snap is not None:
                return ident, snap
        return None, None

    def _save_with_fallback(self, identity, sectors, snapshot, candidates):
        for cand in candidates:
            located = replace(identity, phantom_location=cand)
            if self._store.save(cand, located, sectors, snapshot):
                return located, True
        return replace(identity, phantom_location=""), False

    # ---------- identitet ----------
    def _build_identity(self, old, disk_type, purpose, general_use, now, mount, group) -> DiskIdentity:
        disk_id = old.disk_id if old else self._new_id()
        created = old.created_at if old else now
        serial = old.serial if old else ""
        signed = phantom_store.sign_id(serial, created, self._key)

        if group is not None:
            phys_num = group.physical.number
            phys_model = group.physical.model
            phys_serial = group.physical.serial
            bus = group.physical.bus_type
            related = tuple(
                RelatedPartition(mount=p.mount, size_bytes=p.size_bytes)
                for p in group.partitions
            )
        else:
            phys_num, phys_model, phys_serial, bus = None, "", "", ""
            related = ()

        return DiskIdentity(
            disk_id=disk_id, signed_id=signed, serial=serial,
            owner="CORE", disk_type=disk_type,
            purpose=purpose or (old.purpose if old else ""),
            general_use=general_use or (old.general_use if old else ""),
            created_at=created, last_scan_at=now,
            physical_disk_number=phys_num, physical_model=phys_model,
            physical_serial=phys_serial, bus_type=bus,
            related_partitions=related,
        )
