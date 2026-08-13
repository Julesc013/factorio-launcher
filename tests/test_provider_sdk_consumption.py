# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import jsonschema

from tools import provider_conformance
from tools import provider_sdk_consumption as consumption


ROOT = Path(__file__).resolve().parents[1]


class ProviderSdkConsumptionTests(unittest.TestCase):
    def test_workflow_preserves_nested_phase_a_failure_logs(self) -> None:
        workflow = (
            ROOT / ".github/workflows/provider-sdk-consumption.yml"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "facman-provider-sdk-consumption-evidence/"
            "provider-input-phase-a/logs/*.log",
            workflow,
        )

    def test_phase_a_classification_distinguishes_proof_from_rehearsal(self) -> None:
        result, skips = consumption._classify_phase_a(
            {"result": "bounded_provider_input_conformance_pass"},
            skip_provider_self_conformance=False,
        )
        self.assertEqual(result, "provider_sdk_consumption_pass")
        self.assertEqual(skips, [])

        result, skips = consumption._classify_phase_a(
            {"result": "bounded_provider_input_development_rehearsal"},
            skip_provider_self_conformance=True,
        )
        self.assertEqual(result, "provider_sdk_consumption_development_rehearsal")
        self.assertEqual(skips, ["provider_self_conformance"])

        with self.assertRaisesRegex(ValueError, "Phase-A result is inconsistent"):
            consumption._classify_phase_a(
                {"result": "bounded_provider_input_development_rehearsal"},
                skip_provider_self_conformance=False,
            )

    def test_candidate_lock_is_distinct_non_authorizing_and_exact(self) -> None:
        sources = []
        for index, spec in enumerate(provider_conformance.PROVIDERS, start=1):
            sources.append(
                provider_conformance.ProviderSource(
                    spec=spec,
                    root=ROOT,
                    commit=str(index) * 40,
                    tree=str(index + 2) * 40,
                )
            )
        tracked = {
            item.spec.provider_id: {"pin": "9" * 40} for item in sources
        }
        text = provider_conformance.candidate_lock_text(
            sources, tracked, candidate_class="sdk_consumption"
        )
        self.assertIn('schema = "facman.provider_sdk_consumption_lock.v1"', text)
        self.assertIn("conformance_only = false", text)
        self.assertIn("sdk_consumption_candidate = true", text)
        self.assertIn("candidate_not_adopted = true", text)
        self.assertIn("release_eligible = false", text)
        self.assertTrue(
            all(f"{key} = false" in text for key in provider_conformance.AUTHORITY)
        )

    def test_install_inventory_is_path_independent_and_detects_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "bin").mkdir()
            payload = root / "bin/facman"
            payload.write_bytes(b"candidate")
            first = consumption._inventory(root)
            self.assertEqual(first["file_count"], 1)
            payload.write_bytes(b"changed")
            second = consumption._inventory(root)
            self.assertNotEqual(first["sha256"], second["sha256"])

    def test_runtime_filter_excludes_facman_own_runtime(self) -> None:
        files = [Path("bin/flb_factorio.dll"), Path("bin/ulk.dll"), Path("bin/usk.dll")]
        selected = consumption._provider_runtime_files(files, {"ULK.DLL", "usk.dll"})
        self.assertEqual([path.name for path in selected], ["ulk.dll", "usk.dll"])

    def test_schema_requires_false_authority_and_seven_modes(self) -> None:
        schema = json.loads(
            (ROOT / "contracts/schema/release/provider_sdk_consumption.v1.schema.json")
            .read_text(encoding="utf-8")
        )
        validator = jsonschema.Draft202012Validator(schema)
        authority = dict(provider_conformance.AUTHORITY)
        mode_names = [mode.name for mode in consumption.semantics.MODES]
        mode_records = [
            {
                "name": mode.name,
                "provider_mode": mode.provider_mode,
                "linkage": mode.linkage,
                "runtime_closure": mode.runtime,
                "raw_probe_sha256": "a" * 64,
                "normalized_semantic_sha256": "b" * 64,
                "install": {
                    "file_count": 1,
                    "sha256": "c" * 64,
                    "build_identity_sha256": "d" * 64,
                    "runtime_file_count": 0,
                    "runtime_sha256": "e" * 64,
                },
                "result": "pass",
            }
            for mode in consumption.semantics.MODES
        ]
        value = {
            "schema": consumption.SCHEMA,
            "observed_at_utc": "2026-08-06T00:00:00+00:00",
            "result": "provider_sdk_consumption_pass",
            "facman": {"commit": "1" * 40, "tree": "2" * 40},
            "platform": {"system": "Linux", "architecture": "x86_64", "runner_os": "Linux", "runner_arch": "X64"},
            "providers": [
                {"id": "universal_launcher", "commit": "3" * 40, "tree": "4" * 40, "remote": "https://example.invalid/ulk.git", "canonical_main_ref": "refs/heads/main"},
                {"id": "universal_setup", "commit": "5" * 40, "tree": "6" * 40, "remote": "https://example.invalid/usk.git", "canonical_main_ref": "refs/heads/main"},
            ],
            "provider_input_observation": {"path": "phase-a.json", "sha256": "7" * 64},
            "tracked_lock_records": {
                "workspace": {"path": "workspace.toml", "sha256": "8" * 64},
                "release_provider": {"path": "providers.toml", "sha256": "9" * 64},
            },
            "candidate_lock": {
                "sha256": "a" * 64,
                "sdk_consumption_candidate": True,
                "candidate_not_adopted": True,
                "release_eligible": False,
                "tracked_lock_mutated": False,
            },
            "modes": mode_records,
            "normalized_semantic_sha256": "b" * 64,
            "negative_controls": {
                name: "refused"
                for name in (
                    "ambient_sdk_fallback",
                    "candidate_lock_without_candidate_mode",
                    "conformance_mode_with_sdk_lock",
                    "missing_shared_runtime",
                    "partial_sdk_tree",
                    "stale_relocation_metadata",
                    "undeclared_runtime_dependency",
                )
            },
            "required_skips": [],
            "source_mode_rollback_proven": True,
            "installed_modes_source_independent": True,
            "tracked_lock_mutated": False,
            "provider_adoption": False,
            "provider_repin": False,
            "release_eligible": False,
            "authority": authority,
        }
        validator.validate(value)
        self.assertEqual(mode_names, [item["name"] for item in value["modes"]])
        value["result"] = "provider_sdk_consumption_development_rehearsal"
        value["required_skips"] = ["provider_self_conformance"]
        validator.validate(value)
        value["result"] = "provider_sdk_consumption_pass"
        self.assertTrue(list(validator.iter_errors(value)))
        value["required_skips"] = []
        value["authority"]["factorio_execution"] = True
        self.assertTrue(list(validator.iter_errors(value)))


if __name__ == "__main__":
    unittest.main()
