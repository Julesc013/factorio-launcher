# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import unittest

from tools import ci_proof_check


class CiProofTests(unittest.TestCase):
    def test_ci_workflows_reproduce_the_claimed_proof(self) -> None:
        self.assertEqual(ci_proof_check.validate(), [])

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

    def test_every_release_oriented_package_lane_consumes_live_source_custody(self) -> None:
        workflow = (ci_proof_check.WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
        for job in ("linux-native", "windows-native-package", "macos-native-cli"):
            section = workflow.partition(f"  {job}:")[2]
            self.assertIn("Remove ephemeral checkout credential includes", section)
            self.assertIn("python tools/ci_checkout_credential_cleanup.py", section)
            self.assertIn("Record exact checkout and provider observation", section)
            self.assertIn("Project release source observation", section)
            self.assertIn("python tools/facman_release.py source-observation", section)
            self.assertIn("--source-observation", section)


if __name__ == "__main__":
    unittest.main()
