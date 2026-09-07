# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Exercise damaged retained evidence through the public native command boundary."""
from __future__ import annotations

import os
import json
import itertools
import tempfile
import unittest
from pathlib import Path

from native_cli import facman_executable
from tools import workspace_lifecycle_package_proof as proof


def bytes_by_path(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*") if path.is_file()
    }


class WorkspaceRecoveryRefusalTests(unittest.TestCase):
    def test_damaged_retained_evidence_refuses_without_rewriting_state(self) -> None:
        executable = facman_executable()
        cases = itertools.product(
            ("rollback", "recover"), ("0.source.json", "0.target.json"),
            ("missing", "corrupt"), ("valid", "root", "plan"),
        )
        for action, evidence_name, damage, binding in cases:
            with self.subTest(action=action, evidence=evidence_name, damage=damage, binding=binding):
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    driver = proof.Driver(executable, root)
                    workspace = root / "Workspace"
                    plan, _legacy, _canonical = proof.prepare_legacy(driver, workspace)
                    arguments = proof.apply_arguments(plan, "damaged-evidence")
                    if action == "rollback":
                        driver.json(workspace, arguments)
                    else:
                        environment = os.environ.copy()
                        environment["FACMAN_TEST_WORKSPACE_MIGRATION_FAULT"] = "after_staging_verification"
                        driver.json(workspace, arguments, expected=1,
                                    error_code="workspace_migration_interrupted",
                                    environment=environment)
                    operation = "operation-damaged-evidence"
                    inspection = driver.json(workspace, [
                        "workspace", "migration", "operation", "inspect", operation,
                    ])
                    retained = workspace / "transactions/workspace-migrations" / (
                        operation + ".data"
                    ) / evidence_name
                    if damage == "missing":
                        retained.unlink()
                    else:
                        retained.write_bytes(b"{}\n")
                    if binding != "valid":
                        journal_path = workspace / "transactions/workspace-migrations" / (
                            operation + ".workspace-migration.v2.json"
                        )
                        journal = json.loads(journal_path.read_text(encoding="utf-8"))
                        if binding == "root":
                            journal["operation"]["expected_root_identity"] = "0" * 64
                            journal["input_identities"]["root_identity"] = "0" * 64
                        else:
                            journal["operation"]["plan_digest"] = "0" * 64
                            journal["input_identities"]["plan_digest"] = "0" * 64
                        journal_path.write_text(json.dumps(journal), encoding="utf-8")
                    before = bytes_by_path(workspace)
                    expected = ("workspace_migration_recovery_required" if action == "rollback"
                                else "workspace_migration_conflict")
                    if binding != "valid":
                        expected = "workspace_migration_apply_unproven"
                    result = driver.json(workspace, proof.control_arguments(
                        action, operation, str(inspection["observed_workspace_revision"]),
                        "damaged-evidence-control",
                    ), expected=1, error_code=expected)
                    self.assertEqual(result["effects"], [])
                    self.assertEqual(bytes_by_path(workspace), before)


if __name__ == "__main__":
    unittest.main()
