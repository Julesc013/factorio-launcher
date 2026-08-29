# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Validate the exact non-authorizing FacMan alpha.1 publication preparation."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
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

PREPARATION = ROOT / "release/index/alpha1_publication_preparation.v1.toml"
SCHEMA = ROOT / "contracts/schema/release/alpha1_publication_preparation.v1.schema.json"
TAG_CLOSEOUT = ROOT / "release/index/alpha1_tag_truth_closeout.v1.toml"
ROUTE = ROOT / "release/index/successor_play_route.v5.toml"
ROUTE_REQUEST = ROOT / "release/index/factorio_2_1_14_route_d3_d4_request.v1.toml"
ALPHA_SOURCE = ROOT / "release/index/alpha_release_source.v1.toml"
PROSPECTIVE = ROOT / "release/ledger/0.1.0-alpha.1/prospective-entry.v1.json"
SCOPE = ROOT / "release/index/technical_preview_scope.v1.toml"
TRAIN = ROOT / "release/index/version_train.v1.toml"
WORKFLOW = ROOT / ".github/workflows/release.yml"
ASSET_SET = ROOT / "tools/alpha_asset_set.py"
HUMAN_TEST_PACKET = ROOT / "tools/alpha_portable_test_packet.py"
PUBLICATION_GATE = ROOT / "tools/alpha_publication_gate.py"
PUBLICATION_AUTHORITY_SCHEMA = (
    ROOT / "contracts/schema/release/alpha_publication_authority.v1.schema.json"
)

PRODUCT_REVISION = "fa60aaa17e9044bef7bb7347261056959690f1cd"
PRODUCT_TREE = "5536891662461d3617ee40e93654cb2f0659905c"
TAG_OBJECT = "52a7a66092ff2b3b3c1059e9c29260f95b1cb287"
QUALIFICATION_SHA256 = "83b439c4d6fff3dfabfd3f93d0d61f125ccb1113f5745c435e802631156e4c44"
ROUTE_ID = "facman.play.windows-x64.factorio-2.1.14.base.menu.sandbox-task-owned.successor.v5"
ROUTE_DIGEST = "d4627348d997ab20d8f5a540b8571bca145048ff6da365d0b42fdc18714c689e"
REQUEST_ID = "facman.factorio-2-1-14.route-d3-d4-request.01"
REQUEST_DIGEST = "eaf8fb1a1b92638ff1d0cd71a6403263beae87e41dddd9e3109af81e2e0ee630"
PACKAGES = {
    "windows_cli_x64_portable": (
        "facman-0.1.0-alpha.1-windows-cli-x64-portable.zip",
        "62e45380674728cf7712238d96fd241bc1954780f24c5fe1dfea7e9bdde20fc5",
    ),
    "windows_tui_x64_portable": (
        "facman-0.1.0-alpha.1-windows-tui-x64-portable.zip",
        "cadd6277438ec188946fd0ea6b6b77a52f430e784583af39fc2a3ca78de39b48",
    ),
    "windows_winforms_x64_portable": (
        "FacMan-0.1.0-alpha.1-windows-x64-portable.zip",
        "00fcf5dfc9597a7118ad8d81ff4489d5ace6019c272e79bcc12e966547149c86",
    ),
}
PUBLIC_GATE_IDS = {
    "immutable_alpha1_tag_and_tag_only_assets",
    "exact_alpha1_human_acceptance",
    "accepted_factorio_2_1_14_route_and_promotion",
    "complete_unsupported_unsigned_alpha_assets_and_disclosures",
    "explicit_invocation_scoped_publication_authority",
}


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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def preparation_digest(value: dict[str, Any]) -> str:
    payload = deepcopy(value)
    payload.pop("preparation_digest", None)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def load() -> dict[str, Any]:
    return _toml(PREPARATION)


