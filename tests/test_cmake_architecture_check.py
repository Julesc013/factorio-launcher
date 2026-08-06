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

    def test_installed_provider_headers_use_the_validated_include_root(self) -> None:
        install = (
            Path(cmake_architecture_check.__file__).resolve().parents[1]
            / "cmake"
            / "FacManInstall.cmake"
        ).read_text(encoding="utf-8")
        self.assertIn("${FACMAN_UNIVERSAL_LAUNCHER_INCLUDE_DIR}/ulk", install)
        self.assertNotIn("${FLAUNCH_UNIVERSAL_LAUNCHER_ROOT}/include/ulk", install)


if __name__ == "__main__":
    unittest.main()
