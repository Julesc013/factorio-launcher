# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Remove only actions/checkout's verified temporary credential includes."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
CREDENTIAL_NAME = re.compile(
    r"^git-credentials-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
    r"[0-9a-f]{4}-[0-9a-f]{12}\.config$",
    re.IGNORECASE,
)
POSIX_RUNNER_TEMP = PurePosixPath("/github/runner_temp")


class CleanupFailure(ValueError):
    pass


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.update(
        {
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_TERMINAL_PROMPT": "0",
        }
    )
    return subprocess.run(
        ["git", *args],
        cwd=root,
        env=environment,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _local_config(root: Path) -> list[tuple[str, str]]:
    result = _git(root, "config", "--local", "--no-includes", "--null", "--list")
    if result.returncode != 0:
        raise CleanupFailure("cannot inspect repository-local Git configuration")
    entries: list[tuple[str, str]] = []
    for record in result.stdout.split("\0"):
        if not record:
            continue
        if "\n" not in record:
            raise CleanupFailure("repository-local Git configuration is malformed")
        entries.append(tuple(record.split("\n", 1)))
    return entries


def _include_entries(root: Path) -> list[tuple[str, str]]:
    return [
        (key, value)
        for key, value in _local_config(root)
        if key.casefold() == "include.path"
        or (key.casefold().startswith("includeif.") and key.casefold().endswith(".path"))
    ]


def cleanup(root: Path, runner_temp: Path) -> int:
    root = root.resolve(strict=True)
    runner_temp = runner_temp.resolve(strict=True)
    includes = _include_entries(root)
    if not includes:
        return 0

    direct_names: set[str] = set()
    alias_names: set[str] = set()
    for key, value in includes:
        lowered = key.casefold()
        if not lowered.startswith("includeif.gitdir:") or not lowered.endswith(".path"):
            raise CleanupFailure(f"refusing non-checkout Git include key: {key}")
        normalized = value.replace("\\", "/")
        posix_value = PurePosixPath(normalized)
        name = posix_value.name
        if CREDENTIAL_NAME.fullmatch(name) is None:
            raise CleanupFailure(f"refusing non-checkout Git include value for {key}")
        if posix_value.parent == POSIX_RUNNER_TEMP:
            alias_names.add(name.casefold())
            continue
        candidate = Path(value)
        if not candidate.is_absolute() or candidate.parent.resolve(strict=True) != runner_temp:
            raise CleanupFailure(f"refusing Git include outside RUNNER_TEMP for {key}")
        direct_names.add(candidate.name.casefold())

    if not direct_names:
        raise CleanupFailure("temporary credential aliases lack a verified RUNNER_TEMP file")
    if not alias_names.issubset(direct_names):
        raise CleanupFailure("temporary credential alias differs from the verified file")

    for key, value in includes:
        result = _git(
            root,
            "config",
            "--local",
            "--fixed-value",
            "--unset-all",
            key,
            value,
        )
        if result.returncode != 0:
            raise CleanupFailure(f"cannot remove verified checkout credential include: {key}")
    remaining = _include_entries(root)
    if remaining:
        raise CleanupFailure("repository-local Git includes remain after cleanup")
    return len(includes)


def main() -> int:
    runner_temp = os.environ.get("RUNNER_TEMP")
    if not runner_temp:
        print("ci-checkout-credential-cleanup: RUNNER_TEMP is required", file=sys.stderr)
        return 2
    try:
        count = cleanup(ROOT, Path(runner_temp))
    except (CleanupFailure, OSError) as exc:
        print(f"ci-checkout-credential-cleanup: {exc}", file=sys.stderr)
        return 1
    print(f"ci-checkout-credential-cleanup: removed {count} verified include(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
