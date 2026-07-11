# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools import package_pipeline_check
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


if __name__ == "__main__":
    unittest.main()
