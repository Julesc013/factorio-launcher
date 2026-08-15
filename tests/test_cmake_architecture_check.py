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

    def test_project_and_documentation_readmes_have_distinct_install_names(self) -> None:
        root = Path(cmake_architecture_check.__file__).resolve().parents[1]
        install = (root / "cmake" / "FacManInstall.cmake").read_text(
            encoding="utf-8"
        )
        pipeline = (root / "tools" / "package" / "pipeline.py").read_text(
            encoding="utf-8"
        )

        self.assertIn("RENAME PROJECT-README.md", install)
        self.assertIn(
            'install_root / "share" / "doc" / "facman" / "PROJECT-README.md"',
            pipeline,
        )

    def test_operator_execution_authority_is_independently_default_off(self) -> None:
        root = Path(cmake_architecture_check.__file__).resolve().parents[1]
        options = (root / "cmake" / "FacManOptions.cmake").read_text(
            encoding="utf-8"
        )

        self.assertIn("set(_facman_play_evidence_default OFF)", options)
        self.assertNotIn(
            "set(_facman_play_evidence_default ${_facman_tests_default})", options
        )
        self.assertEqual(cmake_architecture_check.validate(), [])

    def test_engineering_harness_does_not_embed_the_source_route_path(self) -> None:
        root = Path(cmake_architecture_check.__file__).resolve().parents[1]
        native_cmake = (root / "tests/native/CMakeLists.txt").read_text(
            encoding="utf-8"
        )
        harness = (
            root / "tests/native/facman_engineering_play_harness.cpp"
        ).read_text(encoding="utf-8")

        self.assertNotIn("FACMAN_ENGINEERING_ROUTE_RECORD_PATH", native_cmake)
        self.assertIn('required("--route-record")', harness)
        self.assertIn(
            "route_record_valid(options.route_record, route_record_sha256)", harness
        )


if __name__ == "__main__":
    unittest.main()
