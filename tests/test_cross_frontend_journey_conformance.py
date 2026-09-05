# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from tools import cross_frontend_journey_conformance as conformance
from tools import test_obligations


class CrossFrontendJourneyConformanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.corpus = json.loads(conformance.CORPUS.read_text(encoding="utf-8"))

    def test_corpus_and_projection_sources_are_complete(self) -> None:
        self.assertEqual(conformance.validate_corpus(self.corpus), [])
        self.assertEqual(conformance.validate_projection_sources(), [])

    def test_available_cli_proves_normalized_read_parity(self) -> None:
        self.require_candidate()
        self.assertEqual(conformance.observe_read_projection_parity(), [])

    def test_available_cli_proves_existing_install_projection_parity(self) -> None:
        self.require_candidate()
        self.assertEqual(conformance.observe_existing_install_projection_parity(), [])

    def test_available_cli_proves_onboarding_projection_parity(self) -> None:
        self.require_candidate()
        self.assertEqual(conformance.observe_onboarding_projection_parity(), [])

    def require_candidate(self) -> None:
        if not os.environ.get("FACMAN_CLI_EXE"):
            self.skipTest("required_blocked: FACMAN_CLI_EXE is absent; executable parity not run")
        conformance.configured_executable()

    def test_stale_revision_cannot_gain_effects(self) -> None:
        changed = copy.deepcopy(self.corpus)
        stale = next(item for item in changed["scenarios"] if item["id"] == "stale_snapshot")
        stale["expected"]["effects"] = True
        self.assertTrue(any("stale snapshot" in item for item in conformance.validate_corpus(changed)))

    def test_duplicate_action_cannot_dispatch_twice(self) -> None:
        changed = copy.deepcopy(self.corpus)
        duplicate = next(item for item in changed["scenarios"] if item["id"] == "duplicate_action")
        duplicate["expected"]["dispatch_count"] = 2
        self.assertTrue(any("duplicate action" in item for item in conformance.validate_corpus(changed)))

    def test_frontend_close_cannot_become_cancellation(self) -> None:
        changed = copy.deepcopy(self.corpus)
        closed = next(item for item in changed["scenarios"] if item["id"] == "frontend_close")
        closed["expected"]["ordinary_cancellation"] = True
        self.assertTrue(any("frontend close" in item for item in conformance.validate_corpus(changed)))


