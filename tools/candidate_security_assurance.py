# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Fail-closed security and supply-chain inspection for a FacMan candidate ZIP."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tomllib
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BINARIES = {
    "bin/facman.exe",
    "bin/FacMan.WinForms.exe",
    "bin/flb_factorio.dll",
    "bin/ulk.dll",
    "bin/usk.dll",
}
EXPECTED_SBOM_PACKAGES = {
    "FacMan",
    "Universal Launcher",
    "Universal Setup",
    "Miniz",
    "PicoJSON",
}
REQUIRED_LICENSES = {
    "licenses/LICENSE",
    "licenses/THIRD_PARTY_NOTICES.md",
    "licenses/UniversalLauncher.txt",
    "licenses/UniversalSetup.txt",
    "licenses/Miniz.txt",
    "licenses/PicoJSON.txt",
}
ALLOWED_ENGINEERING_SCHEMA = (
    "contracts/schema/factorio/facman_engineering_play_result.v1.schema.json"
)
TEXT_SUFFIXES = {
    ".cfg", ".cmake", ".config", ".ini", ".json", ".license", ".md",
    ".ps1", ".sh", ".toml", ".txt", ".xml", ".yaml", ".yml",
}
PRIVATE_MARKERS = (
    b"factorio-space-age_win_2.1.14.zip",
    b"E:\\Downloads",
    b"E:\\F8FIX",
    b"D:\\Projects\\Factorio",
    b"C:\\Users\\Jules",
)
TOKEN_PATTERNS = (
    re.compile(rb"gho_[A-Za-z0-9_]{20,}"),
    re.compile(rb"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(rb"AKIA[0-9A-Z]{16}"),
)


@dataclass(frozen=True)
class Finding:
    severity: str
    code: str
    location: str
    detail: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_zip_name(name: str) -> bool:
    if not name or "\\" in name or name.startswith("/") or "\x00" in name or ":" in name:
        return False
    value = PurePosixPath(name.rstrip("/"))
    return bool(value.parts) and all(part not in ("", ".", "..") for part in value.parts)


def _sensitive_markers(data: bytes) -> list[str]:
    lowered = data.lower()
    matches = [marker.decode("ascii") for marker in PRIVATE_MARKERS if marker.lower() in lowered]
    for pattern in TOKEN_PATTERNS:
        if pattern.search(data):
            matches.append(pattern.pattern.decode("ascii"))
    return matches


def _source_findings(source_root: Path) -> list[Finding]:
    findings: list[Finding] = []
    result = subprocess.run(
        ["git", "ls-files", "-z"], cwd=source_root, check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    for raw_name in result.stdout.split(b"\0"):
        if not raw_name:
            continue
        relative = raw_name.decode("utf-8", errors="strict")
        if relative in {
            "tools/candidate_security_assurance.py",
            "tests/test_candidate_security_assurance.py",
        }:
            continue
        path = source_root / relative
        try:
            data = path.read_bytes()
        except OSError as error:
            findings.append(Finding("error", "source_read_failed", relative, str(error)))
            continue
        for marker in _sensitive_markers(data):
            historical = relative.startswith((
                ".aide/history/", ".aide/queue/", "docs/release/checkpoints/",
                "docs/reviews/", "tests/",
            ))
            findings.append(Finding(
                "warning" if historical else "error",
                "historical_evidence_local_marker" if historical else "private_or_local_source_marker",
                relative,
                f"tracked source contains local/private marker excluded from candidate bytes: {marker}",
            ))
    return findings


def _zip_findings(archive: zipfile.ZipFile) -> tuple[list[Finding], dict[str, str]]:
    findings: list[Finding] = []
    names: list[str] = []
    digests: dict[str, str] = {}
    seen: set[str] = set()
    casefolded: dict[str, str] = {}
    binaries: set[str] = set()

    for info in archive.infolist():
        name = info.filename
        names.append(name)
        if not _safe_zip_name(name):
            findings.append(Finding("error", "unsafe_zip_path", name, "path is not a safe relative POSIX path"))
        if name in seen:
            findings.append(Finding("error", "duplicate_zip_path", name, "path occurs more than once"))
        seen.add(name)
        folded = name.casefold()
        prior = casefolded.get(folded)
        if prior is not None and prior != name:
            findings.append(Finding("error", "case_collision", name, f"collides with {prior}"))
        casefolded[folded] = name
        if ":" in name:
            findings.append(Finding("error", "alternate_data_stream_path", name, "colon is forbidden in package paths"))
        unix_mode = (info.external_attr >> 16) & 0xFFFF
        if stat.S_ISLNK(unix_mode):
            findings.append(Finding("error", "zip_symlink", name, "symbolic links are forbidden"))
        lowered = name.lower()
        if lowered.endswith((".pdb", ".ilk", ".obj", ".lib", ".exp")):
            findings.append(Finding("error", "debug_or_build_artifact", name, "build-only artifact is shipped"))
        if lowered.endswith((".exe", ".dll")):
            binaries.add(name)
        if name != ALLOWED_ENGINEERING_SCHEMA and re.search(
            r"(?i)(fake[-_]?executor|test[-_]?executor|engineering[-_]?play[-_]?harness|gate4c[-_]?verdict[-_]?harness)",
            name,
        ):
            findings.append(Finding("error", "operator_or_test_payload", name, "operator/test payload is shipped"))
        if info.is_dir():
            continue
        data = archive.read(info)
        digests[name] = hashlib.sha256(data).hexdigest()
        for marker in _sensitive_markers(data):
            findings.append(Finding(
                "error", "private_local_or_credential_marker", name,
                f"package bytes contain forbidden marker: {marker}",
            ))
        if name != ALLOWED_ENGINEERING_SCHEMA and (
            b"facman_engineering_play_harness" in data or
            b"FACMAN_ENABLE_ISOLATED_ENGINEERING_EXECUTION" in data
        ):
            findings.append(Finding(
                "error", "compiled_engineering_authority_marker", name,
                "shipping bytes contain operator-only engineering authority",
            ))

    if names != sorted(names):
        findings.append(Finding("error", "zip_order_nondeterministic", "<archive>", "entries are not lexically ordered"))
    for unexpected in sorted(binaries - EXPECTED_BINARIES):
        findings.append(Finding("error", "unexpected_binary", unexpected, "binary is outside the exact package allowlist"))
    for missing in sorted(EXPECTED_BINARIES - binaries):
        findings.append(Finding("error", "missing_binary", missing, "required package binary is absent"))
    for missing in sorted(REQUIRED_LICENSES - seen):
        findings.append(Finding("error", "missing_license", missing, "required licence/notice is absent"))
    return findings, digests


def _toml_string(text: str, key: str) -> str | None:
    match = re.search(rf'(?m)^\s*{re.escape(key)}\s*=\s*"([^"]+)"\s*$', text)
    return match.group(1) if match else None


def _manifest_findings(
    archive: zipfile.ZipFile,
    digests: dict[str, str],
    source_revision: str,
) -> list[Finding]:
    findings: list[Finding] = []
    names = set(archive.namelist())
    required = {
        "manifest/package.v1.toml",
        "manifest/components.v1.json",
        "manifest/sbom.spdx.v2.3.json",
        "manifest/repaired-provider-canary.v1.json",
    }
    for missing in sorted(required - names):
        findings.append(Finding("error", "missing_manifest", missing, "required custody manifest is absent"))
    if required - names:
        return findings

    package = archive.read("manifest/package.v1.toml").decode("utf-8")
    for anchor in (
        "signed = false", "published = false", "source_dirty = false",
        "python_runtime = false", "bundles_factorio_binaries = false",
    ):
        if anchor not in package:
            findings.append(Finding("error", "package_authority_mismatch", "manifest/package.v1.toml", f"missing {anchor}"))
    packaged_revision = _toml_string(package, "source_revision")
    if packaged_revision != source_revision:
        findings.append(Finding(
            "error", "package_source_revision_mismatch", "manifest/package.v1.toml",
            f"package declares {packaged_revision!r}, inspected source is {source_revision}",
        ))

    canary = json.loads(archive.read("manifest/repaired-provider-canary.v1.json"))
    if any(canary.get(key) is not False for key in (
        "release_eligible", "provider_adoption", "signed", "published"
    )):
        findings.append(Finding("error", "canonical_claim_open", "manifest/repaired-provider-canary.v1.json", "release, provider-adoption, signing, and publication authority must remain false"))
    if canary.get("classification") != "noncanonical_engineering_candidate":
        findings.append(Finding("error", "canary_classification_mismatch", "manifest/repaired-provider-canary.v1.json", "explicit canary classification is absent"))
    if canary.get("canonical_provider_pin_unchanged") is not True:
        findings.append(Finding("error", "canonical_pin_claim_mismatch", "manifest/repaired-provider-canary.v1.json", "tracked canonical provider pin must remain unchanged"))
    try:
        workspace = tomllib.loads(
            archive.read("release/index/workspace_lock.v1.toml").decode("utf-8")
        )
    except (KeyError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        findings.append(Finding(
            "error", "canary_workspace_lock_invalid",
            "release/index/workspace_lock.v1.toml", str(exc),
        ))
        workspace = {}
    workspace_components = {
        str(item.get("id", "")): item
        for item in workspace.get("component", [])
        if isinstance(item, dict)
    }
    for provider_id in ("universal_launcher", "universal_setup"):
        component = workspace_components.get(provider_id, {})
        if component.get("pin") != canary.get("source_revisions", {}).get(provider_id):
            findings.append(Finding(
                "error", "canary_provider_revision_mismatch",
                "release/index/workspace_lock.v1.toml",
                f"{provider_id} revision differs from canary custody",
            ))
        if component.get("tree") != canary.get("source_trees", {}).get(provider_id):
            findings.append(Finding(
                "error", "canary_provider_tree_mismatch",
                "release/index/workspace_lock.v1.toml",
                f"{provider_id} tree differs from canary custody",
            ))
        if component.get("required_ref") != canary.get("required_refs", {}).get(provider_id):
            findings.append(Finding(
                "error", "canary_provider_ref_mismatch",
                "release/index/workspace_lock.v1.toml",
                f"{provider_id} ref differs from canary custody",
            ))

    components = json.loads(archive.read("manifest/components.v1.json"))
    component_map = {
        item["destination"]: item for item in components.get("components", [])
        if isinstance(item, dict) and isinstance(item.get("destination"), str)
    }
    for binary in EXPECTED_BINARIES:
        component = component_map.get(binary)
        if component is None:
            findings.append(Finding("error", "binary_missing_from_component_manifest", binary, "shipped binary is not represented"))
        elif component.get("sha256") != digests.get(binary):
            findings.append(Finding("error", "component_digest_mismatch", binary, "component digest differs from ZIP bytes"))

    sbom = json.loads(archive.read("manifest/sbom.spdx.v2.3.json"))
    package_names = {
        item.get("name") for item in sbom.get("packages", []) if isinstance(item, dict)
    }
    for missing in sorted(EXPECTED_SBOM_PACKAGES - package_names):
        findings.append(Finding("error", "sbom_package_missing", missing, "required shipped source component is absent from SBOM"))
    return findings


def _stage_findings(stage_root: Path, zip_digests: dict[str, str]) -> list[Finding]:
    findings: list[Finding] = []
    stage_files = {
        path.relative_to(stage_root).as_posix(): sha256_file(path)
        for path in sorted(stage_root.rglob("*")) if path.is_file()
    }
    for missing in sorted(set(zip_digests) - set(stage_files)):
        findings.append(Finding("error", "stage_file_missing", missing, "ZIP file is absent from stage"))
    for extra in sorted(set(stage_files) - set(zip_digests)):
        findings.append(Finding("error", "stage_file_extra", extra, "stage file is absent from ZIP"))
    for name in sorted(set(stage_files) & set(zip_digests)):
        if stage_files[name] != zip_digests[name]:
            findings.append(Finding("error", "stage_zip_digest_mismatch", name, "stage and ZIP bytes differ"))
    return findings


def inspect(source_root: Path, stage_root: Path | None, zip_path: Path, expected_sha256: str) -> dict[str, object]:
    actual_sha256 = sha256_file(zip_path)
    findings: list[Finding] = []
    source_revision = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=source_root, text=True
    ).strip()
    source_tree = subprocess.check_output(
        ["git", "rev-parse", "HEAD^{tree}"], cwd=source_root, text=True
    ).strip()
    source_dirty = bool(subprocess.check_output(
        ["git", "status", "--porcelain=v1", "--untracked-files=normal"],
        cwd=source_root,
        text=True,
    ).strip())
    if source_dirty:
        findings.append(Finding(
            "error", "source_dirty", "<source>",
            "inspected source has tracked or untracked changes",
        ))
    if actual_sha256 != expected_sha256.lower():
        findings.append(Finding("error", "zip_digest_mismatch", str(zip_path), f"expected {expected_sha256}, got {actual_sha256}"))
    findings.extend(_source_findings(source_root))
    with zipfile.ZipFile(zip_path, "r") as archive:
        archive_findings, digests = _zip_findings(archive)
        findings.extend(archive_findings)
        findings.extend(_manifest_findings(archive, digests, source_revision))
    if stage_root is not None:
        findings.extend(_stage_findings(stage_root, digests))
    errors = [finding for finding in findings if finding.severity == "error"]
    return {
        "schema": "facman.candidate_security_assurance.v1",
        "status": "pass" if not errors else "failed",
        "classification": "noncanonical_candidate_security_assurance_no_release_authority",
        "source": {
            "root": str(source_root),
            "revision": source_revision,
            "tree": source_tree,
            "dirty": source_dirty,
        },
        "candidate": {
            "path": str(zip_path),
            "sha256": actual_sha256,
            "size": zip_path.stat().st_size,
            "stage": str(stage_root) if stage_root is not None else None,
            "files": len(digests),
        },
        "checks": {
            "safe_zip_paths": True,
            "exact_binary_allowlist": sorted(EXPECTED_BINARIES),
            "stage_zip_byte_identity_checked": stage_root is not None,
            "sbom_packages_required": sorted(EXPECTED_SBOM_PACKAGES),
            "unsigned_expected": True,
        },
        "findings": [asdict(finding) for finding in findings],
        "authority": {
            "canonical_release_verified": False,
            "signed": False,
            "published": False,
            "supported": False,
        },
    }


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=ROOT)
    parser.add_argument("--stage-root", type=Path)
    parser.add_argument("--zip", dest="zip_path", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    report = inspect(
        args.source_root.resolve(),
        args.stage_root.resolve() if args.stage_root else None,
        args.zip_path.resolve(),
        args.expected_sha256,
    )
    _write_json(args.output.resolve(), report)
    print(json.dumps({"status": report["status"], "output": str(args.output.resolve())}))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
