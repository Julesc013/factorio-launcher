from __future__ import annotations

from pathlib import Path


TARGETS = {
    "facman_cli": ("bin/facman.exe", "bin/facman"),
    "facman_tui": ("bin/facman-tui.exe", "bin/facman-tui"),
    "facman_daemon": ("bin/facmand.exe", "bin/facmand"),
    "ulk_shared": ("bin/ulk.dll", "lib/libulk.so", "lib/libulk.dylib"),
    "usk_shared": ("bin/usk.dll", "lib/libusk.so", "lib/libusk.dylib"),
    "flb_factorio_shared": ("bin/flb_factorio.dll", "lib/libflb_factorio.so", "lib/libflb_factorio.dylib"),
    "apps/gui/windows/winforms": ("bin/FacMan.WinForms.exe",),
}


def resolve(install_root: Path, source_target: str) -> Path:
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
