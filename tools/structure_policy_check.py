# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ALLOWED_TOP_LEVEL = {
    ".aide",
    ".aide.local.example",
    ".agents",
    ".codex",
    ".gitattributes",
    ".github",
    ".gitignore",
    "AGENTS.md",
    "CHANGELOG.md",
    "CMakeLists.txt",
    "CMakePresets.json",
    "CODE_OF_CONDUCT.md",
    "CONTRIBUTING.md",
    "LICENSE",
    "LICENSES",
    "README.md",
    "REUSE.toml",
    "SECURITY.md",
    "THIRD_PARTY_NOTICES.md",
    "apps",
    "archive",
    "cmake",
    "content",
    "contracts",
    "docs",
    "examples",
    "external",
    "include",
    "release",
    "runtime",
    "tests",
    "tools",
}

# This is the executable source of truth for the AIDE target root-authority
# policy.  Roots omitted from this table are repository metadata, not product
# ownership roots.  A false value means the root is deliberately
# non-authoritative (for example explanatory docs or quarantined history).
AIDE_ROOT_AUTHORITY = {
    ".aide": False,
    "apps": True,
    "archive": False,
    "cmake": True,
    "content": True,
    "contracts": True,
    "docs": False,
    "examples": False,
    "external": True,
    "include": True,
    "LICENSES": True,
    "release": True,
    "runtime": True,
    "tests": True,
    "tools": True,
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
    "data",
    "packaging",
    "product",
    "prototypes",
    "schemas",
    "source",
    "src",
    "tui",
    "universal",
}

FRONTENDS = {"cli", "daemon", "gui", "tui"}
GUI_PROVIDERS = {
    "windows/winforms",
    "windows/winui",
    "macos/appkit",
    "macos/swiftui",
    "linux/gtk",
    "linux/qt",
}
GUI_OS_ROOTS = {"windows", "macos", "linux"}

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

ALLOWED_CONTENT_ROOTS = {"factorio"}
ALLOWED_FACTORIO_CONTENT_ROOTS = {
    "discovery",
    "instance_templates",
    "launch_templates",
    "mod_portal",
    "policy",
    "product",
    "redaction",
    "strings",
    "ui",
}

ALLOWED_CONTRACT_ROOTS = {"abi", "command", "generated-index", "policy", "result", "refusal", "diagnostic", "schema"}
ALLOWED_SCHEMA_ROOTS = {"command", "common", "facman", "factorio", "release", "transport", "ui"}
ALLOWED_RELEASE_ROOTS = {"index", "packaging", "profiles"}
ALLOWED_PACKAGING_ROOTS = {"common", "linux", "macos", "portable", "windows"}
ALLOWED_RELEASE_PROFILE_ROOTS = {
    "dev",
    "linux_portable_cli_x64",
    "linux_portable_tui_x64",
    "linux_x11_gtk_x64",
    "linux_wayland_qt",
    "linux_x11_gtk",
    "macos_legacy_appkit_x64",
    "macos_portable_cli_x64",
    "macos_portable_tui_x64",
    "macos_legacy_appkit",
    "macos_modern_swiftui",
    "portable",
    "portable_cli",
    "portable_cli_x64",
    "portable_tui",
    "portable_tui_x64",
    "windows_legacy_winforms_x64",
    "windows_portable_cli_x64",
    "windows_portable_tui_x64",
    "windows_legacy_winforms",
    "windows_modern_winui",
}
ALLOWED_RUNTIME_ROOTS = {
    "archive",
    "base",
    "client",
    "core",
    "factorio",
    "package",
    "platform",
    "transaction",
    "workspace",
}
ALLOWED_FACTORIO_RUNTIME_ROOTS = {
    "accounts",
    "application",
    "binding",
    "compat",
    "diagnostics",
    "discovery",
    "install_validation",
    "instance",
    "launch",
    "mod_portal",
    "mods",
    "modsets",
    "redaction",
    "saves",
    "server",
}


def main() -> int:
    problems: list[str] = []
    problems.extend(check_top_level())
    problems.extend(check_retired_roots())
    problems.extend(check_no_src_or_source_dirs())
    problems.extend(check_root_namespaces())
    problems.extend(check_apps_are_shells())
    problems.extend(check_include_is_public_abi_only())
    problems.extend(check_data_is_not_code())
    problems.extend(check_command_graph_spine())
    problems.extend(check_python_is_not_product_runtime())
    problems.extend(check_aide_is_not_runtime_dependency())
    problems.extend(check_facman_identity())
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


