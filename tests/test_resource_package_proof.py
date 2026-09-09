# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT
"""Resource proof oracles, bounded failures and optional actual native fixtures."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock
import zipfile

from tools import json_contract
from tools import resource_package_cases as cases
from tools import resource_package_proof as proof


class ResourcePackageProofTests(unittest.TestCase):
    def test_package_path_rejects_unrelated_equal_bytes_and_hardlinks(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            expected = root / "expected.resources"
            expected.write_bytes(b"exact bytes")
            cases.require_package_path(str(expected), expected)
            other = root / "other.resources"
            other.write_bytes(expected.read_bytes())
            with self.assertRaisesRegex(ValueError, "actual relocated"):
                cases.require_package_path(str(other), expected)
            linked = root / "hardlink.resources"
            os.link(expected, linked)
            self.assertTrue(expected.samefile(linked))
            with self.assertRaisesRegex(ValueError, "actual relocated"):
                cases.require_package_path(str(linked), expected)

    def test_package_path_equal_spellings_still_require_same_file_object(self):
        with tempfile.TemporaryDirectory() as temporary:
            left, right = (Path(temporary) / name for name in ("left.resources", "right.resources"))
            left.write_bytes(b"equal bytes")
            right.write_bytes(left.read_bytes())
            self.assertFalse(left.samefile(right))
            # Model name equality independently of the actual filesystem identity.
            with mock.patch.object(Path, "__eq__", return_value=True):
                with self.assertRaisesRegex(ValueError, "different object"):
                    cases.require_package_path(str(left), right)

    def test_package_path_rejects_relative_dot_parent_and_reparse_components(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            expected = root / "pack.resources"
            expected.write_bytes(b"exact bytes")
            with self.assertRaisesRegex(ValueError, "absolute"):
                cases.require_package_path("pack.resources", expected)
            with self.assertRaisesRegex(ValueError, "dot-parent"):
                cases.require_package_path(str(root / "unused" / ".." / expected.name), expected)
            original = Path.lstat
            def observed(path, *args, **kwargs):
                if path == root:
                    return SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x400)
                return original(path, *args, **kwargs)
            with mock.patch.object(Path, "lstat", observed), self.assertRaisesRegex(ValueError, "reparse"):
                cases.require_package_path(str(expected), expected)

    @unittest.skipUnless(sys.platform == "win32", "unsupported: Windows short-path spelling")
    def test_package_path_accepts_actual_windows_short_spelling(self):
        import ctypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetShortPathNameW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint]
        kernel.GetShortPathNameW.restype = ctypes.c_uint
        with tempfile.TemporaryDirectory(prefix="facman canonical package ") as temporary:
            expected = Path(temporary) / "resource package with spaces.resources"
            expected.write_bytes(b"exact bytes")
            buffer = ctypes.create_unicode_buffer(32768)
            length = kernel.GetShortPathNameW(str(expected), buffer, len(buffer))
            self.assertGreater(length, 0)
            self.assertLess(length, len(buffer))
            actual = Path(buffer.value)
            if actual == expected:
                self.skipTest("unsupported: 8.3 names are disabled on the temporary volume")
            self.assertTrue(actual.samefile(expected))
            self.assertNotEqual(actual, expected)
            cases.require_package_path(str(actual), expected)
            cases.require_package_path(str(expected), actual)

    def test_zip_oracle_includes_internal_manifest_and_exact_payload(self):
        with tempfile.TemporaryDirectory() as temporary:
            pack = Path(temporary) / "foreign.resources"
            cases.foreign_pack(pack)
            oracle = cases.zip_oracle(pack)
            self.assertEqual(oracle["entries"], ["content/proof-foreign.txt"])
            self.assertEqual(set(oracle["members"]), {cases.MANIFEST, "content/proof-foreign.txt"})
            with zipfile.ZipFile(pack) as archive:
                for path, expected in oracle["members"].items():
                    data = archive.read(path)
                    self.assertEqual(expected, {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()})

    def test_zip_oracle_refuses_manifest_digest_corruption(self):
        with tempfile.TemporaryDirectory() as temporary:
            original, corrupt = (Path(temporary) / name for name in ("original.zip", "corrupt.zip"))
            cases.foreign_pack(original)
            with zipfile.ZipFile(original) as source, zipfile.ZipFile(corrupt, "x") as target:
                for name in source.namelist():
                    data = source.read(name)
                    if name == cases.MANIFEST:
                        value = json.loads(data)
                        value["entries"][0]["sha256"] = "0" * 64
                        data = json.dumps(value).encode()
                    target.writestr(name, data)
            with self.assertRaisesRegex(ValueError, "member mismatch"):
                cases.zip_oracle(corrupt)

    def test_unsafe_or_colliding_zip_members_refuse_without_extraction(self):
        with tempfile.TemporaryDirectory() as temporary:
            for index, names in enumerate((("../escape.txt",), ("A.txt", "a.txt"))):
                path = Path(temporary) / f"invalid-{index}.zip"
                with zipfile.ZipFile(path, "x") as archive:
                    for name in names:
                        archive.writestr(name, b"test")
                with self.assertRaisesRegex(ValueError, "unsafe|colliding"):
                    cases.zip_oracle(path)
            self.assertFalse((Path(temporary).parent / "escape.txt").exists())

    def test_inventory_and_copy_bind_files_modes_and_empty_directories(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            (source / "empty").mkdir(parents=True)
            (source / "data").write_bytes(b"original")
            before = cases.snapshot(source)
            cases.copy_package(source, root / "copy", before)
            self.assertEqual(cases.snapshot(root / "copy"), before)
            self.assertEqual(cases.snapshot(source), before)
            with self.assertRaisesRegex(ValueError, "already exists"):
                cases.copy_package(source, root / "copy", before)

    def test_copy_refuses_source_drift_and_retains_partial_destination(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            (source / "data").write_bytes(b"original")
            before = cases.snapshot(source)
            (source / "data").write_bytes(b"replaced")
            with self.assertRaisesRegex(ValueError, "source changed"):
                cases.copy_package(source, root / "copy", before)
            self.assertEqual((root / "copy/data").read_bytes(), b"replaced")
            self.assertEqual((source / "data").read_bytes(), b"replaced")

    def test_reparse_observation_refuses_before_read(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "data"
            path.write_bytes(b"sentinel")
            original = Path.lstat

            def observed(candidate, *args, **kwargs):
                if candidate == path:
                    return SimpleNamespace(st_mode=stat.S_IFREG, st_file_attributes=0x400)
                return original(candidate, *args, **kwargs)

            with mock.patch.object(Path, "lstat", observed), self.assertRaisesRegex(ValueError, "reparse"):
                cases.file_bytes(path)

    def driver(self, root):
        work = root / "work"
        work.mkdir()
        receipt = {"commands": [], "artifacts": []}
        return proof.Driver(work, receipt, root), receipt

    def test_failed_child_retains_raw_stdout_stderr_and_exit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            driver, receipt = self.driver(root)
            code = "import sys; print('raw stdout'); print('raw stderr',file=sys.stderr); sys.exit(7)"
            with self.assertRaisesRegex(ValueError, "command failed"):
                driver.raw("failed", Path(sys.executable), ["-c", code])
            command = receipt["commands"][0]
            self.assertEqual(command["exit_code"], 7)
            self.assertIn(b"raw stdout", (root / command["stdout"]).read_bytes())
            self.assertIn(b"raw stderr", (root / command["stderr"]).read_bytes())
            for artifact in receipt["artifacts"]:
                data = (root / artifact["path"]).read_bytes()
                self.assertEqual((artifact["bytes"], artifact["sha256"]),
                                 (len(data), hashlib.sha256(data).hexdigest()))

    def test_timeout_retains_raw_files_and_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            driver, receipt = self.driver(root)
            with mock.patch.object(proof, "COMMAND_TIMEOUT", 0.1):
                with self.assertRaisesRegex(ValueError, "command failed"):
                    driver.raw("timeout", Path(sys.executable), ["-c", "import time; time.sleep(4)"])
            self.assertTrue(receipt["commands"][0]["timed_out"])
            self.assertTrue(all((root / row["path"]).is_file() for row in receipt["artifacts"]))

    def test_output_limit_retains_bounded_prefix_and_fails_even_zero_exit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            driver, receipt = self.driver(root)
            with mock.patch.object(proof, "LOG_LIMIT", 128):
                with self.assertRaisesRegex(ValueError, "command failed"):
                    driver.raw("excess", Path(sys.executable), ["-c", "import sys; sys.stdout.write('X'*4096)"])
            command = receipt["commands"][0]
            self.assertTrue(command["output_limit_exceeded"])
            self.assertEqual((root / command["stdout"]).read_bytes(), b"X" * 128)

    def test_typed_error_followed_by_wrong_exit_is_not_a_refusal(self):
        with tempfile.TemporaryDirectory() as temporary:
            driver, receipt = self.driver(Path(temporary))
            payload = {"schema": "facman.transport_response.v2", "error": {"code": "resource_failure"}}
            code = "import sys;print(" + repr(json.dumps(payload)) + ");sys.exit(7)"
            with self.assertRaisesRegex(ValueError, "typed resource failure"):
                driver.refusal("wrong_exit", Path(sys.executable), ["-c", code])
            self.assertEqual(receipt["commands"][0]["exit_code"], 7)

    def test_evidence_overlap_or_missing_owner_refuses_before_writes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaisesRegex(ValueError, "overlaps"):
                proof.prepare(root / "evidence.json", root)
            with mock.patch.object(proof.development_layout, "MARKER_NAME", ".missing-proof-marker"):
                with self.assertRaisesRegex(ValueError, "marker-owned"):
                    proof.prepare(root / "evidence.json", root / "package")
            self.assertEqual(list(root.iterdir()), [])
            with self.assertRaisesRegex(ValueError, "filename stem budget"):
                proof.prepare(root / ("x" * 97 + ".json"), root / "package")

    def test_prepare_accepts_exactly_bound_explicit_task_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task_root = root / "explicit-candidate-task"
            package_root = root / "package"
            package_root.mkdir()
            proof.development_layout.ensure_task_root(
                task_root, proof.ROOT, "product-candidate-test"
            )
            work, owner = proof.prepare(
                task_root / "evidence" / "resource-package.v1.json", package_root
            )
            self.assertEqual(owner["root"], str(task_root.resolve()))
            self.assertTrue(work.is_dir())
            marker = json.loads(
                (task_root / proof.development_layout.MARKER_NAME).read_text(encoding="utf-8")
            )
            self.assertEqual(marker["canonical_path"], str(task_root.resolve()))

    def test_source_identity_does_not_trust_github_sha_override(self):
        expected = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=proof.ROOT, text=True).strip()
        with mock.patch.dict(os.environ, {"GITHUB_SHA": "f" * 40}):
            self.assertEqual(proof.source_identity()["source_revision"], expected)

    def test_export_inventory_rejects_extra_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / cases.MARKER).write_bytes(b"schema=facman.archive_staging.v1\n")
            (root / "foreign").write_bytes(b"unexpected")
            with self.assertRaisesRegex(ValueError, "exported files"):
                cases.exported_inventory(root, {"members": {}})

    @unittest.skipUnless(os.environ.get("FACMAN_RESOURCE_PROOF_FIXTURE") and
                         os.environ.get("FACMAN_RESOURCE_PROOF_CLI"), "optional: supplementary native fixture replay; produced-package proofs are mandatory in candidate workflow")
    def test_actual_native_fixture_both_modes_with_closed_receipt(self):
        platform = "windows" if os.name == "nt" else "macos" if sys.platform == "darwin" else "linux"
        profile = platform + "_product_x64"
        root = Path(tempfile.mkdtemp(prefix="resource-proof-"))
        print("native_fixture_root=" + str(root))
        package = root / "package"
        subprocess.run([os.environ["FACMAN_RESOURCE_PROOF_FIXTURE"], "--make-fixture", platform,
                        str(package), os.environ["FACMAN_RESOURCE_PROOF_CLI"]],
                       check=True, capture_output=True, timeout=30)
        before = cases.snapshot(package)
        for mode in ("portable", "installed_stage"):
            with self.subTest(mode=mode):
                evidence = root / (platform + "-" + mode.replace("_", "-") + "-resource-package.v1.json")
                result = proof.prove(package / cases.PROFILES[profile][0], profile, mode, evidence)
                self.assertEqual(result["status"], "pass", result["failure"])
                self.assertEqual([row["id"] for row in result["cases"]], list(cases.CASE_IDS))
                self.assertEqual(result["input_provenance"], "supplied_path_not_producer_attested")
                self.assertTrue(result["original_unchanged"])
                self.assertFalse(any(result["authority"].values()))
                self.assertEqual(json_contract.validate(result, json_contract.load_schema(proof.SCHEMA)), [])
                self.assertEqual(cases.snapshot(package), before)
                inventory = root / result["input"]["inventory_artifact"]
                self.assertEqual(result["input"]["inventory_sha256"], hashlib.sha256(inventory.read_bytes()).hexdigest())
                self.assertEqual(json.loads(inventory.read_bytes()), before["files"])
                uploaded = list(root.glob(platform + "-*-resource-package*"))
                self.assertIn(evidence, uploaded)
                for artifact in result["artifacts"]:
                    actual = root / artifact["path"]
                    self.assertTrue(any(actual == path or actual.is_relative_to(path) for path in uploaded),
                                    "workflow upload glob must cover every generated artifact")

        bad_package = root / "invalid-package"
        cases.copy_package(package, bad_package, before)
        (bad_package / cases.PROFILES[profile][2]).write_bytes(b"{}")
        failed_evidence = root / "failed.json"
        failed = proof.prove(bad_package / cases.PROFILES[profile][0], profile, "portable", failed_evidence)
        self.assertEqual(failed["status"], "fail")
        self.assertTrue(failed["original_unchanged"])
        self.assertIsNotNone(failed["failure"])
        self.assertNotEqual(failed["commands"][0]["exit_code"], 0)
        self.assertEqual(json.loads(failed_evidence.read_bytes()), failed)
        self.assertEqual(json_contract.validate(failed, json_contract.load_schema(proof.SCHEMA)), [])
        for artifact in failed["artifacts"]:
            self.assertTrue((root / artifact["path"]).is_file())


if __name__ == "__main__":
    unittest.main()
