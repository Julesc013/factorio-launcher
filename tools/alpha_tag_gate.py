# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Fail-closed eligibility gate for immutable, unpublished FacMan alpha tags."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import json_contract

POLICY_PATH = ROOT / "release/index/alpha_delegation.v1.toml"
VERSION_TRAIN_PATH = ROOT / "release/index/version_train.v1.toml"
AUTONOMY_PATH = ROOT / "release/index/autonomy_policy.v1.toml"
BRANCH_POLICY_PATH = ROOT / "release/index/branch_policy.v1.toml"
CHANNELS_PATH = ROOT / "release/index/channels.v1.toml"
VERSION_PATH = ROOT / "release/index/version.v2.toml"
BUILD_MANIFEST_PATH = ROOT / "release/index/build_manifest.v1.toml"
WORKSPACE_LOCK_PATH = ROOT / "release/index/workspace_lock.v1.toml"
PROVIDER_LOCK_PATH = ROOT / "release/index/providers.lock.v2.toml"
GENERATED_VERSION_HEADER_PATH = ROOT / "runtime/core/generated/version.h"
ELIGIBILITY_SCHEMA_PATH = (
    ROOT / "contracts/schema/release/alpha_tag_eligibility.v1.schema.json"
)
CANDIDATE_SCHEMA_PATH = ROOT / "contracts/schema/release/release_candidate.v1.schema.json"
LEDGER_ROOT = ROOT / "release/ledger"
ALPHA_VERSION = re.compile(r"^0\.1\.0-alpha\.([1-9][0-9]*)$")
ALPHA_TAG = re.compile(r"^v0\.1\.0-alpha\.([1-9][0-9]*)$")
CONTRACT_SET_DEFINE = re.compile(
    r'^#define FACMAN_CONTRACT_SET_SHA256 "([0-9a-f]{64})"$', re.MULTILINE
)


def _toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        value = tomllib.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a TOML table")
    return value


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _json_array(path: Path) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError(f"{path} must contain a JSON array of objects")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode:
        raise ValueError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout.strip()


def _schema_problems(value: dict[str, Any], path: Path, label: str) -> list[str]:
    return [
        f"{label} schema rejection: {problem}"
        for problem in json_contract.validate(value, json_contract.load_schema(path))
    ]


def _alpha_versions(values: Iterable[str]) -> set[str]:
    observed: set[str] = set()
    for value in values:
        match = ALPHA_TAG.fullmatch(value)
        if match:
            observed.add(f"0.1.0-alpha.{match.group(1)}")
            continue
        if ALPHA_VERSION.fullmatch(value):
            observed.add(value)
    return observed


def ledger_versions() -> set[str]:
    if not LEDGER_ROOT.is_dir():
        return set()
    return {
        path.name
        for path in LEDGER_ROOT.iterdir()
        if path.is_dir() and ALPHA_VERSION.fullmatch(path.name)
    }


def local_alpha_tags() -> set[str]:
    return set(filter(None, _git("tag", "--list", "v0.1.0-alpha.*").splitlines()))


def next_alpha_number(existing: Iterable[str]) -> int:
    numbers = [
        int(match.group(1))
        for value in existing
        if (match := ALPHA_VERSION.fullmatch(value)) is not None
    ]
    return max(numbers, default=0) + 1


def current_contract_set_sha256() -> str:
    match = CONTRACT_SET_DEFINE.search(
        GENERATED_VERSION_HEADER_PATH.read_text(encoding="utf-8")
    )
    if match is None:
        raise ValueError("generated version header lacks the contract-set digest")
    return match.group(1)


