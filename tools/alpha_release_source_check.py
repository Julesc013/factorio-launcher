# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Validate the staged, non-authorizing FacMan alpha.1 release source."""

from __future__ import annotations

import json
import sys
import tomllib
from pathlib import Path
from typing import Any

from jsonschema import FormatChecker
from jsonschema.validators import validator_for

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import json_contract

INDEX = ROOT / "release/index"
SOURCE = INDEX / "alpha_release_source.v1.toml"
SOURCE_SCHEMA = ROOT / "contracts/schema/release/alpha_release_source.v1.schema.json"
PROSPECTIVE = ROOT / "release/ledger/0.1.0-alpha.1/prospective-entry.v1.json"
PROSPECTIVE_SCHEMA = (
    ROOT / "contracts/schema/release/prospective_release_ledger_entry.v1.schema.json"
)
WORK_UNIT = (
    ROOT
    / ".aide/queue/active/FACMAN-0.1.0-ALPHA.1-RELEASE-SOURCE-01/task.yaml"
)
PRECURSOR_STATUS = (
    ROOT
    / ".aide/queue/active/FACMAN-WINDOWS-TECHNICAL-PREVIEW-CANDIDATE-01/status.yaml"
)

EXPECTED_VERSION = "0.1.0-alpha.1"
EXPECTED_CANONICAL = "facman-0.1.0-alpha.1"
EXPECTED_PACKAGES = {
    "windows_cli_x64_portable": (
        "windows_portable_cli_x64",
        "facman-0.1.0-alpha.1-windows-cli-x64-portable.zip",
    ),
    "windows_tui_x64_portable": (
        "windows_portable_tui_x64",
        "facman-0.1.0-alpha.1-windows-tui-x64-portable.zip",
    ),
    "windows_winforms_x64_portable": (
        "windows_legacy_winforms_x64",
        "FacMan-0.1.0-alpha.1-windows-x64-portable.zip",
    ),
}
EXPECTED_TAG_ROLES = {
    "package_set",
    "checksums",
    "sbom_set",
    "provenance_set",
    "known_limitations",
    "licence_inventory_set",
    "candidate_record",
    "tag_receipt",
}
EXPECTED_PUBLIC_ROLES = {
    "route_receipt",
    "human_test_receipt",
    "public_release_ledger_entry",
    "publication_authority_receipt",
}
EXPECTED_BETA_ROLES: set[str] = set()
EXPECTED_ASSET_COUNTS = {
    "tag_only": 16,
    "public_alpha_additional": 4,
    "beta_only": 0,
}
EXPECTED_PENDING_GATES = {
    "human_alpha_acceptance",
    "accepted_real_play_route",
    "route_capability_promotion",
    "public_asset_verification",
    "publication_delegation",
}
EXPECTED_PRODUCT_REVISION = "fa60aaa17e9044bef7bb7347261056959690f1cd"
EXPECTED_PRODUCT_TREE = "5536891662461d3617ee40e93654cb2f0659905c"
EXPECTED_TAG_OBJECT = "52a7a66092ff2b3b3c1059e9c29260f95b1cb287"


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


def load() -> tuple[dict[str, Any], dict[str, Any]]:
    return _toml(SOURCE), _json(PROSPECTIVE)


