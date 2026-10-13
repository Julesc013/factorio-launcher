# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT
"""Linux and Darwin existing-INI owner admission is explicit."""
import json
import os
import sys
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

    def test_existing_ini_owner_host_boundary_and_unsafe_target_refusal(self):
        with tempfile.TemporaryDirectory(prefix="posix-retained-admission-") as value:
            workspace = Path(value).resolve()
            instance, original, _ = reconciliation.ExistingConfigurationTests.prepare(self, workspace)
            frozen = snapshot(workspace)
            for scope in ("instances", "launch_deck"):
                projected = self.query(workspace, scope)
                component = projected["dependency_identities"]["configuration_preparation"]
                action = next(a for a in projected["available_semantic_actions"]
                              if a["action_id"] == "readiness.prepare_configuration")
                if sys.platform in ("linux", "darwin"):
                    self.assertIsNotNone(component["plan"], component["refusal"])
                    self.assertEqual("existing_routing_configuration", component["plan"]["component"])
                    self.assertEqual("available", action["availability"])
                    self.assertEqual(frozen, snapshot(workspace))
                    continue
                self.assertIsNone(component["plan"])
                self.assertEqual("configuration_publication_unavailable", component["refusal"]["code"])
                self.assertEqual("refused", action["availability"])
                code, out, err = invoke_machine(self.args(workspace, projected["revision"], scope=scope))
                self.assertNotEqual(0, code, out)
                self.assertEqual("", err, out)
                self.assertIsInstance(json.loads(out), dict)
                self.assertEqual(original, (instance / "config/config.ini").read_bytes())
                self.assertEqual(frozen, snapshot(workspace))
            if sys.platform in ("linux", "darwin"):
                target = instance / "config/config.ini"
                target.chmod(0o444)
                try:
                    for scope in ("instances", "launch_deck"):
                        projected = self.query(workspace, scope)
                        component = projected["dependency_identities"]["configuration_preparation"]
                        self.assertIsNone(component["plan"])
                        self.assertEqual("configuration_original_custody_unavailable", component["refusal"]["code"])
                        held = snapshot(workspace)
                        code, out, err = invoke_machine(self.args(workspace, projected["revision"], scope=scope))
                        self.assertNotEqual(0, code, out)
                        self.assertEqual("", err, out)
                        self.assertEqual(original, target.read_bytes())
                        self.assertEqual(held, snapshot(workspace))
                finally:
                    target.chmod(0o644)
