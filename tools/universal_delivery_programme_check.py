# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Validate the non-authorizing Universal delivery programme preparation."""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

PLAN = ROOT / "release" / "index" / "plan.v1.toml"
TRUST = ROOT / "release" / "index" / "trust.v1.toml"
SUPPORT = ROOT / "release" / "index" / "support.v2.toml"
PROVIDERS = ROOT / "release" / "index" / "providers.lock.v2.toml"
DOCTRINE = ROOT / "docs" / "architecture" / "universal_multi_consumer_productization.md"

NEAR_TERM = {
    "THREE-REPO-SOURCE-VS-SDK-CONFORMANCE-01": {
        "status": "active",
        "depends_on": ["SYNTHETIC-PRODUCT-TCK-01"],
        "decision_blockers": [],
        "repos": [
            "factorio-launcher",
            "universal-launcher",
            "universal-setup",
        ],
    },
    "FACMAN-PROVIDER-SDK-CONSUMPTION-01": {
        "status": "planned",
        "depends_on": ["THREE-REPO-SOURCE-VS-SDK-CONFORMANCE-01"],
        "decision_blockers": [],
        "repos": [
            "factorio-launcher",
            "universal-launcher",
            "universal-setup",
        ],
    },
    "FACMAN-PROVIDER-PIN-RECONCILIATION-01": {
        "status": "planned",
        "depends_on": ["FACMAN-PROVIDER-SDK-CONSUMPTION-01"],
        "decision_blockers": [],
        "repos": ["factorio-launcher"],
    },
    "FACMAN-SUCCESSOR-PLAY-ROUTE-DEFINITION-02": {
        "status": "planned",
        "depends_on": [
            "FACMAN-SUCCESSOR-PLAY-ROUTE-DEFINITION-01",
            "FACMAN-PROVIDER-PIN-RECONCILIATION-01",
        ],
        "decision_blockers": [],
        "repos": ["factorio-launcher"],
        "immutable_predecessor_contract": "release/index/successor_play_route.v1.toml",
        "pending_active_contract": "release/index/successor_play_route.v2.toml",
    },
    "FACMAN-SUCCESSOR-PLAY-SOURCE-CLOSURE-01": {
        "status": "blocked",
        "depends_on": ["FACMAN-SUCCESSOR-PLAY-ROUTE-DEFINITION-02"],
        "decision_blockers": [],
        "repos": [
            "factorio-launcher",
            "universal-launcher",
            "universal-setup",
        ],
        "immutable_predecessor_contract": "release/index/successor_play_route.v1.toml",
        "pending_active_contract": "release/index/successor_play_route.v2.toml",
    },
}

EVOLUTION_GATES = {
    "UNIVERSAL-COMPATIBILITY-EVOLUTION-CONSTITUTION-01",
    "UNIVERSAL-CAPABILITY-GUARANTEE-MODEL-01",
    "UNIVERSAL-DURABLE-STATE-MIGRATION-LAW-01",
    "FACMAN-PRESENTATION-EXPLANATION-GRAPH-01",
    "FACMAN-DOCTOR-AND-SAFE-MODE-01",
}

LATER_GATES = {
    "FACMAN-PACKAGE-COMPONENT-SPLIT-01",
    "FACMAN-PACKAGE-ADAPTER-CONFORMANCE-01",
    "FACMAN-RELEASE-LOCK-AND-SOURCE-CLOSURE-01",
    "FACMAN-PRESENTATION-V1-01",
    "FACMAN-NATIVE-SHELL-CONFORMANCE-01",
    "DOMINIUM-UNIVERSAL-CONSUMER-01",
    "C3-USK-PACKAGE-AUTHORING-01",
    "FACMAN-ULK-PHYSICAL-CONVERGENCE-01",
    "USK-PRODUCTION-LIFECYCLE-01",
    "FACMAN-TRUSTED-PREVIEW-01",
    "UNIVERSAL-PROVIDER-HEALTH-AND-ADOPTION-AUTOMATION-01",
    "FACMAN-PERFORMANCE-AND-FAULT-INJECTION-01",
    "FACMAN-PACKAGE-PRODUCER-CONVERGENCE-01",
    "FACMAN-RELEASE-RESOLUTION-SECURITY-REVIEW-01",
} | EVOLUTION_GATES

COMPLETED_GATES = {
    "FACMAN-RELEASE-IDENTITY-NORMALIZATION-01",
    "FACMAN-RELEASE-RESOLUTION-INTEGRATION-01",
}

