# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / "release" / "index" / "c3_universal_consumer_profile.v1.toml"
DOCUMENT_PATH = ROOT / "docs" / "product" / "c3_universal_consumer_profile_01.md"

SNAPSHOT_COMMIT = "ea984df9b7ab99cf47fcdbd8edcb571e6ce80d52"
FINAL_OBSERVED_HEAD = "2d99b047058bcc017e7094231d39e5abe66afefd"
EXPECTED_ROW_IDS = {f"C3-{number:02d}" for number in range(1, 29)}
DISPOSITIONS = {"retain", "move", "adapt", "delete"}


def load_profile() -> dict:
    with PROFILE_PATH.open("rb") as handle:
        return tomllib.load(handle)


class C3UniversalConsumerProfileTests(unittest.TestCase):
    def test_snapshot_is_exact_and_distinct_from_concurrent_final_head(self) -> None:
        profile = load_profile()

        self.assertEqual(profile["snapshot_commit"], SNAPSHOT_COMMIT)
        self.assertEqual(profile["final_observed_head"], FINAL_OBSERVED_HEAD)
        self.assertNotEqual(profile["snapshot_commit"], profile["final_observed_head"])
        self.assertEqual(profile["capture_branch"], "master")
        self.assertEqual(profile["capture_tracking_ref"], "origin/master")
        self.assertEqual(profile["capture_tracking_commit"], SNAPSHOT_COMMIT)

        capture = profile["capture_observation"]
        self.assertEqual(capture["head"], SNAPSHOT_COMMIT)
        self.assertTrue(capture["worktree_dirty"])
        self.assertEqual(capture["modified_count"], 11)
        self.assertEqual(capture["untracked_count"], 1)
        self.assertEqual(len(capture["modified"]), 11)
        self.assertEqual(len(capture["untracked"]), 1)

        final = profile["final_observation"]
        self.assertEqual(final["head"], FINAL_OBSERVED_HEAD)
        self.assertEqual(final["tracking_head"], SNAPSHOT_COMMIT)
        self.assertEqual(final["ahead_of_tracking"], 2)
        self.assertTrue(final["worktree_dirty"])
        self.assertEqual(final["modified_count"], 12)
        self.assertEqual(final["untracked_count"], 0)
        self.assertEqual(len(final["modified"]), 12)

    def test_matrix_has_exactly_28_unique_complete_rows(self) -> None:
        rows = load_profile()["matrix_row"]
        ids = [row["id"] for row in rows]

        self.assertEqual(len(rows), 28)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(set(ids), EXPECTED_ROW_IDS)

        required = {
            "id",
            "source",
            "symbol",
            "responsibility",
            "permanent_owner",
            "disposition",
            "characterization",
            "dependency",
            "rollback",
        }
        for row in rows:
            with self.subTest(row=row["id"]):
                self.assertEqual(set(row), required)
                for field in required:
                    self.assertTrue(str(row[field]).strip(), f"{row['id']} has empty {field}")
                self.assertIn(row["disposition"], DISPOSITIONS)

    def test_ratified_lane_and_launcher_decisions_are_exact(self) -> None:
        decisions = {
            decision["id"]: decision for decision in load_profile()["profile_decision"]
        }
        self.assertEqual(
            set(decisions),
            {
                "legacy_x86_package_authoring",
                "modern_x64_optional_maintenance",
                "launcher_boundary",
            },
        )

        legacy = decisions["legacy_x86_package_authoring"]
        self.assertEqual(legacy["scope"], "win-x86-net40")
        self.assertTrue(legacy["package_authoring"])
        self.assertEqual(
            legacy["external_usk_maintenance"], "disabled_pending_native_proof"
        )
        self.assertEqual(legacy["ulk"], "absent")
        self.assertFalse(legacy["native_xp_product_proof"])
        self.assertFalse(legacy["native_xp_usk_proof"])

        modern = decisions["modern_x64_optional_maintenance"]
        self.assertEqual(modern["scope"], "win-x64-net48")
        self.assertTrue(modern["package_authoring"])
        self.assertEqual(modern["external_usk_maintenance"], "optional_after_contract")
        self.assertEqual(modern["ulk"], "absent")
        self.assertFalse(modern["minimum_os_runtime_proof"])

        launcher = decisions["launcher_boundary"]
        self.assertEqual(launcher["scope"], "all_lanes")
        self.assertEqual(launcher["ulk"], "absent")
        self.assertFalse(launcher["activation_session_demonstrated"])

    def test_data_boundaries_preserve_user_owned_state(self) -> None:
        boundaries = {
            boundary["id"]: boundary for boundary in load_profile()["data_boundary"]
        }
        self.assertEqual(
            set(boundaries),
            {
                "application_payload",
                "user_settings",
                "catalogue_xml",
                "catalogue_backup",
                "crash_reports",
                "console_exports",
            },
        )

        payload = boundaries["application_payload"]
        self.assertEqual(payload["permanent_owner"], "c3")
        self.assertEqual(payload["classification"], "replaceable_verified_product_payload")
        self.assertFalse(payload["preserve_on_uninstall"])

        for boundary_id in (
            "user_settings",
            "catalogue_xml",
            "catalogue_backup",
            "crash_reports",
            "console_exports",
        ):
            with self.subTest(boundary=boundary_id):
                boundary = boundaries[boundary_id]
                self.assertEqual(boundary["permanent_owner"], "c3_user")
                self.assertTrue(boundary["preserve_on_uninstall"])

        self.assertEqual(boundaries["catalogue_xml"]["classification"], "user_document")
        self.assertEqual(
            boundaries["catalogue_backup"]["classification"], "product_data_rollback"
        )

    def test_historical_installer_and_uninstaller_are_delete_only(self) -> None:
        profile = load_profile()
        history = {entry["id"]: entry for entry in profile["historical_commit"]}
        self.assertEqual(
            {entry_id: entry["commit"] for entry_id, entry in history.items()},
            {
                "last_installer_snapshot": "509c9ec29679e30dcdcb1f57d8874b850cee310c",
                "installer_deprecated": "bf3260987458a97dd3a4ed3db154f7992d9d48cc",
                "installer_removed": "08bb8da0d8d8d042fc75982510e56e81a08e38e8",
            },
        )

        rows = {row["id"]: row for row in profile["matrix_row"]}
        for row_id in ("C3-23", "C3-24", "C3-25"):
            with self.subTest(row=row_id):
                self.assertEqual(rows[row_id]["disposition"], "delete")
                self.assertIn("Never", rows[row_id]["rollback"])

    def test_audit_is_read_only_and_moves_no_implementation(self) -> None:
        profile = load_profile()
        result = profile["result"]

        self.assertTrue(profile["read_only"])
        self.assertFalse(profile["implementation_moved"])
        self.assertTrue(result["read_only"])
        self.assertFalse(result["implementation_moved"])
        self.assertFalse(result["consumer_repository_written"])
        self.assertFalse(result["provider_contract_implemented"])
        self.assertFalse(result["setup_integration_authorized"])
        self.assertFalse(result["ulk_integration_authorized"])

        document = DOCUMENT_PATH.read_text(encoding="utf-8")
        self.assertIn("## No-code-move result", document)
        self.assertIn("The audit moved no implementation.", document)
        self.assertIn(SNAPSHOT_COMMIT, document)
        self.assertIn(FINAL_OBSERVED_HEAD, document)
        for row_id in EXPECTED_ROW_IDS:
            self.assertEqual(document.count(f"### {row_id} —"), 1)


if __name__ == "__main__":
    unittest.main()
