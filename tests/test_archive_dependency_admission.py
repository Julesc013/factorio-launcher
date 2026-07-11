# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import hashlib
import json
import tomllib
import unittest
from pathlib import Path

from tools.validators.release import check_dependency_lock

ROOT = Path(__file__).resolve().parents[1]
MINIZ = ROOT / "external" / "miniz"


class ArchiveDependencyAdmissionTests(unittest.TestCase):
    def test_dependency_lock_and_sbom_pin_exact_miniz_release(self) -> None:
        self.assertEqual(check_dependency_lock.validate(), [])
        with (ROOT / "release" / "index" / "dependency_lock.v1.toml").open("rb") as handle:
            lock = tomllib.load(handle)
        miniz = next(item for item in lock["component"] if item["id"] == "miniz")
        self.assertEqual(miniz["version"], "3.1.2")
        self.assertEqual(miniz["pin"], "77d0dce8627735138c51770d1799a1ef48f2117d")
        self.assertEqual(
            miniz["source_archive_sha256"],
            "f0446d863f9c19926ad9483c523fdc42e42b8d4a6a431d27e09d49c79a140d9a",
        )
        self.assertEqual(miniz["transitive_runtime_dependencies"], [])
        self.assertFalse(miniz["runtime_network"])

        sbom = json.loads(
            (ROOT / "release" / "index" / "sbom.components.v1.json").read_text(
                encoding="utf-8"
            )
        )
        sbom_miniz = next(item for item in sbom["components"] if item["id"] == "miniz")
        self.assertEqual(sbom_miniz["commit"], miniz["pin"])
        self.assertFalse(sbom["publisher_authenticity_proven"])

    def test_vendored_release_files_match_reviewed_hashes(self) -> None:
        expected = {
            "miniz.c": "e2c1aeb66eef9191d8c3feb164db2def2335a61d039bf04ed849f6b042433b30",
            "miniz.h": "b53b62ed122e559b8f679e3cb787a0b0035fe87a58f909da0e44931678f4e85f",
            "LICENSE": "0115478d567121238cf6cc1c0c361926cf07a49d9e4c9e66da97fac6a01646b3",
        }
        for name, digest in expected.items():
            self.assertEqual(hashlib.sha256(MINIZ.joinpath(name).read_bytes()).hexdigest(), digest)
        self.assertIn("Permission is hereby granted", MINIZ.joinpath("LICENSE").read_text())
        self.assertEqual(
            {path.name for path in (ROOT / "external").iterdir()},
            {"CMakeLists.txt", "README.md", "miniz", "picojson"},
        )
        attributes = ROOT.joinpath(".gitattributes").read_text(encoding="utf-8")
        self.assertIn("external/miniz/LICENSE binary", attributes)

    def test_upstream_api_exposes_required_archive_capability_floor(self) -> None:
        header = MINIZ.joinpath("miniz.h").read_text(encoding="utf-8")
        for anchor in [
            "MZ_ZIP_FLAG_WRITE_ZIP64",
            "m_is_encrypted",
            "m_external_attr",
            "mz_zip_reader_extract_iter_read",
            "mz_zip_writer_add_read_buf_callback",
            "mz_zip_validate_archive",
            "MZ_ZIP_CRC_CHECK_FAILED",
            "optional descriptor following the compressed data",
        ]:
            self.assertIn(anchor, header)
        source = MINIZ.joinpath("miniz.c").read_text(encoding="utf-8")
        self.assertIn("has_data_descriptor", source)
        self.assertIn("zip64_total_num_of_disks != 1U", source)

    def test_build_graph_uses_source_only_private_static_target(self) -> None:
        external_cmake = ROOT.joinpath("external/CMakeLists.txt").read_text(encoding="utf-8")
        tests_cmake = ROOT.joinpath("tests/native/CMakeLists.txt").read_text(encoding="utf-8")
        self.assertIn("add_library(miniz_static STATIC miniz/miniz.c)", external_cmake)
        self.assertIn("facman_native_test(miniz_dependency_smoke", tests_cmake)
        forbidden_suffixes = {".dll", ".exe", ".lib", ".a", ".so", ".dylib"}
        self.assertFalse(
            any(path.suffix.lower() in forbidden_suffixes for path in MINIZ.rglob("*"))
        )


if __name__ == "__main__":
    unittest.main()
