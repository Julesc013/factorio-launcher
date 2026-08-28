# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import unittest

from tools import release_identity_coherence_check


class ReleaseIdentityCoherenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.records = release_identity_coherence_check.load_records()

    def test_current_release_identity_is_coherent(self) -> None:
        self.assertEqual(
            release_identity_coherence_check.validate_records(copy.deepcopy(self.records)),
            set(),
        )
        self.assertEqual(release_identity_coherence_check.validate_source_bindings(), set())
        self.assertEqual(release_identity_coherence_check.detect_misnumbered_identity(), set())

    def test_rejects_version_package_and_authority_drift(self) -> None:
        changed = copy.deepcopy(self.records)
        changed["version"]["semver"] = "4.0.0"
        changed["distribution"]["artifact"][0]["filename"] = "facman-4.0.0.zip"
        changed["distribution"]["authority"]["publication"] = True
        changed["current"]["product"]["safe_beta"] = True
        problems = release_identity_coherence_check.validate_records(changed)
        self.assertTrue(any(problem.startswith("version.semver") for problem in problems))
        self.assertTrue(any(problem.startswith("distribution.packages") for problem in problems))
        self.assertTrue(any(problem.startswith("distribution.authority") for problem in problems))
        self.assertTrue(any(problem.startswith("current.product.safe_beta") for problem in problems))

    def test_only_explicit_containment_lines_may_retain_old_identity(self) -> None:
        check = release_identity_coherence_check.misnumbered_line_is_allowed
        self.assertTrue(
            check(
                "release/index/plan.v1.toml",
                'depends_on = ["FACMAN-4.0.0-MISNUMBERING-CONTAINMENT-01"]',
            )
        )
        self.assertFalse(
            check("README.md", "Current package: facman-4.0.0-windows.zip")
        )
        self.assertTrue(
            check(
                "docs/release/history/facman-4.0.0-misnumbered-internal-candidate.md",
                "Historical FacMan 4.0.0 internal candidate",
            )
        )


if __name__ == "__main__":
    unittest.main()
