# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Build the non-executing Gate 4C preflight evidence record.

This tool is deliberately incapable of issuing a permit or starting Factorio.  It
binds the frozen policy, reviewed artifacts, repositories, standalone executable,
portable instance projections, source evidence, host state, and observer
prerequisites.  Any missing fact is a blocker, never an inferred success.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from types import MappingProxyType
from typing import Any

from tools import play_staged_candidate as STAGED
from tools.play_evidence_resource_spec import (
    build_resource_specification,
    startup_environment_snapshot,
)
from tools.play_evidence_stable_io import (
    EvidenceIo,
    StableIoError,
    file_payload_sha256,
    file_payload_size,
)
from tools.play_verdict_route import (
    CandidateQualificationBinding,
    HERMETIC_VERDICT03,
    PlayVerdictRoute,
    RouteBindingError,
    load_qualification_binding,
    route_by_id,
)

WORK_UNIT = "FACMAN-HERMETIC-STANDALONE-PLAY-VERDICT-03"
POLICY_DIGEST = "6fde31f26d57e23d67c01dd598cb869a4914d11711868b46d4f817709455e7a2"
CANDIDATE_REVISION = "da3e2274a3dc8a5757078b20276a1a6a93084860"
CANDIDATE_MERGE = "e9c1e69fee1ae815f62638db8b7263cb01b70389"
CANDIDATE_CLOSEOUT_MERGE = "7fe12635f7309e4fd709810dd192d43ff920592f"
FINAL_EVIDENCE_DEV = "6f883cd00e7a06b1b804cb7d868d212b83c10952"
UNIVERSAL_LAUNCHER_REVISION = "7bd4425f0c35414f738159b45d8bec42edf70235"
UNIVERSAL_SETUP_REVISION = "3f8489275077347c2918f3bb03614ec6431362ff"
EXPECTED_FACTORIO_VERSION = "2.0.77"
EXPECTED_INSTANCE_ID = "gate-4c-disposable-2-0-77"
EXPECTED_SPEC_DIGEST = "1930126ce9449328c5d333a03c07dcf10234ca337dfe1a563edc213efe24bc28"
EXPECTED_BINDING_DIGEST = "b5a27b41459a9287681894dc9bcd08a2e04c614d754f18f507030738050530a2"
EXPECTED_READINESS_DIGEST = "21c3b86fac164ba3d0f202cf26687f5d1e882cb048d6343b7e0242b68a4bc2d1"
EXPECTED_FACTORIO_SHA256 = "d3bcfca4dbee407d472013b745ce2445d34af6f021aacc5753ee0dac54b56b0b"
EXPECTED_FACMAN_SHA256 = "47ccf1f151eb65daea1ae4d8ff782f48df08bbedd92d9434e5ca6fd86536270a"
EXPECTED_SIGNER = "Wube Software Ltd"
ATTESTATION_SCHEMA = "factorio.gate4c_quiet_host_attestation.v2"
INSTANCE_ATTESTATION_SCHEMA = (
    "factorio.instance_isolated_quiet_host_attestation.v3"
)
WINDOWS_PRINCIPAL_SCHEMA = "factorio.windows_principal_identity.v1"
PENDING_RESTART_SCHEMA = "factorio.windows_pending_restart_observation.v1"
OBSERVER_SELF_TEST_SCHEMA = "factorio.gate4c_observer_self_test.v5"
OBSERVER_PROVIDER_ID = "factorio.play.process-tree-observer"
OBSERVER_PROVIDER_REVISION = "gate4c-etw-file-registry-process.v6"
OBSERVER_PROFILE_RELATIVE_PATH = "tools/gate4c_process_tree_observer.wprp"
OBSERVER_PROFILE_CANONICAL_SHA256 = (
    "df5daf34e8338602922977b15890dad7bf16cac6b667673d9a60c498a4bf6979"
)
OBSERVER_PROFILE_NAME = "FacManGate4CObserver"
OBSERVER_PROFILE_DETAIL_LEVEL = "Verbose"
OBSERVER_PROFILE_LOGGING_MODE = "File"
OBSERVER_PROFILE_BUFFER_SIZE_KB = 1024
OBSERVER_PROFILE_BUFFER_COUNT = 256
OBSERVER_PROFILE_SYSTEM_KEYWORDS = (
    "ProcessThread",
    "DiskIO",
    "FileIO",
    "FileIOInit",
    "Registry",
)
ATTESTATION_MAX_AGE_SECONDS = 600
OBSERVER_SELF_TEST_MAX_AGE_SECONDS = 900
MAX_FUTURE_SKEW_SECONDS = 30
WINDOWS_REPARSE_ATTRIBUTE = 0x400
MAX_SOURCE_PACKAGE_ENTRIES = 50_000
MAX_SOURCE_PACKAGE_UNCOMPRESSED_BYTES = 16 * 1024 * 1024 * 1024
MAX_SOURCE_PACKAGE_EXPANSION_RATIO = 20
MAX_SOURCE_EXECUTABLE_BYTES = 256 * 1024 * 1024
WINDOWS_PERFORMANCE_TOOLKIT_ROOT = Path(
    r"C:\Program Files (x86)\Windows Kits\10\Windows Performance Toolkit"
)
PROVIDER_SCOPED_REVIEWER = re.compile(
    r"^[a-z][a-z0-9._-]{1,63}:[A-Za-z0-9][A-Za-z0-9._@-]{0,127}$"
)
STARTUP_ENVIRONMENT_NAMES = (
    "APPDATA",
    "LOCALAPPDATA",
    "PROGRAMDATA",
    "ProgramFiles",
    "ProgramFiles(x86)",
    "SystemRoot",
    "USERPROFILE",
)
STARTUP_ENVIRONMENT = MappingProxyType(
    {name: os.environ.get(name, "") for name in STARTUP_ENVIRONMENT_NAMES}
)
STARTUP_ENVIRONMENT_RECORD = startup_environment_snapshot(
    STARTUP_ENVIRONMENT
)


class PreflightError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        return None
    return parsed.astimezone(timezone.utc)


def time_window(
    value: Any,
    *,
    now: datetime | None,
    maximum_age_seconds: int,
) -> dict[str, Any]:
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    parsed = parse_utc(value)
    if parsed is None:
        return {
            "valid": False,
            "reason": "timestamp_not_utc",
            "age_seconds": None,
            "expires_at": None,
        }
    age = (current - parsed).total_seconds()
    valid = -MAX_FUTURE_SKEW_SECONDS <= age <= maximum_age_seconds
    reason = (
        "ok"
        if valid
        else "timestamp_materially_in_future"
        if age < -MAX_FUTURE_SKEW_SECONDS
        else "timestamp_expired"
    )
    return {
        "valid": valid,
        "reason": reason,
        "age_seconds": age,
        "expires_at": (parsed + timedelta(seconds=maximum_age_seconds))
        .isoformat()
        .replace("+00:00", "Z"),
    }


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")


def digest_value(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def stable_identity_digest(audit: dict[str, Any]) -> str | None:
    if not audit.get("safe"):
        return None
    return digest_value(
        {
            "device": audit.get("device"),
            "file_id": audit.get("file_id"),
            "kind": audit.get("kind"),
            "size": audit.get("size"),
        }
    )


def is_link_or_reparse(metadata: os.stat_result) -> bool:
    attributes = int(getattr(metadata, "st_file_attributes", 0))
    return stat.S_ISLNK(metadata.st_mode) or bool(attributes & WINDOWS_REPARSE_ATTRIBUTE)


def audit_no_follow(path: Path, *, require_file: bool | None = None) -> dict[str, Any]:
    absolute = Path(os.path.abspath(path))
    if not absolute.exists():
        return {"path": str(absolute), "present": False, "safe": False, "reason": "missing"}
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current = current / part
        try:
            metadata = current.lstat()
        except OSError as exc:
            return {
                "path": str(absolute),
                "present": False,
                "safe": False,
                "reason": f"lstat_failed:{exc}",
            }
        if is_link_or_reparse(metadata):
            return {
                "path": str(absolute),
                "present": True,
                "safe": False,
                "reason": f"link_or_reparse:{current}",
            }
    metadata = absolute.lstat()
    kind = "file" if stat.S_ISREG(metadata.st_mode) else "directory" if stat.S_ISDIR(metadata.st_mode) else "other"
    kind_ok = require_file is None or (require_file and kind == "file") or (not require_file and kind == "directory")
    return {
        "path": str(absolute),
        "present": True,
        "safe": bool(kind_ok),
        "reason": "ok" if kind_ok else f"unexpected_kind:{kind}",
        "kind": kind,
        "size": metadata.st_size,
        "device": metadata.st_dev,
        "file_id": metadata.st_ino,
    }


def sha256_file(path: Path) -> str:
    audit = audit_no_follow(path, require_file=True)
    if not audit["safe"]:
        raise PreflightError(f"unsafe file path: {audit}")
    digest = hashlib.sha256()
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags)
    try:
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    finally:
        os.close(descriptor)
    return digest.hexdigest()


def path_is_within(path: Path, root: Path) -> bool:
    candidate = os.path.normcase(os.path.abspath(path))
    boundary = os.path.normcase(os.path.abspath(root))
    try:
        return os.path.commonpath((candidate, boundary)) == boundary
    except ValueError:
        return False


def safe_zip_member(info: zipfile.ZipInfo) -> bool:
    name = info.filename
    if not name or "\x00" in name or "\\" in name:
        return False
    parsed = PurePosixPath(name)
    if parsed.is_absolute() or any(part in {"", ".", ".."} for part in parsed.parts):
        return False
    if any(":" in part for part in parsed.parts):
        return False
    normalized = parsed.as_posix() + ("/" if info.is_dir() else "")
    if normalized != name:
        return False
    mode = (info.external_attr >> 16) & 0xFFFF
    if mode and stat.S_ISLNK(mode):
        return False
    return not bool(info.flag_bits & 0x1)


def sha256_zip_member(
    archive: zipfile.ZipFile,
    info: zipfile.ZipInfo,
) -> tuple[str, int]:
    if info.file_size > MAX_SOURCE_EXECUTABLE_BYTES:
        raise PreflightError("source package executable exceeds the inspection limit")
    digest = hashlib.sha256()
    observed = 0
    with archive.open(info, "r") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            observed += len(block)
            if observed > MAX_SOURCE_EXECUTABLE_BYTES:
                raise PreflightError(
                    "source package executable exceeded the inspection limit"
                )
            digest.update(block)
    if observed != info.file_size:
        raise PreflightError("source package executable size changed during inspection")
    return digest.hexdigest(), observed


def run(args: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )


def run_json(args: list[str], *, cwd: Path | None = None) -> dict[str, Any]:
    result = run(args, cwd=cwd)
    if result.returncode != 0:
        raise PreflightError(
            f"command failed ({result.returncode}): {args!r}: {result.stderr.strip()}"
        )
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise PreflightError(f"command did not return strict JSON: {args!r}: {exc}") from exc
    if not isinstance(value, dict):
        raise PreflightError(f"command returned a non-object: {args!r}")
    return value


def git_identity(
    path: Path,
    expected: str,
    *,
    required_ancestors: list[str] | None = None,
    required_ref: str | None = None,
) -> dict[str, Any]:
    head = run(["git", "rev-parse", "HEAD"], cwd=path)
    status = run(["git", "status", "--short", "--branch"], cwd=path)
    if head.returncode != 0 or status.returncode != 0:
        return {"path": str(path), "valid": False, "reason": "git_inspection_failed"}
    revision = head.stdout.strip()
    ancestors: dict[str, bool] = {}
    for ancestor in required_ancestors or []:
        result = run(["git", "merge-base", "--is-ancestor", ancestor, revision], cwd=path)
        ancestors[ancestor] = result.returncode == 0
    ref_reachable = None
    if required_ref:
        ref_result = run(
            ["git", "merge-base", "--is-ancestor", revision, required_ref],
            cwd=path,
        )
        ref_reachable = ref_result.returncode == 0
    clean = len(status.stdout.splitlines()[1:]) == 0
    return {
        "path": str(path),
        "revision": revision,
        "expected_revision": expected,
        "exact": revision == expected,
        "required_ancestors": ancestors,
        "required_ref": required_ref,
        "required_ref_reachable": ref_reachable,
        "status": status.stdout.splitlines(),
        "clean": clean,
        "valid": (
            revision == expected
            and clean
            and all(ancestors.values())
            and (ref_reachable is not False)
        ),
    }


