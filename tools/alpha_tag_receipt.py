# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Create a closed, non-publication receipt for one immutable alpha tag."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import json_contract

SCHEMA_PATH = ROOT / "contracts/schema/release/alpha_tag_receipt.v1.schema.json"
SHA1 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
TAG = re.compile(r"^v0\.1\.0-alpha\.([1-9][0-9]*)$")


def load_plan(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("alpha tag plan must be a JSON object")
    return value


def make_receipt(
    plan: dict[str, Any],
    *,
    tag_object_sha: str,
    eligibility_sha256: str,
    github_run_id: str,
    created_at: str,
) -> dict[str, Any]:
    expected_plan = {
        "schema": "facman.alpha_tag_plan.v1",
        "eligible": True,
        "publication": False,
        "signing": False,
    }
    for field, expected in expected_plan.items():
        if plan.get(field) != expected:
            raise ValueError(f"alpha tag plan {field} must be {expected!r}")
    tag_match = TAG.fullmatch(str(plan.get("tag", "")))
    if tag_match is None:
        raise ValueError("alpha tag plan tag is invalid")
    if plan.get("version") != str(plan["tag"])[1:]:
        raise ValueError("alpha tag plan version does not match its tag")
    tag_ruleset_ids = plan.get("tag_ruleset_ids")
    if (
        not isinstance(tag_ruleset_ids, list)
        or not tag_ruleset_ids
        or any(type(value) is not int or value < 1 for value in tag_ruleset_ids)
        or len(tag_ruleset_ids) != len(set(tag_ruleset_ids))
    ):
        raise ValueError("alpha tag plan does not bind immutable tag rulesets")
    for field in ("source_revision", "source_tree"):
        if not SHA1.fullmatch(str(plan.get(field, ""))):
            raise ValueError(f"alpha tag plan {field} is invalid")
    if not SHA256.fullmatch(str(plan.get("candidate_sha256", ""))):
        raise ValueError("alpha tag plan candidate digest is invalid")
    if not SHA1.fullmatch(tag_object_sha):
        raise ValueError("tag object SHA is invalid")
    if not SHA256.fullmatch(eligibility_sha256):
        raise ValueError("eligibility digest is invalid")
    if not re.fullmatch(r"[1-9][0-9]*", github_run_id):
        raise ValueError("GitHub run ID is invalid")
    try:
        timestamp = dt.datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("created_at is not an ISO timestamp") from exc
    if timestamp.tzinfo is None:
        raise ValueError("created_at must include a timezone")

    receipt = {
        "schema": "facman.alpha_tag_receipt.v1",
        "tag": plan["tag"],
        "tag_object_sha": tag_object_sha,
        "tag_ruleset_ids": tag_ruleset_ids,
        "source_revision": plan["source_revision"],
        "source_tree": plan["source_tree"],
        "candidate_sha256": plan["candidate_sha256"],
        "eligibility_sha256": eligibility_sha256,
        "github_run_id": github_run_id,
        "created_at": created_at,
        "publication": False,
        "signing": False,
    }
    problems = json_contract.validate(receipt, json_contract.load_schema(SCHEMA_PATH))
    if problems:
        raise ValueError("alpha tag receipt schema rejection: " + "; ".join(problems))
    return receipt


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--plan", required=True)
    result.add_argument("--tag-object-sha", required=True)
    result.add_argument("--eligibility-sha256", required=True)
    result.add_argument("--github-run-id", required=True)
    result.add_argument("--created-at")
    result.add_argument("--output", required=True)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    output = Path(args.output)
    if output.exists():
        print(f"alpha-tag-receipt: output already exists: {output}", file=sys.stderr)
        return 1
    created_at = args.created_at or dt.datetime.now(dt.timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )
    try:
        receipt = make_receipt(
            load_plan(Path(args.plan)),
            tag_object_sha=args.tag_object_sha,
            eligibility_sha256=args.eligibility_sha256,
            github_run_id=args.github_run_id,
            created_at=created_at,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"alpha-tag-receipt: {exc}", file=sys.stderr)
        return 1
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"alpha-tag-receipt: wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
