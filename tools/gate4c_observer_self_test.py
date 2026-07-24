# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Elevated, non-Factorio self-test for the Gate 4C ETW observer prerequisites."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import io
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
        r"dropped\s+([0-9]+)\s+events",
    )
    values: list[int] = []
    for pattern in patterns:
        values.extend(int(item) for item in re.findall(pattern, stats, flags=re.IGNORECASE))
    return max(values) if values else None


def resolve_lost_events(
    active_collector_status: str,
    completion_output: str,
) -> tuple[int | None, dict[str, Any]]:
    active = parse_lost_events(active_collector_status)
    completion = parse_lost_events(completion_output)
    resolved = None if active is None else max(active, completion or 0)
    return resolved, {
        "active_collector_events_lost": active,
        "completion_reported_events_lost": completion,
        "active_collector_count_required": True,
        "completion_loss_report_present": completion is not None,
        "resolved": resolved is not None,
    }


def wpr_is_not_recording(result: subprocess.CompletedProcess[str]) -> bool:
    return result.returncode == 0 and "is not recording" in (
        result.stdout + result.stderr
    ).casefold()


def wpr_start_arguments(wpr: str, profile: Path, run_root: Path) -> list[str]:
    selector = (
        f"{profile}!{PREFLIGHT.OBSERVER_PROFILE_NAME}."
        f"{PREFLIGHT.OBSERVER_PROFILE_DETAIL_LEVEL}"
    )
    return [
        wpr,
        "-start",
        selector,
        "-filemode",
        "-recordtempto",
        str(run_root),
    ]


def wpr_collector_status_arguments(wpr: str) -> list[str]:
    return [wpr, "-status", "collectors", "-details"]


def normalize_trace_text(value: str) -> str:
    return value.replace("\\\\", "\\").replace("/", "\\").casefold()


def xperf_rows(dump: str) -> list[tuple[str, ...]]:
    rows: list[tuple[str, ...]] = []
    for row in csv.reader(io.StringIO(dump)):
        fields = tuple(field.strip() for field in row)
        if not fields or not fields[0] or fields[0] in {"BeginHeader", "EndHeader"}:
            continue
        rows.append(fields)
    return rows


def process_name_pid(value: str) -> int | None:
    match = re.search(r"\(\s*([0-9]+)\s*\)\s*$", value)
    return int(match.group(1)) if match else None


def positional_domain_attribution(
    rows: list[tuple[str, ...]],
    *,
    marker: str,
    process_id: int,
    process_field: int,
    event_prefixes: tuple[str, ...] = (),
    exact_events: tuple[str, ...] = (),
    additional_process_id: int | None = None,
    additional_process_field: int | None = None,
) -> dict[str, Any]:
    marker_normalized = normalize_trace_text(marker)
    marker_rows = [
        row
        for row in rows
        if any(marker_normalized in normalize_trace_text(field) for field in row)
    ]
    event_rows = [
        row
        for row in marker_rows
        if (
            row[0].casefold() in exact_events
            or any(row[0].casefold().startswith(prefix) for prefix in event_prefixes)
        )
    ]
    pid_rows = [
        row
        for row in event_rows
        if len(row) > process_field
        and process_name_pid(row[process_field]) == process_id
    ]
    additional_pid_observed = (
        True
        if additional_process_id is None
        else any(
            additional_process_field is not None
            and len(row) > additional_process_field
            and row[additional_process_field].strip() == str(additional_process_id)
            for row in pid_rows
        )
    )
    return {
        "format": "xperf_dumper_csv",
        "marker_observed": bool(marker_rows),
        "expected_process_id": process_id,
        "process_field": process_field,
        "pid_attributed": bool(pid_rows),
        "event_class_observed": bool(event_rows),
        "matching_event_classes": sorted({row[0] for row in event_rows}),
        "additional_process_id": additional_process_id,
        "additional_process_field": additional_process_field,
        "additional_process_id_observed": additional_pid_observed,
        "matching_line_count": len(marker_rows),
        "complete": bool(pid_rows) and additional_pid_observed,
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
    rows = xperf_rows(dump)
    file_result = positional_domain_attribution(
        rows,
        marker=file_marker,
        process_id=parent_process_id,
        process_field=2,
        event_prefixes=("fileio",),
    )
    registry_result = positional_domain_attribution(
        rows,
        marker=registry_marker,
        process_id=parent_process_id,
        process_field=3,
        event_prefixes=("reg",),
    )
    process_result = positional_domain_attribution(
        rows,
        marker=process_marker,
        process_id=child_process_id,
        process_field=2,
        additional_process_id=parent_process_id,
        additional_process_field=3,
        exact_events=("p-start",),
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
    profile = PREFLIGHT.observer_profile_identity(ROOT)
    provider = PREFLIGHT.observer_provider_identity(ROOT)
    profile_path = ROOT / PREFLIGHT.OBSERVER_PROFILE_RELATIVE_PATH
    observer_tools = {
        "wpr": PREFLIGHT.executable_tool_identity(wpr),
        "xperf": PREFLIGHT.executable_tool_identity(xperf),
        "wpaexporter": PREFLIGHT.executable_tool_identity(wpaexporter),
    }
    if not host_session.get("valid"):
        raise PREFLIGHT.PreflightError("current machine and boot-session identity is unavailable")
    if not tooling.get("valid"):
        raise PREFLIGHT.PreflightError("observer self-test requires a clean, committed tooling revision")
    if not profile.get("valid"):
        raise PREFLIGHT.PreflightError("observer profile does not match the reviewed closed contract")
    if not provider.get("valid"):
        raise PREFLIGHT.PreflightError("observer provider identity is not valid")
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
        start_args = wpr_start_arguments(wpr, profile_path, run_root)
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
        collector_status_args = wpr_collector_status_arguments(wpr)
        collector_status = command(collector_status_args)
        commands.append(
            {
                "args": collector_status_args,
                "returncode": collector_status.returncode,
                "stdout": collector_status.stdout,
                "stderr": collector_status.stderr,
            }
        )
        if collector_status.returncode != 0:
            errors.append("active_collector_status_failed")
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
    completion_loss_text = "\n".join(
        (
            stop.stdout,
            stop.stderr,
            dump_result.stdout,
            dump_result.stderr,
            stats_result.stdout,
            stats_result.stderr,
            stats_text,
        )
    )
    active_loss_text = "\n".join(
        (collector_status.stdout, collector_status.stderr)
    )
    lost_events, loss_evidence = resolve_lost_events(
        active_loss_text,
        completion_loss_text,
    )
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
        "provider": provider,
        "probe_process_id": os.getpid(),
        "child_process_id": child_process_id,
        "child_parent_process_id": child_parent_process_id,
        "classification": classification,
        "attribution_complete": classification["attribution_complete"],
        "lost_events": lost_events,
        "loss_evidence": loss_evidence,
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
