from __future__ import annotations

import unittest

from tools import (
    aide_queue_state_check,
    apps_boundary_check,
    critical_io_check,
    generated_catalog_check,
    manual_json_check,
    target_dependency_check,
    version_truth_check,
)


class ArchitectureFitnessTests(unittest.TestCase):
    def test_known_architecture_debt_is_exactly_budgeted(self) -> None:
        checks = [
            apps_boundary_check.main,
            manual_json_check.main,
            critical_io_check.main,
            generated_catalog_check.main,
            version_truth_check.main,
            target_dependency_check.main,
            aide_queue_state_check.main,
        ]
        for check in checks:
            with self.subTest(check=check.__module__):
                self.assertEqual(check(), 0)

    def test_queue_has_no_completed_pass_left_active(self) -> None:
        self.assertEqual(aide_queue_state_check.detect(), set())


if __name__ == "__main__":
    unittest.main()
