# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools import ulk_canonical_adoption as adoption


MAIN_SHA = "a" * 40
MAIN_TREE = "b" * 40


def observation(**changes: object) -> adoption.Observation:
    values: dict[str, object] = {
        "origin_remote": adoption.REMOTE,
        "canonical_main_sha": MAIN_SHA,
        "resolved_tree": MAIN_TREE,
        "parent_count": 2,
        "repair_is_ancestor": True,
        "cmake_version": adoption.EXPECTED_CMAKE_VERSION,
        "package_version": adoption.EXPECTED_PACKAGE_VERSION,
        "abi_major": adoption.EXPECTED_ABI[0],
        "abi_minor": adoption.EXPECTED_ABI[1],
        "abi_manifest_sha256": "c" * 64,
        "current_abi_manifest_sha256": "c" * 64,
        "session_contracts_present": True,
        "tracked_identity_consistent": True,
        "tracked_revision": "d" * 40,
        "tracked_tree": "e" * 40,
    }
    values.update(changes)
    return adoption.Observation(**values)  # type: ignore[arg-type]


def checks(*, conclusion: str = "success", head: str = MAIN_SHA) -> dict[str, object]:
    return {
        "check_runs": [
            {
                "name": name,
                "status": "completed",
                "conclusion": conclusion,
                "head_sha": head,
            }
            for name in sorted(adoption.REQUIRED_CHECKS)
        ]
    }


class UlkCanonicalAdoptionTests(unittest.TestCase):
    def test_exact_merged_main_with_green_ci_is_eligible(self) -> None:
        self.assertEqual(
            adoption.evaluate(
                MAIN_SHA,
                MAIN_TREE,
                adoption.REQUIRED_REF,
                observation(),
                checks(),
            ),
            [],
        )

    def test_task_sha_is_never_a_canonical_pin(self) -> None:
        problems = adoption.evaluate(
            adoption.REPAIR_SHA,
            MAIN_TREE,
            adoption.REQUIRED_REF,
            observation(canonical_main_sha=adoption.REPAIR_SHA),
            checks(head=adoption.REPAIR_SHA),
        )
        self.assertIn("the #16 task SHA cannot be used as a canonical pin", problems)

    def test_old_main_and_dev_only_sha_are_refused(self) -> None:
        problems = adoption.evaluate(
            MAIN_SHA,
            MAIN_TREE,
            adoption.REQUIRED_REF,
            observation(canonical_main_sha="f" * 40, repair_is_ancestor=False),
            checks(),
        )
        self.assertIn("proposed SHA is not the exact current canonical ULK main tip", problems)
        self.assertIn("canonical ULK main does not contain the #16 repair ancestry", problems)

    def test_wrong_tree_or_nonmerge_tip_is_refused(self) -> None:
        problems = adoption.evaluate(
            MAIN_SHA,
            "f" * 40,
            adoption.REQUIRED_REF,
            observation(parent_count=1),
            checks(),
        )
        self.assertIn("proposed ULK tree does not match the proposed commit", problems)
        self.assertIn("canonical ULK repair tip is not a history-preserving merge commit", problems)

    def test_red_or_wrong_head_ci_is_refused(self) -> None:
        red = adoption.evaluate(
            MAIN_SHA, MAIN_TREE, adoption.REQUIRED_REF, observation(), checks(conclusion="failure")
        )
        self.assertTrue(any("is not green" in problem for problem in red))
        wrong = adoption.evaluate(
            MAIN_SHA, MAIN_TREE, adoption.REQUIRED_REF, observation(), checks(head="f" * 40)
        )
        self.assertTrue(any("wrong SHA" in problem for problem in wrong))

    def test_mixed_sdk_or_package_identity_is_refused(self) -> None:
        problems = adoption.evaluate(
            MAIN_SHA,
            MAIN_TREE,
            adoption.REQUIRED_REF,
            observation(tracked_identity_consistent=False),
            checks(),
        )
        self.assertIn("FacMan currently contains mixed ULK source/package identities", problems)

    def test_abi_and_package_drift_are_refused(self) -> None:
        problems = adoption.evaluate(
            MAIN_SHA,
            MAIN_TREE,
            adoption.REQUIRED_REF,
            observation(
                package_version="2.0.0",
                abi_minor=10,
                abi_manifest_sha256="f" * 64,
                session_contracts_present=False,
            ),
            checks(),
        )
        self.assertIn("ULK SDK package version is incompatible", problems)
        self.assertIn("ULK public ABI version changed", problems)
        self.assertIn("ULK public ABI manifest changed", problems)
        self.assertIn("ULK session contracts are incomplete", problems)

    def test_evidence_must_be_outside_source(self) -> None:
        value = adoption.report(
            MAIN_SHA, MAIN_TREE, adoption.REQUIRED_REF, observation(), checks()
        )
        with self.assertRaisesRegex(ValueError, "outside the source repository"):
            adoption._write_external(adoption.ROOT / "build" / "adoption.json", value)
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "adoption.json"
            adoption._write_external(destination, value)
            self.assertTrue(destination.is_file())


if __name__ == "__main__":
    unittest.main()
