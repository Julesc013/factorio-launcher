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
import shutil
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
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
WINDOWS_REPARSE_ATTRIBUTE = 0x400


class PreflightError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")


def digest_value(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


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
        "file_version=$f.VersionInfo.FileVersion;product_version=$f.VersionInfo.ProductVersion}"
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
    evidence["valid"] = evidence.get("status") == "Valid" and EXPECTED_SIGNER in str(evidence.get("signer_subject", ""))
    return evidence


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
    return {"available": True, "processes": processes, "quiet": len(processes) == 0}


def observer_prerequisites(self_test_path: Path | None) -> dict[str, Any]:
    wpr = shutil.which("wpr.exe") or shutil.which("wpr")
    xperf = shutil.which("xperf.exe") or shutil.which("xperf")
    if xperf is None:
        candidate = Path(r"C:\Program Files (x86)\Windows Kits\10\Windows Performance Toolkit\xperf.exe")
        if candidate.is_file():
            xperf = str(candidate)
    wpa_exporter = shutil.which("wpaexporter.exe") or shutil.which("wpaexporter")
    if wpa_exporter is None:
        candidate = Path(r"C:\Program Files (x86)\Windows Kits\10\Windows Performance Toolkit\wpaexporter.exe")
        if candidate.is_file():
            wpa_exporter = str(candidate)
    recording = None
    status_output = ""
    if wpr:
        status = run([wpr, "-status"])
        status_output = (status.stdout + "\n" + status.stderr).strip()
        recording = "is not recording" not in status_output.lower()
    self_test: dict[str, Any] | None = None
    if self_test_path:
        audit = audit_no_follow(self_test_path, require_file=True)
        if audit["safe"]:
            self_test = json.loads(self_test_path.read_text(encoding="utf-8"))
            self_test = {**self_test, "artifact_sha256": sha256_file(self_test_path), "path_audit": audit}
        else:
            self_test = {"status": "invalid", "path_audit": audit}
    self_test_passed = bool(
        self_test
        and self_test.get("schema") == "factorio.gate4c_observer_self_test.v1"
        and self_test.get("status") == "pass"
        and self_test.get("lost_events") == 0
        and self_test.get("attribution_complete") is True
    )
    return {
        "wpr": wpr,
        "xperf": xperf,
        "wpaexporter": wpa_exporter,
        "tools_available": all([wpr, xperf, wpa_exporter]),
        "elevated": is_elevated(),
        "recording_active": recording,
        "status_output": status_output,
        "self_test": self_test,
        "self_test_passed": self_test_passed,
        "ready": all([wpr, xperf, wpa_exporter]) and is_elevated() and recording is False and self_test_passed,
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


def source_evidence(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {
            "status": "missing",
            "valid": False,
            "reason": "operator_supplied_authenticated_wube_source_required",
        }
    audit = audit_no_follow(path, require_file=True)
    if not audit["safe"]:
        return {"status": "invalid", "valid": False, "path_audit": audit}
    signature = authenticode(path)
    record = {
        "status": "verified" if signature.get("valid") else "invalid",
        "path_audit": audit,
        "artifact_sha256": sha256_file(path),
        "signature": signature,
    }
    record["authentication_evidence_digest"] = digest_value(record)
    source_version = str(
        signature.get("product_version") or signature.get("file_version") or ""
    )
    record["expected_version"] = EXPECTED_FACTORIO_VERSION
    record["valid"] = (
        signature.get("valid") is True
        and source_version.startswith(EXPECTED_FACTORIO_VERSION)
    )
    return record


def factorio_evidence(path: Path) -> dict[str, Any]:
    audit = audit_no_follow(path, require_file=True)
    if not audit["safe"]:
        return {"valid": False, "path_audit": audit}
    signature = authenticode(path)
    actual_hash = sha256_file(path)
    version = str(signature.get("product_version") or signature.get("file_version") or "")
    valid = (
        actual_hash == EXPECTED_FACTORIO_SHA256
        and signature.get("valid") is True
        and version.startswith(EXPECTED_FACTORIO_VERSION)
    )
    return {
        "path_audit": audit,
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


def operator_attestation(path: Path | None) -> dict[str, Any]:
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
    exact_keys = required_true | {"schema", "attested_at", "reviewer_id"}
    valid = (
        isinstance(value, dict)
        and set(value) == exact_keys
        and value.get("schema") == "factorio.gate4c_quiet_host_attestation.v1"
        and isinstance(value.get("attested_at"), str)
        and bool(value.get("reviewer_id"))
        and all(value.get(key) is True for key in required_true)
    )
    return {
        "status": "verified" if valid else "invalid",
        "valid": valid,
        "path_audit": audit,
        "artifact_sha256": sha256_file(path),
        "attestation_digest": digest_value(value),
        "attested_at": value.get("attested_at") if isinstance(value, dict) else None,
        "reviewer_id": value.get("reviewer_id") if isinstance(value, dict) else None,
        "required_true": sorted(required_true),
    }


def add_blocker(blockers: list[dict[str, str]], code: str, detail: str) -> None:
    blockers.append({"code": code, "detail": detail})


def build_preflight(args: argparse.Namespace) -> dict[str, Any]:
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
    source = source_evidence(Path(args.source_artifact) if args.source_artifact else None)
    executable = factorio_evidence(factorio)
    instance = instance_evidence(facman, workspace, args.instance_id)
    processes = process_inventory()
    observer = observer_prerequisites(
        Path(args.observer_self_test) if args.observer_self_test else None
    )
    attestation = operator_attestation(
        Path(args.operator_attestation) if args.operator_attestation else None
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
    if not observer.get("tools_available"):
        add_blocker(blockers, "observer_tools_missing", "WPR, XPerf, and WPAExporter are required.")
    if not observer.get("elevated"):
        add_blocker(blockers, "observer_elevation_required", "The ETW FileIO/Registry observer self-test requires an elevated operator session.")
    if observer.get("recording_active") is not False:
        add_blocker(blockers, "observer_session_busy_or_unknown", "WPR must report no active recording before baseline capture.")
    if not observer.get("self_test_passed"):
        add_blocker(blockers, "observer_self_test_missing", "No complete, gap-free Gate 4C observer self-test is bound.")
    if not attestation.get("valid"):
        add_blocker(blockers, "quiet_host_attestation_missing", "A fresh operator attestation for restart, competing processes, synchronization activity, and sleep prevention is required.")

    core: dict[str, Any] = {
        "schema": "factorio.hermetic_play_verdict_preflight.v1",
        "canonicalization_version": "facman.sorted-json.v1",
        "generated_at": utc_now(),
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
            "process_inventory": processes,
        },
        "observer": observer,
        "operator_attestation": attestation,
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
