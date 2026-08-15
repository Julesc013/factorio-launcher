# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Report-only D2 protected-integration admission validation.

This tool validates evidence. It never writes refs, merges, approves, or grants
authority. Owner ratification and an independent integrator remain external.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_ROOT = ROOT / "contracts" / "schema" / "release"
SCHEMAS = {
    "implementation": SCHEMA_ROOT / "d2_implementation_attestation.v1.schema.json",
    "assurance": SCHEMA_ROOT / "d2_independent_assurance.v1.schema.json",
    "policy": SCHEMA_ROOT / "d2_policy_admission.v1.schema.json",
}


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def changed_paths_sha256(paths: Sequence[str]) -> str:
    normalized = sorted({path.replace("\\", "/") for path in paths if path})
    payload = "".join(f"{path}\n" for path in normalized).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _git(repo_root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _schema_problems(kind: str, record: dict[str, Any]) -> list[str]:
    schema = load_json(SCHEMAS[kind])
    validator = jsonschema.Draft202012Validator(schema)
    return [
        f"{kind} schema at {'.'.join(str(part) for part in error.absolute_path) or '$'}: {error.message}"
        for error in sorted(validator.iter_errors(record), key=lambda item: list(item.absolute_path))
    ]


def _subject_from_implementation(record: dict[str, Any]) -> dict[str, Any]:
    base = record.get("base", {})
    head = record.get("head", {})
    return {
        "base_revision": base.get("revision"),
        "base_tree": base.get("tree"),
        "head_revision": head.get("revision"),
        "head_tree": head.get("tree"),
        "changed_paths_sha256": record.get("changed_paths_sha256"),
    }


def _check_set(record: dict[str, Any]) -> dict[str, tuple[Any, Any]]:
    result: dict[str, tuple[Any, Any]] = {}
    for check in record.get("checks", []):
        if isinstance(check, dict):
            result[str(check.get("name", ""))] = (
                check.get("state"),
                check.get("head_revision"),
            )
    return result


def validate_premerge(
    implementation: dict[str, Any],
    assurance: dict[str, Any],
    policy: dict[str, Any],
    *,
    implementation_sha256: str,
    assurance_sha256: str,
    repo_root: Path,
    require_clean: bool = True,
) -> list[str]:
    problems = [
        *_schema_problems("implementation", implementation),
        *_schema_problems("assurance", assurance),
        *_schema_problems("policy", policy),
    ]
    subject = _subject_from_implementation(implementation)
    if assurance.get("subject") != subject:
        problems.append("assurance subject does not exactly bind the implementation")
    if policy.get("subject") != subject:
        problems.append("policy subject does not exactly bind the implementation")
    for name, record in (("assurance", assurance), ("policy", policy)):
        if record.get("repository") != implementation.get("repository"):
            problems.append(f"{name} repository does not match implementation")
        if record.get("workunit") != implementation.get("workunit"):
            problems.append(f"{name} WorkUnit does not match implementation")
    if assurance.get("implementation_attestation_sha256") != implementation_sha256:
        problems.append("assurance implementation digest is not exact")
    if policy.get("implementation_attestation_sha256") != implementation_sha256:
        problems.append("policy implementation digest is not exact")
    if policy.get("assurance_attestation_sha256") != assurance_sha256:
        problems.append("policy assurance digest is not exact")

    identities = {
        str(implementation.get("author_identity", "")),
        str(assurance.get("assurance_identity", "")),
        str(policy.get("policy_identity", "")),
    }
    if "" in identities or len(identities) != 3:
        problems.append("implementation, assurance, and policy identities must be distinct")
    if implementation.get("high_risk_surfaces") and assurance.get("high_risk_review_complete") is not True:
        problems.append("high-risk surfaces require completed independent review")
    assurance_checks = _check_set(assurance)
    policy_checks = _check_set(policy)
    if len(assurance_checks) != len(assurance.get("checks", [])):
        problems.append("assurance check names must be unique")
    if len(policy_checks) != len(policy.get("checks", [])):
        problems.append("policy check names must be unique")
    if assurance_checks != policy_checks:
        problems.append("policy checks do not exactly match independent assurance checks")

    base = str(subject.get("base_revision", ""))
    head = str(subject.get("head_revision", ""))
    try:
        observed_head = _git(repo_root, "rev-parse", "HEAD").stdout.strip()
        observed_tree = _git(repo_root, "rev-parse", "HEAD^{tree}").stdout.strip()
        observed_base_tree = _git(repo_root, "rev-parse", f"{base}^{{tree}}").stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        problems.append(f"git identity observation failed: {exc}")
        return problems
    if observed_head != head:
        problems.append(f"repository HEAD is {observed_head}, expected immutable head {head}")
    if observed_tree != subject.get("head_tree"):
        problems.append("repository HEAD tree does not match the admitted head tree")
    if observed_base_tree != subject.get("base_tree"):
        problems.append("base tree does not match the admitted base tree")
    ancestry = _git(repo_root, "merge-base", "--is-ancestor", base, head, check=False)
    if ancestry.returncode != 0:
        problems.append("admitted base is not an ancestor of admitted head")
    try:
        changed = _git(repo_root, "diff", "--name-only", "--no-renames", base, head).stdout.splitlines()
    except (OSError, subprocess.CalledProcessError) as exc:
        problems.append(f"changed-path observation failed: {exc}")
    else:
        if changed_paths_sha256(changed) != subject.get("changed_paths_sha256"):
            problems.append("changed-path digest does not match the exact base-to-head diff")
    if require_clean and _git(repo_root, "status", "--porcelain").stdout:
        problems.append("repository worktree is not clean at the admitted head")
    return problems


def validate_postmerge(
    policy: dict[str, Any],
    *,
    merge_revision: str,
    integration_ref: str,
    post_merge_checks: dict[str, Any],
    repo_root: Path,
) -> list[str]:
    problems = _schema_problems("policy", policy)
    subject = policy.get("subject", {})
    base = str(subject.get("base_revision", ""))
    head = str(subject.get("head_revision", ""))
    try:
        ref_revision = _git(repo_root, "rev-parse", integration_ref).stdout.strip()
        parent_line = _git(repo_root, "show", "-s", "--format=%P", merge_revision).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        return [*problems, f"post-merge git observation failed: {exc}"]
    if ref_revision != merge_revision:
        problems.append("integration ref does not identify the claimed merge revision")
    parents = parent_line.split()
    if parents != [base, head]:
        problems.append("merge commit must preserve exact base and head as its two ordered parents")
    for revision, label in ((base, "base"), (head, "head")):
        ancestry = _git(repo_root, "merge-base", "--is-ancestor", revision, merge_revision, check=False)
        if ancestry.returncode != 0:
            problems.append(f"merge revision does not preserve admitted {label} ancestry")
    if post_merge_checks.get("revision") != merge_revision:
        problems.append("post-merge checks do not bind the exact merge revision")
    checks = post_merge_checks.get("checks")
    if not isinstance(checks, list) or not checks:
        problems.append("post-merge checks are required")
    else:
        names: set[str] = set()
        for index, check_record in enumerate(checks):
            if not isinstance(check_record, dict):
                problems.append(f"post-merge check {index} is not an object")
                continue
            name = str(check_record.get("name", ""))
            if not name or name in names:
                problems.append("post-merge check names must be nonempty and unique")
            names.add(name)
            if check_record.get("state") != "success":
                problems.append(f"post-merge check {name or index} is not successful")
            if check_record.get("revision") != merge_revision:
                problems.append(f"post-merge check {name or index} does not bind the merge revision")
    return problems


def _write_report(path: Path | None, mode: str, problems: list[str]) -> None:
    result = {
        "schema": "facman.d2_integration_admission_report.v1",
        "mode": mode,
        "result": "refused" if problems else "pass",
        "problems": problems,
        "authority_granted": False,
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if path is None:
        print(rendered, end="")
    else:
        path.write_text(rendered, encoding="utf-8")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    subparsers = parser.add_subparsers(dest="mode", required=True)
    premerge = subparsers.add_parser("premerge")
    premerge.add_argument("--implementation", type=Path, required=True)
    premerge.add_argument("--assurance", type=Path, required=True)
    premerge.add_argument("--policy", type=Path, required=True)
    premerge.add_argument("--allow-dirty", action="store_true")
    postmerge = subparsers.add_parser("postmerge")
    postmerge.add_argument("--policy", type=Path, required=True)
    postmerge.add_argument("--merge-revision", required=True)
    postmerge.add_argument("--integration-ref", default="refs/heads/dev")
    postmerge.add_argument("--checks", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.mode == "premerge":
            implementation = load_json(args.implementation)
            assurance = load_json(args.assurance)
            policy = load_json(args.policy)
            problems = validate_premerge(
                implementation,
                assurance,
                policy,
                implementation_sha256=sha256(args.implementation),
                assurance_sha256=sha256(args.assurance),
                repo_root=args.repo_root,
                require_clean=not args.allow_dirty,
            )
        else:
            policy = load_json(args.policy)
            checks = load_json(args.checks)
            problems = validate_postmerge(
                policy,
                merge_revision=args.merge_revision,
                integration_ref=args.integration_ref,
                post_merge_checks=checks,
                repo_root=args.repo_root,
            )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        problems = [str(exc)]
    _write_report(args.output, args.mode, problems)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
