# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
import tomllib
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import factorio_2_1_14_route_packet_check as schema_adapter
from tools.release_compiler.canonical import domain_digest_value


TEMPLATE = (
    ROOT
    / "docs/quality/evidence/"
    "facman_accessibility_human_test_receipt.template.v1.json"
)
PACKET = ROOT / "docs/quality/facman_accessibility_human_test_packet.md"
SCHEMA = ROOT / "contracts/schema/release/human_test_receipt.v1.schema.json"
CAPABILITY_MATRIX = ROOT / "release/index/capability_frontend_matrix.v1.toml"
PROVIDER_LOCK = ROOT / "release/index/providers.lock.v2.toml"
ALPHA_SOURCE = ROOT / "release/index/alpha_release_source.v1.toml"

UNBOUND_REVISION = "0" * 40
UNBOUND_SHA256 = "0" * 64
EXPECTED_PROVIDER_LOCK_SHA256 = (
    "d33943841431afdeffb7961c7453d8999619ef371793a6310ad2c2952b118f00"
)
EXPECTED_PROVIDERS = {
    "universal_launcher": "5479939ca5cbc9ee0f901608a92012778b4752ae",
    "universal_setup": "d2a2aae7e61c47035c92334b0522143b4fea3880",
}
EXPECTED_TARGET = "windows_winforms_technical_preview_x64"
EXPECTED_ARTIFACT = "windows_winforms_technical_preview_zip"
EXPECTED_PENDING_RECEIPT_ID = "facman-accessibility-human-alpha-1-unbound"
EXPECTED_CANDIDATE_ID = "facman-alpha-1-unbound"
UNASSIGNED = "UNASSIGNED_TEMPLATE_DO_NOT_ACCEPT"

REQUIRED_JOURNEYS = (
    "facman.accessibility.winforms.keyboard-navigation",
    "facman.accessibility.winforms.screen-reader",
    "facman.accessibility.winforms.high-contrast",
    "facman.accessibility.winforms.dpi-100",
    "facman.accessibility.winforms.dpi-150",
    "facman.accessibility.winforms.dpi-200",
    "facman.accessibility.winforms.terminology-navigation",
    "facman.accessibility.tui.keyboard-navigation",
    "facman.accessibility.tui.screen-reader-linear",
    "facman.accessibility.tui.non-color-focus-motion",
    "facman.accessibility.tui.resize-unicode-ascii",
    "facman.accessibility.tui.terminology-navigation",
)

