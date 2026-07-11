# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import cross_repo_check

REPO_NAMES = ("universal-setup", "universal-launcher")


def resolved_repos() -> dict[str, Path]:
    return {name: cross_repo_check.repo_root(name).resolve(strict=False) for name in REPO_NAMES}


def missing_repos(repos: dict[str, Path]) -> list[str]:
    return [name for name, path in repos.items() if not (path / "CMakeLists.txt").is_file()]


def cmake_path(path: Path) -> str:
    return path.resolve(strict=False).as_posix()


def cmake_args(repos: dict[str, Path]) -> list[str]:
    return [
        "-S",
        ".",
        "-B",
        "build/native-smoke",
        f"-DFLAUNCH_UNIVERSAL_SETUP_ROOT={cmake_path(repos['universal-setup'])}",
        f"-DFLAUNCH_UNIVERSAL_LAUNCHER_ROOT={cmake_path(repos['universal-launcher'])}",
        "-DFLAUNCH_BUILD_NATIVE_APPS=ON",
        "-DFLAUNCH_BUILD_TESTS=ON",
    ]


def cmake_command(repos: dict[str, Path]) -> str:
    return "cmake " + " ".join(quote_arg(arg) for arg in cmake_args(repos))


def quote_arg(value: str) -> str:
    if not value or any(ch.isspace() for ch in value):
        return '"' + value.replace('"', '\\"') + '"'
    return value


def cmake_user_presets(repos: dict[str, Path]) -> dict[str, object]:
    return {
        "version": 6,
        "configurePresets": [
            {
                "name": "facman-native-smoke-local",
                "displayName": "FacMan native smoke local workspace",
                "description": "Machine-local FacMan build using discovered Universal repo paths.",
                "binaryDir": "${sourceDir}/build/native-smoke",
                "cacheVariables": {
                    "FLAUNCH_UNIVERSAL_SETUP_ROOT": cmake_path(repos["universal-setup"]),
                    "FLAUNCH_UNIVERSAL_LAUNCHER_ROOT": cmake_path(repos["universal-launcher"]),
                    "FLAUNCH_BUILD_NATIVE_APPS": "ON",
                    "FLAUNCH_BUILD_TESTS": "ON",
                },
            }
        ],
    }


def write_cmake_user_presets(repos: dict[str, Path]) -> Path:
    path = ROOT / "CMakeUserPresets.json"
    path.write_text(json.dumps(cmake_user_presets(repos), indent=2) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Resolve local FacMan workspace repository paths.")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("doctor", help="Print resolved Universal repository paths.")
    subparsers.add_parser("cmake-args", help="Print a portable CMake configure command.")
    subparsers.add_parser("validate", help="Return nonzero if required Universal repos are missing.")
    subparsers.add_parser("write-cmake-user-presets", help="Write ignored CMakeUserPresets.json for this checkout.")

    args = parser.parse_args(argv)
    command = args.command or "doctor"
    repos = resolved_repos()
    missing = missing_repos(repos)

    if command == "cmake-args":
        print(cmake_command(repos))
    elif command == "write-cmake-user-presets":
        path = write_cmake_user_presets(repos)
        print(f"workspace-config: wrote {path}")
    else:
        for name in REPO_NAMES:
            status = "ok" if name not in missing else "missing"
            print(f"workspace-config: {name}={repos[name]} {status}")

    if missing:
        print(
            "workspace-config: missing required repos: "
            + ", ".join(f"{name} ({repos[name]})" for name in missing),
            file=sys.stderr,
        )
        return 1

    print("workspace-config: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
