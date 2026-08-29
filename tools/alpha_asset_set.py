# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Assemble non-authorizing FacMan alpha machine, tag, and public asset sets."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tomllib
from pathlib import Path
from typing import Any

from jsonschema import FormatChecker
from jsonschema.validators import validator_for

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import alpha_portable_test_packet, json_contract

SOURCE_PATH = ROOT / "release/index/alpha_release_source.v1.toml"
CANDIDATE_SCHEMA = ROOT / "contracts/schema/release/release_candidate.v1.schema.json"
QUALIFICATION_SCHEMA = (
    ROOT
    / "contracts/schema/release/alpha1_final_dev_three_root_qualification.v1.schema.json"
)
LEDGER_SCHEMA = ROOT / "contracts/schema/release/release_ledger_entry.v1.schema.json"
ROUTE_SCHEMA = ROOT / "contracts/schema/release/human_test_receipt.v1.schema.json"
HUMAN_ALPHA_SCHEMA = (
    ROOT
    / "contracts/schema/release/alpha1_portable_human_test_receipt.v1.schema.json"
)
TAG_RECEIPT_SCHEMA = ROOT / "contracts/schema/release/alpha_tag_receipt.v1.schema.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def digest_mapping(value: dict[str, str]) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as stream:
        value = tomllib.load(stream)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a TOML table")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def require_new_output(path: Path) -> Path:
    resolved = path.resolve()
    if resolved.exists():
        raise ValueError(f"output directory must be new: {resolved}")
    resolved.mkdir(parents=True)
    return resolved


def write_receipt(path: Path, value: dict[str, Any]) -> None:
    resolved = path.resolve()
    if resolved.exists():
        raise ValueError(f"receipt path must be new: {resolved}")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    write_json(resolved, value)


def package_records(source: dict[str, Any]) -> dict[str, dict[str, Any]]:
    records = {
        str(item["id"]): item
        for item in source.get("package", [])
        if isinstance(item, dict)
    }
    if set(records) != {
        "windows_cli_x64_portable",
        "windows_tui_x64_portable",
        "windows_winforms_x64_portable",
    }:
        raise ValueError("alpha release source must contain the exact three-package set")
    return records


def asset_records(source: dict[str, Any]) -> dict[str, dict[str, Any]]:
    records = {
        str(item["id"]): item
        for item in source.get("assets", [])
        if isinstance(item, dict)
    }
    if len(records) != 20:
        raise ValueError("alpha release source must contain exactly twenty asset identities")
    return records


def asset_for(
    assets: dict[str, dict[str, Any]], role: str, package_id: str | None = None
) -> dict[str, Any]:
    matches = [
        item
        for item in assets.values()
        if item.get("role") == role
        and (package_id is None or item.get("package_id") == package_id)
    ]
    if len(matches) != 1:
        suffix = f"/{package_id}" if package_id else ""
        raise ValueError(f"alpha release source must contain one {role}{suffix} asset")
    return matches[0]


def milestone_names(source: dict[str, Any], milestone: str) -> set[str]:
    return {
        str(item["filename"])
        for item in source.get("assets", [])
        if isinstance(item, dict) and item.get("milestone") == milestone
    }


def _validate_schema(value: dict[str, Any], schema: Path, label: str) -> None:
    contract = json_contract.load_schema(schema)
    validator_class = validator_for(contract)
    validator_class.check_schema(contract)
    problems = [
        error.message
        for error in sorted(
            validator_class(contract, format_checker=FormatChecker()).iter_errors(value),
            key=lambda error: tuple(str(part) for part in error.absolute_path),
        )
    ]
    if problems:
        raise ValueError(f"{label} schema rejection: {'; '.join(problems)}")


def _closed_authority(authority: object, label: str) -> None:
    if not isinstance(authority, dict) or any(value is not False for value in authority.values()):
        raise ValueError(f"{label} authority must be present and entirely false")


def _artifact(path: Path) -> dict[str, Any]:
    return {
        "name": path.name,
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
        "media_type": "application/zip",
        "signed": False,
        "published": False,
    }


