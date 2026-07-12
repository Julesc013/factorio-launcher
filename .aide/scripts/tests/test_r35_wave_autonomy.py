from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = REPO_ROOT / ".aide/scripts/aide_lite.py"
sys.path.insert(0, str(MODULE_PATH.parent))
SPEC = importlib.util.spec_from_file_location("aide_lite_r35_wave", MODULE_PATH)
aide_lite = importlib.util.module_from_spec(SPEC)
sys.modules["aide_lite_r35_wave"] = aide_lite
assert SPEC.loader is not None
SPEC.loader.exec_module(aide_lite)


class R35WaveAutonomyTests(unittest.TestCase):
    def make_repo(self) -> Path:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        (root / ".aide/scripts/tests").mkdir(parents=True)
        (root / ".aide/scripts/tests/smoke.py").write_text("assert True\n", encoding="utf-8")
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.email", "aide@example.invalid"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.name", "AIDE Test"], cwd=root, check=True)
        subprocess.run(["git", "add", "."], cwd=root, check=True)
        subprocess.run(["git", "commit", "-qm", "test: initialize fixture"], cwd=root, check=True)
        return root

    def args(self, root: Path, **values: object) -> argparse.Namespace:
        defaults: dict[str, object] = {
            "repo_root": root,
            "wave_id": "fixture-wave",
            "title": "Fixture wave",
            "manifest": None,
            "force": False,
            "workunit": None,
            "test_result": [],
        }
        defaults.update(values)
        return argparse.Namespace(**defaults)

    def test_parser_exposes_complete_wave_lifecycle(self) -> None:
        parser = aide_lite.build_parser(REPO_ROOT)
        for operation in ["create", "status", "next", "start", "verify", "close", "resume", "archive"]:
            parsed = parser.parse_args(["wave", operation])
            self.assertTrue(callable(getattr(parsed, "handler", None)), operation)

    def test_green_workunit_closes_to_resumable_checkpoint(self) -> None:
        root = self.make_repo()
        self.assertEqual(aide_lite.command_wave_create(self.args(root)), 0)
        self.assertEqual(aide_lite.command_wave_start(self.args(root)), 0)
        self.assertEqual(
            aide_lite.command_wave_verify(
                self.args(root, test_result=["aide-lite-test=PASS", "fixture-smoke=PASS"])
            ),
            0,
        )
        state = aide_lite.wave_read_state(root, "fixture-wave")
        self.assertEqual(state["workunits"][0]["status"], "verified")
        evidence = state["workunits"][0]["verification"]
        self.assertFalse(evidence["promotion_eligible"])
        self.assertFalse(evidence["target_runner_evidence_inferred"])
        self.assertTrue(evidence["source_fingerprint"])

        self.assertEqual(aide_lite.command_wave_close(self.args(root)), 0)
        closed = aide_lite.wave_read_state(root, "fixture-wave")
        checkpoint = closed["checkpoints"][-1]
        self.assertTrue(checkpoint["clean_status"])
        self.assertEqual(checkpoint["commit_sha"], closed["workunits"][0]["last_green_commit"])
        self.assertEqual(checkpoint["remaining_workunits"], [])
        self.assertEqual(aide_lite.command_wave_resume(self.args(root)), 0)

    def test_failed_verification_blocks_close_and_archive(self) -> None:
        root = self.make_repo()
        aide_lite.command_wave_create(self.args(root))
        aide_lite.command_wave_start(self.args(root))
        self.assertEqual(aide_lite.command_wave_verify(self.args(root, test_result=["smoke=FAIL"])), 1)
        state = aide_lite.wave_read_state(root, "fixture-wave")
        self.assertEqual(state["workunits"][0]["status"], "blocked")
        self.assertTrue(state["workunits"][0]["blockers"])
        with self.assertRaisesRegex(ValueError, "passing verification"):
            aide_lite.command_wave_close(self.args(root, workunit="WORKUNIT-01"))
        with self.assertRaisesRegex(ValueError, "only a complete wave"):
            aide_lite.command_wave_archive(self.args(root))

    def test_manifest_validation_rejects_unknown_dependencies(self) -> None:
        root = self.make_repo()
        aide_lite.command_wave_create(self.args(root))
        path = aide_lite.wave_state_path(root, "fixture-wave")
        data = json.loads(path.read_text(encoding="utf-8"))
        data["workunits"][0]["dependencies"] = ["MISSING"]
        path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "unknown dependencies"):
            aide_lite.wave_read_state(root, "fixture-wave")


if __name__ == "__main__":
    unittest.main()
