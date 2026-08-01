# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import unittest

from tools import facman_presentation_check, generate_presentation_fixtures


class FacManPresentationTests(unittest.TestCase):
    def test_contract_and_fixtures(self) -> None:
        self.assertEqual(facman_presentation_check.main(), 0)

    def test_generator_is_deterministic(self) -> None:
        first = generate_presentation_fixtures.render_fixtures()
        second = generate_presentation_fixtures.render_fixtures()
        self.assertEqual(first, second)
        self.assertEqual(len(first), 6)

    def test_stale_refusal_requires_newer_revision(self) -> None:
        snapshot = copy.deepcopy(
            generate_presentation_fixtures.snapshots()["refused"]
        )
        snapshot["refusal"]["current_readiness_revision"] = 7
        problems = facman_presentation_check.validate_snapshot(snapshot, "refused")
        self.assertTrue(any("must exceed observed" in problem for problem in problems))

    def test_frontend_cannot_own_or_cancel_operation(self) -> None:
        snapshot = copy.deepcopy(
            generate_presentation_fixtures.snapshots()["running"]
        )
        operation = snapshot["pages"]["activity"]["operations"][0]
        operation["backend_operation_owner"] = "frontend"
        operation["frontend_disconnect"] = "cancel"
        problems = facman_presentation_check.validate_snapshot(snapshot, "running")
        self.assertTrue(any("operation owner" in problem for problem in problems))
        self.assertTrue(any("cannot cancel" in problem for problem in problems))

    def test_live_process_effect_remains_refused(self) -> None:
        snapshot = copy.deepcopy(
            generate_presentation_fixtures.snapshots()["refused"]
        )
        play = snapshot["launch_deck"]["primary_action"]
        play["availability"] = "available"
        play["refusal"] = None
        problems = facman_presentation_check.validate_snapshot(snapshot, "refused")
        self.assertTrue(any("must remain refused" in problem for problem in problems))


if __name__ == "__main__":
    unittest.main()
