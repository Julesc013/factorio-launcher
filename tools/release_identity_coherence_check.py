# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import architecture_fitness


VERSION = "0.1.0-alpha.5"
CANONICAL_VERSION = f"facman-{VERSION}"
TAG = f"v{VERSION}"
CHANNEL = "alpha"
ALPHA3_VERSION = "0.1.0-alpha.3"
ALPHA3_CANONICAL_VERSION = f"facman-{ALPHA3_VERSION}"
SOURCE_WORK_UNIT = "FACMAN-ALPHA3-DISTRIBUTION-CONVERGENCE-01"
RECOVERY_WORK_UNIT = "FACMAN-ALPHA3-RELEASE-RECOVERY-01"
CURRENT_SOURCE_WORK_UNIT = "FACMAN-0.1-ALPHA5-FINAL-CANDIDATE-CLOSEOUT-01"
CLOSEOUT_WORK_UNIT = CURRENT_SOURCE_WORK_UNIT
ACTIVE_WORK_UNIT = "FACMAN-0.1-ALPHA6-WORKSPACE-MIGRATION-RECOVERY-01"
LAST_CLOSED_WORK_UNIT = "FACMAN-BETA-RULESET-AND-TAG-PROTECTION-01"
BETA_READINESS_WORK_UNIT = "FACMAN-0.1-BETA-READINESS-01"
HISTORICAL_CLOSEOUT_WORK_UNIT = "FACMAN-0.1-ALPHA5-PROMOTION-CANDIDATE-CLOSEOUT-01"
TRUTH_REMEDIATION_WORK_UNIT = "FACMAN-0.1-ALPHA5-TRUTH-REMEDIATION-01"
HUMAN_WORK_UNIT = "FACMAN-0.1.0-ALPHA.3-HUMAN-ACCEPTANCE-01"
PHASE = "facman_0_1_alpha6_workspace_migration_recovery"
CHECKPOINT = "facman-0-1-alpha6-workspace-migration-recovery"
NEXT_WORK_UNIT = "FACMAN-0.1-ALPHA6-WORKSPACE-MIGRATION-RECOVERY-01"
IMPLEMENTATION_REVISION = "4683ecd9a1b9ead5eb84be152760d12583da0f0e"
MAIN_REVISION = IMPLEMENTATION_REVISION
DEV_REVISION = "488994a81ddb5eb54d541ef3a48b64ca83f67d4a"
SOURCE_TREE = "c07938618bc0f533fd12756cba123f54b8592048"
PHASE0_DEV_REVISION = "0d61feede2acd49bf54a4a7a1cd00bba3c867fb2"
PHASE0_DEV_TREE = "5ff92f7ee668a900dfe26bbdcba2c061492358de"
CURRENT_DEV_REVISION = "c5262596483a5a9767b4c66d4d5ef51b8086cfdc"
CURRENT_DEV_TREE = "06a55dede6c343d823b5a3c13d3db66efba21f0d"
CANDIDATE_RUN = 33603385303
CANDIDATE_ATTEMPT = 1
CANDIDATE_RECEIPT = "release/index/alpha5_final_candidate_closeout.v1.toml"
CANDIDATE_ARTIFACT = (
    "FacMan-0.1.0-alpha.5-unsigned-unpublished-candidate-33603385303-1-"
    + MAIN_REVISION
)
CANDIDATE_ARTIFACT_DIGEST = (
    "sha256:1c53c1e1337dced910f8aa88c9d32c9a36a68d5b87dff2cce7172381f386e736"
)
CUSTODY_LOCATOR = (
    "facman-custody://candidates/facman-0.1-beta-candidate-main-4683ecd9-"
    "run-33603385303"
)
CUSTODY_MANIFEST_SHA256 = (
    "1be3a4ade7370a6c0ed51dc04eff5ce2ad86eb8034393cdaefa961acd8d4a923"
)
CUSTODY_CHECKSUMS_SHA256 = (
    "a9b8d06fc6d5062b41e68215399680dfa66689e3dacf9d062424f5d1547944b7"
)
ALPHA3_MAIN_REVISION = "227257f36b1d37d5ca13ad3b49cbd7d90836790c"
NEXT_AUTHORITY_GATE = (
    "alpha6_workspace_migration_and_managed_install_then_alpha7_content_world_"
    "play_and_frontend_parity_then_feature_freeze_and_exact_beta_human_release_"
    "authority"
)
ALPHA1_VERSION = "0.1.0-alpha.1"
ALPHA1_CANONICAL_VERSION = f"facman-{ALPHA1_VERSION}"
ALPHA1_TAG = f"v{ALPHA1_VERSION}"
ALPHA2_CANONICAL_VERSION = "facman-0.1.0-alpha.2"
CONTAINMENT_WORK_UNIT = "FACMAN-4.0.0-MISNUMBERING-CONTAINMENT-01"
EXPECTED_PACKAGES = [
    "FacMan-0.1.0-alpha.3-windows-x64-portable.zip",
    "FacMan-0.1.0-alpha.3-windows-x64-setup.exe",
    "FacMan-0.1.0-alpha.3-macos-x64-portable.zip",
    "FacMan-0.1.0-alpha.3-macos-x64-setup.pkg",
    "FacMan-0.1.0-alpha.3-linux-x64-portable.tar.zst",
    "FacMan-0.1.0-alpha.3-linux-x64-setup.run",
    "FacMan-0.1.0-alpha.3-SHA256SUMS.txt",
    "FacMan-0.1.0-alpha.3-evidence.zip",
]
MISNUMBERED_IDENTITY = re.compile(
    r"(?i)(?<![0-9])4\.0\.0(?![0-9])|facman[_-]4[_-]0[_-]0|4-0-0"
)
HISTORICAL_PATH_PREFIXES = (
    ".aide/history/facman-4-0-final-distribution-misnumbered-internal-candidate/",
    ".aide/queue/active/FACMAN-4.0.0-MISNUMBERING-CONTAINMENT-01/",
    "docs/release/history/facman-4.0.0-misnumbered-internal-candidate.md",
    "release/evidence/factorio-version-capability-corpus-4.0.0.v1.json",
    "release/evidence/factorio-version-family-matrix-4.0.0.v1.json",
    "release/index/misnumbering_containment.v1.toml",
    "tests/test_release_identity_coherence.py",
    "tools/release_identity_coherence_check.py",
)