def validate_policy() -> list[str]:
    problems: list[str] = []
    try:
        policy = _toml(POLICY_PATH)
        train = _toml(VERSION_TRAIN_PATH)
        autonomy = _toml(AUTONOMY_PATH)
        branch = _toml(BRANCH_POLICY_PATH)
        channels = _toml(CHANNELS_PATH)
    except (OSError, ValueError, tomllib.TOMLDecodeError) as exc:
        return [f"alpha delegation policy cannot be read: {exc}"]

    expected_policy = {
        "schema": "facman.alpha_delegation.v1",
        "policy_id": "FACMAN-AUTONOMOUS-ALPHA-DELEGATION-01",
        "status": "active_when_reachable_from_protected_dev_and_tag_ruleset_enforced",
        "product_id": "facman",
        "release_train": "0.1.0-alpha.N",
        "source_ref": "dev",
        "source_requirement": "exact_current_protected_dev_commit_and_tree",
        "tag_type": "annotated",
        "tag_pattern": r"^v0\.1\.0-alpha\.([1-9][0-9]*)$",
        "tag_every_commit": False,
        "required_check_freshness_hours": 24,
        "required_check_app_id": 15368,
        "required_contract_set_source": "runtime/core/generated/version.h",
        "required_state_identity": "facman.workspace.v1",
        "required_package_profile": "windows_winforms_technical_preview_x64",
        "required_tag_ruleset_include": "refs/tags/v0.1.0-alpha.*",
        "required_tag_ruleset_enforcement": "active",
        "required_tag_rules": ["deletion", "update"],
        "tag_ruleset_bypass_actors_allowed": False,
    }
    for field, expected in expected_policy.items():
        if policy.get(field) != expected:
            problems.append(f"alpha delegation {field} must be {expected!r}")
    if not policy.get("required_checks"):
        problems.append("alpha delegation must bind required checks")
    elif len(policy["required_checks"]) != len(set(policy["required_checks"])):
        problems.append("alpha delegation repeats a required check")
    if not policy.get("release_significant_reasons"):
        problems.append("alpha delegation must define release-significant reasons")

    authority = policy.get("authority", {})
    expected_authority = {
        "version_allocation": True,
        "tag_creation": True,
        "alpha_supersession": True,
        "protected_dev_merge": False,
        "publication": False,
        "signing": False,
        "beta_rc_stable_tags": False,
        "route_effects": False,
        "support_activation": False,
        "human_verdict": False,
    }
    if authority != expected_authority:
        problems.append("alpha delegation authority ceiling has drifted")

    if train.get("activation_status") != "partial_alpha_tagging_active":
        problems.append("version train does not record partial alpha-tagging activation")
    for field in ("version_allocation_authorized", "tag_creation_authorized"):
        if train.get(field) is not True:
            problems.append(f"version train {field} must be true")
    for field in ("signing_authorized", "publication_authorized"):
        if train.get(field) is not False:
            problems.append(f"version train {field} must remain false")
    train_authority = train.get("authority", {})
    if train_authority.get("version_allocation") is not True:
        problems.append("version train must authorize bounded alpha allocation")
    if train_authority.get("tag_creation") is not True:
        problems.append("version train must authorize bounded alpha tag creation")
    if any(
        train_authority.get(field) is not False
        for field in ("signing", "publication", "withdrawal", "stable_promotion")
    ):
        problems.append("version train grants authority beyond alpha allocation and tags")
    classes = {item.get("id"): item for item in train.get("release_class", [])}
    if classes.get("alpha", {}).get("currently_authorized") is not True:
        problems.append("version train alpha class is not active")
    for class_id in ("snapshot", "beta", "rc", "stable_0x", "stable_1x"):
        if classes.get(class_id, {}).get("currently_authorized") is not False:
            problems.append(f"version train improperly authorizes {class_id}")

    autonomy_authority = autonomy.get("authority", {})
    if autonomy.get("activation_status") != "partial_alpha_tagging_active":
        problems.append("autonomy policy does not record partial alpha-tagging activation")
    if autonomy_authority.get("alpha_tag_creation") is not True:
        problems.append("autonomy policy does not authorize alpha tag creation")
    if any(
        value is not False
        for key, value in autonomy_authority.items()
        if key != "alpha_tag_creation"
    ):
        problems.append("autonomy policy grants authority beyond alpha tag creation")

    delegated = branch.get("delegated_development", {})
    if delegated.get("autonomous_alpha_tagging_active") is not True:
        problems.append("branch policy does not activate autonomous alpha tagging")
    if delegated.get("protected_dev_merge_active") is not False:
        problems.append("branch policy improperly activates protected dev integration")
    if branch.get("automation_authority", {}).get("self_merge") is not False:
        problems.append("branch policy must continue to prohibit self-merge")

    alpha_channel = next(
        (
            item
            for item in channels.get("channel", [])
            if isinstance(item, dict) and item.get("id") == "alpha"
        ),
        {},
    )
    if alpha_channel.get("publication_authorized") is not False:
        problems.append("alpha GitHub prerelease publication must remain inactive")
    return problems


