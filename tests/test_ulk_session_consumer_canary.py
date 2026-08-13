# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class UlkSessionConsumerCanaryTests(unittest.TestCase):
    def test_canary_is_exact_non_authorizing_and_default_off(self) -> None:
        cmake = (ROOT / "cmake" / "FacManProviders.cmake").read_text(encoding="utf-8")
        self.assertIn("option(FACMAN_ULK_SESSION_CONSUMER_CANARY", cmake)
        self.assertIn('"e6de83ad1e1a2c646d31eb2ca68aa5cddb323b4a"', cmake)
        self.assertIn('"d877bfa3a86158f65705facf757e8700a067d077"', cmake)
        self.assertIn("requires non-authorizing provider conformance mode", cmake)
        self.assertIn("refs/heads/dev", cmake)
        self.assertIn("refs/heads/main", cmake)
        self.assertIn("CANDIDATE_RELEASE_IDENTITY", cmake)

    def test_adapter_uses_public_abi_and_bounded_two_call_read(self) -> None:
        source = (
            ROOT / "runtime" / "factorio" / "application" / "last_run_provider.cpp"
        ).read_text(encoding="utf-8")
        self.assertIn('#include "ulk/ulk_session.h"', source)
        self.assertEqual(source.count("ulk_session_journal_last_run_v1("), 2)
        self.assertIn("kMaximumLastRunJsonBytes", source)
        self.assertIn("latest_session_nonterminal", source)
        self.assertIn("record_corrupt_or_incompatible", source)
        self.assertIn("outcome_unknown", source)
        self.assertIn("recovery_required", source)
        self.assertNotIn("LOCALAPPDATA", source)

    def test_harness_preserves_tracked_lock_and_closed_authority(self) -> None:
        harness = (ROOT / "tools" / "ulk_session_consumer_canary.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("tracked_lock_mutated", harness)
        self.assertIn("candidate_not_adopted", harness)
        self.assertIn("release_eligible", harness)
        self.assertIn("negative-tracked-lock", harness)
        self.assertIn("provider.AUTHORITY", harness)
        self.assertNotIn("git push", harness)
        self.assertNotIn("Factorio.exe", harness)


if __name__ == "__main__":
    unittest.main()
