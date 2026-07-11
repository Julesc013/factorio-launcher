# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import argparse
import hashlib
import os
import shlex
import subprocess
import sys
import tempfile
from collections.abc import Iterable, Sequence
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[1]

REPO_NAMES = ("factorio-launcher", "universal-setup", "universal-launcher")

REPO_MARKERS = {
    "factorio-launcher": [
        "CMakeLists.txt",
        "include/flb/flb_api.h",
        "runtime/factorio/binding/flb_api.c",
        "tools/strict_check.py",
    ],
    "universal-setup": [
        "CMakeLists.txt",
        "include/usk/usk_api.h",
        "runtime/setup/kernel/usk_api.c",
        "contracts/schema/setup/install_plan.v1.schema.json",
        "tools/strict_check.py",
        "apps/gui/README.md",
    ],
    "universal-launcher": [
        "CMakeLists.txt",
        "include/ulk/ulk_api.h",
        "runtime/launcher/kernel/ulk_api.c",
        "docs/architecture/command_graph.md",
        "tools/strict_check.py",
        "apps/gui/README.md",
    ],
}

SPECIFIC_ENV = {
    "universal-setup": "FLAUNCH_UNIVERSAL_SETUP_ROOT",
    "universal-launcher": "FLAUNCH_UNIVERSAL_LAUNCHER_ROOT",
}

IGNORED_PATH_PARTS = {".git", "build", "__pycache__", ".pytest_cache"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate a reproducible FacMan three-repo workspace.",
    )
    parser.add_argument(
        "--workspace-root",
        type=Path,
        help="Workspace root containing either flat repos or Factorio/ and Universal/ groups.",
    )
    parser.add_argument(
        "--factorio-root",
        type=Path,
        help="Factorio launcher checkout to validate. Defaults to this checkout or the workspace root.",
    )
    parser.add_argument(
        "--build",
        action="store_true",
        help="Run the full CMake, ctest, AIDE Lite, strict, and unittest validation matrix.",
    )
    parser.add_argument(
        "--build-root",
        type=Path,
        help="Out-of-tree build root. Defaults to a temp path keyed by the resolved repo paths.",
    )
    parser.add_argument(
        "--require-git",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Require every repository to be a Git checkout. Enabled by default.",
    )
    parser.add_argument(
        "--require-clean",
        action="store_true",
        help="Require every repository worktree to have no local changes.",
    )
    parser.add_argument(
        "--python",
        help="Python command for nested checks, such as 'py -3'. Defaults to the current interpreter.",
    )
    args = parser.parse_args(argv)

    repos = resolve_workspace_repos(args.workspace_root, args.factorio_root)
    problems = check_workspace(repos, require_git=args.require_git)
    if args.require_clean:
        problems.extend(check_clean_worktrees(repos))

    for name in REPO_NAMES:
        print(f"repro-workspace-smoke: {name}={repos[name]}")

    if problems:
        for problem in problems:
            print(f"repro-workspace-smoke: {problem}", file=sys.stderr)
        return 1

    print("repro-workspace-smoke: check-only ok")
    if not args.build:
        return 0

    return run_validation_matrix(repos, python_command(args.python), repro_build_root(repos, args.build_root))


def resolve_workspace_repos(workspace_root: Path | None = None, factorio_root: Path | None = None) -> dict[str, Path]:
    resolved_factorio = resolve_factorio_root(workspace_root, factorio_root)
    return {
        "factorio-launcher": resolved_factorio,
        "universal-setup": resolve_universal_repo("universal-setup", resolved_factorio, workspace_root),
        "universal-launcher": resolve_universal_repo("universal-launcher", resolved_factorio, workspace_root),
    }


def resolve_factorio_root(workspace_root: Path | None, factorio_root: Path | None) -> Path:
    if factorio_root is not None:
        return factorio_root.resolve(strict=False)
    if workspace_root is not None:
        for candidate in [
            workspace_root / "factorio-launcher",
            workspace_root / "Factorio" / "factorio-launcher",
        ]:
            if (candidate / "CMakeLists.txt").is_file():
                return candidate.resolve(strict=False)
    return SOURCE_ROOT.resolve(strict=False)


def resolve_universal_repo(name: str, factorio_root: Path, workspace_root: Path | None) -> Path:
    candidates = universal_candidates(name, factorio_root, workspace_root)
    for candidate in candidates:
        if (candidate / "CMakeLists.txt").is_file():
            return candidate.resolve(strict=False)
    return candidates[0].resolve(strict=False)


