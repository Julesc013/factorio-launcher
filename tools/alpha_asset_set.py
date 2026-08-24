# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Assemble non-authorizing FacMan alpha machine and route-bound asset sets."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import json_contract

SOURCE_PATH = ROOT / "release/index/alpha_release_source.v1.toml"
CANDIDATE_SCHEMA = ROOT / "contracts/schema/release/release_candidate.v1.schema.json"
LEDGER_SCHEMA = ROOT / "contracts/schema/release/release_ledger_entry.v1.schema.json"
ROUTE_SCHEMA = ROOT / "contracts/schema/release/human_test_receipt.v1.schema.json"
ZERO_SHA256 = "0" * 64


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def asset_names(source: dict[str, Any]) -> dict[str, str]:
    records = {
        str(item["role"]): str(item["filename"])
        for item in source.get("assets", [])
        if isinstance(item, dict)
    }
    if len(records) != 10:
        raise ValueError("alpha release source must contain exactly ten asset roles")
    return records


def _validate_schema(value: dict[str, Any], schema: Path, label: str) -> None:
    problems = json_contract.validate(value, json_contract.load_schema(schema))
    if problems:
        raise ValueError(f"{label} schema rejection: {'; '.join(problems)}")


def _closed_authority(authority: object, label: str) -> None:
    if not isinstance(authority, dict) or any(value is not False for value in authority.values()):
        raise ValueError(f"{label} authority must be present and entirely false")


def validate_comparison(
    comparison: dict[str, Any], provenance: dict[str, Any], source_revision: str
) -> None:
    if comparison.get("schema") != "facman.canonical_v2_three_root_comparison.v1":
        raise ValueError("qualification comparison has the wrong schema")
    if comparison.get("source_revision") != source_revision:
        raise ValueError("qualification comparison has the wrong source revision")
    roots = comparison.get("roots")
    if not isinstance(roots, list) or [item.get("id") for item in roots] != [
        "root1",
        "root2",
        "root3",
    ]:
        raise ValueError("qualification comparison must contain roots 1, 2, and 3")
    root_shapes = {
        (item.get("file_count"), item.get("total_bytes"))
        for item in roots
        if isinstance(item, dict)
    }
    if len(root_shapes) != 1 or comparison.get("mismatch_count") != 0:
        raise ValueError("qualification comparison is not byte-identical across three roots")
    if comparison.get("mismatches") != []:
        raise ValueError("qualification comparison retains mismatch records")
    required_decisions = {
        "stable_root_build": "pass_in_every_root",
        "native_package_verify": "pass_in_every_root",
        "drift_refusal": "pass_in_every_root",
        "archive_verify": "pass_in_every_root",
        "assurance_verify": "pass_in_every_root",
    }
    if comparison.get("qualification") != required_decisions:
        raise ValueError("qualification comparison does not carry every passing machine decision")
    _closed_authority(comparison.get("authority"), "qualification comparison")
    source = provenance.get("source", {})
    if source.get("revision") != source_revision or source.get("tree") != comparison.get(
        "source_tree"
    ):
        raise ValueError("candidate provenance has the wrong source identity")
    if source.get("dirty") is not False or source.get("release_eligible") is not True:
        raise ValueError("candidate provenance source is not clean and release-eligible")
    if provenance.get("status") != "pass" or provenance.get("published") is not False:
        raise ValueError("candidate provenance is not passing and unpublished")
    artifact = provenance.get("artifact", {})
    if artifact.get("sha256") != comparison.get("archive_sha256"):
        raise ValueError("candidate archive differs from the three-root comparison")
    if provenance.get("resolution", {}).get("root_digest") != comparison.get(
        "resolution_root_digest"
    ):
        raise ValueError("candidate resolution root differs from the comparison")
    if provenance.get("stage", {}).get("stage_digest") != comparison.get("stage_digest"):
        raise ValueError("candidate stage differs from the comparison")
    verifier = provenance.get("runtime_verifier", {})
    if (
        verifier.get("native_admission_ready") is not True
        or verifier.get("source_release_eligible") is not True
        or verifier.get("static_closure_verified") is not True
    ):
        raise ValueError("candidate native runtime-verifier admission is incomplete")
    _closed_authority(provenance.get("authority"), "candidate provenance")


