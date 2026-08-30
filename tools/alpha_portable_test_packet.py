# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Validate or bind the alpha.1 portable human-test packet to exact packages."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import json_contract

TEMPLATE = ROOT / "docs/quality/evidence/facman_0_1_alpha1_human_test_receipt.template.v1.json"
SCHEMA = ROOT / "contracts/schema/release/alpha1_portable_human_test_receipt.v1.schema.json"
QUALIFICATION_SCHEMA = ROOT / "contracts/schema/release/alpha1_final_dev_three_root_qualification.v1.schema.json"
ZERO40 = "0" * 40
ZERO64 = "0" * 64
UNASSIGNED = "UNASSIGNED_TEMPLATE_DO_NOT_ACCEPT"
PACKAGE_IDS = (
    "windows_cli_x64_portable",
    "windows_tui_x64_portable",
    "windows_winforms_x64_portable",
)
LANE_IDS = (
    "windows.cli-json",
    "windows.cli-human",
    "windows.tui",
    "windows.winforms",
    "api.frontend-session-v2",
    "sdk.providers",
    "sdk.facman-engineering",
    "linux.package-previews",
    "factorio.real-play-boundary",
)
HUMAN_VERDICTS = ("Pass", "Fail", "Inconclusive")
PACKAGE_FIELDS = (
    "id", "profile", "filename", "providers", "contract_set_sha256",
    "state_identity", "package_tree_sha256", "archive_sha256",
    "embedded_manifest_sha256", "sbom_sha256", "provenance_sha256",
    "licence_inventory_sha256", "file_count", "uncompressed_bytes", "archive_bytes",
)
ARCHIVE_MEMBERS = {
    "manifest/hashes.sha256": "package_tree_sha256",
    "manifest/package.v1.toml": "embedded_manifest_sha256",
}