PACKET_ANCHORS = (
    "Mechanical prechecks do not constitute a human verdict.",
    "## Required human judgments",
    "accessibility.winforms",
    "accessibility.tui",
    "0.1.0-alpha.1",
    "derive the exact binding from the verified package and resolution",
    "facman.human_test_receipt.v1",
    "allocated alpha.1 release source",
    "--bind-output",
    "--pending",
    "--receipt",
    "Pass is not",
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        value = tomllib.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a TOML table")
    return value


def load_template() -> dict[str, Any]:
    return load_json(TEMPLATE)


def load_matrix() -> dict[str, Any]:
    return load_toml(CAPABILITY_MATRIX)


def alpha_route_package(source: dict[str, Any]) -> dict[str, Any]:
    route_id = source.get("route_candidate_package")
    packages = source.get("package", [])
    if not isinstance(packages, list):
        raise ValueError("alpha release source package set must be an array")
    matches = [item for item in packages if isinstance(item, dict) and item.get("id") == route_id]
    if len(matches) != 1:
        raise ValueError("alpha release source must identify one route candidate package")
    return matches[0]


def _load_package_stage(path: Path) -> tuple[dict[str, Any], list[str]]:
    if not zipfile.is_zipfile(path):
        return {}, ["human packet package must be a ZIP candidate"]
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            stage = json.loads(archive.read("manifest/stage.v1.json"))
    except KeyError:
        return {}, ["human packet package is missing canonical stage metadata"]
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return {}, [f"human packet package stage metadata cannot be read: {exc}"]
    except (OSError, zipfile.BadZipFile) as exc:
        return {}, [f"human packet package cannot be inspected: {exc}"]
    required = {"bin/facman.exe", "bin/FacMan.WinForms.exe", "manifest/stage.v1.json"}
    missing = sorted(required - names)
    if missing:
        return {}, [f"human packet package is missing canonical entries {missing}"]
    if not isinstance(stage, dict):
        return {}, ["human packet package stage metadata must be a JSON object"]
    return stage, []


def _load_resolution_binding(path: Path) -> tuple[dict[str, str], list[str]]:
    try:
        record = load_json(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {}, [f"human packet resolution cannot be read: {exc}"]
    problems: list[str] = []
    if record.get("schema") != "facman.release_resolution_set.v1":
        problems.append("human packet resolution has the wrong schema")
    if record.get("target_id") != EXPECTED_TARGET:
        problems.append("human packet resolution has the wrong target")
    root_digest = str(record.get("root_digest", ""))
    if len(root_digest) != 64:
        problems.append("human packet resolution has an invalid root digest")
    source = record.get("source", {})
    if not isinstance(source, dict):
        return {}, problems + ["human packet resolution source must be a JSON object"]
    source_revision = str(source.get("implementation_revision", ""))
    source_tree = str(source.get("build_tree", ""))
    if len(source_revision) != 40 or len(source_tree) != 40:
        problems.append("human packet resolution has an invalid source identity")
    if source.get("dirty") is not False or source.get("release_eligible") is not True:
        problems.append("human packet resolution source is not clean and release-eligible")
    providers = {
        item.get("id"): item.get("commit")
        for item in source.get("providers", [])
        if isinstance(item, dict)
    }
    if providers != EXPECTED_PROVIDERS:
        problems.append("human packet resolution has the wrong provider identities")
    if any(
        item.get("dirty") is not False
        for item in source.get("providers", [])
        if isinstance(item, dict)
    ):
        problems.append("human packet resolution has a dirty provider observation")

    composition_name = "resolved-composition.v1.json"
    composition_path = path.parent / composition_name
    records = record.get("records", {})
    expected_composition_sha256 = (
        records.get(composition_name) if isinstance(records, dict) else None
    )
    resolution_digest = ""
    if not composition_path.is_file():
        problems.append("human packet resolution is missing resolved composition")
    else:
        try:
            composition = load_json(composition_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            problems.append(f"human packet resolved composition cannot be read: {exc}")
        else:
            if (
                domain_digest_value("facman.release_resolution.v1", composition)
                != expected_composition_sha256
            ):
                problems.append(
                    "human packet resolved composition digest does not match the set"
                )
            resolution_digest = str(composition.get("resolution_digest", ""))
            if len(resolution_digest) != 64:
                problems.append("human packet resolution has an invalid resolution digest")
    return {
        "source_revision": source_revision,
        "source_tree": source_tree,
        "resolution_root_digest": root_digest,
        "resolution_digest": resolution_digest,
    }, problems


def _artifact_binding(
    package: Path | None,
    resolution: Path | None,
    *,
    mode: str,
) -> tuple[dict[str, str], list[str]]:
    problems: list[str] = []
    if package is None or not package.is_file():
        problems.append(f"{mode} requires the exact package file")
    if resolution is None or not resolution.is_file():
        problems.append(f"{mode} requires the exact resolution file")
    if problems:
        return {}, problems
    assert package is not None and resolution is not None

    alpha_source = load_toml(ALPHA_SOURCE)
    expected_name = alpha_route_package(alpha_source).get("filename")
    if package.name != expected_name:
        problems.append("human packet package filename is not the allocated alpha.1 artifact")
    stage, stage_problems = _load_package_stage(package)
    resolution_binding, resolution_problems = _load_resolution_binding(resolution)
    problems.extend(stage_problems)
    problems.extend(resolution_problems)
    stage_digest = str(stage.get("stage_digest", ""))
    if stage and resolution_binding:
        expected_stage = {
            "schema": "facman.stage_manifest.v1",
            "target_id": EXPECTED_TARGET,
            "product_version": alpha_source.get("canonical_version"),
            "artifact_id": EXPECTED_ARTIFACT,
            "resolution_digest": resolution_binding["resolution_digest"],
            "resolution_root_digest": resolution_binding["resolution_root_digest"],
        }
        for field, expected in expected_stage.items():
            if stage.get(field) != expected:
                problems.append(f"human packet package has the wrong stage {field}")
    if len(stage_digest) != 64:
        problems.append("human packet package has an invalid stage digest")

    binding = {
        **resolution_binding,
        "candidate_id": (
            f"facman-candidate-{resolution_binding.get('source_revision', '')[:8]}-"
            f"{resolution_binding.get('resolution_root_digest', '')[:8]}"
        ),
        "package_sha256": file_sha256(package),
        "resolution_sha256": file_sha256(resolution),
        "provider_lock_sha256": file_sha256(PROVIDER_LOCK),
        "stage_digest": stage_digest,
    }
    return binding, problems


def _candidate_binding_problems(
    record: dict[str, Any], binding: dict[str, str]
) -> list[str]:
    candidate = record.get("candidate", {})
    labels = {
        "candidate_id": "derived qualified candidate identity",
        "source_revision": "verified resolution source revision",
        "package_sha256": "supplied package digest",
        "resolution_sha256": "supplied resolution file digest",
        "provider_lock_sha256": "tracked provider lock",
    }
    return [
        f"receipt is not bound to the {labels[field]}"
        for field in labels
        if candidate.get(field) != binding.get(field)
    ]


def _input_problems(
    record: dict[str, Any],
    matrix: dict[str, Any],
    packet_text: str,
) -> list[str]:
    problems: list[str] = []
    try:
        schema = load_json(SCHEMA)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"human receipt schema cannot be read: {exc}"]

    problems.extend(
        schema_adapter._schema_problems(record, schema, "accessibility receipt")
    )
    if file_sha256(PROVIDER_LOCK) != EXPECTED_PROVIDER_LOCK_SHA256:
        problems.append("tracked provider lock no longer matches the packet binding")

    journeys = record.get("journeys", [])
    journey_ids = [item.get("id") for item in journeys if isinstance(item, dict)]
    if journey_ids != list(REQUIRED_JOURNEYS):
        problems.append("receipt must preserve the complete ordered accessibility journey set")
    if any(
        not isinstance(item, dict) or item.get("version") != "candidate.v1"
        for item in journeys
    ):
        problems.append("every accessibility journey must use candidate.v1")

    authority = record.get("authority", {})
    if not isinstance(authority, dict) or any(value is not False for value in authority.values()):
        problems.append("accessibility receipt may not open release or route authority")

    capabilities = {
        item.get("id"): item
        for item in matrix.get("capability", [])
        if isinstance(item, dict)
    }
    expected_interfaces = {
        "accessibility.winforms": ["winforms"],
        "accessibility.tui": ["tui"],
    }
    for capability_id, interfaces in expected_interfaces.items():
        capability = capabilities.get(capability_id, {})
        if capability.get("status") != "implemented_unqualified":
            problems.append(f"{capability_id} must remain implemented_unqualified")
        if capability.get("required_interfaces") != interfaces:
            problems.append(f"{capability_id} interface binding changed")
        receipt_law = " ".join(
            (
                str(capability.get("accessibility", "")),
                str(capability.get("limits", "")),
            )
        ).lower()
        if "receipt" not in receipt_law:
            problems.append(f"{capability_id} no longer requires exact receipt evidence")

    for anchor in PACKET_ANCHORS:
        if anchor not in packet_text:
            problems.append(f"human packet is missing required anchor {anchor!r}")
    return problems


def validate_template(
    record: dict[str, Any] | None = None,
    matrix: dict[str, Any] | None = None,
    packet_text: str | None = None,
) -> list[str]:
    try:
        record = copy.deepcopy(record) if record is not None else load_template()
        matrix = copy.deepcopy(matrix) if matrix is not None else load_matrix()
        packet_text = packet_text if packet_text is not None else PACKET.read_text(encoding="utf-8")
    except (OSError, ValueError, json.JSONDecodeError, tomllib.TOMLDecodeError) as exc:
        return [f"accessibility packet input cannot be read: {exc}"]

    problems = _input_problems(record, matrix, packet_text)
    expected_template_values = {
        "receipt_id": EXPECTED_PENDING_RECEIPT_ID,
        "tester": UNASSIGNED,
        "tested_at": "1970-01-01T00:00:00Z",
    }
    observed_template_values = {
        "receipt_id": record.get("receipt_id"),
        "tester": record.get("tester"),
        "tested_at": record.get("tested_at"),
    }
    for field, expected in expected_template_values.items():
        if observed_template_values.get(field) != expected:
            problems.append(f"tracked template {field} does not match the pending packet")

    expected_candidate = {
        "candidate_id": EXPECTED_CANDIDATE_ID,
        "source_revision": UNBOUND_REVISION,
        "package_sha256": UNBOUND_SHA256,
        "resolution_sha256": UNBOUND_SHA256,
        "provider_lock_sha256": EXPECTED_PROVIDER_LOCK_SHA256,
    }
    if record.get("candidate") != expected_candidate:
        problems.append(
            "tracked template must remain alpha.1-bound but artifact-unassigned"
        )

    environment = record.get("environment", {})
    for field in ("os", "os_version", "display_profile"):
        if environment.get(field) != UNASSIGNED:
            problems.append(f"tracked template environment.{field} must remain unassigned")
    if environment.get("assistive_technology") is not None:
        problems.append("tracked template assistive technology must remain unassigned")

    journeys = record.get("journeys", [])
    if any(item.get("result") != "Inconclusive" for item in journeys if isinstance(item, dict)):
        problems.append("tracked template journeys must remain Inconclusive")
    if record.get("result") != "Inconclusive":
        problems.append("tracked template result must remain Inconclusive")
    if record.get("accepted_limitations") != []:
        problems.append("tracked template may not pre-accept limitations")
    return problems


def _artifact_problems(
    record: dict[str, Any],
    package: Path | None,
    resolution: Path | None,
    *,
    mode: str,
) -> list[str]:
    binding, problems = _artifact_binding(package, resolution, mode=mode)
    if binding:
        problems.extend(_candidate_binding_problems(record, binding))
    return problems


def bind_pending_receipt(
    package: Path | None,
    resolution: Path | None,
) -> tuple[dict[str, Any], list[str]]:
    binding, problems = _artifact_binding(
        package,
        resolution,
        mode="alpha.1 packet binding",
    )
    if problems:
        return {}, problems
    record = load_template()
    record["receipt_id"] = (
        f"facman-accessibility-human-{binding['source_revision'][:8]}-pending-01"
    )
    record["candidate"] = {
        field: binding[field]
        for field in (
            "candidate_id",
            "source_revision",
            "package_sha256",
            "resolution_sha256",
            "provider_lock_sha256",
        )
    }
    return record, []


def validate_pending_receipt(
    record: dict[str, Any],
    package: Path | None,
    resolution: Path | None,
    matrix: dict[str, Any] | None = None,
    packet_text: str | None = None,
) -> list[str]:
    try:
        selected_matrix = copy.deepcopy(matrix) if matrix is not None else load_matrix()
        selected_packet = packet_text if packet_text is not None else PACKET.read_text(encoding="utf-8")
    except (OSError, ValueError, tomllib.TOMLDecodeError) as exc:
        return [f"accessibility packet input cannot be read: {exc}"]
    problems = _input_problems(record, selected_matrix, selected_packet)
    problems.extend(
        _artifact_problems(
            record,
            package,
            resolution,
            mode="pending human packet",
        )
    )
    candidate = record.get("candidate", {})
    expected_id = f"facman-accessibility-human-{str(candidate.get('source_revision', ''))[:8]}-pending-01"
    if record.get("receipt_id") != expected_id:
        problems.append("pending receipt identity does not match its exact source")
    if record.get("tester") != UNASSIGNED or record.get("tested_at") != "1970-01-01T00:00:00Z":
        problems.append("pending receipt must retain unassigned human identity and time")
    environment = record.get("environment", {})
    if any(environment.get(field) != UNASSIGNED for field in ("os", "os_version", "display_profile")):
        problems.append("pending receipt must retain an unassigned environment")
    if environment.get("assistive_technology") is not None:
        problems.append("pending receipt must retain unassigned assistive technology")
    if record.get("result") != "Inconclusive" or any(
        item.get("result") != "Inconclusive"
        for item in record.get("journeys", [])
        if isinstance(item, dict)
    ):
        problems.append("pending receipt must keep every verdict Inconclusive")
    return problems


def validate_receipt(
    record: dict[str, Any],
    package: Path | None,
    resolution: Path | None,
    matrix: dict[str, Any] | None = None,
    packet_text: str | None = None,
) -> list[str]:
    try:
        selected_matrix = copy.deepcopy(matrix) if matrix is not None else load_matrix()
        selected_packet = packet_text if packet_text is not None else PACKET.read_text(encoding="utf-8")
    except (OSError, ValueError, tomllib.TOMLDecodeError) as exc:
        return [f"accessibility packet input cannot be read: {exc}"]

    problems = _input_problems(record, selected_matrix, selected_packet)
    problems.extend(
        _artifact_problems(
            record,
            package,
            resolution,
            mode="completed receipt",
        )
    )

    if record.get("receipt_id") == "unassigned" or str(record.get("receipt_id", "")).endswith("-pending-01"):
        problems.append("completed receipt requires a new human receipt identity")
    if record.get("tester") == UNASSIGNED:
        problems.append("completed receipt requires an identified tester")
    if record.get("tested_at") == "1970-01-01T00:00:00Z":
        problems.append("completed receipt requires the observed test time")

    environment = record.get("environment", {})
    if any(environment.get(field) == UNASSIGNED for field in ("os", "os_version", "display_profile")):
        problems.append("completed receipt requires the exact observed environment")
    if not environment.get("assistive_technology"):
        problems.append("completed receipt must name the assistive technology used")

    journeys = record.get("journeys", [])
    if any(
        "TEMPLATE ONLY" in observation
        for item in journeys
        if isinstance(item, dict)
        for observation in item.get("observations", [])
        if isinstance(observation, str)
    ):
        problems.append("completed receipt retains template-only journey observations")
    if any(
        "TEMPLATE ONLY" in observation
        for observation in record.get("observations", [])
        if isinstance(observation, str)
    ):
        problems.append("completed receipt retains template-only overall observations")

    result = record.get("result")
    journey_results = [item.get("result") for item in journeys if isinstance(item, dict)]
    if result == "Pass":
        if any(value != "Pass" for value in journey_results):
            problems.append("overall Pass requires every required journey to Pass")
        if record.get("unresolved_findings"):
            problems.append("overall Pass cannot retain unresolved findings")
    elif result == "Fail" and "Fail" not in journey_results:
        problems.append("overall Fail requires at least one failed journey")
    elif result == "Inconclusive" and "Inconclusive" not in journey_results:
        problems.append("overall Inconclusive requires an inconclusive journey")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate the non-authorizing FacMan accessibility human-test packet."
    )
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--package", type=Path)
    parser.add_argument("--resolution", type=Path)
    parser.add_argument(
        "--bind-output",
        type=Path,
        help="write a no-clobber alpha.1 Inconclusive receipt bound to the supplied exact artifacts",
    )
    parser.add_argument(
        "--pending",
        action="store_true",
        help="verify the bound Inconclusive packet and exact artifacts before human execution",
    )
    args = parser.parse_args(argv)

    if args.bind_output is not None:
        if args.receipt is not None or args.pending:
            problems = ["--bind-output cannot be combined with --receipt or --pending"]
        elif args.bind_output.exists():
            problems = ["--bind-output refuses to overwrite an existing receipt"]
        else:
            receipt, problems = bind_pending_receipt(args.package, args.resolution)
            if not problems:
                problems = validate_pending_receipt(
                    receipt,
                    args.package,
                    args.resolution,
                )
            if not problems:
                args.bind_output.parent.mkdir(parents=True, exist_ok=True)
                args.bind_output.write_text(
                    json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
        success = "exact alpha.1 artifacts bound to an Inconclusive human packet"
    elif args.pending and args.receipt is None:
        problems = ["--pending requires --receipt plus the exact package and resolution"]
        success = ""
    elif args.receipt is None:
        problems = validate_template()
        success = "alpha.1 template is artifact-unassigned and Inconclusive; no verdict accepted"
    else:
        try:
            receipt = load_json(args.receipt)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            problems = [f"human receipt cannot be read: {exc}"]
        else:
            if args.pending:
                problems = validate_pending_receipt(
                    receipt,
                    args.package,
                    args.resolution,
                )
            else:
                problems = validate_receipt(receipt, args.package, args.resolution)
        success = (
            "exact candidate packet is ready for human execution; every verdict remains Inconclusive"
            if args.pending
            else "receipt is structurally valid and non-authorizing; human acceptance remains separate"
        )

    if problems:
        for problem in problems:
            print(f"accessibility-human-test-packet-check: {problem}", file=sys.stderr)
        return 1
    print(f"accessibility-human-test-packet-check: ok ({success})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
