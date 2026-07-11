# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

from tools import json_contract
from test_diagnostic_redaction import (
    assert_no_secret_values,
    run_json,
    setup_redaction_workspace,
    tree_snapshot,
)

ROOT = Path(__file__).resolve().parents[1]


class DiagnosticExportSafetyTests(unittest.TestCase):
    def test_bundle_hash_closure_and_no_clobber(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            setup_redaction_workspace(workspace)
            output = workspace / "diagnostic proof.zip"
            code, result, stdout, stderr = run_json(
                [
                    "--workspace",
                    str(workspace),
                    "diagnostics",
                    "export",
                    "--instance",
                    "redaction-proof",
                    "--out",
                    str(output),
                    "--json",
                ]
            )
            self.assertEqual(code, 0, stderr)
            self.assertTrue(result["self_verified"])
            assert_no_secret_values(self, stdout)

            with zipfile.ZipFile(output) as archive:
                manifest_bytes = archive.read("manifest/diagnostic-bundle.v1.json")
                manifest = json.loads(manifest_bytes)
                read_report = json.loads(archive.read("reports/file-reads.v1.json"))
                omission_report = json.loads(archive.read("reports/omissions.v1.json"))
                for file in manifest["files"]:
                    self.assertEqual(
                        hashlib.sha256(archive.read(file["path"])).hexdigest(),
                        file["sha256"],
                        file["path"],
                    )
                payload = b"".join(archive.read(name) for name in archive.namelist())
            schema_pairs = [
                (manifest, "diagnostic_bundle.v1.schema.json"),
                (read_report, "diagnostic_file_read_report.v1.schema.json"),
                (omission_report, "diagnostic_omission_report.v1.schema.json"),
            ]
            for document, schema_name in schema_pairs:
                schema = json.loads(
                    (ROOT / "contracts" / "schema" / "factorio" / schema_name).read_text(
                        encoding="utf-8"
                    )
                )
                self.assertEqual(json_contract.validate(document, schema), [], schema_name)
            self.assertEqual(hashlib.sha256(manifest_bytes).hexdigest(), result["manifest_sha256"])
            self.assertNotIn(str(workspace).encode("utf-8"), payload)
            assert_no_secret_values(self, payload)

            before = output.read_bytes()
            code, refusal, _stdout, _stderr = run_json(
                [
                    "--workspace",
                    str(workspace),
                    "diagnostics",
                    "export",
                    "--instance",
                    "redaction-proof",
                    "--out",
                    str(output),
                    "--json",
                ]
            )
            self.assertEqual(code, 1)
            self.assertEqual(refusal["refusal"]["code"], "diagnostic_bundle_target_exists")
            self.assertEqual(output.read_bytes(), before)

    def test_malformed_reviewed_json_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            instance = setup_redaction_workspace(workspace)
            malformed = instance / "config" / "server-settings.json"
            malformed.write_text('{"rcon_password":"must-not-escape"\n', encoding="utf-8")
            output = workspace / "malformed.zip"
            code, refusal, stdout, _stderr = run_json(
                [
                    "--workspace",
                    str(workspace),
                    "diagnostics",
                    "export",
                    "--instance",
                    "redaction-proof",
                    "--out",
                    str(output),
                    "--json",
                ]
            )
            self.assertEqual(code, 1)
            self.assertEqual(refusal["refusal"]["code"], "diagnostic_structured_input_invalid")
            self.assertNotIn("must-not-escape", stdout)
            self.assertFalse(output.exists())

    def test_hardlinked_selected_file_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            instance = setup_redaction_workspace(workspace)
            source = instance / "logs" / "factorio-current.log"
            alias = instance / "logs" / "factorio-alias.log"
            try:
                os.link(source, alias)
            except OSError as exc:
                self.skipTest(f"hard links unavailable: {exc}")
            output = workspace / "hardlink.zip"
            code, refusal, _stdout, _stderr = run_json(
                [
                    "--workspace",
                    str(workspace),
                    "diagnostics",
                    "export",
                    "--instance",
                    "redaction-proof",
                    "--out",
                    str(output),
                    "--json",
                ]
            )
            self.assertEqual(code, 1)
            self.assertEqual(refusal["refusal"]["code"], "diagnostic_source_link_refused")
            self.assertIn("diagnostic_source_link_refused", refusal["refusal"]["detail"])
            self.assertFalse(output.exists())

    def test_linked_external_tree_is_omitted_without_reading(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            external = Path(tmp) / "external"
            instance = setup_redaction_workspace(workspace)
            external.mkdir()
            secret = "external-linked-secret-must-not-escape"
            (external / "foreign.log").write_text(secret, encoding="utf-8")
            linked = instance / "logs" / "linked"
            try:
                linked.symlink_to(external, target_is_directory=True)
            except OSError as exc:
                if os.name != "nt":
                    self.fail(f"directory link creation failed: {exc}")
                created = subprocess.run(
                    ["cmd", "/c", "mklink", "/J", str(linked), str(external)],
                    check=False,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                self.assertEqual(created.returncode, 0, created.stderr or created.stdout)
            output = workspace / "linked.zip"
            code, _result, _stdout, stderr = run_json(
                [
                    "--workspace",
                    str(workspace),
                    "diagnostics",
                    "export",
                    "--instance",
                    "redaction-proof",
                    "--out",
                    str(output),
                    "--json",
                ]
            )
            self.assertEqual(code, 0, stderr)
            with zipfile.ZipFile(output) as archive:
                payload = b"".join(archive.read(name) for name in archive.namelist())
                omissions = json.loads(archive.read("reports/omissions.v1.json"))
            self.assertNotIn(secret.encode("utf-8"), payload)
            self.assertIn(
                "link_or_reparse_refused",
                {item["reason"] for item in omissions["omissions"]},
            )

    def test_fault_matrix_never_leaves_partial_target(self) -> None:
        states = [
            "requested",
            "validated",
            "planned",
            "staging",
            "staged",
            "verified",
            "committing",
            "committed",
            "audited",
            "complete",
        ]
        for state in states:
            with self.subTest(state=state), tempfile.TemporaryDirectory() as tmp:
                workspace = Path(tmp)
                setup_redaction_workspace(workspace)
                output = workspace / f"fault-{state}.zip"
                os.environ["FACMAN_TEST_TRANSACTION_FAIL_STATE"] = state
                try:
                    code, _result, _stdout, _stderr = run_json(
                        [
                            "--workspace",
                            str(workspace),
                            "diagnostics",
                            "export",
                            "--instance",
                            "redaction-proof",
                            "--out",
                            str(output),
                            "--json",
                        ]
                    )
                finally:
                    os.environ.pop("FACMAN_TEST_TRANSACTION_FAIL_STATE", None)
                self.assertEqual(code, 1)
                if state in {"requested", "validated", "planned", "staging", "staged", "verified", "committing"}:
                    self.assertFalse(output.exists())
                else:
                    self.assertTrue(output.is_file())
                    with zipfile.ZipFile(output) as archive:
                        self.assertIn("manifest/diagnostic-bundle.v1.json", archive.namelist())

    def test_sources_and_fixtures_are_immutable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            instance = setup_redaction_workspace(workspace)
            before = tree_snapshot(instance)
            output = workspace / "immutability.zip"
            code, _result, _stdout, stderr = run_json(
                [
                    "--workspace",
                    str(workspace),
                    "diagnostics",
                    "export",
                    "--instance",
                    "redaction-proof",
                    "--out",
                    str(output),
                    "--json",
                ]
            )
            self.assertEqual(code, 0, stderr)
            self.assertEqual(tree_snapshot(instance), before)

    def test_committed_fault_recovery_preserves_zip_and_removes_owned_staging(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            setup_redaction_workspace(workspace)
            output = workspace / "committed-fault.zip"
            os.environ["FACMAN_TEST_TRANSACTION_FAIL_STATE"] = "committed"
            try:
                code, _refusal, _stdout, _stderr = run_json(
                    [
                        "--workspace",
                        str(workspace),
                        "diagnostics",
                        "export",
                        "--instance",
                        "redaction-proof",
                        "--out",
                        str(output),
                        "--json",
                    ]
                )
            finally:
                os.environ.pop("FACMAN_TEST_TRANSACTION_FAIL_STATE", None)
            self.assertEqual(code, 1)
            self.assertTrue(output.is_file())
            before = output.read_bytes()
            journals = sorted((workspace / "transactions").glob("*.transaction.v1.json"))
            diagnostic_journal = next(
                path
                for path in journals
                if json.loads(path.read_text(encoding="utf-8"))["command_id"]
                == "diagnostics.export"
            )
            transaction_id = diagnostic_journal.name.removesuffix(".transaction.v1.json")
            code, recovered, _stdout, stderr = run_json(
                [
                    "--workspace",
                    str(workspace),
                    "workspace",
                    "recovery",
                    "apply",
                    transaction_id,
                    "--json",
                ]
            )
            self.assertEqual(code, 0, stderr)
            self.assertEqual(recovered["transactions"][0]["state"], "complete")
            self.assertEqual(output.read_bytes(), before)
            self.assertEqual(list(workspace.glob(".facman-diagnostic-*")), [])


if __name__ == "__main__":
    unittest.main()