def _provider_identities(record: dict[str, Any]) -> list[dict[str, str]]:
    identities = [
        {
            "id": str(item["id"]),
            "revision": str(item["source_revision"]),
            "tree": str(item["source_tree"]),
            "package_identity": str(item["package_identity"]),
            "abi": str(item["abi_version"]),
            "contract_digest": str(item["contract_digest"]),
        }
        for item in record.get("providers", [])
        if isinstance(item, dict)
    ]
    identities.sort(key=lambda item: item["id"])
    if [item["id"] for item in identities] != ["universal_launcher", "universal_setup"]:
        raise ValueError("qualification does not contain exact ULK and USK identities")
    return identities


def validate_qualification(
    comparison: dict[str, Any], source_revision: str
) -> dict[str, dict[str, Any]]:
    if comparison.get("schema") != "facman.alpha1_final_dev_three_root_qualification.v1":
        raise ValueError("qualification comparison has the wrong schema")
    if comparison.get("status") != "pass" or comparison.get("source_revision") != source_revision:
        raise ValueError("qualification comparison is not passing for the requested source")
    if comparison.get("root_count") != 3 or comparison.get("roots") != [
        "root1",
        "root2",
        "root3",
    ]:
        raise ValueError("qualification comparison must contain three fresh roots")
    if comparison.get("mismatch_count") != 0 or comparison.get("mismatches") != []:
        raise ValueError("qualification comparison is not byte-identical across three roots")
    required = {
        "fresh_roots": "pass_in_every_root",
        "native_static_debug_release": "pass_in_every_root",
        "native_shared_debug_release": "pass_in_every_root",
        "package_runtime": "pass_in_every_root",
        "hash_manifest": "pass_in_every_root",
        "drift_refusal": "pass_in_every_root",
        "byte_identical_archives": "pass_in_every_root",
    }
    if comparison.get("qualification") != required:
        raise ValueError("qualification comparison does not carry every passing decision")
    _closed_authority(comparison.get("authority"), "qualification comparison")
    packages = {
        str(item["id"]): item
        for item in comparison.get("packages", [])
        if isinstance(item, dict)
    }
    if set(packages) != {
        "windows_cli_x64_portable",
        "windows_tui_x64_portable",
        "windows_winforms_x64_portable",
    }:
        raise ValueError("qualification comparison omits an alpha package")
    for package in packages.values():
        if package.get("source_revision") != source_revision:
            raise ValueError("qualified package has the wrong source revision")
        _provider_identities(package)
    return packages


def _copy_exact(source: Path, destination: Path, expected_sha256: str) -> None:
    if not source.is_file() or sha256(source) != expected_sha256:
        raise ValueError(f"qualified asset is absent or substituted: {source}")
    shutil.copy2(source, destination)


def _core_names(source: dict[str, Any]) -> set[str]:
    excluded = {"checksums", "tag_receipt"}
    return {
        str(item["filename"])
        for item in source.get("assets", [])
        if isinstance(item, dict)
        and item.get("milestone") == "tag_only"
        and item.get("role") not in excluded
    }


def _require_inventory(root: Path, expected: set[str], label: str) -> None:
    observed = {path.name for path in root.iterdir() if path.is_file()}
    if observed != expected:
        raise ValueError(
            f"{label} inventory differs: missing={sorted(expected - observed)}, "
            f"unexpected={sorted(observed - expected)}"
        )


