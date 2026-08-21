# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Validate the atomic, non-authorizing Universal provider reconciliation."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.release_compiler.canonical import (  # noqa: E402
    domain_digest_value,
    pretty_json,
)

SCHEMA = "facman.provider_pin_reconciliation.v1"
PACKAGE_SET_DOMAIN = "facman.provider_sdk_package_set.v1"
EVIDENCE_REVISION = "55d3ffb02ffc54d79fb6feb131f05976de421306"
ROUTE_V1_SHA256 = "98561d1c956435d0d57fd7f184545c0fdfa3bf2586ec944c59b9ee75bdde8632"
HEX_40 = re.compile(r"^[0-9a-f]{40}$")
HEX_64 = re.compile(r"^[0-9a-f]{64}$")
SYSTEMS = {"linux", "macos", "windows"}
LINKAGES = {"static", "shared"}
PROVIDERS = {
    "universal_launcher": {
        "source": "universal-launcher",
        "repository": "Julesc013/universal-launcher",
        "remote": "https://github.com/Julesc013/universal-launcher.git",
        "revision": "5479939ca5cbc9ee0f901608a92012778b4752ae",
        "tree": "7728e4d415539a0f24e6f17aa7d22be00cc99d80",
        "prior_revision": "09f0639ab6529fba2f2aa22e9bf68e5eebed0553",
        "package_version": "1.9.1",
        "cmake_package_version": "1.9.1",
        "abi_version": "1.9",
        "abi_manifest_digest": "ce17990b20ee3730cb73a709d8a649fdc5234df8b8e9735bf9a6ea0ea992210e",
        "contract_set_id": "ulk_contract_set_1_9",
        "contract_digest": "edb62fda28fac02bf7e07a6295c867b3813f4881886c6783f379b52b5c8761f9",
        "maturity": "canonical_main_experimental_session_subset_consumer_qualified",
        "sdk_adoption": "accepted_exact_main_session_provider",
    },
    "universal_setup": {
        "source": "universal-setup",
        "repository": "Julesc013/universal-setup",
        "remote": "https://github.com/Julesc013/universal-setup.git",
        "revision": "d2a2aae7e61c47035c92334b0522143b4fea3880",
        "tree": "291d63214cdd0cd3d15c809de5744ee3514fb2b2",
        "prior_revision": "32488fc13bd2439f9f6e52e83a97f6da345a7650",
        "package_version": "1.0.0",
        "cmake_package_version": "1.0.0",
        "abi_version": "1.0",
        "abi_manifest_digest": "07c2d023d4ecf6854301f10babb779a8ccd20eafb8f088a4cc29e361ca7beea0",
        "contract_set_id": "usk_product_package_contract_set_1",
        "contract_digest": "045a570f305a9e578dccbe22ec1d3c1945d6743a5e8d55d3c754dc3c2efd6f56",
        "maturity": "canonical_main_sdk_qualified",
        "sdk_adoption": "accepted_non_authorizing_input",
    },
}
AUTHORITY = {
    "factorio_execution": False,
    "observer_capture": False,
    "permit_issuance": False,
    "publication": False,
    "route_promotion": False,
    "setup_mutation": False,
    "signing": False,
}
SDK_DIGEST_FIELDS = (
    "identity_sha256",
    "metadata_sha256",
    "inventory_manifest_sha256",
    "inventory_sha256",
    "abi_manifest_sha256",
    "contract_digest",
)


def _toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        value = tomllib.load(handle)
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _index(rows: Any, key: str) -> tuple[dict[str, dict[str, Any]], list[str]]:
    result: dict[str, dict[str, Any]] = {}
    problems: list[str] = []
    if not isinstance(rows, list):
        return {}, [f"{key} records must be an array"]
    for row in rows:
        if not isinstance(row, dict):
            problems.append(f"{key} contains a non-object record")
            continue
        identity = str(row.get(key, ""))
        if not identity or identity in result:
            problems.append(f"{key} identity is missing or duplicated: {identity!r}")
            continue
        result[identity] = row
    return result, problems


