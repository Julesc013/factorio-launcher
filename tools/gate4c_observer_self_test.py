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
import shutil
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


def tool(name: str, fallback: str | None = None) -> str:
    value = shutil.which(name)
    if value:
        return value
    if fallback and Path(fallback).is_file():
        return fallback
    raise PREFLIGHT.PreflightError(f"required observer tool is unavailable: {name}")


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


def normalize_trace_text(value: str) -> str:
    return value.replace("\\\\", "\\").replace("/", "\\").casefold()


def classify_dump(
    dump: str,
    *,
    process_id: int,
    file_marker: str,
    registry_marker: str,
    process_marker: str,
) -> dict[str, Any]:
    normalized = normalize_trace_text(dump)
    pid_tokens = (f",{process_id},", f" {process_id} ", f"pid={process_id}", f"pid: {process_id}")
    file_present = normalize_trace_text(file_marker) in normalized
    registry_present = registry_marker.casefold() in normalized
    process_present = process_marker.casefold() in normalized
    pid_present = any(token.casefold() in normalized for token in pid_tokens)
    relevant_lines = [
        line
        for line in dump.splitlines()
        if file_marker.casefold() in normalize_trace_text(line)
        or registry_marker.casefold() in line.casefold()
        or process_marker.casefold() in line.casefold()
    ]
    pid_attributed = any(str(process_id) in line for line in relevant_lines)
    return {
        "file_probe_observed": file_present,
        "registry_probe_observed": registry_present,
        "process_probe_observed": process_present,
        "process_id_observed": pid_present,
        "probe_event_pid_attributed": pid_attributed,
        "relevant_line_count": len(relevant_lines),
        "attribution_complete": all(
            [file_present, registry_present, process_present, pid_present, pid_attributed]
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

    wpr = tool("wpr.exe")
    xperf = tool(
        "xperf.exe",
        r"C:\Program Files (x86)\Windows Kits\10\Windows Performance Toolkit\xperf.exe",
    )
    status = command([wpr, "-status"])
    if status.returncode != 0 or "is not recording" not in (status.stdout + status.stderr).lower():
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
                "import os,sys; print(sys.argv[1], os.getpid())",
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
        started = False
        if stop.returncode != 0 or not trace.is_file():
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
    classification = classify_dump(
        dump_text,
        process_id=os.getpid(),
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
        "schema": "factorio.gate4c_observer_self_test.v1",
        "canonicalization_version": "facman.sorted-json.v1",
        "generated_at": utc_now(),
        "work_unit": PREFLIGHT.WORK_UNIT,
        "status": "pass" if not errors else "inconclusive",
        "run_id": run_id,
        "elevated": True,
        "provider": {
            "id": "factorio.play.process-tree-observer",
            "revision": "gate4c-etw-file-registry-process.v1",
            "profiles": ["GeneralProfile", "FileIO", "Registry"],
        },
        "probe_process_id": os.getpid(),
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
