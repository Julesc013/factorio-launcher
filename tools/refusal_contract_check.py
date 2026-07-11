# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "contracts" / "refusal" / "refusal_codes.v1.toml"
EFFECTS_POLICY = ROOT / "contracts" / "policy" / "effects.v1.toml"
GOLDEN_ROOT = ROOT / "tests" / "golden" / "commands"

SEVERITIES = {"info", "warning", "error", "blocked"}


def main() -> int:
    problems: list[str] = []
    registry, registry_problems = load_toml(REGISTRY)
    effects, effects_problems = load_effects()
    problems.extend(registry_problems)
    problems.extend(effects_problems)
    if registry_problems or effects_problems:
        return report(problems)

    if registry.get("schema") != "facman.refusal_codes.v1":
        problems.append(f"{REGISTRY.relative_to(ROOT)}: schema must be facman.refusal_codes.v1")

    required_codes = registry.get("required_codes", [])
    if not isinstance(required_codes, list) or not required_codes:
        problems.append(f"{REGISTRY.relative_to(ROOT)}: required_codes must be a non-empty array")

    entries = registry.get("code", [])
    if not isinstance(entries, list) or not entries:
        problems.append(f"{REGISTRY.relative_to(ROOT)}: code registry must be non-empty")
        return report(problems)

    registered: dict[str, dict[str, Any]] = {}
    for entry in entries:
        problems.extend(validate_entry(entry, effects, registered))

    registered_codes = set(registered)
    for code in sorted(str(code) for code in required_codes):
        if code not in registered_codes:
            problems.append(f"{REGISTRY.relative_to(ROOT)}: missing required refusal code {code}")

    for code, path in golden_refusal_codes().items():
        if code not in registered_codes:
            problems.append(f"{path.relative_to(ROOT)}: refusal code {code} is not registered")

    return report(problems, registered_codes)


def load_toml(path: Path) -> tuple[dict[str, Any], list[str]]:
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return {}, [f"{path.relative_to(ROOT)}: {exc}"]
    return data, []


def load_effects() -> tuple[set[str], list[str]]:
    data, problems = load_toml(EFFECTS_POLICY)
    if problems:
        return set(), problems
    effects = data.get("effects", {})
    if not isinstance(effects, dict) or not effects:
        return set(), [f"{EFFECTS_POLICY.relative_to(ROOT)}: effects table must be non-empty"]
    return set(effects), []


def validate_entry(entry: Any, effects: set[str], registered: dict[str, dict[str, Any]]) -> list[str]:
    problems: list[str] = []
    if not isinstance(entry, dict):
        return [f"{REGISTRY.relative_to(ROOT)}: refusal code entries must be tables"]

    required = ["id", "severity", "effect", "retryable", "message"]
    for key in required:
        if key not in entry:
            problems.append(f"{REGISTRY.relative_to(ROOT)}: code entry missing {key}")
    if problems:
        return problems

    code = entry["id"]
    if not isinstance(code, str) or not code:
        problems.append(f"{REGISTRY.relative_to(ROOT)}: code id must be a non-empty string")
        return problems
    if code in registered:
        problems.append(f"{REGISTRY.relative_to(ROOT)}: duplicate refusal code {code}")
    registered[code] = entry

    severity = entry["severity"]
    if severity not in SEVERITIES:
        problems.append(f"{REGISTRY.relative_to(ROOT)}: {code} has invalid severity {severity!r}")
    effect = entry["effect"]
    if effect not in effects:
        problems.append(f"{REGISTRY.relative_to(ROOT)}: {code} has unknown effect {effect!r}")
    if not isinstance(entry["retryable"], bool):
        problems.append(f"{REGISTRY.relative_to(ROOT)}: {code} retryable must be boolean")
    if not isinstance(entry["message"], str) or not entry["message"].strip():
        problems.append(f"{REGISTRY.relative_to(ROOT)}: {code} message must be non-empty")
    return problems


def golden_refusal_codes() -> dict[str, Path]:
    codes: dict[str, Path] = {}
    for path in sorted(GOLDEN_ROOT.glob("*.refusal.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        refusal = data.get("refusal", {})
        if isinstance(refusal, dict) and isinstance(refusal.get("code"), str):
            codes[refusal["code"]] = path
    return codes


def report(problems: list[str], registered_codes: set[str] | None = None) -> int:
    if problems:
        for problem in problems:
            print(f"refusal-contract-check: {problem}", file=sys.stderr)
        return 1
    count = len(registered_codes or set())
    print(f"refusal-contract-check: ok ({count} codes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