def validate(
    source: dict[str, Any] | None = None,
    prospective: dict[str, Any] | None = None,
) -> list[str]:
    problems: list[str] = []
    try:
        source = source if source is not None else _toml(SOURCE)
        prospective = prospective if prospective is not None else _json(PROSPECTIVE)
        channels = _toml(INDEX / "channels.v1.toml")
        train = _toml(INDEX / "version_train.v1.toml")
        scope = _toml(INDEX / "technical_preview_scope.v1.toml")
    except (OSError, ValueError, json.JSONDecodeError, tomllib.TOMLDecodeError) as exc:
        return [f"alpha release-source input cannot be read: {exc}"]

    for label, value, schema_path in (
        ("alpha release source", source, SOURCE_SCHEMA),
        ("prospective ledger entry", prospective, PROSPECTIVE_SCHEMA),
    ):
        contract = json_contract.load_schema(schema_path)
        validator_class = validator_for(contract)
        validator_class.check_schema(contract)
        for issue in sorted(
            validator_class(contract, format_checker=FormatChecker()).iter_errors(value),
            key=lambda error: tuple(str(part) for part in error.absolute_path),
        ):
            problems.append(f"{label} schema rejection: {issue.message}")

    alpha_channels = [
        item
        for item in channels.get("channel", [])
        if isinstance(item, dict) and item.get("id") == "alpha"
    ]
    if len(alpha_channels) != 1 or EXPECTED_CANONICAL not in alpha_channels[0].get("versions", []):
        problems.append("alpha channel must retain the allocated alpha.1 identity")
    if not alpha_channels or alpha_channels[0].get("publication_authorized") is not False:
        problems.append("alpha channel publication authority must remain false")

    packages = {
        str(item.get("id", "")): (
            str(item.get("profile", "")),
            str(item.get("filename", "")),
        )
        for item in source.get("package", [])
        if isinstance(item, dict)
    }
    if packages != EXPECTED_PACKAGES:
        problems.append("alpha release source does not bind the exact three-package set")
    assets = [item for item in source.get("assets", []) if isinstance(item, dict)]
    asset_ids = [str(item.get("id", "")) for item in assets]
    filenames = [str(item.get("filename", "")) for item in assets]
    if len(asset_ids) != 20 or len(asset_ids) != len(set(asset_ids)):
        problems.append("alpha asset manifest must carry twenty unique asset identities")
    if len(filenames) != len(set(filenames)):
        problems.append("alpha asset manifest repeats a filename")
    counts = {
        milestone: sum(1 for item in assets if item.get("milestone") == milestone)
        for milestone in EXPECTED_ASSET_COUNTS
    }
    if counts != EXPECTED_ASSET_COUNTS:
        problems.append("alpha assets are not split exactly across tag, public-alpha, and beta gates")
    package_assets = {
        str(item.get("package_id", "")): str(item.get("filename", ""))
        for item in assets
        if item.get("role") == "package"
    }
    if package_assets != {
        package_id: identity[1] for package_id, identity in EXPECTED_PACKAGES.items()
    }:
        problems.append("tag-only package assets differ from the canonical package set")
    for role in ("sbom", "provenance", "licence_inventory"):
        associated = {
            str(item.get("package_id", ""))
            for item in assets
            if item.get("role") == role and item.get("milestone") == "tag_only"
        }
        if associated != set(EXPECTED_PACKAGES):
            problems.append(f"tag-only {role} assets do not cover every package")
    if set(prospective.get("tag_only_artifact_roles", [])) != EXPECTED_TAG_ROLES:
        problems.append("prospective ledger tag-only roles differ from the release source")
    if set(prospective.get("public_alpha_additional_roles", [])) != EXPECTED_PUBLIC_ROLES:
        problems.append("prospective ledger public-alpha roles differ from the release source")
    if set(prospective.get("beta_only_evidence_roles", [])) != EXPECTED_BETA_ROLES:
        problems.append("prospective ledger beta-only roles differ from the release source")
    if prospective.get("human_receipt_required") is not True:
        problems.append("prospective public alpha must require the exact alpha human receipt")
    if prospective.get("known_limitations") != source.get("known_limitations"):
        problems.append("prospective ledger limitations differ from the release source")
    if set(prospective.get("pending_gates", [])) != EXPECTED_PENDING_GATES:
        problems.append("prospective ledger must retain every uncompleted alpha gate")

    expected_train = {"allocated_release_class": "alpha"}
    for field, expected in expected_train.items():
        if train.get(field) != expected:
            problems.append(f"version train {field} must be {expected!r}")
    for field in ("version_allocation_authorized", "tag_creation_authorized"):
        if train.get(field) is not True:
            problems.append(f"version train {field} must be active for bounded alpha tags")
    for field in ("signing_authorized", "publication_authorized"):
        if train.get(field) is not False:
            problems.append(f"version train {field} must remain closed")
    if train.get("authority", {}) != {
        "version_allocation": True,
        "tag_creation": True,
        "signing": False,
        "publication": False,
        "withdrawal": False,
        "stable_promotion": False,
    }:
        problems.append("version train authority must remain bounded to alpha allocation and tags")
    if train.get("public_alpha_human_receipt_required") is not True:
        problems.append("version train must require G2 human acceptance before public alpha")
    if train.get("beta_requires_distinct_exact_byte_human_receipt") is not True:
        problems.append("version train must require a distinct exact-byte beta receipt")

    alpha_class = next(
        (
            item
            for item in train.get("release_class", [])
            if isinstance(item, dict) and item.get("id") == "alpha"
        ),
        {},
    )
    if alpha_class.get("human_receipt_required") is not False:
        problems.append("tag-only alpha allocation must not require the later public receipt")
    if alpha_class.get("support_class") != "unsupported_public_alpha":
        problems.append("alpha support class must remain unsupported_public_alpha")
    if alpha_class.get("currently_authorized") is not True:
        problems.append("bounded alpha tag class must be active")
    if alpha_class.get("publication_kind") not in {
        "unpublished_annotated_tag",
        "private_draft_github_prerelease",
    }:
        problems.append("alpha class must remain unpublished or private-draft only")

    gate_ids = {
        item.get("id")
        for item in scope.get("publication_gate", [])
        if isinstance(item, dict)
    }
    if gate_ids != {
        "immutable_alpha1_tag_and_tag_only_assets",
        "exact_alpha1_human_acceptance",
        "accepted_factorio_2_1_14_route_and_promotion",
        "complete_unsupported_unsigned_alpha_assets_and_disclosures",
        "explicit_invocation_scoped_publication_authority",
    }:
        problems.append("Technical Preview alpha publication gates have drifted")

    source_binding = source.get("source", {})
    if source_binding != {
        "product_revision": EXPECTED_PRODUCT_REVISION,
        "product_tree": EXPECTED_PRODUCT_TREE,
        "product_ref": "refs/tags/v0.1.0-alpha.1",
        "control_source_ref": "dev",
        "control_source_requirement": "exact_current_protected_dev_release_control_commit",
    }:
        problems.append("alpha release source does not separate frozen product and release-control identity")
    tag_binding = source.get("tag", {})
    if tag_binding != {
        "name": "v0.1.0-alpha.1",
        "annotated": True,
        "status": "sealed_immutable_tag_only_assets_verified",
        "target_revision": EXPECTED_PRODUCT_REVISION,
        "object_sha": EXPECTED_TAG_OBJECT,
        "ruleset_id": 21787868,
    }:
        problems.append("alpha release source does not record the sealed immutable tag")
    qualification = source.get("qualification", {})
    if qualification.get("human_receipt") != "required_before_public_alpha":
        problems.append("alpha release source must require the G2 receipt before public alpha")
    if qualification.get("beta_human_receipt") != "distinct_exact_beta_bytes_required_after_beta_freeze":
        problems.append("alpha release source must preserve distinct exact-byte beta acceptance")

    if not WORK_UNIT.is_file():
        problems.append("alpha.1 release-source WorkUnit is missing")
    else:
        work_unit_status = next(
            (
                line.split(":", 1)[1].strip()
                for line in WORK_UNIT.read_text(encoding="utf-8").splitlines()
                if line.startswith("status:")
            ),
            "",
        )
        if work_unit_status not in {"active", "verified_pending_closeout", "passed"}:
            problems.append(
                "alpha.1 release-source WorkUnit is neither active, verified pending closeout, nor closed"
            )
    if not PRECURSOR_STATUS.is_file():
        problems.append("precursor candidate closeout status is missing")
    else:
        precursor = PRECURSOR_STATUS.read_text(encoding="utf-8")
        if "status: passed" not in precursor or "lifecycle_state: closed" not in precursor:
            problems.append("machine-qualified precursor WorkUnit is not closed")

    for authority in (source.get("authority", {}), prospective.get("authority", {})):
        if any(value is not False for value in authority.values()):
            problems.append("alpha source or prospective ledger grants authority")
    return problems


def main() -> int:
    problems = validate()
    if problems:
        for problem in problems:
            print(f"alpha-release-source-check: {problem}", file=sys.stderr)
        return 1
    print(
        "alpha-release-source-check: ok "
        "(three-package alpha.1 source and immutable tag are sealed; later effects remain closed)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