def verify_artifact_manifest(
    path: Path,
    *,
    route: PlayVerdictRoute = HERMETIC_VERDICT03,
    qualification: CandidateQualificationBinding | None = None,
) -> dict[str, Any]:
    audit = audit_no_follow(path, require_file=True)
    if not audit["safe"]:
        return {"manifest": audit, "valid": False, "artifacts": []}
    manifest = json.loads(path.read_text(encoding="utf-8"))
    artifacts: list[dict[str, Any]] = []
    valid = (
        manifest.get("schema") == "facman.gate4c_artifact_binding.v1"
        and manifest.get("work_unit") == route.work_unit
        and manifest.get("source_candidate_revision")
        == (
            qualification.factorio_launcher.revision
            if qualification
            else CANDIDATE_REVISION
        )
        and (
            qualification is None
            or manifest.get("qualification_digest")
            == qualification.qualification_digest
        )
        and manifest.get("copy_verified") is True
    )
    expected_qualified_artifacts = (
        qualification.artifact_mapping() if qualification else None
    )
    observed_names: set[str] = set()
    for expected in manifest.get("artifacts", []):
        logical_name = str(expected.get("logical_name", ""))
        if qualification:
            bound = expected_qualified_artifacts.get(logical_name)
            valid = bool(
                valid
                and bound is not None
                and expected.get("sha256") == bound.sha256
                and expected.get("bytes") == bound.size
            )
            observed_names.add(logical_name)
        artifact_path = path.parent / str(expected.get("name", ""))
        artifact_audit = audit_no_follow(artifact_path, require_file=True)
        actual_hash = sha256_file(artifact_path) if artifact_audit["safe"] else None
        actual_size = artifact_path.stat().st_size if artifact_audit["safe"] else None
        matches = actual_hash == expected.get("sha256") and actual_size == expected.get("bytes")
        valid = valid and matches
        artifacts.append(
            {
                "name": expected.get("name"),
                "path": str(artifact_path),
                "sha256": actual_hash,
                "bytes": actual_size,
                "matches_manifest": matches,
                "path_audit": artifact_audit,
            }
        )
    if qualification:
        valid = valid and observed_names == set(expected_qualified_artifacts)
    return {
        "manifest": audit,
        "manifest_sha256": sha256_file(path),
        "source_candidate_revision": manifest.get("source_candidate_revision"),
        "artifacts": artifacts,
        "valid": valid,
    }


def powershell() -> str | None:
    return shutil.which("pwsh") or shutil.which("powershell")


def authenticode(path: Path) -> dict[str, Any]:
    shell = powershell()
    if shell is None or os.name != "nt":
        return {"available": False, "valid": False, "reason": "powershell_or_windows_unavailable"}
    environment = os.environ.copy()
    environment["FACMAN_GATE4C_SIGNATURE_PATH"] = str(path)
    script = (
        "$s=Get-AuthenticodeSignature -LiteralPath $env:FACMAN_GATE4C_SIGNATURE_PATH;"
        "$f=Get-Item -LiteralPath $env:FACMAN_GATE4C_SIGNATURE_PATH;"
        "[pscustomobject]@{status=[string]$s.Status;status_message=$s.StatusMessage;"
        "signer_subject=if($s.SignerCertificate){$s.SignerCertificate.Subject}else{$null};"
        "signer_thumbprint=if($s.SignerCertificate){$s.SignerCertificate.Thumbprint}else{$null};"
        "timestamp_subject=if($s.TimeStamperCertificate){$s.TimeStamperCertificate.Subject}else{$null};"
        "timestamp_thumbprint=if($s.TimeStamperCertificate){$s.TimeStamperCertificate.Thumbprint}else{$null};"
        "file_version=$f.VersionInfo.FileVersion;product_version=$f.VersionInfo.ProductVersion;"
        "product_name=$f.VersionInfo.ProductName;file_description=$f.VersionInfo.FileDescription;"
        "original_filename=$f.VersionInfo.OriginalFilename;internal_name=$f.VersionInfo.InternalName}"
        "|ConvertTo-Json -Compress"
    )
    result = run([shell, "-NoProfile", "-NonInteractive", "-Command", script], env=environment)
    if result.returncode != 0:
        return {"available": True, "valid": False, "reason": result.stderr.strip()}
    try:
        evidence = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return {"available": True, "valid": False, "reason": f"invalid_json:{exc}"}
    evidence["available"] = True
    evidence["signature_valid"] = evidence.get("status") == "Valid"
    evidence["wube_signer_valid"] = EXPECTED_SIGNER in str(
        evidence.get("signer_subject", "")
    )
    evidence["valid"] = bool(
        evidence["signature_valid"] and evidence["wube_signer_valid"]
    )
    return evidence


def executable_tool_identity(path: Path | str | None) -> dict[str, Any]:
    if path is None:
        return {"valid": False, "reason": "tool_unavailable"}
    candidate = Path(path)
    audit = audit_no_follow(candidate, require_file=True)
    if not audit.get("safe"):
        return {"valid": False, "path_audit": audit}
    metadata = authenticode(candidate)
    return {
        "path_audit": audit,
        "stable_identity_digest": stable_identity_digest(audit),
        "sha256": sha256_file(candidate),
        "file_version": metadata.get("file_version"),
        "product_version": metadata.get("product_version"),
        "signature_status": metadata.get("status"),
        "signer_thumbprint": metadata.get("signer_thumbprint"),
        "valid": True,
    }


def observer_tool_paths() -> dict[str, str | None]:
    toolkit = {
        name: WINDOWS_PERFORMANCE_TOOLKIT_ROOT / filename
        for name, filename in (
            ("wpr", "wpr.exe"),
            ("xperf", "xperf.exe"),
            ("wpaexporter", "wpaexporter.exe"),
        )
    }
    if all(path.is_file() for path in toolkit.values()):
        return {name: str(path) for name, path in toolkit.items()}
    return {name: None for name in toolkit}


def observer_toolchain_coherent(paths: dict[str, str | None]) -> bool:
    if not all(paths.values()):
        return False
    parents: set[str] = set()
    for value in paths.values():
        assert value is not None
        text = str(value)
        parent = (
            str(PureWindowsPath(text).parent)
            if "\\" in text or re.match(r"^[A-Za-z]:", text)
            else str(Path(text).parent)
        )
        parents.add(parent.casefold())
    return len(parents) == 1


def canonical_text_sha256(path: Path) -> str:
    content = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(content).hexdigest()


def observer_profile_identity(repo_root: Path) -> dict[str, Any]:
    profile = repo_root / OBSERVER_PROFILE_RELATIVE_PATH
    audit = audit_no_follow(profile, require_file=True)
    actual_sha256 = sha256_file(profile) if audit.get("safe") else None
    canonical_sha256 = (
        canonical_text_sha256(profile) if audit.get("safe") else None
    )
    result: dict[str, Any] = {
        "relative_path": OBSERVER_PROFILE_RELATIVE_PATH,
        "path_audit": audit,
        "sha256": actual_sha256,
        "canonical_sha256": canonical_sha256,
        "expected_canonical_sha256": OBSERVER_PROFILE_CANONICAL_SHA256,
        "name": OBSERVER_PROFILE_NAME,
        "detail_level": OBSERVER_PROFILE_DETAIL_LEVEL,
        "logging_mode": OBSERVER_PROFILE_LOGGING_MODE,
        "buffer_size_kb": OBSERVER_PROFILE_BUFFER_SIZE_KB,
        "buffer_count": OBSERVER_PROFILE_BUFFER_COUNT,
        "system_keywords": list(OBSERVER_PROFILE_SYSTEM_KEYWORDS),
        "valid": False,
    }
    if not audit.get("safe"):
        result["reason"] = "profile_path_unsafe"
        return result
    try:
        root = ET.parse(profile).getroot()
    except (ET.ParseError, OSError) as exc:
        result["reason"] = f"profile_xml_invalid:{exc}"
        return result

    profiles = root.find("Profiles")
    if root.tag != "WindowsPerformanceRecorder" or profiles is None:
        result["reason"] = "profile_root_invalid"
        return result
    collector = profiles.find("./SystemCollector[@Id='FacManGate4CSystemCollector']")
    provider = profiles.find("./SystemProvider[@Id='FacManGate4CSystemProvider']")
    file_profile = profiles.find(
        "./Profile[@Id='FacManGate4CObserver.Verbose.File']"
    )
    memory_profile = profiles.find(
        "./Profile[@Id='FacManGate4CObserver.Verbose.Memory']"
    )
    observed_keywords = (
        [
            item.get("Value")
            for item in provider.findall("./Keywords/Keyword")
        ]
        if provider is not None
        else []
    )
    collector_buffer_size = (
        collector.find("BufferSize").get("Value")
        if collector is not None and collector.find("BufferSize") is not None
        else None
    )
    collector_buffer_count = (
        collector.find("Buffers").get("Value")
        if collector is not None and collector.find("Buffers") is not None
        else None
    )
    file_binding = (
        file_profile.find(
            "./Collectors/SystemCollectorId"
            "[@Value='FacManGate4CSystemCollector']/"
            "SystemProviderId[@Value='FacManGate4CSystemProvider']"
        )
        if file_profile is not None
        else None
    )
    expected_profiles = {
        "FacManGate4CObserver.Verbose.File",
        "FacManGate4CObserver.Verbose.Memory",
    }
    profile_ids = {item.get("Id") for item in profiles.findall("Profile")}
    closed = bool(
        len(profiles.findall("SystemCollector")) == 1
        and len(profiles.findall("SystemProvider")) == 1
        and not profiles.findall("EventCollector")
        and not profiles.findall("EventProvider")
        and profile_ids == expected_profiles
    )
    valid = bool(
        canonical_sha256 == OBSERVER_PROFILE_CANONICAL_SHA256
        and closed
        and collector is not None
        and collector.get("Name") == "NT Kernel Logger"
        and collector_buffer_size == str(OBSERVER_PROFILE_BUFFER_SIZE_KB)
        and collector_buffer_count == str(OBSERVER_PROFILE_BUFFER_COUNT)
        and provider is not None
        and observed_keywords == list(OBSERVER_PROFILE_SYSTEM_KEYWORDS)
        and provider.find("Stacks") is None
        and file_profile is not None
        and file_profile.get("Name") == OBSERVER_PROFILE_NAME
        and file_profile.get("DetailLevel") == OBSERVER_PROFILE_DETAIL_LEVEL
        and file_profile.get("LoggingMode") == OBSERVER_PROFILE_LOGGING_MODE
        and file_binding is not None
        and memory_profile is not None
        and memory_profile.get("Base") == "FacManGate4CObserver.Verbose.File"
        and memory_profile.get("Name") == OBSERVER_PROFILE_NAME
        and memory_profile.get("DetailLevel") == OBSERVER_PROFILE_DETAIL_LEVEL
        and memory_profile.get("LoggingMode") == "Memory"
    )
    result["valid"] = valid
    result["reason"] = "valid" if valid else "profile_contract_mismatch"
    return result


def observer_provider_identity(repo_root: Path) -> dict[str, Any]:
    profile = observer_profile_identity(repo_root)
    valid = profile.get("valid") is True
    return {
        "id": OBSERVER_PROVIDER_ID,
        "revision": OBSERVER_PROVIDER_REVISION,
        "valid": valid,
        "reason": "valid" if valid else "observer_profile_invalid",
        "profile": {
            key: profile.get(key)
            for key in (
                "relative_path",
                "sha256",
                "canonical_sha256",
                "expected_canonical_sha256",
                "name",
                "detail_level",
                "logging_mode",
                "buffer_size_kb",
                "buffer_count",
                "system_keywords",
            )
        },
    }


