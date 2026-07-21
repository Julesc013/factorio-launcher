# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools import cmake_architecture_check


class CMakeArchitectureCheckTests(unittest.TestCase):
    def test_source_files_survive_build_named_ancestor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "build" / "clean-repro" / "factorio-launcher"
            source = root / "runtime" / "core" / "CMakeLists.txt"
            generated = root / "build" / "native-smoke" / "CMakeLists.txt"
            source.parent.mkdir(parents=True)
            generated.parent.mkdir(parents=True)
            source.write_text("add_library(facman_core)\n", encoding="utf-8")
            generated.write_text("generated\n", encoding="utf-8")

            discovered = cmake_architecture_check.source_cmake_files(root)

        self.assertEqual(discovered, [source])


if __name__ == "__main__":
    unittest.main()
