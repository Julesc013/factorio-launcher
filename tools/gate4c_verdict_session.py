# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Evidence-only capture backend for the Gate 4C native verdict harness.

This tool can start and finish the frozen ETW observation provider.  It cannot
issue a permit, start Factorio, decide the human verdict, or enable Play.  The
reviewed native candidate owns those boundaries.
"""

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
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]


def _load_tool(name: str, relative: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PREFLIGHT = _load_tool("gate4c_verdict_preflight", "tools/gate4c_verdict_preflight.py")
SELFTEST = _load_tool("gate4c_observer_self_test", "tools/gate4c_observer_self_test.py")

CAPTURE_SCHEMA = "factorio.gate4c_observer_capture.v1"
CLASSIFICATION_SCHEMA = "factorio.gate4c_effect_classification.v1"
OBSERVATION_SCHEMA = "factorio.play_candidate_observation.v1"
BOUND_PROVIDER_REVISION = "bound-observation-artifact.v1"
OBSERVER_START_PROBE_SCHEMA = "factorio.gate4c_observer_start_probe.v1"
OBSERVER_START_REPAIR_WORK_UNIT = (
    "FACMAN-HERMETIC-STANDALONE-PLAY-OBSERVER-START-REPAIR-01"
)
MUTATING_FILE_EVENTS = {
    "fileiocreate",
    "fileiowrite",
    "fileiosetinfo",
    "fileiodelete",
    "fileiorename",
    "fileiosetsecurity",
    "fileiosetea",
}
MUTATING_REGISTRY_EVENTS = {
    "regcreatekey",
    "regdeletekey",
    "regsetvalue",
    "regdeletevalue",
    "regsetinformation",
    "regflush",
}


class SessionError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def lowercase_digest(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def digest_value(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def observation_output_digest(observation: dict[str, Any]) -> str:
    """Match the reviewed C++ observation encoder's canonical field order."""
    effects = sorted(
        observation["effects"],
        key=lambda item: (
            item["sequence"],
            item["domain"],
            item["logical_resource_id"],
        ),
    )
    effect_values = [
        {
            "sequence": item["sequence"],
            "domain": item["domain"],
            "process_identity_digest": item["process_identity_digest"],
            "target_identity_digest": item["target_identity_digest"],
            "logical_resource_id": item["logical_resource_id"],
            "classification": item["classification"],
        }
        for item in effects
    ]
    gap = observation["gaps"]
    gaps = {
        "lost_events": gap["lost_events"],
        "buffer_overflow": gap["buffer_overflow"],
        "unknown_process_identity": gap["unknown_process_identity"],
        "unresolved_target": gap["unresolved_target"],
        "delayed_events": gap["delayed_events"],
        "attribution_gap": gap["attribution_gap"],
        "provider_failure": gap["provider_failure"],
    }
    core = {
        "schema": observation["schema"],
        "provider_id": observation["provider_id"],
        "provider_revision": observation["provider_revision"],
        "plan_digest": observation["plan_digest"],
        "capture_session_digest": observation["capture_session_digest"],
        "raw_artifact_digest": observation["raw_artifact_digest"],
        "active_before_process": observation["active_before_process"],
        "capture_complete": observation["capture_complete"],
        "gaps": gaps,
        "effects": effect_values,
    }
    encoded = json.dumps(
        core,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True).encode("utf-8")
        + b"\n"
    )
    os.replace(temporary, path)


def exact_task_root(value: Path) -> Path:
    result = Path(os.path.abspath(value))
    audit = PREFLIGHT.audit_no_follow(result, require_file=False)
    if not audit["safe"] or result.name != PREFLIGHT.WORK_UNIT:
        raise SessionError("task root is not the exact Gate 4C root")
    return result


def exact_operation_root(task_root: Path, value: Path) -> Path:
    result = Path(os.path.abspath(value))
    expected_parent = task_root / "workspace" / "temporary"
    try:
        result.relative_to(expected_parent)
    except ValueError as exc:
        raise SessionError("operation root must remain under the Gate 4C workspace temporary root") from exc
    if result.parent != expected_parent or not result.name.startswith("gate4c-"):
        raise SessionError("operation root must be one exact Gate 4C operation")
    audit = PREFLIGHT.audit_no_follow(result, require_file=False)
    owner = result / ".facman-gate4c-verdict-owner"
    owner_audit = PREFLIGHT.audit_no_follow(owner, require_file=True)
    if (
        not audit["safe"]
        or not owner_audit["safe"]
        or owner.read_text(encoding="utf-8").splitlines()[:1]
        != [PREFLIGHT.WORK_UNIT]
    ):
        raise SessionError("operation root crosses an unsafe path boundary")
    return result