def validate(root: Path = ROOT) -> list[str]:
    problems: list[str] = []
    index_root = root / "release" / "index"
    workspace = _toml(index_root / "workspace_lock.v1.toml")
    release = _toml(index_root / "providers.lock.v2.toml")
    dependency = _toml(index_root / "dependency_lock.v1.toml")
    sbom = json.loads((index_root / "sbom.components.v1.json").read_text(encoding="utf-8"))
    abi_compatibility = json.loads(
        (root / "contracts/abi/flb/compatibility.v1.json").read_text(
            encoding="utf-8"
        )
    )

    workspace_rows, workspace_problems = _index(workspace.get("component"), "id")
    provider_rows, provider_problems = _index(release.get("provider"), "id")
    dependency_rows, dependency_problems = _index(dependency.get("component"), "id")
    sbom_rows, sbom_problems = _index(sbom.get("components"), "id")
    problems.extend(workspace_problems + provider_problems + dependency_problems + sbom_problems)

    ulk_abi = PROVIDERS["universal_launcher"]["abi_version"].split(".")
    expected_required_ulk = {
        "major": int(ulk_abi[0]),
        "minor": int(ulk_abi[1]),
        "encoded": (int(ulk_abi[0]) << 16) | int(ulk_abi[1]),
    }
    if abi_compatibility.get("required_ulk_abi") != expected_required_ulk:
        problems.append("FacMan required ULK ABI differs from the reconciled provider ABI")

    if release.get("sdk_package_set_digest_domain") != PACKAGE_SET_DOMAIN:
        problems.append("release-provider lock has the wrong SDK package-set digest domain")
    if release.get("sdk_qualification_evidence_revision") != EVIDENCE_REVISION:
        problems.append("release-provider lock is not bound to the accepted SDK evidence head")

    sdk_rows = release.get("sdk_package")
    if not isinstance(sdk_rows, list):
        problems.append("release-provider lock omits the SDK package evidence matrix")
        sdk_rows = []
    seen_sdk: set[tuple[str, str, str, str]] = set()
    sdk_by_provider: dict[str, list[dict[str, Any]]] = {
        provider_id: [] for provider_id in PROVIDERS
    }
    for row in sdk_rows:
        if not isinstance(row, dict):
            problems.append("SDK package matrix contains a non-object record")
            continue
        provider_id = str(row.get("provider_id", ""))
        system = str(row.get("system", ""))
        architecture = str(row.get("architecture", ""))
        linkage = str(row.get("linkage", ""))
        key = (provider_id, system, architecture, linkage)
        if key in seen_sdk:
            problems.append(f"SDK package matrix repeats {key}")
            continue
        seen_sdk.add(key)
        if provider_id not in PROVIDERS:
            problems.append(f"SDK package matrix names unknown provider {provider_id!r}")
            continue
        sdk_by_provider[provider_id].append(row)
        expected = PROVIDERS[provider_id]
        expected_values = {
            "architecture": "x86_64",
            "consumption_mode": f"installed_{linkage}",
            "source_revision": expected["revision"],
            "source_tree": expected["tree"],
            "package_version": expected["package_version"],
            "abi_manifest_sha256": expected["abi_manifest_digest"],
            "contract_digest": expected["contract_digest"],
            "evidence_facman_revision": EVIDENCE_REVISION,
            "authorizing": False,
        }
        if system not in SYSTEMS or linkage not in LINKAGES:
            problems.append(f"SDK package matrix key is unsupported: {key}")
        for field, value in expected_values.items():
            if row.get(field) != value:
                problems.append(f"SDK package {key} {field} differs from accepted evidence")
        for field in SDK_DIGEST_FIELDS:
            if not HEX_64.fullmatch(str(row.get(field, ""))):
                problems.append(f"SDK package {key} {field} is not SHA-256")

    expected_matrix = {
        (provider_id, system, "x86_64", linkage)
        for provider_id in PROVIDERS
        for system in SYSTEMS
        for linkage in LINKAGES
    }
    if seen_sdk != expected_matrix:
        problems.append("SDK package evidence matrix is not exactly 2 providers x 3 systems x 2 linkages")

    for provider_id, expected in PROVIDERS.items():
        workspace_row = workspace_rows.get(provider_id, {})
        provider_row = provider_rows.get(provider_id, {})
        dependency_row = dependency_rows.get(provider_id, {})
        sbom_row = sbom_rows.get(provider_id, {})
        workspace_expected = {
            "source": expected["source"],
            "pin": expected["revision"],
            "tree": expected["tree"],
            "remote": expected["remote"],
            "required_ref": "refs/heads/main",
            "reachability": "required_for_source_closure",
        }
        provider_expected = {
            "repository": expected["repository"],
            "source_revision": expected["revision"],
            "source_tree": expected["tree"],
            "package_version": expected["package_version"],
            "cmake_package_version": expected["cmake_package_version"],
            "package_identity_kind": "canonical_sdk_package_set",
            "abi_version": expected["abi_version"],
            "abi_manifest_digest": expected["abi_manifest_digest"],
            "contract_set_id": expected["contract_set_id"],
            "contract_digest": expected["contract_digest"],
            "consumption_mode": "source",
            "supported_consumption_modes": ["source", "installed_static", "installed_shared"],
            "maturity": expected["maturity"],
            "sdk_adoption": expected["sdk_adoption"],
            "prior_source_revision": expected["prior_revision"],
        }
        for field, value in workspace_expected.items():
            if workspace_row.get(field) != value:
                problems.append(f"workspace {provider_id} {field} is not atomically reconciled")
        for field, value in provider_expected.items():
            if provider_row.get(field) != value:
                problems.append(f"release provider {provider_id} {field} is not atomically reconciled")
        package_rows = sdk_by_provider[provider_id]
        expected_package_digest = domain_digest_value(PACKAGE_SET_DOMAIN, package_rows)
        if provider_row.get("package_digest") != expected_package_digest:
            problems.append(f"release provider {provider_id} package-set digest is invalid")
        for projection_name, projection, version_key in (
            ("dependency lock", dependency_row, "pin"),
            ("SBOM", sbom_row, "commit"),
        ):
            if projection.get(version_key) != expected["revision"]:
                problems.append(f"{projection_name} {provider_id} revision differs")
            if projection.get("tree") != expected["tree"]:
                problems.append(f"{projection_name} {provider_id} tree differs")
            if projection.get("version") != expected["package_version"]:
                problems.append(f"{projection_name} {provider_id} version differs")

    route_path = index_root / "successor_play_route.v1.toml"
    if _sha256(route_path) != ROUTE_V1_SHA256:
        problems.append("successor route v1 changed during provider reconciliation")
    return problems


