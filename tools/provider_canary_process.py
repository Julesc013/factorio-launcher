# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Finite, retained command execution for the Windows local source canary."""
from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from tools import provider_canary_process_windows as windows

MAX_SECONDS = 7200.0
MAX_OUTPUT_BYTES = 32 * 1024 * 1024
MAX_INPUT_BYTES = 8 * 1024 * 1024
MAX_RECEIPT_BYTES = 8 * 1024 * 1024
CLEANUP_SECONDS = 5.0


def seconds(value: float, label: str = "deadline") -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(label + " must be a finite positive number")
    result = float(value)
    if not math.isfinite(result) or not 0 < result <= MAX_SECONDS:
        raise ValueError(label + " must be finite, positive and at most 7200 seconds")
    return result


@dataclass
class Budget:
    overall_seconds: float
    command_seconds: float

    def __post_init__(self) -> None:
        self.overall_seconds = seconds(self.overall_seconds, "overall deadline")
        self.command_seconds = seconds(self.command_seconds, "command deadline")
        self.started = time.monotonic()
        self.deadline = self.started + self.overall_seconds

    def remaining(self) -> float:
        return max(0.0, self.deadline - time.monotonic())


@dataclass
class Result:
    returncode: int | None
    stdout: bytes
    stderr: bytes
    receipt: dict
    directory: Path

    @property
    def ok(self) -> bool:
        return self.receipt["termination"] == "completed" and self.returncode == 0


class CommandFailure(RuntimeError):
    def __init__(self, result: Result):
        self.result = result
        super().__init__("canary command " + result.receipt["termination"] +
                         "; retained evidence: " + str(result.directory))


def write_json(path: Path, value: dict) -> None:
    raw = bytearray()
    for piece in json.JSONEncoder(indent=2, allow_nan=False).iterencode(value):
        data = piece.encode("utf-8")
        if len(raw) + len(data) + 1 > MAX_RECEIPT_BYTES:
            raise ValueError("canary result exceeds its bounded receipt size")
        raw.extend(data)
    path.write_bytes(raw + b"\n")


def command(command: list[str], *, cwd: Path, environment: dict[str, str] | None = None,
            timeout: float = 30.0, budget: Budget | None = None, directory: Path | None = None,
            input_bytes: bytes = b"", output_limit: int = MAX_OUTPUT_BYTES) -> Result:
    limit = seconds(timeout, "command deadline")
    if os.name != "nt":
        raise ValueError("owned canary execution is qualified on Windows only")
    if budget is not None:
        limit = min(limit, budget.command_seconds)
    if not isinstance(output_limit, int) or isinstance(output_limit, bool) or not 1 <= output_limit <= MAX_OUTPUT_BYTES:
        raise ValueError("canary output budget must be between 1 byte and 32 MiB")
    if len(input_bytes) > MAX_INPUT_BYTES:
        raise ValueError("canary standard input exceeds 8 MiB")
    if not command or len(command) > 256 or any(not isinstance(arg, str) or "\0" in arg for arg in command):
        raise ValueError("canary command arguments are invalid")
    if sum(len(arg) + 1 for arg in command) > 30000:
        raise ValueError("canary command arguments exceed their size budget")
    env = dict(os.environ) if environment is None else dict(environment)
    if any(not isinstance(key, str) or not isinstance(value, str) or not key or
           "=" in key or "\0" in key or "\0" in value for key, value in env.items()):
        raise ValueError("canary environment is invalid")
    if sum(len(key) + len(value) + 2 for key, value in env.items()) > 262144:
        raise ValueError("canary environment exceeds its size budget")
    executable = shutil.which(command[0], path=env.get("PATH"))
    if executable is None or Path(executable).suffix.lower() not in {".exe", ".com"}:
        raise ValueError("canary requires a resolved native executable; shell wrappers are unsupported")
    selected = [executable, *command[1:]]
    if directory is None:
        root = os.environ.get("FACMAN_CANARY_EVIDENCE_ROOT", tempfile.gettempdir())
        directory = Path(tempfile.mkdtemp(prefix="canary-command-", dir=root))
    else:
        directory.mkdir(parents=False)
    remaining = budget.remaining() if budget else limit
    effective = min(limit, remaining)
    started = time.monotonic()
    receipt = {"schema": "facman.canary-command.v1", "command": selected, "cwd": str(cwd),
               "configured_seconds": limit, "effective_seconds": effective,
               "cleanup_seconds": CLEANUP_SECONDS, "output_limit_per_stream": output_limit,
               "dispatched": None, "termination": "prepared_outcome_unknown",
               "effects": "unknown_if_interrupted",
               "exit_code": None, "environment_values_logged": False}
    stdout_path, stderr_path = directory / "stdout.raw", directory / "stderr.raw"
    (directory / "stdin.raw").write_bytes(input_bytes)
    write_json(directory / "receipt.json", receipt)
    with (directory / "stdin.raw").open("rb") as source, stdout_path.open("x+b") as stdout, stderr_path.open("x+b") as stderr:
        effective = min(effective, max(0.0, started + effective - time.monotonic()))
        receipt["effective_seconds"] = effective
        if effective > 0:
            native = windows.run(selected, cwd, env, (source, stdout, stderr), seconds=effective,
                                 cleanup_seconds=CLEANUP_SECONDS, output_limit=output_limit)
            receipt.update(native)
            if native["termination"] == "timed_out":
                receipt["termination"] = "overall_timeout" if budget is not None and remaining <= limit else "command_timeout"
        else:
            receipt.update(dispatched=False, termination="overall_deadline_before_dispatch")
        stdout.flush()
        stderr.flush()
        stdout.seek(0)
        stderr.seek(0)
        output, errors = stdout.read(output_limit + 1), stderr.read(output_limit + 1)
        if len(output) > output_limit or len(errors) > output_limit:
            receipt["termination"] = "output_limit"
            output, errors = output[:output_limit], errors[:output_limit]
        receipt["stdout"] = {"file": stdout_path.name, "captured_bytes": len(output),
                             "sha256": hashlib.sha256(output).hexdigest()}
        receipt["stderr"] = {"file": stderr_path.name, "captured_bytes": len(errors),
                             "sha256": hashlib.sha256(errors).hexdigest()}
    receipt["elapsed_seconds"] = round(time.monotonic() - started, 6)
    receipt["effects"] = "possible_retained" if receipt["dispatched"] else "command_not_dispatched"
    write_json(directory / "receipt.json", receipt)
    return Result(receipt["exit_code"], output, errors, receipt, directory)


def require(result: Result) -> Result:
    if not result.ok:
        raise CommandFailure(result)
    return result
