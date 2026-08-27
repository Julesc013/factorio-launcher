# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Validate and apply the FacMan 4.0 Factorio version-family contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tomllib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "release" / "index" / "factorio_version_families.v1.toml"
SCHEMA_PATH = (
    ROOT
    / "contracts"
    / "schema"
    / "factorio"
    / "factorio_version_family_matrix.v1.schema.json"
)
EXPECTED_FAMILIES = (
    ("F100", 100, 1, 0),
    ("F110", 110, 1, 1),
    ("F200", 200, 2, 0),
    ("F210", 210, 2, 1),
)
VERSION_PATTERN = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:\.(0|[1-9][0-9]*))?$")


@dataclass(frozen=True)
class VersionClassification:
    status: str
    family_id: str | None
    normalized_version: str | None
    exact_patch: bool


def load_policy(path: Path = POLICY_PATH) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def canonical_json_sha256(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def classify_version(value: object, policy: dict[str, Any]) -> VersionClassification:
    if not isinstance(value, str):
        return VersionClassification("invalid", None, None, False)
    match = VERSION_PATTERN.fullmatch(value)
    if match is None:
        return VersionClassification("invalid", None, None, False)
    major = int(match.group(1))
    minor = int(match.group(2))
    patch = match.group(3)
    normalized = f"{major}.{minor}" + (f".{int(patch)}" if patch is not None else "")
    for family in policy.get("family", []):
        if family.get("major") == major and family.get("minor") == minor:
            return VersionClassification(
                "eligible",
                str(family.get("id")),
                normalized,
                patch is not None,
            )
    return VersionClassification("outside", None, normalized, patch is not None)


def validate_policy(policy: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    expected_top = {
        "schema": "facman.factorio_version_families.v1",
        "policy_id": "FACMAN-FACTORIO-VERSION-FAMILIES-4.0",
        "product_target": "4.0.0",
        "target_status": "qualified_release_source",
        "identifier_interpretation": "F<major><minor><compatibility-slot-zero>",
        "qualification_claim": "qualified_exact_read_only_observations_without_support_promotion",
        "qualification_corpus": "release/evidence/factorio-version-capability-corpus-4.0.0.v1.json",
        "qualification_matrix": "release/evidence/factorio-version-family-matrix-4.0.0.v1.json",
        "exact_patch_observation_required": True,
        "all_required_families_required": True,
        "support_promotion_authorized": False,
        "route_execution_authorized": False,
    }
    for field, expected in expected_top.items():
        if policy.get(field) != expected:
            problems.append(f"{field} must be {expected!r}")

    families = policy.get("family")
    if not isinstance(families, list):
        return problems + ["family entries are required"]
    actual = [
        (entry.get("id"), entry.get("order"), entry.get("major"), entry.get("minor"))
        for entry in families
        if isinstance(entry, dict)
    ]
    if actual != list(EXPECTED_FAMILIES):
        problems.append(f"family order and mappings must be {list(EXPECTED_FAMILIES)!r}")
    for index, family in enumerate(families):
        if not isinstance(family, dict):
            problems.append(f"family[{index}] must be a table")
            continue
        expected_line = f"{family.get('major')}.{family.get('minor')}.x"
        if family.get("version_line") != expected_line:
            problems.append(f"{family.get('id', index)} version_line must be {expected_line}")
        if family.get("required") is not True:
            problems.append(f"{family.get('id', index)} must be required")
        minimum = family.get("minimum_exact_observations")
        if not isinstance(minimum, int) or isinstance(minimum, bool) or minimum < 1:
            problems.append(f"{family.get('id', index)} needs at least one exact observation")
        capabilities = family.get("required_capabilities")
        if not isinstance(capabilities, list) or not capabilities:
            problems.append(f"{family.get('id', index)} must name required capabilities")
        elif (
            any(not isinstance(item, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", item) for item in capabilities)
            or len(capabilities) != len(set(capabilities))
            or capabilities != sorted(capabilities)
        ):
            problems.append(f"{family.get('id', index)} capabilities must be unique sorted identifiers")
    return problems


def validate_bound_evidence(policy: dict[str, Any], root: Path = ROOT) -> list[str]:
    problems: list[str] = []
    corpus_path = root / str(policy.get("qualification_corpus", ""))
    matrix_path = root / str(policy.get("qualification_matrix", ""))
    try:
        corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
        matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"bound qualification evidence cannot be read: {exc}"]
    if not isinstance(corpus, dict) or not isinstance(matrix, dict):
        return ["bound qualification evidence roots must be objects"]
    expected_corpus = {
        "schema": "factorio.version_capability_corpus.v1",
        "status": "complete",
        "read_only_install_probe": True,
        "user_state_environment_redirected": True,
        "raw_process_output_persisted": False,
        "absolute_paths_persisted": False,
        "selection_mode": "expected_only",
        "installation_count": 4,
    }
    for field, expected in expected_corpus.items():
        if corpus.get(field) != expected:
            problems.append(f"qualification corpus {field} must be {expected!r}")
    if corpus.get("expected_labels") != ["1.0", "1.1", "2.0", "2.1"]:
        problems.append("qualification corpus must bind exactly 1.0, 1.1, 2.0, and 2.1")
    if matrix.get("product_target") != "4.0.0" or matrix.get("overall_status") != "qualified":
        problems.append("qualification matrix must qualify product target 4.0.0")
    if matrix.get("source_corpus_sha256") != canonical_json_sha256(corpus):
        problems.append("qualification matrix does not bind the canonical corpus digest")
    if matrix.get("policy_sha256") != hashlib.sha256(POLICY_PATH.read_bytes()).hexdigest():
        problems.append("qualification matrix does not bind the current family policy")
    families = matrix.get("families")
    if not isinstance(families, list) or [item.get("id") for item in families] != [
        "F100", "F110", "F200", "F210"
    ] or any(item.get("status") != "qualified" for item in families):
        problems.append("qualification matrix must qualify F100, F110, F200, and F210 in order")
    if matrix.get("support_claim") != "unclaimed" or any(matrix.get("authority", {}).values()):
        problems.append("qualification evidence must not promote support or release authority")
    problems.extend(f"qualification matrix schema: {item}" for item in validate_matrix_schema(matrix))
    return problems


def _observed_true_capabilities(installation: dict[str, Any]) -> list[str]:
    capabilities = installation.get("capabilities")
    if not isinstance(capabilities, dict):
        return []
    return sorted(name for name, present in capabilities.items() if isinstance(name, str) and present is True)


def _probe_completed(installation: dict[str, Any], name: str) -> bool:
    probe = installation.get(name)
    return isinstance(probe, dict) and probe.get("status") == "completed"


def build_matrix(
    corpus: dict[str, Any],
    policy: dict[str, Any],
    *,
    policy_sha256: str | None = None,
    generated_utc: str | None = None,
) -> dict[str, Any]:
    policy_problems = validate_policy(policy)
    if policy_problems:
        raise ValueError("invalid family policy: " + "; ".join(policy_problems))

    families = policy["family"]
    families_by_id = {str(entry["id"]): entry for entry in families}
    installations = corpus.get("installations")
    if not isinstance(installations, list):
        installations = []
    observations: list[dict[str, Any]] = []
    candidates_by_family: dict[str, list[dict[str, Any]]] = {
        family_id: [] for family_id in families_by_id
    }

    for raw in installations:
        installation = raw if isinstance(raw, dict) else {}
        reported = installation.get("reported_version", "unknown")
        classification = classify_version(reported, policy)
        observed_capabilities = _observed_true_capabilities(installation)
        required_capabilities = (
            list(families_by_id[classification.family_id]["required_capabilities"])
            if classification.family_id is not None
            else []
        )
        missing_capabilities = sorted(set(required_capabilities) - set(observed_capabilities))
        reasons: list[str] = []
        if installation.get("status") != "probed":
            reasons.append("probe_status_not_probed")
        if installation.get("install_tree_unchanged") is not True:
            reasons.append("install_tree_changed")
        if classification.status == "invalid":
            reasons.append("version_invalid")
        elif classification.status == "outside":
            reasons.append("version_outside_target")
        elif not classification.exact_patch:
            reasons.append("exact_patch_required")
        if not _probe_completed(installation, "version_probe"):
            reasons.append("version_probe_not_completed")
        if not _probe_completed(installation, "help_probe"):
            reasons.append("help_probe_not_completed")
        if missing_capabilities:
            reasons.append("required_capability_missing")

        basic_eligible = (
            classification.status == "eligible"
            and classification.exact_patch
            and installation.get("status") == "probed"
            and installation.get("install_tree_unchanged") is True
            and _probe_completed(installation, "version_probe")
            and _probe_completed(installation, "help_probe")
        )
        accepted = basic_eligible and not missing_capabilities
        observation = {
            "label": str(installation.get("label", "")),
            "reported_version": str(reported),
            "normalized_version": classification.normalized_version,
            "classification_status": classification.status,
            "family_id": classification.family_id,
            "exact_patch": classification.exact_patch,
            "accepted": accepted,
            "observed_capabilities": observed_capabilities,
            "missing_capabilities": missing_capabilities,
            "reasons": reasons,
        }
        observations.append(observation)
        if basic_eligible and classification.family_id is not None:
            candidates_by_family[classification.family_id].append(observation)

    family_results: list[dict[str, Any]] = []
    limitations: list[str] = []
    for family in families:
        family_id = str(family["id"])
        candidates = candidates_by_family[family_id]
        accepted = [observation for observation in candidates if observation["accepted"]]
        capability_sets = [set(item["observed_capabilities"]) for item in candidates]
        intersection = sorted(set.intersection(*capability_sets)) if capability_sets else []
        required = list(family["required_capabilities"])
        missing = sorted(set(required) - set(intersection))
        minimum = int(family["minimum_exact_observations"])
        status = "qualified" if len(accepted) >= minimum else "incomplete"
        if status != "qualified":
            limitations.append(
                f"{family_id} lacks {minimum} accepted exact-patch observation(s)"
            )
        family_results.append(
            {
                "id": family_id,
                "version_line": str(family["version_line"]),
                "status": status,
                "minimum_exact_observations": minimum,
                "eligible_observation_count": len(candidates),
                "accepted_observation_count": len(accepted),
                "observed_versions": sorted(
                    {str(item["normalized_version"]) for item in candidates}
                ),
                "required_capabilities": required,
                "capability_intersection": intersection,
                "missing_required_capabilities": missing,
            }
        )

    source_schema = corpus.get("schema")
    source_status = corpus.get("status")
    corpus_valid = source_schema == "factorio.version_capability_corpus.v1"
    normalized_source_status = (
        str(source_status) if corpus_valid and source_status in {"complete", "incomplete"} else "invalid"
    )
    if normalized_source_status != "complete":
        limitations.append("source capability corpus is not complete")
    required_family_ids = [str(item["id"]) for item in families if item.get("required") is True]
    all_families_qualified = all(item["status"] == "qualified" for item in family_results)
    overall_status = (
        "qualified"
        if normalized_source_status == "complete" and all_families_qualified
        else "incomplete"
    )
    unassigned = sum(1 for item in observations if item["family_id"] is None)
    return {
        "schema": "factorio.version_family_matrix.v1",
        "generated_utc": generated_utc
        or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "product_target": str(policy["product_target"]),
        "policy_sha256": policy_sha256 or canonical_json_sha256(policy),
        "source_corpus_schema": str(source_schema),
        "source_corpus_sha256": canonical_json_sha256(corpus),
        "source_corpus_status": normalized_source_status,
        "required_family_ids": required_family_ids,
        "family_count": len(family_results),
        "unassigned_observation_count": unassigned,
        "overall_status": overall_status,
        "support_claim": "unclaimed",
        "families": family_results,
        "observations": observations,
        "limitations": sorted(set(limitations)),
        "authority": {
            "support_promotion": False,
            "route_execution": False,
            "release_publication": False,
        },
    }


def validate_matrix_schema(matrix: dict[str, Any], schema_path: Path = SCHEMA_PATH) -> list[str]:
    try:
        import jsonschema
    except ModuleNotFoundError:
        return ["jsonschema dependency is unavailable"]
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
        return [
            f"{'.'.join(str(part) for part in error.absolute_path) or '$'}: {error.message}"
            for error in sorted(validator.iter_errors(matrix), key=lambda item: list(item.absolute_path))
        ]
    except (OSError, json.JSONDecodeError, jsonschema.exceptions.SchemaError) as exc:
        return [str(exc)]


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--policy", type=Path, default=POLICY_PATH)
    value.add_argument("--corpus", type=Path)
    value.add_argument("--output", type=Path)
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    problems: list[str] = []
    try:
        policy = load_policy(args.policy)
        problems.extend(validate_policy(policy))
        if args.policy.resolve() == POLICY_PATH.resolve() and args.corpus is None:
            problems.extend(validate_bound_evidence(policy))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        problems.append(str(exc))
        policy = {}
    if not SCHEMA_PATH.is_file():
        problems.append(f"missing matrix schema: {SCHEMA_PATH.relative_to(ROOT)}")
    try:
        with (ROOT / "release" / "index" / "release_index.v1.toml").open("rb") as handle:
            release_index = tomllib.load(handle)
        if release_index.get("factorio_version_families") != (
            "release/index/factorio_version_families.v1.toml"
        ):
            problems.append("release index does not bind the Factorio version-family contract")
    except (OSError, tomllib.TOMLDecodeError) as exc:
        problems.append(str(exc))
    if args.output is not None and args.corpus is None:
        problems.append("--output requires --corpus")
    if problems:
        for problem in problems:
            print(f"factorio-version-family-check: {problem}", file=sys.stderr)
        return 1
    if args.corpus is None:
        print("factorio-version-family-check: ok (F100, F110, F200, F210 target contract)")
        return 0
    try:
        corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
        if not isinstance(corpus, dict):
            raise ValueError("corpus root must be an object")
        matrix = build_matrix(
            corpus,
            policy,
            policy_sha256=hashlib.sha256(args.policy.read_bytes()).hexdigest(),
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"factorio-version-family-check: {exc}", file=sys.stderr)
        return 1
    schema_problems = validate_matrix_schema(matrix)
    if schema_problems:
        for problem in schema_problems:
            print(f"factorio-version-family-check: matrix: {problem}", file=sys.stderr)
        return 1
    rendered = json.dumps(matrix, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if matrix["overall_status"] == "qualified" else 2


if __name__ == "__main__":
    raise SystemExit(main())
