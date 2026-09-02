# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

import unittest

from tools import engineering_quality_check


class EngineeringQualityTests(unittest.TestCase):
    def test_alpha5_quality_budgets_hold(self) -> None:
        self.assertEqual([], engineering_quality_check.detect())

    def test_complexity_metric_ignores_comments_and_strings(self) -> None:
        source = '''
        // if while &&
        const char *text = "if or ||";
        if (ready && valid) {
            for (const auto &item : items) consume(item);
        }
        # comment with elif and or
        '''
        self.assertEqual(
            3,
            engineering_quality_check.lexical_decision_points(source, ".cpp"),
        )

    def test_python_multiline_strings_and_hash_comments_are_ignored(self) -> None:
        source = '''
        """if while and
        elif or ||
        """
        # if fake_condition:
        # elif another_fake_condition:
        if ready and valid:
            return True
        '''
        self.assertEqual(
            2,
            engineering_quality_check.lexical_decision_points(source, ".py"),
        )

    def test_c_family_preprocessor_conditionals_remain_decision_points(self) -> None:
        source = '''
        # if ENABLED
        #elif FALLBACK
        #endif
        '''
        self.assertEqual(
            2,
            engineering_quality_check.lexical_decision_points(source, ".cpp"),
        )


if __name__ == "__main__":
    unittest.main()
