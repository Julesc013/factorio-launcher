# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

import jsonschema

from tools import control_gallery_fixtures as fixtures
from tools import development_layout, native_control_gallery

ROOT = Path(__file__).resolve().parents[1]


class NativeControlGalleryTests(unittest.TestCase):
    def test_child_failure_preserves_full_log_and_reports_bounded_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            log = Path(temporary) / "child.log"
            code = "import sys; print('OUT-BEGIN' + 'x' * 7000 + 'OUT-END'); print('ERR-BEGIN' + 'y' * 7000 + 'ERR-END', file=sys.stderr); sys.exit(7)"
            with self.assertRaises(RuntimeError) as caught:
                native_control_gallery.run_command([sys.executable, "-c", code], log)
            message = str(caught.exception)
            self.assertIn("failed (7)", message)
            self.assertIn("OUT-END", message)
            self.assertIn("ERR-END", message)
            self.assertNotIn("OUT-BEGIN", message)
            self.assertNotIn("ERR-BEGIN", message)
            self.assertLess(len(message), 12500)
            full = log.read_text(encoding="utf-8")
            self.assertIn("OUT-BEGIN" + "x" * 7000 + "OUT-END", full)
            self.assertIn("ERR-BEGIN" + "y" * 7000 + "ERR-END", full)

    def test_all_gallery_scopes_follow_the_production_snapshot_schema(self) -> None:
        schema = json.loads((ROOT / "contracts/schema/presentation/presentation_snapshot.v1.schema.json").read_text(encoding="utf-8"))
        validator = jsonschema.Draft202012Validator(schema)
        self.assertEqual(set(fixtures.STATES) | {"ready-overflow"}, set(fixtures.cases()))
        for name, case in fixtures.cases().items():
            with self.subTest(case=name):
                if case["state"] == "error":
                    self.assertEqual({}, case["snapshots"])
                    continue
                self.assertEqual(set(fixtures.SCOPES), set(case["snapshots"]))
                for scope, snapshot in case["snapshots"].items():
                    self.assertEqual(scope, snapshot["page"]["scope"])
                    validator.validate(snapshot)

    def test_scenarios_have_distinct_semantic_oracles(self) -> None:
        ready = fixtures.scenario("ready")["snapshots"]["launch_deck"]
        blocked = fixtures.scenario("blocked")["snapshots"]["launch_deck"]
        busy = fixtures.scenario("busy")["snapshots"]["activity_recovery"]
        recovery = fixtures.scenario("recovery")["snapshots"]["activity_recovery"]
        empty = fixtures.scenario("empty")["snapshots"]["instances"]
        self.assertTrue(ready["readiness"]["execution_available"])
        self.assertFalse(blocked["readiness"]["execution_available"])
        self.assertEqual("stale_readiness", blocked["specific_blockers"][0]["code"])
        self.assertEqual("gallery-operation", busy["active_operations"][0]["operation_id"])
        self.assertEqual("gallery-transaction", recovery["recovery"]["transactions"][0]["transaction_id"])
        self.assertEqual([], empty["page"]["items"])
        self.assertEqual({}, empty["selected_context"])

    def test_fixtures_are_deterministic_and_overflow_is_real_data(self) -> None:
        self.assertEqual(fixtures.cases(), fixtures.cases())
        case = fixtures.scenario("ready", overflow=True)
        items = case["snapshots"]["instances"]["page"]["items"]
        self.assertEqual(41, len(items))
        self.assertGreater(len(items[0]["display_name"]), 200)
        self.assertIn("工場", items[0]["display_name"])
        with self.assertRaises(ValueError):
            fixtures.scenario("invented-ready-state")

    @unittest.skipUnless(os.name == "nt", "not_applicable: actual WinForms controls require Windows")
    def test_real_production_controls_record_actions_and_preserve_state(self) -> None:
        receipt = native_control_gallery.run(development_layout.task_root(ROOT))
        self.assertEqual("PASS", receipt["result"])
        self.assertEqual(28, len(receipt["rows"]))
        self.assertEqual(1, len(receipt["constrained_rows"]))
        constrained = receipt["constrained_rows"][0]
        self.assertEqual("blocked/baseline", constrained["scenario"])
        self.assertEqual(1.25, constrained["scale"])
        self.assertEqual(1024, constrained["maximum_window"]["Width"])
        self.assertEqual(768, constrained["maximum_window"]["Height"])
        self.assertFalse(receipt["live_transport_constructed"])
        self.assertEqual("pending", receipt["gtk"])


if __name__ == "__main__":
    unittest.main()
