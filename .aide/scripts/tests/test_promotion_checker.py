from __future__ import annotations

import hashlib
import base64
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import textwrap
from datetime import datetime, timedelta, timezone
import unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("aide_lite_promotion", REPO_ROOT / ".aide/scripts/aide_lite.py")
aide_lite = importlib.util.module_from_spec(SPEC)
sys.modules["aide_lite_promotion"] = aide_lite
assert SPEC.loader is not None
SPEC.loader.exec_module(aide_lite)
TEST_KEY_DIR = tempfile.TemporaryDirectory()
TEST_PRIVATE_KEY = Path(TEST_KEY_DIR.name) / "attestation-private.pem"
TEST_PUBLIC_KEY = Path(TEST_KEY_DIR.name) / "attestation-public.pem"
subprocess.run(["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(TEST_PRIVATE_KEY)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
subprocess.run(["openssl", "pkey", "-in", str(TEST_PRIVATE_KEY), "-pubout", "-out", str(TEST_PUBLIC_KEY)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
aide_lite.TRUSTED_WORKFLOW_PUBLIC_KEYS = {"test-fixture": TEST_PUBLIC_KEY.read_text(encoding="utf-8")}


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, encoding="utf-8").stdout.strip()


def commit(root: Path, subject: str, name: str, content: str) -> str:
    (root / name).parent.mkdir(parents=True, exist_ok=True)
    (root / name).write_text(content, encoding="utf-8")
    git(root, "add", name)
    git(root, "commit", "-m", subject + "\n\nWork-Item: TEST-PROMOTION-1")
    return git(root, "rev-parse", "HEAD")


def init(root: Path) -> None:
    git(root, "init")
    git(root, "config", "user.email", "fixture@example.invalid")
    git(root, "config", "user.name", "Fixture")
    git(root, "remote", "add", "origin", "https://github.com/example/repo.git")
    commit(root, "chore(test): initialize fixture", "README.md", "fixture\n")
    commit(root, "chore(test): add trusted workflow", ".github/workflows/task-to-dev-promotion-check.yml", "name: fixture\n")
    for rel in [
        aide_lite.COMMIT_MESSAGE_POLICY_PATH,
        aide_lite.FACMAN_COMMIT_MESSAGE_POLICY_PATH,
        aide_lite.VERIFIED_PROTECTED_PR_MERGE_SCHEMA_PATH,
        aide_lite.DEV_TO_MAIN_BOOTSTRAP_SCHEMA_PATH,
    ]:
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text((REPO_ROOT / rel).read_text(encoding="utf-8"), encoding="utf-8")
    git(root, "add", ".aide")
    git(root, "commit", "-m", "chore(test): seed commit policy\n\nWork-Item: TEST-PROMOTION-1")
    git(root, "branch", "-M", "main")
    git(root, "update-ref", aide_lite.TASK_TO_DEV_TRUSTED_MAIN_REF, "main")
    git(root, "checkout", "-b", "dev")
    git(root, "checkout", "-b", "task/example")


def write_json(path: Path, data: dict[str, object]) -> str:
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

def merge_fixture(root: Path, external: Path, *, nested: bool = False) -> tuple[str, Path, dict[str, object]]:
    task_head = commit(root, "fix(test): add task change", "task.txt", "task\n")
    if nested:
        git(root, "checkout", "-b", "task/nested", task_head)
        nested_head = commit(root, "fix(test): add nested change", "nested.txt", "nested\n")
        git(root, "checkout", "task/example")
        git(root, "merge", "--no-ff", "task/nested", "-m", "Merge branch 'task/nested'")
        task_head = git(root, "rev-parse", "HEAD")
        assert nested_head
    git(root, "checkout", "dev")
    base = git(root, "rev-parse", "HEAD")
    git(root, "merge", "--no-ff", "task/example", "-m", "Promotion fixture (#7)")
    merge = git(root, "rev-parse", "HEAD")
    tree = git(root, "rev-parse", f"{merge}^{{tree}}")
    parents = git(root, "show", "-s", "--format=%P", merge).split()
    trusted_main = git(root, "rev-parse", "main")
    reachable = git(root, "rev-list", "--reverse", task_head, f"^{base}", f"^{trusted_main}").splitlines()
    full_range = git(root, "rev-list", "--reverse", task_head, f"^{base}").splitlines()
    external.mkdir(parents=True, exist_ok=True)
    raw_pr = {"repository": "example/repo", "number": 7, "title": "Promotion fixture", "state": "closed", "draft": False, "merged": True, "base_ref": "dev", "base_oid": base, "head_ref": "task/example", "head_oid": parents[1], "merge_oid": merge}
    raw_protection = {"repository": "example/repo", "branch": "dev", "protected": True, "prior_base_oid": base, "required_status": "task-to-dev-promotion-check"}
    raw_status = {"schema_version": aide_lite.TASK_TO_DEV_STATUS_SCHEMA, "repository": "example/repo", "pull_request_number": 7, "base_oid": base, "head_oid": parents[1], "range": f"{base}..{parents[1]}", "trusted_main_oid": trusted_main, "full_history_checked": True, "candidate_history_checked": True, "trusted_main_history_excluded": True, "conclusion": "success", "commit_count": len(reachable), "commit_oids": reachable, "full_range_commit_count": len(full_range), "full_range_commit_oids": full_range}
    record = {"repository": "example/repo", "pull_request_number": 7, "pull_request_title": "Promotion fixture", "state": "closed", "draft": False, "merged": True, "base_ref": "dev", "base_oid": base, "head_ref": "task/example", "head_oid": parents[1], "merge_oid": merge, "merge_tree": tree, "parents": parents, "raw": {"pull_request": {"path": str(external / "pr.json"), "sha256": write_github_observation(external / "pr.json", raw_pr)}, "protection": {"path": str(external / "protection.json"), "sha256": write_github_observation(external / "protection.json", raw_protection)}, "status": {"path": str(external / "status.json"), "sha256": write_github_observation(external / "status.json", raw_status)}}}
    evidence = {"schema_version": aide_lite.VERIFIED_PROTECTED_PR_MERGE_SCHEMA, "repository": "example/repo", "merges": [record]}
    path = external / "merge-evidence.json"
    write_json(path, evidence)
    return merge, path, evidence


def bootstrap_fixture(root: Path, external: Path) -> tuple[Path, Path]:
    merge, normal_evidence, _normal = merge_fixture(root, external / "normal")
    git(root, "update-ref", "refs/remotes/origin/main", "main")
    git(root, "update-ref", "refs/remotes/origin/dev", "dev")
    parents = git(root, "show", "-s", "--format=%P", merge).split()
    promotion = {"number": 13, "base_ref": "main", "base_oid": git(root, "rev-parse", "main"), "base_tree": git(root, "rev-parse", "main^{tree}"), "head_ref": "dev", "head_oid": git(root, "rev-parse", "dev"), "head_tree": git(root, "rev-parse", "dev^{tree}")}
    results, _failed, _baseline = aide_lite.validate_commit_range_messages(
        root, aide_lite.git_commit_messages_for_range(root, f"{promotion['base_oid']}..{promotion['head_oid']}")
    )
    debt = [{"oid": oid, "diagnostics": [check.message for check in checks if check.severity == "FAIL"]} for oid, _subject, result, checks in results if result == "FAIL"]
    pr = {"repository": "example/repo", "state": "open", "draft": False, "merged": False, **promotion}
    approval = {"repository": "example/repo", "pull_request_number": promotion["number"], "base_oid": promotion["base_oid"], "head_oid": promotion["head_oid"], "commit_id": promotion["head_oid"], "state": "APPROVED", "author_id": 11, "reviewer_id": 12}
    check = {"repository": "example/repo", "pull_request_number": promotion["number"], "base_oid": promotion["base_oid"], "head_oid": promotion["head_oid"], "name": "dev-to-main-bootstrap-preflight", "conclusion": "success"}
    activation = {"repository": "example/repo", "branch": "dev", "required_status": "task-to-dev-promotion-check", "active": True, "frontier_oid": promotion["head_oid"]}
    default_activation = {"repository": "example/repo", "default_branch": "main", "workflow_path": ".github/workflows/task-to-dev-promotion-check.yml", "workflow_blob_oid": git(root, "rev-parse", "main:.github/workflows/task-to-dev-promotion-check.yml"), "active": True}
    data = {
        "schema_version": aide_lite.DEV_TO_MAIN_BOOTSTRAP_SCHEMA, "repository": "example/repo",
        "expires_at": "2099-01-01T00:00:00Z", "promotion_pr": promotion,
        "first_parent_merges": [{"merge_oid": merge, "parents": parents, "tree": git(root, "rev-parse", f"{merge}^{{tree}}"), "legacy_status": "not_observed", "historical": {"availability": "not_observed", "reason": "pre-status-history"}}],
        "historical": {"protection": "not_observed", "required_status": "not_observed", "retrospective": {"range": f"{promotion['base_oid']}..{promotion['head_oid']}", "outcome": "debt", "debt": debt}},
        "raw": {
            "pull_request": {"path": str(external / "pr.json"), "sha256": write_github_observation(external / "pr.json", pr)},
            "approval": {"path": str(external / "approval.json"), "sha256": write_github_observation(external / "approval.json", approval)},
            "check": {"path": str(external / "check.json"), "sha256": write_github_observation(external / "check.json", check)},
        },
        "activation": {"observation": {"path": str(external / "activation.json"), "sha256": write_github_observation(external / "activation.json", activation)}, "default_branch_observation": {"path": str(external / "default-activation.json"), "sha256": write_github_observation(external / "default-activation.json", default_activation)}},
        "authorization": {"bootstrap_digest": "", "review": {"path": str(external / "authorization.json"), "sha256": ""}},
    }
    digest = aide_lite.bootstrap_digest(data)
    data["authorization"]["bootstrap_digest"] = digest
    exceptions = hashlib.sha256(aide_lite.stable_json_text([merge]).encode("utf-8")).hexdigest()
    auth = {"repository": "example/repo", "base_oid": promotion["base_oid"], "head_oid": promotion["head_oid"], "bootstrap_digest": digest, "exception_set_digest": exceptions, "commit_id": promotion["head_oid"], "author_id": 11, "reviewer_id": 12, "state": "APPROVED"}
    data["authorization"]["review"]["sha256"] = write_github_observation(external / "authorization.json", auth)
    bootstrap = external / "bootstrap.json"; write_json(bootstrap, data)
    empty = external / "verified.json"; write_json(empty, {"schema_version": aide_lite.VERIFIED_PROTECTED_PR_MERGE_SCHEMA, "repository": "example/repo", "merges": []})
    return empty, bootstrap


class PromotionCheckerTests(unittest.TestCase):
    def test_bootstrap_binds_exact_topology_debt_and_activation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            container = Path(temp); root = container / "repo"; root.mkdir(); init(root)
            evidence, bootstrap = bootstrap_fixture(root, container / "external")
            blockers, count = aide_lite.validate_verified_protected_pr_merges(root, "main..dev", str(evidence), str(bootstrap))
            self.assertEqual((blockers, count), ([], 1))
            original = json.loads(bootstrap.read_text(encoding="utf-8"))
            variants = {
                "debt": (lambda data: data["historical"]["retrospective"].update({"debt": [{"oid": "0" * 40, "diagnostics": []}]}), "bootstrap_retrospective_debt_mismatch"),
                "topology": (lambda data: data.update({"first_parent_merges": []}), "bootstrap_topology_mismatch"),
                "invented": (lambda data: data["historical"].update({"required_status": "success"}), "bootstrap_invented_historical_status"),
                "expiry": (lambda data: data.update({"expires_at": "2000-01-01T00:00:00Z"}), "bootstrap_expired"),
            }
            for _name, (mutate, expected) in variants.items():
                data = deepcopy(original); mutate(data); write_json(bootstrap, data)
                blockers, _count = aide_lite.validate_verified_protected_pr_merges(root, "main..dev", str(evidence), str(bootstrap))
                self.assertIn(expected, blockers)
            nested_extra = deepcopy(original)
            nested_extra["promotion_pr"]["unexpected"] = True
            write_json(bootstrap, nested_extra)
            blockers, _count = aide_lite.validate_verified_protected_pr_merges(root, "main..dev", str(evidence), str(bootstrap))
            self.assertTrue(any("bootstrap_schema_invalid: $.promotion_pr:additional:unexpected" == item for item in blockers), blockers)
            wrong_blob = deepcopy(original)
            default_raw = json.loads((container / "external/default-activation.json").read_text(encoding="utf-8"))["payload"]["raw_payload"]
            default_raw["workflow_blob_oid"] = "0" * 40
            wrong_blob["activation"]["default_branch_observation"]["sha256"] = write_github_observation(container / "external/default-activation.json", default_raw)
            write_json(bootstrap, wrong_blob)
            blockers, _count = aide_lite.validate_verified_protected_pr_merges(root, "main..dev", str(evidence), str(bootstrap))
            self.assertIn("bootstrap_default_branch_activation_invalid", blockers)
            missing_check = deepcopy(original)
            missing_check["raw"].pop("check")
            write_json(bootstrap, missing_check)
            blockers, _count = aide_lite.validate_verified_protected_pr_merges(root, "main..dev", str(evidence), str(bootstrap))
            self.assertIn("merge_evidence_raw_bootstrap_check_missing", blockers)
            merged_pr = deepcopy(original)
            raw_pr = json.loads((container / "external/pr.json").read_text(encoding="utf-8"))
            raw_pr["payload"]["raw_payload"]["merged"] = True
            merged_pr["raw"]["pull_request"]["sha256"] = write_github_observation(container / "external/pr.json", raw_pr["payload"]["raw_payload"])
            write_json(bootstrap, merged_pr)
            blockers, _count = aide_lite.validate_verified_protected_pr_merges(root, "main..dev", str(evidence), str(bootstrap))
            self.assertIn("bootstrap_pull_request_summary_mismatch", blockers)
            missing_provenance = deepcopy(original)
            raw_check = json.loads((container / "external/check.json").read_text(encoding="utf-8"))
            raw_check = raw_check["payload"]["raw_payload"]
            missing_provenance["raw"]["check"]["sha256"] = write_json(container / "external/check.json", raw_check)
            write_json(bootstrap, missing_provenance)
            blockers, _count = aide_lite.validate_verified_protected_pr_merges(root, "main..dev", str(evidence), str(bootstrap))
            self.assertIn("merge_evidence_raw_bootstrap_check_trusted_envelope_missing", blockers)
            fabricated = deepcopy(original)
            promotion = original["promotion_pr"]
            write_github_observation(container / "external/check.json", {"repository": "example/repo", "pull_request_number": promotion["number"], "base_oid": promotion["base_oid"], "head_oid": promotion["head_oid"], "name": "dev-to-main-bootstrap-preflight", "conclusion": "success"})
            forged_check = json.loads((container / "external/check.json").read_text(encoding="utf-8"))
            forged_check["signature"] = "0" * 64
            fabricated["raw"]["check"]["sha256"] = write_json(container / "external/check.json", forged_check)
            write_json(bootstrap, fabricated)
            blockers, _count = aide_lite.validate_verified_protected_pr_merges(root, "main..dev", str(evidence), str(bootstrap))
            self.assertIn("merge_evidence_raw_bootstrap_check_trusted_envelope_signature_invalid", blockers)
            write_json(bootstrap, original)
            git(root, "checkout", "dev")
            commit(root, "fix(test): post-frontier change", "post.txt", "post\n")
            git(root, "update-ref", "refs/remotes/origin/dev", "dev")
            blockers, _count = aide_lite.validate_verified_protected_pr_merges(root, "main..dev", str(evidence), str(bootstrap))
            self.assertIn("bootstrap_promotion_range_mismatch", blockers)

    def test_trusted_envelope_refuses_noncanonical_rsa_signature_encodings(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "signed.json"
            write_github_observation(path, {"head_oid": "a" * 40})
            envelope = json.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(aide_lite.verify_trusted_workflow_attestation(envelope["payload"], envelope["key_id"], envelope["signature"]))
            signature = base64.b64decode(envelope["signature"])
            modulus, _exponent = aide_lite.trusted_rsa_public_numbers(TEST_PUBLIC_KEY.read_text(encoding="utf-8"))
            for malformed in (b"\0" + signature, signature + b"\0", (int.from_bytes(signature, "big") + modulus).to_bytes(len(signature) + 1, "big")):
                self.assertFalse(aide_lite.verify_trusted_workflow_attestation(envelope["payload"], envelope["key_id"], base64.b64encode(malformed).decode("ascii")))

    def test_workflow_identity_binds_each_event_to_its_protected_ref_and_sha(self) -> None:
        repo = "example/repo"; workflow = ".github/workflows/task-to-dev-promotion-check.yml"
        dev = "a" * 40; main = "b" * 40
        self.assertTrue(aide_lite.task_to_dev_workflow_identity_is_exact("pull_request_target", repo, f"{repo}/{workflow}@refs/heads/dev", dev, dev, "main", main, 7, 7, dev))
        self.assertTrue(aide_lite.task_to_dev_workflow_identity_is_exact("issue_comment", repo, f"{repo}/{workflow}@refs/heads/main", main, dev, "main", main, 7, 7, main))
        for event, ref, sha, run_sha in [
            ("pull_request_target", f"{repo}/{workflow}@refs/heads/main", dev, dev),
            ("pull_request_target", f"{repo}/{workflow}@refs/heads/dev", main, main),
            ("issue_comment", f"{repo}/{workflow}@refs/heads/dev", main, main),
            ("issue_comment", f"{repo}/{workflow}@refs/heads/main", dev, dev),
        ]:
            self.assertFalse(aide_lite.task_to_dev_workflow_identity_is_exact(event, repo, ref, sha, dev, "main", main, 7, 7, run_sha))

    def test_embedded_workflow_python_registers_dataclass_module_before_execution(self) -> None:
        workflow = (REPO_ROOT / ".github/workflows/task-to-dev-promotion-check.yml").read_text(encoding="utf-8")
        steps = (
            ("control-change", "Require exact-head owner command for protected control changes", "Fetch candidate and trusted main history without checking them out", "def api"),
            ("publication", "Publish exact-head trusted task-to-dev admission", "Retain raw status receipt", "workflow_id ="),
        )
        for name, step, next_step, prelude_end in steps:
            section = workflow.split(f"- name: {step}", 1)[1]
            script = textwrap.dedent(section.split("        run: |\n", 1)[1].split(f"      - name: {next_step}", 1)[0])
            compile(script, f"task-to-dev-{name}.py", "exec")
            prelude = script.split(prelude_end, 1)[0]
            environment = dict(os.environ)
            environment.pop("PYTHONPATH", None)
            result = subprocess.run([sys.executable, "-c", prelude], cwd=REPO_ROOT, env=environment, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('sys.path.insert(0, ".aide/scripts")', prelude)
            self.assertIn('spec_from_file_location("trusted_aide_lite", ".aide/scripts/aide_lite.py")', prelude)
            self.assertIn("sys.modules[spec.name] = aide_lite", prelude)
            self.assertIn("spec.loader.exec_module(aide_lite)", prelude)
            self.assertLess(prelude.index("sys.modules[spec.name] = aide_lite"), prelude.index("spec.loader.exec_module(aide_lite)"))

    def test_hosted_control_path_gate_uses_base_workflow_and_exact_head_owner_command(self) -> None:
        workflow = (REPO_ROOT / ".github/workflows/task-to-dev-promotion-check.yml").read_text(encoding="utf-8")
        docs = (REPO_ROOT / "docs/reference/git-helper-workflow.md").read_text(encoding="utf-8")
        for marker in [
            "pull_request_target:", "issue_comment:", "created, edited, deleted",
            "Require exact-head owner command for protected control changes",
            '["gh", "api", "--paginate", "--slurp"', "previous_filename",
            "checks: write", "owner_control_change_authorized", "final_comments", "WORKFLOW_SHA", "task_to_dev_workflow_identity_is_exact", "event_base",
            "Candidate code is fetched as Git objects only and is never executed",
            "git/ref/heads/main", "task-to-dev-trusted-main", "trusted main moved between observation and fetch",
            '--trusted-main "$TRUSTED_MAIN_OID"', 'receipt.get("trusted_main_oid") != default_branch_sha',
        ]:
            self.assertIn(marker, workflow)
        self.assertIn(".aide/scripts/aide_lite.py", aide_lite.PROTECTED_CONTROL_EXACT_PATHS)
        self.assertIn(".aide/commit_policy_baseline.toml", aide_lite.PROTECTED_CONTROL_EXACT_PATHS)
        self.assertIn(".github/workflows/", aide_lite.PROTECTED_CONTROL_PREFIXES)
        self.assertIn("Ordinary source PRs do not require this extra", docs)
        self.assertIn("rulesets must separately require", docs)

    def test_control_change_gate_refuses_renames_and_non_owner_or_stale_commands(self) -> None:
        head = "a" * 40
        self.assertEqual(
            aide_lite.protected_control_paths([
                {"filename": "docs/renamed.md", "previous_filename": ".github/workflows/old.yml"}
            ]),
            [".github/workflows/old.yml"],
        )
        with self.assertRaisesRegex(ValueError, "normalized"):
            aide_lite.protected_control_paths([{"filename": "../.aide/scripts/aide_lite.py"}])
        valid = {"author_association": "OWNER", "user": {"id": 7}, "body": f"/authorize-control-change {head}"}
        self.assertTrue(aide_lite.owner_control_change_authorized(head, 7, [valid]))
        for comment in [
            {**valid, "user": {"id": 8}},
            {**valid, "author_association": "MEMBER"},
            {**valid, "body": f"/authorize-control-change {'b' * 40}"},
            {**valid, "body": f"please /authorize-control-change {head}"},
            {**valid, "body": f"/authorize-control-change {head}\n"},
        ]:
            self.assertFalse(aide_lite.owner_control_change_authorized(head, 7, [comment]))

    def test_task_to_dev_status_checks_full_range_without_candidate_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            container = Path(temp); root = container / "repo"; root.mkdir(); init(root)
            base = git(root, "rev-parse", "dev")
            trusted_main = git(root, "rev-parse", "main")
            head = commit(root, "fix(test): status fixture", "status.txt", "status\n")
            output = container / "external-status.json"
            result = aide_lite.command_git_task_to_dev_status(SimpleNamespace(
                repo_root=root, repository="example/repo", pull_request=9,
                base=base, head=head, trusted_main=trusted_main, output=str(output),
            ))
            receipt = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(result, 0, receipt.get("blockers"))
            self.assertEqual(receipt["range"], f"{base}..{head}")
            self.assertEqual(receipt["trusted_main_oid"], trusted_main)
            self.assertEqual(receipt["commit_oids"], [head])
            self.assertEqual(receipt["full_range_commit_oids"], [head])
            self.assertTrue(receipt["full_history_checked"])
            self.assertTrue(receipt["candidate_history_checked"])
            self.assertFalse(receipt["candidate_code_executed"])

    def test_task_to_dev_status_excludes_only_trusted_main_history(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            container = Path(temp); root = container / "repo"; root.mkdir(); init(root)
            base = git(root, "rev-parse", "dev")
            git(root, "checkout", "main")
            protected_bad = commit(root, "ordinary protected merge subject", "protected.txt", "protected\n")
            trusted_main = git(root, "rev-parse", "main")
            git(root, "update-ref", aide_lite.TASK_TO_DEV_TRUSTED_MAIN_REF, trusted_main)
            git(root, "checkout", "task/example")
            git(root, "merge", "--no-ff", "main", "-m", "chore(test): synchronize protected main\n\nWork-Item: TEST-PROMOTION-1")
            candidate_merge = git(root, "rev-parse", "HEAD")
            head = commit(root, "fix(test): retain candidate validation", "candidate.txt", "candidate\n")
            output = container / "external-status.json"
            result = aide_lite.command_git_task_to_dev_status(SimpleNamespace(
                repo_root=root, repository="example/repo", pull_request=10,
                base=base, head=head, trusted_main=trusted_main, output=str(output),
            ))
            receipt = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(result, 0, receipt.get("blockers"))
            self.assertNotIn(protected_bad, receipt["commit_oids"])
            self.assertEqual(receipt["commit_oids"], [candidate_merge, head])
            self.assertIn(protected_bad, receipt["full_range_commit_oids"])

    def test_task_to_dev_status_requires_exact_lowercase_trusted_main_oid(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            container = Path(temp); root = container / "repo"; root.mkdir(); init(root)
            base = git(root, "rev-parse", "dev")
            head = commit(root, "fix(test): status fixture", "status.txt", "status\n")
            output = container / "external-status.json"
            for trusted_main in ("main", "A" * 40, f" {git(root, 'rev-parse', 'main')}"):
                with self.subTest(trusted_main=trusted_main), self.assertRaisesRegex(
                    ValueError, "exact lowercase 40-character commit OID"
                ):
                    aide_lite.command_git_task_to_dev_status(SimpleNamespace(
                        repo_root=root, repository="example/repo", pull_request=11,
                        base=base, head=head, trusted_main=trusted_main, output=str(output),
                    ))
            self.assertFalse(output.exists())
            with patch.object(aide_lite, "git_oid", side_effect=[base, head, "b" * 40]):
                with self.assertRaisesRegex(ValueError, "exact supplied commit OID"):
                    aide_lite.command_git_task_to_dev_status(SimpleNamespace(
                        repo_root=root, repository="example/repo", pull_request=11,
                        base=base, head=head, trusted_main="a" * 40, output=str(output),
                    ))
            self.assertFalse(output.exists())
            with patch.object(aide_lite, "git_oid", side_effect=[base, head, "a" * 40, "b" * 40]):
                with self.assertRaisesRegex(ValueError, "exact fetched protected main ref"):
                    aide_lite.command_git_task_to_dev_status(SimpleNamespace(
                        repo_root=root, repository="example/repo", pull_request=11,
                        base=base, head=head, trusted_main="a" * 40, output=str(output),
                    ))
            self.assertFalse(output.exists())

    def test_task_to_dev_status_rejects_unavailable_trusted_main_and_bad_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            container = Path(temp); root = container / "repo"; root.mkdir(); init(root)
            base = git(root, "rev-parse", "dev")
            trusted_main = git(root, "rev-parse", "main")
            bad = commit(root, "ordinary malformed", "bad-candidate.txt", "bad\n")
            with self.assertRaises(ValueError):
                aide_lite.command_git_task_to_dev_status(SimpleNamespace(
                    repo_root=root, repository="example/repo", pull_request=11,
                    base=base, head=bad, trusted_main="f" * 40,
                    output=str(container / "unavailable.json"),
                ))
            output = container / "bad-status.json"
            result = aide_lite.command_git_task_to_dev_status(SimpleNamespace(
                repo_root=root, repository="example/repo", pull_request=11,
                base=base, head=bad, trusted_main=trusted_main, output=str(output),
            ))
            receipt = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(result, 1)
            self.assertIn("candidate_history_contains_malformed_commit", receipt["blockers"])

    def test_full_history_remains_default_and_first_parent_requires_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "repo"; root.mkdir(); init(root)
            bad = commit(root, "ordinary malformed", "bad.txt", "bad\n")
            blockers, _count, _baseline = aide_lite.git_full_range_validation(root, f"dev..{bad}")
            self.assertIn("commit_range_contains_malformed_commit", blockers)
            self.assertEqual(aide_lite.validate_verified_protected_pr_merges(root, "main..dev", "relative.json")[0], ["merge_evidence_evidence_path_not_absolute"])

    def test_verified_merge_accepts_github_and_title_subject_forms(self) -> None:
        for github_subject in (False, True):
            with self.subTest(github_subject=github_subject), tempfile.TemporaryDirectory() as temp:
                container = Path(temp); root = container / "repo"; root.mkdir(); init(root)
                merge, evidence_path, evidence = merge_fixture(root, container / "external")
                if github_subject:
                    git(root, "commit", "--amend", "-m", "Merge pull request #7 from example/task/example")
                    new_merge = git(root, "rev-parse", "HEAD")
                    evidence["merges"][0]["merge_oid"] = new_merge
                    evidence["merges"][0]["merge_tree"] = git(root, "rev-parse", f"{new_merge}^{{tree}}")
                    evidence["merges"][0]["parents"] = git(root, "show", "-s", "--format=%P", new_merge).split()
                    raw_pr = json.loads((container / "external/pr.json").read_text())["payload"]["raw_payload"]
                    raw_pr["merge_oid"] = new_merge
                    evidence["merges"][0]["raw"]["pull_request"]["sha256"] = write_github_observation(container / "external/pr.json", raw_pr)
                    write_json(evidence_path, evidence)
                blockers, count = aide_lite.validate_verified_protected_pr_merges(root, "main..dev", str(evidence_path))
                self.assertEqual((blockers, count), ([], 1))

    def test_receipt_refuses_required_negative_bindings(self) -> None:
        cases = ["wrong_repo", "wrong_pr", "wrong_base", "wrong_head", "wrong_merge", "wrong_tree", "wrong_parents", "wrong_target", "raw_hash", "open", "draft", "unprotected", "stale", "duplicate_conflicting", "outside_range", "nested_extra", "nested_wrong_type"]
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temp:
                container = Path(temp); root = container / "repo"; root.mkdir(); init(root)
                merge, evidence_path, evidence = merge_fixture(root, container / "external")
                record = evidence["merges"][0]
                if case == "wrong_repo": evidence["repository"] = "other/repo"
                elif case == "wrong_pr": record["pull_request_number"] = 8
                elif case == "wrong_base": record["base_oid"] = "0" * 40
                elif case == "wrong_head": record["head_oid"] = "1" * 40
                elif case == "wrong_merge": record["merge_oid"] = "2" * 40
                elif case == "wrong_tree": record["merge_tree"] = "3" * 40
                elif case == "wrong_parents": record["parents"] = list(reversed(record["parents"]))
                elif case == "wrong_target": record["base_ref"] = "main"
                elif case == "raw_hash": record["raw"]["status"]["sha256"] = "0" * 64
                elif case == "open": record["state"] = "open"
                elif case == "draft": record["draft"] = True
                elif case == "unprotected":
                    raw = json.loads((container / "external/protection.json").read_text())["payload"]["raw_payload"]; raw["protected"] = False; record["raw"]["protection"]["sha256"] = write_github_observation(container / "external/protection.json", raw)
                elif case == "stale":
                    raw = json.loads((container / "external/protection.json").read_text())["payload"]["raw_payload"]; raw["prior_base_oid"] = "f" * 40; record["raw"]["protection"]["sha256"] = write_github_observation(container / "external/protection.json", raw)
                elif case == "duplicate_conflicting":
                    duplicate = deepcopy(record); duplicate["head_ref"] = "task/other"; evidence["merges"].append(duplicate)
                elif case == "outside_range": record["merge_oid"] = git(root, "rev-parse", "main")
                elif case == "nested_extra": record["raw"]["extra"] = {"path": "x", "sha256": "0" * 64}
                elif case == "nested_wrong_type": record["raw"]["status"] = "not-an-object"
                write_json(evidence_path, evidence)
                blockers, _count = aide_lite.validate_verified_protected_pr_merges(root, "main..dev", str(evidence_path))
                self.assertTrue(blockers, blockers)

    def test_refuses_candidate_evidence_one_parent_and_nested_debt(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            container = Path(temp); root = container / "repo"; root.mkdir(); init(root)
            _merge, evidence_path, evidence = merge_fixture(root, container / "external", nested=True)
            raw = json.loads((container / "external/status.json").read_text())["payload"]["raw_payload"]
            raw["commit_oids"] = raw["commit_oids"][-1:]
            evidence["merges"][0]["raw"]["status"]["sha256"] = write_github_observation(container / "external/status.json", raw)
            write_json(evidence_path, evidence)
            blockers, _count = aide_lite.validate_verified_protected_pr_merges(root, "main..dev", str(evidence_path))
            self.assertTrue(any("status_summary_mismatch" in item for item in blockers), blockers)
            inside = root / "candidate-evidence.json"; write_json(inside, evidence)
            self.assertEqual(aide_lite.validate_verified_protected_pr_merges(root, "main..dev", str(inside))[0], ["merge_evidence_evidence_path_inside_candidate_checkout"])
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "repo"; root.mkdir(); init(root)
            git(root, "checkout", "dev")
            direct = commit(root, "ordinary malformed", "direct.txt", "direct\n")
            git(root, "checkout", "task/example")
            _merge, evidence_path, _evidence = merge_fixture(root, Path(temp) / "external")
            blockers, _count = aide_lite.validate_verified_protected_pr_merges(root, "main..dev", str(evidence_path))
            self.assertIn(f"first_parent_direct_commit_malformed: {direct}", blockers)
            self.assertEqual(git(root, "show", "-s", "--format=%P", direct), git(root, "rev-parse", "main"))


if __name__ == "__main__":
    unittest.main()