def _parse_time(value: str) -> dt.datetime | None:
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(dt.timezone.utc)


def _authenticated_check_runs(value: dict[str, Any]) -> list[dict[str, Any]]:
    runs = value.get("check_runs", [])
    return [item for item in runs if isinstance(item, dict)] if isinstance(runs, list) else []


def matching_tag_ruleset_ids(
    rulesets: list[dict[str, Any]], tag: str, policy: dict[str, Any]
) -> list[int]:
    if ALPHA_TAG.fullmatch(tag) is None:
        return []
    required_include = str(policy["required_tag_ruleset_include"])
    required_rules = set(policy["required_tag_rules"])
    matches: list[int] = []
    for ruleset in rulesets:
        raw_conditions = ruleset.get("conditions")
        conditions = (
            raw_conditions.get("ref_name", {})
            if isinstance(raw_conditions, dict)
            else {}
        )
        if not isinstance(conditions, dict):
            conditions = {}
        includes = conditions.get("include", [])
        excludes = conditions.get("exclude", [])
        if not isinstance(includes, list):
            includes = []
        if not isinstance(excludes, list):
            excludes = []
        raw_rules = ruleset.get("rules")
        rule_types = {
            item.get("type")
            for item in (raw_rules if isinstance(raw_rules, list) else [])
            if isinstance(item, dict)
        }
        ruleset_id = ruleset.get("id")
        if (
            ruleset.get("target") == "tag"
            and ruleset.get("enforcement") == policy["required_tag_ruleset_enforcement"]
            and ruleset.get("bypass_actors") == []
            and required_include in includes
            and excludes == []
            and required_rules.issubset(rule_types)
            and type(ruleset_id) is int
            and ruleset_id > 0
        ):
            matches.append(ruleset_id)
    return sorted(set(matches))


