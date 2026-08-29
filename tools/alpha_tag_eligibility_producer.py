# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Produce an exact, non-effecting alpha tag eligibility artifact."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import alpha_asset_set, alpha_tag_gate, json_contract

WORK_UNIT = "FACMAN-ALPHA-TAG-ELIGIBILITY-PRODUCER-01"
ELIGIBILITY_SCHEMA = (
    ROOT / "contracts/schema/release/alpha_tag_eligibility.v1.schema.json"
)
PRODUCER_RECEIPT_SCHEMA = (
    ROOT
    / "tools/schema/alpha_tag_eligibility_producer_receipt.v1.schema.json"
)
QUALIFICATION_SCHEMA = (
    ROOT
    / "contracts/schema/release/alpha1_final_dev_three_root_qualification.v1.schema.json"
)
CANDIDATE_SCHEMA = ROOT / "contracts/schema/release/release_candidate.v1.schema.json"
ALPHA_RELEASE_SOURCE = ROOT / "release/index/alpha_release_source.v1.toml"
REVISION = re.compile(r"^[0-9a-f]{40}$")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_bytes(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def load_json_array(path: Path) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError(f"{path} must contain an array of JSON objects")
    return value


def schema_problems(
    value: dict[str, Any], schema: Path, label: str
) -> list[str]:
    return [
        f"{label}: {problem}"
        for problem in json_contract.validate(value, json_contract.load_schema(schema))
    ]


def parse_time(value: str) -> dt.datetime:
    parsed = alpha_tag_gate._parse_time(value)
    if parsed is None:
        raise ValueError("observed time must be a timezone-aware ISO timestamp")
    return parsed


def git(root: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=True,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout.strip()


def provider_main_mapping(values: Iterable[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values:
        provider_id, separator, revision = value.partition("=")
        if not separator or provider_id in result or REVISION.fullmatch(revision) is None:
            raise ValueError(f"invalid provider main observation: {value}")
        result[provider_id] = revision
    if set(result) != {"universal_launcher", "universal_setup"}:
        raise ValueError("provider main observations must contain exact ULK and USK revisions")
    return result


def _required_checks(
    github_check_runs: dict[str, Any],
    *,
    revision: str,
    observed_at: dt.datetime,
) -> list[dict[str, Any]]:
    policy = alpha_tag_gate._toml(alpha_tag_gate.POLICY_PATH)
    expected_app = int(policy["required_check_app_id"])
    freshness = dt.timedelta(hours=int(policy["required_check_freshness_hours"]))
    authenticated = alpha_tag_gate._authenticated_check_runs(github_check_runs)
    records: list[dict[str, Any]] = []
    for name in policy["required_checks"]:
        matches: list[tuple[dt.datetime, dict[str, Any]]] = []
        for run in authenticated:
            completed = alpha_tag_gate._parse_time(str(run.get("completed_at", "")))
            if (
                run.get("name") == name
                and run.get("head_sha") == revision
                and str(run.get("status", "")).lower() == "completed"
                and str(run.get("conclusion", "")).lower() == "success"
                and run.get("app", {}).get("id") == expected_app
                and completed is not None
                and dt.timedelta(minutes=-5) <= observed_at - completed <= freshness
            ):
                matches.append((completed, run))
        if not matches:
            raise ValueError(f"authenticated GitHub evidence lacks fresh required check {name}")
        records.append(
            {
                "name": name,
                "head_sha": revision,
                "status": "completed",
                "conclusion": "success",
                "app_id": expected_app,
            }
        )
    return records


def _qualification_and_candidate_problems(
    qualification: dict[str, Any],
    candidate: dict[str, Any],
    *,
    qualification_path: Path,
    candidate_path: Path,
) -> list[str]:
    problems = schema_problems(
        qualification, QUALIFICATION_SCHEMA, "three-root qualification"
    )
    problems.extend(schema_problems(candidate, CANDIDATE_SCHEMA, "candidate"))
    if problems:
        return problems
    try:
        packages = alpha_asset_set.validate_qualification(
            qualification, str(candidate["source"]["revision"])
        )
    except ValueError as exc:
        return [str(exc)]
    if qualification.get("source_tree") != candidate["source"].get("tree"):
        problems.append("qualification and candidate source trees differ")
    if sha256(qualification_path) != candidate["evidence"].get("test_summary_sha256"):
        problems.append("candidate assurance digest differs from qualification bytes")
    if (
        qualification.get("comparison_table_sha256")
        != candidate["resolution"].get("root_sha256")
    ):
        problems.append("candidate implementation digest differs from comparison table")
    if (
        sha256(ALPHA_RELEASE_SOURCE)
        != candidate["three_key"]["policy"].get("evidence_sha256")
    ):
        problems.append("candidate control digest differs from alpha release source")
    if sha256(candidate_path) == "0" * 64:
        problems.append("candidate digest is invalid")
    expected_artifacts = {
        (str(item["filename"]), str(item["archive_sha256"]), int(item["archive_bytes"]))
        for item in packages.values()
    }
    candidate_artifacts = {
        (str(item.get("name")), str(item.get("sha256")), int(item.get("bytes", 0)))
        for item in candidate.get("artifacts", [])
        if isinstance(item, dict)
    }
    if candidate_artifacts != expected_artifacts:
        problems.append("candidate package bytes differ from three-root qualification")
    contract_sets = {
        str(item.get("contract_set_sha256")) for item in packages.values()
    }
    if contract_sets != {alpha_tag_gate.current_contract_set_sha256()}:
        problems.append("qualification contract set differs from release source")
    return problems


def produce_records(
    *,
    candidate_path: Path,
    qualification_path: Path,
    product_revision: str,
    product_tree: str,
    checkout_clean: bool,
    protected_dev_revision: str,
    github_ref: dict[str, Any],
    github_check_runs: dict[str, Any],
    github_branch_rules: list[dict[str, Any]],
    github_tag_rulesets: list[dict[str, Any]],
    tag_ruleset_observation: dict[str, Any],
    tag_ruleset_observation_path: Path,
    provider_main_revisions: dict[str, str],
    existing_tags: Iterable[str],
    existing_ledger_versions: Iterable[str],
    qualification_run_id: int,
    control_source_revision: str,
    control_source_tree: str,
    control_source_ref: str,
    github_run_id: int,
    observed_at: dt.datetime,
) -> tuple[dict[str, Any], dict[str, Any]]:
    candidate_path = candidate_path.resolve()
    qualification_path = qualification_path.resolve()
    tag_ruleset_observation_path = tag_ruleset_observation_path.resolve()
    candidate = load_json(candidate_path)
    qualification = load_json(qualification_path)
    problems = _qualification_and_candidate_problems(
        qualification,
        candidate,
        qualification_path=qualification_path,
        candidate_path=candidate_path,
    )
    if product_revision != candidate.get("source", {}).get("revision"):
        problems.append("observed product revision differs from candidate")
    if product_tree != candidate.get("source", {}).get("tree"):
        problems.append("observed product tree differs from candidate")
    if not checkout_clean:
        problems.append("observed product checkout is dirty")
    if protected_dev_revision != product_revision:
        problems.append("protected dev differs from frozen product source")
    candidate_providers = {
        str(item.get("id")): str(item.get("revision"))
        for item in candidate.get("providers", {}).get("identities", [])
        if isinstance(item, dict)
    }
    if candidate_providers != provider_main_revisions:
        problems.append("provider pins are not the authenticated canonical main revisions")
    if qualification_run_id < 1 or github_run_id < 1:
        problems.append("qualification and producer workflow run IDs must be positive")
    if REVISION.fullmatch(control_source_revision) is None:
        problems.append("control-plane source revision is invalid")
    if REVISION.fullmatch(control_source_tree) is None:
        problems.append("control-plane source tree is invalid")
    if not control_source_ref:
        problems.append("control-plane source ref is missing")
    if (
        tag_ruleset_observation_path
        != alpha_tag_gate.TAG_RULESET_OBSERVATION_PATH.resolve()
    ):
        problems.append("tag ruleset observation is not the reviewed canonical path")
    if problems:
        raise ValueError("; ".join(problems))

    check_records = _required_checks(
        github_check_runs, revision=product_revision, observed_at=observed_at
    )
    policy = alpha_tag_gate._toml(alpha_tag_gate.POLICY_PATH)
    existing_tag_set = set(existing_tags)
    existing_ledger_set = set(existing_ledger_versions)
    existing_versions = sorted(
        alpha_tag_gate._alpha_versions(existing_tag_set)
        | alpha_tag_gate._alpha_versions(existing_ledger_set),
        key=lambda item: int(
            alpha_tag_gate.ALPHA_VERSION.fullmatch(item).group(1)  # type: ignore[union-attr]
        ),
    )
    next_number = alpha_tag_gate.next_alpha_number(existing_versions)
    version = str(candidate["version"])
    tag = f"v{version}"
    package_profiles = [str(item["profile"]) for item in qualification["packages"]]
    role_inputs = (
        ("implementation", "facman-alpha1-three-root-byte-comparison", "implementation"),
        ("assurance", "facman-alpha1-qualification-assurance", "assurance"),
        ("control", "facman-alpha1-release-source-control", "policy"),
    )
    attestations = [
        {
            "role": role,
            "issuer": issuer,
            "source_revision": product_revision,
            "source_tree": product_tree,
            "result": "pass",
            "evidence_sha256": candidate["three_key"][candidate_key][
                "evidence_sha256"
            ],
        }
        for role, issuer, candidate_key in role_inputs
    ]
    eligibility = {
        "schema": "facman.alpha_tag_eligibility.v1",
        "work_unit": "FACMAN-AUTONOMOUS-ALPHA-DELEGATION-01",
        "version": version,
        "tag": tag,
        "release_significance": "package_bytes",
        "source": {
            "revision": product_revision,
            "tree": product_tree,
            "ref": "dev",
            "protected": True,
            "clean": True,
        },
        "candidate": {
            "path": "candidate.v1.json",
            "sha256": sha256(candidate_path),
            "status": "qualified",
            "three_root_reproducible": True,
        },
        "providers": {
            "workspace_lock_sha256": candidate["providers"]["workspace_lock_sha256"],
            "provider_lock_sha256": candidate["providers"]["provider_lock_sha256"],
            "canonical_main_reachable": True,
            "mixed_identity": False,
        },
        "contracts": {
            "contract_set_sha256": qualification["packages"][0][
                "contract_set_sha256"
            ],
            "state_identity": "facman.workspace.v1",
            "package_profiles": package_profiles,
        },
        "checks": {
            "source_revision": product_revision,
            "observed_at": observed_at.isoformat().replace("+00:00", "Z"),
            "required_unknown_skips": 0,
            "runs": check_records,
        },
        "attestations": attestations,
        "allocation": {
            "next_number": next_number,
            "existing_versions": existing_versions,
            "number_reused": False,
            "retroactive_bulk_allocation": False,
        },
        "authority": {
            "tag_creation": True,
            "publication": False,
            "signing": False,
            "beta_rc_stable_tags": False,
            "protected_dev_merge": False,
            "route_effects": False,
            "support_activation": False,
            "human_verdict": False,
        },
    }
    problems = schema_problems(eligibility, ELIGIBILITY_SCHEMA, "eligibility")
    problems.extend(
        alpha_tag_gate.validate(
            eligibility,
            candidate,
            candidate_path=candidate_path,
            protected_dev_revision=protected_dev_revision,
            head_revision=product_revision,
            head_tree=product_tree,
            checkout_clean=checkout_clean,
            existing_tags=existing_tag_set,
            existing_ledger_versions=existing_ledger_set,
            github_ref=github_ref,
            github_check_runs=github_check_runs,
            github_branch_rules=github_branch_rules,
            github_tag_rulesets=github_tag_rulesets,
            tag_ruleset_observation=tag_ruleset_observation,
            now=observed_at,
        )
    )
    if problems:
        raise ValueError("; ".join(problems))

    tag_ruleset_ids = alpha_tag_gate.matching_tag_ruleset_ids(
        github_tag_rulesets, tag, policy, tag_ruleset_observation
    )
    receipt = {
        "schema": "facman.alpha_tag_eligibility_producer_receipt.v1",
        "work_unit": WORK_UNIT,
        "product_source": {
            "revision": product_revision,
            "tree": product_tree,
            "ref": "dev",
        },
        "control_plane_source": {
            "revision": control_source_revision,
            "tree": control_source_tree,
            "ref": control_source_ref,
            "clean": True,
        },
        "qualification": {
            "run_id": qualification_run_id,
            "sha256": sha256(qualification_path),
            "candidate_sha256": sha256(candidate_path),
        },
        "requested_tag": tag,
        "checks": {
            "observed_at": eligibility["checks"]["observed_at"],
            "required_names": [str(item) for item in policy["required_checks"]],
            "required_unknown_skips": 0,
        },
        "providers": provider_main_revisions,
        "tag_ruleset_ids": tag_ruleset_ids,
        "tag_ruleset_observation": {
            "path": alpha_tag_gate.TAG_RULESET_OBSERVATION_PATH.relative_to(
                alpha_tag_gate.ROOT
            ).as_posix(),
            "sha256": sha256(tag_ruleset_observation_path),
        },
        "workflow": {"run_id": github_run_id},
        "outputs": {
            "eligibility_sha256": hashlib.sha256(json_bytes(eligibility)).hexdigest(),
            "candidate_sha256": sha256(candidate_path),
        },
        "authority": {
            "tag_creation": False,
            "publication": False,
            "signing": False,
            "route_effects": False,
            "support_activation": False,
            "human_verdict": False,
        },
    }
    problems = schema_problems(receipt, PRODUCER_RECEIPT_SCHEMA, "producer receipt")
    if problems:
        raise ValueError("; ".join(problems))
    return eligibility, receipt


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--candidate", required=True, type=Path)
    value.add_argument("--qualification", required=True, type=Path)
    value.add_argument("--product-root", required=True, type=Path)
    value.add_argument("--protected-dev-revision", required=True)
    value.add_argument("--github-ref-json", required=True, type=Path)
    value.add_argument("--github-check-runs-json", required=True, type=Path)
    value.add_argument("--github-branch-rules-json", required=True, type=Path)
    value.add_argument("--github-tag-rulesets-json", required=True, type=Path)
    value.add_argument(
        "--tag-ruleset-observation",
        type=Path,
        default=alpha_tag_gate.TAG_RULESET_OBSERVATION_PATH,
    )
    value.add_argument("--provider-main", action="append", default=[])
    value.add_argument("--existing-tag", action="append", default=[])
    value.add_argument("--ledger-version", action="append", default=[])
    value.add_argument("--qualification-run-id", required=True, type=int)
    value.add_argument("--control-source-revision", required=True)
    value.add_argument("--control-source-tree", required=True)
    value.add_argument("--control-source-ref", required=True)
    value.add_argument("--github-run-id", required=True, type=int)
    value.add_argument("--observed-at")
    value.add_argument("--output", required=True, type=Path)
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    output = args.output.resolve()
    try:
        if output.exists():
            raise ValueError(f"output directory must be new: {output}")
        product_root = args.product_root.resolve()
        product_revision = git(product_root, "rev-parse", "HEAD")
        product_tree = git(product_root, "rev-parse", "HEAD^{tree}")
        product_clean = not bool(git(product_root, "status", "--porcelain"))
        control_revision = git(ROOT, "rev-parse", "HEAD")
        control_tree = git(ROOT, "rev-parse", "HEAD^{tree}")
        control_clean = not bool(git(ROOT, "status", "--porcelain"))
        if control_revision != args.control_source_revision:
            raise ValueError("declared control-plane revision differs from checkout")
        if control_tree != args.control_source_tree:
            raise ValueError("declared control-plane tree differs from checkout")
        if not control_clean:
            raise ValueError("control-plane checkout is dirty")
        observed_at = (
            parse_time(args.observed_at)
            if args.observed_at
            else dt.datetime.now(dt.timezone.utc)
        )
        eligibility, receipt = produce_records(
            candidate_path=args.candidate,
            qualification_path=args.qualification,
            product_revision=product_revision,
            product_tree=product_tree,
            checkout_clean=product_clean,
            protected_dev_revision=args.protected_dev_revision,
            github_ref=load_json(args.github_ref_json),
            github_check_runs=load_json(args.github_check_runs_json),
            github_branch_rules=load_json_array(args.github_branch_rules_json),
            github_tag_rulesets=load_json_array(args.github_tag_rulesets_json),
            tag_ruleset_observation=load_json(args.tag_ruleset_observation),
            tag_ruleset_observation_path=args.tag_ruleset_observation.resolve(),
            provider_main_revisions=provider_main_mapping(args.provider_main),
            existing_tags=args.existing_tag,
            existing_ledger_versions=(
                set(args.ledger_version) | alpha_tag_gate.ledger_versions()
            ),
            qualification_run_id=args.qualification_run_id,
            control_source_revision=control_revision,
            control_source_tree=control_tree,
            control_source_ref=args.control_source_ref,
            github_run_id=args.github_run_id,
            observed_at=observed_at,
        )
        output.mkdir(parents=True)
        (output / "eligibility.v1.json").write_bytes(json_bytes(eligibility))
        (output / "candidate.v1.json").write_bytes(args.candidate.read_bytes())
        (output / "producer-receipt.v1.json").write_bytes(json_bytes(receipt))
    except (
        OSError,
        ValueError,
        json.JSONDecodeError,
        subprocess.CalledProcessError,
    ) as exc:
        print(f"alpha-tag-eligibility-producer: {exc}", file=sys.stderr)
        return 1
    print(
        "alpha-tag-eligibility-producer: ok "
        f"({eligibility['tag']}; product={product_revision}; control={control_revision}; "
        "no tag effect)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
