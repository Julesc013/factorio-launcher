from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = REPO_ROOT / ".aide/scripts/aide_lite.py"
SPEC = importlib.util.spec_from_file_location("aide_lite_q27", MODULE_PATH)
aide_lite = importlib.util.module_from_spec(SPEC)
sys.modules["aide_lite_q27"] = aide_lite
assert SPEC.loader is not None
SPEC.loader.exec_module(aide_lite)


class Q27CommitRecoveryTests(unittest.TestCase):
    def result_for(self, message: str) -> str:
        return aide_lite.commit_message_result(aide_lite.validate_commit_message_text(message))

    def test_valid_commit_message_passes(self) -> None:
        self.assertEqual(self.result_for(aide_lite.COMMIT_GOOD_EXAMPLE), "PASS")

    def test_invalid_commit_type_fails(self) -> None:
        message = aide_lite.COMMIT_GOOD_EXAMPLE.replace("policy(aide):", "random(aide):")
        self.assertEqual(self.result_for(message), "FAIL")

    def test_vague_summary_fails(self) -> None:
        message = aide_lite.COMMIT_GOOD_EXAMPLE.replace(
            "policy(aide): define structured commit recovery",
            "policy(aide): update",
        )
        self.assertEqual(self.result_for(message), "FAIL")

    def test_too_long_subject_fails(self) -> None:
        message = aide_lite.COMMIT_GOOD_EXAMPLE.replace(
            "policy(aide): define structured commit recovery",
            "policy(aide): " + "x" * 80,
        )
        self.assertEqual(self.result_for(message), "FAIL")

    def test_missing_heading_fails(self) -> None:
        message = aide_lite.COMMIT_GOOD_EXAMPLE.replace("## Validation", "## Checks")
        self.assertEqual(self.result_for(message), "FAIL")

    def test_missing_changelog_category_fails(self) -> None:
        message = aide_lite.COMMIT_GOOD_EXAMPLE.replace("- Added:", "- Unknown:")
        self.assertEqual(self.result_for(message), "FAIL")

    def test_trailer_parsing(self) -> None:
        trailers = aide_lite.parse_commit_trailers(aide_lite.COMMIT_GOOD_EXAMPLE)
        self.assertEqual(trailers["AIDE-Task"], "Q27-commit-discipline-workunit-recovery-v0")
        self.assertEqual(trailers["AIDE-Phase"], "Q27")

    def test_commit_check_inline_command(self) -> None:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = aide_lite.main(["commit", "check", "--message", aide_lite.COMMIT_GOOD_EXAMPLE])
        self.assertEqual(code, 0)
        self.assertIn("result: PASS", buffer.getvalue())

    def test_changelog_preview_groups_and_reports_malformed(self) -> None:
        data = {
            "schema_version": "aide.changelog-preview.v0",
            "source_range": "fixture",
            "commit_count": 2,
            "categories": {
                "Added": [
                    {
                        "commit": "abc123",
                        "subject": "policy(aide): define structured commit recovery",
                        "entry": "commit-message enforcement.",
                    }
                ]
            },
            "malformed_commits": [{"commit": "bad", "subject": "update", "reason": "vague"}],
        }
        rendered = aide_lite.render_changelog_preview(data)
        self.assertIn("## Added", rendered)
        self.assertIn("Malformed Commits", rendered)
        self.assertIn("release_publishing: false", rendered)

    def test_task_complete_fixture_returns_noop(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            aide_lite.write_text(
                root / ".aide/queue/index.yaml",
                """items:
  - id: TASK-1
    status: passed
    task: .aide/queue/TASK-1/task.yaml
    evidence: .aide/queue/TASK-1/evidence
""",
            )
            aide_lite.write_text(root / ".aide/queue/TASK-1/task.yaml", "id: TASK-1\nacceptance:\n  - done\n")
            aide_lite.write_text(root / ".aide/queue/TASK-1/status.yaml", "status: passed\n")
            aide_lite.write_text(root / ".aide/queue/TASK-1/evidence/changed-files.md", "# Changed\n")
            aide_lite.write_text(root / ".aide/queue/TASK-1/evidence/validation.md", "# Validation\n- PASS\n")
            aide_lite.write_text(root / ".aide/queue/TASK-1/evidence/remaining-risks.md", "# Risks\n- None\n")
            inspection = aide_lite.inspect_task(root, "TASK-1")
        self.assertEqual(inspection["classification"], "complete")
        self.assertEqual(aide_lite.task_recovery_suggestion(inspection), "noop_already_complete")

    def test_task_partial_fixture_suggests_resume(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            aide_lite.write_text(root / ".aide/queue/TASK-2/task.yaml", "id: TASK-2\n")
            aide_lite.write_text(root / ".aide/queue/TASK-2/status.yaml", "status: running\n")
            aide_lite.write_text(root / ".aide/queue/TASK-2/evidence/changed-files.md", "# Changed\n")
            inspection = aide_lite.inspect_task(root, "TASK-2")
        self.assertEqual(inspection["classification"], "partial")
        self.assertEqual(aide_lite.task_recovery_suggestion(inspection), "continue_from_status_and_evidence")

    def test_task_short_id_resolves_from_queue_index(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            aide_lite.write_text(
                root / ".aide/queue/index.yaml",
                """items:
  - id: Q28-git-workflow-policy-v0
    status: superseded
    task: .aide/queue/Q28-git-workflow-policy-v0/task.yaml
    evidence: .aide/queue/Q28-git-workflow-policy-v0/evidence
""",
            )
            aide_lite.write_text(root / ".aide/queue/Q28-git-workflow-policy-v0/task.yaml", "id: Q28-git-workflow-policy-v0\n")
            aide_lite.write_text(root / ".aide/queue/Q28-git-workflow-policy-v0/status.yaml", "status: superseded\n")
            inspection = aide_lite.inspect_task(root, "Q28")
        self.assertEqual(inspection["requested_task_id"], "Q28")
        self.assertEqual(inspection["task_id"], "Q28-git-workflow-policy-v0")
        self.assertEqual(inspection["classification"], "partial")

    def test_hook_and_template_have_no_live_external_behavior(self) -> None:
        hook = aide_lite.read_text(REPO_ROOT / ".aide/hooks/commit-msg")
        template = aide_lite.read_text(REPO_ROOT / ".aide/git/commit-template.md")
        self.assertIn("commit check --message-file", hook)
        self.assertIn("provider", hook.lower())
        self.assertIn("network", hook.lower())
        self.assertIn("## Changelog", template)
        self.assertNotIn("OPENAI_API_KEY=", hook)
        self.assertNotIn("BEGIN PRIVATE KEY", template)

    def test_changelog_preview_json_shape_from_fixture(self) -> None:
        data = aide_lite.make_changelog_preview(REPO_ROOT, revision_range="HEAD~1..HEAD")
        self.assertEqual(data["schema_version"], "aide.changelog-preview.v0")
        self.assertIn("malformed_commits", data)
        json.dumps(data)


if __name__ == "__main__":
    unittest.main()
