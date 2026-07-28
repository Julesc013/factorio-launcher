# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import argparse
import json
import sys
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "contracts" / "policy" / "test_obligations.v1.json"


def load_policy() -> dict[str, Any]:
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def classify(reason: str, policy: dict[str, Any]) -> str:
    prefix, separator, _ = reason.partition(":")
    if separator and prefix in policy["classes"]:
        return prefix
    return "unknown"


class ObligationResult(unittest.TextTestResult):
    policy: dict[str, Any]

    def __init__(self, *args: Any, policy: dict[str, Any], **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.policy = policy
        self.classified_skips: list[dict[str, str]] = []

    def addSkip(self, test: unittest.case.TestCase, reason: str) -> None:
        super().addSkip(test, reason)
        self.classified_skips.append(
            {
                "test": test.id(),
                "reason": reason,
                "classification": classify(reason, self.policy),
            }
        )


def run_suite(
    *,
    start_directory: str,
    pattern: str,
    profile: str,
    verbosity: int,
) -> tuple[ObligationResult, dict[str, Any]]:
    policy = load_policy()
    if profile not in policy["profiles"]:
        raise ValueError(f"unknown test-obligation profile: {profile}")
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    tests_path = str(ROOT / "tests")
    if tests_path not in sys.path:
        sys.path.insert(0, tests_path)
    suite = unittest.defaultTestLoader.discover(
        start_dir=str(ROOT / start_directory),
        pattern=pattern,
        top_level_dir=str(ROOT),
    )

    def result_factory(*args: Any, **kwargs: Any) -> ObligationResult:
        return ObligationResult(*args, policy=policy, **kwargs)

    runner = unittest.TextTestRunner(verbosity=verbosity, resultclass=result_factory)
    result = runner.run(suite)
    counts = {classification: 0 for classification in [*policy["classes"], "unknown"]}
    for skip in result.classified_skips:
        counts[skip["classification"]] += 1
    required_class = str(policy["required_class"])
    required_limit = int(policy["profiles"][profile]["required_skip_limit"])
    unknown_limit = int(policy["unknown_skip_limit"])
    gate_passed = (
        result.wasSuccessful()
        and counts["unknown"] <= unknown_limit
        and (required_limit < 0 or counts[required_class] <= required_limit)
    )
    summary = {
        "schema": "facman.test_obligation_result.v1",
        "profile": profile,
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "expected_failures": len(result.expectedFailures),
        "unexpected_successes": len(result.unexpectedSuccesses),
        "skip_counts": counts,
        "required_skip_limit": required_limit,
        "unknown_skip_limit": unknown_limit,
        "gate_passed": gate_passed,
        "skips": result.classified_skips,
    }
    return result, summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Python tests and classify every skipped obligation."
    )
    parser.add_argument("--profile", choices=sorted(load_policy()["profiles"]), default="local")
    parser.add_argument("--start-directory", default="tests")
    parser.add_argument("--pattern", default="test_*.py")
    parser.add_argument("--verbosity", type=int, choices=(1, 2), default=2)
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    _, summary = run_suite(
        start_directory=args.start_directory,
        pattern=args.pattern,
        profile=args.profile,
        verbosity=args.verbosity,
    )
    rendered = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    if args.evidence:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if summary["gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
