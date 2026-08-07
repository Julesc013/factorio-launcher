# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from tools import provider_semantic_conformance as semantic


ROOT = Path(__file__).resolve().parents[1]


def probe(mode: semantic.Mode, workspace: Path) -> dict[str, object]:
    corpus = semantic.load_corpus()
    commands = [
        {
            "id": row["id"],
            "command": row["command"],
            "status": row["expected_status"],
            "request_validated": row["expected_status"] == "ok",
            "dispatch_classification": "read_only",
            "response_ownership": "client_owned_value",
        }
        for row in corpus["command_dispatch"]
    ]
    operations = [
        {
            "id": row["id"],
            "operation_id": "operation-semantic-" + row["id"],
            "attempt_id": "attempt-semantic-" + row["id"],
            "owner": "facman.client",
            "phase": "fixture",
            "terminal_outcome": row["outcome"],
            "effects_may_have_occurred": row["effects_may_have_occurred"],
            "error_code": "",
            "recovery": {
                "required": row["effects_may_have_occurred"],
                "transaction_id": (
                    corpus["interrupted_recovery"]["journal_identity"]
                    if row["effects_may_have_occurred"]
                    else ""
                ),
                "inspect_command": (
                    "workspace.recovery.inspect"
                    if row["effects_may_have_occurred"]
                    else ""
                ),
            },
        }
        for row in corpus["operation_outcomes"]
    ]
    refusals = [
        {
            **row,
            "reason": "deterministic test reason",
        }
        for row in corpus["structured_refusals"]
    ]
    return {
        "schema": semantic.PROBE_SCHEMA,
        "provider_mode": mode.name,
        "linkage": mode.linkage,
        "workspace": str(workspace),
        "semantics": {
            "command_dispatch": commands,
            "operation_outcomes": operations,
            "structured_refusals": refusals,
            "interrupted_recovery": corpus["interrupted_recovery"],
        },
    }


