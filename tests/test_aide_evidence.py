# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import unittest

from tools import aide_evidence


class AideEvidenceTests(unittest.TestCase):
    def test_active_and_archived_task_files_resolve_by_identity(self) -> None:
        active = aide_evidence.resolve_task_file(
            "FACMAN-BUILD-AND-DEVELOPMENT-TRUTH-01",
            "task.yaml",
        )
        archived = aide_evidence.resolve_task_file(
            "FACMAN-GATE4C-PRIVILEGE-SEPARATION-REPAIR-01",
            "evidence/live-privilege-probe.json",
        )
        self.assertIsNotNone(active)
        self.assertIsNotNone(archived)
        self.assertIn(".aide/history/", archived.as_posix())

    def test_task_and_relative_paths_reject_traversal(self) -> None:
        with self.assertRaisesRegex(ValueError, "invalid AIDE task id"):
            aide_evidence.resolve_task_file("../task", "task.yaml")
        with self.assertRaisesRegex(ValueError, "invalid task-relative"):
            aide_evidence.resolve_task_file(
                "FACMAN-BUILD-AND-DEVELOPMENT-TRUTH-01",
                "../status.yaml",
            )
