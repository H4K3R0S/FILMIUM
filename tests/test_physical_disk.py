# tests/test_physical_disk.py
# ========== TEST: topologija diskova (Windows PS-oblik + Linux lsblk backend) ==========
# Regresija: pre je postojao SAMO PowerShell upit -> na Linuxu je tiho vraćao
# prazno (grupisanje fizičkih diskova/USB nije radilo). Sad Linux ide preko lsblk.
import sys

import pytest

from core.system.file_monitor import physical_disk as pd


# ---------- Windows oblik (back-compat: DriveLetter) ----------
def _windows_query():
    parts = [
        {"DriveLetter": "E", "DiskNumber": 1, "Size": 100},
        {"DriveLetter": "G", "DiskNumber": 1, "Size": 200},
        {"DriveLetter": "C", "DiskNumber": 0, "Size": 500},
    ]
    disks = [
        {"Number": 0, "Model": "Sistem", "Serial": "S0", "BusType": "NVMe", "Size": 500},
        {"Number": 1, "Model": "USB Stik", "Serial": "S1", "BusType": "USB", "Size": 300},
    ]
    return parts, disks


def test_windows_oblik_grupise_sestre_i_normalizuje_slova():
    group = pd.disk_group_for("e:", query=_windows_query)

    assert group is not None
    assert group.physical.model == "USB Stik"
    assert group.physical.bus_type == "USB"
    # E i G su na istom fizičkom disku (broj 1), C nije.
    assert {p.mount for p in group.partitions} == {"E:\\", "G:\\"}
    assert group.sibling_mounts("E:\\") == ("G:\\",)


# ---------- Linux oblik (Mount putanje) ----------
def _linux_query():
    parts = [
        {"Mount": "/run/media/kalima/FILMIUM", "DiskNumber": 0, "Size": 4000},
        {"Mount": "/run/media/kalima/Ventoy", "DiskNumber": 1, "Size": 123},
        {"Mount": "/run/media/kalima/VTOYEFI", "DiskNumber": 1, "Size": 33},
    ]
    disks = [
        {"Number": 0, "Model": "ST4000VN008", "Serial": "ZGY", "BusType": "sata", "Size": 4000},
        {"Number": 1, "Model": "DataTraveler 3.0", "Serial": "E0D", "BusType": "usb", "Size": 123},
    ]
    return parts, disks


def test_linux_oblik_grupise_usb_particije_po_putanji():
    group = pd.disk_group_for("/run/media/kalima/Ventoy", query=_linux_query)

    assert group is not None
    assert group.physical.bus_type == "usb"
    assert group.physical.model == "DataTraveler 3.0"
    assert {p.mount for p in group.partitions} == {
        "/run/media/kalima/Ventoy",
        "/run/media/kalima/VTOYEFI",
    }
    assert group.sibling_mounts("/run/media/kalima/Ventoy") == ("/run/media/kalima/VTOYEFI",)


def test_linux_putanja_nije_iskvarena_dodavanjem_dvotacke():
    mapping = pd.physical_map(query=_linux_query)
    # Putanja ostaje putanja (bez ":" koji je Windows konvencija).
    assert "/run/media/kalima/FILMIUM" in mapping
    assert mapping["/run/media/kalima/FILMIUM"].bus_type == "sata"


def test_nepoznat_mount_vraca_none():
    assert pd.disk_group_for("/nema/ovoga", query=_linux_query) is None


# ---------- Linux parser lsblk stabla ----------
def test_iter_mountpoints_ide_kroz_decu_i_ignorise_swap():
    device = {
        "mountpoint": None, "size": 1000,
        "children": [
            {"mountpoint": "/boot", "size": 100},
            {"mountpoint": "[SWAP]", "size": 50},
            {"mountpoint": None, "size": 800, "children": [
                {"mountpoint": "/", "size": 800},
            ]},
        ],
    }
    mounts = {m for m, _ in pd._iter_mountpoints(device)}
    assert mounts == {"/boot", "/"}


def test_linux_query_parsira_lsblk_json(monkeypatch):
    fake = {
        "blockdevices": [
            {"name": "sda", "mountpoint": None, "size": 4000, "model": "ST4000",
             "serial": "ZGY", "tran": "sata", "type": "disk", "children": [
                 {"name": "sda1", "mountpoint": None, "size": 16, "type": "part"},
                 {"name": "sda2", "mountpoint": "/run/media/kalima/FILMIUM",
                  "size": 3984, "type": "part"},
             ]},
        ]
    }
    monkeypatch.setattr(pd, "_run_lsblk", lambda: fake)
    parts, disks = pd._linux_query()

    assert disks == [{"Number": 0, "Model": "ST4000", "Serial": "ZGY",
                      "BusType": "sata", "Size": 4000}]
    assert parts == [{"Mount": "/run/media/kalima/FILMIUM", "DiskNumber": 0, "Size": 3984}]


# ---------- prava integracija na Linuxu ----------
@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="lsblk je Linux alat")
def test_realni_lsblk_daje_neku_topologiju():
    mapping = pd.physical_map()  # pravi _default_query -> _linux_query -> lsblk
    # Na svakom Linux sistemu bar jedan mount (npr. "/") mora postojati.
    assert mapping, "physical_map je prazan — lsblk backend ne radi"
    assert all(isinstance(v, pd.PhysicalDisk) for v in mapping.values())
