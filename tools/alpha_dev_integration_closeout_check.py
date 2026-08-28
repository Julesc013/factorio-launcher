# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Validate the exact protected-dev integration receipt for FacMan alpha.1."""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / "release/index/alpha1_dev_integration_closeout.v1.toml"
EXPECTED_RUNS = {
    "synthetic-product-tck": 33168126260,
    "ci": 33168126261,
    "code-security": 33168126270,
    "security-policy": 33168126284,
    "provider-sdk-consumption": 33168126285,
    "schema-check": 33168126308,
    "bounded-provider-input-conformance": 33168126322,
}
EXPECTED_PROVIDERS = {
    "universal_launcher": (
        "5479939ca5cbc9ee0f901608a92012778b4752ae",
        "7728e4d415539a0f24e6f17aa7d22be00cc99d80",
    ),
    "universal_setup": (
        "d2a2aae7e61c47035c92334b0522143b4fea3880",
        "291d63214cdd0cd3d15c809de5744ee3514fb2b2",
    ),
}


def load(path: Path = RECEIPT) -> dict[str, Any]:
    with path.open("rb") as stream:
        value = tomllib.load(stream)
    if not isinstance(value, dict):
        raise ValueError("integration receipt must contain a TOML table")
    return value


def validate(value: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    exact = {
        "schema": "facman.alpha1_dev_integration_closeout.v1",
        "status": "protected_dev_merge_verified",
        "work_unit": "FACMAN-0.1.0-ALPHA.1-DEV-INTEGRATION-CLOSEOUT-01",
        "integrated_work_unit": "FACMAN-0.1.0-ALPHA.1-FINAL-INTEGRATION-01",
        "pull_request": 191,
        "prior_dev": "e73d778173be283d47925fa055ba1aae7b82fb28",
        "pull_request_head": "e3c994770b0da07f0493e22c6c502aafd653680c",
        "pull_request_tree": "ffeb7b092f4c8f2a55f5418068593677d5426670",
        "dev_merge_commit": "06f0f7c9084ad90c59b09c5691847791ddc7dd85",
        "dev_merge_tree": "ffeb7b092f4c8f2a55f5418068593677d5426670",
        "merge_parents": [
            "e73d778173be283d47925fa055ba1aae7b82fb28",
            "e3c994770b0da07f0493e22c6c502aafd653680c",
        ],
        "merge_actor": "Julesc013",
        "merge_method": "merge_commit",
        "merged_at": "2026-08-28T11:41:44Z",
        "merge_head_check_count": 20,
        "merge_head_success_count": 20,
        "merge_head_failure_count": 0,
        "incorporated_pull_requests": [188, 189, 190],
        "incorporated_pull_request_state": "merged_by_ancestry_at_pr_191_merge",
    }
    for key, expected in exact.items():
        if value.get(key) != expected:
            problems.append(f"{key} must equal {expected!r}")
    runs = {
        item.get("name"): item
        for item in value.get("workflow", [])
        if isinstance(item, dict)
    }
    if set(runs) != set(EXPECTED_RUNS):
        problems.append("workflow receipt must contain the exact seven merge-head runs")
    for name, run_id in EXPECTED_RUNS.items():
        record = runs.get(name, {})
        if record.get("run_id") != run_id:
            problems.append(f"{name}: wrong run ID")
        if record.get("head_sha") != exact["dev_merge_commit"]:
            problems.append(f"{name}: wrong workflow head")
        if record.get("status") != "completed" or record.get("conclusion") != "success":
            problems.append(f"{name}: workflow is not completed successfully")
    providers = {
        item.get("id"): item
        for item in value.get("provider", [])
        if isinstance(item, dict)
    }
    if set(providers) != set(EXPECTED_PROVIDERS):
        problems.append("receipt must contain exactly Universal Launcher and Setup")
    for provider_id, (revision, tree) in EXPECTED_PROVIDERS.items():
        record = providers.get(provider_id, {})
        if record.get("revision") != revision or record.get("tree") != tree:
            problems.append(f"{provider_id}: exact provider source identity differs")
    authority = value.get("authority", {})
    expected_authority = {
        "tagging": False, "signing": False, "publication": False,
        "support": False, "main_promotion": False, "route_promotion": False,
        "factorio_execution": False, "human_verdict": False,
    }
    if authority != expected_authority:
        problems.append("integration receipt authority must remain exactly closed")
    return problems


def check(path: Path = RECEIPT) -> list[str]:
    if not path.is_file():
        return [f"missing integration receipt: {path.relative_to(ROOT)}"]
    try:
        return validate(load(path))
    except (OSError, ValueError, tomllib.TOMLDecodeError) as exc:
        return [f"integration receipt cannot be read: {exc}"]


def main() -> int:
    problems = check()
    if problems:
        for problem in problems:
            print(f"alpha-dev-integration-closeout-check: {problem}", file=sys.stderr)
        return 1
    print("alpha-dev-integration-closeout-check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