def _toml(relative: str) -> dict[str, Any]:
    with (ROOT / relative).open("rb") as handle:
        return tomllib.load(handle)


def _json(relative: str) -> dict[str, Any]:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def load_records() -> dict[str, Any]:
    return {
        "version": _toml("release/index/version.v2.toml"),
        "compatibility": _toml("release/index/version.v1.toml"),
        "build": _toml("release/index/build_manifest.v1.toml"),
        "channels": _toml("release/index/channels.v1.toml"),
        "product": _toml("release/index/product.v2.toml"),
        "artifacts": _toml("release/index/artifacts.v2.toml"),
        "dependency": _toml("release/index/dependency_lock.v1.toml"),
        "sbom": _json("release/index/sbom.components.v1.json"),
        "train": _toml("release/index/version_train.v1.toml"),
        "distribution": _toml("release/index/final_distribution.v1.toml"),
        "status": _toml("release/index/project_status.v2.toml"),
        "current": _toml("release/index/current_state.v1.toml"),
        "plan": _toml("release/index/plan.v1.toml"),
        "factorio": _toml("release/index/factorio_version_families.v1.toml"),
        "alpha_source": _toml("release/index/alpha_release_source.v1.toml"),
        "ledger": _json("release/ledger/0.1.0-alpha.1/prospective-entry.v1.json"),
        "containment": _toml("release/index/misnumbering_containment.v1.toml"),
        "candidate_closeout": _toml(CANDIDATE_RECEIPT),
    }


def _component(records: list[Any], component_id: str) -> dict[str, Any]:
    return next(
        (
            item
            for item in records
            if isinstance(item, dict) and item.get("id") == component_id
        ),
        {},
    )


def _record(records: list[Any], record_id: str) -> dict[str, Any]:
    return next(
        (
            item
            for item in records
            if isinstance(item, dict) and item.get("id") == record_id
        ),
        {},
    )


