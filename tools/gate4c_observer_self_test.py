# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Elevated, non-Factorio self-test for the Gate 4C ETW observer prerequisites."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "gate4c_verdict_preflight", ROOT / "tools/gate4c_verdict_preflight.py"
)
assert SPEC and SPEC.loader
PREFLIGHT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PREFLIGHT)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def command(args: list[str], *, timeout: int = 180) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def parse_lost_events(stats: str) -> int | None:
    patterns = (
        r"events\s+lost\s*[:=]\s*([0-9]+)",
        r"eventslost\s*[:=]\s*([0-9]+)",
        r"lost\s+events\s*[:=]\s*([0-9]+)",
    )
    values: list[int] = []
    for pattern in patterns:
        values.extend(int(item) for item in re.findall(pattern, stats, flags=re.IGNORECASE))
    return max(values) if values else None


def wpr_is_not_recording(result: subprocess.CompletedProcess[str]) -> bool:
    return result.returncode == 0 and "is not recording" in (
        result.stdout + result.stderr
    ).casefold()


def normalize_trace_text(value: str) -> str:
    return value.replace("\\\\", "\\").replace("/", "\\").casefold()


def line_has_pid(
    line: str,
    process_id: int,
    *,
    fields: tuple[str, ...] = ("pid", "processid"),
) -> bool:
    names = "|".join(re.escape(field) for field in fields)
    return (
        re.search(
            rf"(?:^|[,;\s])(?:{names})\s*[:=]\s*{process_id}(?![0-9])",
            line,
            flags=re.IGNORECASE,
        )
        is not None
    )


def domain_attribution(
    dump: str,
    *,
    marker: str,
    process_id: int,
    event_tokens: tuple[str, ...],
    additional_process_id: int | None = None,
    additional_pid_fields: tuple[str, ...] = ("parentpid", "parentprocessid"),
) -> dict[str, Any]:
    marker_normalized = normalize_trace_text(marker)
    lines = [
        line
        for line in dump.splitlines()
        if marker_normalized in normalize_trace_text(line)
    ]
    pid_lines = [line for line in lines if line_has_pid(line, process_id)]
    event_lines = [
        line
        for line in pid_lines
        if any(token in line.casefold() for token in event_tokens)
    ]
    additional_pid_observed = (
        True
        if additional_process_id is None
        else any(
            line_has_pid(
                line,
                additional_process_id,
                fields=additional_pid_fields,
            )
            for line in event_lines
        )
    )
    return {
        "marker_observed": bool(lines),
        "expected_process_id": process_id,
        "pid_attributed": bool(pid_lines),
        "event_class_observed": bool(event_lines),
        "additional_process_id": additional_process_id,
        "additional_process_id_observed": additional_pid_observed,
        "matching_line_count": len(lines),
        "complete": bool(event_lines) and additional_pid_observed,
    }


def classify_dump(
    dump: str,
    *,
    parent_process_id: int,
    child_process_id: int,
    file_marker: str,
    registry_marker: str,
    process_marker: str,
) -> dict[str, Any]:
    file_result = domain_attribution(
        dump,
        marker=file_marker,
        process_id=parent_process_id,
        event_tokens=("fileio/", "fileio ", "file/"),
    )
    registry_result = domain_attribution(
        dump,
        marker=registry_marker,
        process_id=parent_process_id,
        event_tokens=("registry/", "registry "),
    )
    process_result = domain_attribution(
        dump,
        marker=process_marker,
        process_id=child_process_id,
        additional_process_id=parent_process_id,
        event_tokens=("process/start", "process start", "process/dcstart"),
    )
    return {
        "parent_process_id": parent_process_id,
        "child_process_id": child_process_id,
        "file": file_result,
        "registry": registry_result,
        "process_start": process_result,
        "attribution_complete": all(
            item["complete"]
            for item in (file_result, registry_result, process_result)
        ),
    }


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True).encode("utf-8") + b"\n"
    )
    os.replace(temporary, path)


def registry_probe(marker: str) -> None:
    import winreg

    # One unique leaf directly under HKCU\Software avoids leaving parent keys
    # behind after the exact owned probe key is removed.
    relative = rf"Software\{marker}"
    key = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, relative, 0, winreg.KEY_WRITE)
    try:
        winreg.SetValueEx(key, "Probe", 0, winreg.REG_SZ, marker)
        winreg.FlushKey(key)
        winreg.DeleteValue(key, "Probe")
    finally:
        winreg.CloseKey(key)
    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, relative)


