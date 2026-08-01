# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import unittest

from tools import facman_fixture_journey_check, generate_facman_fixture_journeys


class FacManFixtureJourneyTests(unittest.TestCase):
    def test_complete_fixture_vertical_slice(self) -> None:
        self.assertEqual(facman_fixture_journey_check.main(), 0)

    def test_journey_generation_is_deterministic(self) -> None:
        self.assertEqual(
            generate_facman_fixture_journeys.render_fixtures(),
            generate_facman_fixture_journeys.render_fixtures(),
        )

    def test_stale_refusal_cannot_start_a_process(self) -> None:
        journey = copy.deepcopy(generate_facman_fixture_journeys.journeys()["stale-readiness"])
        journey["steps"][3]["fixture_process_starts"] = 1
        problems = facman_fixture_journey_check.validate_journey(journey)
        self.assertTrue(any("never start" in problem for problem in problems), problems)

    def test_stale_refusal_identity_is_exact(self) -> None:
        journey = copy.deepcopy(generate_facman_fixture_journeys.journeys()["stale-readiness"])
        journey["structured_refusal"]["code"] = "generic_error"
        problems = facman_fixture_journey_check.validate_journey(journey)
        self.assertTrue(any("structured refusal differs" in problem for problem in problems), problems)

    def test_frontend_close_cannot_become_cancellation(self) -> None:
        journey = copy.deepcopy(generate_facman_fixture_journeys.journeys()["interrupted-recovery"])
        close = next(step for step in journey["steps"] if step["event"] == "frontend.close")
        close["ordinary_cancellation_observed"] = True
        problems = facman_fixture_journey_check.validate_journey(journey)
        self.assertTrue(any("ordinary cancellation" in problem for problem in problems), problems)

    def test_response_loss_cannot_auto_retry(self) -> None:
        journey = copy.deepcopy(generate_facman_fixture_journeys.journeys()["interrupted-recovery"])
        lost = next(step for step in journey["steps"] if step["event"] == "rpc.response_lost")
        lost["fixture_process_starts"] = 2
        problems = facman_fixture_journey_check.validate_journey(journey)
        self.assertTrue(any("outcome_unknown without retry" in problem for problem in problems), problems)


if __name__ == "__main__":
    unittest.main()
