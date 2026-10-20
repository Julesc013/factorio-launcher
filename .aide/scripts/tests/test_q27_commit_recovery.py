from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = REPO_ROOT / ".aide/scripts/aide_lite.py"
SPEC = importlib.util.spec_from_file_location("aide_lite_q27", MODULE_PATH)
aide_lite = importlib.util.module_from_spec(SPEC)
sys.modules["aide_lite_q27"] = aide_lite
assert SPEC.loader is not None
SPEC.loader.exec_module(aide_lite)


class Q27CommitRecoveryTests(unittest.TestCase):
    def test_review_date_allows_ahead_of_utc_civil_timezones(self) -> None:
        self.assertEqual(
            aide_lite.latest_possible_local_review_date(datetime(2026, 9, 24, 22, 0, tzinfo=timezone.utc)).isoformat(),
            "2026-09-25",
        )
        self.assertEqual(
            aide_lite.latest_possible_local_review_date(datetime(2026, 9, 24, 8, 0, tzinfo=timezone.utc)).isoformat(),
            "2026-09-24",
        )

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

    def make_commit_fixture(self) -> tuple[tempfile.TemporaryDirectory[str], Path, str, str, list[aide_lite.Check]]:
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        subprocess.run(["git", "init", "--quiet", str(root)], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.name", "AIDE Fixture"], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.email", "fixture@example.invalid"], check=True)
        (root / "fixture.txt").write_text("base\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "fixture.txt"], check=True)
        subprocess.run(
            ["git", "-C", str(root), "commit", "--quiet", "-m", "fixture base"],
            check=True,
        )
        (root / "fixture.txt").write_text("historical\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "fixture.txt"], check=True)
        message = aide_lite.COMMIT_GOOD_EXAMPLE.replace(
            "- `py -3 .aide/scripts/aide_lite.py commit check --message-file fixture`: PASS.",
            "- Validation was recorded historically without a recognized outcome label.",
        )
        message_path = root / "message.txt"
        message_path.write_text(message, encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(root), "commit", "--quiet", "-F", str(message_path)],
            check=True,
        )
        commit_hash = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        ).stdout.strip()
        committed_message = aide_lite.git_commit_messages_for_range(root, "HEAD^..HEAD")[0][2]
        checks = aide_lite.validate_commit_message_text(committed_message)
        self.assertEqual(aide_lite.commit_message_result(checks), "FAIL")
        return temp, root, commit_hash, committed_message, checks

    def accepted_disposition(
        self,
        root: Path,
        commit_hash: str,
        message: str,
        checks: list[aide_lite.Check],
    ) -> dict[str, object]:
        facts = aide_lite.git_commit_object_facts(root, commit_hash)
        policy_path = root / aide_lite.COMMIT_MESSAGE_DISPOSITION_POLICY_PATH
        decision_path = root / ".aide/queue/FIXTURE/evidence/decision.json"
        evidence_path = root / ".aide/queue/FIXTURE/evidence/validation.md"
        decision_path.parent.mkdir(parents=True, exist_ok=True)
        policy_path.parent.mkdir(parents=True, exist_ok=True)
        policy_path.write_text(
            "decision:\n"
            "  authorized_reviewers:\n"
            "    - owner:fixture\n"
            "  decision_window_start: 2026-01-01\n",
            encoding="utf-8",
        )
        decision_path.write_text(
            aide_lite.stable_json_text(
                {
                    "schema_version": "aide.commit-message-disposition-decision.v1",
                    "disposition_id": "fixture-historical-message",
                    "status": "accepted",
                    "commit": commit_hash,
                    "tree": facts["tree"],
                    "message_sha256": aide_lite.canonical_commit_message_sha256(message),
                    "scope": "historical_commit_message_only",
                    "decision": "accept_historical_nonconformance",
                    "reviewed_by": "owner:fixture",
                    "reviewed_at": "2026-09-22",
                }
            ),
            encoding="utf-8",
        )
        evidence_path.write_text("# Validation\n\nFixture evidence.\n", encoding="utf-8")
        record: dict[str, object] = {
            "schema_version": "aide.commit-message-disposition.v1",
            "disposition_id": "fixture-historical-message",
            "status": "accepted",
            "commit": commit_hash,
            "tree": facts["tree"],
            "parents": facts["parents"],
            "message_sha256": aide_lite.canonical_commit_message_sha256(message),
            "failed_checks": [check.message for check in checks if check.severity == "FAIL"],
            "scope": "historical_commit_message_only",
            "decision": "accept_historical_nonconformance",
            "reviewed_by": "owner:fixture",
            "reviewed_at": "2026-09-22",
            "decision_ref": {
                "path": ".aide/queue/FIXTURE/evidence/decision.json",
                "sha256": aide_lite.sha256_file(decision_path),
            },
            "evidence": [
                {
                    "path": ".aide/queue/FIXTURE/evidence/validation.md",
                    "sha256": aide_lite.sha256_file(evidence_path),
                }
            ],
        }
        record["record_digest"] = aide_lite.historical_disposition_record_digest(record)
        return record

    def test_git_replacement_cannot_change_checked_message_or_traversal(self) -> None:
        temp, root, commit_hash, message, _checks = self.make_commit_fixture()
        self.addCleanup(temp.cleanup)
        facts = aide_lite.git_commit_object_facts(root, commit_hash)
        command = ["git", "-C", str(root), "commit-tree", str(facts["tree"])]
        for parent in facts["parents"]:
            command.extend(["-p", str(parent)])
        replacement = subprocess.run(
            command,
            check=True,
            input=aide_lite.COMMIT_GOOD_EXAMPLE,
            capture_output=True,
            text=True,
            encoding="utf-8",
        ).stdout.strip()
        subprocess.run(["git", "-C", str(root), "replace", commit_hash, replacement], check=True)

        checked = aide_lite.git_commit_messages_for_range(root, "HEAD^..HEAD")
        self.assertEqual([item[0] for item in checked], [commit_hash])
        self.assertEqual(checked[0][2], message)
        self.assertEqual(aide_lite.commit_message_result(aide_lite.validate_commit_message_text(checked[0][2])), "FAIL")

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = aide_lite.main(
                ["--repo-root", str(root), "commit", "check", "--range", "HEAD^..HEAD", "--no-dispositions"]
            )
        self.assertEqual(code, 1, output.getvalue())
        self.assertIn(f"- {commit_hash[:7]} FAIL", output.getvalue())

    def test_range_disposition_preserves_raw_failure_and_requires_acceptance(self) -> None:
        temp, root, commit_hash, message, checks = self.make_commit_fixture()
        self.addCleanup(temp.cleanup)
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = aide_lite.main(["--repo-root", str(root), "commit", "check", "--range", "HEAD^..HEAD"])
        self.assertEqual(code, 1)
        self.assertIn("result: FAIL", buffer.getvalue())

        record = self.accepted_disposition(root, commit_hash, message, checks)
        registry_path = root / aide_lite.COMMIT_MESSAGE_DISPOSITIONS_PATH
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        registry_path.write_text(
            aide_lite.stable_json_text(
                {
                    "schema_version": "aide.commit-message-dispositions.v1",
                    "records": [record],
                }
            ),
            encoding="utf-8",
        )
        accepted = io.StringIO()
        with contextlib.redirect_stdout(accepted):
            code = aide_lite.main(["--repo-root", str(root), "commit", "check", "--range", "HEAD^..HEAD"])
        self.assertEqual(code, 0, accepted.getvalue())
        self.assertIn("result: PASS_WITH_DISPOSITIONS", accepted.getvalue())
        self.assertIn("DISPOSITIONED", accepted.getvalue())
        self.assertIn("original_failure:", accepted.getvalue())

        raw = io.StringIO()
        with contextlib.redirect_stdout(raw):
            code = aide_lite.main(
                ["--repo-root", str(root), "commit", "check", "--range", "HEAD^..HEAD", "--no-dispositions"]
            )
        self.assertEqual(code, 1)
        self.assertIn("result: FAIL", raw.getvalue())
        self.assertNotIn("DISPOSITIONED", raw.getvalue())

    def test_disposition_rejects_altered_exact_identity_and_decision_fields(self) -> None:
        temp, root, commit_hash, message, checks = self.make_commit_fixture()
        self.addCleanup(temp.cleanup)
        baseline = self.accepted_disposition(root, commit_hash, message, checks)
        mutations = {
            "commit": "*",
            "tree": "0" * 40,
            "parents": ["0" * 40],
            "message_sha256": "0" * 64,
            "failed_checks": ["different failure"],
            "scope": "all_commits",
            "decision": "ignore_failure",
            "reviewed_by": "",
            "reviewed_at": "not-a-date",
            "decision_ref": {"path": "../outside.md", "sha256": "0" * 64},
            "evidence": [],
            "record_digest": "0" * 64,
        }
        for key, value in mutations.items():
            with self.subTest(field=key):
                record = dict(baseline)
                record[key] = value
                if key != "record_digest":
                    record["record_digest"] = aide_lite.historical_disposition_record_digest(record)
                result = aide_lite.evaluate_historical_commit_disposition(
                    root,
                    commit_hash,
                    message,
                    checks,
                    {
                        "schema_version": "aide.commit-message-dispositions.v1",
                        "records": [record],
                    },
                )
                self.assertNotEqual(result["status"], "accepted", result)
                self.assertTrue(result["errors"], result)

    def test_disposition_rejects_tampered_evidence_duplicate_and_unknown_fields(self) -> None:
        temp, root, commit_hash, message, checks = self.make_commit_fixture()
        self.addCleanup(temp.cleanup)
        record = self.accepted_disposition(root, commit_hash, message, checks)

        evidence_path = root / str(record["evidence"][0]["path"])
        evidence_path.write_text("tampered\n", encoding="utf-8")
        tampered = aide_lite.evaluate_historical_commit_disposition(
            root,
            commit_hash,
            message,
            checks,
            {"schema_version": "aide.commit-message-dispositions.v1", "records": [record]},
        )
        self.assertEqual(tampered["status"], "invalid")
        self.assertTrue(any("sha256 does not match" in error for error in tampered["errors"]))

        duplicate = aide_lite.evaluate_historical_commit_disposition(
            root,
            commit_hash,
            message,
            checks,
            {"schema_version": "aide.commit-message-dispositions.v1", "records": [record, record]},
        )
        self.assertEqual(duplicate["status"], "missing")
        self.assertTrue(any("multiple disposition records" in error for error in duplicate["errors"]))

        evidence_path.write_text("# Validation\n\nFixture evidence.\n", encoding="utf-8")
        unknown = dict(record)
        unknown["wildcard"] = True
        unknown["record_digest"] = aide_lite.historical_disposition_record_digest(unknown)
        unsupported = aide_lite.evaluate_historical_commit_disposition(
            root,
            commit_hash,
            message,
            checks,
            {"schema_version": "aide.commit-message-dispositions.v1", "records": [unknown]},
        )
        self.assertEqual(unsupported["status"], "invalid")
        self.assertTrue(any("unsupported fields" in error for error in unsupported["errors"]))

    def test_entire_registry_must_be_valid_before_a_match_can_apply(self) -> None:
        temp, root, commit_hash, message, checks = self.make_commit_fixture()
        self.addCleanup(temp.cleanup)
        record = self.accepted_disposition(root, commit_hash, message, checks)
        bad_registries = [
            [record, "not-an-object"],
            [record, {"disposition_id": "incomplete"}],
        ]
        duplicate_id = dict(record)
        duplicate_id["commit"] = str(record["parents"][0])
        duplicate_id["record_digest"] = aide_lite.historical_disposition_record_digest(duplicate_id)
        bad_registries.append([record, duplicate_id])
        for records in bad_registries:
            with self.subTest(records=records):
                result = aide_lite.evaluate_historical_commit_disposition(
                    root,
                    commit_hash,
                    message,
                    checks,
                    {"schema_version": "aide.commit-message-dispositions.v1", "records": records},
                )
                self.assertFalse(result["effective"], result)
                self.assertEqual(result["status"], "invalid", result)
                self.assertTrue(any("records[1]" in error for error in result["errors"]), result)

    def test_acceptance_requires_exact_structured_authority_and_current_date(self) -> None:
        temp, root, commit_hash, message, checks = self.make_commit_fixture()
        self.addCleanup(temp.cleanup)
        baseline = self.accepted_disposition(root, commit_hash, message, checks)

        decision_path = root / str(baseline["decision_ref"]["path"])
        request_text = "# Decision request\n\nThis is not an acceptance.\n"
        decision_path.write_text(request_text, encoding="utf-8")
        request_record = dict(baseline)
        request_record["decision_ref"] = {
            "path": str(baseline["decision_ref"]["path"]),
            "sha256": aide_lite.sha256_file(decision_path),
        }
        request_record["record_digest"] = aide_lite.historical_disposition_record_digest(request_record)
        request_result = aide_lite.evaluate_historical_commit_disposition(
            root,
            commit_hash,
            message,
            checks,
            {"schema_version": "aide.commit-message-dispositions.v1", "records": [request_record]},
        )
        self.assertFalse(request_result["effective"], request_result)
        self.assertTrue(any("structured JSON" in error for error in request_result["errors"]), request_result)

        baseline = self.accepted_disposition(root, commit_hash, message, checks)
        decision = json.loads(decision_path.read_text(encoding="utf-8"))
        for reviewed_by, reviewed_at, expected in [
            ("owner:untrusted", "2026-09-22", "authorized_reviewers"),
            ("owner:fixture", "9999-12-31", "future"),
        ]:
            with self.subTest(reviewed_by=reviewed_by, reviewed_at=reviewed_at):
                altered_decision = dict(decision)
                altered_decision["reviewed_by"] = reviewed_by
                altered_decision["reviewed_at"] = reviewed_at
                decision_path.write_text(aide_lite.stable_json_text(altered_decision), encoding="utf-8")
                altered_record = dict(baseline)
                altered_record["reviewed_by"] = reviewed_by
                altered_record["reviewed_at"] = reviewed_at
                altered_record["decision_ref"] = {
                    "path": str(baseline["decision_ref"]["path"]),
                    "sha256": aide_lite.sha256_file(decision_path),
                }
                altered_record["record_digest"] = aide_lite.historical_disposition_record_digest(altered_record)
                result = aide_lite.evaluate_historical_commit_disposition(
                    root,
                    commit_hash,
                    message,
                    checks,
                    {"schema_version": "aide.commit-message-dispositions.v1", "records": [altered_record]},
                )
                self.assertFalse(result["effective"], result)
                self.assertTrue(any(expected in error for error in result["errors"]), result)

    def test_proposed_disposition_is_visible_but_ineffective(self) -> None:
        temp, root, commit_hash, message, checks = self.make_commit_fixture()
        self.addCleanup(temp.cleanup)
        record = self.accepted_disposition(root, commit_hash, message, checks)
        record["status"] = "proposed"
        record["record_digest"] = aide_lite.historical_disposition_record_digest(record)
        result = aide_lite.evaluate_historical_commit_disposition(
            root,
            commit_hash,
            message,
            checks,
            {"schema_version": "aide.commit-message-dispositions.v1", "records": [record]},
        )
        self.assertEqual(result["status"], "proposed")
        self.assertFalse(result["effective"])

    def test_source_disposition_registry_is_not_exportable(self) -> None:
        self.assertTrue(aide_lite.is_forbidden_export_path(aide_lite.COMMIT_MESSAGE_DISPOSITIONS_PATH))


if __name__ == "__main__":
    unittest.main()
