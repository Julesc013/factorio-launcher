# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Enforce the integrated release-resolution custody and migration policy."""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "release" / "index"

HISTORICAL_EXCEPTIONS = {
    "451dc6376d52ac2ddaf82c07ee95e423deec0829": "land: task/c1-backend-identity-01 into dev",
    "6538e519af3be221614879cc7f3323b9835dfae6": "promote: dev into main",
    "0da078ff89e9d5e85bb8a98c1b7d4f546c4757bd": (
        "Promote dev after UNIVERSAL-BRANCH-MODEL-RATIFICATION-01"
    ),
    "9766c01afae3ef6b70a4e55b53ade1db479e254c": (
        "merge: reconcile provider contract wave"
    ),
    "e21b200ee7e6a8f1364399c592bbd3539d2b6291": (
        "promote: provider contract wave reconciliation"
    ),
    "9461c6ae7e733446ddaa719d89d89a39f9147e71": (
        "merge: workspace root authority and provider closeout"
    ),
    "5dfef289aa98a1a8df62b8e32b81e1743d2aeaad": (
        "promote: workspace root authority and provider closeout"
    ),
}

COMPLETED_WORKUNITS = {
    "FACMAN-RELEASE-MODEL-V2-NORMALIZATION-01",
    "FACMAN-RELEASE-RESOLUTION-V1-01",
    "FACMAN-RELEASE-IDENTITY-NORMALIZATION-01",
    "FACMAN-HISTORICAL-COMMIT-POLICY-CLOSEOUT-01",
    "FACMAN-RELEASE-RESOLUTION-INTEGRATION-01",
}

LATER_WORKUNITS = {
    "FACMAN-PACKAGE-PRODUCER-CONVERGENCE-01",
    "FACMAN-RELEASE-RESOLUTION-SECURITY-REVIEW-01",
}
POLICY_EFFECTIVE_REVISION = "5dfef289aa98a1a8df62b8e32b81e1743d2aeaad"


def _toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as source:
        return tomllib.load(source)


def _version_problems() -> list[str]:
    version = _toml(INDEX / "version.v2.toml")
    problems = []
    if "source_revision" in version or "source_tree_identity" in version:
        problems.append("tracked version policy must not claim observed build source identity")
    lineage = version.get("development_lineage", {})
    reviewed_base = str(lineage.get("reviewed_base_revision", ""))
    if len(reviewed_base) != 40 or any(char not in "0123456789abcdef" for char in reviewed_base):
        problems.append("reviewed development lineage must bind one exact base revision")
    return problems


def _artifact_problems() -> list[str]:
    artifacts = _toml(INDEX / "artifacts.v2.toml").get("artifact", [])
    problems = []
    for artifact in artifacts:
        sources = {
            str(item.get("source", ""))
            for item in artifact.get("integration", [])
            if item.get("path") == "manifest/resolution"
        }
        if sources != {"resolution://runtime-metadata"}:
            problems.append(
                f"{artifact.get('id')}: packages must embed only bounded runtime metadata"
            )
    return problems


