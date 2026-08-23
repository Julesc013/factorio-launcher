# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import unittest

from tools import ci_proof_check


class CiProofTests(unittest.TestCase):
    def test_ci_workflows_reproduce_the_claimed_proof(self) -> None:
        self.assertEqual(ci_proof_check.validate(), [])

    def test_ci_events_deduplicate_task_branch_pushes(self) -> None:
        self.assertEqual(ci_proof_check.validate_event_dedup(), [])

    def test_every_external_action_is_pinned_to_the_reviewed_full_sha(self) -> None:
        self.assertEqual(ci_proof_check.validate_immutable_action_pins(), [])

        workflows = {
            "ci.yml": (
                ci_proof_check.WORKFLOWS / "ci.yml"
            ).read_text(encoding="utf-8").replace(
                ci_proof_check.ACTION_PINS["actions/checkout"],
                "v6",
                1,
            )
        }
        problems = ci_proof_check.validate_immutable_action_pins(workflows)
        self.assertTrue(any("must pin actions/checkout" in item for item in problems))

    def test_ci_event_policy_rejects_unbounded_push_and_global_cancellation(self) -> None:
        workflows = {
            name: (ci_proof_check.WORKFLOWS / name).read_text(encoding="utf-8")
            for name in ci_proof_check.DEDUP_WORKFLOW_CLASSES
        }
        workflows["security.yml"] = workflows["security.yml"].replace(
            "  push:\n    branches:\n      - dev\n      - main",
            "  push:",
        ).replace(
            "cancel-in-progress: ${{ github.event_name == 'pull_request' }}",
            "cancel-in-progress: true",
        )
        problems = ci_proof_check.validate_event_dedup(workflows)
        self.assertTrue(
            any(
                "security.yml must retain a protected-branch push trigger" in problem
                for problem in problems
            ),
            problems,
        )
        self.assertTrue(
            any("cancel-in-progress" in problem for problem in problems),
            problems,
        )

    def test_required_package_runner_is_fail_closed(self) -> None:
        text = (ci_proof_check.ROOT / "tools" / "required_package_proof.py").read_text(encoding="utf-8")
        self.assertIn("if result.skipped:", text)
        self.assertIn('source checkout must be clean', text)

    def test_reproducibility_runner_is_clean_and_authority_bounded(self) -> None:
        text = (
            ci_proof_check.ROOT / "tools" / "package_reproducibility_proof.py"
        ).read_text(encoding="utf-8")
        self.assertIn("allow_dirty=False", text)
        self.assertIn('"h1_inference": "none"', text)
        self.assertIn('"execution_authority": "unchanged_not_authorized"', text)

    def test_checkout_observation_is_versioned_and_out_of_tree(self) -> None:
        text = (
            ci_proof_check.ROOT / "tools" / "current_checkout_observation.py"
        ).read_text(encoding="utf-8")
        self.assertIn('SCHEMA = "facman.current_checkout_observation.v2"', text)
        self.assertIn('OUTPUT_STEM = "current-checkout-observation.v2"', text)
        self.assertIn(
            "--output-dir must be outside every ",
            text,
        )
        self.assertIn("observed source/provider checkout", text)
        self.assertIn("merge-base", text)
        self.assertIn("ABI_PATTERN", text)
        self.assertIn('"GIT_NO_LAZY_FETCH": "1"', text)
        self.assertIn('"local_tracking_ref_only"', text)
        self.assertIn("POLICY_RELATIVE_PATH", text)

    def test_every_general_package_lane_consumes_integration_source_custody(self) -> None:
        workflow = (ci_proof_check.WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
        for job in ("linux-native", "windows-native-package", "macos-native-cli"):
            section = workflow.partition(f"  {job}:")[2]
            self.assertIn("Record exact checkout and provider observation", section)
            self.assertIn("Project lock-agnostic checkout source facts", section)
            self.assertIn("Project integration source coherence", section)
            self.assertIn("Prove atomic provider identity reconciliation", section)
            self.assertIn(
                "Prove exact release-source coherence and wrong-provider refusals",
                section,
            )
            self.assertIn("--integration-source-observation", section)
            self.assertNotIn("python tools/facman_release.py source-observation", section)
        windows = workflow.partition("  windows-native-package:")[2].partition(
            "\n  macos-archive-core:"
        )[0]
        scrub = windows.find("Remove checkout-owned temporary credential includes")
        observe = windows.find("Record exact checkout and provider observation")
        self.assertGreaterEqual(scrub, 0)
        self.assertLess(scrub, observe)
        self.assertIn("python tools/ci_checkout_credential_scrub.py", windows)
        self.assertNotIn("python tools/windows_c1_release_candidate.py", windows)
        self.assertNotIn("windows-c1-release-candidate-", windows)
        self.assertNotIn("python tools/facman_release.py package", workflow)

    def test_windows_package_roots_are_explicit_distinct_and_ordered(self) -> None:
        workflow = (ci_proof_check.WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
        windows = workflow.partition("  windows-native-package:")[2].partition(
            "\n  macos-archive-core:"
        )[0]
        anchors = (
            "Configure static Windows native core",
            "-DFACMAN_PROVIDER_SOURCE_LINKAGE=static",
            "Build and test static Windows Release",
            "--profile windows_portable_cli_x64",
            "--profile windows_portable_tui_x64",
            "Configure shared Windows WinForms package root",
            "-DFACMAN_PROVIDER_SOURCE_LINKAGE=shared",
            "Build and test shared Windows native core",
            "--profile windows_legacy_winforms_x64",
            "--build-root build/winforms-shared",
            "windows_package_composition_proof.py",
        )
        positions = [windows.find(anchor) for anchor in anchors]
        self.assertTrue(all(position >= 0 for position in positions), positions)
        self.assertLess(
            windows.find("Configure static Windows native core"),
            windows.find("Build selected Windows static package"),
        )
        self.assertLess(
            windows.find("Build selected Windows static package"),
            windows.find("Configure shared Windows WinForms package root"),
        )
        self.assertLess(
            windows.find("Configure shared Windows WinForms package root"),
            windows.find("Build and smoke shared legacy WinForms compatibility package"),
        )
        legacy_step = windows.partition(
            "Build and smoke shared legacy WinForms compatibility package"
        )[2].partition("- name:")[0]
        self.assertIn("--build-root build/winforms-shared", legacy_step)
        self.assertNotIn("--build-root build/native-smoke", legacy_step)
        self.assertNotIn("copy ulk.dll", windows.lower())
        self.assertNotIn("copy usk.dll", windows.lower())
        self.assertNotIn("copy flb_factorio.dll", windows.lower())
        self.assertNotIn("copy contracts/schema", windows.lower())


if __name__ == "__main__":
    unittest.main()
