# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from tools.package.runtime_identity import require_backend_identity


class PackageRuntimeIdentityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "manifest").mkdir()
        (self.root / "bin").mkdir()
        self.exe = self.root / "bin/facman.exe"
        self.exe.write_bytes(b"explicit-test-executable-not-run")
        self.fields = {"source_revision": "a" * 40, "source_dirty": False,
                       "universal_launcher_revision": "b" * 40,
                       "universal_setup_revision": "c" * 40}
        manifest = dict(self.fields, profile_id="windows_product_x64")
        (self.root / "manifest/package.v1.toml").write_text(
            "".join(f"{k} = {json.dumps(v)}\n" for k, v in manifest.items()), encoding="utf-8")
        (self.root / "manifest/build_info.v1.json").write_text(
            json.dumps({"build_identity": "test-build-a"}), encoding="utf-8")
        (self.root / "manifest/hashes.sha256").write_text(
            "d" * 64 + "  test-fixture\n", encoding="utf-8")
        package = dict(manifest, verified=True, build_matches_package=True,
                       contract_set_matches_build=True, mode="packaged",
                       integrity="sha256_consistent", backend_relative_path="bin/facman.exe",
                       contract_set_sha256="e" * 64, files_verified=1)
        for k, p in (("manifest_sha256", "manifest/package.v1.toml"),
                     ("closure_sha256", "manifest/hashes.sha256"), ("backend_sha256", "bin/facman.exe")):
            package[k] = hashlib.sha256((self.root / p).read_bytes()).hexdigest()
        self.product = {"backend_identity": {"build": dict(self.fields, build_identity="test-build-a"),
                                            "package": package, "contract_set_sha256": "e" * 64}}

    def verify(self, product=None):
        return require_backend_identity(self.root, self.exe, product or self.product)

    def test_consistent_executed_identity_is_admitted(self):
        self.assertEqual(self.verify()["compiled_source_revision"], "a" * 40)

    def test_stale_object_cannot_be_hidden_by_current_manifest(self):
        value = copy.deepcopy(self.product)
        value["backend_identity"]["build"]["source_revision"] = "f" * 40
        with self.assertRaisesRegex(ValueError, "build.source_revision"):
            self.verify(value)

    def test_dirty_source_type_or_provider_drift_refuses(self):
        for key, bad in (("source_dirty", True), ("source_dirty", 0),
                         ("universal_launcher_revision", "f" * 40),
                         ("universal_setup_revision", "f" * 40), ("build_identity", "stale")):
            with self.subTest(key=key, bad=bad):
                value = copy.deepcopy(self.product)
                value["backend_identity"]["build"][key] = bad
                with self.assertRaises(ValueError):
                    self.verify(value)

    def test_unverified_or_missing_contracts_refuse(self):
        for key, bad in (("verified", False), ("verified", 1),
                         ("build_matches_package", False), ("contract_set_matches_build", False),
                         ("contract_set_sha256", None), ("contract_set_sha256", "f" * 64)):
            with self.subTest(key=key):
                value = copy.deepcopy(self.product)
                value["backend_identity"]["package"][key] = bad
                with self.assertRaises(ValueError):
                    self.verify(value)

    def test_self_reported_backend_bytes_must_match_actual_file(self):
        self.exe.write_bytes(b"different bytes")
        with self.assertRaisesRegex(ValueError, "backend_sha256"):
            self.verify()

    def test_package_digest_path_and_count_drift_refuse(self):
        for key, bad in (("profile_id", "other"), ("manifest_sha256", "f" * 64),
                         ("closure_sha256", "f" * 64), ("backend_relative_path", "other.exe"),
                         ("files_verified", 2), ("files_verified", True)):
            with self.subTest(key=key):
                value = copy.deepcopy(self.product)
                value["backend_identity"]["package"][key] = bad
                with self.assertRaises(ValueError):
                    self.verify(value)

    def test_contract_digest_is_typed_and_well_formed(self):
        for bad in (None, 3, "not-a-digest", "A" * 64):
            value = copy.deepcopy(self.product)
            value["backend_identity"]["contract_set_sha256"] = bad
            with self.assertRaises(ValueError):
                self.verify(value)


if __name__ == "__main__":
    unittest.main()
