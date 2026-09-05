# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Prospective delivery requirements must never promote observed qualification."""

from __future__ import annotations

import copy
import tomllib
import unittest

from tools import generate_plan_views, project_state_release_view


class CorrectedDeliveryTrainTests(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = generate_plan_views.load_plan()

    def test_corrected_scope_is_valid(self) -> None:
        self.assertEqual(generate_plan_views.validate_delivery_train(self.plan), [])

    def test_scope_allocates_capabilities_to_the_correct_minors(self) -> None:
        train = self.plan["delivery_train"]
        self.assertEqual([item["minor"] for item in train["release"]], ["0.1", "0.2", "0.3", "0.4"])
        self.assertEqual(train["checkpoint_order"][-2:], ["reference_desktops_machine_complete", "accepted_0_1_release"])
        self.assertFalse(train["terminal_checkpoint_is_final_release"])
        self.assertIn("macos_intel_x64", train["terminal_platforms"])
        self.assertEqual(train["reference_desktops_0_1"], ["winforms", "gtk3"])
        self.assertEqual(train["desktop_graduation_0_4"], ["appkit"])

    def test_scope_rejects_missing_target_surface_or_desktop(self) -> None:
        for field in ("terminal_platforms", "terminal_surfaces", "reference_desktops_0_1", "local_journeys"):
            with self.subTest(field=field):
                invalid = copy.deepcopy(self.plan)
                invalid["delivery_train"][field].pop()
                self.assertTrue(generate_plan_views.validate_delivery_train(invalid))

    def test_scope_rejects_false_completion_and_authority(self) -> None:
        for field in (
            "terminal_checkpoint_is_final_release", "future_scaffolds_count_as_implemented",
            "gui_dependency_allowed_in_terminal", "ordinary_workflow_requires_advanced",
            "current_qualification_inherited", "authority_granted",
        ):
            with self.subTest(field=field):
                invalid = copy.deepcopy(self.plan)
                invalid["delivery_train"][field] = True
                self.assertTrue(generate_plan_views.validate_delivery_train(invalid))

    def test_scope_rejects_silently_frontloaded_acquisition_or_hosting(self) -> None:
        for feature in ("connected_acquisition", "credential_storage", "local_hosting", "appkit_graduation"):
            invalid = copy.deepcopy(self.plan)
            invalid["delivery_train"]["release"][0]["capabilities"].append(feature)
            self.assertTrue(generate_plan_views.validate_delivery_train(invalid))
            invalid = copy.deepcopy(self.plan)
            invalid["delivery_train"]["release"][0]["excludes"].remove(feature)
            self.assertTrue(generate_plan_views.validate_delivery_train(invalid))

    def test_admission_is_in_progress_not_completed(self) -> None:
        invalid = copy.deepcopy(self.plan)
        work = next(item for item in invalid["workunit"] if item["id"] == invalid["delivery_train"]["workunit"])
        self.assertEqual(work["status"], "active")
        self.assertNotIn("evidence", work)
        work["status"] = "complete"
        self.assertTrue(generate_plan_views.validate_delivery_train(invalid))

    def test_scope_does_not_promote_current_version_packages_or_support(self) -> None:
        root = generate_plan_views.ROOT
        def read(name: str) -> dict:
            with (root / "release/index" / name).open("rb") as stream:
                return tomllib.load(stream)
        train = read("version_train.v1.toml")
        self.assertEqual(train["allocated_version"], "0.1.0-alpha.5")
        self.assertEqual(train["release_source_revision"], "4683ecd9a1b9ead5eb84be152760d12583da0f0e")
        self.assertEqual(train["release_source_tree"], "c07938618bc0f533fd12756cba123f54b8592048")
        active = read("active_release_view.v1.toml")
        self.assertEqual(active["active_asset_count"], 8)
        self.assertFalse(active["release_authority"])
        self.assertFalse(active["publication"])
        self.assertFalse(active["support_activation"])
        scope = read("foundation_public_beta_scope.v2.toml")
        self.assertTrue(all(value is False for value in scope["authority"].values()))
        self.assertEqual(scope["platforms"]["macos_intel_x64"]["tier"], "experimental_preview")
        self.assertEqual(scope["platforms"]["linux_x64"]["tier"], "experimental_preview")

    def test_generated_roadmap_explains_the_corrected_train(self) -> None:
        roadmap = generate_plan_views.render_roadmap(self.plan)
        self.assertIn("Corrected delivery train (prospective requirements)", roadmap)
        self.assertIn("not plain 0.1.0", roadmap)
        for item in self.plan["delivery_train"]["release"]:
            self.assertIn(item["outcome"], roadmap)

    def test_out_of_sequence_active_scope_work_does_not_reopen_history(self) -> None:
        lines = project_state_release_view.roadmap_lines(self.plan["workunit"])
        self.assertIn("FACMAN-0.1-ALPHA6-WORKSPACE-MIGRATION-RECOVERY-01", lines[0])
        text = "\n".join(lines)
        for completed in project_state_release_view.ROADMAP_SEQUENCE[:4]:
            self.assertNotIn(completed, text)

    def test_roadmap_omits_all_terminal_dispositions(self) -> None:
        for state in ("complete", "cancelled", "superseded"):
            workunits = copy.deepcopy(self.plan["workunit"])
            for workunit in workunits:
                workunit["status"] = state
            self.assertEqual(project_state_release_view.roadmap_lines(workunits), [])


if __name__ == "__main__":
    unittest.main()
