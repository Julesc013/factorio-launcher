# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Prepare a fail-closed Windows Sandbox bundle for private route replay.

The private archive is staged under a generic name by hard link.  Windows
Sandbox receives only narrowly scoped, read-only input directories and a
separate writable evidence directory.  The archive is never added to a FacMan
package or uploaded by this tool.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.sax.saxutils import escape


ROOT = Path(__file__).resolve().parents[1]
GUEST_RUNNER = ROOT / "tools" / "windows_private_route_guest.ps1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class BundleError(RuntimeError):
    """A fail-closed bundle validation error."""


WSB_SCALAR_SETTINGS = (
    ("VGpu", "Disable"),
    ("Networking", "Disable"),
    ("ClipboardRedirection", "Disable"),
    ("PrinterRedirection", "Disable"),
    ("AudioInput", "Disable"),
    ("VideoInput", "Disable"),
    ("ProtectedClient", "Enable"),
)


def _xml_text(element: ET.Element, label: str) -> str:
    if element.attrib or list(element):
        raise BundleError(f"{label} must be one scalar XML element")
    value = element.text or ""
    if value != value.strip() or not value:
        raise BundleError(f"{label} has non-canonical text")
    return value


def validate_wsb_configuration(
    text: str,
    expected_mappings: list[tuple[Path, str, bool]],
    expected_command: str,
) -> None:
    """Validate the complete authority-relevant Windows Sandbox structure."""

    try:
        root = ET.fromstring(text)
    except ET.ParseError as error:
        raise BundleError("WSB configuration is not well-formed XML") from error
    if root.tag != "Configuration" or root.attrib or (root.text or "").strip():
        raise BundleError("WSB root must be one canonical Configuration element")

    expected_top_level = [name for name, _value in WSB_SCALAR_SETTINGS] + [
        "MappedFolders",
        "LogonCommand",
    ]
    actual_top_level = [child.tag for child in root]
    if actual_top_level != expected_top_level:
        raise BundleError("WSB authority elements are missing, duplicated, unknown, or reordered")
    for child, (name, value) in zip(root[: len(WSB_SCALAR_SETTINGS)], WSB_SCALAR_SETTINGS):
        if child.tag != name or _xml_text(child, name) != value:
            raise BundleError(f"WSB {name} must be {value}")

    mapped_folders = root[len(WSB_SCALAR_SETTINGS)]
    if mapped_folders.attrib or (mapped_folders.text or "").strip():
        raise BundleError("MappedFolders must not carry attributes or text")
    mapped = list(mapped_folders)
    if len(mapped) != len(expected_mappings):
        raise BundleError("WSB mapped-folder set changed")
    for element, (host, guest, read_only) in zip(mapped, expected_mappings):
        if element.tag != "MappedFolder" or element.attrib or (element.text or "").strip():
            raise BundleError("WSB contains an invalid mapped-folder element")
        children = list(element)
        if [child.tag for child in children] != ["HostFolder", "SandboxFolder", "ReadOnly"]:
            raise BundleError("WSB mapped-folder fields are missing, duplicated, unknown, or reordered")
        expected = (str(host), guest, str(read_only).lower())
        actual = tuple(_xml_text(child, child.tag) for child in children)
        if actual != expected:
            raise BundleError("WSB mapped-folder custody or access mode changed")

    logon = root[len(WSB_SCALAR_SETTINGS) + 1]
    if logon.attrib or (logon.text or "").strip():
        raise BundleError("LogonCommand must not carry attributes or text")
    logon_children = list(logon)
    if [child.tag for child in logon_children] != ["Command"]:
        raise BundleError("WSB LogonCommand fields changed")
    if _xml_text(logon_children[0], "Command") != expected_command:
        raise BundleError("WSB LogonCommand changed")


def build_wsb_configuration(
    mappings: list[tuple[Path, str, bool]],
    command: str,
) -> str:
    def mapped(host: Path, guest: str, read_only: bool) -> str:
        return (
            "      <MappedFolder>\n"
            f"        <HostFolder>{escape(str(host))}</HostFolder>\n"
            f"        <SandboxFolder>{escape(guest)}</SandboxFolder>\n"
            f"        <ReadOnly>{str(read_only).lower()}</ReadOnly>\n"
            "      </MappedFolder>"
        )

    scalars = "".join(f"  <{name}>{value}</{name}>\n" for name, value in WSB_SCALAR_SETTINGS)
    value = (
        "<Configuration>\n"
        + scalars
        + "  <MappedFolders>\n"
        + "\n".join(mapped(*mapping) for mapping in mappings)
        + "\n  </MappedFolders>\n"
        "  <LogonCommand>\n"
        f"    <Command>{escape(command)}</Command>\n"
        "  </LogonCommand>\n"
        "</Configuration>\n"
    )
    validate_wsb_configuration(value, mappings, command)
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _exact_file(path: Path, label: str) -> Path:
    resolved = path.resolve(strict=True)
    if not resolved.is_file() or resolved.is_symlink():
        raise BundleError(f"{label} must be one regular, non-symlink file")
    return resolved


