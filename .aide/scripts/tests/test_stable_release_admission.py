"""Portable target/source admission and FacMan mutation boundaries."""
import argparse
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("portable_stable_admission_lite", ROOT / ".aide/scripts/aide_lite.py")
lite = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = lite
spec.loader.exec_module(lite)
PROFILE = "profile_id: factorio-launcher\ngenerated_from: aide-lite-pack-v0\nstatus: target_initialized\n"

class PortableAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = contextlib.ExitStack()
        self.addCleanup(self.temp.close)
        with patch.dict(os.environ):
            os.environ.pop("AIDE_JOB_ID", None)
            self.root = Path(self.temp.enter_context(lite.public_archive_fixture("aide-public-release-test-")))
        (self.root / ".aide/queue").mkdir(parents=True)
        (self.root / ".aide/queue/index.yaml").write_text("tasks: []\n")

    def test_portable_target_queue_does_not_require_source_host(self):
        (self.root / ".aide/profile.yaml").write_text(PROFILE)
        self.assertTrue(lite.source_maintainer_job_guard(self.root))

    def test_unknown_queue_without_owner_fails_closed(self):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertFalse(lite.source_maintainer_job_guard(self.root))
        self.assertIn("no managed job owner", output.getvalue())

    def test_committed_source_identity_cannot_use_target_working_profile(self):
        (self.root / ".aide/profile.yaml").write_text(PROFILE)
        source_profile = "profile_id: aide-self-hosting\nprofile_mode: self-hosting\n"
        with patch.object(lite, "run_git_status_code", return_value=(0, source_profile, "")), contextlib.redirect_stdout(io.StringIO()):
            self.assertFalse(lite.source_maintainer_job_guard(self.root))

    def test_committed_facman_identity_survives_working_policy_deletion(self):
        def committed(root, args, **kwargs):
            self.assertTrue(kwargs.get("ignore_replacements"))
            return (0, PROFILE, "") if args == ["show", "HEAD:.aide/profile.yaml"] else (128, "", "absent")
        with patch.object(lite, "run_git_status_code", side_effect=committed):
            self.assertTrue(lite.facman_portable_installation(self.root))
            args = argparse.Namespace(repo_root=self.root, apply=True, classification="review.json")
            with patch.object(lite.importlib.util, "spec_from_file_location") as load, contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(1, lite.command_commit_create(args))
            load.assert_not_called()
            self.assertIn("required FacMan controls", output.getvalue())

    def test_facman_apply_refuses_unpinned_review_control_transaction(self):
        args = argparse.Namespace(repo_root=self.root, apply=True, classification="review.json")
        with patch.object(lite, "facman_portable_installation", return_value=True), patch.object(lite, "facman_missing_commit_controls", return_value=[]), patch.object(lite.importlib.util, "spec_from_file_location") as load, contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(1, lite.command_commit_create(args))
        load.assert_not_called()
        self.assertIn("atomic independent-review/control binding", output.getvalue())

    def test_facman_dry_run_requires_independent_classification(self):
        args = argparse.Namespace(repo_root=self.root, apply=False)
        with patch.object(lite, "facman_portable_installation", return_value=True), patch.object(lite, "facman_missing_commit_controls", return_value=[]), patch.object(lite.importlib.util, "spec_from_file_location") as load, contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(1, lite.command_commit_create(args))
        load.assert_not_called()
        self.assertIn("--classification", output.getvalue())

if __name__ == "__main__":
    unittest.main()
