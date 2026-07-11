# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class UpdateCheckTests(unittest.TestCase):
    def test_update_check_is_report_only(self) -> None:
        report = load_toml(ROOT / "release/index/update_report.v1.toml")
        self.assertEqual(report["schema"], "facman.update_report.v1")
        self.assertEqual(report["mode"], "check")
        self.assertFalse(report["mutates_install"])
        self.assertFalse(report["mutates_workspace"])
        self.assertFalse(report["downloads_payload"])
        self.assertEqual(report["apply_authority"], "universal_setup")


def load_toml(path: Path) -> dict[str, object]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


if __name__ == "__main__":
    unittest.main()
