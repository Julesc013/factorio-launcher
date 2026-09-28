# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools import provider_adoption_successor_check as successor


class ProviderAdoptionSuccessorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.record = successor._load_json(successor.RECORD)

    def test_canonical_successor_is_exact_and_non_authorizing(self) -> None:
        self.assertEqual([], successor.validate())
        self.assertFalse(any(self.record["authority"].values()))

    def test_current_projection_drift_is_rejected(self) -> None:
        changed = copy.deepcopy(self.record)
        changed["current_inputs"]["providers_lock"] = "0" * 64
        problems = successor.validate(record=changed)
        self.assertTrue(any("current input closure differs" in item for item in problems))

    def test_followup_import_refuses_source_and_projection_drift(self) -> None:
        relatives = [
            successor.FOLLOWUP_RECEIPT.relative_to(successor.ROOT),
            successor.FOLLOWUP_SCHEMA.relative_to(successor.ROOT),
            *(Path(path) for path in {
                **successor.PROVIDER_LOCKED_INPUT_PATHS,
                **successor.PRODUCT_VERSION_INPUT_PATHS,
            }.values()),
        ]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for relative in relatives:
                destination = root / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes((successor.ROOT / relative).read_bytes())
            self.assertEqual([], successor._followup_import_problems(root))

            receipt_path = root / successor.FOLLOWUP_RECEIPT.relative_to(successor.ROOT)
            original = receipt_path.read_bytes()
            receipt = json.loads(original)
            receipt["source"]["commit"] = "0" * 40
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
            self.assertTrue(any(
                "source or policy context differs" in problem
                for problem in successor._followup_import_problems(root)
            ))

            receipt["source"]["commit"] = successor.FOLLOWUP_SOURCE
            receipt["state_formats"]["transaction_journal"]["write_version"] = 2
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
            self.assertTrue(any(
                "state formats differ" in problem
                for problem in successor._followup_import_problems(root)
            ))

            receipt_path.write_bytes(original)
            lock = root / successor.PROVIDER_LOCKED_INPUT_PATHS["providers_lock"]
            lock.write_bytes(lock.read_bytes() + b"\n# altered after import\n")
            self.assertTrue(any(
                "generated projection differs" in problem
                for problem in successor._followup_import_problems(root)
            ))

    def test_product_only_successor_scope_is_closed(self) -> None:
        changed = copy.deepcopy(self.record)
        changed["product_version_successor"]["qualification"] = "machine_qualified"
        problems = successor.validate(record=changed)
        self.assertTrue(
            any("product version successor differs" in item for item in problems),
            problems,
        )

    def test_unrelated_product_input_change_cannot_pass_version_normalization(self) -> None:
        data = (successor.ROOT / "release/index/dependency_lock.v1.toml").read_bytes()
        changed = data.replace(b'miniz-3.1.2.zip', b'miniz-3.1.3.zip')
        self.assertNotEqual(
            hashlib.sha256(successor._normalise_product_version_successor(changed)).hexdigest(),
            successor.ADOPTION_INPUTS["dependency_lock"],
        )

    def test_current_projection_binds_six_jobs_without_an_aggregate(self) -> None:
        self.assertIsNone(self.record["projection_source"]["aggregate_job"])
        self.assertEqual(
            set(self.record["projection_source"]["artifact_jobs"]),
            {
                "linux/static",
                "linux/shared",
                "macos/static",
                "macos/shared",
                "windows/static",
                "windows/shared",
            },
        )
        changed = copy.deepcopy(self.record)
        changed["projection_source"]["artifact_jobs"].pop("windows/shared")
        problems = successor.validate(record=changed)
        self.assertTrue(any("hosted projection source" in item for item in problems))

    def test_authority_reuse_is_rejected(self) -> None:
        changed = copy.deepcopy(self.record)
        changed["authority"]["route_promotion"] = True
        problems = successor.validate(record=changed)
        self.assertTrue(any("opens authority" in item for item in problems))

    def test_missing_historical_invalidation_is_rejected(self) -> None:
        changed = copy.deepcopy(self.record)
        changed["invalidated_evidence"] = changed["invalidated_evidence"][1:]
        problems = successor.validate(record=changed)
        self.assertTrue(any("invalidation set differs" in item for item in problems))

    def test_historical_candidate_validators_run_as_direct_scripts(self) -> None:
        for script in (
            "tools/alpha5_promotion_candidate_closeout_check.py",
            "tools/alpha5_final_candidate_closeout_check.py",
        ):
            with self.subTest(script=script):
                result = subprocess.run(
                    [sys.executable, "-B", script],
                    cwd=successor.ROOT,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
