# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import unittest
from pathlib import Path

from tools import factorio_setup_recipe_check

ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / "content" / "factorio" / "product" / "factorio.portable-windows-zip.recipe.v1.json"


class FactorioSetupRecipeTests(unittest.TestCase):
    def test_recipe_policy_and_generated_projection(self) -> None:
        self.assertEqual(factorio_setup_recipe_check.main(), 0)

    def test_recipe_is_data_only_and_execution_neutral(self) -> None:
        recipe = json.loads(RECIPE.read_text(encoding="utf-8"))
        self.assertEqual(recipe["source"]["kind"], "local_archive")
        self.assertEqual(recipe["target_scope"], "portable")
        self.assertTrue(all(value is False for value in recipe["authority"].values()))
        self.assertEqual(
            recipe["post_stage_verification"]["strict_isolation_classification"],
            "candidate_unproven_until_live_h1",
        )


if __name__ == "__main__":
    unittest.main()
