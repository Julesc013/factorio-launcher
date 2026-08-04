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
from contextlib import redirect_stdout
from pathlib import Path

from tools import facman_release, release_resolution_check
from tools.release_compiler.canonical import canonical_bytes
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
            })
            self.assertEqual(len(outputs["components"]["components"]), 7)
            self.assertEqual(len(outputs["paths"]["paths"]), 9)
            self.assertFalse(outputs["authority"]["product_authority_granted"])
            self.assertFalse(outputs["qualification_plan"]["qualified"])
            digests.add(outputs["composition"]["resolution_digest"])
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
            original_digest = resolve(self.inputs, TARGETS[0])["composition"]["resolution_digest"]
            changed_digest = resolve(changed, TARGETS[0])["composition"]["resolution_digest"]
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