def validate(preparation: dict[str, Any] | None = None) -> list[str]:
    problems: list[str] = []
    try:
        preparation = preparation if preparation is not None else _toml(PREPARATION)
        closeout = _toml(TAG_CLOSEOUT)
        route = _toml(ROUTE)
        request = _toml(ROUTE_REQUEST)
        alpha_source = _toml(ALPHA_SOURCE)
        prospective = _json(PROSPECTIVE)
        scope = _toml(SCOPE)
        train = _toml(TRAIN)
        workflow = WORKFLOW.read_text(encoding="utf-8")
        asset_set = ASSET_SET.read_text(encoding="utf-8")
        human_test_packet = HUMAN_TEST_PACKET.read_text(encoding="utf-8")
        publication_gate = PUBLICATION_GATE.read_text(encoding="utf-8")
        publication_authority_schema = _json(PUBLICATION_AUTHORITY_SCHEMA)
    except (OSError, ValueError, json.JSONDecodeError, tomllib.TOMLDecodeError) as exc:
        return [f"publication preparation input cannot be read: {exc}"]

    contract = json_contract.load_schema(SCHEMA)
    validator_class = validator_for(contract)
    validator_class.check_schema(contract)
    for issue in sorted(
        validator_class(contract, format_checker=FormatChecker()).iter_errors(preparation),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    ):
        problems.append(f"publication preparation schema rejection: {issue.message}")
    observed_digest = str(preparation.get("preparation_digest", ""))
    expected_digest = preparation_digest(preparation)
    if observed_digest != expected_digest:
        problems.append(
            f"publication preparation digest mismatch: expected {expected_digest}, observed {observed_digest}"
        )

    product = preparation.get("frozen_product", {})
    expected_product = {
        "version": "0.1.0-alpha.1",
        "source_revision": PRODUCT_REVISION,
        "source_tree": PRODUCT_TREE,
        "tag": "v0.1.0-alpha.1",
        "tag_object": TAG_OBJECT,
        "candidate_record_sha256": closeout.get("qualification", {}).get("candidate_sha256"),
        "qualification_sha256": QUALIFICATION_SHA256,
        "provider_lock_sha256": closeout.get("qualification", {}).get("provider_lock_sha256"),
        "contract_set_sha256": closeout.get("qualification", {}).get("contract_set_sha256"),
    }
    if product != expected_product:
        problems.append("publication preparation frozen product differs from sealed tag truth")
    package_map = {
        str(item.get("id", "")): (str(item.get("filename", "")), str(item.get("sha256", "")))
        for item in preparation.get("package", [])
        if isinstance(item, dict)
    }
    if package_map != PACKAGES:
        problems.append("publication preparation package set differs from frozen alpha.1 bytes")

    g1 = preparation.get("g1_tag", {})
    if g1.get("truth_closeout_sha256") != _sha256(TAG_CLOSEOUT):
        problems.append("G1 preparation does not bind the exact tag-truth closeout")
    if closeout.get("tag", {}).get("object_sha") != TAG_OBJECT:
        problems.append("tag-truth closeout no longer identifies the immutable alpha.1 tag object")
    if closeout.get("tag_asset_set", {}).get("file_count") != 16:
        problems.append("tag-truth closeout no longer proves the sixteen tag-only assets")

    g2 = preparation.get("g2_human_alpha", {})
    if g2.get("status") != "pending" or g2.get("current_result") != "Inconclusive":
        problems.append("G2 preparation must truthfully retain the pending Inconclusive receipt")
    if g2.get("required_result") != "Pass" or g2.get("every_lane_must_pass") is not True:
        problems.append("G2 preparation must require a human Pass in every exact-package lane")
    if g2.get("receipt_grants_publication") is not False:
        problems.append("G2 receipt must not grant publication authority")

    g3 = preparation.get("g3_route", {})
    if g3.get("route_record_sha256") != _sha256(ROUTE):
        problems.append("G3 preparation does not bind the exact route-v5 record")
    if route.get("route_id") != ROUTE_ID or route.get("definition_digest") != ROUTE_DIGEST:
        problems.append("G3 route-v5 identity has drifted")
    if g3.get("request_record_sha256") != _sha256(ROUTE_REQUEST):
        problems.append("G3 preparation does not bind the exact D3/D4 request record")
    if request.get("request_id") != REQUEST_ID or request.get("request_digest") != REQUEST_DIGEST:
        problems.append("G3 D3/D4 request identity has drifted")
    for field in (
        "d3_authorized",
        "d4_authorized",
        "route_capability_integrated",
        "route_promotion_integrated",
        "route_receipt_grants_publication",
    ):
        if g3.get(field) is not False:
            problems.append(f"G3 preparation must keep {field} false")

    source_section = alpha_source.get("source", {})
    if source_section.get("product_revision") != PRODUCT_REVISION:
        problems.append("alpha release source does not separate and bind the frozen product revision")
    if source_section.get("product_tree") != PRODUCT_TREE:
        problems.append("alpha release source does not separate and bind the frozen product tree")
    if source_section.get("control_source_requirement") != "exact_current_protected_dev_release_control_commit":
        problems.append("alpha release source does not require an exact current control-plane commit")
    if alpha_source.get("tag", {}).get("status") != "sealed_immutable_tag_only_assets_verified":
        problems.append("alpha release source still describes the immutable tag as uncreated")
    if alpha_source.get("qualification", {}).get("human_receipt") != "required_before_public_alpha":
        problems.append("alpha release source does not require G2 before public alpha")

    public_roles = set(prospective.get("public_alpha_additional_roles", []))
    if "human_test_receipt" not in public_roles or prospective.get("human_receipt_required") is not True:
        problems.append("prospective public alpha does not require the exact alpha human receipt")
    if prospective.get("beta_only_evidence_roles") != []:
        problems.append("alpha receipt is still incorrectly classified as beta-only evidence")

    gate_ids = {
        str(item.get("id", ""))
        for item in scope.get("publication_gate", [])
        if isinstance(item, dict)
    }
    if gate_ids != PUBLIC_GATE_IDS:
        problems.append("Technical Preview public-alpha gates do not match G1 through G3 plus authority")
    if train.get("public_alpha_human_receipt_required") is not True:
        problems.append("version train does not require human acceptance for public alpha")
    if train.get("beta_requires_distinct_exact_byte_human_receipt") is not True:
        problems.append("version train does not preserve distinct exact-byte beta acceptance")

    workflow_anchors = (
        "control_source_revision:",
        "human_alpha_receipt_sha256:",
        "FACMAN_ALPHA_1_HUMAN_RECEIPT_JSON",
        "--control-source-revision",
        "--product-source-revision",
        "--human-alpha-receipt-sha256",
    )
    for anchor in workflow_anchors:
        if anchor not in workflow:
            problems.append(f"alpha release workflow is missing publication-control anchor: {anchor}")
    if "ref: ${{ inputs.control_source_revision }}" not in workflow:
        problems.append("public-alpha jobs do not checkout the separate control-source revision")
    for anchor in (
        "alpha1_portable_human_test_receipt.v1.schema.json",
        "completed_human_problems",
        "human_receipt_sha256",
        "facman.successor-play.human-verdict.05",
    ):
        if anchor not in asset_set:
            problems.append(f"public asset assembly is missing G2/G3 anchor: {anchor}")
    for anchor in (
        "human_execution_complete",
        "exact nine ordered test lanes",
        "must record direct observations",
        "must record assigned test environments",
    ):
        if anchor not in human_test_packet:
            problems.append(f"completed human-packet validation is missing anchor: {anchor}")
    for anchor in (
        "route_capability_authorized",
        "route_promotion_authorized",
        "human_alpha_receipt_sha256",
        "control_source_revision",
        "product_source_revision",
        "facman.successor-play.human-verdict.05",
    ):
        if anchor not in publication_gate:
            problems.append(f"publication gate is missing exact prerequisite anchor: {anchor}")
    authority_required = set(publication_authority_schema.get("required", []))
    if not {
        "product_source_revision",
        "product_source_tree",
        "control_source_revision",
        "control_source_tree",
        "human_alpha_receipt_sha256",
        "route_receipt_sha256",
        "route_index_digest",
        "release_policy",
        "authority",
    }.issubset(authority_required):
        problems.append("publication authority schema omits an exact G2/G3/source/policy binding")
    authority_rules = (
        publication_authority_schema.get("properties", {})
        .get("authority", {})
        .get("properties", {})
    )
    if authority_rules != {
        "tag_creation": {"const": False},
        "publication": {"const": True},
        "signing": {"const": False},
        "support_promotion": {"const": False},
        "route_promotion": {"const": False},
    }:
        problems.append("publication authority schema exceeds one unsigned publication effect")

    signing = preparation.get("signing_policy", {})
    if signing.get("mode") != "explicit_unsigned_unsupported_prerelease":
        problems.append("public-alpha signing policy is not the explicit unsigned mode")
    if signing.get("production_signing_authorized") is not False:
        problems.append("publication preparation unexpectedly authorizes production signing")
    signing_preparation = preparation.get("signing_preparation", {})
    closed_signing_fields = (
        "release_package_signing_permitted",
        "frozen_alpha1_signing_permitted",
        "production_certificate_access",
        "production_private_key_access",
        "signing_environment_activated",
    )
    for field in closed_signing_fields:
        if signing_preparation.get(field) is not False:
            problems.append(f"signing preparation must keep {field} false")
    for field in (
        "signing_identity",
        "certificate_thumbprint",
        "timestamp_authority",
        "rehearsal_receipt",
        "production_authority_receipt",
    ):
        if signing_preparation.get(field) != "UNASSIGNED":
            problems.append(f"signing preparation must keep {field} unassigned")
    if signing_preparation.get("rehearsal_scope") != "disposable_non_release_fixture_only":
        problems.append("signing rehearsal preparation must exclude release package bytes")
    required_signing_controls = (
        "exact_candidate_binding_required",
        "sha256_authenticode_required",
        "rfc3161_timestamp_required",
        "pre_and_post_signing_digests_required",
        "all_shipped_windows_executables_must_verify",
        "secret_material_in_repository_or_logs_forbidden",
        "separate_owner_approval_required",
        "future_invocation_scoped_authority_required",
        "activation_requires_reviewed_future_work_unit",
    )
    for field in required_signing_controls:
        if signing_preparation.get(field) is not True:
            problems.append(f"signing preparation must require {field}")
    if any(value is not False for value in preparation.get("authority", {}).values()):
        problems.append("publication preparation grants authority")
    if preparation.get("request_itself_grants_no_authority") is not True:
        problems.append("publication preparation must explicitly grant no authority")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--print-digest", action="store_true")
    args = parser.parse_args(argv)
    try:
        preparation = load()
    except (OSError, ValueError, tomllib.TOMLDecodeError) as exc:
        print(f"alpha1-publication-preparation-check: {exc}", file=sys.stderr)
        return 1
    if args.print_digest:
        print(preparation_digest(preparation))
        return 0
    problems = validate(preparation)
    if problems:
        for problem in problems:
            print(f"alpha1-publication-preparation-check: {problem}", file=sys.stderr)
        return 1
    print(
        "alpha1-publication-preparation-check: ok "
        "(G1 sealed; G2, G3, publication and signing authority remain closed)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
