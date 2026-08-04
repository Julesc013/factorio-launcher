# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from tools import facman_release, release_resolution_check
from tools.release_compiler.canonical import canonical_bytes, domain_digest_value
from tools.release_compiler.compiler import (
    INPUT_FILES,
    CompilerInputs,
    ResolutionFailure,
    diff_resolutions,
    explain,
    load_inputs,
    resolve,
)
from tools.release_compiler.outputs import load_resolution, validate_resolution, write_resolution
from tools.release_compiler.source_observation import (
    from_checkout_observation,
    synthetic_source_observation,
)


ROOT = Path(__file__).resolve().parents[1]
INPUT_ROOT = ROOT / "release" / "index"
TARGETS = (
    "windows_portable_cli_x64",
    "linux_portable_cli_x64",
    "macos_portable_cli_x64",
)


class ReleaseCompilerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.inputs = load_inputs(INPUT_ROOT, ROOT)

    def mutated_inputs(self) -> CompilerInputs:
        return CompilerInputs(
            root=self.inputs.root,
            model=copy.deepcopy(self.inputs.model),
            input_hashes=dict(self.inputs.input_hashes),
        )

    def test_all_reviewed_targets_resolve_and_validate(self) -> None:
        digests = set()
        for target in TARGETS:
            outputs = resolve(self.inputs, target)
            validate_resolution(outputs, ROOT)
            self.assertEqual(set(outputs), {
                "composition",
                "components",
                "paths",
                "entrypoints",
                "authority",
                "compatibility",
                "package_plan",
                "qualification_plan",
                "claims",
                "trace",
                "resolution_set",
                "runtime_metadata",
            })
            self.assertEqual(len(outputs["components"]["components"]), 7)
            self.assertEqual(len(outputs["paths"]["paths"]), 9)
            self.assertFalse(outputs["authority"]["product_authority_granted"])
            self.assertFalse(outputs["qualification_plan"]["qualified"])
            digests.add(outputs["resolution_set"]["root_digest"])
        self.assertEqual(len(digests), len(TARGETS))

    def test_resolution_is_byte_deterministic_and_environment_independent(self) -> None:
        first = resolve(self.inputs, TARGETS[0])
        previous = os.environ.get("FACMAN_RELEASE_TEST_NOISE")
        os.environ["FACMAN_RELEASE_TEST_NOISE"] = "must-not-affect-resolution"
        try:
            second = resolve(self.inputs, TARGETS[0])
        finally:
            if previous is None:
                os.environ.pop("FACMAN_RELEASE_TEST_NOISE", None)
            else:
                os.environ["FACMAN_RELEASE_TEST_NOISE"] = previous
        self.assertEqual(canonical_bytes(first), canonical_bytes(second))

    def test_explicit_source_observation_changes_only_observed_identity(self) -> None:
        first_observation = synthetic_source_observation(self.inputs.model)
        second_observation = copy.deepcopy(first_observation)
        second_observation["canonical_ref"] = "refs/heads/reviewed-candidate"
        core = dict(second_observation)
        core.pop("observation_digest")
        second_observation["observation_digest"] = domain_digest_value(
            "facman.source_observation.v1",
            core,
        )
        first = resolve(self.inputs, TARGETS[0], first_observation)
        second = resolve(self.inputs, TARGETS[0], second_observation)
        self.assertEqual(
            first["composition"]["product"]["reviewed_base_revision"],
            second["composition"]["product"]["reviewed_base_revision"],
        )
        self.assertNotEqual(
            first["resolution_set"]["root_digest"],
            second["resolution_set"]["root_digest"],
        )

    def test_tampered_provider_observation_digest_is_refused(self) -> None:
        observation = synthetic_source_observation(self.inputs.model)
        observation["providers"][0]["observation_digest"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "provider .* digest is invalid"):
            resolve(self.inputs, TARGETS[0], observation)

    def test_passing_checkout_projects_to_path_free_release_source_custody(self) -> None:
        providers = []
        for provider in self.inputs.model["providers"]["provider"]:
            providers.append(
                {
                    "id": provider["id"],
                    "pin": provider["source_revision"],
                    "origin_remote": provider["repository"],
                    "required_ref": "refs/heads/main",
                    "remote_matches_lock": True,
                    "status": "pass",
                    "checkout": {
                        "tree": "3" * 40,
                        "dirty": False,
                    },
                }
            )
        checkout = {
            "schema": "facman.current_checkout_observation.v2",
            "result": {"status": "pass"},
            "source": {
                "head": "1" * 40,
                "tree": "2" * 40,
                "dirty": False,
                "branch": "task/release-candidate",
                "origin_remote": self.inputs.model["product"]["source_repository"],
            },
            "observation_policy": {
                "sha256": "4" * 64,
                "line_ending_profile": {"id": "facman_checkout_lf_v1"},
            },
            "providers": providers,
        }
        observation = from_checkout_observation(checkout, self.inputs.model)
        self.assertTrue(observation["release_eligible"])
        self.assertNotIn("root", observation)
        self.assertEqual(observation["commit"], "1" * 40)
        self.assertEqual(observation["tree"], "2" * 40)

    def test_checkout_projection_refuses_failed_or_forged_source_custody(self) -> None:
        providers = []
        for provider in self.inputs.model["providers"]["provider"]:
            providers.append(
                {
                    "id": provider["id"],
                    "pin": provider["source_revision"],
                    "origin_remote": provider["repository"],
                    "required_ref": "refs/heads/main",
                    "remote_matches_lock": True,
                    "status": "pass",
                    "checkout": {"tree": "3" * 40, "dirty": False},
                }
            )
        checkout = {
            "schema": "facman.current_checkout_observation.v2",
            "result": {"status": "pass"},
            "source": {
                "head": "1" * 40,
                "tree": "2" * 40,
                "dirty": False,
                "branch": "task/release-candidate",
                "origin_remote": self.inputs.model["product"]["source_repository"],
            },
            "observation_policy": {
                "sha256": "4" * 64,
                "line_ending_profile": {"id": "facman_checkout_lf_v1"},
            },
            "providers": providers,
        }

        for field, value, message in (
            ("status", "fail", "did not pass"),
            ("remote_matches_lock", False, "remote does not match"),
            ("origin_remote", "https://evil.example/provider.git", "origin remote differs"),
        ):
            forged = copy.deepcopy(checkout)
            forged["providers"][0][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, message):
                from_checkout_observation(forged, self.inputs.model)

        forged_source = copy.deepcopy(checkout)
        forged_source["source"]["origin_remote"] = "https://evil.example/facman.git"
        with self.assertRaisesRegex(ValueError, "source origin remote differs"):
            from_checkout_observation(forged_source, self.inputs.model)

    def test_resolution_root_is_domain_separated_and_acyclic(self) -> None:
        outputs = resolve(self.inputs, TARGETS[0])
        resolution_set = outputs["resolution_set"]
        self.assertEqual(len(resolution_set["records"]), 10)
        for key in (
            "composition",
            "components",
            "paths",
            "entrypoints",
            "authority",
            "compatibility",
            "package_plan",
            "qualification_plan",
            "claims",
            "trace",
        ):
            self.assertNotIn("root_digest", outputs[key])
        core = dict(resolution_set)
        actual = core.pop("root_digest")
        self.assertEqual(
            actual,
            domain_digest_value("facman.release_resolution_set.v1", core),
        )

    def test_runtime_metadata_is_a_bounded_projection(self) -> None:
        runtime = resolve(self.inputs, TARGETS[0])["runtime_metadata"]
        self.assertNotIn("input_hashes", runtime)
        self.assertNotIn("trace", runtime)
        self.assertNotIn("paths", runtime)
        self.assertNotIn("package_plan", runtime)
        self.assertIn("resolution_root_digest", runtime)
        self.assertIn("provider_locks", runtime)

    def test_cli_resolve_refuses_implicit_synthetic_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            error = io.StringIO()
            with redirect_stderr(error):
                result = facman_release.main(
                    [
                        "resolve",
                        "--target",
                        TARGETS[0],
                        "--output",
                        str(Path(temporary) / "resolution"),
                    ]
                )
        self.assertEqual(result, 1)
        self.assertIn("requires --source-observation", error.getvalue())

    def test_input_byte_change_changes_resolution_digest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "index"
            copied.mkdir()
            for filename in INPUT_FILES:
                shutil.copy2(INPUT_ROOT / filename, copied / filename)
            support = copied / "support.v2.toml"
            support.write_text(
                support.read_text(encoding="utf-8").replace(
                    'status = "package_preview"',
                    'status = "experimental_preview"',
                    1,
                ),
                encoding="utf-8",
            )
            changed = load_inputs(copied, ROOT)
            original_digest = resolve(self.inputs, TARGETS[0])["resolution_set"]["root_digest"]
            changed_digest = resolve(changed, TARGETS[0])["resolution_set"]["root_digest"]
            self.assertNotEqual(original_digest, changed_digest)

    def test_missing_capability_reports_deterministic_minimal_conflict(self) -> None:
        inputs = self.mutated_inputs()
        target = inputs.model["targets"]["target"][0]
        target["capabilities"].remove("static_provider_linkage")
        with self.assertRaises(ResolutionFailure) as caught:
            resolve(inputs, str(target["id"]))
        diagnostic = caught.exception.diagnostics[0]
        self.assertEqual(diagnostic["code"], "missing_target_capability")
        self.assertEqual(
            diagnostic["constraints"],
            [
                "component:facman_cli",
                "target:windows_portable_cli_x64",
                "capability:static_provider_linkage",
            ],
        )

    def test_dependency_cycle_fails_closed(self) -> None:
        inputs = self.mutated_inputs()
        components = {row["id"]: row for row in inputs.model["components"]["component"]}
        components["universal_launcher"]["dependencies"] = ["factorio_binding"]
        with self.assertRaises(ResolutionFailure) as caught:
            resolve(inputs, TARGETS[0])
        self.assertIn("component_cycle", {item["code"] for item in caught.exception.diagnostics})

    def test_overlapping_path_ownership_fails_closed(self) -> None:
        inputs = self.mutated_inputs()
        components = {row["id"]: row for row in inputs.model["components"]["component"]}
        components["legal_notices"]["path"][0]["destination"] = "contracts/schema/foreign"
        with self.assertRaises(ResolutionFailure) as caught:
            resolve(inputs, TARGETS[0])
        self.assertIn(
            "overlapping_path_ownership",
            {item["code"] for item in caught.exception.diagnostics},
        )

    def test_authority_ceiling_fails_closed(self) -> None:
        inputs = self.mutated_inputs()
        artifact = inputs.model["artifacts"]["artifact"][0]
        artifact["authority_ceiling"].remove("setup_mutation")
        with self.assertRaises(ResolutionFailure) as caught:
            resolve(inputs, TARGETS[0])
        self.assertIn("authority_ceiling_exceeded", {item["code"] for item in caught.exception.diagnostics})

    def test_explain_records_selection_and_exclusion(self) -> None:
        outputs = resolve(self.inputs, TARGETS[0])
        selected = explain(outputs, "universal_setup")
        excluded = explain(outputs, "facman_daemon")
        self.assertEqual(selected["events"][0]["action"], "select")
        self.assertEqual(excluded["events"][0]["action"], "exclude")

    def test_resolution_directory_round_trip_and_tamper_refusal(self) -> None:
        outputs = resolve(self.inputs, TARGETS[0])
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "resolution"
            write_resolution(destination, outputs)
            loaded = load_resolution(destination)
            self.assertEqual(canonical_bytes(outputs), canonical_bytes(loaded))
            paths_file = destination / "resolved-paths.v1.json"
            paths = json.loads(paths_file.read_text(encoding="utf-8"))
            paths["paths"][0]["destination"] = "tampered/path"
            paths_file.write_text(json.dumps(paths), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "content digest"):
                load_resolution(destination)

    def test_resolution_output_refuses_nonempty_destination(self) -> None:
        outputs = resolve(self.inputs, TARGETS[0])
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "resolution"
            destination.mkdir()
            (destination / "foreign.txt").write_text("foreign", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "absent or empty"):
                write_resolution(destination, outputs)

    def test_diff_reports_target_specific_path_change(self) -> None:
        windows = resolve(self.inputs, TARGETS[0])
        linux = resolve(self.inputs, TARGETS[1])
        left = windows["components"] | windows["paths"]
        right = linux["components"] | linux["paths"]
        difference = diff_resolutions(left, right)
        self.assertTrue(difference["changed"])
        self.assertIn("facman_cli/facman_cli_binary", difference["paths"]["changed"])

    def test_cli_validate_and_explain(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            result = facman_release.main(["validate"])
        self.assertEqual(result, 0)
        self.assertIn("valid inputs", output.getvalue())
        output = io.StringIO()
        with redirect_stdout(output):
            result = facman_release.main([
                "explain",
                "--target",
                TARGETS[0],
                "--component",
                "facman_daemon",
            ])
        self.assertEqual(result, 0)
        self.assertEqual(json.loads(output.getvalue())["events"][0]["action"], "exclude")

    def test_strict_release_resolution_validator(self) -> None:
        self.assertEqual(release_resolution_check.main(), 0)


if __name__ == "__main__":
    unittest.main()
