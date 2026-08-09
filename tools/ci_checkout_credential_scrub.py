#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Remove only checkout@v6 temporary credential includes from a CI checkout."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

CREDENTIAL_NAME = re.compile(
    r"git-credentials-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
    r"[0-9a-f]{4}-[0-9a-f]{12}\.config",
    re.IGNORECASE,
)
MAX_CREDENTIAL_FILE_BYTES = 8192
MAX_LOCAL_CONFIG_BYTES = 1024 * 1024


def _git_config(config: Path, *args: str) -> subprocess.CompletedProcess[str]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith("GIT_")
    }
    environment.update(
        {
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_TERMINAL_PROMPT": "0",
        }
    )
    return subprocess.run(
        ["git", "config", "--file", str(config), "--no-includes", *args],
        cwd=config.parent.parent,
        env=environment,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _nul_items(completed: subprocess.CompletedProcess[str]) -> list[str]:
    if completed.returncode == 1:
        return []
    if completed.returncode != 0:
        raise ValueError("cannot inspect repository-local Git config")
    return [item for item in completed.stdout.split("\0") if item]


def _include_keys(config: Path) -> list[str]:
    keys = _nul_items(
        _git_config(
            config,
            "--name-only",
            "--null",
            "--get-regexp",
            ".*",
        )
    )
    return [
        key
        for key in keys
        if key.casefold() == "include.path"
        or (
            key.casefold().startswith("includeif.")
            and key.casefold().endswith(".path")
        )
    ]


def _values(config: Path, key: str) -> list[str]:
    return _nul_items(_git_config(config, "--null", "--get-all", key))


def _normalized_key(key: str) -> str:
    return key.replace("\\", "/").casefold()


def _require_checkout_credential_target(path: Path, root: Path) -> None:
    if not path.is_absolute():
        raise ValueError("checkout credential include must use an absolute path")
    if root.is_symlink() or path.is_symlink():
        raise ValueError("checkout credential include must not use a link")
    resolved_root = root.resolve(strict=True)
    resolved = path.resolve(strict=False)
    if resolved == resolved_root or not resolved.is_relative_to(resolved_root):
        raise ValueError("checkout credential include must remain within runner temp")
    if CREDENTIAL_NAME.fullmatch(path.name) is None:
        raise ValueError("checkout credential include has an unexpected file name")
    if not path.exists():
        return
    if not path.is_file():
        raise ValueError("checkout credential include must name a plain file")
    size = path.stat().st_size
    if size <= 0 or size > MAX_CREDENTIAL_FILE_BYTES:
        raise ValueError("checkout credential include file has an invalid size")


def scrub_checkout_credentials(repo: Path, runner_temp: Path) -> int:
    resolved_repo = repo.resolve(strict=True)
    if not resolved_repo.is_dir() or repo.is_symlink():
        raise ValueError("CI checkout root must be a plain directory")
    git_dir = resolved_repo / ".git"
    config = git_dir / "config"
    if git_dir.is_symlink() or not git_dir.is_dir():
        raise ValueError("CI checkout must use an in-tree .git directory")
    if config.is_symlink() or not config.is_file():
        raise ValueError("CI checkout Git config must be a plain file")
    resolved_git_dir = git_dir.resolve(strict=True)
    if resolved_git_dir.parent != resolved_repo:
        raise ValueError("CI checkout .git directory must remain inside its root")
    if config.resolve(strict=True).parent != resolved_git_dir:
        raise ValueError("CI checkout Git config must remain inside .git")
    config_size = config.stat().st_size
    if config_size <= 0 or config_size > MAX_LOCAL_CONFIG_BYTES:
        raise ValueError("CI checkout Git config has an invalid size")

    keys = _include_keys(config)
    if not keys:
        return 0

    git_dir_token = str(resolved_git_dir).replace("\\", "/")
    expected = {
        _normalized_key(f"includeIf.gitdir:{git_dir_token}.path"),
        _normalized_key(
            f"includeIf.gitdir:{git_dir_token}/worktrees/*.path"
        ),
    }
    actual = {_normalized_key(key) for key in keys}
    if len(keys) != 2 or actual != expected:
        raise ValueError(
            "repository includes are not the exact checkout-owned credential pair"
        )

    values_by_key = {key: _values(config, key) for key in keys}
    if any(len(values) != 1 for values in values_by_key.values()):
        raise ValueError("checkout-owned include keys must each have one value")
    credential_values = {values[0] for values in values_by_key.values()}
    if len(credential_values) != 1:
        raise ValueError("checkout-owned include keys must share one credential file")
    credential_value = next(iter(credential_values))
    credential = Path(credential_value)
    _require_checkout_credential_target(credential, runner_temp)

    for key in keys:
        removed = _git_config(
            config,
            "--fixed-value",
            "--unset-all",
            key,
            credential_value,
        )
        if removed.returncode != 0:
            raise ValueError("cannot remove verified checkout-owned credential include")
    if _include_keys(config):
        raise ValueError("repository-local Git config includes remain after credential scrub")
    return len(keys)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--runner-temp", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        removed = scrub_checkout_credentials(args.repo, args.runner_temp)
    except (OSError, ValueError) as error:
        print(f"ci-checkout-credential-scrub: {error}", file=sys.stderr)
        return 1
    print(f"ci-checkout-credential-scrub: ok ({removed} verified includes removed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
