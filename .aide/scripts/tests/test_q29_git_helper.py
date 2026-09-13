from __future__ import annotations

import importlib.util
import base64
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = REPO_ROOT / ".aide/scripts/aide_lite.py"
SPEC = importlib.util.spec_from_file_location("aide_lite_q29", MODULE_PATH)
aide_lite = importlib.util.module_from_spec(SPEC)
sys.modules["aide_lite_q29"] = aide_lite
assert SPEC.loader is not None
SPEC.loader.exec_module(aide_lite)
TEST_KEY_DIR = tempfile.TemporaryDirectory()
TEST_PRIVATE_KEY = Path(TEST_KEY_DIR.name) / "attestation-private.pem"
TEST_PUBLIC_KEY = Path(TEST_KEY_DIR.name) / "attestation-public.pem"
subprocess.run(["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(TEST_PRIVATE_KEY)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
subprocess.run(["openssl", "pkey", "-in", str(TEST_PRIVATE_KEY), "-pubout", "-out", str(TEST_PUBLIC_KEY)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
aide_lite.TRUSTED_WORKFLOW_PUBLIC_KEYS = {"test-fixture": TEST_PUBLIC_KEY.read_text(encoding="utf-8")}


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, data: dict[str, object]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(aide_lite.stable_json_text(data), encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_github_observation(path: Path, data: dict[str, object]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw_digest = hashlib.sha256(aide_lite.stable_json_text(data).encode("utf-8")).hexdigest()
    admitted = next((data[key] for key in ("head_oid", "commit_id", "merge_oid", "frontier_oid") if isinstance(data.get(key), str)), "a" * 40)
    now = datetime.now(timezone.utc)
    issued_at = (now - timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
    observed_at = now.isoformat().replace("+00:00", "Z")
    expires_at = (now + timedelta(days=7)).isoformat().replace("+00:00", "Z")
    provenance = {
        "source": "github_actions_artifact", "purpose": "facman.promotion-evidence.v1", "repository": "example/repo",
        "repository_id": 101, "actor_id": 202, "workflow_id": 303, "workflow_run_id": 303,
        "run_attempt": 1, "artifact_id": 404, "publisher": "task-to-dev-promotion-check",
        "ruleset_id": 505, "ruleset_version": "v1", "workflow_path": ".github/workflows/task-to-dev-promotion-check.yml",
        "workflow_ref": "example/repo/.github/workflows/task-to-dev-promotion-check.yml@main",
        "admitted_ref": "refs/heads/dev", "admitted_oid": admitted, "unique_id": raw_digest,
        "url": "https://github.com/example/repo/actions/runs/303", "observed_at": observed_at,
        "issued_at": issued_at, "expires_at": expires_at,
        "raw_payload_sha256": raw_digest, "artifact_sha256": raw_digest,
    }
    payload = {"provenance": provenance, "raw_payload": data}
    signing_input = path.with_suffix(path.suffix + ".signing-input")
    signature_path = path.with_suffix(path.suffix + ".signature")
    signing_input.write_bytes(aide_lite.stable_json_text(payload).encode("utf-8"))
    subprocess.run(["openssl", "dgst", "-sha256", "-sign", str(TEST_PRIVATE_KEY), "-out", str(signature_path), str(signing_input)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    signature = base64.b64encode(signature_path.read_bytes()).decode("ascii")
    signing_input.unlink(); signature_path.unlink()
    return write_json(path, {"schema_version": aide_lite.TRUSTED_WORKFLOW_ENVELOPE_SCHEMA, "key_id": "test-fixture", "payload": payload, "signature": signature})

def write_protected_merge_evidence(root: Path, external: Path) -> Path:
    """Make a hash-bound task-to-dev PR merge receipt outside the checkout."""
    base = git(root, "rev-parse", "dev")
    create_task_branch(root, "task/promotion", "promotion.txt")
    git(root, "checkout", "dev")
    git(root, "merge", "--no-ff", "task/promotion", "-m", "Promotion fixture (#7)")
    merge_oid = git(root, "rev-parse", "HEAD")
    parents = git(root, "show", "-s", "--format=%P", "HEAD").split()
    tree = git(root, "rev-parse", "HEAD^{tree}")
    commits = git(root, "rev-list", "--reverse", f"{parents[0]}..{parents[1]}").splitlines()
    pr = {
        "repository": "example/repo", "number": 7, "title": "Promotion fixture",
        "state": "closed", "draft": False, "merged": True, "base_ref": "dev",
        "base_oid": parents[0], "head_ref": "task/promotion", "head_oid": parents[1],
        "merge_oid": merge_oid,
    }
    protection = {
        "repository": "example/repo", "branch": "dev", "protected": True,
        "prior_base_oid": parents[0], "required_status": "task-to-dev-promotion-check",
    }
    status = {
        "schema_version": aide_lite.TASK_TO_DEV_STATUS_LEGACY_SCHEMA,
        "repository": "example/repo", "pull_request_number": 7,
        "base_oid": parents[0], "head_oid": parents[1],
        "range": f"{parents[0]}..{parents[1]}", "full_history_checked": True,
        "conclusion": "success", "commit_oids": commits,
    }
    record = {
        "repository": "example/repo", "pull_request_number": 7,
        "pull_request_title": "Promotion fixture", "state": "closed", "draft": False,
        "merged": True, "base_ref": "dev", "base_oid": parents[0],
        "head_ref": "task/promotion", "head_oid": parents[1], "merge_oid": merge_oid,
        "merge_tree": tree, "parents": parents,
        "raw": {
            "pull_request": {"path": str(external / "pr.json"), "sha256": write_github_observation(external / "pr.json", pr)},
            "protection": {"path": str(external / "protection.json"), "sha256": write_github_observation(external / "protection.json", protection)},
            "status": {"path": str(external / "status.json"), "sha256": write_github_observation(external / "status.json", status)},
        },
    }
    path = external / "merge-evidence.json"
    write_json(path, {"schema_version": aide_lite.VERIFIED_PROTECTED_PR_MERGE_SCHEMA, "repository": "example/repo", "merges": [record]})
    return path


def init_git_repo(root: Path) -> None:
    git(root, "init")
    git(root, "config", "user.email", "fixture@example.invalid")
    git(root, "config", "user.name", "Fixture User")
    git(root, "remote", "add", "origin", "https://github.com/example/repo.git")
    write(root, "README.md", "# Fixture\n")
    git(root, "add", "README.md")
    git(root, "commit", "-m", "initial")
    git(root, "branch", "-M", "main")
    git(root, "checkout", "-b", "dev")
    git(root, "checkout", "main")


def seed_helper_policy(root: Path) -> None:
    for rel in [
        *aide_lite.GIT_HELPER_POLICY_FILES,
        aide_lite.GIT_HELPER_COMMANDS_MD_PATH,
        aide_lite.COMMIT_MESSAGE_POLICY_PATH,
        aide_lite.FACMAN_COMMIT_MESSAGE_POLICY_PATH,
        aide_lite.VERIFIED_PROTECTED_PR_MERGE_SCHEMA_PATH,
        aide_lite.DEV_TO_MAIN_BOOTSTRAP_SCHEMA_PATH,
    ]:
        source = REPO_ROOT / rel
        if source.exists():
            aide_lite.write_text(root / rel, aide_lite.read_text(source))
    git(root, "add", ".aide")
    git(root, "commit", "-m", "seed aide helper policy")
    branches = set(git(root, "branch", "--format=%(refname:short)").splitlines())
    current = git(root, "branch", "--show-current")
    if "dev" in branches:
        git(root, "checkout", "dev")
        git(root, "merge", "--ff-only", current)
        git(root, "checkout", current)


def create_task_branch(root: Path, branch: str = "task/example", filename: str = "task.txt") -> None:
    git(root, "checkout", "dev")
    git(root, "checkout", "-b", branch)
    write(root, filename, f"{branch}\n")
    git(root, "add", filename)
    git(
        root,
        "commit",
        "-m",
        "fix(test): land fixture change\n\nWork-Item: TEST-Q29-LAND-1",
    )


def write_commit_plan_inputs(
    root: Path,
    evidence_root: Path,
    paths: list[str],
    *,
    work_item: str = "TEST-COMMIT-1",
) -> tuple[Path, Path]:
    changed_paths = []
    for rel in paths:
        git_blob_oid, error = aide_lite.helper_git_blob_oid(root, rel, index=False)
        if not git_blob_oid:
            raise AssertionError(f"could not bind fixture Git blob for {rel}: {error}")
        changed_paths.append({
            "path": rel,
            "state": "content",
            "sha256": aide_lite.sha256_file(root / rel),
            "git_blob_oid": git_blob_oid,
            "ownership": "task_owned",
        })
    snapshot_sha256 = aide_lite.helper_commit_snapshot_sha256(changed_paths)
    message_path = evidence_root / "commit-message.txt"
    message = (
        "fix(aide): validate classified commit snapshots\n\n"
        "Keep commit preparation distinct from integration gates.\n\n"
        f"Work-Item: {work_item}\n"
    )
    message_path.parent.mkdir(parents=True, exist_ok=True)
    message_path.write_text(message, encoding="utf-8")
    message_sha256 = hashlib.sha256(message_path.read_bytes()).hexdigest()
    review_path = evidence_root / "review.json"
    review = {
        "schema_version": aide_lite.GIT_COMMIT_REVIEW_SCHEMA,
        "verdict": "PASS",
        "branch": git(root, "branch", "--show-current"),
        "base_commit": git(root, "rev-parse", "HEAD"),
        "snapshot_sha256": snapshot_sha256,
        "message_sha256": message_sha256,
    }
    review_path.write_text(aide_lite.stable_json_text(review), encoding="utf-8")
    classification_path = evidence_root / "classification.json"
    classification = {
        "schema_version": aide_lite.GIT_COMMIT_CLASSIFICATION_SCHEMA,
        "branch": review["branch"],
        "base_commit": review["base_commit"],
        "work_item": work_item,
        "snapshot_sha256": snapshot_sha256,
        "message_sha256": message_sha256,
        "changed_paths": changed_paths,
        "reviews": [
            {
                "path": review_path.name,
                "sha256": hashlib.sha256(review_path.read_bytes()).hexdigest(),
                "verdict": "PASS",
            }
        ],
    }
    classification_path.write_text(
        aide_lite.stable_json_text(classification), encoding="utf-8"
    )
    return classification_path, message_path


class Q29GitHelperTests(unittest.TestCase):
    def test_helper_policy_anchors(self) -> None:
        checks = aide_lite.validate_git_helper_policy_files(REPO_ROOT)
        failures = [check.message for check in checks if check.severity == "FAIL"]
        self.assertEqual(failures, [])

    def test_routine_task_branch_actions_are_not_repository_authority(self) -> None:
        workflow = aide_lite.read_text(
            REPO_ROOT / aide_lite.GIT_WORKFLOW_POLICY_PATH
        )
        helper = aide_lite.read_text(REPO_ROOT / aide_lite.GIT_HELPER_POLICY_PATH)
        self.assertIn("automatic_reversible:", workflow)
        self.assertIn("create_local_task_branch_from_exact_reviewed_ref", workflow)
        self.assertIn("push_non_protected_task_branch", workflow)
        self.assertIn("repository_authority:", workflow)
        self.assertIn("product_authority:", workflow)
        self.assertIn("workunit_status_ready_or_active", workflow)
        self.assertIn("requested_base_equals_recorded_exact_revision", workflow)
        self.assertIn(
            "routine_task_actions_require_no_operator_approval: true", helper
        )
        self.assertIn(
            "non_protected_task_branch_push: automatic_after_mechanical_checks",
            helper,
        )

    def test_helper_role_classification_path(self) -> None:
        self.assertEqual(aide_lite.classify_branch_role("task/example"), "task")
        self.assertEqual(aide_lite.classify_branch_role("dev"), "integration")
        self.assertEqual(aide_lite.classify_branch_role("main"), "canonical")

    def test_current_repo_plan_is_non_mutating(self) -> None:
        before = git(REPO_ROOT, "rev-parse", "HEAD")
        plan = aide_lite.make_git_helper_plan(REPO_ROOT, "plan", dry_run=True)
        after = git(REPO_ROOT, "rev-parse", "HEAD")
        self.assertEqual(before, after)
        self.assertTrue(plan["dry_run"])
        self.assertFalse(plan["remote_mutation"])
        self.assertFalse(plan["force_push_allowed"])

    def test_sync_dry_run_does_not_mutate(self) -> None:
        before = git(REPO_ROOT, "rev-parse", "HEAD")
        plan = aide_lite.make_git_helper_plan(REPO_ROOT, "sync", dry_run=True)
        after = git(REPO_ROOT, "rev-parse", "HEAD")
        self.assertEqual(before, after)
        self.assertTrue(plan["dry_run"])
        self.assertEqual(plan["executed_commands"], [])

    def test_land_dry_run_and_apply_in_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            init_git_repo(root)
            seed_helper_policy(root)
            create_task_branch(root)
            dry = aide_lite.make_git_helper_plan(root, "land", dry_run=True, target="dev", validation_ok=True)
            self.assertEqual(dry["status"], "ready_dry_run")
            self.assertIn("git merge --no-ff task/example", "\n".join(dry["planned_commands"]))
            apply_plan = aide_lite.make_git_helper_plan(root, "land", dry_run=False, apply_requested=True, target="dev", validation_ok=True)
            applied = aide_lite.execute_git_helper_plan(root, apply_plan)
            self.assertEqual(applied["status"], "applied", applied.get("blockers"))
            self.assertIn("fix(test): land fixture change", git(root, "log", "dev", "--oneline"))
            checks = aide_lite.validate_commit_message_text(
                git(root, "log", "-1", "--pretty=%B", "dev"), repo_root=root
            )
            self.assertEqual(aide_lite.commit_message_result(checks), "PASS")

    def test_promote_dry_run_and_apply_in_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            container = Path(temp)
            root = container / "repo"
            root.mkdir()
            init_git_repo(root)
            seed_helper_policy(root)
            evidence = write_protected_merge_evidence(root, container / "external")
            dry = aide_lite.make_git_helper_plan(root, "promote", dry_run=True, source="dev", target="main", validation_ok=True, review_ok=True, merge_evidence=str(evidence))
            self.assertEqual(dry["status"], "ready_dry_run", dry.get("blockers"))
            apply_plan = aide_lite.make_git_helper_plan(root, "promote", dry_run=False, apply_requested=True, source="dev", target="main", validation_ok=True, review_ok=True, merge_evidence=str(evidence))
            applied = aide_lite.execute_git_helper_plan(root, apply_plan)
            self.assertEqual(applied["status"], "applied", applied.get("blockers"))
            checks = aide_lite.validate_commit_message_text(
                git(root, "log", "-1", "--pretty=%B", "main"), repo_root=root
            )
            self.assertEqual(aide_lite.commit_message_result(checks), "PASS")

    def test_promote_apply_refuses_source_ref_race_before_merge(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            container = Path(temp); root = container / "repo"; root.mkdir()
            init_git_repo(root); seed_helper_policy(root)
            evidence = write_protected_merge_evidence(root, container / "external")
            expected_main = git(root, "rev-parse", "main")
            git(root, "checkout", "-b", "task/race", "dev")
            write(root, "race.txt", "race\n"); git(root, "add", "race.txt")
            git(root, "commit", "-m", "fix(test): race source\n\nWork-Item: TEST-Q29-RACE-1")
            raced_source = git(root, "rev-parse", "HEAD")
            git(root, "checkout", "dev")
            plan = aide_lite.make_git_helper_plan(root, "promote", dry_run=False, apply_requested=True, source="dev", target="main", validation_ok=True, review_ok=True, merge_evidence=str(evidence))
            original_git_oid = aide_lite.git_oid
            source_reads = 0
            def raced_git_oid(repo: Path, ref: str) -> str:
                nonlocal source_reads
                if ref == "dev":
                    source_reads += 1
                    if source_reads == 2:
                        git(root, "update-ref", "refs/heads/dev", raced_source)
                return original_git_oid(repo, ref)
            with mock.patch.object(aide_lite, "git_oid", side_effect=raced_git_oid):
                applied = aide_lite.execute_git_helper_plan(root, plan)
            self.assertEqual(applied["status"], "blocked")
            self.assertIn("promotion_source_or_target_changed_before_merge", applied["blockers"])
            self.assertEqual(git(root, "rev-parse", "main"), expected_main)

    def test_prune_contained_branch_apply_deletes_local_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            init_git_repo(root)
            seed_helper_policy(root)
            create_task_branch(root)
            apply_land = aide_lite.make_git_helper_plan(root, "land", dry_run=False, apply_requested=True, target="dev", validation_ok=True)
            aide_lite.execute_git_helper_plan(root, apply_land)
            prune = aide_lite.make_git_helper_plan(root, "prune", dry_run=True, target="dev")
            eligible = [item for item in prune["prune_candidates"] if item["branch"] == "task/example"]
            self.assertTrue(eligible and eligible[0]["eligible"])
            apply_prune = aide_lite.make_git_helper_plan(root, "prune", dry_run=False, apply_requested=True, target="dev")
            applied = aide_lite.execute_git_helper_plan(root, apply_prune)
            self.assertEqual(applied["status"], "applied", applied.get("blockers"))
            self.assertNotIn("task/example", git(root, "branch", "--format=%(refname:short)"))

    def test_prune_refuses_unmerged_branch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            init_git_repo(root)
            seed_helper_policy(root)
            create_task_branch(root)
            git(root, "checkout", "dev")
            prune = aide_lite.make_git_helper_plan(root, "prune", dry_run=True, target="dev")
            task = next(item for item in prune["prune_candidates"] if item["branch"] == "task/example")
            self.assertFalse(task["eligible"])
            self.assertEqual(task["reason"], "ancestor_containment_not_proven")

    def test_protected_branches_never_pruned(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            init_git_repo(root)
            seed_helper_policy(root)
            git(root, "checkout", "-b", "release/1.0", "main")
            git(root, "checkout", "-b", "gh-pages", "main")
            git(root, "checkout", "dev")
            prune = aide_lite.make_git_helper_plan(root, "prune", dry_run=True, target="main")
            protected = {item["branch"]: item for item in prune["prune_candidates"] if item["branch"] in {"main", "dev", "release/1.0", "gh-pages"}}
            self.assertEqual(set(protected), {"main", "dev", "release/1.0", "gh-pages"})
            self.assertTrue(all(not item["eligible"] for item in protected.values()))

    def test_dirty_tree_blocks_land_and_promote(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            init_git_repo(root)
            seed_helper_policy(root)
            create_task_branch(root)
            write(root, "dirty.txt", "dirty\n")
            plan = aide_lite.make_git_helper_plan(root, "plan", dry_run=True)
            land = aide_lite.make_git_helper_plan(root, "land", dry_run=True, target="dev", validation_ok=True)
            promote = aide_lite.make_git_helper_plan(root, "promote", dry_run=True, source="dev", target="main", validation_ok=True, review_ok=True)
            self.assertEqual(plan["status"], "needs_commit_classification")
            self.assertIn("commit_classification_missing", plan["warnings"])
            self.assertNotIn("dirty_tree_requires_classification", plan["blockers"])
            self.assertIn("dirty_tree_blocks_land", land["blockers"])
            self.assertIn("dirty_tree_blocks_promote", promote["blockers"])

    def test_classified_dirty_snapshot_reaches_commit(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            container = Path(temp)
            root = container / "repo"
            root.mkdir()
            init_git_repo(root)
            seed_helper_policy(root)
            create_task_branch(root)
            write(root, "task.txt", "reviewed task change\n")
            classification, message = write_commit_plan_inputs(
                root, container / "evidence", ["task.txt"]
            )

            before_stage = aide_lite.make_git_commit_plan(root, classification, message)
            self.assertEqual(before_stage["status"], "ready_to_stage", before_stage["blockers"])
            self.assertEqual(before_stage["blockers"], [])
            self.assertEqual(
                before_stage["planned_argv"][0], ["git", "add", "--", "task.txt"]
            )

            git(root, "add", "--", "task.txt")
            after_stage = aide_lite.make_git_commit_plan(root, classification, message)
            self.assertEqual(after_stage["status"], "ready_to_commit", after_stage["blockers"])
            self.assertEqual(after_stage["blockers"], [])

    def test_commit_plan_blocks_unrelated_staged_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            container = Path(temp)
            root = container / "repo"
            root.mkdir()
            init_git_repo(root)
            seed_helper_policy(root)
            create_task_branch(root)
            write(root, "task.txt", "reviewed task change\n")
            classification, message = write_commit_plan_inputs(
                root, container / "evidence", ["task.txt"]
            )
            write(root, "unrelated.txt", "not reviewed\n")
            git(root, "add", "--", "unrelated.txt")

            plan = aide_lite.make_git_commit_plan(root, classification, message)
            self.assertEqual(plan["status"], "blocked")
            self.assertIn(
                "staged_snapshot_differs_from_classification: unrelated.txt",
                plan["blockers"],
            )

    def test_commit_plan_blocks_stale_classification(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            container = Path(temp)
            root = container / "repo"
            root.mkdir()
            init_git_repo(root)
            seed_helper_policy(root)
            create_task_branch(root)
            write(root, "task.txt", "reviewed task change\n")
            classification, message = write_commit_plan_inputs(
                root, container / "evidence", ["task.txt"]
            )
            write(root, "task.txt", "changed after review\n")

            plan = aide_lite.make_git_commit_plan(root, classification, message)
            self.assertEqual(plan["status"], "blocked")
            self.assertIn("classified_content_sha256_mismatch: task.txt", plan["blockers"])

    def test_commit_plan_blocks_unresolved_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            container = Path(temp)
            root = container / "repo"
            root.mkdir()
            init_git_repo(root)
            seed_helper_policy(root)
            create_task_branch(root)
            write(root, "conflict.txt", "base\n")
            git(root, "add", "conflict.txt")
            git(root, "commit", "-m", "add conflict base")
            git(root, "checkout", "-b", "review/conflicting-change")
            write(root, "conflict.txt", "review branch\n")
            git(root, "add", "conflict.txt")
            git(root, "commit", "-m", "review change")
            git(root, "checkout", "task/example")
            write(root, "conflict.txt", "task branch\n")
            git(root, "add", "conflict.txt")
            git(root, "commit", "-m", "task change")
            merge = subprocess.run(
                ["git", "merge", "review/conflicting-change"],
                cwd=root,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                encoding="utf-8",
            )
            self.assertNotEqual(merge.returncode, 0)
            classification, message = write_commit_plan_inputs(
                root, container / "evidence", ["conflict.txt"]
            )

            plan = aide_lite.make_git_commit_plan(root, classification, message)
            self.assertEqual(plan["status"], "blocked")
            self.assertIn("unresolved_conflict: conflict.txt", plan["blockers"])

    def test_commit_plan_rejects_negative_review_wording(self) -> None:
        for verdict in ["NOT APPROVED", "REVIEW_NOT_PASS"]:
            with self.subTest(verdict=verdict), tempfile.TemporaryDirectory() as temp:
                container = Path(temp)
                root = container / "repo"
                root.mkdir()
                init_git_repo(root)
                seed_helper_policy(root)
                create_task_branch(root)
                write(root, "task.txt", "reviewed task change\n")
                classification_path, message = write_commit_plan_inputs(
                    root, container / "evidence", ["task.txt"]
                )
                classification = json.loads(classification_path.read_text(encoding="utf-8"))
                review_path = classification_path.parent / classification["reviews"][0]["path"]
                review = json.loads(review_path.read_text(encoding="utf-8"))
                review["verdict"] = verdict
                review_path.write_text(aide_lite.stable_json_text(review), encoding="utf-8")
                classification["reviews"][0]["verdict"] = verdict
                classification["reviews"][0]["sha256"] = hashlib.sha256(
                    review_path.read_bytes()
                ).hexdigest()
                classification_path.write_text(
                    aide_lite.stable_json_text(classification), encoding="utf-8"
                )

                plan = aide_lite.make_git_commit_plan(root, classification_path, message)
                self.assertEqual(plan["status"], "blocked")
                self.assertIn("classification_review_verdict_invalid: 1", plan["blockers"])
                self.assertIn("classification_review_receipt_not_pass: 1", plan["blockers"])

    def test_commit_plan_preserves_whitespace_in_unclassified_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            container = Path(temp)
            root = container / "repo"
            root.mkdir()
            init_git_repo(root)
            seed_helper_policy(root)
            create_task_branch(root)
            write(root, "task.txt", "reviewed task change\n")
            classification, message = write_commit_plan_inputs(
                root, container / "evidence", ["task.txt"]
            )
            write(root, " task.txt", "unclassified leading-space path\n")

            plan = aide_lite.make_git_commit_plan(root, classification, message)
            self.assertEqual(plan["status"], "blocked")
            self.assertIn("unclassified_worktree_path:  task.txt", plan["blockers"])

    def test_commit_plan_blocks_status_paths_it_cannot_represent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            container = Path(temp)
            root = container / "repo"
            root.mkdir()
            init_git_repo(root)
            seed_helper_policy(root)
            create_task_branch(root)
            write(root, "task.txt", "reviewed task change\n")
            classification, message = write_commit_plan_inputs(
                root, container / "evidence", ["task.txt"]
            )
            unsafe_status = [{
                "code": "??",
                "path": "a\\b",
                "original_path": "",
                "staged": False,
                "unstaged": True,
                "unmerged": False,
            }]

            with mock.patch.object(
                aide_lite, "helper_git_status_entries", return_value=(unsafe_status, "")
            ):
                plan = aide_lite.make_git_commit_plan(root, classification, message)
            self.assertEqual(plan["status"], "blocked")
            self.assertTrue(
                any(item.startswith("git_status_path_unsafe: ") for item in plan["blockers"])
            )

    def test_commit_plan_keeps_shell_metacharacters_out_of_display_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            container = Path(temp)
            root = container / "repo"
            root.mkdir()
            init_git_repo(root)
            seed_helper_policy(root)
            create_task_branch(root)
            rel = "$(echo injected).txt"
            write(root, rel, "reviewed path\n")
            classification, message = write_commit_plan_inputs(
                root, container / "evidence", [rel]
            )

            plan = aide_lite.make_git_commit_plan(root, classification, message)
            self.assertEqual(plan["status"], "ready_to_stage", plan["blockers"])
            self.assertNotIn("$(echo injected)", "\n".join(plan["planned_commands"]))
            self.assertEqual(plan["planned_argv"][0], ["git", "add", "--", rel])

    def test_unknown_branch_role_blocks_land(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            init_git_repo(root)
            seed_helper_policy(root)
            git(root, "checkout", "-b", "weird")
            plan = aide_lite.make_git_helper_plan(root, "land", dry_run=True, target="dev", validation_ok=True)
            self.assertEqual(plan["status"], "blocked")
            self.assertIn("source_role_not_landable: unknown", plan["blockers"])

    def test_no_push_or_force_push_is_executed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            init_git_repo(root)
            seed_helper_policy(root)
            create_task_branch(root)
            dry = aide_lite.make_git_helper_plan(root, "land", dry_run=True, push_requested=True, target="dev", validation_ok=True)
            self.assertIn("git push origin dev", dry["planned_commands"])
            apply_plan = aide_lite.make_git_helper_plan(root, "land", dry_run=False, apply_requested=True, push_requested=True, target="dev", validation_ok=True)
            applied = aide_lite.execute_git_helper_plan(root, apply_plan)
            self.assertEqual(applied["status"], "blocked")
            self.assertEqual(applied["executed_commands"], [])
            serialized = json.dumps(applied)
            self.assertNotIn("--force", serialized)

    def test_helper_output_json_and_markdown_shape(self) -> None:
        plan = aide_lite.make_git_helper_plan(REPO_ROOT, "plan", dry_run=True)
        rendered = aide_lite.render_git_helper_plan_md(plan)
        self.assertEqual(plan["schema_version"], "aide.git-helper-plan.v0")
        self.assertIn("state", plan)
        self.assertIn("planned_commands", plan)
        self.assertIn("# AIDE Git Helper Plan", rendered)

    def test_q29_golden_tasks_pass(self) -> None:
        for task_id in [
            "git_helper_policy_golden",
            "git_land_plan_golden",
            "git_promote_plan_golden",
            "git_prune_guard_golden",
            "git_live_repo_no_mutation_golden",
        ]:
            with self.subTest(task_id=task_id):
                result = aide_lite.run_golden_task(REPO_ROOT, task_id)
                self.assertEqual(result.result, "PASS", result.errors)


if __name__ == "__main__":
    unittest.main()
