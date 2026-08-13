# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from tools import provider_reconciled_consumption as reconciled
from tools import provider_sdk_consumption as consumption
from tools import provider_semantic_conformance as semantics


ROOT = Path(__file__).resolve().parents[1]


class ProviderReconciledConsumptionTests(unittest.TestCase):
    def test_tracked_command_uses_the_workspace_lock_without_candidate_mode(self) -> None:
        mode = next(item for item in semantics.MODES if item.name == "source_static")
        command = consumption._candidate_command(
            ROOT,
            Path("build/reconciled"),
            ROOT / "release/index/workspace_lock.v1.toml",
            mode,
            {
                "universal_launcher": SimpleNamespace(root=Path("C:/providers/ulk")),
                "universal_setup": SimpleNamespace(root=Path("C:/providers/usk")),
            },
            None,
            None,
            "cmake",
            "Release",
            None,
            tracked_selection=True,
        )
        self.assertIn("-DFACMAN_PROVIDER_SDK_CONSUMPTION_CANDIDATE=OFF", command)
        self.assertIn(
            f"-DFACMAN_PROVIDER_LOCK_FILE={ROOT / 'release/index/workspace_lock.v1.toml'}",
            command,
        )
        self.assertNotIn("-DFACMAN_PROVIDER_CONFORMANCE_ONLY=ON", command)

    def test_tracked_build_identity_refuses_candidate_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            build = Path(temporary)
            identity = (
                "provider_lock_kind=tracked;"
                "provider_conformance_only=false;"
                "provider_sdk_consumption_candidate=false;"
                "provider_candidate_differs_from_tracked=false;"
                "provider_release_identity_coherent=true;"
                "ulk_session_consumer_canary=false\n"
            )
            (build / "facman-build-identity.v1.txt").write_text(
                identity, encoding="utf-8"
            )
            _, values = consumption._build_identity(
                build, tracked_selection=True
            )
            self.assertEqual(values["provider_lock_kind"], "tracked")
            with self.assertRaisesRegex(ValueError, "provider_lock_kind"):
                consumption._build_identity(build, tracked_selection=False)

    def test_reconciled_schema_requires_adoption_truth_and_false_authority(self) -> None:
        schema = json.loads(
            (
                ROOT
                / "contracts/schema/release/provider_reconciled_consumption.v1.schema.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(
            schema["properties"]["provider_input_adopted"]["const"], True
        )
        self.assertEqual(schema["properties"]["provider_repin"]["const"], True)
        self.assertEqual(schema["properties"]["release_eligible"]["const"], False)
        self.assertEqual(schema["properties"]["resumed_work"]["type"], "boolean")
        self.assertTrue(
            all(
                definition["const"] is False
                for definition in schema["$defs"]["authority"]["properties"].values()
            )
        )
        self.assertEqual(reconciled.SCHEMA, schema["properties"]["schema"]["const"])

if __name__ == "__main__":
    unittest.main()
