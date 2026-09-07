# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

from pathlib import Path, PurePosixPath


EXTERNAL_TARGETS = frozenset({"apps/gui/windows/winforms"})

TARGETS = {
    "facman_cli": ("bin/facman.exe", "bin/facman"),
    "facman_tui": ("bin/facman-tui.exe", "bin/facman-tui"),
    "facman_daemon": ("bin/facmand.exe", "bin/facmand"),
    "ulk_shared": ("bin/ulk.dll", "lib/libulk.so", "lib/libulk.dylib"),
    "usk_shared": ("bin/usk.dll", "lib/libusk.so", "lib/libusk.dylib"),
    "flb_factorio_shared": ("bin/flb_factorio.dll", "lib/libflb_factorio.so", "lib/libflb_factorio.dylib"),
    "facman.resources": ("share/facman/facman.resources", "facman.resources"),
}


def resolve(
    install_root: Path, source_target: str, *, destination: str | None = None
) -> Path:
    if source_target in EXTERNAL_TARGETS:
        # External builds are staged at the admitted bundle destination.
        # A filename alias can resolve to the native CLI on Windows.
        if not destination:
            raise ValueError(f"install tree is missing component target: {source_target}; exact destination required")
        relative = PurePosixPath(destination)
        if "\\" in destination or ":" in destination or relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"external component destination must be relative and portable: {destination}")
        candidate = install_root / relative
        if not candidate.is_file():
            raise ValueError(f"missing source file: {candidate}")
        return candidate
    for relative in TARGETS.get(source_target, (source_target,)):
        candidate = install_root / relative
        if candidate.is_file():
            return candidate
    raise ValueError(f"install tree is missing component target: {source_target}")


def tree(install_root: Path, source_target: str) -> Path:
    mapping = {
        "contracts/schema": "share/facman/contracts/schema",
        "content/factorio": "share/facman/content/factorio",
    }
    candidate = install_root / mapping[source_target]
    if not candidate.is_dir():
        raise ValueError(f"install tree is missing component tree: {source_target}")
    return candidate