class ExecutableQualificationAccountingTests(unittest.TestCase):
    def run_conformance(self, arguments: list[str], executable: str) -> tuple[int, str, str]:
        output, error = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, {"FACMAN_CLI_EXE": executable}):
            with redirect_stdout(output), redirect_stderr(error):
                status = conformance.main(arguments)
        return status, output.getvalue(), error.getvalue()

    def test_static_only_is_explicit_and_does_not_run_observers(self) -> None:
        with mock.patch.object(conformance, "observe_read_projection_parity") as observer:
            status, output, error = self.run_conformance([], "")
        self.assertEqual(status, 0, error)
        self.assertIn("static_only; executable parity not_run", output)
        observer.assert_not_called()

    def test_required_executable_cannot_fall_back_to_static_only(self) -> None:
        status, output, error = self.run_conformance(["--require-executable"], "")
        self.assertEqual(status, 1)
        self.assertEqual(output, "")
        self.assertIn("required_blocked", error)

    def test_invalid_configured_path_fails_even_without_required_flag(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman-conformance-invalid-") as temporary:
            for executable in (temporary, str(Path(temporary) / "missing-facman")):
                with self.subTest(executable=executable):
                    status, output, error = self.run_conformance([], executable)
                    self.assertEqual(status, 1)
                    self.assertEqual(output, "")
                    self.assertIn("does not point to a file", error)

    def test_configured_executable_failure_is_not_static_success(self) -> None:
        with mock.patch.object(conformance, "_invoke", side_effect=OSError("cannot start candidate")):
            status, output, error = self.run_conformance([], sys.executable)
        self.assertEqual(status, 1)
        self.assertEqual(output, "")
        self.assertIn("cannot start candidate", error)

    def test_required_mode_runs_every_existing_observer(self) -> None:
        with mock.patch.object(conformance, "observe_read_projection_parity", return_value=[]) as reads:
            with mock.patch.object(conformance, "observe_onboarding_projection_parity", return_value=[]) as onboarding:
                with mock.patch.object(conformance, "observe_existing_install_projection_parity", return_value=[]) as journey:
                    status, output, error = self.run_conformance(["--require-executable"], sys.executable)
        self.assertEqual(status, 0, error)
        self.assertIn("executable query/journey parity passed", output)
        reads.assert_called_once_with()
        onboarding.assert_called_once_with()
        journey.assert_called_once_with()

    def test_observers_do_not_silently_pass_without_an_executable(self) -> None:
        with mock.patch.dict(os.environ, {"FACMAN_CLI_EXE": ""}):
            for observer in (
                conformance.observe_read_projection_parity,
                conformance.observe_onboarding_projection_parity,
                conformance.observe_existing_install_projection_parity,
            ):
                with self.subTest(observer=observer.__name__):
                    with self.assertRaisesRegex(ValueError, "required_blocked"):
                        observer()

    def test_missing_candidate_is_classified_by_existing_obligation_runner(self) -> None:
        policy = test_obligations.load_policy()
        suite = unittest.TestSuite(
            CrossFrontendJourneyConformanceTests(name)
            for name in (
                "test_available_cli_proves_normalized_read_parity",
                "test_available_cli_proves_existing_install_projection_parity",
                "test_available_cli_proves_onboarding_projection_parity",
            )
        )
        with mock.patch.dict(os.environ, {"FACMAN_CLI_EXE": ""}):
            result = unittest.TextTestRunner(
                stream=io.StringIO(),
                resultclass=lambda *args, **kwargs: test_obligations.ObligationResult(
                    *args, policy=policy, **kwargs
                ),
            ).run(suite)
        self.assertEqual(len(result.classified_skips), 3)
        self.assertTrue(all(item["classification"] == "required_blocked" for item in result.classified_skips))
        self.assertGreater(len(result.classified_skips), policy["profiles"]["promotion"]["required_skip_limit"])

    def test_refused_query_is_a_failure_for_every_transport(self) -> None:
        refused = subprocess.CompletedProcess([], 1, '{"error":"refused"}', "")
        with mock.patch.dict(os.environ, {"FACMAN_CLI_EXE": sys.executable}):
            with mock.patch.object(conformance, "_invoke", return_value=refused):
                problems = conformance.observe_read_projection_parity()
        self.assertEqual(len(problems), 4)
        self.assertTrue(all("query failed rc=1" in problem for problem in problems))


class FixtureTreeObservationTests(unittest.TestCase):
    def test_all_fixture_bytes_and_empty_directories_are_observed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman-conformance-tree-") as temporary:
            root = Path(temporary) / "fixture"
            conformance._write_installation_fixture(root)
            baseline = conformance.fixture_tree_snapshot(root)
            self.assertEqual(baseline, conformance.fixture_tree_snapshot(root))
            for relative in ("config-path.cfg", "data/base/info.json"):
                path = root / relative
                original = path.read_bytes()
                path.write_bytes(original + b"changed")
                self.assertNotEqual(baseline, conformance.fixture_tree_snapshot(root))
                path.write_bytes(original)
            extra = root / "unexpected-directory"
            extra.mkdir()
            self.assertNotEqual(baseline, conformance.fixture_tree_snapshot(root))
            extra.rmdir()
            added = root / "unexpected-file"
            added.write_bytes(b"unexpected")
            self.assertNotEqual(baseline, conformance.fixture_tree_snapshot(root))
            added.unlink()
            (root / "config-path.cfg").unlink()
            self.assertNotEqual(baseline, conformance.fixture_tree_snapshot(root))

    def test_large_fixture_file_is_refused_before_reading(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman-conformance-tree-limit-") as temporary:
            root = Path(temporary)
            with (root / "oversize").open("wb") as handle:
                handle.truncate(4 * 1024 * 1024 + 1)
            with self.assertRaisesRegex(ValueError, "file size limit"):
                conformance.fixture_tree_snapshot(root)

    def test_link_target_is_observed_without_traversal(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman-conformance-tree-link-") as temporary:
            root = Path(temporary) / "fixture"
            root.mkdir()
            link = root / "link"
            link.touch()
            original_is_symlink = Path.is_symlink
            with mock.patch.object(Path, "is_symlink", lambda path: path == link or original_is_symlink(path)):
                with mock.patch.object(conformance.os, "readlink", return_value="outside-fixture"):
                    snapshot = conformance.fixture_tree_snapshot(root)
            self.assertEqual(snapshot["link"][0], "link")
            self.assertEqual(snapshot["link"][2], "outside-fixture")
            self.assertEqual(len(snapshot), 2)

    def test_snapshot_entry_budget_is_enforced_before_visiting_children(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman-conformance-entry-limit-") as temporary:
            root = Path(temporary)
            children = (root / str(index) for index in range(1024))
            with mock.patch.object(Path, "iterdir", return_value=children):
                with self.assertRaisesRegex(ValueError, "entry limit"):
                    conformance.fixture_tree_snapshot(root)

    def test_snapshot_total_content_budget_is_enforced(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman-conformance-content-limit-") as temporary:
            root = Path(temporary)
            for index in range(5):
                with (root / str(index)).open("wb") as handle:
                    handle.truncate(4 * 1024 * 1024)
            with self.assertRaisesRegex(ValueError, "total byte limit"):
                conformance.fixture_tree_snapshot(root)


if __name__ == "__main__":
    unittest.main()
