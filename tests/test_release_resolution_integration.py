# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import unittest
from unittest.mock import patch

from tools import release_resolution_integration_check as integration


class ReleaseResolutionIntegrationTests(unittest.TestCase):
    def test_repository_policy_is_integrated(self) -> None:
        self.assertEqual(integration.detect(), [])
        self.assertEqual(integration.main(), 0)

    def test_tracked_source_revision_is_refused(self) -> None:
        version = {
            "source_revision": "0" * 40,
            "development_lineage": {"reviewed_base_revision": "1" * 40},
        }
        with patch.object(integration, "_toml", return_value=version):
            problems = integration._version_problems()
        self.assertTrue(any("must not claim observed" in item for item in problems))

    def test_runtime_full_evidence_embedding_is_refused(self) -> None:
        artifacts = {
            "artifact": [
                {
                    "id": "example",
                    "integration": [
                        {
                            "path": "manifest/resolution",
                            "source": "resolution://outputs",
                        }
                    ],
                }
            ]
        }
        with patch.object(integration, "_toml", return_value=artifacts):
            problems = integration._artifact_problems()
        self.assertTrue(any("bounded runtime metadata" in item for item in problems))

    def test_temporary_producer_exception_requires_expiry(self) -> None:
        policy = integration._toml(integration.INDEX / "package_producers.v1.toml")
        changed = copy.deepcopy(policy)
        exception = next(
            item for item in changed["producer"] if item["state"] == "temporary_exception"
        )
        exception.pop("expiry_workunit")
        with patch.object(integration, "_toml", return_value=changed):
            problems = integration._producer_problems()
        self.assertTrue(any("missing expiry_workunit" in item for item in problems))

    def test_historical_exception_requires_exact_full_identity(self) -> None:
        baseline = integration._toml(integration.ROOT / ".aide" / "commit_policy_baseline.toml")
        changed = copy.deepcopy(baseline)
        exact = next(
            item
            for item in changed["commit"]
            if item["sha"] == "451dc6376d52ac2ddaf82c07ee95e423deec0829"
        )
        exact["sha"] = "451dc63"
        with patch.object(integration, "_toml", return_value=changed):
            problems = integration._history_problems()
        self.assertTrue(any("must appear exactly once" in item for item in problems))


if __name__ == "__main__":
    unittest.main()
