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


TEMPLATE = (
    ROOT
    / "docs/quality/evidence/"
    "facman_accessibility_human_test_receipt.template.v1.json"
)
PACKET = ROOT / "docs/quality/facman_accessibility_human_test_packet.md"
SCHEMA = ROOT / "contracts/schema/release/human_test_receipt.v1.schema.json"
CAPABILITY_MATRIX = ROOT / "release/index/capability_frontend_matrix.v1.toml"
PROVIDER_LOCK = ROOT / "release/index/providers.lock.v2.toml"

EXPECTED_SOURCE_REVISION = "601c5f49b7aa1cf4eb2b2af9733ac3e07e7ed27f"
EXPECTED_SOURCE_TREE = "05cb5d547f64064eb52e0f9bc5d314ac9697864f"
EXPECTED_PROVIDER_LOCK_SHA256 = (
    "d33943841431afdeffb7961c7453d8999619ef371793a6310ad2c2952b118f00"
)
EXPECTED_PROVIDERS = {
    "universal_launcher": "5479939ca5cbc9ee0f901608a92012778b4752ae",
    "universal_setup": "d2a2aae7e61c47035c92334b0522143b4fea3880",
}
EXPECTED_TARGET = "windows_winforms_technical_preview_x64"
ZERO_SHA256 = "0" * 64
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
    EXPECTED_SOURCE_REVISION,
    EXPECTED_SOURCE_TREE,
    "facman.human_test_receipt.v1",
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


def _package_problems(path: Path) -> list[str]:
    if not zipfile.is_zipfile(path):
        return ["completed receipt package must be a ZIP candidate"]
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
    except (OSError, zipfile.BadZipFile) as exc:
        return [f"completed receipt package cannot be inspected: {exc}"]
    required = {"bin/facman.exe", "bin/FacMan.WinForms.exe", "manifest/stage.v1.json"}
    missing = sorted(required - names)
    if missing:
        return [f"completed receipt package is missing canonical entries {missing}"]
    return []


def _resolution_problems(path: Path) -> list[str]:
    try:
        record = load_json(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"completed receipt resolution cannot be read: {exc}"]
    problems: list[str] = []
    if record.get("schema") != "facman.release_resolution_set.v1":
        problems.append("completed receipt resolution has the wrong schema")
    if record.get("target_id") != EXPECTED_TARGET:
        problems.append("completed receipt resolution has the wrong target")
    source = record.get("source", {})
    if source.get("implementation_revision") != EXPECTED_SOURCE_REVISION:
        problems.append("completed receipt resolution has the wrong source revision")
    if source.get("dirty") is not False or source.get("release_eligible") is not True:
        problems.append("completed receipt resolution source is not clean and release-eligible")
    providers = {
        item.get("id"): item.get("commit")
        for item in source.get("providers", [])
        if isinstance(item, dict)
    }
    if providers != EXPECTED_PROVIDERS:
        problems.append("completed receipt resolution has the wrong provider identities")
    return problems


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

    candidate = record.get("candidate", {})
    if candidate.get("source_revision") != EXPECTED_SOURCE_REVISION:
        problems.append("receipt is not bound to the exact packet source revision")
    if candidate.get("provider_lock_sha256") != EXPECTED_PROVIDER_LOCK_SHA256:
        problems.append("receipt is not bound to the exact provider lock")

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
    candidate = record.get("candidate", {})
    expected_sentinels = {
        "receipt_id": "unassigned",
        "candidate_id": "unassigned",
        "package_sha256": ZERO_SHA256,
        "resolution_sha256": ZERO_SHA256,
        "tester": UNASSIGNED,
        "tested_at": "1970-01-01T00:00:00Z",
    }
    observed_sentinels = {
        "receipt_id": record.get("receipt_id"),
        "candidate_id": candidate.get("candidate_id"),
        "package_sha256": candidate.get("package_sha256"),
        "resolution_sha256": candidate.get("resolution_sha256"),
        "tester": record.get("tester"),
        "tested_at": record.get("tested_at"),
    }
    for field, expected in expected_sentinels.items():
        if observed_sentinels.get(field) != expected:
            problems.append(f"tracked template {field} must remain the unassigned sentinel")

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
    candidate = record.get("candidate", {})
    for label, path, field in (
        ("package", package, "package_sha256"),
        ("resolution", resolution, "resolution_sha256"),
    ):
        if path is None or not path.is_file():
            problems.append(f"completed receipt requires the exact {label} file")
        elif candidate.get(field) != file_sha256(path):
            problems.append(f"completed receipt {label} digest does not match the supplied file")
        elif label == "package":
            problems.extend(_package_problems(path))
        else:
            problems.extend(_resolution_problems(path))

    if record.get("receipt_id") == "unassigned":
        problems.append("completed receipt requires an assigned receipt identity")
    if candidate.get("candidate_id") == "unassigned":
        problems.append("completed receipt requires an assigned candidate identity")
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
    args = parser.parse_args(argv)

    if args.receipt is None:
        problems = validate_template()
        success = "template is deterministic and Inconclusive; no verdict accepted"
    else:
        try:
            receipt = load_json(args.receipt)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            problems = [f"human receipt cannot be read: {exc}"]
        else:
            problems = validate_receipt(receipt, args.package, args.resolution)
        success = "receipt is structurally valid and non-authorizing; human acceptance remains separate"

    if problems:
        for problem in problems:
            print(f"accessibility-human-test-packet-check: {problem}", file=sys.stderr)
        return 1
    print(f"accessibility-human-test-packet-check: ok ({success})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