def _provider_identities(provider_lock: dict[str, Any]) -> list[dict[str, str]]:
    identities: list[dict[str, str]] = []
    for item in provider_lock.get("provider", []):
        if not isinstance(item, dict):
            continue
        identities.append(
            {
                "id": str(item["id"]),
                "revision": str(item["source_revision"]),
                "tree": str(item["source_tree"]),
                "package_identity": (
                    f"{item['package_identity_kind']}:{item['package_digest']}"
                ),
                "abi": str(item["abi_version"]),
                "contract_digest": str(item["contract_digest"]),
            }
        )
    identities.sort(key=lambda item: item["id"])
    if [item["id"] for item in identities] != ["universal_launcher", "universal_setup"]:
        raise ValueError("provider lock does not contain the exact ULK and USK identities")
    return identities


def _artifact(path: Path, media_type: str, *, unpublished: bool = False) -> dict[str, Any]:
    record: dict[str, Any] = {
        "name": path.name,
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
        "media_type": media_type,
    }
    if unpublished:
        record.update({"signed": False, "published": False})
    return record


def build_machine_assets(
    *,
    qualification_root: Path,
    output_root: Path,
    source_revision: str,
    release_source_root: Path | None = None,
) -> dict[str, Any]:
    qualification_root = qualification_root.resolve()
    exact_source_root = (
        release_source_root.resolve()
        if release_source_root is not None
        else qualification_root / "root1/facman"
    )
    exact_source_path = exact_source_root / "release/index/alpha_release_source.v1.toml"
    exact_provider_lock_path = exact_source_root / "release/index/providers.lock.v2.toml"
    exact_workspace_lock_path = exact_source_root / "release/index/workspace_lock.v1.toml"
    source = load_toml(exact_source_path)
    provider_lock = load_toml(exact_provider_lock_path)
    names = asset_names(source)
    comparison_path = qualification_root / "three-root-comparison.v1.json"
    comparison = load_json(comparison_path)
    root1 = qualification_root / "root1"
    provenance_paths = list((root1 / "dist/assurance").glob("*.provenance.v1.json"))
    sbom_paths = list((root1 / "dist/assurance").glob("*.sbom.spdx.v2.3.json"))
    if len(provenance_paths) != 1 or len(sbom_paths) != 1:
        raise ValueError("qualification root must contain one canonical provenance and SBOM")
    provenance_path = provenance_paths[0]
    sbom_path = sbom_paths[0]
    provenance = load_json(provenance_path)
    validate_comparison(comparison, provenance, source_revision)
    archive = root1 / "dist" / names["package"]
    if not archive.is_file():
        raise ValueError("qualification root does not contain the canonical alpha package")
    if sha256(archive) != comparison.get("archive_sha256"):
        raise ValueError("canonical alpha package digest differs from the comparison")
    if sha256(sbom_path) != comparison.get("sbom_sha256"):
        raise ValueError("canonical alpha SBOM digest differs from the comparison")
    if sha256(provenance_path) != comparison.get("provenance_sha256"):
        raise ValueError("canonical alpha provenance digest differs from the comparison")

    resolution_set = root1 / "resolution/release-resolution-set.v1.json"
    resolution = load_json(resolution_set)
    output = require_new_output(output_root)
    for source_path, role in (
        (archive, "package"),
        (sbom_path, "sbom"),
        (provenance_path, "provenance"),
    ):
        shutil.copy2(source_path, output / names[role])

    limitations = [str(item) for item in source.get("known_limitations", [])]
    limitations_text = "# FacMan 0.1.0-alpha.1 known limitations\n\n" + "".join(
        f"- {item}\n" for item in limitations
    )
    (output / names["known_limitations"]).write_text(
        limitations_text, encoding="utf-8", newline="\n"
    )

    licence_inventory = {
        "schema": "facman.alpha_licence_inventory.v1",
        "version": source["version"],
        "package_sha256": sha256(output / names["package"]),
        "entries": provenance.get("licences", []),
        "authority": {
            "signing": False,
            "publication": False,
            "support_promotion": False,
        },
    }
    write_json(output / names["licence_inventory"], licence_inventory)

    workspace_lock_sha = sha256(exact_workspace_lock_path)
    provider_lock_sha = sha256(exact_provider_lock_path)
    package_record = _artifact(
        output / names["package"], "application/zip", unpublished=True
    )
    candidate = {
        "schema": "facman.release_candidate.v1",
        "candidate_id": "facman-0.1.0-alpha.1-windows-x86_64",
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
            "workspace_lock_sha256": workspace_lock_sha,
            "provider_lock_sha256": provider_lock_sha,
            "identities": _provider_identities(provider_lock),
        },
        "resolution": {
            "schema": str(resolution["schema"]),
            "root_sha256": comparison["resolution_root_digest"],
        },
        "artifacts": [package_record],
        "evidence": {
            "test_summary_sha256": sha256(comparison_path),
            "sbom_sha256": sha256(output / names["sbom"]),
            "provenance_sha256": sha256(output / names["provenance"]),
            "known_limitations": limitations,
        },
        "three_key": {
            "implementation": {
                "role": "implementation",
                "result": "pass",
                "evidence_sha256": str(comparison["source_observation_digest"]),
            },
            "assurance": {
                "role": "assurance",
                "result": "pass",
                "evidence_sha256": sha256(comparison_path),
            },
            "policy": {
                "role": "control",
                "result": "pass",
                "evidence_sha256": sha256(exact_source_path),
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
    write_json(output / names["candidate_record"], candidate)

    ledger = {
        "schema": "facman.release_ledger_entry.v1",
        "version": source["version"],
        "tag": source["tag"]["name"],
        "release_class": "alpha",
        "state": "active",
        "candidate_record": "release/ledger/0.1.0-alpha.1/candidate.v1.json",
        "source": {
            "revision": source_revision,
            "tree": comparison["source_tree"],
            "ref": "dev",
        },
        "provider_lock_sha256": provider_lock_sha,
        "workspace_lock_sha256": workspace_lock_sha,
        "resolution_sha256": sha256(resolution_set),
        "artifacts": [
            {
                key: value
                for key, value in package_record.items()
                if key not in {"signed", "published"}
            }
        ],
        "sbom": {
            "path": names["sbom"],
            "sha256": sha256(output / names["sbom"]),
        },
        "provenance": {
            "path": names["provenance"],
            "sha256": sha256(output / names["provenance"]),
        },
        "test_summary_sha256": sha256(comparison_path),
        "known_limitations": limitations,
        "support_class": "unsupported_public_alpha",
        "migration": {
            "status": "not_required",
            "evidence": ["The portable alpha does not migrate a foreign Factorio installation."],
        },
        "rollback": {
            "status": "supported",
            "evidence": ["Remove the portable package and task-owned FacMan workspace."],
        },
        "human_receipt": None,
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
    write_json(output / names["release_ledger_entry"], ledger)

    expected = {
        names[role]
        for role in (
            "package",
            "sbom",
            "provenance",
            "known_limitations",
            "licence_inventory",
            "candidate_record",
            "release_ledger_entry",
        )
    }
    observed = {path.name for path in output.iterdir() if path.is_file()}
    if observed != expected:
        raise ValueError("machine asset inventory is not exact")
    receipt = {
        "schema": "facman.alpha_machine_asset_set.v1",
        "source_revision": source_revision,
        "package_sha256": sha256(output / names["package"]),
        "comparison_sha256": sha256(comparison_path),
        "asset_sha256": {name: sha256(output / name) for name in sorted(observed)},
        "pending": ["passing_route_receipt", "publication_authority"],
        "authority": {
            "tagging": False,
            "signing": False,
            "publication": False,
            "support": False,
        },
    }
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return receipt


def assemble_route_bound_assets(
    *, machine_root: Path, route_receipt: Path, output_root: Path
) -> dict[str, Any]:
    source = load_toml(SOURCE_PATH)
    names = asset_names(source)
    machine_root = machine_root.resolve()
    expected_machine = {
        names[role]
        for role in (
            "package",
            "sbom",
            "provenance",
            "known_limitations",
            "licence_inventory",
            "candidate_record",
            "release_ledger_entry",
        )
    }
    observed_machine = {
        path.name for path in machine_root.iterdir() if path.is_file()
    }
    if observed_machine != expected_machine:
        raise ValueError("downloaded machine asset inventory is not exact")
    candidate = load_json(machine_root / names["candidate_record"])
    ledger = load_json(machine_root / names["release_ledger_entry"])
    _validate_schema(candidate, CANDIDATE_SCHEMA, "candidate record")
    _validate_schema(ledger, LEDGER_SCHEMA, "release ledger entry")
    _closed_authority(candidate.get("authority"), "candidate record")
    _closed_authority(ledger.get("authority"), "release ledger entry")

    route = load_json(route_receipt)
    _validate_schema(route, ROUTE_SCHEMA, "route receipt")
    if route.get("result") != "Pass":
        raise ValueError("route-bound assembly requires a passing route receipt")
    route_candidate = route.get("candidate", {})
    package_sha = sha256(machine_root / names["package"])
    if route_candidate.get("source_revision") != candidate.get("source", {}).get("revision"):
        raise ValueError("route receipt source differs from the machine candidate")
    if route_candidate.get("package_sha256") != package_sha:
        raise ValueError("route receipt package differs from the machine candidate")
    if route_candidate.get("resolution_sha256") != ledger.get("resolution_sha256"):
        raise ValueError("route receipt resolution differs from the machine candidate")
    if route_candidate.get("provider_lock_sha256") != candidate.get("providers", {}).get(
        "provider_lock_sha256"
    ):
        raise ValueError("route receipt provider lock differs from the machine candidate")
    if any(item.get("result") != "Pass" for item in route.get("journeys", [])):
        raise ValueError("route receipt contains a non-passing journey")
    _closed_authority(route.get("authority"), "route receipt")

    output = require_new_output(output_root)
    for name in sorted(expected_machine):
        shutil.copy2(machine_root / name, output / name)
    shutil.copy2(route_receipt, output / names["route_receipt"])
    checksummed_names = sorted(expected_machine | {names["route_receipt"]})
    checksum_lines = "".join(
        f"{sha256(output / name)}  {name}\n" for name in checksummed_names
    )
    (output / names["checksums"]).write_text(
        checksum_lines, encoding="utf-8", newline="\n"
    )
    expected_final_without_authority = expected_machine | {
        names["route_receipt"],
        names["checksums"],
    }
    observed = {path.name for path in output.iterdir() if path.is_file()}
    if observed != expected_final_without_authority:
        raise ValueError("route-bound alpha asset inventory is not exact")
    receipt = {
        "schema": "facman.alpha_route_bound_asset_set.v1",
        "source_revision": candidate["source"]["revision"],
        "package_sha256": package_sha,
        "route_receipt_sha256": sha256(output / names["route_receipt"]),
        "checksums_sha256": sha256(output / names["checksums"]),
        "asset_sha256": {name: sha256(output / name) for name in sorted(observed)},
        "pending": ["publication_authority"],
        "authority": {
            "tagging": False,
            "signing": False,
            "publication": False,
            "support": False,
        },
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
    assemble = commands.add_parser("assemble")
    assemble.add_argument("--machine-root", type=Path, required=True)
    assemble.add_argument("--route-receipt", type=Path, required=True)
    assemble.add_argument("--output", type=Path, required=True)
    assemble.add_argument("--receipt", type=Path)
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
        else:
            receipt = assemble_route_bound_assets(
                machine_root=args.machine_root,
                route_receipt=args.route_receipt,
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