def repository_tool_identity(repo_root: Path) -> dict[str, Any]:
    revision = run(["git", "rev-parse", "HEAD"], cwd=repo_root)
    status = run(["git", "status", "--short"], cwd=repo_root)
    files: dict[str, Any] = {}
    for relative in (
        "tools/gate4c_verdict_preflight.py",
        "tools/gate4c_observer_self_test.py",
        "tools/gate4c_verdict_session.py",
        "tools/gate4c_verdict_evidence.py",
        "tools/play_verdict_route.py",
        "tools/instance_isolated_verdict_coordinator.py",
        OBSERVER_PROFILE_RELATIVE_PATH,
    ):
        path = repo_root / relative
        audit = audit_no_follow(path, require_file=True)
        files[relative] = {
            "path_audit": audit,
            "sha256": sha256_file(path) if audit.get("safe") else None,
        }
    profile = observer_profile_identity(repo_root)
    valid = (
        revision.returncode == 0
        and status.returncode == 0
        and not status.stdout.strip()
        and all(item["path_audit"].get("safe") for item in files.values())
        and profile.get("valid") is True
    )
    return {
        "facman_tool_commit": revision.stdout.strip() if revision.returncode == 0 else None,
        "worktree_clean": status.returncode == 0 and not status.stdout.strip(),
        "tool_files": files,
        "observer_profile": profile,
        "valid": valid,
    }


def host_session_identity() -> dict[str, Any]:
    shell = powershell()
    if shell is None or os.name != "nt":
        return {"valid": False, "reason": "windows_host_identity_unavailable"}
    script = (
        "$m=(Get-ItemProperty -LiteralPath 'HKLM:\\SOFTWARE\\Microsoft\\Cryptography' "
        "-Name MachineGuid -ErrorAction Stop).MachineGuid;"
        "$b=(Get-CimInstance Win32_OperatingSystem -ErrorAction Stop).LastBootUpTime."
        "ToUniversalTime().ToString('O');"
        "$w=(& powercfg.exe /lastwake 2>&1|Out-String);"
        "[pscustomobject]@{machine_guid=$m;computer_name=$env:COMPUTERNAME;"
        "boot_time=$b;wake_state=$w}"
        "|ConvertTo-Json -Compress"
    )
    result = run([shell, "-NoProfile", "-NonInteractive", "-Command", script])
    if result.returncode != 0:
        return {"valid": False, "reason": result.stderr.strip() or "host_query_failed"}
    try:
        raw = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return {"valid": False, "reason": f"host_query_invalid_json:{exc}"}
    if not all(
        raw.get(key)
        for key in ("machine_guid", "computer_name", "boot_time", "wake_state")
    ):
        return {"valid": False, "reason": "host_query_incomplete"}
    return {
        "provider": "windows.machine-local-session.v1",
        # The raw MachineGuid, computer name, and boot time are deliberately not persisted.
        "machine_binding_id": digest_value(
            {
                "provider": "windows.machine-local.v1",
                "machine_guid": raw["machine_guid"],
                "computer_name": str(raw["computer_name"]).casefold(),
            }
        ),
        "boot_identity": digest_value(
            {
                "provider": "windows.boot-session.v1",
                "machine_guid": raw["machine_guid"],
                "boot_time": raw["boot_time"],
            }
        ),
        "wake_identity": digest_value(
            {
                "provider": "windows.last-wake-observation.v1",
                "machine_guid": raw["machine_guid"],
                "wake_state": raw["wake_state"],
            }
        ),
        "valid": True,
    }


