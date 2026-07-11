# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import statistics
import subprocess
import time
import zipfile
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "docs" / "quality" / "benchmarks" / "baseline.v1.json"


def timed(operation: Callable[[], None], repeats: int) -> dict[str, float | int]:
    samples = []
    for _ in range(repeats):
        start = time.perf_counter_ns()
        operation()
        samples.append((time.perf_counter_ns() - start) / 1_000_000.0)
    return {
        "repeats": repeats,
        "median_ms": round(statistics.median(samples), 4),
        "minimum_ms": round(min(samples), 4),
        "maximum_ms": round(max(samples), 4),
    }


def command(cli: Path, *arguments: str) -> Callable[[], None]:
    def invoke() -> None:
        completed = subprocess.run(
            [str(cli), *arguments], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        if completed.returncode:
            raise RuntimeError(f"benchmark command failed: {' '.join(arguments)}")
    return invoke


def zip_inspect(path: Path) -> Callable[[], None]:
    def inspect() -> None:
        with zipfile.ZipFile(path) as archive:
            for entry in archive.infolist():
                _ = (entry.filename, entry.file_size, entry.CRC)
    return inspect


def tree_hash(root: Path) -> Callable[[], None]:
    files = sorted(path for path in root.rglob("*") if path.is_file())
    def digest() -> None:
        value = hashlib.sha256()
        for path in files:
            value.update(path.relative_to(root).as_posix().encode())
            value.update(path.read_bytes())
        value.digest()
    return digest


def collect(cli: Path, repeats: int) -> dict[str, object]:
    archive = ROOT / "tests" / "fixtures" / "factorio_saves" / "valid_simple_save" / "starter.zip"
    mod = ROOT / "tests" / "fixtures" / "factorio_mods" / "valid_simple" / "simple_mod_1.0.0.zip"
    diagnostics = ROOT / "tests" / "fixtures" / "redaction"
    release_inputs = ROOT / "release"
    operations = {
        "startup": command(cli, "--version"),
        "command_dispatch": command(cli, "command-graph", "inspect", "--json"),
        "archive_inspect": zip_inspect(archive),
        "mod_inspection": zip_inspect(mod),
        "diagnostic_export_traversal": tree_hash(diagnostics),
        "package_hashing": tree_hash(release_inputs),
    }
    return {
        "schema": "facman.performance_baseline.v1",
        "advisory": True,
        "host": {"system": platform.system(), "machine": platform.machine(), "python": platform.python_version()},
        "maximum_regression_percent": 25.0,
        "measurements": {name: timed(operation, repeats) for name, operation in operations.items()},
    }


def compare(current: dict[str, object], baseline: dict[str, object]) -> list[str]:
    threshold = float(baseline["maximum_regression_percent"])
    warnings = []
    for name, measurement in current["measurements"].items():
        prior = float(baseline["measurements"][name]["median_ms"])
        now = float(measurement["median_ms"])
        if prior > 0 and ((now - prior) / prior * 100.0) > threshold:
            warnings.append(f"{name}: {now:.4f} ms exceeds {prior:.4f} ms by more than {threshold:.1f}%")
    return warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect advisory FacMan performance evidence.")
    parser.add_argument("--cli", required=True, type=Path)
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--write-baseline", action="store_true")
    parser.add_argument("--compare", action="store_true")
    parser.add_argument("--enforce", action="store_true")
    args = parser.parse_args()
    current = collect(args.cli.resolve(), args.repeats)
    if args.write_baseline:
        BASELINE.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"benchmark: wrote {BASELINE.relative_to(ROOT)}")
    if args.compare:
        warnings = compare(current, json.loads(BASELINE.read_text(encoding="utf-8")))
        for warning in warnings:
            print(f"benchmark: warning: {warning}")
        if warnings and args.enforce:
            return 1
    if not args.write_baseline and not args.compare:
        print(json.dumps(current, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
