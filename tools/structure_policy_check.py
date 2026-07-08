from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ALLOWED_TOP_LEVEL = {
    ".aide",
    ".aide.local.example",
    ".agents",
    ".codex",
    ".github",
    ".gitignore",
    "AGENTS.md",
    "CHANGELOG.md",
    "CMakeLists.txt",
    "CODE_OF_CONDUCT.md",
    "CONTRIBUTING.md",
    "LICENSE",
    "README.md",
    "SECURITY.md",
    "THIRD_PARTY_NOTICES.md",
    "apps",
    "cmake",
    "data",
    "docs",
    "examples",
    "external",
    "include",
    "packaging",
    "pyproject.toml",
    "schemas",
    "source",
    "tests",
    "tools",
}

IGNORED_TOP_LEVEL = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "bin",
    "build",
    "dist",
    "factorio_workspace",
    "obj",
    "out",
}

RETIRED_ROOTS = {
    "cli",
    "daemon",
    "factorio",
    "gui",
    "launcher",
    "product",
    "prototypes",
    "src",
    "tui",
    "universal",
}

FRONTENDS = {
    "appkit",
    "factorio_cli",
    "factorio_daemon",
    "factorio_tui",
    "gtk",
    "qt",
    "winforms",
}

SHELL_ALLOWED_FILES = {
    "README.md",
    "CMakeLists.txt",
    "meson.build",
}

SHELL_ALLOWED_SUFFIXES = {
    ".plist",
    ".sln",
    ".vcxproj",
    ".vcxproj.filters",
    ".xcodeproj",
}

CODE_SUFFIXES = {
    ".c",
    ".cc",
    ".cpp",
    ".cs",
    ".go",
    ".h",
    ".hpp",
    ".java",
    ".kt",
    ".m",
    ".mm",
    ".py",
    ".rs",
    ".swift",
}

ALLOWED_DATA_ROOTS = {"factorio"}
ALLOWED_FACTORIO_DATA_ROOTS = {
    "discovery",
    "instance_templates",
    "launch_templates",
    "mod_portal",
    "policy",
    "product",
    "redaction",
}

ALLOWED_SCHEMA_ROOTS = {"common", "factorio", "packaging", "ulk", "usk"}
ALLOWED_PACKAGING_ROOTS = {"linux", "macos", "portable", "windows"}
ALLOWED_SOURCE_ROOTS = {
    "apps",
    "base",
    "client",
    "factorio",
    "platform",
    "prototypes",
    "runtime",
    "ulk",
    "usk",
}


def main() -> int:
    problems: list[str] = []
    problems.extend(check_top_level())
    problems.extend(check_retired_roots())
    problems.extend(check_single_source_root())
    problems.extend(check_root_namespaces())
    problems.extend(check_apps_are_shells())
    problems.extend(check_include_is_public_abi_only())
    problems.extend(check_data_is_not_code())
    problems.extend(check_command_graph_spine())
    problems.extend(check_aide_is_not_runtime_dependency())
    if problems:
        for problem in problems:
            print(f"structure-check: {problem}", file=sys.stderr)
        return 1
    print("structure-check: ok")
    return 0


def check_top_level() -> list[str]:
    problems: list[str] = []
    for path in ROOT.iterdir():
        name = path.name
        if name in IGNORED_TOP_LEVEL or name.endswith(".egg-info"):
            continue
        if name == ".aide":
            problems.extend(check_aide_root(path))
            continue
        if name not in ALLOWED_TOP_LEVEL:
            problems.append(f"unexpected top-level path {name}")
    return problems


def check_aide_root(path: Path) -> list[str]:
    problems: list[str] = []
    generated_or_local = {"local"}
    required = {
        "memory",
        "policies",
        "profile.yaml",
        "scripts",
    }
    existing = {child.name for child in path.iterdir()}
    missing = required - existing
    for name in sorted(missing):
        problems.append(f".aide/ missing imported AIDE Lite path {name}")
    for child in path.iterdir():
        if child.name in generated_or_local:
            continue
        if child.name == ".aide.local" or child.name.lower().endswith(".secret"):
            problems.append(f".aide/{child.name} must not contain local secrets")
    return problems


def check_retired_roots() -> list[str]:
    problems: list[str] = []
    for name in sorted(RETIRED_ROOTS):
        if (ROOT / name).exists():
            problems.append(f"retired root must not exist: {name}/")
    return problems