def check_no_src_or_source_dirs() -> list[str]:
    problems: list[str] = []
    source_dirs = sorted(path for path in ROOT.rglob("*") if path.is_dir() and path.name == "source")
    for path in source_dirs:
        problems.append(f"directory named source is retired: {path.relative_to(ROOT)}")
    for path in sorted(ROOT.rglob("*")):
        if path.is_dir() and path.name == "src":
            problems.append(f"directory named src is forbidden: {path.relative_to(ROOT)}")
    return problems


def check_root_namespaces() -> list[str]:
    problems: list[str] = []
    problems.extend(check_children("runtime", ALLOWED_RUNTIME_ROOTS))
    problems.extend(check_children("content", ALLOWED_CONTENT_ROOTS))
    problems.extend(check_children("content/factorio", ALLOWED_FACTORIO_CONTENT_ROOTS))
    problems.extend(check_children("contracts", ALLOWED_CONTRACT_ROOTS))
    problems.extend(check_children("contracts/schema", ALLOWED_SCHEMA_ROOTS))
    problems.extend(check_children("release", ALLOWED_RELEASE_ROOTS))
    problems.extend(check_children("release/packaging", ALLOWED_PACKAGING_ROOTS))
    problems.extend(check_children("release/profiles", ALLOWED_RELEASE_PROFILE_ROOTS))
    problems.extend(check_children("runtime/factorio", ALLOWED_FACTORIO_RUNTIME_ROOTS))
    problems.extend(check_no_language_version_runtime_buckets())
    return problems


def check_children(relative_root: str, allowed: set[str]) -> list[str]:
    problems: list[str] = []
    root = ROOT / relative_root
    if not root.exists():
        problems.append(f"missing required root {relative_root}/")
        return problems
    for child in root.iterdir():
        if child.name in {"README.md", "CMakeLists.txt"}:
            continue
        if relative_root == "release/profiles" and child.name == "profile_catalog.v1.toml":
            continue
        if child.is_dir() and child.name in allowed:
            continue
        if child.is_file() and relative_root.endswith("schema") and child.suffix == ".json":
            problems.append(f"schema file must live in a schema namespace: {child.relative_to(ROOT)}")
            continue
        problems.append(f"{relative_root}/ contains unexpected path {child.name}")
    return problems


def check_apps_are_shells() -> list[str]:
    problems: list[str] = []
    apps = ROOT / "apps"
    for name in sorted(FRONTENDS):
        if not (apps / name).is_dir():
            problems.append(f"missing app root apps/{name}/")
    for name in sorted(GUI_PROVIDERS):
        if not (apps / "gui" / Path(name)).is_dir():
            problems.append(f"missing GUI provider apps/gui/{name}/")
    gui_root = apps / "gui"
    for child in gui_root.iterdir():
        if child.name == "README.md":
            continue
        if child.is_dir() and child.name in GUI_OS_ROOTS:
            continue
        problems.append(f"apps/gui/ contains unexpected provider root {child.name}")
    for old_name in ["appkit", "gtk", "qt", "win32", "winforms"]:
        if (apps / old_name).exists():
            problems.append(f"GUI provider must live under apps/gui/, not apps/{old_name}/")
        if (gui_root / old_name).exists():
            problems.append(f"GUI provider must be OS-first, not apps/gui/{old_name}/")
    for path in apps.rglob("*"):
        if path.is_dir():
            if path.name in {"src", "source"}:
                problems.append(f"app shell must not contain nested source root: {path.relative_to(ROOT)}")
            continue
        if path.name in SHELL_ALLOWED_FILES:
            continue
        if any(path.name.endswith(suffix) for suffix in SHELL_ALLOWED_SUFFIXES):
            continue
    return problems


def check_include_is_public_abi_only() -> list[str]:
    problems: list[str] = []
    include = ROOT / "include"
    allowed = {"flb"}
    for child in include.iterdir():
        if child.name == "README.md":
            continue
        if child.is_dir() and child.name in allowed:
            continue
        problems.append(f"include/ contains non-ABI path {child.name}")
    for path in include.rglob("*"):
        if path.is_file() and path.suffix.lower() not in {".h", ".md"}:
            problems.append(f"include/ may contain only public C headers/docs: {path.relative_to(ROOT)}")
    return problems


def check_data_is_not_code() -> list[str]:
    problems: list[str] = []
    for path in (ROOT / "content").rglob("*"):
        if path.is_file() and path.suffix.lower() in CODE_SUFFIXES:
            problems.append(f"content/ must not contain executable source: {path.relative_to(ROOT)}")
    return problems


