from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECTS = ROOT.parent
UNIVERSAL_SETUP = PROJECTS / "universal-setup"
UNIVERSAL_LAUNCHER = PROJECTS / "universal-launcher"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate FacMan sibling repository boundaries.")
    parser.add_argument(
        "--product-only",
        action="store_true",
        help="Validate only rules that do not require sibling repository checkouts.",
    )
    args = parser.parse_args(argv)

    problems: list[str] = []
    problems.extend(check_factorio_repo_boundaries())
    if not args.product_only:
        problems.extend(check_sibling_repos())
        problems.extend(check_sibling_boundaries())

    if problems:
        for problem in problems:
            print(f"cross-repo-check: {problem}", file=sys.stderr)
        return 1
    print("cross-repo-check: ok")
    return 0


def check_factorio_repo_boundaries() -> list[str]:
    problems: list[str] = []
    include_children = {child.name for child in (ROOT / "include").iterdir() if child.name != "README.md"}
    if include_children != {"flb"}:
        problems.append(f"factorio-launcher/include must expose only flb, found {sorted(include_children)}")
    for forbidden in ["runtime/usk", "runtime/ulk", "include/usk", "include/ulk"]:
        if (ROOT / forbidden).exists():
            problems.append(f"factorio-launcher must not own sibling implementation path {forbidden}")
    return problems


def check_sibling_repos() -> list[str]:
    required = [
        UNIVERSAL_SETUP / "include" / "usk" / "usk_api.h",
        UNIVERSAL_SETUP / "runtime" / "setup" / "kernel" / "usk_api.c",
        UNIVERSAL_SETUP / "contracts" / "schema" / "setup" / "install_plan.v1.schema.json",
        UNIVERSAL_LAUNCHER / "include" / "ulk" / "ulk_api.h",
        UNIVERSAL_LAUNCHER / "runtime" / "launcher" / "kernel" / "ulk_api.c",
        UNIVERSAL_LAUNCHER / "docs" / "architecture" / "command_graph.md",
    ]
    return [f"missing sibling path {path}" for path in required if not path.exists()]


def check_sibling_boundaries() -> list[str]:
    problems: list[str] = []
    if UNIVERSAL_LAUNCHER.exists():
        problems.extend(check_no_path_token(UNIVERSAL_LAUNCHER, ("factorio", "mod_portal", "modset")))
        for forbidden in ["runtime/setup", "include/usk"]:
            if (UNIVERSAL_LAUNCHER / forbidden).exists():
                problems.append(f"universal-launcher must not own setup path {forbidden}")
    if UNIVERSAL_SETUP.exists():
        problems.extend(check_no_path_token(UNIVERSAL_SETUP, ("factorio", "mod_portal", "modset", "save_manager")))
        for forbidden in ["runtime/launcher", "include/ulk"]:
            if (UNIVERSAL_SETUP / forbidden).exists():
                problems.append(f"universal-setup must not own launcher path {forbidden}")
    return problems


def check_no_path_token(root: Path, tokens: tuple[str, ...]) -> list[str]:
    problems: list[str] = []
    ignored = {".git", "build", "__pycache__", ".pytest_cache"}
    for path in root.rglob("*"):
        rel_parts = path.relative_to(root).parts
        if any(part in ignored for part in rel_parts):
            continue
        rel = path.relative_to(root).as_posix().lower()
        for token in tokens:
            if token in rel:
                problems.append(f"{root.name} contains product-specific path {rel}")
    return problems


if __name__ == "__main__":
    raise SystemExit(main())