DOCTRINE_ANCHORS = (
    "Universal product runtime and delivery programme",
    "Providers define reusable capability. Products define meaning.",
    "Permanent six-plane constitution",
    "Three authoritative graphs",
    "Identity and compatibility law",
    "Provider productization contract",
    "FacMan product and presentation direction",
    "Physical convergence and migration law",
    "Security and operational trust",
    "Reliability and performance preparation",
    "Repository and CI governance",
    "Dependency-ordered preparation register",
    "Deferred and rejected directions",
    "Programme success measures",
    "Evolution-proof architecture",
    "Compatibility vector",
    "Capability-guarantee model",
    "Durable state and migration law",
    "Extension trust ladder",
    "not a fourth repository",
    "Only the canonical plan may move a prepared item to ready or active.",
)


def _toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def load_inputs() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], str]:
    return (
        _toml(PLAN),
        _toml(TRUST),
        _toml(SUPPORT),
        _toml(PROVIDERS),
        DOCTRINE.read_text(encoding="utf-8"),
    )


def validate(
    plan: dict[str, Any],
    trust: dict[str, Any],
    support: dict[str, Any],
    providers: dict[str, Any],
    doctrine: str,
) -> list[str]:
    problems: list[str] = []

    workunits = {item.get("id"): item for item in plan.get("workunit", [])}
    for workunit_id, expected in NEAR_TERM.items():
        actual = workunits.get(workunit_id)
        if actual is None:
            problems.append(f"canonical plan omits prepared WorkUnit {workunit_id}")
            continue
        for field, value in expected.items():
            if actual.get(field) != value:
                problems.append(
                    f"{workunit_id} {field} must remain {value!r}, got {actual.get(field)!r}"
                )
    for workunit_id in sorted(COMPLETED_GATES):
        if workunits.get(workunit_id, {}).get("status") != "complete":
            problems.append(f"canonical plan omits completed programme gate {workunit_id}")

    later_records = {item.get("id"): item for item in plan.get("later", [])}
    later = set(later_records)
    missing_later = sorted(LATER_GATES - later)
    if missing_later:
        problems.append("canonical plan omits later programme gates: " + ", ".join(missing_later))
    misplaced_evolution = sorted(EVOLUTION_GATES & set(workunits))
    if misplaced_evolution:
        problems.append(
            "post-C1 evolution gates cannot enter the active WorkUnit graph: "
            + ", ".join(misplaced_evolution)
        )
    for workunit_id in sorted(EVOLUTION_GATES & later):
        trigger = str(later_records[workunit_id].get("trigger", ""))
        if "C1 is release-proven" not in trigger:
            problems.append(
                f"{workunit_id} trigger must require C1 to be release-proven"
            )

    pending = [
        item
        for item in plan.get("workunit", [])
        if item.get("status") not in {"complete", "cancelled"}
    ]
    active = [
        item
        for item in pending
        if item.get("status") in {"active", "in_progress", "review", "verified_pending_closeout"}
    ]
    if len(pending) > int(plan.get("next_workunit_limit", 0)) + len(active):
        problems.append("programme preparation exceeds the canonical near-term WorkUnit limit")

    roles = {item.get("id"): item.get("authorized") for item in trust.get("role", [])}
    if roles.get("source_reviewer") is not True:
        problems.append("source review must remain the only currently authorized trust role")
    for role_id in ("build_operator", "release_signer", "release_publisher"):
        if roles.get(role_id) is not False:
            problems.append(f"programme preparation cannot authorize {role_id}")

    for item in support.get("support", []):
        if item.get("release_authorized") is not False:
            problems.append(f"programme preparation cannot authorize support {item.get('id')}")
        if item.get("qualification_evidence"):
            problems.append(f"support {item.get('id')} cannot acquire evidence from planning")

    for provider in providers.get("provider", []):
        provider_id = provider.get("id", "<provider>")
        if provider.get("consumption_mode") != "source":
            problems.append(f"{provider_id} SDK consumption has not been accepted")
        if provider.get("maturity") != "fixture_qualified":
            problems.append(f"{provider_id} maturity exceeds prepared evidence")

    for anchor in DOCTRINE_ANCHORS:
        if anchor not in doctrine:
            problems.append(f"programme doctrine is missing anchor: {anchor}")

    return problems


def detect() -> list[str]:
    try:
        return validate(*load_inputs())
    except (OSError, tomllib.TOMLDecodeError, ValueError) as error:
        return [str(error)]


def main() -> int:
    problems = detect()
    if problems:
        for problem in problems:
            print(f"universal-delivery-programme-check: {problem}", file=sys.stderr)
        return 1
    print(
        "universal-delivery-programme-check: ok "
        f"({len(NEAR_TERM)} near-term, {len(LATER_GATES)} later gates)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
