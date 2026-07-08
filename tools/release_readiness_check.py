from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_LAYOUT_ROOTS = (
    "include/",
    "runtime/",
    "apps/",
    "content/",
    "contracts/",
    "release/",
    "docs/",
    "tests/",
    "tools/",
)

RETIRED_ROOTS = ("source/", "src/", "data/", "schemas/", "packaging/")

REQUIRED_RELEASE_PROFILES = (
    "dev",
    "portable",
    "windows7",
    "windows10",
    "macos_10_13",
    "linux_appimage",
    "linux_legacy_cli",
)

REQUIRED_PACKAGING_PATHS = (
    "release/packaging/windows/facman_portable.v1.toml",
    "release/packaging/windows/facman_single_exe.v1.toml",
    "release/packaging/macos/facman_app.v1.toml",
    "release/packaging/linux/appimage.v1.toml",
    "release/packaging/linux/legacy_cli_tarball.v1.toml",
)


def main() -> int:
    problems: list[str] = []
    problems.extend(check_readme_layout())
    problems.extend(check_release_ladder())
    problems.extend(check_release_profiles())
    problems.extend(check_packaging_smoke())
    if problems:
        for problem in problems:
            print(f"release-readiness-check: {problem}", file=sys.stderr)
        return 1
    print("release-readiness-check: ok")
    return 0


def check_readme_layout() -> list[str]:
    readme = ROOT / "README.md"
    text = readme.read_text(encoding="utf-8")
    problems: list[str] = []
    block = extract_durable_layout_block(text)
    if not block:
        return ["README.md: Durable Layout block missing"]
    for root in REQUIRED_LAYOUT_ROOTS:
        if root not in block:
            problems.append(f"README.md: Durable Layout missing {root}")
    for root in RETIRED_ROOTS:
        if re.search(rf"(?m)^{re.escape(root)}\s", block):
            problems.append(f"README.md: Durable Layout still lists retired root {root}")
    if "must not return" not in text:
        problems.append("README.md: retired-root warning must say old roots must not return")
    return problems


def extract_durable_layout_block(text: str) -> str:
    marker = "## Durable Layout"
    start = text.find(marker)
    if start < 0:
        return ""
    first_fence = text.find("```text", start)
    if first_fence < 0:
        return ""
    block_start = text.find("\n", first_fence)
    block_end = text.find("```", block_start + 1)
    if block_start < 0 or block_end < 0:
        return ""
    return text[block_start:block_end]


def check_release_ladder() -> list[str]:
    roadmap = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")
    problems: list[str] = []
    for tier in ["R0", "R1", "R2", "R3", "R4", "R5", "R6"]:
        if f"{tier} " not in roadmap:
            problems.append(f"docs/roadmap.md: missing release readiness tier {tier}")
    if "FACMAN-INTEGRATION-HARDEN-01" not in roadmap:
        problems.append("docs/roadmap.md: missing FACMAN-INTEGRATION-HARDEN-01")
    return problems


def check_release_profiles() -> list[str]:
    problems: list[str] = []
    for profile in REQUIRED_RELEASE_PROFILES:
        path = ROOT / "release" / "profiles" / profile / "README.md"
        if not path.is_file():
            problems.append(f"missing release profile {path.relative_to(ROOT)}")
    profiles_readme = (ROOT / "release" / "profiles" / "README.md").read_text(encoding="utf-8")
    if "R0" not in profiles_readme or "R6" not in profiles_readme:
        problems.append("release/profiles/README.md: missing release readiness ladder")
    return problems


def check_packaging_smoke() -> list[str]:
    problems: list[str] = []
    for relative in REQUIRED_PACKAGING_PATHS:
        if not (ROOT / relative).is_file():
            problems.append(f"missing packaging smoke path {relative}")
    return problems


if __name__ == "__main__":
    raise SystemExit(main())
