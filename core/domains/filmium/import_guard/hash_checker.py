"""Računanje SHA-256 sažetka fajla, u blokovima."""

from __future__ import annotations

import hashlib

_BLOCK_SIZE = 1024 * 1024


def sha256_file(file_path: str) -> str:
    """
    Računa SHA-256 sažetak fajla.

    Args:
        file_path: Putanja fajla.

    Returns:
        Heksadecimalni sažetak.

    Raises:
        OSError: Ako se fajl ne može pročitati.
    """
    digest = hashlib.sha256()

    with open(file_path, "rb") as handle:
        while True:
            block = handle.read(_BLOCK_SIZE)
            if not block:
                break
            digest.update(block)

    return digest.hexdigest()
