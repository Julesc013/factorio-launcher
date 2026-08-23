# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import json
import unittest

from tools import cross_frontend_journey_conformance as conformance


class CrossFrontendJourneyConformanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.corpus = json.loads(conformance.CORPUS.read_text(encoding="utf-8"))

    def test_corpus_and_projection_sources_are_complete(self) -> None:
        self.assertEqual(conformance.validate_corpus(self.corpus), [])
        self.assertEqual(conformance.validate_projection_sources(), [])

    def test_available_cli_proves_normalized_read_parity(self) -> None:
        self.assertEqual(conformance.observe_read_projection_parity(), [])

    def test_available_cli_proves_existing_install_projection_parity(self) -> None:
        self.assertEqual(conformance.observe_existing_install_projection_parity(), [])

    def test_available_cli_proves_onboarding_projection_parity(self) -> None:
        self.assertEqual(conformance.observe_onboarding_projection_parity(), [])

    def test_stale_revision_cannot_gain_effects(self) -> None:
        changed = copy.deepcopy(self.corpus)
        stale = next(item for item in changed["scenarios"] if item["id"] == "stale_snapshot")
        stale["expected"]["effects"] = True
        self.assertTrue(any("stale snapshot" in item for item in conformance.validate_corpus(changed)))

    def test_duplicate_action_cannot_dispatch_twice(self) -> None:
        changed = copy.deepcopy(self.corpus)
        duplicate = next(item for item in changed["scenarios"] if item["id"] == "duplicate_action")
        duplicate["expected"]["dispatch_count"] = 2
        self.assertTrue(any("duplicate action" in item for item in conformance.validate_corpus(changed)))

    def test_frontend_close_cannot_become_cancellation(self) -> None:
        changed = copy.deepcopy(self.corpus)
        closed = next(item for item in changed["scenarios"] if item["id"] == "frontend_close")
        closed["expected"]["ordinary_cancellation"] = True
        self.assertTrue(any("frontend close" in item for item in conformance.validate_corpus(changed)))


if __name__ == "__main__":
    unittest.main()
