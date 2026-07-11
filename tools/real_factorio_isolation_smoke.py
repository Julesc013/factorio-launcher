# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import stat
import subprocess
import sys
import time
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ACKNOWLEDGEMENT = "I understand this starts my supplied Factorio binary"
ROOT = Path(__file__).resolve().parents[1]
REPARSE_POINT_ATTRIBUTE = 0x400
DEFAULT_SNAPSHOT_MAX_FILES = 100_000
DEFAULT_SNAPSHOT_MAX_BYTES = 10 * 1024 * 1024 * 1024
DEFAULT_SNAPSHOT_MAX_SECONDS = 300.0
DEFAULT_PROCESS_TIMEOUT_SECONDS = 1_800.0
DEFAULT_TERMINATION_GRACE_SECONDS = 10.0
OBSERVATION_CLASSIFICATIONS = {
    "instance-local",
    "os-managed-transient",
    "unexpected",
    "unresolved",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def file_identity(path: Path) -> dict[str, Any]:
    refused_link = path_crosses_link_or_reparse(path)
    result: dict[str, Any] = {
        "path": str(path),
        "exists": path.is_file(),
        "link_or_reparse_refused": refused_link,
    }
    if result["exists"] and not refused_link:
        result["size_bytes"] = path.stat().st_size
        result["sha256"] = sha256_file(path)
    else:
        result["sha256"] = None
    return result


def is_link_or_reparse(metadata: os.stat_result) -> bool:
    return stat.S_ISLNK(metadata.st_mode) or bool(
        getattr(metadata, "st_file_attributes", 0) & REPARSE_POINT_ATTRIBUTE
    )


def path_crosses_link_or_reparse(path: Path) -> bool:
    absolute = Path(os.path.abspath(path))
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current /= part
        if not os.path.lexists(current):
            continue
        try:
            if is_link_or_reparse(current.lstat()):
                return True
        except OSError:
            return True
    return False


def snapshot_file_digest(
    path: Path, expected: os.stat_result, deadline: float
) -> dict[str, Any]:
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    bytes_read = 0
    digest = hashlib.sha256()
    with os.fdopen(descriptor, "rb") as handle:
        opened = os.fstat(handle.fileno())
        identity_changed = bool(expected.st_ino and opened.st_ino) and (
            expected.st_dev,
            expected.st_ino,
        ) != (opened.st_dev, opened.st_ino)
        if (
            not stat.S_ISREG(opened.st_mode)
            or is_link_or_reparse(opened)
            or identity_changed
        ):
            return {"status": "changed", "bytes_read": 0}
        while chunk := handle.read(1024 * 1024):
            bytes_read += len(chunk)
            digest.update(chunk)
            if time.monotonic() > deadline:
                return {"status": "elapsed", "bytes_read": bytes_read}
        after = os.fstat(handle.fileno())
    identity_changed = bool(expected.st_ino and after.st_ino) and (
        expected.st_dev,
        expected.st_ino,
    ) != (after.st_dev, after.st_ino)
    if (
        is_link_or_reparse(after)
        or after.st_size != expected.st_size
        or after.st_mtime_ns != expected.st_mtime_ns
        or identity_changed
    ):
        return {"status": "changed", "bytes_read": bytes_read}
    return {
        "status": "ok",
        "bytes_read": bytes_read,
        "sha256": digest.hexdigest(),
    }


def snapshot(
    root: Path,
    *,
    max_files: int = DEFAULT_SNAPSHOT_MAX_FILES,
    max_bytes: int = DEFAULT_SNAPSHOT_MAX_BYTES,
    max_seconds: float = DEFAULT_SNAPSHOT_MAX_SECONDS,
) -> dict[str, Any]:
    started = time.monotonic()
    result: dict[str, Any] = {
        "root": str(root),
        "root_exists": os.path.lexists(root),
        "complete": True,
        "limits": {
            "max_files": max_files,
            "max_bytes_hashed": max_bytes,
            "max_elapsed_seconds": max_seconds,
        },
        "file_count": 0,
        "directory_count": 0,
        "bytes_hashed": 0,
        "elapsed_seconds": 0.0,
        "directories": [],
        "files": {},
        "omitted_entries": [],
    }

    def omit(relative: str, reason: str, detail: str = "") -> None:
        result["complete"] = False
        item = {"path": relative, "reason": reason}
        if detail:
            item["detail"] = detail
        result["omitted_entries"].append(item)

    if path_crosses_link_or_reparse(root):
        omit(".", "root_link_or_reparse_refused")
        result["elapsed_seconds"] = round(time.monotonic() - started, 6)
        return result
    if not result["root_exists"]:
        result["elapsed_seconds"] = round(time.monotonic() - started, 6)
        return result

    try:
        root_metadata = root.lstat()
    except OSError as exc:
        omit(".", "root_stat_failed", str(exc))
        result["elapsed_seconds"] = round(time.monotonic() - started, 6)
        return result
    if is_link_or_reparse(root_metadata):
        omit(".", "root_link_or_reparse_refused")
        result["elapsed_seconds"] = round(time.monotonic() - started, 6)
        return result
    if not stat.S_ISDIR(root_metadata.st_mode):
        omit(".", "root_not_directory")
        result["elapsed_seconds"] = round(time.monotonic() - started, 6)
        return result

    result["directories"].append(".")
    result["directory_count"] = 1
    stack: list[tuple[Path, str]] = [(root, "")]
    stopped = False
    while stack and not stopped:
        directory, relative_directory = stack.pop()
        if time.monotonic() - started > max_seconds:
            omit(relative_directory or ".", "elapsed_time_limit_exceeded")
            break
        try:
            current_metadata = directory.lstat()
            if is_link_or_reparse(current_metadata):
                omit(relative_directory or ".", "link_or_reparse_refused")
                continue
            with os.scandir(directory) as iterator:
                entries = sorted(iterator, key=lambda entry: entry.name.casefold())
        except OSError as exc:
            omit(relative_directory or ".", "directory_read_failed", str(exc))
            continue
        child_directories: list[tuple[Path, str]] = []
        for entry in entries:
            relative = f"{relative_directory}/{entry.name}" if relative_directory else entry.name
            relative = relative.replace("\\", "/")
            if time.monotonic() - started > max_seconds:
                omit(relative, "elapsed_time_limit_exceeded")
                stopped = True
                break
            try:
                metadata = entry.stat(follow_symlinks=False)
            except OSError as exc:
                omit(relative, "entry_stat_failed", str(exc))
                continue
            if is_link_or_reparse(metadata):
                omit(relative, "link_or_reparse_refused")
                continue
            if stat.S_ISDIR(metadata.st_mode):
                result["directories"].append(relative)
                result["directory_count"] += 1
                child_directories.append((Path(entry.path), relative))
                continue
            if not stat.S_ISREG(metadata.st_mode):
                omit(relative, "non_regular_file_refused")
                continue
            if result["file_count"] >= max_files:
                omit(relative, "file_count_limit_exceeded")
                stopped = True
                break
            if result["bytes_hashed"] + metadata.st_size > max_bytes:
                omit(relative, "byte_limit_exceeded")
                stopped = True
                break
            try:
                hashed = snapshot_file_digest(
                    Path(entry.path), metadata, started + max_seconds
                )
            except OSError as exc:
                omit(relative, "file_read_failed", str(exc))
                continue
            result["bytes_hashed"] += hashed["bytes_read"]
            if hashed["status"] == "elapsed":
                omit(relative, "elapsed_time_limit_exceeded")
                stopped = True
                break
            if hashed["status"] != "ok":
                omit(relative, "file_changed_while_hashing")
                continue
            result["files"][relative] = {
                "sha256": hashed["sha256"],
                "size_bytes": metadata.st_size,
            }
            result["file_count"] += 1
        stack.extend(reversed(child_directories))

    result["directories"] = sorted(result["directories"])
    result["files"] = dict(sorted(result["files"].items()))
    result["elapsed_seconds"] = round(time.monotonic() - started, 6)
    return result


def snapshot_diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    before_files = before["files"]
    after_files = after["files"]
    before_paths = set(before_files)
    after_paths = set(after_files)
    created_files = [
        {
            "path": path,
            "before_sha256": None,
            "after_sha256": after_files[path]["sha256"],
            "before_size_bytes": None,
            "after_size_bytes": after_files[path]["size_bytes"],
        }
        for path in sorted(after_paths - before_paths)
    ]
    deleted_files = [
        {
            "path": path,
            "before_sha256": before_files[path]["sha256"],
            "after_sha256": None,
            "before_size_bytes": before_files[path]["size_bytes"],
            "after_size_bytes": None,
        }
        for path in sorted(before_paths - after_paths)
    ]
    modified_files = [
        {
            "path": path,
            "before_sha256": before_files[path]["sha256"],
            "after_sha256": after_files[path]["sha256"],
            "before_size_bytes": before_files[path]["size_bytes"],
            "after_size_bytes": after_files[path]["size_bytes"],
        }
        for path in sorted(before_paths & after_paths)
        if before_files[path] != after_files[path]
    ]
    before_directories = set(before["directories"])
    after_directories = set(after["directories"])
    created_directories = sorted(after_directories - before_directories)
    deleted_directories = sorted(before_directories - after_directories)
    changed = any(
        (
            before["root_exists"] != after["root_exists"],
            created_files,
            modified_files,
            deleted_files,
            created_directories,
            deleted_directories,
        )
    )
    return {
        "complete": before["complete"] and after["complete"],
        "changed": changed,
        "root_existed_before": before["root_exists"],
        "root_exists_after": after["root_exists"],
        "created_files": created_files,
        "modified_files": modified_files,
        "deleted_files": deleted_files,
        "created_directories": created_directories,
        "deleted_directories": deleted_directories,
        "before_omitted_entries": before["omitted_entries"],
        "after_omitted_entries": after["omitted_entries"],
    }


def run_command_identity(command: list[str], timeout_seconds: float) -> dict[str, Any]:
    started = utc_now()
    try:
        completed = subprocess.run(
            command,
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
        )
        return {
            "command": command,
            "started_utc": started,
            "ended_utc": utc_now(),
            "exit_status": completed.returncode,
            "timed_out": False,
            "termination_requested": False,
            "killed_after_timeout": False,
            "stdout": completed.stdout.strip(),
            "stderr": completed.stderr.strip(),
        }
    except OSError as exc:
        return {
            "command": command,
            "started_utc": started,
            "ended_utc": utc_now(),
            "exit_status": None,
            "timed_out": False,
            "termination_requested": False,
            "killed_after_timeout": False,
            "stdout": "",
            "stderr": str(exc),
        }
    except subprocess.TimeoutExpired as exc:
        stdout = (
            exc.stdout.decode("utf-8", errors="replace")
            if isinstance(exc.stdout, bytes)
            else exc.stdout
        )
        stderr = (
            exc.stderr.decode("utf-8", errors="replace")
            if isinstance(exc.stderr, bytes)
            else exc.stderr
        )
        return {
            "command": command,
            "started_utc": started,
            "ended_utc": utc_now(),
            "exit_status": None,
            "timed_out": True,
            "termination_requested": True,
            "killed_after_timeout": True,
            "stdout": (stdout or "").strip(),
            "stderr": (stderr or "").strip(),
        }


def run_json(command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        check=False,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr or completed.stdout)
    data = json.loads(completed.stdout)
    if not isinstance(data, dict):
        raise RuntimeError("command returned a non-object JSON payload")
    return data


def repository_revisions() -> dict[str, Any]:
    revisions: dict[str, Any] = {
        "factorio_launcher": {"revision": None, "source": "git"},
        "universal_launcher": {"revision": None, "source": "workspace_lock"},
        "universal_setup": {"revision": None, "source": "workspace_lock"},
    }
    git = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        check=False,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if git.returncode == 0:
        revisions["factorio_launcher"]["revision"] = git.stdout.strip()
    else:
        revisions["factorio_launcher"]["error"] = git.stderr.strip() or "git revision unavailable"
    lock_path = ROOT / "release" / "index" / "workspace_lock.v1.toml"
    if lock_path.is_file():
        with lock_path.open("rb") as handle:
            lock = tomllib.load(handle)
        for component in lock.get("component", []):
            component_id = component.get("id")
            if component_id in {"universal_launcher", "universal_setup"}:
                revisions[component_id]["revision"] = component.get("pin")
                revisions[component_id]["lock_file"] = str(lock_path)
    return revisions


def operating_system_identity() -> dict[str, Any]:
    identity: dict[str, Any] = {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "architecture": platform.machine(),
        "python_architecture": platform.architecture()[0],
        "platform": platform.platform(),
    }
    if os.name == "nt":
        windows = sys.getwindowsversion()
        identity["windows_version"] = {
            "major": windows.major,
            "minor": windows.minor,
            "build": windows.build,
            "platform": windows.platform,
            "service_pack": windows.service_pack,
        }
    return identity


def acquire_operator_lock(instance_root: Path) -> tuple[Path, str]:
    lock_path = instance_root / "locks" / "run.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    token = f"operator-{os.getpid()}-{time.time_ns()}"
    content = {
        "schema": "facman.instance_run_lock.v1",
        "process_id": os.getpid(),
        "created_unix": int(time.time()),
        "token": token,
    }
    descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(content, handle, sort_keys=True)
        handle.write("\n")
    return lock_path, token


def release_operator_lock(lock_path: Path, token: str) -> None:
    current = json.loads(lock_path.read_text(encoding="utf-8"))
    if current.get("token") != token:
        raise RuntimeError("run lock token changed; refusing to remove foreign lock")
    lock_path.unlink()


def observe_windows_children(process_id: int) -> dict[str, Any]:
    if os.name != "nt":
        return {"status": "unsupported_platform", "processes": []}
    script = (
        "$items = Get-CimInstance Win32_Process | "
        "Select-Object ProcessId,ParentProcessId,Name,ExecutablePath; "
        "$items | ConvertTo-Json -Compress"
    )
    try:
        completed = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status": "unavailable", "error": str(exc), "processes": []}
    if completed.returncode != 0:
        return {
            "status": "unavailable",
            "error": completed.stderr.strip() or "process query failed",
            "processes": [],
        }
    try:
        raw = json.loads(completed.stdout or "[]")
    except json.JSONDecodeError as exc:
        return {"status": "unavailable", "error": str(exc), "processes": []}
    processes = raw if isinstance(raw, list) else [raw]
    by_parent: dict[int, list[dict[str, Any]]] = {}
    for process in processes:
        if not isinstance(process, dict):
            continue
        by_parent.setdefault(int(process.get("ParentProcessId", -1)), []).append(process)
    descendants: list[dict[str, Any]] = []
    pending = [process_id]
    seen = {process_id}
    while pending:
        parent = pending.pop()
        for child in by_parent.get(parent, []):
            child_id = int(child.get("ProcessId", -1))
            if child_id in seen:
                continue
            seen.add(child_id)
            pending.append(child_id)
            descendants.append(
                {
                    "process_id": child_id,
                    "parent_process_id": int(child.get("ParentProcessId", -1)),
                    "name": child.get("Name"),
                    "executable_path": child.get("ExecutablePath"),
                }
            )
    return {"status": "observed", "processes": descendants}


def supervise_process(
    command: list[str],
    *,
    cwd: Path,
    timeout_seconds: float,
    termination_grace_seconds: float,
) -> dict[str, Any]:
    started_monotonic = time.monotonic()
    started_utc = utc_now()
    process = subprocess.Popen(command, cwd=cwd)
    observed_children: dict[int, dict[str, Any]] = {}
    child_observation_status = "not_attempted"
    next_observation = started_monotonic + min(1.0, timeout_seconds / 2)
    timed_out = False
    termination_requested = False
    killed = False
    operator_interrupted = False

    def terminate_process() -> None:
        nonlocal termination_requested, killed
        termination_requested = True
        process.terminate()
        try:
            process.wait(timeout=termination_grace_seconds)
        except subprocess.TimeoutExpired:
            process.kill()
            killed = True
            process.wait()

    try:
        while process.poll() is None:
            now = time.monotonic()
            if now >= next_observation:
                observation = observe_windows_children(process.pid)
                child_observation_status = observation["status"]
                for child in observation["processes"]:
                    observed_children[child["process_id"]] = child
                next_observation = now + 5
                now = time.monotonic()
            if now - started_monotonic >= timeout_seconds:
                timed_out = True
                terminate_process()
                break
            time.sleep(0.1)
    except KeyboardInterrupt:
        operator_interrupted = True
        if process.poll() is None:
            terminate_process()
    return {
        "command": command,
        "process_id": process.pid,
        "started_utc": started_utc,
        "ended_utc": utc_now(),
        "duration_seconds": round(time.monotonic() - started_monotonic, 3),
        "exit_status": process.returncode,
        "timed_out": timed_out,
        "operator_interrupted": operator_interrupted,
        "termination_requested": termination_requested,
        "killed_after_grace_period": killed,
        "termination_grace_seconds": termination_grace_seconds,
        "child_process_observation": {
            "status": child_observation_status,
            "processes": sorted(observed_children.values(), key=lambda item: item["process_id"]),
        },
    }


def write_observation(args: argparse.Namespace) -> dict[str, Any]:
    record: dict[str, Any] = {
        "required_for_pass": True,
        "method": args.write_observation_method,
        "artifact": None,
        "classifications": [],
        "review_status": "pending",
        "unexpected_persistent_write_detected": False,
        "unresolved_persistent_write_detected": False,
        "allowed_classifications": sorted(OBSERVATION_CLASSIFICATIONS),
    }
    if args.write_observation_artifact:
        record["artifact"] = file_identity(args.write_observation_artifact)
    if args.write_observation_classification:
        classification_path = args.write_observation_classification
        record["classification_file"] = file_identity(classification_path)
        if classification_path.is_file():
            values = json.loads(classification_path.read_text(encoding="utf-8"))
            if not isinstance(values, list):
                raise RuntimeError("write-observation classification must be a JSON array")
            for item in values:
                if not isinstance(item, dict) or item.get("classification") not in OBSERVATION_CLASSIFICATIONS:
                    raise RuntimeError("write-observation classification contains an invalid item")
            record["classifications"] = values
            unresolved = any(item["classification"] == "unresolved" for item in values)
            unexpected = any(item["classification"] == "unexpected" for item in values)
            record["unexpected_persistent_write_detected"] = unexpected
            record["unresolved_persistent_write_detected"] = unresolved
            record["review_status"] = (
                "unexpected_or_unresolved" if unresolved or unexpected else "classified"
            )
    return record


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Operator-only real Factorio isolation smoke; never promotes a claim automatically."
    )
    parser.add_argument("--facman", required=True, type=Path)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--instance-id", required=True)
    parser.add_argument("--factorio-exe", required=True, type=Path)
    parser.add_argument("--protected-root", action="append", default=[], type=Path)
    parser.add_argument("--evidence-out", required=True, type=Path)
    parser.add_argument("--execute-smoke", action="store_true")
    parser.add_argument("--acknowledge", default="")
    parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_PROCESS_TIMEOUT_SECONDS)
    parser.add_argument(
        "--termination-grace-seconds", type=float, default=DEFAULT_TERMINATION_GRACE_SECONDS
    )
    parser.add_argument("--snapshot-max-files", type=int, default=DEFAULT_SNAPSHOT_MAX_FILES)
    parser.add_argument("--snapshot-max-bytes", type=int, default=DEFAULT_SNAPSHOT_MAX_BYTES)
    parser.add_argument("--snapshot-max-seconds", type=float, default=DEFAULT_SNAPSHOT_MAX_SECONDS)
    parser.add_argument(
        "--write-observation-method",
        choices=["not-supplied", "procmon", "filesystem-diff"],
        default="not-supplied",
    )
    parser.add_argument("--write-observation-artifact", type=Path)
    parser.add_argument("--write-observation-classification", type=Path)
    return parser