def validate(
    eligibility: dict[str, Any],
    candidate: dict[str, Any],
    *,
    candidate_path: Path,
    protected_dev_revision: str,
    head_revision: str,
    head_tree: str,
    checkout_clean: bool,
    existing_tags: Iterable[str],
    existing_ledger_versions: Iterable[str],
    github_ref: dict[str, Any] | None = None,
    github_check_runs: dict[str, Any] | None = None,
    github_branch_rules: list[dict[str, Any]] | None = None,
    github_tag_rulesets: list[dict[str, Any]] | None = None,
    now: dt.datetime | None = None,
) -> list[str]:
    existing_tag_set = set(existing_tags)
    existing_ledger_set = set(existing_ledger_versions)
    problems = validate_policy()
    problems.extend(_schema_problems(eligibility, ELIGIBILITY_SCHEMA_PATH, "eligibility"))
    problems.extend(_schema_problems(candidate, CANDIDATE_SCHEMA_PATH, "candidate"))
    if problems:
        return problems

    source = eligibility["source"]
    revision = source["revision"]
    tree = source["tree"]
    if source.get("ref") != "dev" or source.get("protected") is not True:
        problems.append("eligibility source is not protected dev")
    if source.get("clean") is not True:
        problems.append("eligibility source is not recorded clean")
    if protected_dev_revision != revision:
        problems.append("protected dev moved or differs from the admitted alpha source")
    if head_revision != revision or head_tree != tree:
        problems.append("checkout does not match the admitted source commit and tree")
    if not checkout_clean:
        problems.append("alpha tag source checkout is dirty")
    if github_ref is None:
        problems.append("authenticated GitHub dev observation was not supplied")
    elif github_ref.get("object", {}).get("sha") != revision:
        problems.append("authenticated GitHub dev observation differs from the admitted source")

    version = eligibility["version"]
    tag = eligibility["tag"]
    policy = _toml(POLICY_PATH)
    if eligibility.get("release_significance") not in policy["release_significant_reasons"]:
        problems.append("alpha change is not release-significant under the delegated policy")
    expected_invocation_authority = {
        "tag_creation": True,
        "publication": False,
        "signing": False,
        "beta_rc_stable_tags": False,
        "protected_dev_merge": False,
        "route_effects": False,
        "support_activation": False,
        "human_verdict": False,
    }
    if eligibility.get("authority") != expected_invocation_authority:
        problems.append("eligibility authority exceeds one unpublished alpha tag")
    version_match = ALPHA_VERSION.fullmatch(version)
    tag_match = ALPHA_TAG.fullmatch(tag)
    if not version_match or not tag_match or version_match.group(1) != tag_match.group(1):
        problems.append("alpha version and tag number do not match")
    tracked_version = _toml(VERSION_PATH)
    build_manifest = _toml(BUILD_MANIFEST_PATH)
    expected_version_identity = {
        "semver": version,
        "canonical_version": f"facman-{version}",
        "filename_version": f"facman-{version}",
        "component_version": version,
        "build_kind": "release",
        "channel": "alpha",
    }
    for field, expected in expected_version_identity.items():
        if tracked_version.get(field) != expected:
            problems.append(f"tracked version metadata {field} does not bind {version}")
    for field in ("canonical_version", "filename_version", "build_kind", "channel"):
        if build_manifest.get(field) != tracked_version.get(field):
            problems.append(f"build manifest {field} differs from tracked version metadata")

    contracts = eligibility["contracts"]
    if contracts.get("contract_set_sha256") != current_contract_set_sha256():
        problems.append("eligibility contract-set digest differs from the current source tree")
    if contracts.get("state_identity") != policy["required_state_identity"]:
        problems.append("eligibility state identity differs from the delegated policy")
    if contracts.get("package_profile") != policy["required_package_profile"]:
        problems.append("eligibility package profile differs from the delegated policy")

    if candidate.get("version") != version or candidate.get("release_class") != "alpha":
        problems.append("candidate does not bind the requested alpha version")
    eligibility_candidate = eligibility["candidate"]
    if (
        eligibility_candidate.get("status") != "qualified"
        or eligibility_candidate.get("three_root_reproducible") is not True
    ):
        problems.append("eligibility does not bind a qualified three-root candidate")
    if candidate.get("status") != "qualified":
        problems.append("candidate is not qualified")
    candidate_source = candidate.get("source", {})
    if candidate_source != {
        "revision": revision,
        "tree": tree,
        "ref": "dev",
        "ref_kind": "dev",
        "clean": True,
    }:
        problems.append("candidate source is not the exact clean protected dev source")
    if _sha256(candidate_path) != eligibility["candidate"]["sha256"]:
        problems.append("candidate digest differs from the eligibility record")
    if any(item.get("signed") is not False for item in candidate.get("artifacts", [])):
        problems.append("alpha tag candidate must remain unsigned")
    if any(item.get("published") is not False for item in candidate.get("artifacts", [])):
        problems.append("alpha tag candidate must remain unpublished")
    if any(value is not False for value in candidate.get("authority", {}).values()):
        problems.append("candidate record improperly grants authority")

    providers = eligibility["providers"]
    if (
        providers.get("canonical_main_reachable") is not True
        or providers.get("mixed_identity") is not False
    ):
        problems.append("eligibility uses mixed or non-canonical provider identities")
    candidate_providers = candidate.get("providers", {})
    expected_lock_digests = {
        "workspace_lock_sha256": _sha256(WORKSPACE_LOCK_PATH),
        "provider_lock_sha256": _sha256(PROVIDER_LOCK_PATH),
    }
    for field in ("workspace_lock_sha256", "provider_lock_sha256"):
        if providers.get(field) != candidate_providers.get(field):
            problems.append(f"candidate and eligibility {field} differ")
        if providers.get(field) != expected_lock_digests[field]:
            problems.append(f"eligibility {field} differs from the current source tree")
    provider_ids = [item.get("id") for item in candidate_providers.get("identities", [])]
    if sorted(provider_ids) != ["universal_launcher", "universal_setup"]:
        problems.append("candidate does not bind exactly the two canonical providers")
    else:
        workspace_components = {
            item.get("id"): item for item in _toml(WORKSPACE_LOCK_PATH).get("component", [])
        }
        provider_records = {
            item.get("id"): item for item in _toml(PROVIDER_LOCK_PATH).get("provider", [])
        }
        for identity in candidate_providers["identities"]:
            provider_id = identity["id"]
            workspace_identity = workspace_components.get(provider_id, {})
            provider_identity = provider_records.get(provider_id, {})
            expected_identity = {
                "revision": workspace_identity.get("pin"),
                "tree": workspace_identity.get("tree"),
                "abi": provider_identity.get("abi_version"),
                "contract_digest": provider_identity.get("contract_digest"),
            }
            for field, expected in expected_identity.items():
                if not expected or identity.get(field) != expected:
                    problems.append(
                        f"candidate {provider_id} {field} differs from canonical locks"
                    )

    attestations = eligibility["attestations"]
    roles = [item["role"] for item in attestations]
    issuers = [item["issuer"] for item in attestations]
    evidence = [item["evidence_sha256"] for item in attestations]
    if sorted(roles) != ["assurance", "control", "implementation"]:
        problems.append("alpha eligibility lacks the exact three attestation roles")
    if len(set(issuers)) != 3:
        problems.append("alpha attestation issuers are not logically independent")
    if len(set(evidence)) != 3:
        problems.append("alpha attestations must bind three distinct evidence records")
    for item in attestations:
        if item.get("result") != "pass":
            problems.append(f"{item['role']} attestation is not passing")
        if item["source_revision"] != revision or item["source_tree"] != tree:
            problems.append(f"{item['role']} attestation is bound to a different source")
    candidate_three_key = candidate.get("three_key", {})
    by_role = {item["role"]: item for item in attestations}
    for field, role in (
        ("implementation", "implementation"),
        ("assurance", "assurance"),
        ("policy", "control"),
    ):
        decision = candidate_three_key.get(field, {})
        if decision.get("role") != role or decision.get("result") != "pass":
            problems.append(f"candidate {field} decision is not passing")
        elif decision.get("evidence_sha256") != by_role.get(role, {}).get("evidence_sha256"):
            problems.append(f"candidate {field} evidence differs from its attestation")

    required_names = list(policy["required_checks"])
    runs = eligibility["checks"]["runs"]
    run_names = [item["name"] for item in runs]
    if len(run_names) != len(set(run_names)) or sorted(run_names) != sorted(required_names):
        problems.append("eligibility does not bind every required check exactly once")
    if eligibility["checks"]["source_revision"] != revision:
        problems.append("check observation is bound to a different source")
    if eligibility["checks"].get("required_unknown_skips") != 0:
        problems.append("required checks contain unknown skips")
    expected_app_id = int(policy["required_check_app_id"])
    for run in runs:
        if run.get("status") != "completed" or run.get("conclusion") != "success":
            problems.append(f"required check {run['name']} is not successful")
        if run["head_sha"] != revision:
            problems.append(f"required check {run['name']} is bound to a different source")
        if run["app_id"] != expected_app_id:
            problems.append(f"required check {run['name']} has an untrusted app identity")

    current = (now or dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone.utc)
    observed = _parse_time(eligibility["checks"]["observed_at"])
    if observed is None:
        problems.append("check observation time is not a timezone-aware ISO timestamp")
    else:
        age = current - observed
        if age < dt.timedelta(minutes=-5):
            problems.append("check observation time is unexpectedly in the future")
        if age > dt.timedelta(hours=int(policy["required_check_freshness_hours"])):
            problems.append("required check observation is stale")

    if github_check_runs is None:
        problems.append("authenticated GitHub check-run observation was not supplied")
    else:
        authenticated = _authenticated_check_runs(github_check_runs)
        for run in runs:
            matches = [
                item
                for item in authenticated
                if item.get("name") == run["name"]
                and item.get("head_sha") == revision
                and str(item.get("status", "")).lower() == "completed"
                and str(item.get("conclusion", "")).lower() == "success"
                and item.get("app", {}).get("id") == expected_app_id
            ]
            fresh_matches = []
            for item in matches:
                completed_at = _parse_time(str(item.get("completed_at", "")))
                if completed_at is None:
                    continue
                completed_age = current - completed_at
                if dt.timedelta(minutes=-5) <= completed_age <= dt.timedelta(
                    hours=int(policy["required_check_freshness_hours"])
                ):
                    fresh_matches.append(item)
            if not fresh_matches:
                problems.append(
                    "authenticated GitHub observation lacks a fresh successful required "
                    f"check {run['name']}"
                )

    if github_branch_rules is None:
        problems.append("authenticated GitHub dev-rule observation was not supplied")
    else:
        rule_checks: list[tuple[str, int]] = []
        strict_rules = 0
        for rule in github_branch_rules:
            if rule.get("type") != "required_status_checks":
                continue
            parameters = rule.get("parameters", {})
            if parameters.get("strict_required_status_checks_policy") is True:
                strict_rules += 1
            for check in parameters.get("required_status_checks", []):
                if isinstance(check, dict):
                    rule_checks.append((str(check.get("context", "")), check.get("integration_id")))
        expected_rule_checks = sorted((name, expected_app_id) for name in required_names)
        if strict_rules < 1 or sorted(rule_checks) != expected_rule_checks:
            problems.append(
                "authenticated GitHub dev rules do not strictly require the approved checks"
            )

    if github_tag_rulesets is None:
        problems.append("authenticated GitHub tag-protection rules were not supplied")
    elif not matching_tag_ruleset_ids(github_tag_rulesets, tag, policy):
        problems.append(
            "authenticated GitHub rules do not prevent alpha tag updates and deletion"
        )

    existing_versions = _alpha_versions(existing_tag_set) | _alpha_versions(
        existing_ledger_set
    )
    allocation = eligibility["allocation"]
    if (
        allocation.get("number_reused") is not False
        or allocation.get("retroactive_bulk_allocation") is not False
    ):
        problems.append("alpha allocation requests reuse or retroactive bulk tagging")
    recorded_versions = set(allocation["existing_versions"])
    if recorded_versions != existing_versions:
        problems.append("alpha allocation record differs from existing tags and ledger")
    expected_number = next_alpha_number(existing_versions)
    if allocation["next_number"] != expected_number:
        problems.append("alpha allocation next number is not the next never-used value")
    if version_match and int(version_match.group(1)) != expected_number:
        problems.append("requested alpha version is not the next never-used value")
    if tag in existing_tag_set:
        problems.append("requested alpha tag already exists and cannot be moved or reused")
    return problems