def _expect(
    violations: set[str], path: str, actual: Any, expected: Any
) -> None:
    if actual != expected:
        violations.add(f"{path}: expected {expected!r}, got {actual!r}")


def validate_records(records: dict[str, Any]) -> set[str]:
    violations: set[str] = set()
    version = records["version"]
    for field, expected in (
        ("semver", VERSION),
        ("canonical_version", CANONICAL_VERSION),
        ("filename_version", CANONICAL_VERSION),
        ("component_version", VERSION),
        ("channel", CHANNEL),
        ("build_kind", "release"),
    ):
        _expect(violations, f"version.{field}", version.get(field), expected)

    compatibility = records["compatibility"]
    build = records["build"]
    for source_name, source in (("compatibility", compatibility), ("build", build)):
        for field, expected in (
            ("canonical_version", CANONICAL_VERSION),
            ("filename_version", CANONICAL_VERSION),
            ("channel", CHANNEL),
            ("build_kind", "release"),
        ):
            _expect(violations, f"{source_name}.{field}", source.get(field), expected)
    _expect(violations, "compatibility.semver", compatibility.get("semver"), VERSION)
    for component_id in ("facman", "factorio_binding"):
        component = _component(build.get("component", []), component_id)
        _expect(
            violations,
            f"build.component.{component_id}.version",
            component.get("version"),
            VERSION,
        )

    channels = records["channels"].get("channel", [])
    alpha = _record(channels, CHANNEL)
    stable = _record(channels, "stable")
    _expect(
        violations,
        "channels.alpha.versions",
        alpha.get("versions"),
        [
            ALPHA1_CANONICAL_VERSION,
            ALPHA2_CANONICAL_VERSION,
            ALPHA3_CANONICAL_VERSION,
            "facman-0.1.0-alpha.4",
            CANONICAL_VERSION,
        ],
    )
    _expect(violations, "channels.stable.versions", stable.get("versions"), [])
    _expect(
        violations,
        "product.default_channel",
        records["product"].get("default_channel"),
        CHANNEL,
    )

    for artifact in records["artifacts"].get("artifact", []):
        if not isinstance(artifact, dict):
            continue
        filename = str(artifact.get("filename", ""))
        if not filename.lower().startswith(f"facman-{VERSION}-"):
            violations.add(
                "artifacts."
                + str(artifact.get("id", "<unknown>"))
                + f".filename: does not carry {VERSION}"
            )

    dependency = _component(records["dependency"].get("component", []), "factorio_binding")
    sbom = _component(records["sbom"].get("components", []), "factorio_binding")
    _expect(violations, "dependency.factorio_binding.version", dependency.get("version"), VERSION)
    _expect(violations, "sbom.factorio_binding.version", sbom.get("version"), VERSION)
    _expect(
        violations,
        "sbom.publisher_authenticity_proven",
        records["sbom"].get("publisher_authenticity_proven"),
        False,
    )

    train = records["train"]
    for field, expected in (
        ("current_product_target", "0.1.0"),
        ("development_base_version", VERSION),
        ("tracked_contract_identity", CANONICAL_VERSION),
        ("allocated_release_class", CHANNEL),
        ("allocated_version", VERSION),
        ("signing_authorized", False),
        ("publication_authorized", False),
    ):
        _expect(violations, f"train.{field}", train.get(field), expected)
    _expect(
        violations,
        "train.release_source_workunit",
        train.get("release_source_workunit"),
        CURRENT_SOURCE_WORK_UNIT,
    )
    for field, expected in (
        ("release_source_status", "final_candidate_machine_qualified_unpublished"),
        ("release_source_revision", MAIN_REVISION),
        ("release_source_tree", SOURCE_TREE),
        ("release_source_candidate_run", CANDIDATE_RUN),
        ("release_source_candidate_attempt", CANDIDATE_ATTEMPT),
        ("release_source_receipt", CANDIDATE_RECEIPT),
        ("release_source_is_closeout_revision", False),
        ("release_source_is_dev_sync_revision", False),
    ):
        _expect(violations, f"train.{field}", train.get(field), expected)
    for field, expected in (
        ("version_allocation", True),
        ("tag_creation", True),
        ("signing", False),
        ("publication", False),
        ("stable_promotion", False),
    ):
        _expect(violations, f"train.authority.{field}", train.get("authority", {}).get(field), expected)

    distribution = records["distribution"]
    for field, expected in (
        ("version", ALPHA3_VERSION),
        ("canonical_version", ALPHA3_CANONICAL_VERSION),
        ("channel", CHANNEL),
        ("classification", "unsigned_private_draft_cross_platform_manual_test_candidate"),
        ("source_work_unit", SOURCE_WORK_UNIT),
        ("support_claim", "windows_manual_test_candidate_macos_linux_experimental_preview"),
    ):
        _expect(violations, f"distribution.{field}", distribution.get(field), expected)
    _expect(
        violations,
        "distribution.packages",
        [item.get("filename") for item in distribution.get("artifact", [])],
        EXPECTED_PACKAGES,
    )
    authority = distribution.get("authority", {})
    if not authority or any(value is not False for value in authority.values()):
        violations.add("distribution.authority: every external effect must remain false")

    factorio = records["factorio"]
    _expect(violations, "factorio.product_target", factorio.get("product_target"), ALPHA1_VERSION)
    qualification = distribution.get("factorio_qualification", {})
    _expect(
        violations,
        "distribution.factorio_qualification.families",
        qualification.get("families"),
        ["F100", "F110", "F200", "F210"],
    )
    _expect(
        violations,
        "distribution.factorio_qualification.exact_versions",
        qualification.get("exact_versions"),
        ["1.0.0", "1.1.110", "2.0.77", "2.1.14"],
    )
    _expect(
        violations,
        "distribution.factorio_qualification.corpus",
        qualification.get("corpus"),
        "release/evidence/factorio-version-capability-corpus-0.1.0-alpha.1.v1.json",
    )
    _expect(
        violations,
        "distribution.factorio_qualification.matrix",
        qualification.get("matrix"),
        "release/evidence/factorio-version-family-matrix-0.1.0-alpha.1.v1.json",
    )

    status = records["status"]
    current = records["current"]
    _expect(violations, "status.product_version", status.get("product_version"), VERSION)
    _expect(violations, "status.current_checkpoint", status.get("current_checkpoint"), CHECKPOINT)
    _expect(violations, "status.accepted_integration_revision", status.get("accepted_integration_revision"), CURRENT_DEV_REVISION)
    _expect(violations, "status.active_work_unit", status.get("active_work_unit"), ACTIVE_WORK_UNIT)
    _expect(violations, "status.last_closed_work_unit", status.get("last_closed_work_unit"), LAST_CLOSED_WORK_UNIT)
    _expect(violations, "status.next_authority_gate", status.get("next_authority_gate"), NEXT_AUTHORITY_GATE)
    _expect(violations, "status.safe_beta", status.get("safe_beta"), False)
    for field, expected in (
        ("implementation_proof_revision", IMPLEMENTATION_REVISION),
        ("hosted_matrix_revision", MAIN_REVISION),
        ("reviewed_dev_checkpoint_revision", CURRENT_DEV_REVISION),
        ("reviewed_dev_checkpoint_tree", CURRENT_DEV_TREE),
        ("canonical_main_revision", MAIN_REVISION),
        ("promotion_source_revision", IMPLEMENTATION_REVISION),
        ("planning_promotion_revision", MAIN_REVISION),
        ("dev_synchronization_revision", CURRENT_DEV_REVISION),
        ("runtime_candidate_revision", MAIN_REVISION),
        ("qualification_source_revision", MAIN_REVISION),
        ("qualification_evidence_revision", MAIN_REVISION),
        ("qualification_integration_revision", DEV_REVISION),
        ("truth_closeout_revision", CURRENT_DEV_REVISION),
        ("canonical_main_promotion", True),
    ):
        _expect(violations, f"status.{field}", status.get(field), expected)
    status_product = status.get("product", {})
    _expect(violations, "status.product.phase", status_product.get("phase"), PHASE)
    _expect(
        violations,
        "status.product.current_work_unit",
        status_product.get("current_work_unit"),
        ACTIVE_WORK_UNIT,
    )
    _expect(
        violations,
        "status.product.canonical_main_promotion",
        status_product.get("canonical_main_promotion"),
        True,
    )
    status_closeout = status.get("canonical_plan_and_truth_closeout", {})
    for field, expected in (
        ("status", "phase0_integrations_closed"),
        ("work_unit", CLOSEOUT_WORK_UNIT),
        ("promotion_source_revision", IMPLEMENTATION_REVISION),
        ("canonical_main_revision", MAIN_REVISION),
        ("planning_promotion_revision", MAIN_REVISION),
        ("dev_synchronization_revision", PHASE0_DEV_REVISION),
        ("dev_synchronization_tree", PHASE0_DEV_TREE),
        ("candidate_source_tree", SOURCE_TREE),
        ("candidate_run", CANDIDATE_RUN),
        ("candidate_attempt", CANDIDATE_ATTEMPT),
        ("candidate_receipt", CANDIDATE_RECEIPT),
        ("candidate_source_is_closeout_revision", False),
        ("closeout_revision_candidate_qualified", False),
        ("synchronized_tree_extends_revision_qualification", False),
        ("future_revision_requires_new_candidate_run", True),
    ):
        _expect(
            violations,
            f"status.canonical_plan_and_truth_closeout.{field}",
            status_closeout.get(field),
            expected,
        )
    alpha5 = status.get("alpha5_beta_readiness", {})
    for field, expected in (
        ("work_unit", CURRENT_SOURCE_WORK_UNIT),
        ("closeout_work_unit", CLOSEOUT_WORK_UNIT),
        ("truth_remediation_work_unit", TRUTH_REMEDIATION_WORK_UNIT),
        ("receipt", CANDIDATE_RECEIPT),
        ("candidate_source_revision", MAIN_REVISION),
        ("candidate_source_tree", SOURCE_TREE),
        ("candidate_run", CANDIDATE_RUN),
        ("candidate_attempt", CANDIDATE_ATTEMPT),
        ("candidate_artifact_name", CANDIDATE_ARTIFACT),
        ("bundle_artifact_digest", CANDIDATE_ARTIFACT_DIGEST),
        ("custody_locator", CUSTODY_LOCATOR),
        ("custody_manifest_sha256", CUSTODY_MANIFEST_SHA256),
        ("custody_checksums_sha256", CUSTODY_CHECKSUMS_SHA256),
        ("bundle_artifact_id", 9836639957),
        ("bundle_file_count", 14),
        ("candidate_source_is_closeout_revision", False),
        ("candidate_source_is_dev_sync_revision", False),
        ("candidate_source_is_canonical_main_revision", True),
        ("closeout_revision_candidate_qualified", False),
        ("synchronized_tree_extends_revision_qualification", False),
        ("current_main_after_closeout_qualified_by_this_receipt", False),
        ("future_revision_requires_new_candidate_run", True),
        ("beta_ready", False),
        ("factorio_execution", False),
        ("managed_install_human_verdict", False),
        ("accessibility_human_verdict", False),
        ("signing", False),
        ("notarization", False),
        ("publication", False),
        ("support", False),
    ):
        _expect(
            violations,
            f"status.alpha5_beta_readiness.{field}",
            alpha5.get(field),
            expected,
        )
    _expect(violations, "current.product_version", current.get("product_version"), VERSION)
    _expect(violations, "current.phase", current.get("phase"), PHASE)
    _expect(violations, "current.checkpoint", current.get("checkpoint"), CHECKPOINT)
    _expect(violations, "current.active_work_unit", current.get("active_work_unit"), ACTIVE_WORK_UNIT)
    _expect(violations, "current.last_closed_work_unit", current.get("last_closed_work_unit"), LAST_CLOSED_WORK_UNIT)
    _expect(violations, "current.next_work_unit", current.get("next_work_unit"), NEXT_WORK_UNIT)
    _expect(violations, "current.next_authority_gate", current.get("next_authority_gate"), NEXT_AUTHORITY_GATE)
    _expect(violations, "current.product.release", current.get("product", {}).get("release"), "unpublished")
    _expect(violations, "current.product.safe_beta", current.get("product", {}).get("safe_beta"), False)
    current_revisions = current.get("revisions", {})
    for field, expected in (
        ("reviewed_dev_checkpoint", CURRENT_DEV_REVISION),
        ("reviewed_dev_checkpoint_tree", CURRENT_DEV_TREE),
        ("canonical_main", MAIN_REVISION),
        ("promotion_source", IMPLEMENTATION_REVISION),
        ("planning_promotion", MAIN_REVISION),
        ("dev_synchronization", CURRENT_DEV_REVISION),
        ("runtime_candidate", MAIN_REVISION),
        ("qualification_source", MAIN_REVISION),
        ("qualification_evidence", MAIN_REVISION),
        ("qualification_integration", DEV_REVISION),
        ("truth_closeout", CURRENT_DEV_REVISION),
    ):
        _expect(violations, f"current.revisions.{field}", current_revisions.get(field), expected)

    plan = records["plan"]
    _expect(violations, "plan.active_release", plan.get("active_release"), "FACMAN-0.1.0-ALPHA.6")
    plan_release = _record(plan.get("release", []), "FACMAN-0.1.0-ALPHA.5")
    _expect(violations, "plan.release.version", plan_release.get("version"), VERSION)
    _expect(violations, "plan.release.status", plan_release.get("status"), "complete")
    alpha6_release = _record(plan.get("release", []), "FACMAN-0.1.0-ALPHA.6")
    _expect(violations, "plan.alpha6_release.status", alpha6_release.get("status"), "active")
    _expect(violations, "plan.alpha6_release.version_allocated", alpha6_release.get("version_allocated"), False)
    alpha3_release = _record(plan.get("release", []), "FACMAN-0.1.0-ALPHA.3")
    _expect(violations, "plan.alpha3_release.status", alpha3_release.get("status"), "complete")
    alpha1_release = _record(plan.get("release", []), "FACMAN-0.1.0-ALPHA.1")
    _expect(violations, "plan.alpha1_release.status", alpha1_release.get("status"), "complete")
    recovery_work_unit = _record(plan.get("workunit", []), RECOVERY_WORK_UNIT)
    _expect(violations, "plan.recovery_workunit.status", recovery_work_unit.get("status"), "complete")
    human_work_unit = _record(plan.get("workunit", []), HUMAN_WORK_UNIT)
    _expect(violations, "plan.human_workunit.status", human_work_unit.get("status"), "cancelled")
    _expect(violations, "plan.human_workunit.owner", human_work_unit.get("owner"), "Jules")
    _expect(
        violations,
        "plan.human_workunit.base_revision",
        human_work_unit.get("base_revision"),
        ALPHA3_MAIN_REVISION,
    )
    if human_work_unit.get("blockers"):
        violations.add("plan.human_workunit.blockers: superseded historical packet must not remain active")
    human_outcome = str(human_work_unit.get("outcome", "")).lower()
    if "distinct exact-byte human receipt" not in human_outcome or "beta.1" not in human_outcome:
        violations.add("plan.human_workunit.outcome: distinct beta.1 exact-byte receipt law is required")
    source_work_unit = _record(plan.get("workunit", []), SOURCE_WORK_UNIT)
    _expect(
        violations,
        "plan.source_workunit.status",
        source_work_unit.get("status"),
        "complete",
    )
    beta_work_unit = _record(plan.get("workunit", []), BETA_READINESS_WORK_UNIT)
    _expect(
        violations,
        "plan.beta_readiness_workunit.status",
        beta_work_unit.get("status"),
        "complete",
    )
    historical_closeout_work_unit = _record(
        plan.get("workunit", []), HISTORICAL_CLOSEOUT_WORK_UNIT
    )
    _expect(
        violations,
        "plan.alpha5_historical_closeout_workunit.status",
        historical_closeout_work_unit.get("status"),
        "complete",
    )
    remediation_work_unit = _record(
        plan.get("workunit", []), TRUTH_REMEDIATION_WORK_UNIT
    )
    _expect(
        violations,
        "plan.alpha5_truth_remediation_workunit.status",
        remediation_work_unit.get("status"),
        "complete",
    )
    _expect(
        violations,
        "plan.alpha5_truth_remediation_workunit.depends_on",
        remediation_work_unit.get("depends_on"),
        [HISTORICAL_CLOSEOUT_WORK_UNIT],
    )
    closeout_work_unit = _record(plan.get("workunit", []), CLOSEOUT_WORK_UNIT)
    _expect(
        violations,
        "plan.alpha5_closeout_workunit.status",
        closeout_work_unit.get("status"),
        "complete",
    )
    _expect(
        violations,
        "plan.alpha5_closeout_workunit.base_revision",
        closeout_work_unit.get("base_revision"),
        DEV_REVISION,
    )
    _expect(
        violations,
        "plan.alpha5_closeout_workunit.depends_on",
        closeout_work_unit.get("depends_on"),
        [TRUTH_REMEDIATION_WORK_UNIT],
    )

    candidate_closeout = records["candidate_closeout"]
    topology = candidate_closeout.get("topology", {})
    for field, expected in (
        ("main_revision", MAIN_REVISION),
        ("dev_revision", DEV_REVISION),
        ("shared_tree", SOURCE_TREE),
        ("main_is_ancestor_of_dev", True),
        ("trees_equal", True),
    ):
        _expect(
            violations,
            f"candidate_closeout.topology.{field}",
            topology.get(field),
            expected,
        )
    candidate = candidate_closeout.get("candidate", {})
    for field, expected in (
        ("workflow_run", CANDIDATE_RUN),
        ("workflow_attempt", CANDIDATE_ATTEMPT),
        ("head_sha", MAIN_REVISION),
        ("head_tree", SOURCE_TREE),
        ("status", "completed"),
        ("conclusion", "success"),
    ):
        _expect(violations, f"candidate_closeout.candidate.{field}", candidate.get(field), expected)
    _expect(
        violations,
        "candidate_closeout.candidate_artifact_name",
        candidate_closeout.get("candidate_artifact_name"),
        CANDIDATE_ARTIFACT,
    )
    _expect(
        violations,
        "candidate_closeout.candidate_artifact_digest",
        candidate_closeout.get("candidate_artifact_digest"),
        CANDIDATE_ARTIFACT_DIGEST,
    )
    custody = candidate_closeout.get("custody", {})
    for field, expected in (
        ("locator", CUSTODY_LOCATOR),
        ("file_count", 14),
        ("manifest_sha256", CUSTODY_MANIFEST_SHA256),
        ("checksums_sha256", CUSTODY_CHECKSUMS_SHA256),
    ):
        _expect(
            violations,
            f"candidate_closeout.custody.{field}",
            custody.get(field),
            expected,
        )
    guards = candidate_closeout.get("guards", {})
    expected_guards = {
        "candidate_source_is_truth_commit": False,
        "truth_commit_inherits_candidate_qualification": False,
        "future_product_revision_requires_new_candidate_run": True,
        "historical_receipt_is_current": False,
        "historical_distribution_is_current": False,
        "expired_producer_exception_release_active": False,
    }
    for field, expected in expected_guards.items():
        _expect(
            violations,
            f"candidate_closeout.guards.{field}",
            guards.get(field),
            expected,
        )
    axes = candidate_closeout.get("axes", {})
    expected_true_axes = {
        "engineering_complete",
        "machine_qualified",
        "protected_dev_integration",
        "protected_main_promotion",
        "dev_back_sync",
    }
    expected_false_axes = {
        "human_desktop_accepted",
        "real_play_accepted",
        "managed_install_accepted",
        "linux_human_accepted",
        "macos_human_accepted",
        "signed",
        "notarized",
        "tagged",
        "published",
        "supported",
    }
    for field in expected_true_axes:
        _expect(violations, f"candidate_closeout.axes.{field}", axes.get(field), True)
    for field in expected_false_axes:
        _expect(violations, f"candidate_closeout.axes.{field}", axes.get(field), False)

    alpha_source = records["alpha_source"]
    ledger = records["ledger"]
    for source_name, source in (("alpha_source", alpha_source), ("ledger", ledger)):
        _expect(violations, f"{source_name}.version", source.get("version"), ALPHA1_VERSION)
    _expect(
        violations,
        "alpha_source.canonical_version",
        alpha_source.get("canonical_version"),
        ALPHA1_CANONICAL_VERSION,
    )
    _expect(violations, "alpha_source.tag.name", alpha_source.get("tag", {}).get("name"), ALPHA1_TAG)
    _expect(violations, "ledger.tag", ledger.get("tag"), ALPHA1_TAG)
    for source_name, source in (("alpha_source", alpha_source), ("ledger", ledger)):
        source_authority = source.get("authority", {})
        if not source_authority or any(value is not False for value in source_authority.values()):
            violations.add(f"{source_name}.authority: every external effect must remain false")

    containment = records["containment"]
    _expect(violations, "containment.work_unit", containment.get("work_unit"), CONTAINMENT_WORK_UNIT)
    _expect(violations, "containment.source.head", containment.get("source", {}).get("head"), "4889816b65fe474bef8901c4be187cee4d3667c6")
    _expect(violations, "containment.source.tree", containment.get("source", {}).get("tree"), "4794913da07c964cbf356abb9d7811281b3d8b1b")
    external_state = containment.get("external_state", {})
    if not external_state or any(value is not False for value in external_state.values()):
        violations.add("containment.external_state: every external effect must remain false")
    return violations


