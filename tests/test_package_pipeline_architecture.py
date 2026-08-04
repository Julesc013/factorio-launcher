# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools import package_pipeline_check, package_reproducibility_proof
from tools.package import archive, pipeline, verification
from tools.release_compiler.outputs import load_runtime_projection
from tools.release_compiler.compiler import load_inputs
from tools.release_compiler.source_observation import synthetic_source_observation


class PackagePipelineArchitectureTests(unittest.TestCase):
    def test_package_pipeline_contract(self) -> None:
        self.assertEqual(package_pipeline_check.main(), 0)

    def test_zip_archives_are_byte_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = root / "payload"
            payload.mkdir()
            (payload / "z.txt").write_text("z\n", encoding="utf-8")
            (payload / "a.txt").write_text("a\n", encoding="utf-8")
            first = archive.write(payload, root / "first.zip", "portable_zip", "2026-01-02T03:04:05Z")
            second = archive.write(payload, root / "second.zip", "portable_zip", "2026-01-02T03:04:05Z")
            verification.require_identical(first, second)

    def test_package_tree_snapshot_is_stable_and_detects_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "nested").mkdir()
            (root / "nested" / "payload.txt").write_text("one\n", encoding="utf-8")
            first = package_reproducibility_proof.tree_snapshot(root)
            self.assertEqual(
                package_reproducibility_proof.snapshot_digest(first),
                package_reproducibility_proof.snapshot_digest(dict(first)),
            )
            (root / "nested" / "payload.txt").write_text("two\n", encoding="utf-8")
            second = package_reproducibility_proof.tree_snapshot(root)
            self.assertNotEqual(first, second)

    def test_first_family_package_embeds_bounded_runtime_projection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package_root = Path(temporary) / "package"
            package_root.mkdir()
            pipeline.write_release_resolution_metadata(
                package_root,
                "windows_portable_cli_x64",
            )
            metadata_root = package_root / "manifest" / "resolution"
            outputs = load_runtime_projection(metadata_root, pipeline.ROOT)
            self.assertEqual(
                outputs["runtime_metadata"]["target_id"],
                "windows_portable_cli_x64",
            )
            self.assertFalse(outputs["runtime_metadata"]["release_eligible"])
            self.assertEqual(
                {path.name for path in metadata_root.iterdir()},
                {
                    "release-resolution-set.v1.json",
                    "runtime-release-metadata.v1.json",
                },
            )

    def test_release_oriented_package_refuses_synthetic_source_observation(self) -> None:
        inputs = load_inputs(pipeline.ROOT / "release" / "index", pipeline.ROOT)
        observation = synthetic_source_observation(inputs.model)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "source-observation.json"
            path.write_text(json.dumps(observation), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "clean release-eligible"):
                pipeline.package_source_observation(
                    "windows_portable_cli_x64",
                    path,
                    allow_dirty=False,
                )
            loaded = pipeline.package_source_observation(
                "windows_portable_cli_x64",
                path,
                allow_dirty=True,
            )
        self.assertIsNotNone(loaded)
        self.assertFalse(loaded["release_eligible"])

    def test_reproducibility_artifact_filter_excludes_ownership_metadata(self) -> None:
        self.assertEqual(
            package_reproducibility_proof.archive_suffix(Path("facman.zip")),
            ".zip",
        )
        self.assertEqual(
            package_reproducibility_proof.archive_suffix(Path("facman.tar.gz")),
            ".tar.gz",
        )
        self.assertEqual(
            package_reproducibility_proof.archive_suffix(
                Path(".facman-owned-output.v1.json")
            ),
            ".json",
        )


if __name__ == "__main__":
    unittest.main()