def build_machine_assets(
    *,
    qualification_root: Path,
    output_root: Path,
    source_revision: str,
    release_source_root: Path | None = None,
) -> dict[str, Any]:
    qualification_root = qualification_root.resolve()
    exact_source_root = release_source_root.resolve() if release_source_root else ROOT
    source = load_toml(exact_source_root / "release/index/alpha_release_source.v1.toml")
    assets = asset_records(source)
    expected_packages = package_records(source)
    comparison_path = qualification_root / "three-root-qualification.v1.json"
    comparison = load_json(comparison_path)
    _validate_schema(comparison, QUALIFICATION_SCHEMA, "three-root qualification")
    qualified = validate_qualification(comparison, source_revision)
    output = require_new_output(output_root)

    package_artifacts: list[dict[str, Any]] = []
    sbom_digests: dict[str, str] = {}
    provenance_digests: dict[str, str] = {}
    for package_id, expected in expected_packages.items():
        record = qualified[package_id]
        if record.get("profile") != expected.get("profile") or record.get("filename") != expected.get(
            "filename"
        ):
            raise ValueError(f"{package_id}: qualification identity differs from release source")
        root1 = qualification_root / "root1"
        package_root = root1 / "packages" / str(record["profile"])
        archive = root1 / "dist" / str(record["filename"])
        sources = {
            "package": archive,
            "sbom": package_root / "manifest/sbom.spdx.v2.3.json",
            "provenance": root1 / "dist" / f"{record['filename']}.provenance.v1.json",
            "licence_inventory": root1 / "dist" / f"{record['filename']}.licence-inventory.v1.json",
        }
        digests = {
            "package": str(record["archive_sha256"]),
            "sbom": str(record["sbom_sha256"]),
            "provenance": str(record["provenance_sha256"]),
            "licence_inventory": str(record["licence_inventory_sha256"]),
        }
        for role, source_path in sources.items():
            destination_name = str(asset_for(assets, role, package_id)["filename"])
            _copy_exact(source_path, output / destination_name, digests[role])
        package_path = output / str(asset_for(assets, "package", package_id)["filename"])
        package_artifacts.append(_artifact(package_path))
        sbom_digests[package_id] = digests["sbom"]
        provenance_digests[package_id] = digests["provenance"]

    limitations = [str(item) for item in source.get("known_limitations", [])]
    limitations_name = str(asset_for(assets, "known_limitations")["filename"])
    (output / limitations_name).write_text(
        "# FacMan 0.1.0-alpha.1 known limitations\n\n"
        + "".join(f"- {item}\n" for item in limitations),
        encoding="utf-8",
        newline="\n",
    )
    provider_lock = exact_source_root / "release/index/providers.lock.v2.toml"
    workspace_lock = exact_source_root / "release/index/workspace_lock.v1.toml"
    baseline = qualified[source["route_candidate_package"]]
    candidate = {
        "schema": "facman.release_candidate.v1",
        "candidate_id": "facman-0.1.0-alpha.1-windows-x64-package-set",
        "version": source["version"],
        "release_class": "alpha",
        "status": "qualified",
        "source": {
            "revision": source_revision,
            "tree": comparison["source_tree"],
            "ref": "dev",
            "ref_kind": "dev",
            "clean": True,
        },
        "providers": {
            "workspace_lock_sha256": sha256(workspace_lock),
            "provider_lock_sha256": sha256(provider_lock),
            "identities": _provider_identities(baseline),
        },
        "resolution": {
            "schema": str(comparison["schema"]),
            "root_sha256": str(comparison["comparison_table_sha256"]),
        },
        "artifacts": package_artifacts,
        "evidence": {
            "test_summary_sha256": sha256(comparison_path),
            "sbom_sha256": digest_mapping(sbom_digests),
            "provenance_sha256": digest_mapping(provenance_digests),
            "known_limitations": limitations,
        },
        "three_key": {
            "implementation": {
                "role": "implementation",
                "result": "pass",
                "evidence_sha256": str(comparison["comparison_table_sha256"]),
            },
            "assurance": {
                "role": "assurance",
                "result": "pass",
                "evidence_sha256": sha256(comparison_path),
            },
            "policy": {
                "role": "control",
                "result": "pass",
                "evidence_sha256": sha256(
                    exact_source_root / "release/index/alpha_release_source.v1.toml"
                ),
            },
        },
        "authority": {
            "factorio_execution": False,
            "setup_mutation": False,
            "route_promotion": False,
            "signing": False,
            "publication": False,
            "support_promotion": False,
        },
    }
    _validate_schema(candidate, CANDIDATE_SCHEMA, "candidate record")
    candidate_name = str(asset_for(assets, "candidate_record")["filename"])
    write_json(output / candidate_name, candidate)
    expected_core = _core_names(source)
    _require_inventory(output, expected_core, "machine alpha core")
    receipt = {
        "schema": "facman.alpha_machine_asset_set.v2",
        "source_revision": source_revision,
        "source_tree": comparison["source_tree"],
        "package_sha256": {
            item["name"]: item["sha256"] for item in package_artifacts
        },
        "comparison_sha256": sha256(comparison_path),
        "asset_sha256": {name: sha256(output / name) for name in sorted(expected_core)},
        "pending": ["immutable_tag_receipt", "checksums"],
        "authority": {"tagging": False, "signing": False, "publication": False, "support": False},
    }
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return receipt


def _write_checksums(output: Path, checksums_name: str, names: set[str]) -> None:
    lines = "".join(f"{sha256(output / name)}  {name}\n" for name in sorted(names))
    (output / checksums_name).write_text(lines, encoding="utf-8", newline="\n")


