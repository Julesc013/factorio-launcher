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
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any


WORK_UNIT = "FACMAN-HERMETIC-STANDALONE-PLAY-VERDICT-01"
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
EXPECTED_BINDING_DIGEST = "a309925da310a7a5eaa633477ca99a48fd97bc72e18e001b5a627b50edbe121f"
EXPECTED_READINESS_DIGEST = "8b7604d9aead7e7bffdf486d2e6d44365dd32b6e22dc33acd3eaffb3f16ff3ab"
EXPECTED_FACTORIO_SHA256 = "d3bcfca4dbee407d472013b745ce2445d34af6f021aacc5753ee0dac54b56b0b"
EXPECTED_FACMAN_SHA256 = "47ccf1f151eb65daea1ae4d8ff782f48df08bbedd92d9434e5ca6fd86536270a"
EXPECTED_SIGNER = "Wube Software Ltd"
ATTESTATION_SCHEMA = "factorio.gate4c_quiet_host_attestation.v2"
OBSERVER_SELF_TEST_SCHEMA = "factorio.gate4c_observer_self_test.v2"
OBSERVER_PROVIDER_ID = "factorio.play.process-tree-observer"
OBSERVER_PROVIDER_REVISION = "gate4c-etw-file-registry-process.v2"
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


def git_identity(path: Path, expected: str, *, required_ancestors: list[str] | None = None) -> dict[str, Any]:
    head = run(["git", "rev-parse", "HEAD"], cwd=path)
    status = run(["git", "status", "--short", "--branch"], cwd=path)
    if head.returncode != 0 or status.returncode != 0:
        return {"path": str(path), "valid": False, "reason": "git_inspection_failed"}
    revision = head.stdout.strip()
    ancestors: dict[str, bool] = {}
    for ancestor in required_ancestors or []:
        result = run(["git", "merge-base", "--is-ancestor", ancestor, revision], cwd=path)
        ancestors[ancestor] = result.returncode == 0
    return {
        "path": str(path),
        "revision": revision,
        "expected_revision": expected,
        "exact": revision == expected,
        "required_ancestors": ancestors,
        "status": status.stdout.splitlines(),
        "clean": len(status.stdout.splitlines()[1:]) == 0,
        "valid": revision == expected and all(ancestors.values()),
    }


def verify_artifact_manifest(path: Path) -> dict[str, Any]:
    audit = audit_no_follow(path, require_file=True)
    if not audit["safe"]:
        return {"manifest": audit, "valid": False, "artifacts": []}
    manifest = json.loads(path.read_text(encoding="utf-8"))
    artifacts: list[dict[str, Any]] = []
    valid = (
        manifest.get("schema") == "facman.gate4c_artifact_binding.v1"
        and manifest.get("work_unit") == WORK_UNIT
        and manifest.get("source_candidate_revision") == CANDIDATE_REVISION
        and manifest.get("copy_verified") is True
    )
    for expected in manifest.get("artifacts", []):
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


def repository_tool_identity(repo_root: Path) -> dict[str, Any]:
    revision = run(["git", "rev-parse", "HEAD"], cwd=repo_root)
    status = run(["git", "status", "--short"], cwd=repo_root)
    files: dict[str, Any] = {}
    for relative in (
        "tools/gate4c_verdict_preflight.py",
        "tools/gate4c_observer_self_test.py",
    ):
        path = repo_root / relative
        audit = audit_no_follow(path, require_file=True)
        files[relative] = {
            "path_audit": audit,
            "sha256": sha256_file(path) if audit.get("safe") else None,
        }
    valid = (
        revision.returncode == 0
        and status.returncode == 0
        and not status.stdout.strip()
        and all(item["path_audit"].get("safe") for item in files.values())
    )
    return {
        "facman_tool_commit": revision.stdout.strip() if revision.returncode == 0 else None,
        "worktree_clean": status.returncode == 0 and not status.stdout.strip(),
        "tool_files": files,
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
                "work_unit": loaded.get("work_unit") == WORK_UNIT,
                "provider": loaded.get("provider")
                == {
                    "id": OBSERVER_PROVIDER_ID,
                    "revision": OBSERVER_PROVIDER_REVISION,
                    "profiles": ["GeneralProfile", "FileIO", "Registry"],
                },
                "candidate_revision": loaded.get("candidate_revision")
                == CANDIDATE_REVISION,
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
        and is_elevated()
        and recording is False
        and session.get("valid") is True
        and self_test_passed,
    }


