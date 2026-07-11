# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import subprocess
from pathlib import Path


def is_dirty(root: Path) -> bool:
    completed = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=root,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    return completed.returncode != 0 or bool(completed.stdout.strip())


def require_clean(root: Path, allow_dirty: bool) -> None:
    if is_dirty(root) and not allow_dirty:
        raise ValueError("dirty source is refused for proof packaging; pass --allow-dirty for developer output")