def universal_candidates(name: str, factorio_root: Path, workspace_root: Path | None) -> list[Path]:
    candidates: list[Path] = []
    specific = os.environ.get(SPECIFIC_ENV[name])
    universal_root = os.environ.get("FLAUNCH_UNIVERSAL_ROOT")
    env_workspace_root = os.environ.get("FLAUNCH_WORKSPACE_ROOT")

    if specific:
        candidates.append(Path(specific))
    if universal_root:
        candidates.append(Path(universal_root) / name)
    for root in [workspace_root, Path(env_workspace_root) if env_workspace_root else None]:
        if root is not None:
            candidates.append(root / "Universal" / name)
            candidates.append(root / name)

    candidates.append(factorio_root / "external" / name)
    for parent in [factorio_root.parent, *factorio_root.parents]:
        candidates.append(parent / name)
        candidates.append(parent / "Universal" / name)

    return unique_paths(candidates)


def unique_paths(paths: Iterable[Path]) -> list[Path]:
    unique: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        resolved = path.resolve(strict=False)
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(path)
    return unique


def check_workspace(repos: dict[str, Path], *, require_git: bool) -> list[str]:
    problems: list[str] = []
    problems.extend(check_repo_markers(repos, require_git=require_git))
    problems.extend(check_factorio_boundaries(repos["factorio-launcher"]))
    problems.extend(check_universal_boundaries(repos))
    return problems


def check_repo_markers(repos: dict[str, Path], *, require_git: bool) -> list[str]:
    problems: list[str] = []
    for name, markers in REPO_MARKERS.items():
        root = repos[name]
        for marker in markers:
            path = root / marker
            if not path.is_file():
                problems.append(f"{name} missing required path {path}")
        if require_git and not (root / ".git").exists():
            problems.append(f"{name} is not a Git checkout: {root}")
    return problems


def check_factorio_boundaries(root: Path) -> list[str]:
    problems: list[str] = []
    include_root = root / "include"
    if include_root.is_dir():
        include_children = {child.name for child in include_root.iterdir() if child.name != "README.md"}
        if include_children != {"flb"}:
            problems.append(f"factorio-launcher/include must expose only flb, found {sorted(include_children)}")
    else:
        problems.append(f"factorio-launcher missing include root {include_root}")

    for forbidden in ["runtime/usk", "runtime/ulk", "include/usk", "include/ulk"]:
        if (root / forbidden).exists():
            problems.append(f"factorio-launcher must not own sibling implementation path {forbidden}")
    return problems


def check_universal_boundaries(repos: dict[str, Path]) -> list[str]:
    launcher = repos["universal-launcher"]
    setup = repos["universal-setup"]
    problems: list[str] = []
    if launcher.exists():
        problems.extend(check_no_path_token(launcher, ("factorio", "mod_portal", "modset")))
        problems.extend(check_no_universal_gui_toolkit_dirs(launcher))
        for forbidden in ["runtime/setup", "include/usk"]:
            if (launcher / forbidden).exists():
                problems.append(f"universal-launcher must not own setup path {forbidden}")
    if setup.exists():
        problems.extend(check_no_path_token(setup, ("factorio", "mod_portal", "modset", "save_manager")))
        problems.extend(check_no_universal_gui_toolkit_dirs(setup))
        for forbidden in ["runtime/launcher", "include/ulk"]:
            if (setup / forbidden).exists():
                problems.append(f"universal-setup must not own launcher path {forbidden}")
    return problems


def check_no_universal_gui_toolkit_dirs(root: Path) -> list[str]:
    problems: list[str] = []
    for provider in ["win32", "appkit", "gtk", "qt", "winforms", "winui", "swiftui"]:
        path = root / "apps" / "gui" / provider
        if path.exists():
            problems.append(f"{root.name} must not own product GUI toolkit path apps/gui/{provider}")
    return problems


def check_no_path_token(root: Path, tokens: tuple[str, ...]) -> list[str]:
    problems: list[str] = []
    for path in root.rglob("*"):
        rel_parts = path.relative_to(root).parts
        if any(part in IGNORED_PATH_PARTS for part in rel_parts):
            continue
        rel = path.relative_to(root).as_posix().lower()
        for token in tokens:
            if token in rel:
                problems.append(f"{root.name} contains product-specific path {rel}")
    return problems


def check_clean_worktrees(repos: dict[str, Path]) -> list[str]:
    problems: list[str] = []
    for name, root in repos.items():
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            problems.append(f"{name} git status failed: {result.stdout.strip()}")
        elif result.stdout.strip():
            problems.append(f"{name} has local changes")
    return problems


def python_command(value: str | None) -> list[str]:
    if value is None:
        return [sys.executable]
    return shlex.split(value, posix=os.name != "nt")


