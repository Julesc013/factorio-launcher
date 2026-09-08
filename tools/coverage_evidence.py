# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT
"""Run gcovr with bounded diagnostics that survive collection failures."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import threading
from typing import BinaryIO


MAX_CHANNEL_BYTES = 64 * 1024
MAX_REPORT_BYTES = 256 * 1024 * 1024
MAX_TIMEOUT_SECONDS = 900.0


def bounded_seconds(value: str) -> float:
    try:
        seconds = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("timeout must be a number") from error
    if not 0 < seconds <= MAX_TIMEOUT_SECONDS:
        raise argparse.ArgumentTypeError(
            f"timeout must be greater than zero and at most {MAX_TIMEOUT_SECONDS:g} seconds"
        )
    return seconds


def output_path(build_root: Path, selected: Path) -> Path:
    root = build_root.resolve()
    path = selected.resolve(strict=False)
    if path == root or not path.is_relative_to(root):
        raise ValueError(f"coverage output escapes build root: {selected}")
    cursor = root
    if cursor.is_symlink():
        raise ValueError(f"coverage build root is a symbolic link: {root}")
    for part in path.relative_to(root).parts[:-1]:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError(f"coverage output parent is a symbolic link: {cursor}")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        raise FileExistsError(f"coverage output already exists: {path}")
    return path


def drain(stream: BinaryIO, maximum: int = MAX_CHANNEL_BYTES) -> dict[str, object]:
    digest = hashlib.sha256()
    stored = bytearray()
    total = 0
    while True:
        chunk = stream.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        digest.update(chunk)
        remaining = maximum - len(stored)
        if remaining > 0:
            stored.extend(chunk[:remaining])
    return {
        "bytes": total,
        "sha256": digest.hexdigest(),
        "stored_bytes": len(stored),
        "truncated": total > len(stored),
        "text": bytes(stored).decode("utf-8", "replace"),
    }


def channel_record(data: bytes, maximum: int = MAX_CHANNEL_BYTES) -> dict[str, object]:
    stored = data[:maximum]
    return {
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "stored_bytes": len(stored),
        "truncated": len(data) > len(stored),
        "text": stored.decode("utf-8", "replace"),
    }


def run_bounded(command: list[str], cwd: Path, timeout: float) -> dict[str, object]:
    process = subprocess.Popen(
        command,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=os.name == "posix",
    )
    assert process.stdout is not None and process.stderr is not None
    channels: dict[str, dict[str, object]] = {}
    workers = [
        threading.Thread(target=lambda: channels.__setitem__("stdout", drain(process.stdout))),
        threading.Thread(target=lambda: channels.__setitem__("stderr", drain(process.stderr))),
    ]
    for worker in workers:
        worker.start()
    timed_out = False
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
        process.wait()
    for worker in workers:
        worker.join()
    return {
        "exit_code": None if timed_out else process.returncode,
        "timed_out": timed_out,
        "stdout": channels["stdout"],
        "stderr": channels["stderr"],
    }


def collect(
    source_root: Path,
    build_root: Path,
    report_arg: Path,
    diagnostic_arg: Path,
    timeout: float,
    gcovr: str = "gcovr",
) -> int:
    source = source_root.resolve()
    build = build_root.resolve()
    report = output_path(build, report_arg)
    diagnostic = output_path(build, diagnostic_arg)
    if report == diagnostic:
        raise ValueError("coverage report and diagnostic paths must be distinct")
    command = [
        gcovr,
        "--root",
        str(source),
        "--filter",
        "runtime/(archive|base|transaction|workspace)/",
        "--json-pretty",
        "--output",
        str(report),
    ]
    try:
        process = run_bounded(command, source, timeout)
    except OSError as error:
        process = {
            "exit_code": 127,
            "timed_out": False,
            "stdout": channel_record(b""),
            "stderr": channel_record(str(error).encode("utf-8", "replace")),
        }

    report_record: dict[str, object] = {"present": report.exists() or report.is_symlink()}
    exit_code = 124 if process["timed_out"] else int(process["exit_code"])
    if report.is_symlink() or (report.exists() and not report.is_file()):
        report_record["regular_file"] = False
        if exit_code == 0:
            exit_code = 74
    elif report.is_file():
        try:
            report_size = report.stat().st_size
            report_record.update(
                bytes=report_size,
                regular_file=True,
                within_size_limit=report_size <= MAX_REPORT_BYTES,
            )
            if report_size > MAX_REPORT_BYTES:
                if exit_code == 0:
                    exit_code = 73
            else:
                report_bytes = report.read_bytes()
                report_record["sha256"] = hashlib.sha256(report_bytes).hexdigest()
                if exit_code == 0:
                    try:
                        json.loads(report_bytes)
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        report_record["valid_json"] = False
                        exit_code = 65
                    else:
                        report_record["valid_json"] = True
        except OSError as error:
            report_record["inspection_error"] = str(error)
            if exit_code == 0:
                exit_code = 74
    elif exit_code == 0:
        exit_code = 66

    receipt = {
        "schema": "facman.coverage_collection_evidence.v1",
        "recorded_utc": datetime.now(timezone.utc).isoformat(),
        "command": command,
        "cwd": str(source),
        "timeout_seconds": timeout,
        "process": process,
        "report": report_record,
        "result": "pass" if exit_code == 0 else "fail",
        "exit_code": exit_code,
    }
    with diagnostic.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(receipt, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=Path.cwd())
    parser.add_argument("--build-root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--diagnostic", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=bounded_seconds, default=600.0)
    args = parser.parse_args()
    return collect(
        args.source_root,
        args.build_root,
        args.report,
        args.diagnostic,
        args.timeout_seconds,
    )


if __name__ == "__main__":
    raise SystemExit(main())
