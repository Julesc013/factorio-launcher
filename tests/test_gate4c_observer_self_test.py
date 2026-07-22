# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "gate4c_observer_self_test", ROOT / "tools/gate4c_observer_self_test.py"
)
assert SPEC and SPEC.loader
OBSERVER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(OBSERVER)


class Gate4CObserverSelfTestTests(unittest.TestCase):
    def test_lost_event_parser_is_closed_on_unknown_format(self) -> None:
        self.assertIsNone(OBSERVER.parse_lost_events("trace complete without a count"))
        self.assertEqual(OBSERVER.parse_lost_events("Events Lost: 0"), 0)
        self.assertEqual(OBSERVER.parse_lost_events("Events Lost: 0\nEvents Lost: 7"), 7)

    def test_probe_attribution_requires_all_domains_and_pid(self) -> None:
        process_id = 4242
        dump = "\n".join(
            [
                r"FileIo/Write,pid=4242,C:\Gate4C\probe.txt",
                r"Registry/SetValue,pid=4242,FacManGate4CRegistryProbe-test",
                r"Process/Start,pid=4242,FacManGate4CProcessProbe-test",
            ]
        )
        result = OBSERVER.classify_dump(
            dump,
            process_id=process_id,
            file_marker=r"C:\Gate4C\probe.txt",
            registry_marker="FacManGate4CRegistryProbe-test",
            process_marker="FacManGate4CProcessProbe-test",
        )
        self.assertTrue(result["attribution_complete"])

        incomplete = OBSERVER.classify_dump(
            dump.replace("FacManGate4CRegistryProbe-test", "missing"),
            process_id=process_id,
            file_marker=r"C:\Gate4C\probe.txt",
            registry_marker="FacManGate4CRegistryProbe-test",
            process_marker="FacManGate4CProcessProbe-test",
        )
        self.assertFalse(incomplete["attribution_complete"])


if __name__ == "__main__":
    unittest.main()
