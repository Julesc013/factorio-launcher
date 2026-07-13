# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import generate_factorio_setup_recipe

RECIPE = ROOT / "content" / "factorio" / "product" / "factorio.portable-windows-zip.recipe.v1.json"

FORBIDDEN_KEYS = {
    "arbitrary_executable",
    "batch",
    "command",
    "credential_reference",
    "network_url",
    "post_install_command",
    "powershell",
    "registry_script",
    "shell",
}


def walk(value: object, path: str = "$") -> list[str]:
    problems: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in FORBIDDEN_KEYS:
                problems.append(f"{path}.{key}: executable recipe key is forbidden")
            problems.extend(walk(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            problems.extend(walk(child, f"{path}[{index}]"))
    return problems


def main() -> int:
    problems: list[str] = []
    try:
        recipe = json.loads(RECIPE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"factorio-setup-recipe: {error}", file=sys.stderr)
        return 1
    problems.extend(walk(recipe))
    expected_authority = {
        "network",
        "credentials",
        "registry",
        "elevation",
        "package_manager",
        "installer_execution",
        "shell_commands",
        "post_install_hooks",
        "steam_mutation",
        "factorio_execution",
    }
    authority = recipe.get("authority")
    if not isinstance(authority, dict) or set(authority) != expected_authority:
        problems.append("$.authority: exact M1 authority boundary is required")
    elif any(value is not False for value in authority.values()):
        problems.append("$.authority: every forbidden M1 authority must be false")
    if recipe.get("required_paths") != ["bin/x64/factorio.exe", "data/base/info.json"]:
        problems.append("$.required_paths: Windows portable closure markers changed")
    if recipe.get("source", {}).get("archive_digest_binding") != "exact_sha256_at_plan":
        problems.append("$.source.archive_digest_binding: exact plan-time digest is required")
    if generate_factorio_setup_recipe.main(["--check"]) != 0:
        problems.append("generated setup recipe projection is stale")
    if problems:
        for problem in problems:
            print(f"factorio-setup-recipe: {problem}", file=sys.stderr)
        return 1
    print("factorio-setup-recipe: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