def _exact_empty_directory(path: Path, label: str) -> Path:
    resolved = path.resolve(strict=True)
    if not resolved.is_dir() or resolved.is_symlink():
        raise BundleError(f"{label} must be one existing non-symlink directory")
    if any(resolved.iterdir()):
        raise BundleError(f"{label} must be empty before two-phase route preparation")
    return resolved


def _expected_digest(value: str, label: str) -> str:
    normalized = value.lower()
    if not SHA256_RE.fullmatch(normalized):
        raise BundleError(f"{label} must be one lowercase SHA-256 digest")
    return normalized


def _verify(path: Path, expected: str, label: str) -> dict[str, object]:
    actual = sha256_file(path)
    if actual != expected:
        raise BundleError(f"{label} digest mismatch: expected {expected}, got {actual}")
    return {"sha256": actual, "bytes": path.stat().st_size}


def _stage_file(source: Path, destination: Path, allow_copy: bool) -> str:
    try:
        os.link(source, destination)
        return "hardlink"
    except OSError as error:
        if not allow_copy:
            raise BundleError(
                f"cannot hard-link {source.name}; use --allow-copy only when a local copy is acceptable"
            ) from error
        shutil.copy2(source, destination)
        return "copy"


def _ensure_new_output(output: Path) -> Path:
    resolved = output.resolve()
    if resolved == Path(resolved.anchor) or len(resolved.parts) < 3:
        raise BundleError("output must be a narrow task-owned directory")
    if resolved.exists():
        raise BundleError("output already exists; a fresh task-owned directory is required")
    resolved.mkdir(parents=True, exist_ok=False)
    return resolved


