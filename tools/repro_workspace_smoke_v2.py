# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Repository-role-aware successor to the immutable v1 workspace smoke."""

from __future__ import annotations

import contextlib
import sys
from collections.abc import Iterator
from pathlib import Path

from tools import repository_identity
from tools import repro_workspace_smoke as v1


FACMAN_IDENTITY = repository_identity.identity("facman")
FACMAN_WORKSPACE_NAMES = FACMAN_IDENTITY.workspace_names
REPO_NAMES = v1.REPO_NAMES
REPO_MARKERS = v1.REPO_MARKERS


def resolve_workspace_repos(
    workspace_root: Path | None = None,
    factorio_root: Path | None = None,
    *,
    facman_root: Path | None = None,
) -> dict[str, Path]:
    """Resolve both supported FacMan directory names and explicit providers."""

    resolved_facman = resolve_facman_root(
        workspace_root,
        facman_root if facman_root is not None else factorio_root,
    )
    return {
        "factorio-launcher": resolved_facman,
        "universal-setup": v1.resolve_universal_repo(
            "universal-setup", resolved_facman, workspace_root
        ),
        "universal-launcher": v1.resolve_universal_repo(
            "universal-launcher", resolved_facman, workspace_root
        ),
    }


def resolve_facman_root(
    workspace_root: Path | None,
    facman_root: Path | None,
) -> Path:
    if facman_root is not None:
        return facman_root.resolve(strict=False)
    if workspace_root is not None:
        for name in FACMAN_WORKSPACE_NAMES:
            for candidate in (
                workspace_root / name,
                workspace_root / "Factorio" / name,
            ):
                if (candidate / "CMakeLists.txt").is_file():
                    return candidate.resolve(strict=False)
    return v1.SOURCE_ROOT.resolve(strict=False)


@contextlib.contextmanager
def _role_aware_resolution() -> Iterator[None]:
    original = v1.resolve_workspace_repos
    v1.resolve_workspace_repos = resolve_workspace_repos
    try:
        yield
    finally:
        v1.resolve_workspace_repos = original


def main(argv: list[str] | None = None) -> int:
    translated = [
        "--factorio-root" if item == "--facman-root" else item
        for item in (sys.argv[1:] if argv is None else argv)
    ]
    with _role_aware_resolution():
        return v1.main(translated)


def __getattr__(name: str) -> object:
    return getattr(v1, name)


if __name__ == "__main__":
    raise SystemExit(main())
