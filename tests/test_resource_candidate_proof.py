# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT
"""Candidate receipts must bind six actual asset inventories and all raw evidence."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tests import test_product_candidate as fixtures
from tools import product_candidate
from tools.package import resource_candidate_evidence as proof

SUCCESS = ("original_list", "original_verify", "relocated_list", "relocated_verify",
           "original_help", "original_version", "relocated_help", "relocated_version",
           "export", "missing_help", "missing_version", "truncated_help", "truncated_version",
           "standalone_foreign", "foreign_help", "foreign_version")
REFUSALS = ("existing_output", "missing", "truncated", "foreign")


def write(path, value):
    fixtures.write_json(path, value)


def inventory(platform):
    return [{"path": name, "size": len(name.encode()),
             "sha256": hashlib.sha256(name.encode()).hexdigest(),
             "mode": 0o755 if name.endswith(("facman", ".exe")) else 0o644}
            for name in proof.LAYOUTS[platform]]


def populate(root):
    inputs, resources, bundle = root / "inputs", root / "resources", root / "bundle"
    for platform in product_candidate.ASSET_SUFFIXES:
        eq_path = fixtures.ProductCandidateTests().populate_platform(inputs, platform)
        eq = json.loads(eq_path.read_bytes())
        rows = inventory(platform)
        _, stage = proof.validate_inventory(rows, platform)
        eq.update(canonical_stage_digest=stage, payload_runtime_digest=stage,
                  canonical_file_count=len(rows), payload_runtime_file_count=len(rows))
        write(eq_path, eq)
        platform_path = eq_path.parent / "product-candidate-platform.v1.json"
        record = json.loads(platform_path.read_bytes())
        record["payload_equivalence"]["sha256"] = product_candidate.sha256_file(eq_path)
        write(platform_path, record)
        for spelling, mode in proof.MODES.items():
            parent = resources / platform
            prefix = spelling + "-raw/"
            artifacts = []
            def artifact(name, data):
                path = parent / (prefix + name)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
                row = proof.record(path, prefix + name)
                artifacts.append(row)
                return row
            source = artifact("source.json", b'{"fixture": true}')
            recorded = artifact("inventory.json", json.dumps(rows).encode())
            commands = []
            for label in (*SUCCESS, *REFUSALS):
                stdout = artifact(label + ".stdout", b"synthetic fixture output")
                stderr = artifact(label + ".stderr", b"")
                commands.append({"id": label, "command": ["fixture-facman", label],
                                 "exit_code": int(label in REFUSALS), "timed_out": False,
                                 "output_limit_exceeded": False, "error": None,
                                 "stdout": stdout["path"], "stderr": stderr["path"]})
            roles = {role: {"path": item["path"], "bytes": item["size"], "sha256": item["sha256"]}
                     for role, item in zip(("executable", "resource", "manifest"), rows)}
            receipt = {
                "schema": "facman.resource_package_proof.v1", "status": "pass",
                "profile_id": platform + "_product_x64", "package_mode": mode,
                "platform": {"windows": "win32", "linux": "linux", "macos": "darwin"}[platform],
                "source_revision": fixtures.REVISION, "source_tree": fixtures.TREE,
                "source_dirty": False, "input_provenance": "supplied_path_not_producer_attested",
                "input": dict(roles, root="synthetic fixture package",
                              inventory_sha256=recorded["sha256"], inventory_artifact=recorded["path"]),
                "executable_sha256": roles["executable"]["sha256"], "original_unchanged": True,
                "proof_source_artifact": source["path"],
                "cases": [{"id": name, "status": "pass"} for name in sorted(proof.CASES)],
                "commands": commands, "artifacts": artifacts, "failure": None,
                "ownership": {"root": "synthetic fixture task", "marker_sha256": "a" * 64},
                "authority": proof.PROOF_AUTHORITY,
            }
            write(parent / f"{platform}-{spelling}-resource-package.v1.json", receipt)
    with patch.object(product_candidate, "source_tree", return_value=fixtures.TREE):
        product_candidate.bundle(inputs, bundle, fixtures.VERSION, fixtures.REVISION,
                                 fixtures.provenance("bundle"), "platform")
    return resources, bundle


class ResourceCandidateProofTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.inputs, self.bundle = populate(self.root)
        self.output = self.root / "qualification"
        self.receipt = self.inputs / "windows/windows-portable-resource-package.v1.json"

    def test_six_proofs_bind_immutable_candidate_and_survive_relocation(self):
        before = {p.name: p.read_bytes() for p in self.bundle.iterdir()}
        manifest = proof.build(self.bundle, self.inputs, self.output)
        value = proof.verify(self.output, self.bundle)
        self.assertEqual(6, len(value["proofs"]))
        self.assertEqual(6, len(value["assets"]))
        self.assertEqual(proof.AUTHORITY, value["authority"])
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.bundle.iterdir()})
        self.assertEqual(manifest.read_bytes()[-1:], b"\n")
        moved = self.root / "relocated"
        self.output.rename(moved)
        self.assertEqual(value, proof.verify(moved, self.bundle))
        for platform in product_candidate.ASSET_SUFFIXES:
            rows = [r for r in value["proofs"] if r["platform"] == platform]
            self.assertEqual({"portable", "installed_stage"}, {r["package_mode"] for r in rows})

    def test_wrong_receipt_identity_or_missing_case_refuses_before_output(self):
        original = json.loads(self.receipt.read_bytes())
        changes = {"source_revision": "f" * 40, "source_tree": "f" * 40,
                   "source_dirty": True, "profile_id": "linux_product_x64",
                   "package_mode": "installed_stage", "platform": "linux",
                   "status": "fail", "original_unchanged": False, "input": None,
                   "cases": original["cases"][:-1], "commands": [],
                   "authority": dict(proof.PROOF_AUTHORITY, release=True)}
        for field, replacement in changes.items():
            with self.subTest(field=field):
                write(self.receipt, dict(original, **{field: replacement}))
                with self.assertRaises(ValueError):
                    proof.build(self.bundle, self.inputs, self.output)
                self.assertFalse(self.output.exists())
        write(self.receipt, original)

    def test_rehashed_inventory_for_another_package_cannot_qualify_candidate(self):
        value = json.loads(self.receipt.read_bytes())
        path = self.receipt.parent / value["input"]["inventory_artifact"]
        rows = json.loads(path.read_bytes())
        rows[0]["sha256"] = "e" * 64
        write(path, rows)
        updated = proof.record(path, value["input"]["inventory_artifact"])
        value["artifacts"] = [updated if r["path"] == updated["path"] else r for r in value["artifacts"]]
        value["input"]["inventory_sha256"] = updated["sha256"]
        write(self.receipt, value)
        with self.assertRaisesRegex(ValueError, "produced asset payload"):
            proof.build(self.bundle, self.inputs, self.output)
        self.assertFalse(self.output.exists())

    def test_missing_or_tampered_command_raw_evidence_cannot_pass(self):
        value = json.loads(self.receipt.read_bytes())
        path = self.receipt.parent / value["commands"][0]["stdout"]
        original = path.read_bytes()
        for mutation in ("tamper", "missing"):
            with self.subTest(mutation=mutation):
                if mutation == "tamper":
                    path.write_bytes(original + b"changed")
                else:
                    path.unlink()
                with self.assertRaises((ValueError, FileNotFoundError)):
                    proof.build(self.bundle, self.inputs, self.output)
                self.assertFalse(self.output.exists())
                path.write_bytes(original)

    def test_receipt_without_raw_command_reference_is_refused(self):
        value = json.loads(self.receipt.read_bytes())
        value["commands"][0]["stdout"] = "unrecorded.stdout"
        write(self.receipt, value)
        with self.assertRaisesRegex(ValueError, "raw artifact is missing"):
            proof.build(self.bundle, self.inputs, self.output)

    def test_refusal_exit_and_command_set_are_not_self_attested_success(self):
        original = json.loads(self.receipt.read_bytes())
        for mutation in ("wrong_exit", "missing", "timeout", "unknown"):
            value = json.loads(json.dumps(original))
            if mutation == "wrong_exit":
                value["commands"][-1]["exit_code"] = 7
            elif mutation == "missing":
                value["commands"].pop()
            elif mutation == "timeout":
                value["commands"][0]["timed_out"] = True
            else:
                value["commands"][0]["id"] = "not_a_required_command"
            with self.subTest(mutation=mutation):
                write(self.receipt, value)
                with self.assertRaises(ValueError):
                    proof.build(self.bundle, self.inputs, self.output)
                self.assertFalse(self.output.exists())

    def test_companion_tampering_extra_files_and_candidate_rebinding_refuse(self):
        proof.build(self.bundle, self.inputs, self.output)
        (self.output / "unexpected").write_bytes(b"extra")
        with self.assertRaisesRegex(ValueError, "file closure"):
            proof.verify(self.output, self.bundle)
        (self.output / "unexpected").unlink()
        artifact = next((self.output / "proofs").rglob("*.stdout"))
        artifact.write_bytes(b"tamper")
        with self.assertRaisesRegex(ValueError, "raw artifact identity"):
            proof.verify(self.output, self.bundle)

    def test_output_overlap_or_existing_file_refuses_without_source_change(self):
        before = self.receipt.read_bytes()
        for output in (self.inputs / "new", self.bundle / "new", self.root, self.receipt):
            with self.subTest(output=str(output)), self.assertRaises(ValueError):
                proof.build(self.bundle, self.inputs, output)
        self.assertEqual(before, self.receipt.read_bytes())
        self.assertFalse((self.inputs / "new").exists())
        self.assertFalse((self.bundle / "new").exists())

    def test_unsafe_paths_duplicate_inventory_and_hardlinks_are_refused(self):
        for path in ("../escape", "a//b", "/absolute", "a\\b", "a:b", "a\x00b", "./x", "x/"):
            with self.subTest(path=repr(path)), self.assertRaises(ValueError):
                proof.safe_name(path)
        rows = inventory("windows")
        with self.assertRaisesRegex(ValueError, "duplicate"):
            proof.validate_inventory(rows + rows[:1], "windows")
        raw = self.inputs / "windows/portable-raw/original_list.stdout"
        os.link(raw, self.root / "hardlink")
        with self.assertRaisesRegex(ValueError, "linked or over budget"):
            proof.build(self.bundle, self.inputs, self.output)

    def test_cli_bootstraps_and_failed_build_returns_nonzero(self):
        environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        environment.pop("PYTHONPATH", None)
        script = proof.ROOT / "tools/resource_candidate_proof.py"
        result = subprocess.run([sys.executable, str(script), "--help"], cwd=self.root,
                                env=environment, capture_output=True, text=True, timeout=30)
        self.assertEqual(0, result.returncode, result.stderr)
        self.receipt.unlink()
        result = subprocess.run([sys.executable, str(script), "build", "--bundle", str(self.bundle),
                                 "--inputs", str(self.inputs), "--output", str(self.output)],
                                cwd=self.root, env=environment, capture_output=True, text=True, timeout=30)
        self.assertEqual(1, result.returncode, result.stderr)
        self.assertIn("refused", result.stderr)
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
