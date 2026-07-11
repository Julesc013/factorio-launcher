from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import argparse
import json
import os
import platform
import re
import statistics
import subprocess
import time
from pathlib import Path
from typing import Any

from tools import architecture_fitness

ROOT = architecture_fitness.ROOT
JSON_OUTPUT = ROOT / "docs/quality/baselines/r3.4_architecture_fitness.v1.json"
MARKDOWN_OUTPUT = ROOT / "docs/quality/baselines/r3.4_architecture_fitness.md"


def git_revision() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE
    )
    return completed.stdout.strip()


def target_graph() -> dict[str, list[str]]:
    text = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
    targets = set(re.findall(r"add_(?:library|executable)\s*\(\s*([A-Za-z0-9_]+)", text))
    return {target: architecture_fitness.cmake_target_links(target) for target in sorted(targets)}


def include_graph() -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for path in architecture_fitness.first_party_sources("apps", "runtime", "include"):
        includes = sorted(architecture_fitness.include_names(path))
        if includes:
            result[architecture_fitness.relative(path)] = includes
    return result


def line_counts() -> dict[str, Any]:
    roots: dict[str, dict[str, int]] = {}
    total_files = 0
    total_lines = 0
    for root in ["apps", "runtime", "include", "tools", "tests", "contracts", "docs", "release"]:
        files = [path for path in (ROOT / root).rglob("*") if path.is_file()]
        lines = 0
        for path in files:
            try:
                lines += len(path.read_text(encoding="utf-8", errors="replace").splitlines())
            except OSError:
                continue
        roots[root] = {"files": len(files), "physical_lines": lines}
        total_files += len(files)
        total_lines += lines
    return {"roots": roots, "total_files": total_files, "total_physical_lines": total_lines}


def timed(command: list[str], repeats: int = 7) -> dict[str, float | int]:
    samples: list[float] = []
    for _ in range(repeats):
        start = time.perf_counter()
        completed = subprocess.run(command, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        elapsed = (time.perf_counter() - start) * 1000.0
        if completed.returncode != 0:
            raise RuntimeError(f"timing command failed ({completed.returncode}): {' '.join(command)}")
        samples.append(elapsed)
    return {
        "repeats": repeats,
        "median_ms": round(statistics.median(samples), 3),
        "minimum_ms": round(min(samples), 3),
        "maximum_ms": round(max(samples), 3),
    }


def binary_sizes(build_root: Path | None) -> dict[str, int]:
    if build_root is None:
        return {}
    roots = [build_root, build_root / "Debug", build_root / "Release"]
    names = ["facman.exe", "facman", "facman-tui.exe", "facman-tui", "facmand.exe", "facmand"]
    result: dict[str, int] = {}
    for name in names:
        for root in roots:
            candidate = root / name
            if candidate.is_file():
                result[name] = candidate.stat().st_size
                break
    return result


def collect(args: argparse.Namespace) -> dict[str, Any]:
    build_root = Path(args.native_build_root).resolve() if args.native_build_root else None
    cli = None
    if build_root is not None:
        for candidate in [build_root / "Debug/facman.exe", build_root / "facman", build_root / "facman.exe"]:
            if candidate.is_file():
                cli = candidate
                break
    timings: dict[str, Any] = {
        "workspace_matrix_seconds": args.workspace_matrix_seconds,
        "required_package_proof_seconds": args.required_package_seconds,
    }
    if cli is not None:
        timings["cli_version_startup"] = timed([str(cli), "--version"])
        timings["command_graph_inspect"] = timed([str(cli), "command-graph", "inspect", "--json"])
        timings["diagnostic_doctor"] = timed([str(cli), "doctor", "--json"])
    package = Path(args.package_artifact).resolve() if args.package_artifact else None
    return {
        "schema": "facman.architecture_fitness_baseline.v1",
        "source_revision": git_revision(),
        "measurement_host": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "processor_count": os.cpu_count(),
        },
        "line_counts": line_counts(),
        "target_dependency_graph": target_graph(),
        "include_dependency_graph": include_graph(),
        "binary_sizes_bytes": binary_sizes(build_root),
        "selected_package": {
            "name": package.name,
            "size_bytes": package.stat().st_size,
        } if package is not None and package.is_file() else {},
        "test_inventory": {
            "universal_launcher_ctest": 1,
            "universal_setup_ctest": 2,
            "factorio_launcher_ctest": 9,
            "required_windows_package_tests": 14,
            "required_test_skips": 0,
        },
        "timings": timings,
        "known_exception_counts": {
            name: len(architecture_fitness.load_exceptions(name))
            for name in [
                "apps_boundary", "manual_json", "critical_io", "generated_catalog",
                "version_truth", "target_dependency", "aide_queue_state",
            ]
        },
        "notes": [
            "Workspace matrix timing is the clean rerun after an excluded compiler-lock collision.",
            "Archive throughput and diagnostic export fixtures are added when their focused benchmark harnesses land.",
            "All sizes are unsigned local proof artifacts; no release or publication claim is implied.",
        ],
    }


def markdown(data: dict[str, Any]) -> str:
    counts = data["line_counts"]
    timing = data["timings"]
    lines = [
        "# R3.4 Architecture Fitness Baseline",
        "",
        f"Revision: `{data['source_revision']}`.",
        "",
        "This is a measurement and regression-control artifact, not a readiness or release claim.",
        "",
        "## Scale",
        "",
        f"- first-party tracked surfaces measured: {counts['total_files']} files, {counts['total_physical_lines']} physical lines;",
        f"- CMake targets: {len(data['target_dependency_graph'])};",
        f"- source files with include edges: {len(data['include_dependency_graph'])};",
        f"- selected package: `{data['selected_package'].get('name', 'not measured')}` ({data['selected_package'].get('size_bytes', 0)} bytes).",
        "",
        "## Validation inventory",
        "",
    ]
    for key, value in data["test_inventory"].items():
        lines.append(f"- {key.replace('_', ' ')}: {value};")
    lines.extend(["", "## Timings", ""])
    for key, value in timing.items():
        if isinstance(value, dict):
            lines.append(f"- {key.replace('_', ' ')}: median {value['median_ms']} ms over {value['repeats']} runs;")
        else:
            lines.append(f"- {key.replace('_', ' ')}: {value} seconds;")
    lines.extend(["", "## Known architecture exceptions", ""])
    for key, value in data["known_exception_counts"].items():
        lines.append(f"- {key.replace('_', ' ')}: {value};")
    lines.extend([
        "",
        "The complete target graph, include graph, binary sizes, root line counts, host identity, and timing data are in",
        "`r3.4_architecture_fitness.v1.json`. Exception identities are controlled by",
        "`contracts/policy/architecture_fitness_exceptions.v1.toml`.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the revision-pinned R3.4 architecture fitness baseline.")
    parser.add_argument("--native-build-root")
    parser.add_argument("--package-artifact")
    parser.add_argument("--workspace-matrix-seconds", type=float, required=True)
    parser.add_argument("--required-package-seconds", type=float, required=True)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    data = collect(args)
    rendered_json = json.dumps(data, indent=2, sort_keys=True) + "\n"
    rendered_markdown = markdown(data)
    if args.write:
        JSON_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        JSON_OUTPUT.write_text(rendered_json, encoding="utf-8")
        MARKDOWN_OUTPUT.write_text(rendered_markdown, encoding="utf-8")
        print(f"architecture-baseline: wrote {architecture_fitness.relative(JSON_OUTPUT)}")
        print(f"architecture-baseline: wrote {architecture_fitness.relative(MARKDOWN_OUTPUT)}")
    else:
        print(rendered_json, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