def command_record(result: Any, args: list[str]) -> dict[str, Any]:
    return {
        "args": args,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def observer_start_probe(args: argparse.Namespace) -> dict[str, Any]:
    """Exercise the exact WPR start boundary without a permit or Factorio."""
    if os.name != "nt":
        raise SessionError("the Gate 4C observer-start probe is Windows-only")
    if not PREFLIGHT.is_elevated():
        raise SessionError("the Gate 4C observer-start probe requires elevation")
    task_root = Path(os.path.abspath(args.task_root))
    task_audit = PREFLIGHT.audit_no_follow(task_root, require_file=False)
    if (
        not task_audit["safe"]
        or task_root.name != OBSERVER_START_REPAIR_WORK_UNIT
    ):
        raise SessionError("probe root is not the exact observer-start repair root")
    if re.fullmatch(r"gate4c-observer-start-probe-[a-z0-9-]+", args.probe_id) is None:
        raise SessionError("observer-start probe identity is invalid")
    evidence_root = task_root / "evidence" / "observer-start-probes"
    run_root = task_root / "observer-start-probes" / args.probe_id
    expected_out = evidence_root / f"{args.probe_id}.json"
    if (
        os.path.normcase(os.path.abspath(args.out))
        != os.path.normcase(os.path.abspath(expected_out))
        or expected_out.exists()
        or run_root.exists()
    ):
        raise SessionError("observer-start probe outputs are not new and exact")
    evidence_root.mkdir(parents=True, exist_ok=True)
    run_root.mkdir(parents=True, exist_ok=False)
    if (
        not PREFLIGHT.audit_no_follow(evidence_root, require_file=False)["safe"]
        or not PREFLIGHT.audit_no_follow(run_root, require_file=False)["safe"]
    ):
        raise SessionError("observer-start probe output boundary is unsafe")

    observer_paths = PREFLIGHT.observer_tool_paths()
    if not PREFLIGHT.observer_toolchain_coherent(observer_paths):
        raise SessionError("observer tools are not one coherent reviewed toolchain")
    profile = PREFLIGHT.observer_profile_identity(ROOT)
    provider = PREFLIGHT.observer_provider_identity(ROOT)
    tooling = PREFLIGHT.repository_tool_identity(ROOT)
    if not profile.get("valid") or not provider.get("valid"):
        raise SessionError("observer profile or provider identity is invalid")

    wpr = str(observer_paths["wpr"])
    trace = run_root / "observer-start-probe.etl"
    commands: list[dict[str, Any]] = []
    errors: list[str] = []
    recording_started = False

    def probe_command(
        arguments: list[str],
        *,
        timeout: int = 180,
    ) -> subprocess.CompletedProcess[str] | None:
        try:
            result = SELFTEST.command(arguments, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            commands.append(
                {
                    "args": arguments,
                    "returncode": None,
                    "stdout": str(exc.stdout or ""),
                    "stderr": str(exc.stderr or ""),
                    "timed_out": True,
                }
            )
            return None
        record = command_record(result, arguments)
        record["timed_out"] = False
        commands.append(record)
        return result

    try:
        initial_status = probe_command([wpr, "-status"])
        if initial_status is None:
            errors.append("wpr_status_timed_out_before_start")
        elif not SELFTEST.wpr_is_not_recording(initial_status):
            errors.append("wpr_busy_or_indeterminate_before_start")
        else:
            start_args = SELFTEST.wpr_start_arguments(
                wpr,
                ROOT / PREFLIGHT.OBSERVER_PROFILE_RELATIVE_PATH,
                run_root,
            )
            started = probe_command(start_args)
            if started is None:
                errors.append("wpr_start_timed_out")
            elif started.returncode != 0:
                errors.append("wpr_start_failed")
            else:
                recording_started = True
                live_status = probe_command([wpr, "-status"])
                if (
                    live_status is None
                    or live_status.returncode != 0
                    or SELFTEST.wpr_is_not_recording(live_status)
                ):
                    errors.append("wpr_not_active_after_start")

        if recording_started:
            stop_args = [
                wpr,
                "-stop",
                str(trace),
                "FacMan Gate 4C observer-start repair probe",
                "-skipPdbGen",
            ]
            stopped = probe_command(stop_args, timeout=300)
            if stopped is None:
                errors.append("wpr_stop_timed_out")
            elif stopped.returncode != 0:
                errors.append("wpr_stop_failed")
            post_status = probe_command([wpr, "-status"])
            if post_status is not None:
                recording_started = not SELFTEST.wpr_is_not_recording(post_status)
            if not trace.is_file():
                errors.append("wpr_trace_missing")
    finally:
        if recording_started:
            cancelled = probe_command([wpr, "-cancel"])
            final_status = probe_command([wpr, "-status"])
            recording_started = (
                final_status is None
                or not SELFTEST.wpr_is_not_recording(final_status)
            )
            if cancelled is None:
                errors.append("wpr_cancel_timed_out")
            if recording_started:
                errors.append("wpr_recording_remained_active")

    core: dict[str, Any] = {
        "schema": OBSERVER_START_PROBE_SCHEMA,
        "canonicalization_version": "facman.sorted-json.v1",
        "work_unit": OBSERVER_START_REPAIR_WORK_UNIT,
        "probe_id": args.probe_id,
        "generated_at": utc_now(),
        "elevated": True,
        "process_id": os.getpid(),
        "parent_process_id": os.getppid(),
        "machine_session": PREFLIGHT.host_session_identity(),
        "provider": provider,
        "profile": profile,
        "tooling": tooling,
        "observer_tools": {
            key: PREFLIGHT.executable_tool_identity(path)
            for key, path in observer_paths.items()
        },
        "commands": commands,
        "trace": {
            "path": str(trace),
            "present": trace.is_file(),
            "sha256": PREFLIGHT.sha256_file(trace) if trace.is_file() else None,
        },
        "recording_active_after_probe": recording_started,
        "errors": errors,
        "status": "pass" if not errors else "inconclusive",
    }
    core["probe_digest"] = digest_value(core)
    atomic_json(expected_out, core)
    return core


def start_capture(args: argparse.Namespace) -> dict[str, Any]:
    if os.name != "nt":
        raise SessionError("the Gate 4C capture backend is Windows-only")
    if not PREFLIGHT.is_elevated():
        raise SessionError("the Gate 4C capture backend requires elevation")
    task_root = exact_task_root(args.task_root)
    operation_root = exact_operation_root(task_root, args.operation_root)
    if not lowercase_digest(args.preflight_digest):
        raise SessionError("capture requires the exact ready-preflight digest")
    observation_root = operation_root / "process" / "observation"
    observation_audit = PREFLIGHT.audit_no_follow(
        observation_root, require_file=False
    )
    expected_token = observation_root / "capture-token.json"
    if (
        not observation_audit["safe"]
        or any(observation_root.iterdir())
        or os.path.normcase(os.path.abspath(args.out))
        != os.path.normcase(os.path.abspath(expected_token))
    ):
        raise SessionError("prepared observation root is missing, unsafe, or not empty")

    observer_paths = PREFLIGHT.observer_tool_paths()
    if not PREFLIGHT.observer_toolchain_coherent(observer_paths):
        raise SessionError("observer tools are not one coherent reviewed toolchain")
    profile = PREFLIGHT.observer_profile_identity(ROOT)
    provider = PREFLIGHT.observer_provider_identity(ROOT)
    tooling = PREFLIGHT.repository_tool_identity(ROOT)
    if not profile.get("valid") or not provider.get("valid") or not tooling.get("valid"):
        raise SessionError("capture tooling or profile identity is not valid")
    wpr = str(observer_paths["wpr"])
    status = SELFTEST.command([wpr, "-status"])
    if not SELFTEST.wpr_is_not_recording(status):
        raise SessionError("WPR already has an active or indeterminate recording")

    trace = observation_root / "process-tree.etl"
    dump = observation_root / "events.csv"
    stats = observation_root / "trace-stats.txt"
    artifact = observation_root / "observation.json"
    start_args = SELFTEST.wpr_start_arguments(
        wpr,
        ROOT / PREFLIGHT.OBSERVER_PROFILE_RELATIVE_PATH,
        observation_root,
    )
    started = SELFTEST.command(start_args)
    if started.returncode != 0:
        raise SessionError(f"WPR start failed: {started.stderr or started.stdout}")
    live_status = SELFTEST.command([wpr, "-status"])
    if SELFTEST.wpr_is_not_recording(live_status):
        SELFTEST.command([wpr, "-cancel"])
        raise SessionError("WPR did not remain active after start")

    core: dict[str, Any] = {
        "schema": CAPTURE_SCHEMA,
        "canonicalization_version": "facman.sorted-json.v1",
        "started_at": utc_now(),
        "preflight_digest": args.preflight_digest,
        "operation_id": operation_root.name,
        "operation_root": str(operation_root),
        # The independently bound ETW observer is not part of the subject
        # process tree. Its own WPR bookkeeping is covered by the independent
        # protected-state comparison. The FacMan launch-provider process is
        # an observed subject alongside Factorio and supervised children.
        "provider_process_ids": [int(args.launch_provider_process_id)],
        "provider": provider,
        "profile": profile,
        "tooling": tooling,
        "observer_tools": {
            key: PREFLIGHT.executable_tool_identity(path)
            for key, path in observer_paths.items()
        },
        "artifacts": {
            "trace": str(trace),
            "dump": str(dump),
            "stats": str(stats),
            "observation": str(artifact),
        },
        "wpr_start": command_record(started, start_args),
        "active": True,
    }
    core["capture_session_digest"] = digest_value(core)
    atomic_json(expected_token, core)
    return core


def normalized_windows_path(value: str) -> str | None:
    text = value.strip().strip('"').replace("/", "\\")
    if not text:
        return None
    if re.match(r"^[A-Za-z]:\\", text):
        return str(PureWindowsPath(text)).casefold()
    if text.startswith("\\\\"):
        return str(PureWindowsPath(text)).casefold()
    return None


def path_is_within(candidate: str, root: str) -> bool:
    candidate_path = PureWindowsPath(candidate)
    root_path = PureWindowsPath(root)
    try:
        candidate_path.relative_to(root_path)
        return True
    except ValueError:
        return False


def volume_mappings(rows: Iterable[tuple[str, ...]]) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    for row in rows:
        if row[0].casefold() != "volumemapping" or len(row) < 4:
            continue
        nt_path = row[2].strip().rstrip("\\").casefold()
        dos_path = row[3].strip().rstrip("\\").casefold()
        if nt_path and dos_path:
            result.append((nt_path, dos_path))
    result.sort(key=lambda item: len(item[0]), reverse=True)
    return result


def resolve_file_target(value: str, mappings: list[tuple[str, str]]) -> str | None:
    direct = normalized_windows_path(value)
    if direct is not None:
        return direct
    text = value.strip().replace("/", "\\").casefold()
    for nt_path, dos_path in mappings:
        if text == nt_path or text.startswith(nt_path + "\\"):
            return dos_path + text[len(nt_path) :]
    return None


def xperf_headers_and_rows(text: str) -> tuple[dict[str, tuple[str, ...]], list[tuple[str, ...]]]:
    headers: dict[str, tuple[str, ...]] = {}
    rows: list[tuple[str, ...]] = []
    in_header = False
    for raw in csv.reader(io.StringIO(text)):
        row = tuple(field.strip() for field in raw)
        if not row:
            continue
        if row[0] == "BeginHeader":
            in_header = True
            continue
        if row[0] == "EndHeader":
            in_header = False
            continue
        if not row[0]:
            continue
        key = row[0].casefold()
        if in_header:
            headers[key] = row
        else:
            rows.append(row)
    return headers, rows


def header_index(
    headers: dict[str, tuple[str, ...]],
    event: str,
    name: str,
    *,
    last: bool = False,
) -> int | None:
    header = headers.get(event.casefold())
    if header is None:
        return None
    matches = [index for index, value in enumerate(header) if value.casefold() == name.casefold()]
    if not matches:
        return None
    return matches[-1] if last else matches[0]


def event_timestamp(
    headers: dict[str, tuple[str, ...]],
    row: tuple[str, ...],
) -> int | None:
    index = header_index(headers, row[0], "TimeStamp")
    if index is None or len(row) <= index:
        return None
    try:
        return int(row[index])
    except ValueError:
        return None


def attributed_process_intervals(
    headers: dict[str, tuple[str, ...]],
    rows: list[tuple[str, ...]],
    primary_pid: int,
    primary_image_name: str,
    provider_process_ids: Iterable[int],
) -> tuple[dict[int, list[tuple[int, int | None]]], bool]:
    starts: list[tuple[int, int, int, str]] = []
    ends: dict[int, list[int]] = {}
    for row in rows:
        event = row[0].casefold()
        if event not in {"p-start", "p-end"}:
            continue
        process_index = header_index(headers, row[0], "Process Name ( PID)")
        timestamp = event_timestamp(headers, row)
        if process_index is None or len(row) <= process_index or timestamp is None:
            continue
        pid = SELFTEST.process_name_pid(row[process_index])
        if pid is None:
            continue
        if event == "p-end":
            ends.setdefault(pid, []).append(timestamp)
            continue
        parent_index = header_index(headers, row[0], "ParentPID")
        if parent_index is None or len(row) <= parent_index:
            continue
        try:
            parent = int(row[parent_index])
        except ValueError:
            continue
        raw_name = row[process_index]
        image_name = raw_name.rsplit(" (", 1)[0].strip().casefold()
        starts.append((timestamp, pid, parent, image_name))
    starts.sort()
    for values in ends.values():
        values.sort()

    def interval_end(pid: int, started: int) -> int | None:
        next_start = min(
            (
                timestamp
                for timestamp, candidate, _, _ in starts
                if candidate == pid and timestamp > started
            ),
            default=None,
        )
        for ended in ends.get(pid, []):
            if ended >= started and (next_start is None or ended < next_start):
                return ended
        return next_start

    intervals: dict[int, list[tuple[int, int | None]]] = {
        int(pid): [(-1, None)] for pid in provider_process_ids
    }
    primary_records = [
        item
        for item in starts
        if item[1] == primary_pid and item[3] == primary_image_name.casefold()
    ]
    if not primary_records:
        return intervals, False
    primary_start = primary_records[-1][0]
    intervals.setdefault(primary_pid, []).append(
        (primary_start, interval_end(primary_pid, primary_start))
    )

    def active(pid: int, timestamp: int) -> bool:
        return any(
            started <= timestamp and (ended is None or timestamp <= ended)
            for started, ended in intervals.get(pid, [])
        )

    changed = True
    while changed:
        changed = False
        for started, pid, parent, _ in starts:
            candidate = (started, interval_end(pid, started))
            if active(parent, started) and candidate not in intervals.get(pid, []):
                intervals.setdefault(pid, []).append(candidate)
                changed = True
    for values in intervals.values():
        values.sort(key=lambda item: item[0])
    return intervals, True


def load_roots(path: Path) -> dict[str, list[dict[str, str]]]:
    audit = PREFLIGHT.audit_no_follow(path, require_file=True)
    if not audit["safe"]:
        raise SessionError("classification roots artifact is unsafe")
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema") != CLASSIFICATION_SCHEMA:
        raise SessionError("classification roots schema is unsupported")
    exact_keys = {"schema", "writable_filesystem", "protected_filesystem"}
    if set(value) != exact_keys:
        raise SessionError("classification roots object is not closed")
    for key in ("writable_filesystem", "protected_filesystem"):
        if not isinstance(value[key], list):
            raise SessionError("classification root list is malformed")
        for item in value[key]:
            if set(item) != {"resource_id", "path"}:
                raise SessionError("classification root entry is not closed")
            if not isinstance(item["resource_id"], str) or not isinstance(item["path"], str):
                raise SessionError("classification root entry is malformed")
    return value


def classify_filesystem_target(
    target: str,
    roots: dict[str, list[dict[str, str]]],
) -> tuple[str, str]:
    normalized = normalized_windows_path(target)
    if normalized is None:
        return "effects.external_filesystem", "unresolved"
    for item in roots["writable_filesystem"]:
        root = normalized_windows_path(item["path"])
        if root is not None and path_is_within(normalized, root):
            return item["resource_id"], "writable"
    for item in roots["protected_filesystem"]:
        root = normalized_windows_path(item["path"])
        if root is not None and path_is_within(normalized, root):
            return item["resource_id"], "protected"
    return "effects.external_filesystem", "forbidden"


def kcb_names(rows: Iterable[tuple[str, ...]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for row in rows:
        if row[0].casefold() != "regkcbcreate" or len(row) < 4:
            continue
        result[row[2].casefold()] = row[3].strip()
    return result


def registry_target(
    headers: dict[str, tuple[str, ...]],
    row: tuple[str, ...],
    kcbs: dict[str, str],
) -> str | None:
    key_index = header_index(headers, row[0], "Key Name", last=True)
    kcb_index = header_index(headers, row[0], "KCB")
    key_name = row[key_index].strip() if key_index is not None and len(row) > key_index else ""
    kcb = row[kcb_index].casefold() if kcb_index is not None and len(row) > kcb_index else ""
    base = kcbs.get(kcb, "")
    if key_name.startswith("\\Registry\\") or key_name.startswith("HKEY_"):
        return key_name
    if base and key_name:
        return base.rstrip("\\") + "\\" + key_name.lstrip("\\")
    return base or key_name or None


def process_identity_digest(
    pid: int,
    primary_pid: int,
    primary_stable: str,
    interval_start: int,
) -> str:
    if pid == primary_pid:
        return sha256_text("process-identity:" + primary_stable)
    return sha256_text(f"process-child:{primary_pid}:{pid}:{interval_start}")


def observation_effects(
    dump_text: str,
    *,
    primary_pid: int,
    primary_stable_identity: str,
    executable: str,
    roots: dict[str, list[dict[str, str]]],
    provider_process_ids: Iterable[int] = (),
) -> tuple[list[dict[str, Any]], dict[str, bool]]:
    headers, rows = xperf_headers_and_rows(dump_text)
    intervals, primary_start = attributed_process_intervals(
        headers,
        rows,
        primary_pid,
        PureWindowsPath(executable).name,
        provider_process_ids,
    )
    mappings = volume_mappings(rows)
    kcbs = kcb_names(rows)
    effects: list[dict[str, Any]] = [
        {
            "sequence": 0,
            "domain": "process",
            "process_identity_digest": process_identity_digest(
                primary_pid, primary_pid, primary_stable_identity, 0
            ),
            "target_identity_digest": sha256_text(
                "process-image:" + str(PureWindowsPath(executable)).casefold()
            ),
            "logical_resource_id": "process.primary",
            "classification": "writable",
        }
    ]
    unresolved_target = False
    attribution_gap = not primary_start
    sequence = 1
    for row in rows:
        event = row[0].casefold()
        if event not in MUTATING_FILE_EVENTS and event not in MUTATING_REGISTRY_EVENTS:
            continue
        if event == "fileiocreate":
            options_index = header_index(headers, row[0], "Options")
            raw_options = (
                row[options_index]
                if options_index is not None and len(row) > options_index
                else ""
            )
            try:
                create_disposition = (int(raw_options, 0) >> 24) & 0xFF
            except ValueError:
                create_disposition = -1
                attribution_gap = True
            # FILE_OPEN (1) is read/open-only. Every other disposition can
            # create, replace, truncate, or supersede persistent state.
            if create_disposition == 1:
                continue
        process_index = header_index(headers, row[0], "Process Name ( PID)")
        timestamp = event_timestamp(headers, row)
        if process_index is None or len(row) <= process_index or timestamp is None:
            attribution_gap = True
            continue
        pid = SELFTEST.process_name_pid(row[process_index])
        matching_intervals = (
            []
            if pid is None
            else [
                value
                for value in intervals.get(pid, [])
                if value[0] <= timestamp
                and (value[1] is None or timestamp <= value[1])
            ]
        )
        if pid is None or not matching_intervals:
            continue
        interval_start = max(value[0] for value in matching_intervals)
        if event in MUTATING_FILE_EVENTS:
            target_index = header_index(headers, row[0], "FileName", last=True)
            raw_target = row[target_index] if target_index is not None and len(row) > target_index else ""
            target = resolve_file_target(raw_target, mappings)
            if target is None:
                unresolved_target = True
                logical_resource, classification = "effects.external_filesystem", "unresolved"
                target_text = raw_target or "unresolved"
            else:
                logical_resource, classification = classify_filesystem_target(target, roots)
                target_text = target
            domain = "filesystem"
        else:
            target = registry_target(headers, row, kcbs)
            if target is None:
                unresolved_target = True
                target = "unresolved"
                classification = "unresolved"
            else:
                classification = "forbidden"
            logical_resource = "effects.external_registry"
            target_text = target
            domain = "registry"
        effects.append(
            {
                "sequence": sequence,
                "domain": domain,
                "process_identity_digest": process_identity_digest(
                    pid, primary_pid, primary_stable_identity, interval_start
                ),
                "target_identity_digest": sha256_text(
                    f"{domain}-target:{str(target_text).casefold()}"
                ),
                "logical_resource_id": logical_resource,
                "classification": classification,
            }
        )
        sequence += 1
    return effects, {
        "unknown_process_identity": not primary_start,
        "unresolved_target": unresolved_target,
        "attribution_gap": attribution_gap,
    }


def finish_capture(args: argparse.Namespace) -> dict[str, Any]:
    if os.name != "nt" or not PREFLIGHT.is_elevated():
        raise SessionError("finishing the Gate 4C capture requires an elevated Windows session")
    task_root = exact_task_root(args.task_root)
    operation_root = exact_operation_root(task_root, args.operation_root)
    expected_token = operation_root / "process" / "observation" / "capture-token.json"
    token_audit = PREFLIGHT.audit_no_follow(args.capture_token, require_file=True)
    if (
        not token_audit["safe"]
        or os.path.normcase(os.path.abspath(args.capture_token))
        != os.path.normcase(os.path.abspath(expected_token))
    ):
        raise SessionError("capture token is unsafe")
    token = json.loads(args.capture_token.read_text(encoding="utf-8"))
    claimed = token.get("capture_session_digest")
    core = dict(token)
    core.pop("capture_session_digest", None)
    if (
        token.get("schema") != CAPTURE_SCHEMA
        or token.get("operation_root") != str(operation_root)
        or token.get("active") is not True
        or not lowercase_digest(claimed)
        or digest_value(core) != claimed
    ):
        raise SessionError("capture token identity is invalid")
    if not lowercase_digest(args.plan_digest):
        raise SessionError("finish requires the exact reviewed plan digest")
    if args.process_id <= 0 or not args.process_stable_identity:
        raise SessionError("finish requires the restart-safe primary process identity")
    if not PREFLIGHT.path_is_within(args.classification_roots, task_root):
        raise SessionError("classification roots are outside the exact Gate 4C root")
    roots = load_roots(args.classification_roots)

    observer_paths = PREFLIGHT.observer_tool_paths()
    if not PREFLIGHT.observer_toolchain_coherent(observer_paths):
        raise SessionError("observer toolchain changed during capture")
    wpr = str(observer_paths["wpr"])
    xperf = str(observer_paths["xperf"])
    trace = Path(token["artifacts"]["trace"])
    dump = Path(token["artifacts"]["dump"])
    stats = Path(token["artifacts"]["stats"])
    observation_path = Path(token["artifacts"]["observation"])
    commands: list[dict[str, Any]] = []
    errors: list[str] = []

    time.sleep(args.quiescence_seconds)
    collector_args = SELFTEST.wpr_collector_status_arguments(wpr)
    collector = SELFTEST.command(collector_args)
    commands.append(command_record(collector, collector_args))
    if collector.returncode != 0:
        errors.append("active_collector_status_failed")
    stop_args = [
        wpr,
        "-stop",
        str(trace),
        f"FacMan Gate 4C {operation_root.name}",
        "-skipPdbGen",
    ]
    stop = SELFTEST.command(stop_args, timeout=300)
    commands.append(command_record(stop, stop_args))
    post = SELFTEST.command([wpr, "-status"])
    commands.append(command_record(post, [wpr, "-status"]))
    if stop.returncode != 0 or not SELFTEST.wpr_is_not_recording(post) or not trace.is_file():
        SELFTEST.command([wpr, "-cancel"])
        raise SessionError(f"WPR stop failed: {stop.stderr or stop.stdout}")

    dump_args = [xperf, "-i", str(trace), "-o", str(dump), "-a", "dumper", "-add_fieldnames"]
    dump_result = SELFTEST.command(dump_args, timeout=300)
    commands.append(command_record(dump_result, dump_args))
    stats_args = [xperf, "-i", str(trace), "-o", str(stats), "-a", "tracestats", "-detail"]
    stats_result = SELFTEST.command(stats_args, timeout=300)
    commands.append(command_record(stats_result, stats_args))
    if (
        dump_result.returncode != 0
        or stats_result.returncode != 0
        or not dump.is_file()
        or not stats.is_file()
    ):
        errors.append("trace_decode_failed")

    dump_text = dump.read_text(encoding="utf-8", errors="replace") if dump.is_file() else ""
    stats_text = stats.read_text(encoding="utf-8", errors="replace") if stats.is_file() else ""
    lost_events, loss_evidence = SELFTEST.resolve_lost_events(
        collector.stdout + "\n" + collector.stderr,
        "\n".join(
            (
                stop.stdout,
                stop.stderr,
                dump_result.stdout,
                dump_result.stderr,
                stats_result.stdout,
                stats_result.stderr,
                stats_text,
            )
        ),
    )
    if lost_events is None:
        errors.append("lost_event_count_unresolved")
    elif lost_events != 0:
        errors.append("observer_events_lost")
    provider_process_ids = {
        int(value) for value in token.get("provider_process_ids", [])
    }
    effects, inferred_gaps = observation_effects(
        dump_text,
        primary_pid=args.process_id,
        primary_stable_identity=args.process_stable_identity,
        executable=args.executable,
        roots=roots,
        provider_process_ids=provider_process_ids,
    )
    gaps = {
        "lost_events": lost_events not in (0,),
        "buffer_overflow": lost_events not in (0,),
        "unknown_process_identity": inferred_gaps["unknown_process_identity"],
        "unresolved_target": inferred_gaps["unresolved_target"],
        "delayed_events": False,
        "attribution_gap": inferred_gaps["attribution_gap"],
        "provider_failure": bool(errors),
    }
    capture_complete = not any(gaps.values())
    observation: dict[str, Any] = {
        "schema": OBSERVATION_SCHEMA,
        "provider_id": PREFLIGHT.OBSERVER_PROVIDER_ID,
        "provider_revision": BOUND_PROVIDER_REVISION,
        "plan_digest": args.plan_digest,
        "capture_session_digest": claimed,
        "raw_artifact_digest": PREFLIGHT.sha256_file(trace) if trace.is_file() else sha256_text("missing"),
        "active_before_process": True,
        "capture_complete": capture_complete,
        "gaps": gaps,
        "effects": effects,
    }
    observation["output_digest"] = observation_output_digest(observation)
    atomic_json(observation_path, observation)
    diagnostic = {
        "schema": "factorio.gate4c_observer_capture_result.v1",
        "generated_at": utc_now(),
        "capture_session_digest": claimed,
        "plan_digest": args.plan_digest,
        "loss_evidence": loss_evidence,
        "lost_events": lost_events,
        "errors": sorted(set(errors)),
        "commands": commands,
        "artifacts": {
            "trace": {"path": str(trace), "sha256": PREFLIGHT.sha256_file(trace) if trace.is_file() else None},
            "dump": {"path": str(dump), "sha256": PREFLIGHT.sha256_file(dump) if dump.is_file() else None},
            "stats": {"path": str(stats), "sha256": PREFLIGHT.sha256_file(stats) if stats.is_file() else None},
            "observation": {
                "path": str(observation_path),
                "sha256": PREFLIGHT.sha256_file(observation_path),
            },
        },
        "capture_complete": capture_complete,
        "effect_count": len(effects),
    }
    atomic_json(operation_root / "candidate-artifacts" / "observation-result.json", diagnostic)
    return {"observation_path": str(observation_path), "diagnostic": diagnostic}


def abort_capture(args: argparse.Namespace) -> dict[str, Any]:
    if os.name != "nt" or not PREFLIGHT.is_elevated():
        raise SessionError("aborting the Gate 4C capture requires an elevated Windows session")
    task_root = exact_task_root(args.task_root)
    operation_root = exact_operation_root(task_root, args.operation_root)
    expected_token = operation_root / "process" / "observation" / "capture-token.json"
    token_audit = PREFLIGHT.audit_no_follow(args.capture_token, require_file=True)
    if (
        not token_audit["safe"]
        or os.path.normcase(os.path.abspath(args.capture_token))
        != os.path.normcase(os.path.abspath(expected_token))
    ):
        raise SessionError("capture token is unsafe")
    token = json.loads(args.capture_token.read_text(encoding="utf-8"))
    claimed = token.get("capture_session_digest")
    core = dict(token)
    core.pop("capture_session_digest", None)
    if (
        token.get("schema") != CAPTURE_SCHEMA
        or token.get("operation_root") != str(operation_root)
        or token.get("active") is not True
        or not lowercase_digest(claimed)
        or digest_value(core) != claimed
        or claimed != args.capture_session_digest
    ):
        raise SessionError("capture token identity is invalid")

    observer_paths = PREFLIGHT.observer_tool_paths()
    if not PREFLIGHT.observer_toolchain_coherent(observer_paths):
        raise SessionError("observer toolchain changed during capture")
    wpr = str(observer_paths["wpr"])
    before = SELFTEST.command([wpr, "-status"])
    cancel = None
    if not SELFTEST.wpr_is_not_recording(before):
        cancel = SELFTEST.command([wpr, "-cancel"])
    after = SELFTEST.command([wpr, "-status"])
    stopped = SELFTEST.wpr_is_not_recording(after)
    result: dict[str, Any] = {
        "schema": "factorio.gate4c_observer_abort.v1",
        "canonicalization_version": "facman.sorted-json.v1",
        "generated_at": utc_now(),
        "operation_id": operation_root.name,
        "capture_session_digest": claimed,
        "reason": args.reason,
        "wpr_status_before": command_record(before, [wpr, "-status"]),
        "wpr_cancel": (
            command_record(cancel, [wpr, "-cancel"]) if cancel is not None else None
        ),
        "wpr_status_after": command_record(after, [wpr, "-status"]),
        "recording_stopped": stopped,
    }
    result["abort_digest"] = digest_value(result)
    out = operation_root / "candidate-artifacts" / "observer-abort.json"
    atomic_json(out, result)
    if not stopped:
        raise SessionError("WPR remained active after fail-closed abort")
    return result


def status_capture(args: argparse.Namespace) -> dict[str, Any]:
    if os.name != "nt" or not PREFLIGHT.is_elevated():
        raise SessionError("checking the Gate 4C capture requires an elevated Windows session")
    task_root = exact_task_root(args.task_root)
    operation_root = exact_operation_root(task_root, args.operation_root)
    expected_token = operation_root / "process" / "observation" / "capture-token.json"
    token_audit = PREFLIGHT.audit_no_follow(args.capture_token, require_file=True)
    if (
        not token_audit["safe"]
        or os.path.normcase(os.path.abspath(args.capture_token))
        != os.path.normcase(os.path.abspath(expected_token))
    ):
        raise SessionError("capture token is unsafe")
    token = json.loads(args.capture_token.read_text(encoding="utf-8"))
    claimed = token.get("capture_session_digest")
    core = dict(token)
    core.pop("capture_session_digest", None)
    if (
        token.get("schema") != CAPTURE_SCHEMA
        or token.get("operation_root") != str(operation_root)
        or token.get("active") is not True
        or not lowercase_digest(claimed)
        or digest_value(core) != claimed
        or claimed != args.capture_session_digest
    ):
        raise SessionError("capture token identity is invalid")
    observer_paths = PREFLIGHT.observer_tool_paths()
    if not PREFLIGHT.observer_toolchain_coherent(observer_paths):
        raise SessionError("observer toolchain changed during capture")
    wpr = str(observer_paths["wpr"])
    status = SELFTEST.command([wpr, "-status"])
    if SELFTEST.wpr_is_not_recording(status):
        raise SessionError("WPR is not active for the bound capture")
    result: dict[str, Any] = {
        "schema": "factorio.gate4c_observer_status.v1",
        "canonicalization_version": "facman.sorted-json.v1",
        "generated_at": utc_now(),
        "operation_id": operation_root.name,
        "capture_session_digest": claimed,
        "active": True,
        "wpr_status": command_record(status, [wpr, "-status"]),
    }
    result["status_digest"] = digest_value(result)
    return result


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Gate 4C evidence-only verdict-session backend.")
    sub = value.add_subparsers(dest="command", required=True)
    start = sub.add_parser("observer-start")
    start.add_argument("--task-root", type=Path, required=True)
    start.add_argument("--operation-root", type=Path, required=True)
    start.add_argument("--preflight-digest", required=True)
    start.add_argument("--launch-provider-process-id", type=int, required=True)
    start.add_argument("--out", type=Path, required=True)
    finish = sub.add_parser("observer-finish")
    finish.add_argument("--task-root", type=Path, required=True)
    finish.add_argument("--operation-root", type=Path, required=True)
    finish.add_argument("--capture-token", type=Path, required=True)
    finish.add_argument("--plan-digest", required=True)
    finish.add_argument("--process-id", type=int, required=True)
    finish.add_argument("--process-stable-identity", required=True)
    finish.add_argument("--executable", required=True)
    finish.add_argument("--classification-roots", type=Path, required=True)
    finish.add_argument("--quiescence-seconds", type=int, default=2)
    abort = sub.add_parser("observer-abort")
    abort.add_argument("--task-root", type=Path, required=True)
    abort.add_argument("--operation-root", type=Path, required=True)
    abort.add_argument("--capture-token", type=Path, required=True)
    abort.add_argument("--capture-session-digest", required=True)
    abort.add_argument(
        "--reason",
        choices=("coordinator_disconnected", "launch_refused", "operator_cancelled"),
        required=True,
    )
    status = sub.add_parser("observer-status")
    status.add_argument("--task-root", type=Path, required=True)
    status.add_argument("--operation-root", type=Path, required=True)
    status.add_argument("--capture-token", type=Path, required=True)
    status.add_argument("--capture-session-digest", required=True)
    probe = sub.add_parser("observer-start-probe")
    probe.add_argument("--task-root", type=Path, required=True)
    probe.add_argument("--probe-id", required=True)
    probe.add_argument("--out", type=Path, required=True)
    return value


def main() -> int:
    args = parser().parse_args()
    if args.command == "observer-start-probe":
        record = observer_start_probe(args)
        print(
            "gate4c-observer-start-probe: "
            f"{record['status']} ({record['probe_digest']})"
        )
        return 0 if record["status"] == "pass" else 2
    if args.command == "observer-start":
        record = start_capture(args)
        print(f"gate4c-observer-start: active ({record['capture_session_digest']})")
        return 0
    if args.command == "observer-finish":
        result = finish_capture(args)
        print(f"gate4c-observer-finish: {result['observation_path']}")
        return 0
    if args.command == "observer-status":
        result = status_capture(args)
        print(f"gate4c-observer-status: active ({result['status_digest']})")
        return 0
    result = abort_capture(args)
    print(f"gate4c-observer-abort: stopped ({result['abort_digest']})")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError, SessionError) as exc:
        print(f"gate4c-verdict-session: {exc}", file=sys.stderr)
        raise SystemExit(2)