def report(root: Path = ROOT) -> dict[str, Any]:
    problems = validate(root)
    release_path = root / "release" / "index" / "providers.lock.v2.toml"
    workspace_path = root / "release" / "index" / "workspace_lock.v1.toml"
    core = {
        "schema": SCHEMA,
        "result": "pass" if not problems else "fail",
        "problems": problems,
        "provider_revisions": {
            provider_id: expected["revision"]
            for provider_id, expected in sorted(PROVIDERS.items())
        },
        "workspace_lock_sha256": _sha256(workspace_path),
        "release_provider_lock_sha256": _sha256(release_path),
        "successor_route_v1_sha256": _sha256(
            root / "release" / "index" / "successor_play_route.v1.toml"
        ),
        "provider_input_reconciled": not problems,
        "release_source_coherence_required": True,
        "factorio_executed": False,
        "setup_mutated": False,
        "signed": False,
        "published": False,
        "authority": dict(AUTHORITY),
    }
    return {**core, "evidence_digest": domain_digest_value(SCHEMA, core)}


def _write_external(path: Path, value: dict[str, Any]) -> None:
    destination = path.resolve()
    source = ROOT.resolve()
    if destination == source or source in destination.parents:
        raise ValueError("reconciliation evidence must be written outside the source repository")
    if destination.exists():
        raise ValueError(f"reconciliation evidence already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(pretty_json(value), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args(argv)
    try:
        value = report()
        if args.evidence:
            _write_external(args.evidence, value)
    except (OSError, ValueError, json.JSONDecodeError, tomllib.TOMLDecodeError) as error:
        print(f"provider-pin-reconciliation: {error}", file=sys.stderr)
        return 1
    if value["problems"]:
        for problem in value["problems"]:
            print(f"provider-pin-reconciliation: {problem}", file=sys.stderr)
        return 1
    print(f"provider-pin-reconciliation: pass {value['evidence_digest']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
