# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import unittest

from tools import generate_plan_views


class PlanViewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = generate_plan_views.load_plan()

    def test_canonical_plan_is_valid(self) -> None:
        self.assertEqual(generate_plan_views.validate_plan(self.plan), [])

    def test_generated_views_are_current(self) -> None:
        for path, expected in generate_plan_views.render_outputs(self.plan).items():
            self.assertTrue(path.is_file(), path)
            self.assertEqual(path.read_text(encoding="utf-8"), expected)

    def test_dashboard_remains_bounded(self) -> None:
        line_count = len(generate_plan_views.render_dashboard(self.plan).splitlines())
        self.assertGreaterEqual(line_count, 80)
        self.assertLessEqual(line_count, 150)

    def test_dependency_cycle_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.plan)
        invalid["workunit"][0]["depends_on"] = [invalid["workunit"][1]["id"]]
        invalid["workunit"][1]["depends_on"] = [invalid["workunit"][0]["id"]]
        errors = generate_plan_views.validate_plan(invalid)
        self.assertTrue(any("dependency cycle" in error for error in errors), errors)

    def test_ready_work_requires_completed_dependencies(self) -> None:
        invalid = copy.deepcopy(self.plan)
        invalid["workunit"][1]["depends_on"] = [invalid["workunit"][2]["id"]]
        errors = generate_plan_views.validate_plan(invalid)
        self.assertTrue(
            any("ready with incomplete dependencies" in error for error in errors),
            errors,
        )

    def test_completed_work_requires_evidence(self) -> None:
        invalid = copy.deepcopy(self.plan)
        invalid["workunit"][0]["status"] = "complete"
        invalid["workunit"][0]["evidence"] = []
        errors = generate_plan_views.validate_plan(invalid)
        self.assertIn("PLAN-CANON-01 is complete without evidence", errors)

    def test_near_term_plan_is_bounded(self) -> None:
        pending = [
            item
            for item in self.plan["workunit"]
            if item["status"] not in {"complete", "cancelled"}
        ]
        self.assertLessEqual(
            len(pending),
            self.plan["next_workunit_limit"]
            + len([item for item in pending if item["status"] == "active"]),
        )


if __name__ == "__main__":
    unittest.main()