def _contains_unassigned(value: Any) -> bool:
    if isinstance(value, str):
        return not value.strip() or "UNASSIGNED" in value.upper()
    if isinstance(value, dict):
        return any(_contains_unassigned(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_unassigned(item) for item in value)
    return False


def completed_human_problems(value: dict[str, Any]) -> list[str]:
    """Validate the human-only completion semantics required for public alpha."""

    problems = human_execution_problems(value)
    lanes = value.get("test_lanes", [])
    if value.get("result") != "Pass":
        problems.append("completed packet must record an overall Pass")
    for lane in lanes:
        if not isinstance(lane, dict):
            continue
        lane_id = str(lane.get("id", "<missing>"))
        if lane.get("result") != "Pass":
            problems.append(f"completed packet lane {lane_id} must Pass")
    if value.get("unresolved_findings") != []:
        problems.append("completed packet must have no unresolved findings")
    return problems


def human_execution_problems(value: dict[str, Any]) -> list[str]:
    """Validate a completed human receipt without inventing a passing verdict."""

    problems: list[str] = []
    lanes = value.get("test_lanes", [])
    lane_ids = [item.get("id") for item in lanes if isinstance(item, dict)]
    if lane_ids != list(LANE_IDS):
        problems.append("completed packet must retain the exact nine ordered test lanes")
    if value.get("packet_status") != "human_execution_complete":
        problems.append("completed packet must record completed human execution")
    if not isinstance(value.get("tester"), str) or _contains_unassigned(value.get("tester")):
        problems.append("completed packet must identify an assigned tester")
    if not isinstance(value.get("tested_at"), str) or not value["tested_at"].strip():
        problems.append("completed packet must record a test timestamp")
    environment = value.get("environment")
    if not isinstance(environment, dict) or not environment or _contains_unassigned(environment):
        problems.append("completed packet must record assigned test environments")
    if len(lanes) != len(LANE_IDS):
        problems.append("completed packet must contain exactly nine test lanes")
    lane_results: list[object] = []
    for lane in lanes:
        if not isinstance(lane, dict):
            problems.append("completed packet contains a non-object test lane")
            continue
        lane_id = str(lane.get("id", "<missing>"))
        lane_results.append(lane.get("result"))
        if lane.get("result") not in HUMAN_VERDICTS:
            problems.append(f"completed packet lane {lane_id} has an invalid verdict")
        if not isinstance(lane.get("tester"), str) or _contains_unassigned(lane.get("tester")):
            problems.append(f"completed packet lane {lane_id} must identify an assigned tester")
        observations = lane.get("observations")
        if (
            not isinstance(observations, list)
            or not observations
            or _contains_unassigned(observations)
        ):
            problems.append(f"completed packet lane {lane_id} must record direct observations")
    observations = value.get("observations")
    if (
        not isinstance(observations, list)
        or not observations
        or _contains_unassigned(observations)
    ):
        problems.append("completed packet must record overall observations")
    result = value.get("result")
    if result not in HUMAN_VERDICTS:
        problems.append("completed packet has an invalid overall verdict")
    elif result == "Pass" and any(item != "Pass" for item in lane_results):
        problems.append("a passing completed packet requires every lane to Pass")
    elif result == "Fail" and "Fail" not in lane_results:
        problems.append("a failed completed packet must contain at least one failed lane")
    elif result == "Inconclusive" and "Inconclusive" not in lane_results:
        problems.append("an inconclusive completed packet must contain an inconclusive lane")
    unresolved = value.get("unresolved_findings")
    if result == "Pass" and unresolved != []:
        problems.append("a passing completed packet must have no unresolved findings")
    if result in ("Fail", "Inconclusive") and not unresolved:
        problems.append(f"a {str(result).lower()} completed packet must record unresolved findings")
    authority = value.get("authority", {})
    if not isinstance(authority, dict) or any(item is not False for item in authority.values()):
        problems.append("completed packet must keep every authority false")
    return problems


def completed_scope_problems(
    value: dict[str, Any], expected: dict[str, Any]
) -> list[str]:
    """Keep the reviewed nine-lane scope byte-exact in completed evidence."""

    problems: list[str] = []
    observed_lanes = value.get("test_lanes", [])
    expected_lanes = expected.get("test_lanes", [])
    if not isinstance(observed_lanes, list) or len(observed_lanes) != len(expected_lanes):
        problems.append("completed packet changed the immutable lane set")
        return problems
    for index, (observed, frozen) in enumerate(zip(observed_lanes, expected_lanes)):
        if not isinstance(observed, dict) or not isinstance(frozen, dict):
            problems.append(f"completed packet lane {index + 1} is not an object")
            continue
        lane_id = str(frozen.get("id", index + 1))
        for field in ("id", "scope", "classification", "checks"):
            if observed.get(field) != frozen.get(field):
                problems.append(
                    f"completed packet lane {lane_id} changed immutable field {field}"
                )
    return problems


def completed_binding_problems(
    value: dict[str, Any], expected: dict[str, Any]
) -> list[str]:
    """Keep every machine-derived and declared-scope field byte-exact."""

    problems: list[str] = []
    for field in ("schema", "receipt_id", "candidate", "classification", "authority"):
        if value.get(field) != expected.get(field):
            problems.append(f"completed packet changed immutable field {field}")
    problems.extend(completed_scope_problems(value, expected))
    return problems


def completed_receipt_problems(
    value: dict[str, Any], expected: dict[str, Any], *, require_pass: bool
) -> list[str]:
    """Validate one exact-package human receipt for handoff or G2 acceptance."""

    problems = schema_problems(value, SCHEMA)
    problems.extend(completed_binding_problems(value, expected))
    if require_pass:
        problems.extend(completed_human_problems(value))
    else:
        problems.extend(human_execution_problems(value))
    return problems


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def schema_problems(value: dict[str, Any], schema_path: Path) -> list[str]:
    return json_contract.validate(value, json_contract.load_schema(schema_path))


def semantic_problems(value: dict[str, Any], *, bound: bool) -> list[str]:
    problems: list[str] = []
    lanes = value.get("test_lanes", [])
    lane_ids = [item.get("id") for item in lanes if isinstance(item, dict)]
    if lane_ids != list(LANE_IDS):
        problems.append("packet must retain the exact nine ordered test lanes")
    if value.get("result") != "Inconclusive" or any(
        item.get("result") != "Inconclusive" for item in lanes if isinstance(item, dict)
    ):
        problems.append("pending packet must keep every human verdict Inconclusive")
    if value.get("tester") != UNASSIGNED or any(
        item.get("tester") != "UNASSIGNED" for item in lanes if isinstance(item, dict)
    ):
        problems.append("pending packet must not assign or invent a tester")
    authority = value.get("authority", {})
    if not isinstance(authority, dict) or any(item is not False for item in authority.values()):
        problems.append("packet must keep every authority false")
    candidate = value.get("candidate", {})
    packages = candidate.get("packages", []) if isinstance(candidate, dict) else []
    package_ids = [item.get("id") for item in packages if isinstance(item, dict)]
    if package_ids != list(PACKAGE_IDS):
        problems.append("packet must bind the exact ordered CLI, TUI, and WinForms packages")
    if bound:
        if value.get("packet_status") != "exact_artifacts_bound_pending_human_execution":
            problems.append("bound packet has the wrong status")
        if candidate.get("source_revision") == ZERO40 or candidate.get("source_tree") == ZERO40:
            problems.append("bound packet has an unassigned source")
        if candidate.get("qualification_sha256") == ZERO64:
            problems.append("bound packet has an unassigned qualification")
        for package in packages:
            if len(package.get("providers", [])) != 2:
                problems.append(f"{package.get('id')}: bound provider pair is incomplete")
            for key in PACKAGE_FIELDS:
                if key.endswith("_sha256") and package.get(key) == ZERO64:
                    problems.append(f"{package.get('id')}: {key} remains unassigned")
            if any(int(package.get(key, 0)) < 1 for key in ("file_count", "uncompressed_bytes", "archive_bytes")):
                problems.append(f"{package.get('id')}: package counts remain unassigned")
    else:
        if value.get("packet_status") != "unbound_template":
            problems.append("tracked packet template must remain unbound")
        if candidate.get("source_revision") != ZERO40 or candidate.get("source_tree") != ZERO40:
            problems.append("tracked packet template must not bind source identity")
        if candidate.get("qualification_sha256") != ZERO64:
            problems.append("tracked packet template must not bind qualification evidence")
    return problems


def qualification(qualification_root: Path) -> tuple[Path, dict[str, Any]]:
    path = qualification_root.resolve() / "three-root-qualification.v1.json"
    value = load_json(path)
    problems = schema_problems(value, QUALIFICATION_SCHEMA)
    if problems:
        raise ValueError("qualification schema rejection: " + "; ".join(problems))
    if value.get("status") != "pass" or value.get("mismatch_count") != 0:
        raise ValueError("qualification is not a passing byte-identical three-root result")
    return path, value


def verify_machine_package(machine_root: Path, package: dict[str, Any]) -> None:
    filename = str(package["filename"])
    paths = {
        "archive_sha256": machine_root / filename,
        "sbom_sha256": machine_root / f"{filename}.sbom.spdx.v2.3.json",
        "provenance_sha256": machine_root / f"{filename}.provenance.v1.json",
        "licence_inventory_sha256": machine_root / f"{filename}.licence-inventory.v1.json",
    }
    for digest_key, evidence in paths.items():
        if not evidence.is_file() or sha256(evidence) != package[digest_key]:
            raise ValueError(f"{package['id']}: {digest_key} evidence is absent or differs")
    archive_path = paths["archive_sha256"]
    if archive_path.stat().st_size != package["archive_bytes"]:
        raise ValueError(f"{package['id']}: archive byte count differs")
    try:
        with zipfile.ZipFile(archive_path) as archive:
            files = [item for item in archive.infolist() if not item.is_dir()]
            if len(files) != package["file_count"]:
                raise ValueError(f"{package['id']}: package file count differs")
            if sum(item.file_size for item in files) != package["uncompressed_bytes"]:
                raise ValueError(f"{package['id']}: package uncompressed byte count differs")
            for member, digest_key in ARCHIVE_MEMBERS.items():
                if sha256_bytes(archive.read(member)) != package[digest_key]:
                    raise ValueError(f"{package['id']}: embedded {member} differs")
    except (KeyError, zipfile.BadZipFile) as exc:
        raise ValueError(f"{package['id']}: package archive evidence is invalid: {exc}") from exc


def bound_record(qualification_root: Path, machine_root: Path) -> dict[str, Any]:
    qualification_path, qualified = qualification(qualification_root)
    machine_root = machine_root.resolve()
    records = {item["id"]: item for item in qualified["packages"]}
    packages: list[dict[str, Any]] = []
    for package_id in PACKAGE_IDS:
        source = records[package_id]
        verify_machine_package(machine_root, source)
        packages.append({key: copy.deepcopy(source[key]) for key in PACKAGE_FIELDS})
    value = load_json(TEMPLATE)
    value["receipt_id"] = f"facman-0.1.0-alpha.1-portable-human-{qualified['source_revision'][:12]}"
    value["packet_status"] = "exact_artifacts_bound_pending_human_execution"
    value["candidate"] = {
        "source_revision": qualified["source_revision"],
        "source_tree": qualified["source_tree"],
        "qualification_sha256": sha256(qualification_path),
        "packages": packages,
    }
    value["observations"] = [
        "Exact final protected-dev packages are bound. Human execution has not started; automated qualification does not create a human verdict."
    ]
    value["unresolved_findings"] = [
        "Tester, environments, direct observations, and human judgments are unassigned.",
        "All lane and overall verdicts remain Inconclusive pending human execution.",
    ]
    return value


def validate(value: dict[str, Any], *, bound: bool) -> list[str]:
    return schema_problems(value, SCHEMA) + semantic_problems(value, bound=bound)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    actions = value.add_mutually_exclusive_group(required=True)
    actions.add_argument("--check-template", action="store_true")
    actions.add_argument("--bind", action="store_true")
    actions.add_argument("--verify-bound", type=Path)
    actions.add_argument("--verify-human", type=Path)
    actions.add_argument("--verify-passing", type=Path)
    value.add_argument("--qualification-root", type=Path)
    value.add_argument("--machine-root", type=Path)
    value.add_argument("--output", type=Path)
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    success = "human verdict and all authority remain closed"
    try:
        if args.check_template:
            problems = validate(load_json(TEMPLATE), bound=False)
        else:
            if args.qualification_root is None or args.machine_root is None:
                raise ValueError("--qualification-root and --machine-root are required for bind/verify")
            expected = bound_record(args.qualification_root, args.machine_root)
            if args.bind:
                if args.output is None:
                    raise ValueError("--output is required with --bind")
                if args.output.exists():
                    raise ValueError(f"refusing to overwrite {args.output}")
                problems = validate(expected, bound=True)
                if not problems:
                    args.output.parent.mkdir(parents=True, exist_ok=True)
                    args.output.write_text(json.dumps(expected, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            elif args.verify_bound is not None:
                observed = load_json(args.verify_bound)
                problems = validate(observed, bound=True)
                if observed != expected:
                    problems.append("bound packet differs from the exact qualification-derived packet")
            else:
                receipt = args.verify_human or args.verify_passing
                observed = load_json(receipt)
                problems = completed_receipt_problems(
                    observed,
                    expected,
                    require_pass=args.verify_passing is not None,
                )
                success = (
                    f"exact human receipt {observed.get('result', '<missing>')} verified; "
                    "all authority remains closed"
                )
        if problems:
            for problem in problems:
                print(f"alpha-portable-test-packet: {problem}", file=sys.stderr)
            return 1
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"alpha-portable-test-packet: {exc}", file=sys.stderr)
        return 1
    print(f"alpha-portable-test-packet: ok ({success})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