def validate_source_bindings() -> set[str]:
    violations: set[str] = set()
    header = (ROOT / "runtime/core/generated/version.h").read_text(encoding="utf-8")
    for macro, expected in (
        ("FACMAN_VERSION_SEMVER", VERSION),
        ("FACMAN_VERSION_CANONICAL", CANONICAL_VERSION),
        ("FACMAN_VERSION_FILENAME", CANONICAL_VERSION),
        ("FACMAN_VERSION_COMPONENT", VERSION),
    ):
        if f'#define {macro} "{expected}"' not in header:
            violations.add(f"runtime/core/generated/version.h:{macro}: missing {expected}")

    cli = (ROOT / "apps/cli/command_dispatch.cpp").read_text(encoding="utf-8")
    tui = (ROOT / "apps/tui/tui_host.cpp").read_text(encoding="utf-8")
    if "FACMAN_VERSION_SEMVER" not in cli or 'command == "--version"' not in cli:
        violations.add("apps/cli/command_dispatch.cpp: --version is not bound to generated identity")
    if "FACMAN_VERSION_SEMVER" not in tui or 'value == "--version"' not in tui:
        violations.add("apps/tui/tui_host.cpp: --version is not bound to generated identity")

    cmake = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
    if re.search(
        r"project\s*\(\s*facman\s+VERSION\s+0\.1\.0\b",
        cmake,
        re.DOTALL | re.IGNORECASE,
    ) is None:
        violations.add("CMakeLists.txt: numeric project version is not 0.1.0")
    return violations


