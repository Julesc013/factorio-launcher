# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Construct and inspect the unsigned, provisional Windows C1 candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import json_contract, package_build, package_hash_manifest, provenance_build

PROFILE_ID = "windows_legacy_winforms_x64"
SCHEMA = ROOT / "contracts/schema/release/windows_c1_release_candidate.v1.schema.json"
RELEASE_NOTES = "docs/release/facman-0.1.0-windows-release-candidate.md"
REQUIRED_PATHS = (
    "bin/FacMan.WinForms.exe",
    "bin/facman.exe",
    "bin/ulk.dll",
    "bin/usk.dll",
    "bin/flb_factorio.dll",
    "contracts/schema",
    "content/factorio",
    "licenses/LICENSE",
    "licenses/THIRD_PARTY_NOTICES.md",
    "licenses/UniversalLauncher.txt",
    "licenses/UniversalSetup.txt",
    "licenses/Miniz.txt",
    "licenses/PicoJSON.txt",
    "manifest/build_info.v1.json",
    "manifest/components.v1.json",
    "manifest/hashes.sha256",
    "manifest/package.v1.toml",
    "manifest/sbom.spdx.v2.3.json",
    RELEASE_NOTES,
)
BLOCKERS = (
    "windows_10_clean_machine_qualification_pending",
    "windows_11_clean_machine_qualification_pending",
    "keyboard_narrator_accessibility_insights_qualification_pending",
    "high_contrast_and_100_150_200_scaling_qualification_pending",
    "portable_zip_relocation_qualification_pending",
    "diagnostic_redaction_qualification_pending",
    "exact_live_play_route_authority_absent",
    "authenticode_signing_and_publication_deferred",
)
WINDOWS_DEVELOPER_PATHS = (
    re.compile(rb"[a-z]:\\users\\[^\\\r\n<>]{1,64}\\", re.IGNORECASE),
    re.compile(rb"[a-z]:\\projects\\", re.IGNORECASE),
    re.compile(rb"[a-z]:\\a\\factorio-launcher\\", re.IGNORECASE),
)
UNIX_DEVELOPER_PATHS = (
    re.compile(rb"(?<![a-z0-9])/(?:home|users)/[^/\r\n<>]{1,64}/", re.IGNORECASE),
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--dist", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--expected-source-revision", required=True)
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = construct(
            build_root=args.build_root.resolve(),
            out_root=args.out.resolve(),
            dist_root=args.dist.resolve(),
            expected_source_revision=args.expected_source_revision,
            allow_dirty=args.allow_dirty,
        )
        evidence = args.evidence.resolve()
        evidence.parent.mkdir(parents=True, exist_ok=True)
        evidence.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, ValueError, tomllib.TOMLDecodeError) as exc:
        print(f"windows-c1-release-candidate: {exc}", file=sys.stderr)
        return 1
    print(f"windows-c1-release-candidate: provisional {evidence}")
    return 0


def construct(
    *,
    build_root: Path,
    out_root: Path,
    dist_root: Path,
    expected_source_revision: str,
    allow_dirty: bool = False,
) -> dict[str, Any]:
    expected_source_revision = require_revision(expected_source_revision)
    require_equal(repository_revision(), expected_source_revision, "checked-out source revision")
    package_root = package_build.build_profile(
        profile_id=PROFILE_ID,
        out_root=out_root,
        build_root=build_root,
        dist_root=dist_root,
        allow_dirty=allow_dirty,
    )
    artifacts = sorted(dist_root.glob("*.zip"))
    if len(artifacts) != 1:
        raise ValueError(f"expected exactly one Windows candidate ZIP, found {len(artifacts)}")
    artifact = artifacts[0]
    checksum = artifact.with_name(artifact.name + ".sha256")
    checksum.write_text(f"{sha256(artifact)}  {artifact.name}\n", encoding="utf-8", newline="\n")
    return inspect_candidate(package_root, artifact, expected_source_revision)


def inspect_candidate(
    package_root: Path, artifact: Path, expected_source_revision: str
) -> dict[str, Any]:
    package_root = package_root.resolve()
    artifact = artifact.resolve()
    expected_source_revision = require_revision(expected_source_revision)
    require_paths(package_root)
    package = load_toml(package_root / "manifest/package.v1.toml")
    build_info = load_json(package_root / "manifest/build_info.v1.json")
    require_equal(package.get("profile_id"), PROFILE_ID, "profile id")
    require_equal(package.get("target_os"), "windows", "target OS")
    require_equal(package.get("target_arch"), "x64", "target architecture")
    require_equal(package.get("entrypoint"), "bin/FacMan.WinForms.exe", "entrypoint")
    require_equal(package.get("source_revision"), build_info.get("source_commit"), "source identity")
    require_equal(
        package.get("source_revision"),
        expected_source_revision,
        "source revision",
    )
    require_equal(build_info.get("source_dirty"), False, "clean source")
    require_no_developer_machine_paths(package_root)
    if package_hash_manifest.verify_manifest(package_root):
        raise ValueError("candidate package hash manifest failed verification")
    provenance = artifact.with_name(artifact.name + ".provenance.v1.json")
    provenance_problems = provenance_build.verify_artifact_provenance(
        provenance, artifact, package_root
    )
    if provenance_problems:
        raise ValueError("candidate provenance failed: " + "; ".join(provenance_problems))
    checksum = artifact.with_name(artifact.name + ".sha256")
    if checksum.read_text(encoding="utf-8").strip() != f"{sha256(artifact)}  {artifact.name}":
        raise ValueError("candidate checksum does not match artifact")
    require_source_boundaries()
    report = evidence_report(
        source_revision=str(package["source_revision"]), artifact=artifact, checksum=checksum
    )
    problems = json_contract.validate(report, json_contract.load_schema(SCHEMA))
    if problems:
        raise ValueError("candidate evidence violates schema: " + "; ".join(problems))
    return report