def repro_build_root(repos: dict[str, Path], build_root: Path | None = None) -> Path:
    if build_root is not None:
        return build_root.resolve(strict=False)
    key = "|".join(str(repos[name].resolve(strict=False)) for name in REPO_NAMES)
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]
    return (Path(tempfile.gettempdir()) / "facman-repro-smoke" / digest).resolve(strict=False)


def repo_build_dir(build_root: Path, name: str) -> Path:
    return build_root / name


def facman_executable(build_root: Path) -> Path:
    if os.name == "nt":
        return repo_build_dir(build_root, "factorio-launcher") / "Debug" / "facman.exe"
    return repo_build_dir(build_root, "factorio-launcher") / "facman"


def run_validation_matrix(repos: dict[str, Path], python_cmd: Sequence[str], build_root: Path) -> int:
    build_dirs = {name: repo_build_dir(build_root, name) for name in REPO_NAMES}
    env = os.environ.copy()
    env["FLAUNCH_UNIVERSAL_SETUP_ROOT"] = str(repos["universal-setup"])
    env["FLAUNCH_UNIVERSAL_LAUNCHER_ROOT"] = str(repos["universal-launcher"])
    env["FACMAN_CLI_EXE"] = str(facman_executable(build_root))
    print(f"repro-workspace-smoke: build-root={build_root}")

    steps = [
        (
            "universal-launcher cmake configure",
            repos["universal-launcher"],
            ["cmake", "-S", ".", "-B", str(build_dirs["universal-launcher"])],
        ),
        ("universal-launcher cmake build", repos["universal-launcher"], ["cmake", "--build", str(build_dirs["universal-launcher"])]),
        (
            "universal-launcher ctest",
            repos["universal-launcher"],
            ["ctest", "--test-dir", str(build_dirs["universal-launcher"]), "-C", "Debug", "--output-on-failure"],
        ),
        ("universal-launcher strict", repos["universal-launcher"], [*python_cmd, "tools/strict_check.py"]),
        (
            "universal-setup cmake configure",
            repos["universal-setup"],
            ["cmake", "-S", ".", "-B", str(build_dirs["universal-setup"])],
        ),
        ("universal-setup cmake build", repos["universal-setup"], ["cmake", "--build", str(build_dirs["universal-setup"])]),
        (
            "universal-setup ctest",
            repos["universal-setup"],
            ["ctest", "--test-dir", str(build_dirs["universal-setup"]), "-C", "Debug", "--output-on-failure"],
        ),
        ("universal-setup strict", repos["universal-setup"], [*python_cmd, "tools/strict_check.py"]),
        (
            "factorio-launcher cmake configure",
            repos["factorio-launcher"],
            [
                "cmake",
                "-S",
                ".",
                "-B",
                str(build_dirs["factorio-launcher"]),
                f"-DFLAUNCH_UNIVERSAL_SETUP_ROOT={repos['universal-setup'].as_posix()}",
                f"-DFLAUNCH_UNIVERSAL_LAUNCHER_ROOT={repos['universal-launcher'].as_posix()}",
                "-DFLAUNCH_BUILD_NATIVE_APPS=ON",
                "-DFLAUNCH_BUILD_TESTS=ON",
            ],
        ),
        ("factorio-launcher cmake build", repos["factorio-launcher"], ["cmake", "--build", str(build_dirs["factorio-launcher"])]),
        (
            "factorio-launcher ctest",
            repos["factorio-launcher"],
            ["ctest", "--test-dir", str(build_dirs["factorio-launcher"]), "-C", "Debug", "--output-on-failure"],
        ),
        ("factorio-launcher aide-lite", repos["factorio-launcher"], [*python_cmd, ".aide/scripts/aide_lite.py", "test"]),
        ("factorio-launcher strict", repos["factorio-launcher"], [*python_cmd, "tools/strict_check.py"]),
        ("factorio-launcher unittest", repos["factorio-launcher"], [*python_cmd, "-m", "unittest", "discover", "-s", "tests", "-v"]),
    ]
    for label, cwd, command in steps:
        code = run_step(label, cwd, command, env)
        if code != 0:
            return code
    print("repro-workspace-smoke: build matrix ok")
    return 0


def run_step(label: str, cwd: Path, command: Sequence[str], env: dict[str, str]) -> int:
    print(f"repro-workspace-smoke: run {label}")
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print(f"repro-workspace-smoke: FAIL {label} exit={result.returncode}", file=sys.stderr)
        if result.stdout:
            print(result.stdout, file=sys.stderr)
        return result.returncode
    print(f"repro-workspace-smoke: PASS {label}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