def _producer_problems() -> list[str]:
    policy = _toml(INDEX / "package_producers.v1.toml")
    problems = []
    if policy.get("release_authority") is not False:
        problems.append("package-producer census cannot grant release authority")
    if policy.get("policy") != "one_verified_canonical_stage_or_bounded_exception":
        problems.append("package-producer policy must require canonical stage or bounded exception")
    actual_profiles = {
        path.parent.name
        for path in (ROOT / "release" / "profiles").glob("*/profile.toml")
    }
    assigned: list[str] = []
    canonical: set[str] = set()
    for producer in policy.get("producer", []):
        state = producer.get("state")
        profiles = [str(item) for item in producer.get("profiles", [])]
        assigned.extend(profiles)
        if state == "canonical_stage":
            canonical.update(profiles)
        elif state == "temporary_exception":
            for field in (
                "owner",
                "reason",
                "unsupported_invariant",
                "expiry_workunit",
                "qualification_effect",
                "authority_ceiling",
            ):
                if not str(producer.get(field, "")):
                    problems.append(f"{producer.get('id')}: exception is missing {field}")
        elif state == "not_yet_admitted":
            if profiles:
                problems.append(f"{producer.get('id')}: unadmitted producer has profiles")
            if not str(producer.get("admission_workunit", "")):
                problems.append(f"{producer.get('id')}: unadmitted producer lacks an admission WorkUnit")
        else:
            problems.append(f"{producer.get('id')}: unknown producer state {state!r}")
    duplicates = sorted({profile for profile in assigned if assigned.count(profile) > 1})
    if duplicates:
        problems.append(f"package profiles have multiple producer assignments: {duplicates}")
    if set(assigned) != actual_profiles:
        problems.append("package-producer census does not cover exactly every tracked profile")
    if canonical:
        problems.append(
            "no current package producer has yet proven consumption of the canonical stage"
        )
    portable_profiles = {
        "linux_portable_cli_x64",
        "macos_portable_cli_x64",
        "windows_portable_cli_x64",
    }
    portable_rows = [
        producer
        for producer in policy.get("producer", [])
        if set(producer.get("profiles", [])) == portable_profiles
    ]
    if len(portable_rows) != 1 or portable_rows[0].get("unsupported_invariant") != (
        "does_not_consume_the_verified_canonical_release_stage"
    ):
        problems.append("portable CLI stage gap is not represented by one bounded exception")
    return problems


def _history_problems() -> list[str]:
    baseline = _toml(ROOT / ".aide" / "commit_policy_baseline.toml")
    problems = []
    if baseline.get("history_rewrite_allowed") is not False:
        problems.append("historical commit-policy closeout must forbid history rewriting")
    if baseline.get("future_commits_must_conform") is not True:
        problems.append("historical commit-policy closeout must require future conformance")
    if baseline.get("policy_effective_revision") != POLICY_EFFECTIVE_REVISION:
        problems.append("commit-policy effective revision is not the sealed boundary")
    commits = baseline.get("commit", [])
    for sha, subject in HISTORICAL_EXCEPTIONS.items():
        matches = [item for item in commits if item.get("sha") == sha]
        if len(matches) != 1:
            problems.append(f"historical exception {sha} must appear exactly once")
            continue
        if matches[0].get("subject") != subject:
            problems.append(f"historical exception {sha} subject differs from immutable history")
        if not str(matches[0].get("reason", "")):
            problems.append(f"historical exception {sha} lacks a reason")
    return problems


def _plan_problems() -> list[str]:
    plan = _toml(INDEX / "plan.v1.toml")
    workunits = {str(item.get("id")): item for item in plan.get("workunit", [])}
    later = {str(item.get("id")) for item in plan.get("later", [])}
    problems = []
    for workunit_id in sorted(COMPLETED_WORKUNITS):
        if workunits.get(workunit_id, {}).get("status") != "complete":
            problems.append(f"{workunit_id}: completed integration WorkUnit is missing")
    for workunit_id in sorted(LATER_WORKUNITS):
        if workunit_id not in later:
            problems.append(f"{workunit_id}: required later WorkUnit is missing")
    return problems


def detect() -> list[str]:
    release_index = _toml(INDEX / "release_index.v1.toml")
    problems = []
    if release_index.get("release_model_package_producers") != (
        "release/index/package_producers.v1.toml"
    ):
        problems.append("release index does not bind the package-producer census")
    for check in (
        _version_problems,
        _artifact_problems,
        _producer_problems,
        _history_problems,
        _plan_problems,
    ):
        problems.extend(check())
    return problems


def main() -> int:
    problems = detect()
    if problems:
        for problem in problems:
            print(f"release-resolution-integration-check: {problem}", file=sys.stderr)
        return 1
    print(
        "release-resolution-integration-check: ok "
        "(source custody, runtime boundary, producer census, history, and plan)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