def prepare_bundle(args: argparse.Namespace) -> Path:
    candidate = _exact_file(Path(args.candidate_zip), "candidate ZIP")
    archive = _exact_file(Path(args.private_archive), "private archive")
    harness = _exact_file(Path(args.harness), "engineering harness")
    route_record = _exact_file(Path(args.route_record), "route record")
    permit_root = _exact_empty_directory(Path(args.permit_root), "permit handshake root")

    expected = {
        "candidate": _expected_digest(args.candidate_sha256, "candidate digest"),
        "archive": _expected_digest(args.private_archive_sha256, "archive digest"),
        "harness": _expected_digest(args.harness_sha256, "harness digest"),
        "route_record": _expected_digest(args.route_record_sha256, "route-record digest"),
        "factorio_executable": _expected_digest(
            args.factorio_executable_sha256, "Factorio executable digest"
        ),
    }
    verified = {
        "candidate": _verify(candidate, expected["candidate"], "candidate ZIP"),
        "archive": _verify(archive, expected["archive"], "private archive"),
        "harness": _verify(harness, expected["harness"], "engineering harness"),
        "route_record": _verify(route_record, expected["route_record"], "route record"),
    }

    output = _ensure_new_output(Path(args.output))
    input_root = output / "input"
    evidence_root = output / "evidence"
    candidate_root = input_root / "candidate"
    private_root = input_root / "private"
    harness_root = input_root / "harness"
    for directory in (candidate_root, private_root, harness_root, evidence_root):
        directory.mkdir(parents=True, exist_ok=False)

    try:
        staging = {
            "candidate": _stage_file(candidate, candidate_root / "candidate.zip", args.allow_copy),
            "archive": _stage_file(archive, private_root / "private-input.zip", args.allow_copy),
            "harness": _stage_file(harness, harness_root / "harness.exe", args.allow_copy),
            "route_record": _stage_file(
                route_record, harness_root / "route-record.toml", args.allow_copy
            ),
        }
    except Exception:
        # This exact directory was created above and did not exist on entry.
        shutil.rmtree(output)
        raise
    shutil.copy2(GUEST_RUNNER, harness_root / "run.ps1")
    shutil.copy2(Path(__file__).resolve(), harness_root / "bundle-builder.py")

    command = (
        "powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass "
        "-File C:\\FacManHarness\\run.ps1 "
        "-Manifest C:\\FacManHarness\\manifest.v2.json"
    )
    mappings = [
        (candidate_root, "C:\\FacManCandidate", True),
        (private_root, "C:\\FacManPrivate", True),
        (harness_root, "C:\\FacManHarness", True),
        (permit_root, "C:\\FacManPermit", True),
        (evidence_root, "C:\\FacManEvidence", False),
    ]
    wsb = build_wsb_configuration(mappings, command)
    wsb_path = output / "FacManPrivateRoute.wsb"
    wsb_path.write_text(wsb, encoding="utf-8")
    shutil.copy2(wsb_path, harness_root / "sandbox.wsb")

    guest_manifest = {
        "schema": "facman.private_route_guest_manifest.v2",
        "classification": "local_private_input_engineering_only",
        "networking": "disabled",
        "candidate": verified["candidate"],
        "private_archive": verified["archive"],
        "engineering_harness": verified["harness"],
        "route_record": verified["route_record"],
        "guest_runner": {"sha256": sha256_file(harness_root / "run.ps1")},
        "bundle_builder": {"sha256": sha256_file(harness_root / "bundle-builder.py")},
        "sandbox_configuration": {"sha256": sha256_file(harness_root / "sandbox.wsb")},
        "factorio_executable": {"sha256": expected["factorio_executable"]},
        "route_id": args.route_id,
        "harness_acknowledgement": args.harness_acknowledgement,
        "candidate_path": "C:\\FacManCandidate\\candidate.zip",
        "private_archive_path": "C:\\FacManPrivate\\private-input.zip",
        "harness_path": "C:\\FacManHarness\\harness.exe",
        "route_record_path": "C:\\FacManHarness\\route-record.toml",
        "guest_runner_path": "C:\\FacManHarness\\run.ps1",
        "bundle_builder_path": "C:\\FacManHarness\\bundle-builder.py",
        "sandbox_configuration_path": "C:\\FacManHarness\\sandbox.wsb",
        "permit_path": "C:\\FacManPermit",
        "evidence_path": "C:\\FacManEvidence",
        "permit_protocol": {
            "schema": "facman.route_permit_two_phase.v1",
            "topology": "host_guest_evidence_handshake",
            "maximum_ttl_seconds": 120,
            "preissue_both_permits": False,
            "slots": [
                {
                    "launch_ordinal": 1,
                    "action": "launch",
                    "operation_id": "facman.successor-play.launch-1.operation.04",
                    "attempt_id": "facman.successor-play.launch-1.attempt.04",
                },
                {
                    "launch_ordinal": 2,
                    "action": "relaunch",
                    "operation_id": "facman.successor-play.launch-2.operation.04",
                    "attempt_id": "facman.successor-play.launch-2.attempt.04",
                    "requires_first_terminal_receipt": True,
                    "requires_safety_revalidation": True,
                },
            ],
        },
    }
    manifest_path = harness_root / "manifest.v2.json"
    manifest_path.write_text(
        json.dumps(guest_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    custody = {
        "schema": "facman.private_route_bundle_receipt.v1",
        "status": "prepared_not_executed",
        "classification": "private_input_local_only_not_release_evidence",
        "private_archive_uploaded": False,
        "private_archive_packaged": False,
        "networking": "disabled",
        "staging_methods": staging,
        "input_digests": expected,
        "guest_manifest_sha256": sha256_file(manifest_path),
        "guest_runner_sha256": sha256_file(harness_root / "run.ps1"),
        "bundle_builder_sha256": sha256_file(harness_root / "bundle-builder.py"),
        "wsb_sha256": sha256_file(wsb_path),
        "permit_topology": "host_guest_evidence_handshake",
        "preissue_both_permits": False,
    }
    (output / "bundle-receipt.v1.json").write_text(
        json.dumps(custody, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    if args.launch:
        sandbox = Path(os.environ.get("SystemRoot", "C:\\Windows")) / "System32" / "WindowsSandbox.exe"
        if not sandbox.is_file():
            raise BundleError("Windows Sandbox is not installed")
        subprocess.Popen([str(sandbox), str(wsb_path)])
    return wsb_path


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--candidate-zip", required=True)
    value.add_argument("--candidate-sha256", required=True)
    value.add_argument("--private-archive", required=True)
    value.add_argument("--private-archive-sha256", required=True)
    value.add_argument("--harness", required=True)
    value.add_argument("--harness-sha256", required=True)
    value.add_argument("--route-record", required=True)
    value.add_argument("--route-record-sha256", required=True)
    value.add_argument("--factorio-executable-sha256", required=True)
    value.add_argument("--route-id", required=True)
    value.add_argument("--permit-root", required=True)
    value.add_argument(
        "--harness-acknowledgement",
        default="TEST-HARNESS-NO-REAL-RELEASE-AUTHORITY",
    )
    value.add_argument("--output", required=True)
    value.add_argument("--allow-copy", action="store_true")
    value.add_argument("--launch", action="store_true")
    return value


def main() -> int:
    try:
        location = prepare_bundle(parser().parse_args())
    except (BundleError, OSError) as error:
        print(json.dumps({"status": "refused", "detail": str(error)}), file=sys.stderr)
        return 2
    print(json.dumps({"status": "prepared", "wsb": str(location)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