def policy_identity(canonical_policy: Path) -> dict[str, Any]:
    audit = audit_no_follow(canonical_policy, require_file=True)
    if not audit["safe"]:
        return {"path_audit": audit, "valid": False}
    raw = canonical_policy.read_bytes().rstrip()
    computed = hashlib.sha256(raw).hexdigest()
    return {
        "path_audit": audit,
        "computed_digest": computed,
        "expected_digest": POLICY_DIGEST,
        "valid": computed == POLICY_DIGEST,
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


def source_evidence(
    path: Path | None,
    installed_executable: Path | None = None,
    *,
    source_member_executable: Path | None = None,
    task_root: Path | None = None,
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


def factorio_evidence(path: Path) -> dict[str, Any]:
    audit = audit_no_follow(path, require_file=True)
    if not audit["safe"]:
        return {"valid": False, "path_audit": audit}
    signature = authenticode(path)
    actual_hash = sha256_file(path)
    valid = (
        actual_hash == EXPECTED_FACTORIO_SHA256
        and signature.get("valid") is True
        and exact_factorio_version(signature)
    )
    return {
        "path_audit": audit,
        "stable_identity_digest": stable_identity_digest(audit),
        "sha256": actual_hash,
        "expected_sha256": EXPECTED_FACTORIO_SHA256,
        "signature": signature,
        "expected_version": EXPECTED_FACTORIO_VERSION,
        "valid": valid,
    }


def instance_evidence(facman: Path, workspace: Path, instance_id: str) -> dict[str, Any]:
    prefix = [str(facman), "--workspace", str(workspace)]
    inspection = run_json(prefix + ["instances", "inspect", instance_id, "--json"])
    description = run_json(prefix + ["instances", "describe", instance_id, "--intent", "menu", "--json"])
    readiness = run_json(prefix + ["instances", "readiness", instance_id, "--intent", "menu", "--json"])
    launch = run_json(prefix + ["launch", "plan", instance_id, "--preflight", "--json"])
    expected_blockers = {"real_play_gate_not_passed"}
    blocker_codes = {str(item.get("code")) for item in readiness.get("blockers", [])}
    plan_args = launch.get("args", [])
    valid = (
        inspection.get("instance_id") == EXPECTED_INSTANCE_ID
        and inspection.get("factorio_version") == EXPECTED_FACTORIO_VERSION
        and inspection.get("modset_status") == "present"
        and inspection.get("save_count") == 0
        and description.get("instance_spec", {}).get("spec_digest") == EXPECTED_SPEC_DIGEST
        and description.get("instance_binding", {}).get("binding_digest") == EXPECTED_BINDING_DIGEST
        and readiness.get("readiness_digest") == EXPECTED_READINESS_DIGEST
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


def add_blocker(blockers: list[dict[str, str]], code: str, detail: str) -> None:
    blockers.append({"code": code, "detail": detail})


def build_preflight(args: argparse.Namespace) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    task_root = Path(args.task_root)
    task_audit = audit_no_follow(task_root, require_file=False)
    if not task_audit["safe"] or task_root.name != WORK_UNIT:
        raise PreflightError(f"task root is not the exact Gate 4C root: {task_audit}")

    facman_repo = Path(args.repo_root)
    launcher_repo = Path(args.launcher_repo)
    setup_repo = Path(args.setup_repo)
    facman = Path(args.facman)
    workspace = Path(args.workspace)
    factorio = Path(args.factorio_exe)

    policy = policy_identity(
        facman_repo / "contracts/generated-index/hermetic_standalone_play_policy.v1.canonical.json"
    )
    artifacts = verify_artifact_manifest(Path(args.artifact_manifest))
    repositories = {
        "facman": git_identity(
            facman_repo,
            FINAL_EVIDENCE_DEV,
            required_ancestors=[CANDIDATE_REVISION, CANDIDATE_MERGE, CANDIDATE_CLOSEOUT_MERGE, FINAL_EVIDENCE_DEV],
        ),
        "universal_launcher": git_identity(launcher_repo, UNIVERSAL_LAUNCHER_REVISION),
        "universal_setup": git_identity(setup_repo, UNIVERSAL_SETUP_REVISION),
    }
    # Gate 4C evidence/tool commits may descend from the exact final dev pin.
    repositories["facman"]["valid"] = all(repositories["facman"].get("required_ancestors", {}).values())

    facman_hash = sha256_file(facman) if audit_no_follow(facman, require_file=True)["safe"] else None
    facman_artifact = {
        "path": str(facman),
        "sha256": facman_hash,
        "expected_sha256": EXPECTED_FACMAN_SHA256,
        "valid": facman_hash == EXPECTED_FACMAN_SHA256,
    }
    executable = factorio_evidence(factorio)
    source = source_evidence(
        Path(args.source_artifact) if args.source_artifact else None,
        factorio,
        source_member_executable=(
            Path(args.source_member_executable)
            if args.source_member_executable
            else None
        ),
        task_root=task_root,
    )
    instance = instance_evidence(facman, workspace, args.instance_id)
    processes = process_inventory()
    session = host_session_identity()
    observer = observer_prerequisites(
        Path(args.observer_self_test) if args.observer_self_test else None,
        repo_root=facman_repo,
        session=session,
        now=now,
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
    attestation = operator_attestation(
        Path(args.operator_attestation) if args.operator_attestation else None,
        machine_binding_id=session.get("machine_binding_id"),
        boot_identity=session.get("boot_identity"),
        observer_self_test_digest=observer_digest,
        observer_generated_at=observer_generated_at,
        current_host_state_digest=current_host_state,
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

    blockers: list[dict[str, str]] = []
    if not policy["valid"]:
        add_blocker(blockers, "frozen_policy_mismatch", "The canonical Gate 4A policy digest does not match.")
    if not artifacts["valid"] or not facman_artifact["valid"]:
        add_blocker(blockers, "candidate_artifact_mismatch", "The copied reviewed Gate 4B artifact set is incomplete or changed.")
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
    if not observer.get("tools_available"):
        add_blocker(blockers, "observer_tools_missing", "WPR, XPerf, and WPAExporter are required.")
    if not observer.get("elevated"):
        add_blocker(blockers, "observer_elevation_required", "The ETW FileIO/Registry observer self-test requires an elevated operator session.")
    if observer.get("recording_active") is not False:
        add_blocker(blockers, "observer_session_busy_or_unknown", "WPR must report no active recording before baseline capture.")
    if not observer.get("self_test_passed"):
        add_blocker(blockers, "observer_self_test_missing_or_stale", "No fresh, exact-machine, exact-tool, gap-free Gate 4C observer self-test is bound.")
    if not attestation.get("valid"):
        add_blocker(blockers, "quiet_host_attestation_missing", "A fresh operator attestation for restart, competing processes, synchronization activity, and sleep prevention is required.")

    core: dict[str, Any] = {
        "schema": "factorio.hermetic_play_verdict_preflight.v1",
        "canonicalization_version": "facman.sorted-json.v1",
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "work_unit": WORK_UNIT,
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
    core["preflight_digest"] = digest_value(core)
    return core


def write_record(path: Path, record: dict[str, Any], task_root: Path) -> None:
    absolute = Path(os.path.abspath(path))
    root = Path(os.path.abspath(task_root))
    try:
        absolute.relative_to(root)
    except ValueError as exc:
        raise PreflightError("preflight output must remain under the exact Gate 4C root") from exc
    absolute.parent.mkdir(parents=True, exist_ok=True)
    temporary = absolute.with_name(absolute.name + ".tmp")
    temporary.write_bytes(json.dumps(record, indent=2, ensure_ascii=False, sort_keys=True).encode("utf-8") + b"\n")
    os.replace(temporary, absolute)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Build the non-executing Gate 4C preflight packet.")
    value.add_argument("--task-root", required=True, type=Path)
    value.add_argument("--repo-root", required=True, type=Path)
    value.add_argument("--launcher-repo", required=True, type=Path)
    value.add_argument("--setup-repo", required=True, type=Path)
    value.add_argument("--artifact-manifest", required=True, type=Path)
    value.add_argument("--facman", required=True, type=Path)
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
    record = build_preflight(args)
    write_record(args.out, record, args.task_root)
    print(
        f"gate4c-verdict-preflight: {record['status']} "
        f"({len(record['blockers'])} blockers; {record['preflight_digest']})"
    )
    return 0 if record["status"] == "ready" else 3


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError, PreflightError) as exc:
        print(f"gate4c-verdict-preflight: {exc}", file=sys.stderr)
        raise SystemExit(2)