def assemble_tag_assets(
    *, machine_root: Path, tag_receipt: Path, output_root: Path
) -> dict[str, Any]:
    source = load_toml(SOURCE_PATH)
    assets = asset_records(source)
    expected_core = _core_names(source)
    machine_root = machine_root.resolve()
    _require_inventory(machine_root, expected_core, "machine alpha core")
    candidate_name = str(asset_for(assets, "candidate_record")["filename"])
    candidate = load_json(machine_root / candidate_name)
    _validate_schema(candidate, CANDIDATE_SCHEMA, "candidate record")
    _closed_authority(candidate.get("authority"), "candidate record")
    tag = load_json(tag_receipt)
    _validate_schema(tag, TAG_RECEIPT_SCHEMA, "tag receipt")
    if tag.get("source_revision") != candidate.get("source", {}).get("revision"):
        raise ValueError("tag receipt source differs from the machine candidate")
    if tag.get("source_tree") != candidate.get("source", {}).get("tree"):
        raise ValueError("tag receipt tree differs from the machine candidate")
    if tag.get("candidate_sha256") != sha256(machine_root / candidate_name):
        raise ValueError("tag receipt candidate digest differs from the machine candidate")

    output = require_new_output(output_root)
    for name in sorted(expected_core):
        shutil.copy2(machine_root / name, output / name)
    tag_name = str(asset_for(assets, "tag_receipt")["filename"])
    shutil.copy2(tag_receipt, output / tag_name)
    checksums_name = str(asset_for(assets, "checksums")["filename"])
    _write_checksums(output, checksums_name, expected_core | {tag_name})
    expected_tag = milestone_names(source, "tag_only")
    _require_inventory(output, expected_tag, "tag-only alpha")
    receipt = {
        "schema": "facman.alpha_tag_asset_set.v1",
        "source_revision": candidate["source"]["revision"],
        "tag_receipt_sha256": sha256(output / tag_name),
        "checksums_sha256": sha256(output / checksums_name),
        "asset_sha256": {name: sha256(output / name) for name in sorted(expected_tag)},
        "pending": [],
        "authority": {"tagging": False, "signing": False, "publication": False, "support": False},
    }
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return receipt


def _checksum_problems(root: Path, checksums_name: str, expected: set[str]) -> list[str]:
    observed: dict[str, str] = {}
    for line in (root / checksums_name).read_text(encoding="utf-8").splitlines():
        digest, separator, name = line.partition("  ")
        if not separator or len(digest) != 64 or name in observed:
            return ["tag-only checksum manifest is malformed"]
        observed[name] = digest
    if set(observed) != expected - {checksums_name}:
        return ["tag-only checksum manifest has the wrong inventory"]
    return [name for name, digest in observed.items() if sha256(root / name) != digest]


