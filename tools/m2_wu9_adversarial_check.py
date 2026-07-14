# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import hashlib
import json
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/m2_wu9/adversarial-corpus.v1.json"
SETUP_ROOT = ROOT.parent / "universal-setup"
EXPECTED_SETUP_REVISION = "3f8489275077347c2918f3bb03614ec6431362ff"
EXPECTED_SETUP_TREE = "8861d0d640af8dc24e774f5ff934ad67f8a5d5cd"
EXPECTED_SETUP_MANIFEST_SHA256 = "c3d3ee7ff13c95371603ec0690265bdef549e2ade7468ed5ec690c067d8d29bb"
EXPECTED_CASES = {
    "unicode_and_long_paths",
    "case_collisions",
    "unicode_normalization_collisions",
    "links_and_reparse_points",
    "source_replacement",
    "target_ancestor_replacement",
    "concurrent_applies",
    "read_only_sources",
    "partial_writes",
    "insufficient_space_simulation",
    "cross_device_move",
    "changed_ownership_manifests",
    "audit_chain_tampering",
    "stale_and_replayed_plans",
    "foreign_files_during_repair_or_uninstall",
    "frontend_cancellation_and_process_termination",
}


def canonical_text_sha256(path: Path) -> str:
    # Git may materialize text with CRLF on Windows. Hash the repository text
    # identity, not the platform checkout spelling of its line endings.
    return hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()


def main() -> int:
    document = json.loads(CORPUS.read_text(encoding="utf-8"))
    problems: list[str] = []
    if document.get("schema") != "factorio.m2_adversarial_corpus.v1":
        problems.append("unexpected corpus schema")
    if document.get("status") not in {
        "provider_passed_consumer_candidate",
        "accepted_dev_integration_pending_operator_verdict",
    }:
        problems.append("unrecognized monotonic proof status")

    setup = document.get("setup_provider", {})
    expected_setup = {
        "task_head": "682eede3a954d9603b29308fcc28cc87c911aa37",
        "task_tree": EXPECTED_SETUP_TREE,
        "reviewed_pr": 17,
        "main_revision": EXPECTED_SETUP_REVISION,
        "main_tree": EXPECTED_SETUP_TREE,
        "coverage_manifest_sha256": EXPECTED_SETUP_MANIFEST_SHA256,
        "push_ci_run": "29354954411",
        "pr_ci_run": "29354958088",
        "main_ci_run": "29355175219",
    }
    for key, expected in expected_setup.items():
        if setup.get(key) != expected:
            problems.append(f"setup provider {key} must equal {expected!r}")

    lock = tomllib.loads((ROOT / "release/index/workspace_lock.v1.toml").read_text(encoding="utf-8"))
    pins = {item["id"]: item["pin"] for item in lock.get("component", [])}
    if pins.get("universal_setup") != EXPECTED_SETUP_REVISION:
        problems.append("workspace lock must pin the accepted WU9 Universal Setup main")

    manifest = SETUP_ROOT / setup.get("coverage_manifest", "")
    if manifest.is_file() and canonical_text_sha256(manifest) != EXPECTED_SETUP_MANIFEST_SHA256:
        problems.append("local Universal Setup coverage manifest differs from its accepted digest")

    platforms = {item.get("platform"): item for item in document.get("platform_evidence", [])}
    expected_runners = {"linux": "ubuntu-24.04", "macos": "macos-15-intel", "windows": "windows-2022"}
    if set(platforms) != set(expected_runners):
        problems.append("platform evidence must contain exactly Linux, macOS, and Windows")
    for platform, runner in expected_runners.items():
        evidence = platforms.get(platform, {})
        if evidence.get("runner") != runner or evidence.get("workflow_run") != "29355175219" or evidence.get("result") != "success":
            problems.append(f"{platform} must bind successful exact-main Setup run 29355175219")

    cases = document.get("cases", [])
    by_id = {case.get("id"): case for case in cases}
    if len(by_id) != len(cases):
        problems.append("corpus case identifiers must be unique")
    if set(by_id) != EXPECTED_CASES:
        problems.append("corpus must contain exactly the sixteen reviewed M2 cases")
    for case_id, case in by_id.items():
        expected_owner = "factorio_launcher" if case_id == "frontend_cancellation_and_process_termination" else "universal_setup"
        if case.get("owner") != expected_owner:
            problems.append(f"{case_id}: wrong proof owner")
        evidence = case.get("evidence", [])
        if not evidence:
            problems.append(f"{case_id}: missing evidence")
        if expected_owner == "factorio_launcher":
            for proof in evidence:
                path = ROOT / proof.get("path", "")
                if not path.is_file():
                    problems.append(f"{case_id}: missing local evidence file {proof.get('path')}")
                    continue
                text = path.read_text(encoding="utf-8")
                for marker in proof.get("markers", []):
                    if marker not in text:
                        problems.append(f"{case_id}: marker {marker!r} missing from {proof.get('path')}")

    authority = document.get("authority", {})
    if authority != {
        "automation_can_record_operator_verdict": False,
        "operator_verdict": "pending",
        "ordinary_live_apply": "unavailable_pending_operator_acceptance",
        "execution_authority": False,
        "h1_inference": "none",
    }:
        problems.append("corpus authority boundary changed")

    if problems:
        for problem in problems:
            print(f"m2-wu9-adversarial-check: {problem}", file=sys.stderr)
        return 1
    print("m2-wu9-adversarial-check: ok (16 cases; 3 Setup platforms; human verdict pending)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
