from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_ROOT = REPO_ROOT / ".aide/fixtures/aide-self-consumer-fixture-v0"
REPORT_ROOT = REPO_ROOT / ".aide/reports/aide-self-consumer-fixture-v0"

EXPECTED_SCENARIOS = {
    "fresh-install",
    "profile-generation",
    "upgrade-from-previous-version",
    "same-version-idempotence",
    "target-owned-state-preservation",
    "rollback-after-upgrade",
    "uninstall-preserves-target-state",
    "offline-operation",
    "source-repo-confusion-refusal",
}

REQUIRED_PROOFS = {
    "fresh_install",
    "profile_generation",
    "upgrade_from_previous_version",
    "same_version_idempotence",
    "target_owned_state_preservation",
    "rollback",
    "uninstall",
    "offline_operation",
    "source_repo_not_target",
}

TARGET_OWNED_PATHS = {
    ".aide/memory/project-state.md",
    ".aide/queue/target-local-task/status.yaml",
    ".aide/evidence/target-local-proof.md",
    ".aide.local/cache/state.json",
    "AGENTS.md#manual-content",
    "README.md",
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


class AIDESelfConsumerFixtureV0Tests(unittest.TestCase):
    def scenario_paths(self) -> list[Path]:
        return sorted((FIXTURE_ROOT / "scenarios").glob("*.json"))

    def scenarios(self) -> dict[str, dict[str, Any]]:
        data = {}
        for path in self.scenario_paths():
            scenario = read_json(path)
            data[scenario["scenario_id"]] = scenario
        return data

    def test_manifest_declares_expected_fixture_boundary(self) -> None:
        manifest = read_json(FIXTURE_ROOT / "fixture.json")
        self.assertEqual(manifest["result"], "PASS_WITH_WARNINGS")
        self.assertEqual(manifest["proposed_capability"], "aide_self_consumer_fixture_v0")
        self.assertEqual(set(manifest["scenario_ids"]), EXPECTED_SCENARIOS)
        self.assertTrue(REQUIRED_PROOFS.issubset(set(manifest["required_lifecycle_proofs"])))
        target = manifest["target_model"]
        self.assertFalse(target["source_repo_is_target"])
        self.assertFalse(target["source_generated_state_is_target_truth"])
        self.assertTrue(target["fixture_only"])
        self.assertTrue(target["temp_workspace_only"])
        self.assertTrue(target["offline_required"])
        self.assertEqual(manifest["recommended_next_task"], "AIDE-CHECK-AIDE-SELF-CONSUMER-FIXTURE-V0-01")

    def test_all_scenarios_are_fixture_only_and_non_mutating(self) -> None:
        scenarios = self.scenarios()
        self.assertEqual(set(scenarios), EXPECTED_SCENARIOS)
        for scenario_id, scenario in scenarios.items():
            with self.subTest(scenario_id=scenario_id):
                self.assertTrue(scenario["target_fixture_only"])
                self.assertTrue(scenario["temp_workspace_only"])
                self.assertFalse(scenario["source_repo_as_target"])
                self.assertFalse(scenario["source_repo_apply_occurred"])
                self.assertFalse(scenario["real_target_repo_modified"])
                self.assertFalse(scenario["network_calls_occurred"])
                self.assertFalse(scenario["provider_model_calls_occurred"])
                self.assertFalse(scenario["release_publication_occurred"])

    def test_lifecycle_matrix_covers_required_proofs(self) -> None:
        scenarios = self.scenarios()
        observed_proofs = set()
        for scenario in scenarios.values():
            observed_proofs.update(scenario.get("proof_points", []))
        self.assertTrue(REQUIRED_PROOFS.issubset(observed_proofs))
        matrix = read_json(FIXTURE_ROOT / "manifests/lifecycle-matrix.json")
        self.assertTrue(matrix["all_scenarios_are_fixture_only"])
        self.assertTrue(matrix["all_scenarios_are_offline"])
        self.assertFalse(matrix["real_target_apply_authorized"])
        self.assertFalse(matrix["source_repo_apply_authorized"])

    def test_target_owned_state_is_explicitly_preserved(self) -> None:
        ownership = read_json(FIXTURE_ROOT / "manifests/ownership-map.json")
        self.assertTrue(TARGET_OWNED_PATHS.issubset(set(ownership["target_owned_preservation_examples"])))
        for ownership_class in [
            "project_owned",
            "project_overlay",
            "project_generated",
            "runtime_generated",
            "local_only",
            "evidence_only",
            "preserved_legacy",
            "unknown",
            "never_touch",
        ]:
            self.assertIn(ownership_class, ownership["automatic_apply_blocked_for"])
        preservation = read_json(FIXTURE_ROOT / "scenarios/target-owned-state-preservation.json")
        self.assertTrue(TARGET_OWNED_PATHS.issubset(set(preservation["preserved_paths"])))
        uninstall = read_json(FIXTURE_ROOT / "scenarios/uninstall-preserves-target-state.json")
        self.assertTrue(TARGET_OWNED_PATHS.issubset(set(uninstall["preserved_paths"])))

    def test_source_repo_confusion_refuses_closed(self) -> None:
        scenario = read_json(FIXTURE_ROOT / "scenarios/source-repo-confusion-refusal.json")
        self.assertEqual(scenario["expected_result"], "BLOCKED")
        self.assertEqual(
            scenario["expected_refusal_code"],
            "aide_self_consumer_fixture.source_repo_target_confusion_refused",
        )
        self.assertIn("source_repo_apply_refused", scenario["proof_points"])
        self.assertFalse(scenario["source_repo_as_target"])
        self.assertFalse(scenario["source_repo_apply_occurred"])

    def test_source_pack_and_target_states_do_not_export_source_truth(self) -> None:
        source_pack = read_json(FIXTURE_ROOT / "states/source-pack-v0.json")
        self.assertFalse(source_pack["source_repo_is_target"])
        self.assertFalse(source_pack["source_repo_identity_exported_to_target"])
        self.assertFalse(source_pack["source_generated_state_exported_as_target_truth"])
        self.assertFalse(source_pack["contains_raw_prompts"])
        self.assertFalse(source_pack["contains_raw_responses"])
        self.assertFalse(source_pack["contains_secrets"])
        before = read_json(FIXTURE_ROOT / "states/installed-target-before-v0.json")
        after = read_json(FIXTURE_ROOT / "states/installed-target-after-v1.json")
        self.assertFalse(before["source_repo_is_target"])
        self.assertFalse(after["source_repo_is_target"])
        self.assertTrue(TARGET_OWNED_PATHS.issubset(set(after["preserved_target_owned_paths"])))

    def test_report_summary_matches_fixture(self) -> None:
        report = read_json(REPORT_ROOT / "validation-summary.json")
        self.assertEqual(report["result"], "PASS_WITH_WARNINGS")
        self.assertEqual(report["proposed_capability"], "aide_self_consumer_fixture_v0")
        self.assertEqual(report["material_finding_count"], 0)
        self.assertEqual(report["missing_evidence"], 0)
        self.assertEqual(report["scenario_count"], len(EXPECTED_SCENARIOS))
        self.assertTrue(report["fresh_install_proof"])
        self.assertTrue(report["profile_generation_proof"])
        self.assertTrue(report["upgrade_proof"])
        self.assertTrue(report["rollback_proof"])
        self.assertTrue(report["uninstall_proof"])
        self.assertTrue(report["offline_operation_proof"])
        self.assertTrue(report["source_repo_not_target_proof"])
        self.assertFalse(report["real_target_repo_modified"])
        self.assertFalse(report["source_repo_apply_occurred"])
        self.assertEqual(report["recommended_next_task"], "AIDE-CHECK-AIDE-SELF-CONSUMER-FIXTURE-V0-01")


if __name__ == "__main__":
    unittest.main()