def evidence_report(
    *, source_revision: str, artifact: Path, checksum: Path
) -> dict[str, Any]:
    return {
        "schema": "facman.windows_c1_release_candidate.v1",
        "status": "provisional",
        "source_revision": source_revision,
        "profile_id": PROFILE_ID,
        "target": {
            "os": "windows_10_11",
            "architecture": "x64",
            "frontend": "winforms_net_framework_4_8",
            "transport": "bounded_process_rpc",
        },
        "artifact": {
            "name": artifact.name,
            "size": artifact.stat().st_size,
            "sha256": sha256(artifact),
            "checksum_file": checksum.name,
            "signed": False,
            "published": False,
        },
        "package": {
            "component_closure": "pass",
            "hash_manifest": "pass",
            "sbom": "pass",
            "licenses_notices": "pass",
            "release_notes": "pass",
            "support_export": "pass",
            "live_presentation_mode": "pass",
            "explicit_evidence_mode": "pass",
            "source_clean": True,
            "developer_machine_paths": "absent",
        },
        "qualification": {
            "package_construction": "pass",
            "windows_10_clean_machine": "not_run",
            "windows_11_clean_machine": "not_run",
            "accessibility": "not_run",
            "scaling": "not_run",
            "relocation": "not_run",
            "diagnostic_redaction": "not_run",
            "live_play": "blocked_by_exact_route_authority",
        },
        "claims": {
            "release_candidate": False,
            "supported_release": False,
            "live_play": False,
            "signed": False,
            "published": False,
        },
        "blockers": list(BLOCKERS),
    }


def require_paths(root: Path) -> None:
    missing = [relative for relative in REQUIRED_PATHS if not (root / relative).exists()]
    if missing:
        raise ValueError("candidate package is missing: " + ", ".join(missing))
    linked = [relative for relative in REQUIRED_PATHS if (root / relative).is_symlink()]
    if linked:
        raise ValueError("candidate package contains linked required paths: " + ", ".join(linked))


def require_source_boundaries() -> None:
    shell = (ROOT / "apps/gui/windows/winforms/C1ShellForm.cs").read_text(encoding="utf-8")
    live_store = (ROOT / "apps/gui/windows/winforms/C1LivePresentationStore.cs").read_text(
        encoding="utf-8"
    )
    catalog = load_json(ROOT / "contracts/generated-index/command_catalog.v2.json")
    command_ids = {
        item.get("command_id")
        for item in catalog.get("commands", [])
        if isinstance(item, dict)
    }
    if "FACMAN_PRESENTATION_MODE" not in shell or '"evidence"' not in shell:
        raise ValueError("WinForms shell lacks explicit evidence-mode selection")
    if "diagnostics.export" not in command_ids:
        raise ValueError("support export command is absent from the generated backend catalog")
    for anchor in (
        'RequireRoute("presentation.query")',
        'RequireRoute("presentation.action")',
        "BackendPresentationSnapshot.ParseEnvelope",
        "expected_snapshot_revision",
        "idempotency_key",
    ):
        if anchor not in live_store:
            raise ValueError("WinForms live presentation lacks typed backend seam: " + anchor)
    for forbidden in ('"workspace.status"', '"instances.readiness"', '"run.execute"'):
        if forbidden in live_store:
            raise ValueError("WinForms live presentation retains a direct policy route: " + forbidden)


def require_no_developer_machine_paths(root: Path) -> None:
    for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
        payload = path.read_bytes().replace(b"\x00", b"")
        windows_payload = payload.replace(b"/", b"\\")
        if any(pattern.search(windows_payload) for pattern in WINDOWS_DEVELOPER_PATHS) or any(
            pattern.search(payload) for pattern in UNIX_DEVELOPER_PATHS
        ):
            relative = path.relative_to(root).as_posix()
            raise ValueError(f"candidate contains a developer-machine path: {relative}")


def require_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ValueError(f"candidate {label} must be {expected!r}, got {actual!r}")


def require_revision(value: str) -> str:
    if re.fullmatch(r"[0-9a-f]{40}", value) is None:
        raise ValueError("expected source revision must be exactly 40 lowercase hexadecimal characters")
    return value


def repository_revision() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError("cannot resolve the checked-out source revision") from exc
    return require_revision(completed.stdout.strip())


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
