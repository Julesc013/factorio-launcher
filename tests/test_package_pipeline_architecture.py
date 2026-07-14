# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools import package_pipeline_check, package_reproducibility_proof
from tools.package import archive, verification


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
