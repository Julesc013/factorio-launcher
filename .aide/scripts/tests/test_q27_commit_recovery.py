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
        classification, checks = aide_lite.classify_commit_message_text(aide_lite.COMMIT_GOOD_EXAMPLE)
        self.assertEqual(classification, "legacy_structured_v0")
        self.assertEqual(aide_lite.commit_message_result(checks), "WARN")

    def test_compact_subject_only_documentation_commit_passes(self) -> None:
        message = "docs(docs): correct preview support status\n\nWork-Item: FACMAN-DOCS-STATUS-01\n"
        classification, checks = aide_lite.classify_commit_message_text(message)
        self.assertEqual(classification, "compact_v1")
        self.assertEqual(aide_lite.commit_message_result(checks), "PASS")

    def test_compact_rationale_bearing_implementation_commit_passes(self) -> None:
        message = """fix(transport): reject mismatched backend responses

Treat post-dispatch identity mismatches as outcome unknown so callers
cannot manufacture success after an ambiguous backend result.

Work-Item: FACMAN-TRANSPORT-HARDENING-01
Evidence-Ref: .aide/evidence/FACMAN-TRANSPORT-HARDENING-01.json
"""
        self.assertEqual(self.result_for(message), "PASS")

    def test_compact_high_risk_commit_passes(self) -> None:
        message = """security(workspace): bind mutation to root ownership

Foreign, linked, changed, or inconclusive roots must not receive implicit
mutation authority. Require a verified ownership marker before persistence.

The adoption path remains explicit and reversible.

Work-Item: FACMAN-WORKSPACE-ROOT-AUTHORITY-01
Evidence-Ref: docs/security/workspace-root-authority.md
"""
        self.assertEqual(self.result_for(message), "PASS")

    def test_invalid_commit_type_fails(self) -> None:
        message = aide_lite.COMMIT_GOOD_EXAMPLE.replace("policy(aide):", "random(aide):")
        self.assertEqual(self.result_for(message), "FAIL")

    def test_vague_summary_fails(self) -> None:
        message = aide_lite.COMMIT_GOOD_EXAMPLE.replace(
            "policy(aide): define structured commit recovery",
            "policy(aide): update",
        )
        self.assertEqual(self.result_for(message), "FAIL")

    def test_compact_vague_summaries_fail(self) -> None:
        for summary in ("update", "misc", "wip", "changes"):
            with self.subTest(summary=summary):
                message = f"docs(docs): {summary}\n\nWork-Item: FACMAN-DOCS-STATUS-01\n"
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

    def test_compact_h2_heading_fails(self) -> None:
        message = """docs(docs): record preview status

## Summary

The status is current.

Work-Item: FACMAN-DOCS-STATUS-01
"""
        self.assertEqual(self.result_for(message), "FAIL")

    def test_compact_body_over_thirty_nonblank_lines_fails(self) -> None:
        rationale = "\n".join(f"Rationale line {index}." for index in range(1, 32))
        message = f"docs(docs): record extended preview rationale\n\n{rationale}\n\nWork-Item: FACMAN-DOCS-STATUS-01\n"
        self.assertEqual(self.result_for(message), "FAIL")

    def test_compact_body_between_thirteen_and_thirty_lines_warns(self) -> None:
        rationale = "\n".join(f"Rationale line {index}." for index in range(1, 14))
        message = f"docs(docs): record extended preview rationale\n\n{rationale}\n\nWork-Item: FACMAN-DOCS-STATUS-01\n"
        self.assertEqual(self.result_for(message), "WARN")

    def test_missing_work_item_fails_for_compact_managed_work(self) -> None:
        message = "docs(docs): record preview support status\n"
        self.assertEqual(self.result_for(message), "FAIL")

    def test_evidence_reference_is_optional(self) -> None:
        message = "docs(docs): record preview support status\n\nWork-Item: FACMAN-DOCS-STATUS-01\n"
        self.assertEqual(self.result_for(message), "PASS")

    def test_compact_commit_does_not_require_copied_validation(self) -> None:
        message = """fix(transport): preserve ambiguous backend outcome

Treat transport loss after dispatch as outcome unknown.

Work-Item: FACMAN-TRANSPORT-HARDENING-01
"""
        self.assertEqual(self.result_for(message), "PASS")

    def test_unknown_well_formed_scope_warns_instead_of_failing(self) -> None:
        message = "docs(new-surface): record preview support status\n\nWork-Item: FACMAN-DOCS-STATUS-01\n"
        self.assertEqual(self.result_for(message), "WARN")

    def test_trailer_parsing(self) -> None:
        trailers = aide_lite.parse_commit_trailers(aide_lite.COMMIT_GOOD_EXAMPLE)
        self.assertEqual(trailers["AIDE-Task"], "Q27-commit-discipline-workunit-recovery-v0")
        self.assertEqual(trailers["AIDE-Phase"], "Q27")

    def test_commit_check_inline_command(self) -> None:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = aide_lite.main(["commit", "check", "--message", aide_lite.COMMIT_GOOD_EXAMPLE])
        self.assertEqual(code, 0)
        self.assertIn("result: WARN", buffer.getvalue())
        self.assertIn("format: legacy_structured_v0", buffer.getvalue())

    def test_facman_overlay_loads_after_imported_policy(self) -> None:
        profile = aide_lite.load_commit_message_profile(REPO_ROOT)
        self.assertEqual(profile.profile_id, "facman-compact-history-v1")
        self.assertEqual(profile.generated_format, "compact_v1")
        self.assertEqual(profile.template_path, aide_lite.FACMAN_COMMIT_TEMPLATE_PATH)
        self.assertIn("feat", profile.generated_types)
        self.assertIn("policy", profile.accepted_types)

    def test_commit_policy_baseline_loads_explicit_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            aide_lite.write_text(
                root / aide_lite.COMMIT_POLICY_BASELINE_PATH,
                """schema = "facman.aide_commit_policy_baseline.v1"
reason = "Fixture baseline."

[[commit]]
sha = "00b8a40"
subject = "test(mods): add local Factorio mod ZIP fixture matrix"
reason = "Published before current commit-body gate."
""",
            )
            entries = aide_lite.load_commit_policy_baseline(root)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].sha, "00b8a40")
        self.assertEqual(entries[0].subject, "test(mods): add local Factorio mod ZIP fixture matrix")

    def test_commit_range_baseline_acknowledges_only_matching_history(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            aide_lite.write_text(
                root / aide_lite.COMMIT_POLICY_BASELINE_PATH,
                """schema = "facman.aide_commit_policy_baseline.v1"
reason = "Fixture baseline."

[[commit]]
sha = "00b8a40"
subject = "test(mods): add local Factorio mod ZIP fixture matrix"
reason = "Published before current commit-body gate."
""",
            )
            commits = [
                (
                    "00b8a40f00d11111111111111111111111111111",
                    "test(mods): add local Factorio mod ZIP fixture matrix",
                    "test(mods): add local Factorio mod ZIP fixture matrix\n",
                )
            ]
            results, any_fail, baseline_count = aide_lite.validate_commit_range_messages(root, commits)
        self.assertFalse(any_fail)
        self.assertEqual(baseline_count, 1)
        self.assertEqual(results[0][2], "BASELINE")

    def test_commit_range_baseline_does_not_waive_new_bad_commits(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            aide_lite.write_text(
                root / aide_lite.COMMIT_POLICY_BASELINE_PATH,
                """schema = "facman.aide_commit_policy_baseline.v1"
reason = "Fixture baseline."

[[commit]]
sha = "00b8a40"
subject = "test(mods): add local Factorio mod ZIP fixture matrix"
reason = "Published before current commit-body gate."
""",
            )
            commits = [
                (
                    "1234567f00d11111111111111111111111111111",
                    "test(mods): add local Factorio mod ZIP fixture matrix",
                    "test(mods): add local Factorio mod ZIP fixture matrix\n",
                )
            ]
            results, any_fail, baseline_count = aide_lite.validate_commit_range_messages(root, commits)
        self.assertTrue(any_fail)
        self.assertEqual(baseline_count, 0)
        self.assertEqual(results[0][2], "FAIL")

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
        template = aide_lite.read_text(REPO_ROOT / aide_lite.FACMAN_COMMIT_TEMPLATE_PATH)
        self.assertIn("commit check --message-file", hook)
        self.assertIn("provider", hook.lower())
        self.assertIn("network", hook.lower())
        self.assertIn("Work-Item:", template)
        self.assertNotIn("## ", template)
        self.assertNotIn("AIDE-Result:", template)
        self.assertNotIn("OPENAI_API_KEY=", hook)
        self.assertNotIn("BEGIN PRIVATE KEY", template)

    def test_changelog_preview_json_shape_from_fixture(self) -> None:
        data = aide_lite.make_changelog_preview(REPO_ROOT, revision_range="HEAD~1..HEAD")
        self.assertEqual(data["schema_version"], "aide.changelog-preview.v0")
        self.assertIn("malformed_commits", data)
        json.dumps(data)


if __name__ == "__main__":
    unittest.main()
