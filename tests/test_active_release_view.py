# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import unittest

from tools import active_release_view_check


class ActiveReleaseViewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.values = active_release_view_check.load_inputs()

    def test_repository_view_is_coherent(self) -> None:
        self.assertEqual(active_release_view_check.validate(self.values), [])

    def test_schema_rejects_unlisted_authority(self) -> None:
        invalid = copy.deepcopy(self.values)
        invalid["active"]["merge_authority"] = True
        problems = active_release_view_check.validate(invalid)
        self.assertTrue(
            any("additional properties" in problem.lower() for problem in problems),
            problems,
        )

    def test_active_profile_drift_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.values)
        invalid["active"]["active_profile_ids"].append("windows_portable_cli_x64")
        problems = active_release_view_check.validate(invalid)
        self.assertTrue(any("active profile ids" in problem for problem in problems))

    def test_historical_support_row_cannot_become_current(self) -> None:
        invalid = copy.deepcopy(self.values)
        row = next(
            item
            for item in invalid["support"]["platform"]
            if item["id"] == "windows_portable_cli_x64"
        )
        row["current_release_obligation"] = True
        problems = active_release_view_check.validate(invalid)
        self.assertTrue(
            any("current obligations" in problem for problem in problems),
            problems,
        )

    def test_historical_producer_cannot_become_current(self) -> None:
        invalid = copy.deepcopy(self.values)
        row = next(
            item
            for item in invalid["producers"]["producer"]
            if item["id"] == "legacy_console_and_tui"
        )
        row["current_release_obligation"] = True
        problems = active_release_view_check.validate(invalid)
        self.assertTrue(
            any("only canonical product and setup producers" in problem for problem in problems),
            problems,
        )

    def test_eight_asset_shape_drift_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.values)
        invalid["artifacts"]["artifact"][0]["pattern"] = "FacMan-wrong.zip"
        problems = active_release_view_check.validate(invalid)
        self.assertTrue(
            any("eight-asset shape" in problem for problem in problems),
            problems,
        )

    def test_earlier_candidate_cannot_present_as_current(self) -> None:
        invalid = copy.deepcopy(self.values)
        invalid["historical_candidate"]["current_candidate"] = True
        problems = active_release_view_check.validate(invalid)
        self.assertTrue(
            any("earlier Alpha.5 receipt presents as current" in problem for problem in problems),
            problems,
        )


if __name__ == "__main__":
    unittest.main()
