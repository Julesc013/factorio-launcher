# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT
"""Primitive availability must not enable the unqualified existing-INI owner."""
import json
import os
from pathlib import Path
import tempfile
import unittest

from native_cli import invoke_machine
import test_configuration_reconciliation as reconciliation
from test_local_modset_solver import snapshot


@unittest.skipIf(os.name == "nt", "unsupported: POSIX existing-INI owner admission boundary")
class PosixRetainedRewriteAdmissionTests(unittest.TestCase):
    query = reconciliation.ExistingConfigurationTests.query
    args = reconciliation.ExistingConfigurationTests.args

    def test_wrong_existing_ini_owner_remains_refused_and_preserved(self):
        with tempfile.TemporaryDirectory(prefix="posix-retained-admission-") as value:
            workspace = Path(value)
            instance, original, _ = reconciliation.ExistingConfigurationTests.prepare(self, workspace)
            frozen = snapshot(workspace)
            for scope in ("instances", "launch_deck"):
                projected = self.query(workspace, scope)
                component = projected["dependency_identities"]["configuration_preparation"]
                self.assertIsNone(component["plan"])
                self.assertEqual("configuration_publication_unavailable", component["refusal"]["code"])
                action = next(a for a in projected["available_semantic_actions"]
                              if a["action_id"] == "readiness.prepare_configuration")
                self.assertEqual("refused", action["availability"])
                code, out, err = invoke_machine(self.args(workspace, projected["revision"], scope=scope))
                self.assertNotEqual(0, code, out)
                self.assertEqual("", err, out)
                self.assertIsInstance(json.loads(out), dict)
                self.assertEqual(original, (instance / "config/config.ini").read_bytes())
                self.assertEqual(frozen, snapshot(workspace))