def annotation_message(eligibility: dict[str, Any]) -> str:
    policy = _toml(POLICY_PATH)
    number = ALPHA_VERSION.fullmatch(eligibility["version"]).group(1)  # type: ignore[union-attr]
    return str(policy["tag_message_template"]).format(
        n=number,
        revision=eligibility["source"]["revision"],
        candidate_sha256=eligibility["candidate"]["sha256"],
    ).replace("\\n", "\n")


def policy_main() -> int:
    problems = validate_policy()
    if problems:
        for problem in problems:
            print(f"alpha-tag-policy: {problem}", file=sys.stderr)
        return 1
    print("alpha-tag-policy: ok")
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--eligibility", required=True)
    result.add_argument("--candidate")
    result.add_argument("--protected-dev-revision", required=True)
    result.add_argument("--github-ref-json", required=True)
    result.add_argument("--github-check-runs-json", required=True)
    result.add_argument("--github-branch-rules-json", required=True)
    result.add_argument("--github-tag-rulesets-json", required=True)
    result.add_argument("--existing-tag", action="append", default=[])
    result.add_argument("--ledger-version", action="append", default=[])
    result.add_argument("--now")
    result.add_argument("--output")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        eligibility_path = Path(args.eligibility).resolve()
        eligibility = _json(eligibility_path)
        candidate_path = (
            Path(args.candidate).resolve()
            if args.candidate
            else (eligibility_path.parent / eligibility.get("candidate", {}).get("path", "")).resolve()
        )
        candidate = _json(candidate_path)
        head_revision = _git("rev-parse", "HEAD")
        head_tree = _git("rev-parse", "HEAD^{tree}")
        checkout_clean = not bool(_git("status", "--porcelain"))
        observed_tags = set(args.existing_tag) | local_alpha_tags()
        observed_ledger = set(args.ledger_version) | ledger_versions()
        github_ref = _json(Path(args.github_ref_json)) if args.github_ref_json else None
        github_checks = (
            _json(Path(args.github_check_runs_json)) if args.github_check_runs_json else None
        )
        github_rules = (
            _json_array(Path(args.github_branch_rules_json))
            if args.github_branch_rules_json
            else None
        )
        github_tag_rulesets = _json_array(Path(args.github_tag_rulesets_json))
        now = _parse_time(args.now) if args.now else None
        if args.now and now is None:
            raise ValueError("--now must be a timezone-aware ISO timestamp")
        problems = validate(
            eligibility,
            candidate,
            candidate_path=candidate_path,
            protected_dev_revision=args.protected_dev_revision,
            head_revision=head_revision,
            head_tree=head_tree,
            checkout_clean=checkout_clean,
            existing_tags=observed_tags,
            existing_ledger_versions=observed_ledger,
            github_ref=github_ref,
            github_check_runs=github_checks,
            github_branch_rules=github_rules,
            github_tag_rulesets=github_tag_rulesets,
            now=now,
        )
    except (OSError, ValueError, json.JSONDecodeError, tomllib.TOMLDecodeError) as exc:
        problems = [f"alpha tag eligibility cannot be evaluated: {exc}"]
        eligibility = {}

    if problems:
        for problem in problems:
            print(f"alpha-tag-gate: {problem}", file=sys.stderr)
        return 1
    plan = {
        "schema": "facman.alpha_tag_plan.v1",
        "eligible": True,
        "tag": eligibility["tag"],
        "version": eligibility["version"],
        "source_revision": eligibility["source"]["revision"],
        "source_tree": eligibility["source"]["tree"],
        "candidate_sha256": eligibility["candidate"]["sha256"],
        "tag_ruleset_ids": matching_tag_ruleset_ids(
            github_tag_rulesets, eligibility["tag"], _toml(POLICY_PATH)
        ),
        "annotation": annotation_message(eligibility),
        "publication": False,
        "signing": False,
    }
    rendered = json.dumps(plan, indent=2, sort_keys=True) + "\n"
    if args.output:
        output = Path(args.output)
        if output.exists():
            print(f"alpha-tag-gate: output already exists: {output}", file=sys.stderr)
            return 1
        output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