class ProviderSemanticConformanceTests(unittest.TestCase):
    def test_mode_matrix_is_exact_and_closed(self) -> None:
        self.assertEqual(
            [mode.name for mode in semantic.MODES],
            [
                "source_static",
                "source_shared",
                "installed_static",
                "installed_shared",
                "relocated_installed_static",
                "relocated_installed_shared",
                "private_runtime",
            ],
        )
        self.assertEqual({mode.linkage for mode in semantic.MODES}, {"static", "shared"})

    def test_corpus_closes_required_semantic_scenarios(self) -> None:
        corpus = semantic.load_corpus()
        self.assertEqual(8, len(corpus["operation_outcomes"]))
        self.assertEqual(
            {
                "completed",
                "refused-before-dispatch",
                "failed-before-dispatch",
                "cancelled-before-dispatch",
                "cancellation-requested-but-completed",
                "timeout-before-dispatch",
                "post-dispatch-outcome-unknown",
                "transport-loss-outcome-unknown",
            },
            {row["id"] for row in corpus["operation_outcomes"]},
        )
        self.assertEqual(
            {"malformed-request", "unsupported-command", "isolation-not-proven", "stale-readiness"},
            {row["id"] for row in corpus["structured_refusals"]},
        )

    def test_probe_normalization_removes_only_invocation_metadata(self) -> None:
        corpus = semantic.load_corpus()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            first_mode, second_mode = semantic.MODES[:2]
            first = semantic.validate_and_normalize_probe(
                probe(first_mode, root / first_mode.name),
                first_mode,
                root / first_mode.name,
                corpus,
            )
            second = semantic.validate_and_normalize_probe(
                probe(second_mode, root / second_mode.name),
                second_mode,
                root / second_mode.name,
                corpus,
            )
        self.assertEqual(first, second)
        self.assertNotIn("provider_mode", first)
        self.assertNotIn("workspace", first)

    def test_probe_refuses_unknown_paths_fields_and_markers(self) -> None:
        corpus = semantic.load_corpus()
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary).resolve() / "workspace"
            value = probe(semantic.MODES[0], workspace)
            variants = []
            unknown = copy.deepcopy(value)
            unknown["future"] = True
            variants.append((unknown, "unknown or missing"))
            path = copy.deepcopy(value)
            path["semantics"]["structured_refusals"][0]["reason"] = str(
                workspace / "leak"
            )
            variants.append((path, "absolute path"))
            marker = copy.deepcopy(value)
            marker["workspace"] = "<mode-workspace>"
            variants.append((marker, "workspace|marker"))
            for candidate, pattern in variants:
                with self.subTest(pattern=pattern):
                    with self.assertRaisesRegex(ValueError, pattern):
                        semantic.validate_and_normalize_probe(
                            candidate, semantic.MODES[0], workspace, corpus
                        )

    def test_comparison_and_every_material_negative_control_fail_closed(self) -> None:
        baseline = {
            "command_dispatch": [{"id": "command", "status": "ok"}],
            "operation_outcomes": [
                {"id": "operation", "terminal_outcome": "completed", "effects_may_have_occurred": False}
            ],
            "structured_refusals": [{"id": "refusal", "code": "refused"}],
            "interrupted_recovery": {"available_recovery_action": "inspect"},
            "release_resolution": {
                "root_digest": "1" * 64,
                "authority": {"product_authority_granted": False},
            },
            "provider_contract_identity": [{"contract_digest": "2" * 64}],
        }
        equal = {mode.name: copy.deepcopy(baseline) for mode in semantic.MODES}
        self.assertRegex(semantic.compare_semantics(equal), r"^[0-9a-f]{64}$")
        controls = semantic.negative_controls(baseline)
        self.assertEqual(8, len(controls))
        self.assertEqual({"refused"}, set(controls.values()))

    def test_normalization_policy_is_domain_separated_and_material_fields_closed(self) -> None:
        self.assertRegex(semantic.normalization_policy_digest(), r"^[0-9a-f]{64}$")
        self.assertIn("authority", semantic.NORMALIZATION_POLICY["material_fields_never_normalized"])
        self.assertNotIn("authority", semantic.NORMALIZATION_POLICY["normalized_fields"])

    def test_schema_and_workflow_bind_distinct_semantic_evidence(self) -> None:
        schema = json.loads(
            (
                ROOT
                / "contracts/schema/release/provider_semantic_conformance.v1.schema.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(semantic.SCHEMA, schema["properties"]["schema"]["const"])
        workflow = (ROOT / ".github/workflows/provider-conformance.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("tools/provider_semantic_conformance.py", workflow)
        self.assertIn("macos-15-intel", workflow)
        self.assertIn("provider-semantic-conformance-observation.v1.json", workflow)
        semantic_job = workflow.split("  provider-semantic-conformance:", 1)[1]
        self.assertIn(
            "python -m pip install -r tools/requirements-dev.lock",
            semantic_job,
        )
        self.assertNotIn("--skip-provider-self-conformance", workflow)

    def test_source_shared_selector_is_available_for_the_reconciled_tracked_source(self) -> None:
        cmake = (ROOT / "cmake/FacManProviders.cmake").read_text(encoding="utf-8")
        self.assertIn("FACMAN_PROVIDER_SOURCE_LINKAGE", cmake)
        self.assertNotIn(
            "shared source-provider linkage requires an explicit non-adopted candidate",
            cmake,
        )
        self.assertIn("FACMAN_PROVIDER_SDK_CONSUMPTION_CANDIDATE", cmake)
        self.assertIn("set(FACMAN_UNIVERSAL_LAUNCHER_CORE_TARGET ulk_shared)", cmake)
        self.assertIn("set(FACMAN_UNIVERSAL_SETUP_CORE_TARGET usk_shared)", cmake)

    def test_native_probe_requires_the_input_bound_harness(self) -> None:
        cmake = (ROOT / "tests/native/CMakeLists.txt").read_text(encoding="utf-8")
        self.assertIn(
            "add_executable(\n    facman_provider_semantic_probe",
            cmake,
        )
        self.assertNotIn(
            "facman_native_test(\n    facman_provider_semantic_probe",
            cmake,
        )
        harness = (ROOT / "tools/provider_semantic_conformance.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('"--workspace"', harness)
        self.assertIn('"--mode"', harness)
        self.assertIn('"--linkage"', harness)


if __name__ == "__main__":
    unittest.main()