def assemble_public_assets(
    *,
    tag_root: Path,
    route_receipt: Path,
    human_receipt: Path,
    output_root: Path,
) -> dict[str, Any]:
    source = load_toml(SOURCE_PATH)
    assets = asset_records(source)
    packages = package_records(source)
    tag_names = milestone_names(source, "tag_only")
    tag_root = tag_root.resolve()
    _require_inventory(tag_root, tag_names, "tag-only alpha")
    checksums_name = str(asset_for(assets, "checksums")["filename"])
    checksum_problems = _checksum_problems(tag_root, checksums_name, tag_names)
    if checksum_problems:
        raise ValueError("tag-only checksums fail: " + ", ".join(checksum_problems))
    candidate_name = str(asset_for(assets, "candidate_record")["filename"])
    candidate = load_json(tag_root / candidate_name)
    _validate_schema(candidate, CANDIDATE_SCHEMA, "candidate record")
    _closed_authority(candidate.get("authority"), "candidate record")
    route = load_json(route_receipt)
    _validate_schema(route, ROUTE_SCHEMA, "route receipt")
    if route.get("receipt_id") != "facman.successor-play.human-verdict.05":
        raise ValueError("public-alpha assembly requires the exact route-v5 human verdict")
    if route.get("result") != "Pass":
        raise ValueError("public-alpha assembly requires a passing route receipt")
    route_package_id = str(source["route_candidate_package"])
    route_package_name = str(packages[route_package_id]["filename"])
    route_package_sha = sha256(tag_root / route_package_name)
    route_candidate = route.get("candidate", {})
    if route_candidate.get("source_revision") != candidate.get("source", {}).get("revision"):
        raise ValueError("route receipt source differs from the tag candidate")
    if route_candidate.get("package_sha256") != route_package_sha:
        raise ValueError("route receipt package differs from the designated route package")
    if route_candidate.get("candidate_id") != candidate.get("candidate_id"):
        raise ValueError("route receipt candidate identity differs from the tag candidate")
    if route_candidate.get("resolution_sha256") != candidate.get("resolution", {}).get(
        "root_sha256"
    ):
        raise ValueError("route receipt resolution differs from the tag candidate")
    if route_candidate.get("provider_lock_sha256") != candidate.get("providers", {}).get(
        "provider_lock_sha256"
    ):
        raise ValueError("route receipt provider lock differs from the tag candidate")
    if route.get("tester") != "Jules":
        raise ValueError("route-v5 human verdict must be recorded by Jules")
    required_journeys = {
        "facman.factorio-2-1-14.play-to-menu",
        "facman.factorio-2-1-14.last-run-truth",
        "facman.factorio-2-1-14.relaunch-save-visibility",
    }
    observed_journeys = {
        str(item.get("id", ""))
        for item in route.get("journeys", [])
        if isinstance(item, dict)
    }
    if not required_journeys.issubset(observed_journeys):
        raise ValueError("route receipt omits a required route-v5 human journey")
    if any(item.get("result") != "Pass" for item in route.get("journeys", [])):
        raise ValueError("route receipt contains a non-passing journey")
    if route.get("unresolved_findings") != []:
        raise ValueError("route receipt contains unresolved findings")
    _closed_authority(route.get("authority"), "route receipt")

    human = load_json(human_receipt)
    _validate_schema(human, HUMAN_ALPHA_SCHEMA, "alpha human receipt")
    completed_problems = alpha_portable_test_packet.completed_human_problems(human)
    if completed_problems:
        raise ValueError("alpha human receipt rejection: " + "; ".join(completed_problems))
    human_candidate = human.get("candidate", {})
    if human_candidate.get("source_revision") != candidate.get("source", {}).get("revision"):
        raise ValueError("alpha human receipt source differs from the tag candidate")
    if human_candidate.get("source_tree") != candidate.get("source", {}).get("tree"):
        raise ValueError("alpha human receipt tree differs from the tag candidate")
    if human_candidate.get("qualification_sha256") != candidate.get("evidence", {}).get(
        "test_summary_sha256"
    ):
        raise ValueError("alpha human receipt qualification differs from the tag candidate")
    human_packages = {
        str(item.get("id", "")): item
        for item in human_candidate.get("packages", [])
        if isinstance(item, dict)
    }
    if set(human_packages) != set(packages):
        raise ValueError("alpha human receipt does not bind the exact three-package set")
    for package_id, expected in packages.items():
        observed = human_packages[package_id]
        filename = str(expected["filename"])
        if observed.get("filename") != filename:
            raise ValueError(f"alpha human receipt filename differs for {package_id}")
        if observed.get("archive_sha256") != sha256(tag_root / filename):
            raise ValueError(f"alpha human receipt archive differs for {package_id}")

    output = require_new_output(output_root)
    for name in sorted(tag_names - {checksums_name}):
        shutil.copy2(tag_root / name, output / name)
    route_name = str(asset_for(assets, "route_receipt")["filename"])
    shutil.copy2(route_receipt, output / route_name)
    human_name = str(asset_for(assets, "human_test_receipt")["filename"])
    shutil.copy2(human_receipt, output / human_name)
    artifacts = [
        {key: value for key, value in _artifact(output / str(package["filename"])).items() if key not in {"signed", "published"}}
        for package in packages.values()
    ]
    sbom_map = {
        package_id: sha256(output / str(asset_for(assets, "sbom", package_id)["filename"]))
        for package_id in packages
    }
    provenance_map = {
        package_id: sha256(output / str(asset_for(assets, "provenance", package_id)["filename"]))
        for package_id in packages
    }
    ledger = {
        "schema": "facman.release_ledger_entry.v1",
        "version": source["version"],
        "tag": source["tag"]["name"],
        "release_class": "alpha",
        "state": "active",
        "candidate_record": "release/ledger/0.1.0-alpha.1/candidate.v1.json",
        "source": {
            "revision": candidate["source"]["revision"],
            "tree": candidate["source"]["tree"],
            "ref": "dev",
        },
        "provider_lock_sha256": candidate["providers"]["provider_lock_sha256"],
        "workspace_lock_sha256": candidate["providers"]["workspace_lock_sha256"],
        "resolution_sha256": candidate["resolution"]["root_sha256"],
        "artifacts": artifacts,
        "sbom": {"path": "three-package-sbom-set", "sha256": digest_mapping(sbom_map)},
        "provenance": {
            "path": "three-package-provenance-set",
            "sha256": digest_mapping(provenance_map),
        },
        "test_summary_sha256": candidate["evidence"]["test_summary_sha256"],
        "known_limitations": source["known_limitations"],
        "support_class": "unsupported_public_alpha",
        "migration": {
            "status": "not_required",
            "evidence": ["The portable alpha does not migrate a foreign Factorio installation."],
        },
        "rollback": {
            "status": "supported",
            "evidence": ["Remove the portable package and task-owned FacMan workspace."],
        },
        "human_receipt": "release/ledger/0.1.0-alpha.1/human-test-receipt.v1.json",
        "withdrawal": {"state": "not_withdrawn", "record": None},
        "immutable": True,
        "authority": {
            "tag_creation": False,
            "signing": False,
            "publication": False,
            "support_promotion": False,
            "route_promotion": False,
        },
    }
    _validate_schema(ledger, LEDGER_SCHEMA, "release ledger entry")
    ledger_name = str(asset_for(assets, "public_release_ledger_entry")["filename"])
    write_json(output / ledger_name, ledger)
    current_names = {path.name for path in output.iterdir() if path.is_file()}
    _write_checksums(output, checksums_name, current_names)
    expected_public_without_authority = (
        tag_names
        | milestone_names(source, "public_alpha_additional")
    ) - {str(asset_for(assets, "publication_authority_receipt")["filename"])}
    _require_inventory(output, expected_public_without_authority, "public-alpha pre-authority")
    receipt = {
        "schema": "facman.alpha_public_asset_set.v1",
        "source_revision": candidate["source"]["revision"],
        "route_package_sha256": route_package_sha,
        "route_receipt_sha256": sha256(output / route_name),
        "human_receipt_sha256": sha256(output / human_name),
        "checksums_sha256": sha256(output / checksums_name),
        "asset_sha256": {
            name: sha256(output / name) for name in sorted(expected_public_without_authority)
        },
        "pending": ["publication_authority"],
        "authority": {"tagging": False, "signing": False, "publication": False, "support": False},
    }
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return receipt


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    commands = value.add_subparsers(dest="command", required=True)
    machine = commands.add_parser("machine")
    machine.add_argument("--qualification-root", type=Path, required=True)
    machine.add_argument("--source-revision", required=True)
    machine.add_argument("--output", type=Path, required=True)
    machine.add_argument("--receipt", type=Path)
    tag = commands.add_parser("tag")
    tag.add_argument("--machine-root", type=Path, required=True)
    tag.add_argument("--tag-receipt", type=Path, required=True)
    tag.add_argument("--output", type=Path, required=True)
    tag.add_argument("--receipt", type=Path)
    public = commands.add_parser("public")
    public.add_argument("--tag-root", type=Path, required=True)
    public.add_argument("--route-receipt", type=Path, required=True)
    public.add_argument("--human-receipt", type=Path, required=True)
    public.add_argument("--output", type=Path, required=True)
    public.add_argument("--receipt", type=Path)
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "machine":
            receipt = build_machine_assets(
                qualification_root=args.qualification_root,
                output_root=args.output,
                source_revision=args.source_revision,
            )
        elif args.command == "tag":
            receipt = assemble_tag_assets(
                machine_root=args.machine_root,
                tag_receipt=args.tag_receipt,
                output_root=args.output,
            )
        else:
            receipt = assemble_public_assets(
                tag_root=args.tag_root,
                route_receipt=args.route_receipt,
                human_receipt=args.human_receipt,
                output_root=args.output,
            )
        if args.receipt is not None:
            write_receipt(args.receipt, receipt)
    except (OSError, ValueError, json.JSONDecodeError, tomllib.TOMLDecodeError) as exc:
        print(f"alpha-asset-set: {exc}", file=sys.stderr)
        return 1
    print(f"alpha-asset-set: ok ({args.command}; no release authority granted)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