def windows_principal_identity() -> dict[str, Any]:
    """Observe the current token identity without trusting environment text."""

    if os.name != "nt":
        return {
            "schema": WINDOWS_PRINCIPAL_SCHEMA,
            "valid": False,
            "reason": "windows_token_identity_unavailable",
        }
    from ctypes import wintypes

    token_query = 0x0008
    token_user = 1
    token_integrity_level = 25

    class SidAndAttributes(ctypes.Structure):
        _fields_ = [
            ("sid", ctypes.c_void_p),
            ("attributes", wintypes.DWORD),
        ]

    class TokenUser(ctypes.Structure):
        _fields_ = [("user", SidAndAttributes)]

    class TokenMandatoryLabel(ctypes.Structure):
        _fields_ = [("label", SidAndAttributes)]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.GetCurrentProcessId.restype = wintypes.DWORD
    kernel32.ProcessIdToSessionId.argtypes = [
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.ProcessIdToSessionId.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    advapi32.OpenProcessToken.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.HANDLE),
    ]
    advapi32.OpenProcessToken.restype = wintypes.BOOL
    advapi32.GetTokenInformation.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    advapi32.GetTokenInformation.restype = wintypes.BOOL
    advapi32.ConvertSidToStringSidW.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(wintypes.LPWSTR),
    ]
    advapi32.ConvertSidToStringSidW.restype = wintypes.BOOL
    token = wintypes.HANDLE()
    if not advapi32.OpenProcessToken(
        kernel32.GetCurrentProcess(), token_query, ctypes.byref(token)
    ):
        return {
            "schema": WINDOWS_PRINCIPAL_SCHEMA,
            "valid": False,
            "reason": f"open_process_token_failed:{ctypes.get_last_error()}",
        }

    def token_information(info_class: int) -> ctypes.Array[Any]:
        required = wintypes.DWORD()
        advapi32.GetTokenInformation(
            token, info_class, None, 0, ctypes.byref(required)
        )
        if required.value == 0:
            raise OSError(
                ctypes.get_last_error(), "token information size unavailable"
            )
        buffer = ctypes.create_string_buffer(required.value)
        if not advapi32.GetTokenInformation(
            token,
            info_class,
            buffer,
            required,
            ctypes.byref(required),
        ):
            raise OSError(
                ctypes.get_last_error(), "token information unavailable"
            )
        return buffer

    sid_text = wintypes.LPWSTR()
    try:
        user_buffer = token_information(token_user)
        user = ctypes.cast(
            user_buffer, ctypes.POINTER(TokenUser)
        ).contents.user
        if not advapi32.ConvertSidToStringSidW(
            user.sid, ctypes.byref(sid_text)
        ):
            raise OSError(
                ctypes.get_last_error(), "SID conversion unavailable"
            )
        sid = sid_text.value

        integrity_buffer = token_information(token_integrity_level)
        label = ctypes.cast(
            integrity_buffer, ctypes.POINTER(TokenMandatoryLabel)
        ).contents.label
        advapi32.GetSidSubAuthorityCount.restype = ctypes.POINTER(
            ctypes.c_ubyte
        )
        advapi32.GetSidSubAuthorityCount.argtypes = [ctypes.c_void_p]
        advapi32.GetSidSubAuthority.restype = ctypes.POINTER(wintypes.DWORD)
        advapi32.GetSidSubAuthority.argtypes = [
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        count = advapi32.GetSidSubAuthorityCount(label.sid)
        if not count or count.contents.value == 0:
            raise OSError("token integrity SID has no sub-authority")
        rid = advapi32.GetSidSubAuthority(
            label.sid, count.contents.value - 1
        ).contents.value
        if rid < 0x1000:
            integrity = "untrusted"
        elif rid < 0x2000:
            integrity = "low"
        elif rid < 0x3000:
            integrity = "medium"
        elif rid < 0x4000:
            integrity = "high"
        else:
            integrity = "system"

        session_id = wintypes.DWORD()
        process_id = kernel32.GetCurrentProcessId()
        if not kernel32.ProcessIdToSessionId(
            process_id, ctypes.byref(session_id)
        ):
            raise OSError(
                ctypes.get_last_error(), "Windows session ID unavailable"
            )
        core = {
            "schema": WINDOWS_PRINCIPAL_SCHEMA,
            "provider_id": "windows.local-token.v1",
            "principal_sid_digest": hashlib.sha256(
                sid.encode("utf-8")
            ).hexdigest(),
            "windows_session_id": int(session_id.value),
            "integrity": integrity,
            "valid": True,
        }
        return {
            **core,
            "principal_digest": digest_value(core),
        }
    except (AttributeError, OSError, ValueError) as exc:
        return {
            "schema": WINDOWS_PRINCIPAL_SCHEMA,
            "valid": False,
            "reason": f"windows_token_identity_failed:{exc}",
        }
    finally:
        if sid_text:
            kernel32.LocalFree(ctypes.cast(sid_text, ctypes.c_void_p))
        kernel32.CloseHandle(token)


def validate_windows_principal(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    exact = {
        "schema",
        "provider_id",
        "principal_sid_digest",
        "windows_session_id",
        "integrity",
        "principal_digest",
        "valid",
    }
    core = dict(value)
    claimed = core.pop("principal_digest", None)
    return bool(
        set(value) == exact
        and value.get("schema") == WINDOWS_PRINCIPAL_SCHEMA
        and value.get("provider_id") == "windows.local-token.v1"
        and isinstance(value.get("principal_sid_digest"), str)
        and re.fullmatch(r"[0-9a-f]{64}", value["principal_sid_digest"])
        and isinstance(value.get("windows_session_id"), int)
        and not isinstance(value.get("windows_session_id"), bool)
        and value["windows_session_id"] >= 0
        and value.get("integrity")
        in {"untrusted", "low", "medium", "high", "system"}
        and value.get("valid") is True
        and isinstance(claimed, str)
        and digest_value(core) == claimed
    )


def pending_restart_observation() -> dict[str, Any]:
    shell = powershell()
    if shell is None or os.name != "nt":
        return {
            "schema": PENDING_RESTART_SCHEMA,
            "available": False,
            "pending": None,
            "sources": [],
            "valid": False,
        }
    script = (
        "$s=@();"
        "if(Test-Path -LiteralPath "
        "'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Component Based Servicing\\RebootPending')"
        "{$s+='component_based_servicing'};"
        "if(Test-Path -LiteralPath "
        "'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\WindowsUpdate\\Auto Update\\RebootRequired')"
        "{$s+='windows_update'};"
        "$r=(Get-ItemProperty -LiteralPath "
        "'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Session Manager' "
        "-Name PendingFileRenameOperations -ErrorAction SilentlyContinue)."
        "PendingFileRenameOperations;"
        "if($null-ne $r){$s+='pending_file_rename'};"
        "[pscustomobject]@{sources=@($s)}|ConvertTo-Json -Compress"
    )
    result = run([shell, "-NoProfile", "-NonInteractive", "-Command", script])
    if result.returncode != 0:
        return {
            "schema": PENDING_RESTART_SCHEMA,
            "available": False,
            "pending": None,
            "sources": [],
            "valid": False,
            "error_digest": hashlib.sha256(
                result.stderr.encode("utf-8")
            ).hexdigest(),
        }
    try:
        raw = json.loads(result.stdout)
        sources = raw.get("sources", [])
        if isinstance(sources, str):
            sources = [sources]
        sources = sorted(set(str(item) for item in sources))
    except (AttributeError, json.JSONDecodeError, TypeError):
        return {
            "schema": PENDING_RESTART_SCHEMA,
            "available": False,
            "pending": None,
            "sources": [],
            "valid": False,
        }
    core = {
        "schema": PENDING_RESTART_SCHEMA,
        "available": True,
        "pending": bool(sources),
        "sources": sources,
        "valid": True,
    }
    return {**core, "observation_digest": digest_value(core)}


def is_elevated() -> bool:
    if os.name != "nt":
        return os.geteuid() == 0 if hasattr(os, "geteuid") else False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def process_inventory() -> dict[str, Any]:
    shell = powershell()
    if shell is None or os.name != "nt":
        return {"available": False, "processes": [], "quiet": False}
    script = (
        "$names=@('factorio','facman','steam','steamwebhelper');"
        "$p=Get-Process -Name $names -ErrorAction SilentlyContinue|"
        "Select-Object ProcessName,Id,Path;@($p)|ConvertTo-Json -Compress"
    )
    result = run([shell, "-NoProfile", "-NonInteractive", "-Command", script])
    if result.returncode != 0:
        return {"available": True, "processes": [], "quiet": False, "error": result.stderr.strip()}
    value = json.loads(result.stdout or "[]")
    processes = value if isinstance(value, list) else [value]
    processes = sorted(
        processes,
        key=lambda item: (
            str(item.get("ProcessName", "")).casefold(),
            int(item.get("Id", -1)),
            str(item.get("Path", "")).casefold(),
        ),
    )
    return {"available": True, "processes": processes, "quiet": len(processes) == 0}


def host_state_digest(
    session: dict[str, Any],
    processes: dict[str, Any],
    observer_self_test_digest: str | None,
) -> str:
    return digest_value(
        {
            "machine_binding_id": session.get("machine_binding_id"),
            "boot_identity": session.get("boot_identity"),
            "wake_identity": session.get("wake_identity"),
            "process_inventory": processes,
            "observer_self_test_digest": observer_self_test_digest,
        }
    )


def observer_prerequisites(
    self_test_path: Path | None,
    *,
    repo_root: Path,
    session: dict[str, Any],
    now: datetime | None = None,
    route: PlayVerdictRoute = HERMETIC_VERDICT03,
    qualification: CandidateQualificationBinding | None = None,
) -> dict[str, Any]:
    paths = observer_tool_paths()
    wpr = paths["wpr"]
    xperf = paths["xperf"]
    wpa_exporter = paths["wpaexporter"]
    coherent_toolchain = observer_toolchain_coherent(paths)
    recording = None
    status_output = ""
    if wpr:
        status = run([wpr, "-status"])
        status_output = (status.stdout + "\n" + status.stderr).strip()
        recording = "is not recording" not in status_output.lower()
    current_tools = {
        "wpr": executable_tool_identity(wpr),
        "xperf": executable_tool_identity(xperf),
        "wpaexporter": executable_tool_identity(wpa_exporter),
    }
    current_tooling = repository_tool_identity(repo_root)
    self_test: dict[str, Any] | None = None
    validation: dict[str, Any] = {
        "schema": False,
        "work_unit": False,
        "provider": False,
        "candidate_revision": False,
        "elevated": False,
        "time": {"valid": False, "reason": "self_test_missing"},
        "machine_binding": False,
        "boot_identity": False,
        "tooling": False,
        "observer_tools": False,
        "artifacts": False,
        "self_test_digest": False,
        "zero_loss": False,
        "exact_attribution": False,
        "status": False,
    }
    if self_test_path:
        audit = audit_no_follow(self_test_path, require_file=True)
        if audit["safe"]:
            loaded = json.loads(self_test_path.read_text(encoding="utf-8"))
            if not isinstance(loaded, dict):
                loaded = {"status": "invalid", "reason": "self_test_not_object"}
            claimed_digest = loaded.get("self_test_digest")
            digest_core = dict(loaded)
            digest_core.pop("self_test_digest", None)
            artifact_results: dict[str, Any] = {}
            artifact_valid = True
            for name in ("trace", "dump", "stats"):
                expected = loaded.get("artifacts", {}).get(name, {})
                artifact_path = Path(str(expected.get("path", "")))
                artifact_audit = audit_no_follow(artifact_path, require_file=True)
                same_run_root = artifact_path.parent == self_test_path.parent
                actual_hash = (
                    sha256_file(artifact_path) if artifact_audit.get("safe") else None
                )
                matches = bool(
                    artifact_audit.get("safe")
                    and same_run_root
                    and actual_hash == expected.get("sha256")
                )
                artifact_results[name] = {
                    "path_audit": artifact_audit,
                    "same_run_root": same_run_root,
                    "expected_sha256": expected.get("sha256"),
                    "actual_sha256": actual_hash,
                    "valid": matches,
                }
                artifact_valid = artifact_valid and matches
            validation = {
                "schema": loaded.get("schema") == OBSERVER_SELF_TEST_SCHEMA,
                "work_unit": loaded.get("work_unit") == route.work_unit,
                "provider": loaded.get("provider")
                == observer_provider_identity(repo_root),
                "candidate_revision": loaded.get("candidate_revision")
                == (
                    qualification.factorio_launcher.revision
                    if qualification
                    else CANDIDATE_REVISION
                ),
                "elevated": loaded.get("elevated") is True,
                "time": time_window(
                    loaded.get("generated_at"),
                    now=now,
                    maximum_age_seconds=OBSERVER_SELF_TEST_MAX_AGE_SECONDS,
                ),
                "machine_binding": loaded.get("machine_binding_id")
                == session.get("machine_binding_id"),
                "boot_identity": loaded.get("boot_identity")
                == session.get("boot_identity"),
                "tooling": loaded.get("tooling") == current_tooling
                and current_tooling.get("valid") is True,
                "observer_tools": loaded.get("observer_tools") == current_tools
                and all(item.get("valid") for item in current_tools.values()),
                "artifacts": artifact_valid,
                "self_test_digest": claimed_digest == digest_value(digest_core),
                "zero_loss": loaded.get("lost_events") == 0,
                "zero_loss_evidence": (
                    isinstance(loaded.get("loss_evidence"), dict)
                    and loaded["loss_evidence"].get(
                        "active_collector_count_required"
                    )
                    is True
                    and loaded["loss_evidence"].get(
                        "active_collector_events_lost"
                    )
                    == 0
                    and loaded["loss_evidence"].get(
                        "completion_reported_events_lost"
                    )
                    in (None, 0)
                    and loaded["loss_evidence"].get("resolved") is True
                ),
                "exact_attribution": loaded.get("attribution_complete") is True,
                "status": loaded.get("status") == "pass",
            }
            self_test = {
                **loaded,
                "artifact_sha256": sha256_file(self_test_path),
                "path_audit": audit,
                "artifact_validation": artifact_results,
            }
        else:
            self_test = {"status": "invalid", "path_audit": audit}
    self_test_passed = bool(
        self_test
        and all(
            value.get("valid") if key == "time" else value
            for key, value in validation.items()
        )
    )
    return {
        "wpr": wpr,
        "xperf": xperf,
        "wpaexporter": wpa_exporter,
        "toolchain_coherent": coherent_toolchain,
        "tools_available": all([wpr, xperf, wpa_exporter])
        and coherent_toolchain,
        "elevated": is_elevated(),
        "recording_active": recording,
        "status_output": status_output,
        "host_session": session,
        "current_tooling": current_tooling,
        "current_observer_tools": current_tools,
        "self_test": self_test,
        "self_test_validation": validation,
        "self_test_passed": self_test_passed,
        "ready": all([wpr, xperf, wpa_exporter])
        and coherent_toolchain
        and recording is False
        and session.get("valid") is True
        and self_test_passed,
    }


def policy_identity(
    canonical_policy: Path,
    route: PlayVerdictRoute = HERMETIC_VERDICT03,
) -> dict[str, Any]:
    audit = audit_no_follow(canonical_policy, require_file=True)
    if not audit["safe"]:
        return {"path_audit": audit, "valid": False}
    raw = canonical_policy.read_bytes().rstrip()
    computed = hashlib.sha256(raw).hexdigest()
    return {
        "path_audit": audit,
        "computed_digest": computed,
        "expected_digest": route.policy_digest,
        "valid": computed == route.policy_digest,
    }


def exact_factorio_version(signature: dict[str, Any]) -> bool:
    product_version = str(signature.get("product_version") or "").strip()
    file_version = str(signature.get("file_version") or "").strip()
    return product_version == EXPECTED_FACTORIO_VERSION and bool(
        re.fullmatch(rf"{re.escape(EXPECTED_FACTORIO_VERSION)}(?:\.[0-9]+)?", file_version)
    )


def recognized_source_artifact(path: Path, signature: dict[str, Any]) -> bool:
    metadata_names = " ".join(
        str(value or "")
        for value in (
            signature.get("original_filename"),
            signature.get("file_description"),
            signature.get("product_name"),
        )
    ).casefold()
    original = str(signature.get("original_filename") or "").casefold()
    return bool(
        path.suffix.casefold() == ".exe"
        and "factorio" in metadata_names
        and ("setup" in metadata_names or "installer" in metadata_names)
        and original != "factorio.exe"
    )


def source_installer_evidence(
    path: Path,
    *,
    audit: dict[str, Any],
    installed_audit: dict[str, Any],
    installed_executable: Path | None,
) -> dict[str, Any]:
    signature = authenticode(path)
    artifact_hash = sha256_file(path)
    installed_hash = (
        sha256_file(installed_executable) if installed_audit.get("safe") else None
    )
    source_identity = stable_identity_digest(audit)
    installed_identity = stable_identity_digest(installed_audit)
    artifact_class_valid = recognized_source_artifact(path, signature)
    distinct_identity = bool(
        installed_identity
        and source_identity
        and source_identity != installed_identity
        and artifact_hash != installed_hash
    )
    record = {
        "status": "invalid",
        "evidence_origin": "operator_supplied",
        "source_artifact_kind": (
            "wube_windows_installer" if artifact_class_valid else "unrecognized"
        ),
        "path_audit": audit,
        "stable_identity_digest": source_identity,
        "artifact_sha256": artifact_hash,
        "signature": signature,
        "installed_executable_comparison": {
            "path_audit": installed_audit,
            "stable_identity_digest": installed_identity,
            "sha256": installed_hash,
            "distinct_stable_identity_and_content": distinct_identity,
        },
        "artifact_class_valid": artifact_class_valid,
        "exact_version": exact_factorio_version(signature),
        "expected_version": EXPECTED_FACTORIO_VERSION,
    }
    record["valid"] = (
        signature.get("valid") is True
        and record["exact_version"]
        and artifact_class_valid
        and distinct_identity
    )
    record["status"] = "verified" if record["valid"] else "invalid"
    record["authentication_evidence_digest"] = digest_value(record)
    return record


def source_package_evidence(
    path: Path,
    *,
    audit: dict[str, Any],
    installed_executable: Path | None,
    installed_audit: dict[str, Any],
    source_member_executable: Path | None,
    task_root: Path | None,
) -> dict[str, Any]:
    artifact_hash = sha256_file(path)
    source_identity = stable_identity_digest(audit)
    installed_identity = stable_identity_digest(installed_audit)
    installed_hash = (
        sha256_file(installed_executable) if installed_audit.get("safe") else None
    )
    package_distinct = bool(
        installed_identity
        and source_identity
        and source_identity != installed_identity
        and artifact_hash != installed_hash
    )
    expected_member = (
        f"Factorio_{EXPECTED_FACTORIO_VERSION}/bin/x64/factorio.exe"
    )
    expected_base = f"Factorio_{EXPECTED_FACTORIO_VERSION}/data/base/info.json"
    expected_space_age = (
        f"Factorio_{EXPECTED_FACTORIO_VERSION}/data/space-age/info.json"
    )
    package_structure: dict[str, Any] = {
        "entry_count": 0,
        "total_uncompressed_bytes": 0,
        "expansion_ratio": None,
        "directory_digest": None,
        "expected_executable_member": expected_member,
        "expected_executable_member_count": 0,
        "unsafe_entry_count": 0,
        "duplicate_entry_count": 0,
        "encrypted_entry_count": 0,
        "base_content_present": False,
        "space_age_content_present": False,
        "content_files_do_not_prove_entitlement": True,
        "valid": False,
    }
    member_hash: str | None = None
    member_size: int | None = None
    package_reason = "package_not_inspected"
    try:
        with zipfile.ZipFile(path, "r") as archive:
            entries = archive.infolist()
            directory_records: list[dict[str, Any]] = []
            names: dict[str, int] = {}
            unsafe = 0
            encrypted = 0
            total_uncompressed = 0
            expected_infos: list[zipfile.ZipInfo] = []
            for info in entries:
                folded = info.filename.casefold()
                names[folded] = names.get(folded, 0) + 1
                if not safe_zip_member(info):
                    unsafe += 1
                if info.flag_bits & 0x1:
                    encrypted += 1
                total_uncompressed += info.file_size
                if info.filename == expected_member:
                    expected_infos.append(info)
                directory_records.append(
                    {
                        "name": info.filename,
                        "size": info.file_size,
                        "compressed_size": info.compress_size,
                        "crc32": f"{info.CRC:08x}",
                        "compression": info.compress_type,
                        "flags": info.flag_bits,
                        "external_attributes": info.external_attr,
                    }
                )
            duplicates = sum(count - 1 for count in names.values() if count > 1)
            expansion_ratio = total_uncompressed / max(audit.get("size", 0), 1)
            package_structure.update(
                {
                    "entry_count": len(entries),
                    "total_uncompressed_bytes": total_uncompressed,
                    "expansion_ratio": expansion_ratio,
                    "directory_digest": digest_value(
                        sorted(
                            directory_records,
                            key=lambda item: (
                                str(item["name"]).casefold(),
                                str(item["name"]),
                            ),
                        )
                    ),
                    "expected_executable_member_count": len(expected_infos),
                    "unsafe_entry_count": unsafe,
                    "duplicate_entry_count": duplicates,
                    "encrypted_entry_count": encrypted,
                    "base_content_present": names.get(expected_base.casefold(), 0) == 1,
                    "space_age_content_present": (
                        names.get(expected_space_age.casefold(), 0) == 1
                    ),
                }
            )
            structure_valid = (
                0 < len(entries) <= MAX_SOURCE_PACKAGE_ENTRIES
                and total_uncompressed <= MAX_SOURCE_PACKAGE_UNCOMPRESSED_BYTES
                and expansion_ratio <= MAX_SOURCE_PACKAGE_EXPANSION_RATIO
                and unsafe == 0
                and duplicates == 0
                and encrypted == 0
                and len(expected_infos) == 1
                and package_structure["base_content_present"]
            )
            if structure_valid:
                member_hash, member_size = sha256_zip_member(
                    archive, expected_infos[0]
                )
                package_reason = "ok"
            else:
                package_reason = "source_package_structure_invalid"
            package_structure["valid"] = structure_valid
    except (
        OSError,
        RuntimeError,
        NotImplementedError,
        PreflightError,
        zipfile.BadZipFile,
        zipfile.LargeZipFile,
    ) as exc:
        package_reason = f"source_package_inspection_failed:{type(exc).__name__}"

    member_audit = (
        audit_no_follow(source_member_executable, require_file=True)
        if source_member_executable is not None
        else {"safe": False, "reason": "source_package_member_inspection_required"}
    )
    member_within_task = bool(
        source_member_executable is not None
        and task_root is not None
        and path_is_within(source_member_executable, task_root)
    )
    inspected_member_hash = (
        sha256_file(source_member_executable) if member_audit.get("safe") else None
    )
    member_signature = (
        authenticode(source_member_executable)
        if member_audit.get("safe") and member_within_task
        else {
            "available": False,
            "valid": False,
            "reason": (
                "source_package_member_outside_task_root"
                if member_audit.get("safe")
                else member_audit.get("reason")
            ),
        }
    )
    post_audit = audit_no_follow(path, require_file=True)
    post_artifact_hash = sha256_file(path) if post_audit.get("safe") else None
    package_stable_during_inspection = bool(
        post_audit.get("safe")
        and stable_identity_digest(post_audit) == source_identity
        and post_artifact_hash == artifact_hash
    )
    post_member_audit = (
        audit_no_follow(source_member_executable, require_file=True)
        if source_member_executable is not None
        else {"safe": False, "reason": "source_package_member_inspection_required"}
    )
    post_member_hash = (
        sha256_file(source_member_executable)
        if post_member_audit.get("safe")
        else None
    )
    member_stable_during_inspection = bool(
        member_audit.get("safe")
        and post_member_audit.get("safe")
        and stable_identity_digest(member_audit)
        == stable_identity_digest(post_member_audit)
        and inspected_member_hash == post_member_hash
    )
    inspection_matches_package = bool(
        member_hash
        and inspected_member_hash
        and member_hash == inspected_member_hash
        and member_size == member_audit.get("size")
    )
    member_matches_installed = bool(
        member_hash and installed_hash and member_hash == installed_hash
    )
    exact_version = exact_factorio_version(member_signature)
    artifact_class_valid = bool(
        package_structure["valid"]
        and package_stable_during_inspection
        and member_within_task
        and member_stable_during_inspection
        and inspection_matches_package
        and member_matches_installed
        and member_signature.get("valid") is True
        and exact_version
    )
    failure_reason = package_reason
    if package_reason == "ok":
        if not package_stable_during_inspection:
            failure_reason = "source_package_changed_during_inspection"
        elif not member_audit.get("safe"):
            failure_reason = str(
                member_audit.get(
                    "reason", "source_package_member_inspection_required"
                )
            )
        elif not member_within_task:
            failure_reason = "source_package_member_outside_task_root"
        elif not member_stable_during_inspection:
            failure_reason = "source_package_member_changed_during_inspection"
        elif not inspection_matches_package:
            failure_reason = "source_package_member_inspection_mismatch"
        elif not member_matches_installed:
            failure_reason = "source_package_member_does_not_match_installed"
        elif member_signature.get("valid") is not True:
            failure_reason = "source_package_member_authentication_failed"
        elif not exact_version:
            failure_reason = "source_package_member_version_mismatch"
    record = {
        "status": "invalid",
        "reason": failure_reason,
        "evidence_origin": "operator_supplied",
        "source_artifact_kind": (
            "wube_windows_standalone_package"
            if artifact_class_valid
            else "unrecognized"
        ),
        "path_audit": audit,
        "stable_identity_digest": source_identity,
        "artifact_sha256": artifact_hash,
        "inspection_stability": {
            "post_path_audit": post_audit,
            "post_sha256": post_artifact_hash,
            "stable": package_stable_during_inspection,
        },
        "package_structure": package_structure,
        "source_member": {
            "archive_path": expected_member,
            "sha256": member_hash,
            "bytes": member_size,
            "inspection_copy": {
                "path_audit": member_audit,
                "within_gate4c_task_root": member_within_task,
                "sha256": inspected_member_hash,
                "matches_archive_member": inspection_matches_package,
                "post_path_audit": post_member_audit,
                "post_sha256": post_member_hash,
                "stable": member_stable_during_inspection,
            },
            "signature": member_signature,
        },
        "installed_executable_comparison": {
            "path_audit": installed_audit,
            "stable_identity_digest": installed_identity,
            "sha256": installed_hash,
            "distinct_stable_identity_and_content": package_distinct,
            "package_member_matches_installed_executable": member_matches_installed,
        },
        "artifact_class_valid": artifact_class_valid,
        "exact_version": exact_version,
        "expected_version": EXPECTED_FACTORIO_VERSION,
    }
    record["valid"] = bool(
        artifact_class_valid
        and package_distinct
    )
    record["status"] = "verified" if record["valid"] else "invalid"
    if record["valid"]:
        record["reason"] = "ok"
    record["authentication_evidence_digest"] = digest_value(record)
    return record


def source_package_evidence_native(
    path: Path,
    *,
    audit: dict[str, Any],
    installed_executable: Path | None,
    installed_audit: dict[str, Any],
    source_member_executable: Path | None,
    task_root: Path | None,
    evidence_io: EvidenceIo,
) -> dict[str, Any]:
    """Authenticate package structure through USK and exact extracted bytes."""

    package_result = evidence_io.inspect_zip(path)
    inspection = package_result["payload"]["inspection"]
    entries = inspection.get("entries", [])
    source = inspection.get("source", {})
    expected_member = (
        f"Factorio_{EXPECTED_FACTORIO_VERSION}/bin/x64/factorio.exe"
    )
    expected_base = (
        f"Factorio_{EXPECTED_FACTORIO_VERSION}/data/base/info.json"
    )
    expected_space_age = (
        f"Factorio_{EXPECTED_FACTORIO_VERSION}/data/space-age/info.json"
    )
    names = [
        item.get("normalized_path")
        for item in entries
        if isinstance(item, dict)
    ]
    expected_entries = [
        item
        for item in entries
        if isinstance(item, dict)
        and item.get("normalized_path") == expected_member
        and item.get("entry_type") == "file"
    ]
    artifact_hash = str(source.get("sha256", ""))
    artifact_size = int(source.get("size_bytes", 0))
    source_file = evidence_io.inspect_file(path)["payload"]["file"]
    source_file_hash = str(source_file.get("content_sha256", ""))
    source_file_size = int(source_file.get("bytes_read", 0))
    source_inspection_stable = bool(
        source_file.get("identity_stable")
        and source_file_hash == artifact_hash
        and source_file_size == artifact_size
    )
    source_identity = digest_value(source_file["before_identity"])
    installed_file = (
        evidence_io.inspect_file(installed_executable)["payload"]["file"]
        if installed_executable is not None and installed_audit.get("safe")
        else None
    )
    installed_hash = (
        str(installed_file["content_sha256"])
        if installed_file is not None
        else None
    )
    installed_identity = (
        digest_value(installed_file["before_identity"])
        if installed_file is not None
        else None
    )
    exact_member_result = evidence_io.inspect_exact_member(
        path, expected_member
    )
    exact_member = exact_member_result["payload"]["member"]
    exact_member_inspection = exact_member_result["payload"][
        "archive_inspection"
    ]
    exact_member_hash = str(exact_member.get("content_sha256", ""))
    exact_member_size = int(exact_member.get("size", 0))
    exact_member_source = exact_member_inspection.get("source", {})
    exact_member_source_stable = bool(
        exact_member_source.get("sha256") == artifact_hash
        and exact_member_source.get("size_bytes") == artifact_size
        and exact_member_inspection.get("entry_set_digest")
        == inspection.get("entry_set_digest")
    )
    member_audit = (
        audit_no_follow(source_member_executable, require_file=True)
        if source_member_executable is not None
        else {
            "safe": False,
            "reason": "source_package_member_inspection_required",
        }
    )
    member_within_task = bool(
        source_member_executable is not None
        and task_root is not None
        and path_is_within(source_member_executable, task_root)
    )
    member_file = (
        evidence_io.inspect_file(source_member_executable)["payload"]["file"]
        if source_member_executable is not None and member_audit.get("safe")
        else None
    )
    inspection_copy_hash = (
        str(member_file["content_sha256"]) if member_file is not None else None
    )
    inspection_copy_size = (
        int(member_file["bytes_read"]) if member_file is not None else None
    )
    member_signature = (
        authenticode(source_member_executable)
        if source_member_executable is not None
        and member_audit.get("safe")
        and member_within_task
        else {
            "available": False,
            "valid": False,
            "reason": "source_package_member_inspection_required",
        }
    )
    total_uncompressed = int(
        inspection.get("totals", {}).get("uncompressed_bytes", 0)
    )
    package_structure = {
        "entry_count": len(entries),
        "total_uncompressed_bytes": total_uncompressed,
        "expansion_ratio": total_uncompressed / max(artifact_size, 1),
        "directory_digest": inspection.get("entry_set_digest"),
        "expected_executable_member": expected_member,
        "expected_executable_member_count": len(expected_entries),
        "unsafe_entry_count": len(inspection.get("problems", [])),
        "duplicate_entry_count": 0,
        "encrypted_entry_count": 0,
        "base_content_present": names.count(expected_base) == 1,
        "space_age_content_present": names.count(expected_space_age) == 1,
        "content_files_do_not_prove_entitlement": True,
        "provider": "universal-setup.archive-inspection.v1",
        "valid": bool(
            inspection.get("status") == "pass"
            and source_inspection_stable
            and exact_member_source_stable
            and len(expected_entries) == 1
            and exact_member_size
            == expected_entries[0].get("uncompressed_size")
            and re.fullmatch(r"[0-9a-f]{64}", exact_member_hash) is not None
            and names.count(expected_base) == 1
            and 0 < len(entries) <= MAX_SOURCE_PACKAGE_ENTRIES
            and artifact_size <= 8 * 1024 * 1024 * 1024
            and total_uncompressed
            <= MAX_SOURCE_PACKAGE_UNCOMPRESSED_BYTES
            and total_uncompressed / max(artifact_size, 1)
            <= MAX_SOURCE_PACKAGE_EXPANSION_RATIO
        ),
    }
    member_matches_installed = bool(
        exact_member_hash
        and installed_hash
        and exact_member_hash == installed_hash
    )
    inspection_copy_matches_archive = bool(
        inspection_copy_hash
        and inspection_copy_hash == exact_member_hash
        and inspection_copy_size == exact_member_size
    )
    exact_version = exact_factorio_version(member_signature)
    artifact_class_valid = bool(
        package_structure["valid"]
        and member_file is not None
        and member_within_task
        and member_matches_installed
        and inspection_copy_matches_archive
        and member_signature.get("valid") is True
        and exact_version
    )
    package_distinct = bool(
        source_identity
        and installed_identity
        and source_identity != installed_identity
        and artifact_hash != installed_hash
    )
    record: dict[str, Any] = {
        "status": "verified" if artifact_class_valid and package_distinct else "invalid",
        "reason": "ok" if artifact_class_valid and package_distinct else "native_package_authentication_failed",
        "evidence_origin": "operator_supplied",
        "source_artifact_kind": (
            "wube_windows_standalone_package"
            if artifact_class_valid
            else "unrecognized"
        ),
        "path_audit": audit,
        "stable_identity_digest": source_identity,
        "artifact_sha256": artifact_hash,
        "inspection_stability": {
            "post_path_audit": audit,
            "post_sha256": source_file_hash,
            "stable": source_inspection_stable,
            "native_result_digest": package_result["record_digest"],
        },
        "package_structure": package_structure,
        "source_member": {
            "archive_path": expected_member,
            "sha256": exact_member_hash,
            "bytes": exact_member_size,
            "native_result_digest": exact_member_result["record_digest"],
            "inspection_copy": {
                "path_audit": member_audit,
                "within_gate4c_task_root": member_within_task,
                "sha256": inspection_copy_hash,
                "matches_archive_member": inspection_copy_matches_archive,
                "post_path_audit": member_audit,
                "post_sha256": inspection_copy_hash,
                "stable": bool(
                    member_file and member_file["identity_stable"]
                ),
            },
            "signature": member_signature,
        },
        "installed_executable_comparison": {
            "path_audit": installed_audit,
            "stable_identity_digest": installed_identity,
            "sha256": installed_hash,
            "distinct_stable_identity_and_content": package_distinct,
            "package_member_matches_installed_executable": (
                member_matches_installed
            ),
        },
        "artifact_class_valid": artifact_class_valid,
        "exact_version": exact_version,
        "expected_version": EXPECTED_FACTORIO_VERSION,
        "valid": bool(artifact_class_valid and package_distinct),
    }
    record["authentication_evidence_digest"] = digest_value(record)
    return record


def source_evidence(
    path: Path | None,
    installed_executable: Path | None = None,
    *,
    source_member_executable: Path | None = None,
    task_root: Path | None = None,
    evidence_io: EvidenceIo | None = None,
) -> dict[str, Any]:
    if path is None:
        return {
            "status": "missing",
            "valid": False,
            "reason": "operator_supplied_authenticated_wube_source_required",
        }
    audit = audit_no_follow(path, require_file=True)
    if not audit["safe"]:
        return {"status": "invalid", "valid": False, "path_audit": audit}
    installed_audit = (
        audit_no_follow(installed_executable, require_file=True)
        if installed_executable is not None
        else {"safe": False}
    )
    if path.suffix.casefold() == ".zip":
        if evidence_io is not None:
            return source_package_evidence_native(
                path,
                audit=audit,
                installed_executable=installed_executable,
                installed_audit=installed_audit,
                source_member_executable=source_member_executable,
                task_root=task_root,
                evidence_io=evidence_io,
            )
        return source_package_evidence(
            path,
            audit=audit,
            installed_executable=installed_executable,
            installed_audit=installed_audit,
            source_member_executable=source_member_executable,
            task_root=task_root,
        )
    if source_member_executable is not None:
        return {
            "status": "invalid",
            "valid": False,
            "reason": "source_member_only_valid_for_source_package",
            "path_audit": audit,
        }
    return source_installer_evidence(
        path,
        audit=audit,
        installed_audit=installed_audit,
        installed_executable=installed_executable,
    )


def factorio_evidence(
    path: Path,
    qualification: CandidateQualificationBinding | None = None,
    evidence_io: EvidenceIo | None = None,
) -> dict[str, Any]:
    audit = audit_no_follow(path, require_file=True)
    if not audit["safe"]:
        return {"valid": False, "path_audit": audit}
    signature = authenticode(path)
    native_file = (
        evidence_io.inspect_file(path)
        if evidence_io is not None
        else None
    )
    actual_hash = (
        file_payload_sha256(native_file)
        if native_file is not None
        else sha256_file(path)
    )
    expected_sha256 = (
        qualification.factorio_sha256
        if qualification
        else EXPECTED_FACTORIO_SHA256
    )
    expected_signer = (
        qualification.factorio_signer
        if qualification
        else EXPECTED_SIGNER
    )
    valid = (
        actual_hash == expected_sha256
        and signature.get("valid") is True
        and expected_signer in str(signature.get("signer_subject") or "")
        and exact_factorio_version(signature)
    )
    return {
        "path_audit": audit,
        "stable_identity_digest": (
            digest_value(
                native_file["payload"]["file"]["before_identity"]
            )
            if native_file is not None
            else stable_identity_digest(audit)
        ),
        "sha256": actual_hash,
        "expected_sha256": expected_sha256,
        "signature": signature,
        "expected_version": EXPECTED_FACTORIO_VERSION,
        "valid": valid,
    }


def instance_evidence(
    facman: Path,
    workspace: Path,
    instance_id: str,
    qualification: CandidateQualificationBinding | None = None,
    *,
    staged_instance: dict[str, Any] | None = None,
    allow_unbound_runtime_digests: bool = False,
) -> dict[str, Any]:
    if staged_instance is not None and allow_unbound_runtime_digests:
        raise PreflightError(
            "Instance evidence cannot be both staged-bound and unbound"
        )
    prefix = [str(facman), "--workspace", str(workspace)]
    inspection = run_json(prefix + ["instances", "inspect", instance_id, "--json"])
    description = run_json(prefix + ["instances", "describe", instance_id, "--intent", "menu", "--json"])
    readiness = run_json(prefix + ["instances", "readiness", instance_id, "--intent", "menu", "--json"])
    launch = run_json(prefix + ["launch", "plan", instance_id, "--preflight", "--json"])
    expected_blockers = {"real_play_gate_not_passed"}
    blocker_codes = {str(item.get("code")) for item in readiness.get("blockers", [])}
    plan_args = launch.get("args", [])
    expected_instance_id = (
        qualification.instance_id
        if qualification
        else EXPECTED_INSTANCE_ID
    )
    expected_spec_digest = (
        qualification.instance_spec_digest
        if qualification
        else EXPECTED_SPEC_DIGEST
    )
    if staged_instance is not None:
        staged_identity_valid = (
            set(staged_instance)
            == {
                "instance_id",
                "spec_digest",
                "binding_digest",
                "readiness_digest",
            }
            and staged_instance.get("instance_id")
            == expected_instance_id
            and staged_instance.get("spec_digest")
            == expected_spec_digest
            and all(
                isinstance(staged_instance.get(key), str)
                and re.fullmatch(
                    r"[0-9a-f]{64}", staged_instance[key]
                )
                is not None
                for key in (
                    "spec_digest",
                    "binding_digest",
                    "readiness_digest",
                )
            )
        )
        expected_binding_digest = staged_instance.get(
            "binding_digest"
        )
        expected_readiness_digest = staged_instance.get(
            "readiness_digest"
        )
    elif allow_unbound_runtime_digests:
        staged_identity_valid = qualification is not None
        expected_binding_digest = description.get(
            "instance_binding", {}
        ).get("binding_digest")
        expected_readiness_digest = readiness.get("readiness_digest")
        staged_identity_valid = bool(
            staged_identity_valid
            and isinstance(expected_binding_digest, str)
            and re.fullmatch(
                r"[0-9a-f]{64}", expected_binding_digest
            )
            is not None
            and isinstance(expected_readiness_digest, str)
            and re.fullmatch(
                r"[0-9a-f]{64}", expected_readiness_digest
            )
            is not None
        )
    else:
        staged_identity_valid = True
        expected_binding_digest = (
            qualification.instance_binding_digest
            if qualification
            else EXPECTED_BINDING_DIGEST
        )
        expected_readiness_digest = (
            qualification.instance_readiness_digest
            if qualification
            else EXPECTED_READINESS_DIGEST
        )
    valid = (
        staged_identity_valid
        and inspection.get("instance_id") == expected_instance_id
        and inspection.get("factorio_version") == EXPECTED_FACTORIO_VERSION
        and inspection.get("modset_status") == "present"
        and inspection.get("save_count") == 0
        and description.get("instance_spec", {}).get("spec_digest")
        == expected_spec_digest
        and description.get("instance_binding", {}).get("binding_digest")
        == expected_binding_digest
        and readiness.get("readiness_digest")
        == expected_readiness_digest
        and readiness.get("launch_intent") == "menu"
        and blocker_codes == expected_blockers
        and readiness.get("execution_started") is False
        and readiness.get("permit_issued") is False
        and launch.get("status") == "pass"
        and launch.get("started") is False
        and launch.get("executable")
        and len(plan_args) == 4
        and plan_args[0] == "--config"
        and plan_args[2] == "--mod-directory"
    )
    return {
        "inspection": inspection,
        "description": description,
        "readiness": readiness,
        "launch_preflight": launch,
        "expected_product_blockers": sorted(expected_blockers),
        "valid": bool(valid),
    }


def operator_attestation(
    path: Path | None,
    *,
    machine_binding_id: str | None,
    boot_identity: str | None,
    observer_self_test_digest: str | None,
    observer_generated_at: str | None,
    current_host_state_digest: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    required_true = {
        "pending_restart_cleared",
        "steam_closed",
        "unrelated_factorio_facman_closed",
        "install_backup_sync_activity_paused",
        "sleep_and_restart_prevented_for_run",
    }
    if path is None:
        return {
            "status": "missing",
            "valid": False,
            "required_true": sorted(required_true),
        }
    audit = audit_no_follow(path, require_file=True)
    if not audit["safe"]:
        return {"status": "invalid", "valid": False, "path_audit": audit}
    value = json.loads(path.read_text(encoding="utf-8"))
    exact_keys = required_true | {
        "schema",
        "attested_at",
        "reviewer_id",
        "machine_binding_id",
        "boot_identity",
        "observer_self_test_digest",
        "host_state_digest",
    }
    window = time_window(
        value.get("attested_at") if isinstance(value, dict) else None,
        now=now,
        maximum_age_seconds=ATTESTATION_MAX_AGE_SECONDS,
    )
    reviewer_id = value.get("reviewer_id") if isinstance(value, dict) else None
    attested_time = parse_utc(value.get("attested_at") if isinstance(value, dict) else None)
    observer_time = parse_utc(observer_generated_at)
    sequence_valid = bool(
        attested_time is not None
        and observer_time is not None
        and observer_time <= attested_time
    )
    bindings_valid = bool(
        isinstance(value, dict)
        and value.get("machine_binding_id") == machine_binding_id
        and value.get("boot_identity") == boot_identity
        and value.get("observer_self_test_digest") == observer_self_test_digest
        and value.get("host_state_digest") == current_host_state_digest
    )
    valid = (
        isinstance(value, dict)
        and set(value) == exact_keys
        and value.get("schema") == ATTESTATION_SCHEMA
        and window["valid"]
        and isinstance(reviewer_id, str)
        and PROVIDER_SCOPED_REVIEWER.fullmatch(reviewer_id) is not None
        and sequence_valid
        and bindings_valid
        and all(value.get(key) is True for key in required_true)
    )
    return {
        "status": "verified" if valid else "invalid",
        "valid": valid,
        "path_audit": audit,
        "artifact_sha256": sha256_file(path),
        "attestation_digest": digest_value(value),
        "attested_at": value.get("attested_at") if isinstance(value, dict) else None,
        "reviewer_id": reviewer_id,
        "time_window": window,
        "bindings_valid": bindings_valid,
        "after_observer_self_test": sequence_valid,
        "maximum_age_seconds": ATTESTATION_MAX_AGE_SECONDS,
        "baseline_must_begin_before": window.get("expires_at"),
        "required_true": sorted(required_true),
    }


INSTANCE_OPERATOR_CLAIMS = frozenset(
    {
        "backup_and_sync_activity_paused",
        "no_unrelated_file_copy_activity",
        "operator_will_not_suspend_or_restart",
    }
)


def build_instance_operator_attestation(
    *,
    attested_at: str,
    reviewer_principal: dict[str, Any],
    machine_binding_id: str,
    boot_identity: str,
    observer_self_test_digest: str,
    host_state_digest_value: str,
    processes: dict[str, Any],
    pending_restart: dict[str, Any],
    operator_claims: dict[str, bool],
) -> dict[str, Any]:
    if (
        not validate_windows_principal(reviewer_principal)
        or set(operator_claims) != INSTANCE_OPERATOR_CLAIMS
        or not all(isinstance(item, bool) for item in operator_claims.values())
    ):
        raise PreflightError(
            "instance-isolated operator attestation inputs are not closed"
        )
    record: dict[str, Any] = {
        "schema": INSTANCE_ATTESTATION_SCHEMA,
        "attested_at": attested_at,
        "reviewer_principal": reviewer_principal,
        "machine_observations": {
            "machine_binding_id": machine_binding_id,
            "boot_identity": boot_identity,
            "observer_self_test_digest": observer_self_test_digest,
            "host_state_digest": host_state_digest_value,
            "process_inventory_digest": digest_value(processes),
            "process_inventory_quiet": processes.get("quiet") is True,
            "pending_restart_observation_digest": digest_value(
                pending_restart
            ),
            "pending_restart_cleared": bool(
                pending_restart.get("valid") is True
                and pending_restart.get("pending") is False
            ),
        },
        "operator_attestations": dict(sorted(operator_claims.items())),
        "power_request": {
            "provider": "windows.set_thread_execution_state.v1",
            "required_before_permit": True,
            "claimed_active": False,
        },
    }
    record["attestation_digest"] = digest_value(record)
    return record


def instance_operator_attestation(
    path: Path | None,
    *,
    machine_binding_id: str | None,
    boot_identity: str | None,
    observer_self_test_digest: str | None,
    observer_generated_at: str | None,
    current_host_state_digest: str,
    reviewer_principal: dict[str, Any],
    processes: dict[str, Any],
    pending_restart: dict[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    if path is None:
        return {
            "status": "missing",
            "valid": False,
            "required_operator_attestations": sorted(
                INSTANCE_OPERATOR_CLAIMS
            ),
        }
    audit = audit_no_follow(path, require_file=True)
    if not audit["safe"]:
        return {"status": "invalid", "valid": False, "path_audit": audit}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"status": "invalid", "valid": False, "path_audit": audit}
    exact = {
        "schema",
        "attested_at",
        "reviewer_principal",
        "machine_observations",
        "operator_attestations",
        "power_request",
        "attestation_digest",
    }
    machine = (
        value.get("machine_observations")
        if isinstance(value, dict)
        else None
    )
    claims = (
        value.get("operator_attestations")
        if isinstance(value, dict)
        else None
    )
    power = value.get("power_request") if isinstance(value, dict) else None
    principal = (
        value.get("reviewer_principal")
        if isinstance(value, dict)
        else None
    )
    window = time_window(
        value.get("attested_at") if isinstance(value, dict) else None,
        now=now,
        maximum_age_seconds=ATTESTATION_MAX_AGE_SECONDS,
    )
    attested_time = parse_utc(
        value.get("attested_at") if isinstance(value, dict) else None
    )
    observer_time = parse_utc(observer_generated_at)
    sequence_valid = bool(
        attested_time is not None
        and observer_time is not None
        and observer_time <= attested_time
    )
    machine_exact = {
        "machine_binding_id",
        "boot_identity",
        "observer_self_test_digest",
        "host_state_digest",
        "process_inventory_digest",
        "process_inventory_quiet",
        "pending_restart_observation_digest",
        "pending_restart_cleared",
    }
    bindings_valid = bool(
        isinstance(machine, dict)
        and set(machine) == machine_exact
        and machine.get("machine_binding_id") == machine_binding_id
        and machine.get("boot_identity") == boot_identity
        and machine.get("observer_self_test_digest")
        == observer_self_test_digest
        and machine.get("host_state_digest") == current_host_state_digest
        and machine.get("process_inventory_digest")
        == digest_value(processes)
        and machine.get("process_inventory_quiet")
        is (processes.get("quiet") is True)
        and machine.get("pending_restart_observation_digest")
        == digest_value(pending_restart)
        and machine.get("pending_restart_cleared")
        is bool(
            pending_restart.get("valid") is True
            and pending_restart.get("pending") is False
        )
    )
    core = dict(value) if isinstance(value, dict) else {}
    claimed = core.pop("attestation_digest", None)
    valid = bool(
        isinstance(value, dict)
        and set(value) == exact
        and value.get("schema") == INSTANCE_ATTESTATION_SCHEMA
        and window["valid"]
        and sequence_valid
        and validate_windows_principal(principal)
        and principal == reviewer_principal
        and principal.get("integrity") == "medium"
        and bindings_valid
        and processes.get("quiet") is True
        and pending_restart.get("valid") is True
        and pending_restart.get("pending") is False
        and isinstance(claims, dict)
        and set(claims) == INSTANCE_OPERATOR_CLAIMS
        and all(claims.get(key) is True for key in INSTANCE_OPERATOR_CLAIMS)
        and power
        == {
            "provider": "windows.set_thread_execution_state.v1",
            "required_before_permit": True,
            "claimed_active": False,
        }
        and isinstance(claimed, str)
        and re.fullmatch(r"[0-9a-f]{64}", claimed)
        and digest_value(core) == claimed
    )
    return {
        "status": "verified" if valid else "invalid",
        "valid": valid,
        "path_audit": audit,
        "artifact_sha256": sha256_file(path),
        "attestation_digest": claimed,
        "attested_at": (
            value.get("attested_at") if isinstance(value, dict) else None
        ),
        "reviewer_principal": principal,
        "machine_observations": machine,
        "operator_attestations": claims,
        "power_request": power,
        "time_window": window,
        "bindings_valid": bindings_valid,
        "after_observer_self_test": sequence_valid,
        "maximum_age_seconds": ATTESTATION_MAX_AGE_SECONDS,
        "baseline_must_begin_before": window.get("expires_at"),
        "required_operator_attestations": sorted(
            INSTANCE_OPERATOR_CLAIMS
        ),
    }


def add_blocker(blockers: list[dict[str, str]], code: str, detail: str) -> None:
    blockers.append({"code": code, "detail": detail})


def build_preflight(
    args: argparse.Namespace,
    *,
    route: PlayVerdictRoute = HERMETIC_VERDICT03,
    qualification: CandidateQualificationBinding | None = None,
    staged_candidate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if route.route_id != HERMETIC_VERDICT03.route_id and qualification is None:
        raise PreflightError(
            "the selected Play route requires an immutable qualification binding"
        )
    if (
        route.route_id != HERMETIC_VERDICT03.route_id
        and staged_candidate is None
    ):
        raise PreflightError(
            "the selected Play route requires the exact final-workspace "
            "staged candidate binding"
        )
    evidence_io = (
        EvidenceIo(Path(args.evidence_probe))
        if route.route_id != HERMETIC_VERDICT03.route_id
        else None
    )
    if (
        evidence_io is not None
        and (
            not isinstance(getattr(args, "operation_id", None), str)
            or not args.operation_id.startswith(route.operation_prefix)
        )
    ):
        raise PreflightError(
            "instance-isolated preflight requires one exact operation ID"
        )
    now = datetime.now(timezone.utc)
    task_root = Path(args.task_root)
    task_audit = audit_no_follow(task_root, require_file=False)
    if not task_audit["safe"] or task_root.name != route.work_unit:
        raise PreflightError(f"task root is not the exact Gate 4C root: {task_audit}")

    facman_repo = Path(args.repo_root)
    launcher_repo = Path(args.launcher_repo)
    setup_repo = Path(args.setup_repo)
    facman = Path(args.facman)
    workspace = Path(args.workspace)
    if staged_candidate is not None:
        assert qualification is not None
        try:
            staged_candidate = STAGED.parse_staged_candidate(
                staged_candidate,
                task_root=task_root,
                qualification=qualification,
                route=route,
            )
        except STAGED.StagedCandidateError as exc:
            raise PreflightError(str(exc)) from exc
    factorio = Path(args.factorio_exe)

    policy = policy_identity(
        facman_repo / "contracts/generated-index" / route.policy_filename,
        route,
    )
    artifacts = verify_artifact_manifest(
        Path(args.artifact_manifest),
        route=route,
        qualification=qualification,
    )
    if qualification:
        repositories = {
            "facman": git_identity(
                facman_repo,
                qualification.factorio_launcher.revision,
                required_ref=qualification.factorio_launcher.required_ref,
            ),
            "universal_launcher": git_identity(
                launcher_repo,
                qualification.universal_launcher.revision,
                required_ref=qualification.universal_launcher.required_ref,
            ),
            "universal_setup": git_identity(
                setup_repo,
                qualification.universal_setup.revision,
                required_ref=qualification.universal_setup.required_ref,
            ),
        }
    else:
        repositories = {
            "facman": git_identity(
                facman_repo,
                FINAL_EVIDENCE_DEV,
                required_ancestors=[
                    CANDIDATE_REVISION,
                    CANDIDATE_MERGE,
                    CANDIDATE_CLOSEOUT_MERGE,
                    FINAL_EVIDENCE_DEV,
                ],
            ),
            "universal_launcher": git_identity(
                launcher_repo, UNIVERSAL_LAUNCHER_REVISION
            ),
            "universal_setup": git_identity(
                setup_repo, UNIVERSAL_SETUP_REVISION
            ),
        }
        # Gate 4C evidence/tool commits may descend from the exact final dev pin.
        repositories["facman"]["valid"] = all(
            repositories["facman"].get("required_ancestors", {}).values()
        )

    facman_hash = sha256_file(facman) if audit_no_follow(facman, require_file=True)["safe"] else None
    expected_facman_sha256 = (
        qualification.artifact_mapping()["facman"].sha256
        if qualification
        else EXPECTED_FACMAN_SHA256
    )
    facman_artifact = {
        "path": str(facman),
        "sha256": facman_hash,
        "expected_sha256": expected_facman_sha256,
        "valid": facman_hash == expected_facman_sha256,
    }
    executable = factorio_evidence(
        factorio, qualification, evidence_io
    )
    source = source_evidence(
        Path(args.source_artifact) if args.source_artifact else None,
        factorio,
        source_member_executable=(
            Path(args.source_member_executable)
            if args.source_member_executable
            else None
        ),
        task_root=task_root,
        evidence_io=evidence_io,
    )
    instance = instance_evidence(
        facman,
        workspace,
        args.instance_id,
        qualification,
        staged_instance=(
            staged_candidate["instance"]
            if staged_candidate is not None
            else None
        ),
    )
    processes = process_inventory()
    session = host_session_identity()
    principal = (
        windows_principal_identity()
        if route.route_id != HERMETIC_VERDICT03.route_id
        else None
    )
    pending_restart = (
        pending_restart_observation()
        if route.route_id != HERMETIC_VERDICT03.route_id
        else None
    )
    observer = observer_prerequisites(
        Path(args.observer_self_test) if args.observer_self_test else None,
        repo_root=facman_repo,
        session=session,
        now=now,
        route=route,
        qualification=qualification,
    )
    observer_digest = (
        observer.get("self_test", {}).get("self_test_digest")
        if isinstance(observer.get("self_test"), dict)
        else None
    )
    observer_generated_at = (
        observer.get("self_test", {}).get("generated_at")
        if isinstance(observer.get("self_test"), dict)
        else None
    )
    current_host_state = host_state_digest(session, processes, observer_digest)
    if route.route_id == HERMETIC_VERDICT03.route_id:
        attestation = operator_attestation(
            Path(args.operator_attestation)
            if args.operator_attestation
            else None,
            machine_binding_id=session.get("machine_binding_id"),
            boot_identity=session.get("boot_identity"),
            observer_self_test_digest=observer_digest,
            observer_generated_at=observer_generated_at,
            current_host_state_digest=current_host_state,
            now=now,
        )
    else:
        attestation = instance_operator_attestation(
            Path(args.operator_attestation)
            if args.operator_attestation
            else None,
            machine_binding_id=session.get("machine_binding_id"),
            boot_identity=session.get("boot_identity"),
            observer_self_test_digest=observer_digest,
            observer_generated_at=observer_generated_at,
            current_host_state_digest=current_host_state,
            reviewer_principal=principal or {},
            processes=processes,
            pending_restart=pending_restart or {},
            now=now,
        )
    deadlines = [
        parsed
        for parsed in (
            parse_utc(attestation.get("time_window", {}).get("expires_at")),
            parse_utc(observer.get("self_test_validation", {}).get("time", {}).get("expires_at")),
        )
        if parsed is not None
    ]
    baseline_deadline = (
        min(deadlines).isoformat().replace("+00:00", "Z") if deadlines else None
    )
    evidence_probe: dict[str, Any] | None = None
    if evidence_io is not None and qualification is not None:
        probe_result = evidence_io.inspect_file(evidence_io.probe)
        probe_binding = qualification.artifact_mapping()["evidence_probe"]
        evidence_probe = {
            "path": str(evidence_io.probe),
            "sha256": file_payload_sha256(probe_result),
            "size": file_payload_size(probe_result),
            "qualified_sha256": probe_binding.sha256,
            "qualified_size": probe_binding.size,
            "native_result_digest": probe_result["record_digest"],
            "valid": (
                file_payload_sha256(probe_result) == probe_binding.sha256
                and file_payload_size(probe_result) == probe_binding.size
            ),
        }

    blockers: list[dict[str, str]] = []
    if not policy["valid"]:
        add_blocker(blockers, "frozen_policy_mismatch", "The canonical Gate 4A policy digest does not match.")
    if not artifacts["valid"] or not facman_artifact["valid"]:
        add_blocker(blockers, "candidate_artifact_mismatch", "The copied reviewed Gate 4B artifact set is incomplete or changed.")
    if evidence_probe is not None and not evidence_probe["valid"]:
        add_blocker(
            blockers,
            "evidence_probe_mismatch",
            "The native stable evidence-I/O provider differs from qualification.",
        )
    for name, identity in repositories.items():
        if not identity.get("valid"):
            add_blocker(blockers, f"repository_pin_mismatch:{name}", f"{name} does not satisfy its exact Gate 4C pin.")
    if not source["valid"]:
        add_blocker(blockers, "authenticated_source_evidence_missing", "An exact operator-supplied Wube-authenticated source artifact is required; installed files are insufficient.")
    if not executable["valid"]:
        add_blocker(blockers, "factorio_executable_mismatch", "The Factorio executable version, digest, or Wube signature does not match the candidate.")
    if not instance["valid"]:
        add_blocker(blockers, "instance_projection_mismatch", "The disposable instance projections or menu-only launch preflight changed.")
    if not processes.get("quiet"):
        active = sorted({str(item.get("ProcessName", "unknown")) for item in processes.get("processes", [])})
        add_blocker(blockers, "host_not_quiet", f"Protected or competing processes are active: {', '.join(active)}")
    if not session.get("valid"):
        add_blocker(blockers, "host_session_identity_unavailable", "The opaque machine and current boot-session identities could not be established.")
    if (
        route.route_id != HERMETIC_VERDICT03.route_id
        and (
            not validate_windows_principal(principal)
            or principal.get("integrity") != "medium"
        )
    ):
        add_blocker(
            blockers,
            "reviewer_principal_unavailable",
            "The exact medium-integrity Windows token principal and session could not be observed.",
        )
    if (
        route.route_id != HERMETIC_VERDICT03.route_id
        and (
            not isinstance(pending_restart, dict)
            or pending_restart.get("valid") is not True
            or pending_restart.get("pending") is not False
        )
    ):
        add_blocker(
            blockers,
            "pending_restart_or_unknown",
            "Windows reports a pending restart or restart state could not be observed.",
        )
    if not observer.get("tools_available"):
        add_blocker(blockers, "observer_tools_missing", "WPR, XPerf, and WPAExporter are required.")
    if observer.get("recording_active") is not False:
        add_blocker(blockers, "observer_session_busy_or_unknown", "WPR must report no active recording before baseline capture.")
    if not observer.get("self_test_passed"):
        add_blocker(blockers, "observer_self_test_missing_or_stale", "No fresh, exact-machine, exact-tool, gap-free Gate 4C observer self-test is bound.")
    if not attestation.get("valid"):
        add_blocker(blockers, "quiet_host_attestation_missing", "A fresh operator attestation for restart, competing processes, synchronization activity, and sleep prevention is required.")

    resource_specification = (
        build_resource_specification(
            preflight={
                "instance": instance,
                "source_evidence": source,
                "facman_artifact": facman_artifact,
            },
            workspace=workspace,
            operation_id=args.operation_id,
            route=route,
            evidence_io=evidence_io,
            environment_snapshot=STARTUP_ENVIRONMENT_RECORD,
        )
        if evidence_io is not None
        else None
    )
    core: dict[str, Any] = {
        "schema": route.preflight_schema,
        "canonicalization_version": "facman.sorted-json.v1",
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "work_unit": route.work_unit,
        "status": "ready" if not blockers else "blocked",
        "authority": {
            "permit_issued": False,
            "process_started": False,
            "real_factorio_execution": False,
            "public_route_available": False,
            "verdict": "unset",
        },
        "task_root": task_audit,
        "policy": policy,
        "repositories": repositories,
        "reviewed_artifacts": artifacts,
        "facman_artifact": facman_artifact,
        "source_evidence": source,
        "factorio_executable": executable,
        "instance": instance,
        "host": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "session_identity": session,
            "process_inventory": processes,
            "host_state_digest": current_host_state,
            **(
                {
                    "reviewer_principal": principal,
                    "pending_restart": pending_restart,
                }
                if route.route_id != HERMETIC_VERDICT03.route_id
                else {}
            ),
        },
        "observer": observer,
        "operator_attestation": attestation,
        "readiness_lease": {
            "attestation_maximum_age_seconds": ATTESTATION_MAX_AGE_SECONDS,
            "observer_self_test_maximum_age_seconds": OBSERVER_SELF_TEST_MAX_AGE_SECONDS,
            "maximum_future_skew_seconds": MAX_FUTURE_SKEW_SECONDS,
            "baseline_must_begin_before": baseline_deadline,
            "requires_full_preflight_rerun_after_expiry_or_host_change": True,
        },
        "blockers": blockers,
        "next_action": (
            "complete_missing_preflight_evidence"
            if blockers
            else "capture_protected_and_writable_baselines_before_any_permit"
        ),
    }
    if evidence_probe is not None and resource_specification is not None:
        core["evidence_probe"] = evidence_probe
        core["resource_specification"] = resource_specification
    if qualification:
        core["qualification_binding"] = {
            "route_id": route.route_id,
            "qualification_digest": qualification.qualification_digest,
        }
        if staged_candidate is not None:
            core["qualification_binding"]["staged_candidate_digest"] = (
                staged_candidate["staged_candidate_digest"]
            )
    core["preflight_digest"] = digest_value(core)
    return core


def write_record(
    path: Path,
    record: dict[str, Any],
    task_root: Path,
    evidence_io: EvidenceIo | None = None,
) -> None:
    absolute = Path(os.path.abspath(path))
    root = Path(os.path.abspath(task_root))
    try:
        absolute.relative_to(root)
    except ValueError as exc:
        raise PreflightError("preflight output must remain under the exact Gate 4C root") from exc
    absolute.parent.mkdir(parents=True, exist_ok=True)
    if evidence_io is not None:
        if absolute.exists():
            raise PreflightError("preflight output already exists")
        evidence_io.write_new_json(absolute, record)
        return
    temporary = absolute.with_name(absolute.name + ".tmp")
    temporary.write_bytes(json.dumps(record, indent=2, ensure_ascii=False, sort_keys=True).encode("utf-8") + b"\n")
    os.replace(temporary, absolute)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Build the non-executing Gate 4C preflight packet.")
    value.add_argument(
        "--route",
        default=HERMETIC_VERDICT03.route_id,
        help="Closed Play verdict route identifier.",
    )
    value.add_argument(
        "--qualification-binding",
        type=Path,
        help=(
            "Immutable remote-only candidate qualification binding. "
            "Required for the instance-isolated revalidation route."
        ),
    )
    value.add_argument(
        "--staged-candidate-binding",
        type=Path,
        help=(
            "Closed final-workspace candidate binding emitted by the "
            "instance-isolated coordinator stage"
        ),
    )
    value.add_argument("--task-root", required=True, type=Path)
    value.add_argument("--repo-root", required=True, type=Path)
    value.add_argument("--launcher-repo", required=True, type=Path)
    value.add_argument("--setup-repo", required=True, type=Path)
    value.add_argument("--artifact-manifest", required=True, type=Path)
    value.add_argument("--facman", required=True, type=Path)
    value.add_argument("--evidence-probe", type=Path)
    value.add_argument("--operation-id")
    value.add_argument("--workspace", required=True, type=Path)
    value.add_argument("--instance-id", default=EXPECTED_INSTANCE_ID)
    value.add_argument("--factorio-exe", required=True, type=Path)
    value.add_argument("--source-artifact", type=Path)
    value.add_argument(
        "--source-member-executable",
        type=Path,
        help=(
            "Task-root inspection copy of the exact signed Factorio executable "
            "inside a portable source package"
        ),
    )
    value.add_argument("--observer-self-test", type=Path)
    value.add_argument("--operator-attestation", type=Path)
    value.add_argument("--out", required=True, type=Path)
    return value


def main() -> int:
    args = parser().parse_args()
    route = route_by_id(args.route)
    qualification = (
        load_qualification_binding(args.qualification_binding, route)
        if args.qualification_binding
        else None
    )
    if route != HERMETIC_VERDICT03 and qualification is None:
        raise PreflightError(
            "the selected Play route requires an immutable qualification binding"
        )
    if route != HERMETIC_VERDICT03 and args.evidence_probe is None:
        raise PreflightError(
            "the selected Play route requires a qualified native evidence probe"
        )
    staged_candidate = None
    if route != HERMETIC_VERDICT03:
        if args.staged_candidate_binding is None:
            raise PreflightError(
                "the selected Play route requires the exact final-workspace "
                "staged candidate binding"
            )
        assert qualification is not None
        try:
            staged_candidate = STAGED.parse_staged_candidate(
                EvidenceIo(args.evidence_probe).read_json(
                    args.staged_candidate_binding
                )["payload"]["document"],
                task_root=args.task_root,
                qualification=qualification,
                route=route,
            )
        except STAGED.StagedCandidateError as exc:
            raise PreflightError(str(exc)) from exc
    record = build_preflight(
        args,
        route=route,
        qualification=qualification,
        staged_candidate=staged_candidate,
    )
    write_record(
        args.out,
        record,
        args.task_root,
        EvidenceIo(args.evidence_probe) if args.evidence_probe else None,
    )
    print(
        f"gate4c-verdict-preflight: {record['status']} "
        f"({len(record['blockers'])} blockers; {record['preflight_digest']})"
    )
    return 0 if record["status"] == "ready" else 3


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        OSError,
        ValueError,
        json.JSONDecodeError,
        PreflightError,
        StableIoError,
        RouteBindingError,
    ) as exc:
        print(f"gate4c-verdict-preflight: {exc}", file=sys.stderr)
        raise SystemExit(2)