def check_single_source_root() -> list[str]:
    problems: list[str] = []
    source_dirs = sorted(path for path in ROOT.rglob("*") if path.is_dir() and path.name == "source")
    if source_dirs != [ROOT / "source"]:
        problems.append("source/ must be the only directory named source")
        for path in source_dirs:
            problems.append(f"found source directory at {path.relative_to(ROOT)}")
    for path in sorted(ROOT.rglob("*")):
        if path.is_dir() and path.name == "src":
            problems.append(f"directory named src is forbidden: {path.relative_to(ROOT)}")
    return problems


def check_root_namespaces() -> list[str]:
    problems: list[str] = []
    problems.extend(check_children("source", ALLOWED_SOURCE_ROOTS))
    problems.extend(check_children("data", ALLOWED_DATA_ROOTS))
    problems.extend(check_children("data/factorio", ALLOWED_FACTORIO_DATA_ROOTS))
    problems.extend(check_children("schemas", ALLOWED_SCHEMA_ROOTS))
    problems.extend(check_children("packaging", ALLOWED_PACKAGING_ROOTS))
    return problems


def check_children(relative_root: str, allowed: set[str]) -> list[str]:
    problems: list[str] = []
    root = ROOT / relative_root
    if not root.exists():
        problems.append(f"missing required root {relative_root}/")
        return problems
    for child in root.iterdir():
        if child.name == "README.md":
            continue
        if child.is_dir() and child.name in allowed:
            continue
        if child.is_file() and relative_root == "schemas" and child.suffix == ".json":
            problems.append(f"schema file must live in a schema namespace: {child.relative_to(ROOT)}")
            continue
        problems.append(f"{relative_root}/ contains unexpected path {child.name}")
    return problems


def check_apps_are_shells() -> list[str]:
    problems: list[str] = []
    apps = ROOT / "apps"
    source_apps = ROOT / "source" / "apps"
    for name in sorted(FRONTENDS):
        if not (apps / name).is_dir():
            problems.append(f"missing app shell apps/{name}/")
        if not (source_apps / name).is_dir():
            problems.append(f"missing app implementation source/apps/{name}/")
    for path in apps.rglob("*"):
        if path.is_dir():
            if path.name in {"src", "source"}:
                problems.append(f"app shell must not contain nested source root: {path.relative_to(ROOT)}")
            continue
        if path.name in SHELL_ALLOWED_FILES:
            continue
        if any(path.name.endswith(suffix) for suffix in SHELL_ALLOWED_SUFFIXES):
            continue
        if path.suffix.lower() in CODE_SUFFIXES:
            problems.append(f"app shell contains implementation source: {path.relative_to(ROOT)}")
    return problems


def check_include_is_public_abi_only() -> list[str]:
    problems: list[str] = []
    include = ROOT / "include"
    allowed = {"flb", "ulk", "usk"}
    for child in include.iterdir():
        if child.is_dir() and child.name in allowed:
            continue
        problems.append(f"include/ contains non-ABI path {child.name}")
    for path in include.rglob("*"):
        if path.is_file() and path.suffix.lower() not in {".h", ".md"}:
            problems.append(f"include/ may contain only public C headers/docs: {path.relative_to(ROOT)}")
    return problems


def check_data_is_not_code() -> list[str]:
    problems: list[str] = []
    for path in (ROOT / "data").rglob("*"):
        if path.is_file() and path.suffix.lower() in CODE_SUFFIXES:
            problems.append(f"data/ must not contain executable source: {path.relative_to(ROOT)}")
    return problems


def check_command_graph_spine() -> list[str]:
    required = [
        ROOT / "source" / "ulk" / "command",
        ROOT / "schemas" / "ulk" / "command.v1.schema.json",
        ROOT / "tests" / "contract" / "command_graph",
        ROOT / "source" / "factorio" / "binding",
    ]
    return [f"missing command graph spine path {path.relative_to(ROOT)}" for path in required if not path.exists()]


def check_aide_is_not_runtime_dependency() -> list[str]:
    problems: list[str] = []
    pyproject = ROOT / "pyproject.toml"
    if pyproject.is_file() and "aide" in pyproject.read_text(encoding="utf-8").lower():
        problems.append("pyproject.toml must not add AIDE as a runtime dependency")
    for path in ROOT.joinpath("packaging").glob("**/*.toml"):
        text = path.read_text(encoding="utf-8").lower()
        if ".aide" in text or "aide" in text:
            problems.append(f"production package manifest must not bundle AIDE: {path.relative_to(ROOT)}")
    return problems


if __name__ == "__main__":
    raise SystemExit(main())