def tracked_and_untracked_files() -> list[Path]:
    completed = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    return [ROOT / line for line in completed.stdout.splitlines() if (ROOT / line).is_file()]


def misnumbered_line_is_allowed(relative: str, line: str) -> bool:
    if relative.startswith(HISTORICAL_PATH_PREFIXES):
        return True
    remainder = line.replace(CONTAINMENT_WORK_UNIT, "").replace("\\", "")
    return MISNUMBERED_IDENTITY.search(remainder) is None


def detect_misnumbered_identity() -> set[str]:
    violations: set[str] = set()
    for path in tracked_and_untracked_files():
        relative = path.relative_to(ROOT).as_posix()
        if relative.startswith((".git/", ".aide.local/", "build/", "dist/", "out/", "tmp/")):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if MISNUMBERED_IDENTITY.search(relative) and not relative.startswith(HISTORICAL_PATH_PREFIXES):
            violations.add(f"{relative}: misnumbered identity in active path")
        for line_number, line in enumerate(text.splitlines(), start=1):
            normalized = line.replace("\\", "")
            if MISNUMBERED_IDENTITY.search(normalized) and not misnumbered_line_is_allowed(relative, line):
                violations.add(f"{relative}:{line_number}: active misnumbered identity")
    return violations


def detect() -> set[str]:
    violations = validate_records(load_records())
    violations.update(validate_source_bindings())
    violations.update(detect_misnumbered_identity())
    return violations


def main() -> int:
    return architecture_fitness.run("release_identity_coherence", detect)


if __name__ == "__main__":
    raise SystemExit(main())
