#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Bounded archive inventory adapters for package-contract comparison."""

from __future__ import annotations

import hashlib
import stat
import zipfile
from pathlib import Path

from tools.package.payload_equivalence import FileIdentity, safe_inventory_path


MAX_FILES = 20000
MAX_FILE_BYTES = 1024 * 1024 * 1024
MAX_TOTAL_BYTES = 4 * 1024 * 1024 * 1024


def zip_inventory(path: Path) -> list[FileIdentity]:
    """Inventory a ZIP or self-extracting ZIP without materializing its members."""

    if path.is_symlink() or not path.is_file():
        raise ValueError(f"ZIP payload is missing or linked: {path}")
    records: list[FileIdentity] = []
    total = 0
    seen: set[str] = set()
    with zipfile.ZipFile(path.resolve(strict=True), "r") as archive:
        for info in archive.infolist():
            authored_name = info.filename.rstrip("/")
            name = safe_inventory_path(authored_name)
            if name != authored_name:
                raise ValueError(f"non-canonical ZIP member is forbidden: {info.filename}")
            if info.is_dir():
                continue
            if info.flag_bits & 0x1:
                raise ValueError(f"encrypted ZIP member is forbidden: {info.filename}")
            unix_mode = (info.external_attr >> 16) & 0xFFFF
            if stat.S_ISLNK(unix_mode):
                raise ValueError(f"symbolic-link ZIP member is forbidden: {info.filename}")
            if name in seen:
                raise ValueError(f"duplicate ZIP member is forbidden: {info.filename}")
            seen.add(name)
            if info.file_size < 0 or info.file_size > MAX_FILE_BYTES:
                raise ValueError(f"ZIP member exceeds its byte budget: {info.filename}")
            total += info.file_size
            if total > MAX_TOTAL_BYTES:
                raise ValueError("ZIP payload exceeds its aggregate byte budget")
            digest = hashlib.sha256()
            observed = 0
            with archive.open(info, "r") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    observed += len(chunk)
                    if observed > info.file_size:
                        raise ValueError(f"ZIP member grew while reading: {info.filename}")
                    digest.update(chunk)
            if observed != info.file_size:
                raise ValueError(f"ZIP member size changed while reading: {info.filename}")
            records.append(
                FileIdentity(
                    path=name,
                    size=observed,
                    sha256=digest.hexdigest(),
                    mode=stat.S_IMODE(unix_mode) if unix_mode else None,
                )
            )
            if len(records) > MAX_FILES:
                raise ValueError("ZIP payload exceeds its file-count budget")
    if not records:
        raise ValueError("ZIP payload is empty")
    return records
