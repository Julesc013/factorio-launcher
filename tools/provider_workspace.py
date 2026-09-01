#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Materialize immutable, detached provider inputs at the workspace-lock pins."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import cross_repo_check, development_layout  # noqa: E402


LOCK = ROOT / "release" / "index" / "workspace_lock.v1.toml"
PROVIDERS = ("universal_launcher", "universal_setup")


def capture(command: list[str], cwd: Path) -> str:
    completed = subprocess.run(
        command,
        cwd=cwd,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode:
        raise ValueError(completed.stderr.strip() or completed.stdout.strip())
    return completed.stdout.strip()


def locked_components() -> dict[str, dict[str, str]]:
    with LOCK.open("rb") as stream:
        document = tomllib.load(stream)
    components = {
        str(item["id"]): {str(key): str(value) for key, value in item.items()}
        for item in document.get("component", [])
        if isinstance(item, dict) and item.get("id") in PROVIDERS
    }
    if set(components) != set(PROVIDERS):
        raise ValueError("workspace lock must contain exactly the required provider identities")
    return components


def source_checkout(component: dict[str, str]) -> Path | str:
    repository_name = component["source"]
    configured = os.environ.get(
        "FLAUNCH_UNIVERSAL_LAUNCHER_ROOT"
        if repository_name == "universal-launcher"
        else "FLAUNCH_UNIVERSAL_SETUP_ROOT",
        "",
    ).strip()
    candidates = [Path(configured)] if configured else []
    candidates.extend(cross_repo_check.candidate_roots(repository_name))
    for candidate in candidates:
        if (candidate / ".git").exists() and (candidate / "CMakeLists.txt").is_file():
            try:
                capture(["git", "cat-file", "-e", f"{component['pin']}^{{commit}}"], candidate)
            except ValueError:
                continue
            return candidate.resolve()
    remote = component.get("remote", "")
    if not remote:
        raise ValueError(f"no checkout or remote can supply {repository_name} at {component['pin']}")
    return remote


def verify_checkout(path: Path, component: dict[str, str]) -> None:
    head = capture(["git", "rev-parse", "HEAD"], path)
    tree = capture(["git", "rev-parse", "HEAD^{tree}"], path)
    status = capture(["git", "status", "--porcelain=v1", "--untracked-files=normal"], path)
    if head != component["pin"] or tree != component["tree"] or status:
        raise ValueError(
            f"provider cache identity mismatch for {component['id']}: "
            f"head={head} tree={tree} dirty={bool(status)}"
        )


def prepare(task_root: Path) -> dict[str, Path]:
    task_root = development_layout.ensure_task_root(
        task_root, ROOT, development_layout.current_task_id(ROOT)
    )
    provider_root = task_root / "providers"
    provider_root.mkdir(parents=True, exist_ok=True)
    roots: dict[str, Path] = {}
    records: list[dict[str, str]] = []
    for provider_id, component in sorted(locked_components().items()):
        destination = provider_root / f"{component['source']}-{component['pin'][:12]}"
        if not destination.exists():
            source = source_checkout(component)
            temporary = Path(tempfile.mkdtemp(prefix=f".{component['source']}.", dir=provider_root))
            try:
                shutil.rmtree(temporary)
                subprocess.run(
                    ["git", "clone", "--no-checkout", "--no-hardlinks", str(source), str(temporary)],
                    cwd=ROOT,
                    check=True,
                )
                subprocess.run(
                    ["git", "checkout", "--detach", component["pin"]],
                    cwd=temporary,
                    check=True,
                )
                subprocess.run(
                    ["git", "remote", "set-url", "origin", component["remote"]],
                    cwd=temporary,
                    check=True,
                )
                verify_checkout(temporary, component)
                temporary.replace(destination)
            except Exception:
                shutil.rmtree(temporary, ignore_errors=True)
                raise
        subprocess.run(
            ["git", "remote", "set-url", "origin", component["remote"]],
            cwd=destination,
            check=True,
        )
        verify_checkout(destination, component)
        roots[provider_id] = destination
        records.append(
            {
                "id": provider_id,
                "path": str(destination),
                "revision": component["pin"],
                "tree": component["tree"],
                "custody": "detached_marker_owned_external_cache",
            }
        )
    manifest = {
        "schema": "facman.exact_provider_workspace.v1",
        "workspace_lock": str(LOCK),
        "providers": records,
    }
    (provider_root / "manifest.v1.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return roots


def cmake_arguments(roots: dict[str, Path]) -> list[str]:
    return [
        f"-DFLAUNCH_UNIVERSAL_LAUNCHER_ROOT={roots['universal_launcher'].as_posix()}",
        f"-DFLAUNCH_UNIVERSAL_SETUP_ROOT={roots['universal_setup'].as_posix()}",
        f"-DFACMAN_PROVIDER_LOCK_FILE={LOCK.as_posix()}",
    ]


def environment(roots: dict[str, Path]) -> dict[str, str]:
    values = os.environ.copy()
    values["FLAUNCH_UNIVERSAL_LAUNCHER_ROOT"] = str(roots["universal_launcher"])
    values["FLAUNCH_UNIVERSAL_SETUP_ROOT"] = str(roots["universal_setup"])
    return values


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--task-root",
        type=Path,
        default=development_layout.default_task_root(ROOT),
    )
    args = parser.parse_args()
    roots = prepare(args.task_root.resolve())
    print(
        json.dumps(
            {key: str(value) for key, value in sorted(roots.items())},
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