def build_self_test(args: argparse.Namespace) -> dict[str, Any]:
    if os.name != "nt":
        raise PREFLIGHT.PreflightError("the frozen Gate 4C observer self-test is Windows-only")
    if not PREFLIGHT.is_elevated():
        raise PREFLIGHT.PreflightError("run the observer self-test from an elevated operator prompt")
    task_root = Path(os.path.abspath(args.task_root))
    task_audit = PREFLIGHT.audit_no_follow(task_root, require_file=False)
    if not task_audit["safe"] or task_root.name != PREFLIGHT.WORK_UNIT:
        raise PREFLIGHT.PreflightError("the self-test root must be the exact Gate 4C task root")

    observer_paths = PREFLIGHT.observer_tool_paths()
    if not PREFLIGHT.observer_toolchain_coherent(observer_paths):
        raise PREFLIGHT.PreflightError(
            "observer tools must come from one coherent Windows Performance Toolkit root"
        )
    wpr = str(observer_paths["wpr"])
    xperf = str(observer_paths["xperf"])
    wpaexporter = str(observer_paths["wpaexporter"])
    host_session = PREFLIGHT.host_session_identity()
    tooling = PREFLIGHT.repository_tool_identity(ROOT)
    observer_tools = {
        "wpr": PREFLIGHT.executable_tool_identity(wpr),
        "xperf": PREFLIGHT.executable_tool_identity(xperf),
        "wpaexporter": PREFLIGHT.executable_tool_identity(wpaexporter),
    }
    if not host_session.get("valid"):
        raise PREFLIGHT.PreflightError("current machine and boot-session identity is unavailable")
    if not tooling.get("valid"):
        raise PREFLIGHT.PreflightError("observer self-test requires a clean, committed tooling revision")
    if not all(item.get("valid") for item in observer_tools.values()):
        raise PREFLIGHT.PreflightError("observer tool identity could not be hash-closed")
    status = command([wpr, "-status"])
    if not wpr_is_not_recording(status):
        raise PREFLIGHT.PreflightError("WPR already has an active or indeterminate recording")

    run_id = f"observer-self-test-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    run_root = task_root / "observer-selftest" / run_id
    run_root.mkdir(parents=True, exist_ok=False)
    trace = run_root / "file-registry-process.etl"
    dump = run_root / "events.csv"
    stats = run_root / "trace-stats.txt"
    probe = run_root / f"file-probe-{uuid.uuid4().hex}.txt"
    registry_marker = f"FacManGate4CRegistryProbe-{uuid.uuid4().hex}"
    process_marker = f"FacManGate4CProcessProbe-{uuid.uuid4().hex}"
    started = False
    commands: list[dict[str, Any]] = []
    errors: list[str] = []
    try:
        start_args = [
            wpr,
            "-start",
            "GeneralProfile",
            "-start",
            "FileIO",
            "-start",
            "Registry",
            "-filemode",
            "-recordtempto",
            str(run_root),
        ]
        start = command(start_args)
        commands.append({"args": start_args, "returncode": start.returncode, "stdout": start.stdout, "stderr": start.stderr})
        if start.returncode != 0:
            raise PREFLIGHT.PreflightError(f"WPR start failed: {start.stderr or start.stdout}")
        started = True

        with probe.open("wb") as handle:
            handle.write((process_marker + "\n").encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        registry_probe(registry_marker)
        child = command(
            [
                sys.executable,
                "-c",
                "import os,sys; print(sys.argv[1], os.getpid(), os.getppid())",
                process_marker,
            ],
            timeout=30,
        )
        commands.append(
            {
                "args": [sys.executable, "-c", "<fixed process probe>", process_marker],
                "returncode": child.returncode,
                "stdout": child.stdout,
                "stderr": child.stderr,
            }
        )
        if child.returncode != 0:
            errors.append("process_probe_failed")
        time.sleep(2)
        stop_args = [wpr, "-stop", str(trace), "FacMan Gate 4C observer self-test", "-skipPdbGen"]
        stop = command(stop_args, timeout=300)
        commands.append({"args": stop_args, "returncode": stop.returncode, "stdout": stop.stdout, "stderr": stop.stderr})
        post_stop_status = command([wpr, "-status"])
        commands.append(
            {
                "args": [wpr, "-status"],
                "returncode": post_stop_status.returncode,
                "stdout": post_stop_status.stdout,
                "stderr": post_stop_status.stderr,
            }
        )
        if wpr_is_not_recording(post_stop_status):
            started = False
        if (
            stop.returncode != 0
            or not trace.is_file()
            or not wpr_is_not_recording(post_stop_status)
        ):
            raise PREFLIGHT.PreflightError(f"WPR stop failed: {stop.stderr or stop.stdout}")
    finally:
        if started:
            cancelled = command([wpr, "-cancel"])
            commands.append(
                {
                    "args": [wpr, "-cancel"],
                    "returncode": cancelled.returncode,
                    "stdout": cancelled.stdout,
                    "stderr": cancelled.stderr,
                }
            )

    dump_result = command([xperf, "-i", str(trace), "-o", str(dump), "-a", "dumper", "-add_fieldnames"], timeout=300)
    commands.append(
        {"args": [xperf, "-i", str(trace), "-o", str(dump), "-a", "dumper", "-add_fieldnames"], "returncode": dump_result.returncode, "stdout": dump_result.stdout, "stderr": dump_result.stderr}
    )
    stats_result = command([xperf, "-i", str(trace), "-o", str(stats), "-a", "tracestats", "-detail"], timeout=300)
    commands.append(
        {"args": [xperf, "-i", str(trace), "-o", str(stats), "-a", "tracestats", "-detail"], "returncode": stats_result.returncode, "stdout": stats_result.stdout, "stderr": stats_result.stderr}
    )
    if dump_result.returncode != 0 or stats_result.returncode != 0 or not dump.is_file() or not stats.is_file():
        errors.append("trace_decode_failed")

    dump_text = dump.read_text(encoding="utf-8", errors="replace") if dump.is_file() else ""
    stats_text = stats.read_text(encoding="utf-8", errors="replace") if stats.is_file() else ""
    child_match = re.fullmatch(
        rf"{re.escape(process_marker)}\s+([0-9]+)\s+([0-9]+)\s*",
        child.stdout,
    )
    child_process_id = int(child_match.group(1)) if child_match else -1
    child_parent_process_id = int(child_match.group(2)) if child_match else -1
    if not child_match or child_parent_process_id != os.getpid():
        errors.append("process_probe_identity_unresolved")
    classification = classify_dump(
        dump_text,
        parent_process_id=os.getpid(),
        child_process_id=child_process_id,
        file_marker=str(probe),
        registry_marker=registry_marker,
        process_marker=process_marker,
    )
    lost_events = parse_lost_events(stats_text)
    if lost_events is None:
        errors.append("lost_event_count_unresolved")
    if lost_events:
        errors.append("events_lost")
    if not classification["attribution_complete"]:
        errors.append("probe_attribution_incomplete")

    core: dict[str, Any] = {
        "schema": PREFLIGHT.OBSERVER_SELF_TEST_SCHEMA,
        "canonicalization_version": "facman.sorted-json.v1",
        "generated_at": utc_now(),
        "work_unit": PREFLIGHT.WORK_UNIT,
        "candidate_revision": PREFLIGHT.CANDIDATE_REVISION,
        "status": "pass" if not errors else "inconclusive",
        "run_id": run_id,
        "elevated": True,
        "machine_binding_id": host_session["machine_binding_id"],
        "boot_identity": host_session["boot_identity"],
        "tooling": tooling,
        "observer_tools": observer_tools,
        "provider": {
            "id": PREFLIGHT.OBSERVER_PROVIDER_ID,
            "revision": PREFLIGHT.OBSERVER_PROVIDER_REVISION,
            "profiles": ["GeneralProfile", "FileIO", "Registry"],
        },
        "probe_process_id": os.getpid(),
        "child_process_id": child_process_id,
        "child_parent_process_id": child_parent_process_id,
        "classification": classification,
        "attribution_complete": classification["attribution_complete"],
        "lost_events": lost_events,
        "errors": errors,
        "commands": commands,
        "artifacts": {
            "trace": {"path": str(trace), "sha256": PREFLIGHT.sha256_file(trace)},
            "dump": {"path": str(dump), "sha256": PREFLIGHT.sha256_file(dump) if dump.is_file() else None},
            "stats": {"path": str(stats), "sha256": PREFLIGHT.sha256_file(stats) if stats.is_file() else None},
        },
    }
    core["self_test_digest"] = PREFLIGHT.digest_value(core)
    output = run_root / "observer-self-test.json"
    atomic_json(output, core)
    core["output"] = str(output)
    return core


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        description="Run the elevated Gate 4C ETW file/registry/process observer self-test."
    )
    value.add_argument("--task-root", required=True, type=Path)
    return value


def main() -> int:
    result = build_self_test(parser().parse_args())
    print(
        f"gate4c-observer-self-test: {result['status']} "
        f"({result['self_test_digest']}; {result['output']})"
    )
    return 0 if result["status"] == "pass" else 3


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError, PREFLIGHT.PreflightError) as exc:
        print(f"gate4c-observer-self-test: {exc}", file=sys.stderr)
        raise SystemExit(2)
