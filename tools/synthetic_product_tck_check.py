# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Validate the tracked, authority-free synthetic TCK definition."""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import synthetic_product_tck


WORKFLOW = ROOT / ".github" / "workflows" / "synthetic-product-tck.yml"
LOCK = ROOT / "release" / "index" / "workspace_lock.v1.toml"
EXPECTED_PINS = {
    "universal_launcher": "09f0639ab6529fba2f2aa22e9bf68e5eebed0553",
    "universal_setup": "32488fc13bd2439f9f6e52e83a97f6da345a7650",
}


def check() -> list[str]:
    problems: list[str] = []
    orchestration = synthetic_product_tck.load_json(synthetic_product_tck.ORCHESTRATION)
    journal = synthetic_product_tck.load_json(synthetic_product_tck.JOURNAL)
    if orchestration.get("development_only") is not True:
        problems.append("synthetic orchestration must remain development-only")
    if journal.get("development_only") is not True:
        problems.append("interrupted journal must remain development-only")
    if any(orchestration.get("authority", {}).values()):
        problems.append("synthetic orchestration must grant no authority")
    if orchestration.get("structured_refusal", {}).get("process_started") is not False:
        problems.append("synthetic orchestration must not start a process")
    if journal.get("mutation_executed") is not False:
        problems.append("synthetic journal must not execute mutation")

    with LOCK.open("rb") as handle:
        lock = tomllib.load(handle)
    pins = {
        component["id"]: component["pin"]
        for component in lock.get("component", [])
        if component.get("id") in EXPECTED_PINS
    }
    if pins != EXPECTED_PINS:
        problems.append("reconciled FacMan provider pins differ from the synthetic TCK")

    if not WORKFLOW.is_file():
        problems.append("synthetic product TCK workflow is missing")
        return problems
    workflow = WORKFLOW.read_text(encoding="utf-8")
    anchors = (
        "name: synthetic-product-tck",
        "repository: Julesc013/universal-launcher",
        f"ref: {synthetic_product_tck.EXPECTED_ULK_SHA}",
        "repository: Julesc013/universal-setup",
        f"ref: {synthetic_product_tck.EXPECTED_USK_SHA}",
        "tools/synthetic_product_tck.py",
        "${{ runner.temp }}/synthetic-product-tck",
        "synthetic-product-tck-observation.v1.json",
        "if-no-files-found: error",
    )
    for anchor in anchors:
        if anchor not in workflow:
            problems.append(f"synthetic TCK workflow is missing anchor: {anchor}")
    return problems


def main() -> int:
    try:
        problems = check()
    except (OSError, ValueError) as error:
        problems = [str(error)]
    if problems:
        for problem in problems:
            print(f"synthetic-product-tck-check: {problem}", file=sys.stderr)
        return 1
    print("synthetic-product-tck-check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