def write_evidence(path: Path, evidence: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))


def validate_positive_limits(args: argparse.Namespace) -> None:
    values = {
        "--timeout-seconds": args.timeout_seconds,
        "--termination-grace-seconds": args.termination_grace_seconds,
        "--snapshot-max-files": args.snapshot_max_files,
        "--snapshot-max-bytes": args.snapshot_max_bytes,
        "--snapshot-max-seconds": args.snapshot_max_seconds,
    }
    for name, value in values.items():
        if value <= 0:
            raise RuntimeError(f"{name} must be greater than zero")
    if args.write_observation_method == "not-supplied" and (
        args.write_observation_artifact or args.write_observation_classification
    ):
        raise RuntimeError(
            "--write-observation-method is required when observation evidence is supplied"
        )
    if args.write_observation_method != "not-supplied" and not args.write_observation_artifact:
        raise RuntimeError(
            "--write-observation-artifact is required for the selected observation method"
        )


def main() -> int:
    args = build_parser().parse_args()
    validate_positive_limits(args)
    preview = run_json(
        [
            str(args.facman),
            "--workspace",
            str(args.workspace),
            "run",
            args.instance_id,
            "--json",
        ]
    )
    preflight = run_json(
        [
            str(args.facman),
            "--workspace",
            str(args.workspace),
            "launch-plan",
            args.instance_id,
            "--preflight",
            "--json",
        ]
    )
    executable = Path(preview["executable"])
    effective_config = preview["effective_config"]
    config_file = Path(effective_config["config_file"])
    instance_root = Path(effective_config["write_data"])
    protected_roots = []
    seen_roots: set[str] = set()
    for path in [Path(preview["app_dir"]), *args.protected_root]:
        absolute = Path(os.path.abspath(path))
        key = os.path.normcase(str(absolute))
        if key not in seen_roots:
            protected_roots.append(absolute)
            seen_roots.add(key)
    prepared = {
        "schema": "facman.real_factorio_isolation_smoke.v2",
        "status": "prepared",
        "generated_utc": utc_now(),
        "operator_verdict": "pending",
        "factorio_executable": str(executable),
        "instance_root": str(instance_root),
        "args": preview["args"],
        "effective_config": effective_config,
        "preflight": preflight,
        "protected_roots": [str(path) for path in protected_roots],
        "identity": {
            "facman_executable": file_identity(args.facman),
            "facman_version": run_command_identity([str(args.facman), "--version"], 30),
            "factorio_executable": file_identity(args.factorio_exe),
            "factorio_version": {
                "status": "not_run_in_prepare_mode",
                "command": [str(args.factorio_exe), "--version"],
            },
            "repositories": repository_revisions(),
            "operating_system": operating_system_identity(),
            "effective_config_file": file_identity(config_file),
        },
        "snapshot_policy": {
            "follow_links_or_reparse_points": False,
            "max_files": args.snapshot_max_files,
            "max_bytes_hashed": args.snapshot_max_bytes,
            "max_elapsed_seconds": args.snapshot_max_seconds,
            "incomplete_protected_snapshot_result": "inconclusive",
        },
        "process_policy": {
            "timeout_seconds": args.timeout_seconds,
            "termination_grace_seconds": args.termination_grace_seconds,
            "graceful_close_instructions": [
                "Exercise the intended smoke, return to the main menu, and exit Factorio normally.",
                "If the timeout is approaching, exit normally before forced termination is requested.",
            ],
        },
        "system_wide_write_observation": write_observation(args),
        "claim_boundary": "Real Factorio isolation remains unproven until a human reviews this evidence.",
    }
    identity = prepared["identity"]
    identity["pre_execute_complete"] = bool(
        identity["facman_executable"]["sha256"]
        and identity["facman_version"]["exit_status"] == 0
        and identity["factorio_executable"]["sha256"]
        and identity["effective_config_file"]["sha256"]
        and all(
            item["revision"] for item in identity["repositories"].values()
        )
    )
    if executable.resolve(strict=False) != args.factorio_exe.resolve(strict=False):
        raise RuntimeError("--factorio-exe does not match the registered launch plan executable")
    if not args.execute_smoke:
        write_evidence(args.evidence_out, prepared)
        return 0
    if args.acknowledge != ACKNOWLEDGEMENT:
        raise RuntimeError(f"--acknowledge must exactly equal: {ACKNOWLEDGEMENT}")
    if preflight.get("status") != "pass":
        raise RuntimeError("authoritative launch preflight did not pass")
    if not identity["pre_execute_complete"]:
        evidence = {
            **prepared,
            "status": "inconclusive_before_smoke",
            "automated_observation": "required_identity_incomplete",
            "operator_verdict": "pending",
        }
        write_evidence(args.evidence_out, evidence)
        return 3

    snapshot_options = {
        "max_files": args.snapshot_max_files,
        "max_bytes": args.snapshot_max_bytes,
        "max_seconds": args.snapshot_max_seconds,
    }
    protected_before = {
        str(path): snapshot(path, **snapshot_options) for path in protected_roots
    }
    instance_before = snapshot(instance_root, **snapshot_options)
    if not all(item["complete"] for item in protected_before.values()) or not instance_before[
        "complete"
    ]:
        reason = (
            "protected_snapshot_incomplete"
            if not all(item["complete"] for item in protected_before.values())
            else "instance_snapshot_incomplete"
        )
        evidence = {
            **prepared,
            "status": "inconclusive_before_smoke",
            "protected_snapshots": {
                path: {"before": value, "after": None, "diff": None}
                for path, value in protected_before.items()
            },
            "instance_snapshot": {"before": instance_before, "after": None, "diff": None},
            "automated_observation": reason,
            "operator_verdict": "pending",
        }
        write_evidence(args.evidence_out, evidence)
        return 3

    lock_path, token = acquire_operator_lock(instance_root)
    lock_record: dict[str, Any] = {
        "path": str(lock_path),
        "acquired": True,
        "released": False,
        "release_error": None,
    }
    process_record: dict[str, Any] | None = None
    try:
        prepared["identity"]["factorio_version"] = run_command_identity(
            [str(args.factorio_exe), "--version"], min(args.timeout_seconds, 60)
        )
        factorio_version = prepared["identity"]["factorio_version"]
        if not factorio_version["timed_out"] and factorio_version["exit_status"] == 0:
            print(
                "Operator: exercise the intended smoke and exit Factorio normally before the timeout.",
                file=sys.stderr,
                flush=True,
            )
            try:
                process_record = supervise_process(
                    [str(args.factorio_exe), *preview["args"]],
                    cwd=args.factorio_exe.parent,
                    timeout_seconds=args.timeout_seconds,
                    termination_grace_seconds=args.termination_grace_seconds,
                )
            except OSError as exc:
                process_record = {
                    "command": [str(args.factorio_exe), *preview["args"]],
                    "process_id": None,
                    "started_utc": utc_now(),
                    "ended_utc": utc_now(),
                    "duration_seconds": 0.0,
                    "exit_status": None,
                    "timed_out": False,
                    "operator_interrupted": False,
                    "termination_requested": False,
                    "killed_after_grace_period": False,
                    "termination_grace_seconds": args.termination_grace_seconds,
                    "launch_error": str(exc),
                    "child_process_observation": {
                        "status": "not_started",
                        "processes": [],
                    },
                }
    finally:
        try:
            release_operator_lock(lock_path, token)
            lock_record["released"] = True
        except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
            lock_record["release_error"] = str(exc)

    protected_after = {
        str(path): snapshot(path, **snapshot_options) for path in protected_roots
    }
    instance_after = snapshot(instance_root, **snapshot_options)
    protected_records = {
        path: {
            "before": protected_before[path],
            "after": protected_after[path],
            "diff": snapshot_diff(protected_before[path], protected_after[path]),
        }
        for path in protected_before
    }
    instance_record = {
        "before": instance_before,
        "after": instance_after,
        "diff": snapshot_diff(instance_before, instance_after),
    }
    prepared["system_wide_write_observation"] = write_observation(args)
    protected_complete = all(record["diff"]["complete"] for record in protected_records.values())
    protected_changed = any(record["diff"]["changed"] for record in protected_records.values())
    instance_complete = instance_record["diff"]["complete"]
    system_observation = prepared["system_wide_write_observation"]
    factorio_version = prepared["identity"]["factorio_version"]
    factorio_version_failed = (
        factorio_version["timed_out"] or factorio_version["exit_status"] != 0
    )
    if not lock_record["released"]:
        automated_observation = "run_lock_release_failed"
        return_code = 1
    elif protected_changed:
        automated_observation = "protected_root_change_detected"
        return_code = 1
    elif not protected_complete:
        automated_observation = "protected_snapshot_incomplete"
        return_code = 3
    elif not instance_complete:
        automated_observation = "instance_snapshot_incomplete"
        return_code = 3
    elif factorio_version_failed:
        automated_observation = "factorio_version_identity_failed"
        return_code = 3
    elif process_record and process_record.get("launch_error"):
        automated_observation = "factorio_process_launch_failed"
        return_code = 3
    elif system_observation["unexpected_persistent_write_detected"]:
        automated_observation = "unexpected_persistent_write_detected"
        return_code = 1
    elif system_observation["unresolved_persistent_write_detected"]:
        automated_observation = "unresolved_persistent_write_detected"
        return_code = 3
    elif process_record and (process_record["timed_out"] or process_record["termination_requested"]):
        automated_observation = "process_supervision_inconclusive"
        return_code = 3
    else:
        automated_observation = "bounded_snapshots_complete_human_review_required"
        return_code = 0
    evidence = {
        **prepared,
        "status": (
            "inconclusive_before_smoke"
            if factorio_version_failed
            else "awaiting_operator_verdict"
        ),
        "process": process_record,
        "run_lock": lock_record,
        "protected_snapshots": protected_records,
        "instance_snapshot": instance_record,
        "automated_observation": automated_observation,
        "operator_verdict": "pending",
    }
    write_evidence(args.evidence_out, evidence)
    return return_code


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError, tomllib.TOMLDecodeError) as exc:
        print(f"real-factorio-isolation-smoke: {exc}", file=sys.stderr)
        raise SystemExit(2)