def check_no_language_version_runtime_buckets() -> list[str]:
    problems: list[str] = []
    forbidden = {"c11", "cpp11", "c17", "cpp17", "cxx11", "cxx17"}
    for path in (ROOT / "runtime").rglob("*"):
        if path.is_dir() and path.name.lower() in forbidden:
            problems.append(f"runtime folders must be domain-based, not language-version buckets: {path.relative_to(ROOT)}")
    return problems


def check_command_graph_spine() -> list[str]:
    required = [
        ROOT / "tests" / "contract" / "command_graph",
        ROOT / "runtime" / "factorio" / "binding",
        ROOT / "runtime" / "factorio" / "install_validation",
        ROOT / "runtime" / "factorio" / "modsets",
        ROOT / "contracts" / "abi" / "flb",
        ROOT / "contracts" / "command" / "factorio",
        ROOT / "contracts" / "result",
        ROOT / "contracts" / "refusal",
        ROOT / "contracts" / "diagnostic",
        ROOT / "contracts" / "policy",
        ROOT / "contracts" / "schema" / "factorio",
        ROOT / "contracts" / "schema" / "common",
        ROOT / "contracts" / "schema" / "ui",
        ROOT / "release" / "profiles" / "dev",
        ROOT / "release" / "profiles" / "windows_legacy_winforms",
        ROOT / "release" / "profiles" / "windows_modern_winui",
        ROOT / "release" / "profiles" / "macos_legacy_appkit",
        ROOT / "release" / "profiles" / "macos_modern_swiftui",
        ROOT / "release" / "profiles" / "linux_x11_gtk",
        ROOT / "release" / "profiles" / "linux_wayland_qt",
        ROOT / "release" / "profiles" / "portable_cli",
        ROOT / "release" / "profiles" / "portable_tui_x64",
        ROOT / "release" / "profiles" / "windows_legacy_winforms_x64",
        ROOT / "release" / "profiles" / "macos_legacy_appkit_x64",
        ROOT / "release" / "profiles" / "linux_x11_gtk_x64",
    ]
    return [f"missing command graph spine path {path.relative_to(ROOT)}" for path in required if not path.exists()]


def check_aide_is_not_runtime_dependency() -> list[str]:
    problems: list[str] = []
    pyproject = ROOT / "pyproject.toml"
    if pyproject.is_file() and "aide" in pyproject.read_text(encoding="utf-8").lower():
        problems.append("pyproject.toml must not add AIDE as a runtime dependency")
    for path in ROOT.joinpath("release", "packaging").glob("**/*.toml"):
        text = path.read_text(encoding="utf-8").lower()
        if ".aide" in text or "aide" in text:
            problems.append(f"production package manifest must not bundle AIDE: {path.relative_to(ROOT)}")
    return problems


def check_python_is_not_product_runtime() -> list[str]:
    problems: list[str] = []
    if (ROOT / "apps" / "python_cli").exists():
        problems.append("apps/python_cli is retired; Python may be used for tools/tests, not product runtime")
    if (ROOT / "pyproject.toml").exists():
        problems.append("pyproject.toml is retired; FacMan must not expose a Python product package")
    return problems


def check_facman_identity() -> list[str]:
    problems: list[str] = []
    required_docs = [
        ROOT / "docs" / "architecture" / "ecosystem_vision.md",
        ROOT / "docs" / "architecture" / "root_grammar.md",
        ROOT / "docs" / "product" / "product_vision.md",
        ROOT / "docs" / "roadmap.md",
    ]
    for path in required_docs:
        if not path.is_file():
            problems.append(f"missing FacMan vision document: {path.relative_to(ROOT)}")

    readme = ROOT / "README.md"
    if readme.is_file() and "FacMan" not in readme.read_text(encoding="utf-8"):
        problems.append("README.md must use the FacMan product identity")

    product_manifest = ROOT / "content" / "factorio" / "product" / "factorio.product.toml"
    if product_manifest.is_file():
        text = product_manifest.read_text(encoding="utf-8")
        if "FacMan" not in text:
            problems.append("Factorio product manifest must use the FacMan public name")

    bundle_schema = ROOT / "contracts" / "schema" / "release" / "packaging" / "bundle_manifest.v1.schema.json"
    if bundle_schema.is_file():
        text = bundle_schema.read_text(encoding="utf-8")
        if "facman.packaging." not in text:
            problems.append("packaging schema must use the facman.packaging namespace")
    return problems


if __name__ == "__main__":
    raise SystemExit(main())
