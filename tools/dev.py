# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
IMPACT_PATH = ROOT / "contracts" / "policy" / "test_impact.v1.json"
NATIVE_BUILD_PREREQUISITES = {
    "facman_abi_symbol_smoke": "flb_factorio_shared",
}


def run(command: list[str], *, env: dict[str, str] | None = None) -> None:
    print("+ " + " ".join(command), flush=True)
    completed = subprocess.run(command, cwd=ROOT, env=env, check=False)
    if completed.returncode:
        raise SystemExit(completed.returncode)


def capture(command: list[str]) -> str:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise ValueError(detail or f"command failed: {' '.join(command)}")
    return completed.stdout


def default_task_root() -> Path:
    configured = os.environ.get("FACMAN_TASK_ROOT", "").strip()
    if configured:
        return Path(configured).expanduser()
    repo_key = hashlib.sha256(str(ROOT.resolve()).encode("utf-8")).hexdigest()[:12]
    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
        base = (
            Path(local_app_data)
            if local_app_data
            else Path(tempfile.gettempdir()).resolve().parent
        )
        return base / "FacMan" / "Tasks" / f"local-{repo_key}"
    cache = os.environ.get("XDG_CACHE_HOME", "").strip()
    base = Path(cache).expanduser() if cache else Path(tempfile.gettempdir())
    return base / "FacMan" / "Tasks" / f"local-{repo_key}"


def output_path(value: str | None, task_root: Path, child: str) -> Path:
    return Path(value).expanduser() if value else task_root / child


def validate_external_output(path: Path, *, allow_in_tree: bool) -> Path:
    resolved = path.resolve()
    if not allow_in_tree and resolved.is_relative_to(ROOT.resolve()):
        raise ValueError(
            f"generated output must be outside the source checkout: {resolved}; "
            "pass --allow-in-tree-output only for a reviewed legacy workflow"
        )
    return resolved


def load_impact() -> dict[str, Any]:
    return json.loads(IMPACT_PATH.read_text(encoding="utf-8"))


def changed_paths(base: str) -> list[str]:
    commands = [["git", "diff", "--name-only", base]]
    if base != "HEAD":
        commands.insert(0, ["git", "diff", "--name-only", f"{base}...HEAD"])
    values: set[str] = set()
    for command in commands:
        completed = subprocess.run(
            command, cwd=ROOT, check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        if completed.returncode:
            raise ValueError(completed.stderr.strip() or f"could not compare against {base}")
        values.update(line.strip().replace("\\", "/") for line in completed.stdout.splitlines() if line.strip())
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    values.update(line.strip().replace("\\", "/") for line in untracked.stdout.splitlines() if line.strip())
    return sorted(values)


def matches(path: str, prefixes: list[str]) -> bool:
    return any(path == prefix.rstrip("/") or path.startswith(prefix) for prefix in prefixes)


def affected(impact: dict[str, Any], paths: list[str]) -> dict[str, list[str]]:
    selected = {"native_targets": [], "python_tests": [], "strict_validators": [], "package_profiles": []}
    for module in impact["modules"]:
        if not any(matches(path, module["paths"]) for path in paths):
            continue
        for key in selected:
            selected[key].extend(module[key])
    for key in selected:
        selected[key] = sorted(set(selected[key]))
    return selected


def native_executable(build_root: Path, configuration: str = "") -> Path | None:
    preferred = [f"{configuration}/facman.exe"] if configuration else []
    for relative in (*preferred, "facman.exe", "facman", "Debug/facman.exe", "Release/facman.exe"):
        candidate = build_root / relative
        if candidate.is_file():
            return candidate
    return None


def native_tui_executable(
    build_root: Path,
    configuration: str = "",
) -> Path | None:
    preferred = [f"{configuration}/facman-tui.exe"] if configuration else []
    for relative in (
        *preferred,
        "facman-tui.exe",
        "facman-tui",
        "Debug/facman-tui.exe",
        "Release/facman-tui.exe",
    ):
        candidate = build_root / relative
        if candidate.is_file():
            return candidate
    return None


def configure_native(build_root: Path) -> None:
    run(["cmake", "-S", ".", "-B", str(build_root), "-DFACMAN_BUILD_TESTS=ON"])


def build_native(build_root: Path, configuration: str, targets: list[str]) -> None:
    command = ["cmake", "--build", str(build_root), "--config", configuration, "--parallel"]
    if targets and "*" not in targets:
        build_targets = sorted({NATIVE_BUILD_PREREQUISITES.get(target, target) for target in targets})
        command.extend(["--target", *build_targets])
    run(command)


def configured_ctest_graph(build_root: Path, configuration: str) -> list[dict[str, Any]]:
    raw = capture(
        [
            "ctest",
            "--test-dir",
            str(build_root),
            "-C",
            configuration,
            "--show-only=json-v1",
        ]
    )
    document = json.loads(raw)
    tests = document.get("tests")
    if not isinstance(tests, list):
        raise ValueError("configured CTest graph has no test inventory")
    return [test for test in tests if isinstance(test, dict)]


def ctest_labels(test: dict[str, Any]) -> set[str]:
    for prop in test.get("properties", []):
        if isinstance(prop, dict) and prop.get("name") == "LABELS":
            value = prop.get("value", [])
            return {str(label) for label in value} if isinstance(value, list) else set()
    return set()


def configured_fast_targets(impact: dict[str, Any], graph: list[dict[str, Any]]) -> list[str]:
    configured = {
        str(test.get("name", "")): test
        for test in graph
        if "fast-unit" in ctest_labels(test)
    }
    required = set(impact["fast_native_required"])
    optional = set(impact["fast_native_optional"])
    missing = sorted(required - set(configured))
    unexpected = sorted(set(configured) - required - optional)
    if missing:
        raise ValueError(f"configured CTest graph is missing required fast tests: {missing}")
    if unexpected:
        raise ValueError(f"fast-test policy omits configured CTest tests: {unexpected}")
    overrides = impact.get("fast_native_target_overrides", {})
    if not isinstance(overrides, dict):
        raise ValueError("fast native target overrides must be an object")
    return sorted({str(overrides.get(name, name)) for name in configured})


def run_native(
    build_root: Path,
    configuration: str,
    targets: list[str],
    label: str | None = None,
    impact: dict[str, Any] | None = None,
) -> None:
    configure_native(build_root)
    if label == "fast-unit":
        if impact is None:
            raise ValueError("fast native selection requires the test-impact policy")
        targets = configured_fast_targets(
            impact,
            configured_ctest_graph(build_root, configuration),
        )
    build_native(build_root, configuration, targets)
    command = ["ctest", "--test-dir", str(build_root), "-C", configuration, "--output-on-failure"]
    if label:
        command.extend(["-L", label])
    elif targets and "*" not in targets:
        command.extend(["-R", "^(" + "|".join(targets) + ")$"])
    run(command)


def run_python(modules: list[str], build_root: Path, configuration: str = "") -> None:
    if not modules:
        return
    env = os.environ.copy()
    python_paths = [str(ROOT / "tests"), str(ROOT)]
    if env.get("PYTHONPATH"):
        python_paths.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(python_paths)
    env["FACMAN_NATIVE_BUILD_ROOT"] = str(build_root.resolve())
    env["FACMAN_NATIVE_CONFIGURATION"] = configuration
    executable = native_executable(build_root, configuration)
    if executable:
        env["FACMAN_NATIVE_CLI"] = str(executable.resolve())
        env["FACMAN_CLI_EXE"] = str(executable.resolve())
    tui_executable = native_tui_executable(build_root, configuration)
    if tui_executable:
        env["FACMAN_TUI_EXE"] = str(tui_executable.resolve())
    run([sys.executable, "-m", "unittest", "-v", *modules], env=env)


def test_command(args: argparse.Namespace) -> None:
    impact = load_impact()
    task_root = Path(args.task_root)
    build_root = validate_external_output(
        output_path(args.build_root, task_root, "native-smoke"),
        allow_in_tree=args.allow_in_tree_output,
    )
    if args.mode == "full":
        run_native(build_root, args.configuration, ["*"])
        evidence_root = validate_external_output(
            task_root / "evidence",
            allow_in_tree=args.allow_in_tree_output,
        )
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
        env["FACMAN_NATIVE_BUILD_ROOT"] = str(build_root.resolve())
        env["FACMAN_NATIVE_CONFIGURATION"] = args.configuration
        executable = native_executable(build_root, args.configuration)
        if executable:
            env["FACMAN_NATIVE_CLI"] = str(executable.resolve())
            env["FACMAN_CLI_EXE"] = str(executable.resolve())
        tui_executable = native_tui_executable(build_root, args.configuration)
        if tui_executable:
            env["FACMAN_TUI_EXE"] = str(tui_executable.resolve())
        run(
            [
                sys.executable,
                "tools/test_obligations.py",
                "--profile",
                args.obligation_profile,
                "--evidence",
                str(evidence_root / f"python-obligations-{args.obligation_profile}.json"),
            ],
            env=env,
        )
        return
    if args.mode == "fast":
        run_native(build_root, args.configuration, [], "fast-unit", impact)
        run_python(impact["fast_python"], build_root, args.configuration)
        return
    if args.mode == "category":
        if args.category == "operator":
            print(impact["operator"]["message"])
            raise SystemExit(2)
        run_native(build_root, args.configuration, [], args.category, impact)
        run_python(impact["category_python"][args.category], build_root, args.configuration)
        return
    paths = changed_paths(args.base)
    selection = affected(impact, paths)
    print(json.dumps({"changed_paths": paths, "selection": selection}, indent=2))
    if not paths:
        print("No changed paths; running the deterministic fast suite.")
        run_native(build_root, args.configuration, [], "fast-unit", impact)
        run_python(impact["fast_python"], build_root, args.configuration)
        return
    run_native(build_root, args.configuration, selection["native_targets"])
    run_python(selection["python_tests"], build_root, args.configuration)
    for validator in selection["strict_validators"]:
        run([sys.executable, validator])


def package_command(args: argparse.Namespace) -> None:
    task_root = Path(args.task_root)
    build_root = validate_external_output(
        output_path(args.build_root, task_root, "native-smoke"),
        allow_in_tree=args.allow_in_tree_output,
    )
    out = validate_external_output(
        output_path(args.out, task_root, "packages"),
        allow_in_tree=args.allow_in_tree_output,
    )
    dist = validate_external_output(
        output_path(args.dist, task_root, "dist"),
        allow_in_tree=args.allow_in_tree_output,
    )
    command = [
        sys.executable,
        "tools/package_build.py",
        "--profile",
        args.profile,
        "--out",
        str(out),
        "--build-root",
        str(build_root),
        "--dist",
        str(dist),
    ]
    if args.allow_dirty:
        command.append("--allow-dirty")
    run(command)


def main() -> int:
    parser = argparse.ArgumentParser(description="FacMan developer entry point.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    test = subparsers.add_parser("test")
    modes = test.add_mutually_exclusive_group(required=True)
    modes.add_argument("--affected", dest="mode", action="store_const", const="affected")
    modes.add_argument("--fast", dest="mode", action="store_const", const="fast")
    modes.add_argument("--full", dest="mode", action="store_const", const="full")
    modes.add_argument("--category", dest="category", choices=load_impact()["categories"])
    test.set_defaults(mode="category" if "--category" in sys.argv else None)
    test.add_argument("--base", default=os.environ.get("FACMAN_TEST_BASE", "HEAD"))
    test.add_argument("--task-root", default=str(default_task_root()))
    test.add_argument("--build-root")
    test.add_argument("--allow-in-tree-output", action="store_true")
    test.add_argument("--configuration", default="Debug")
    test.add_argument(
        "--obligation-profile",
        choices=sorted(load_impact().get("obligation_profiles", ["local", "promotion"])),
        default="local",
    )
    package = subparsers.add_parser("package")
    package.add_argument("--profile", required=True)
    package.add_argument("--task-root", default=str(default_task_root()))
    package.add_argument("--out")
    package.add_argument("--build-root")
    package.add_argument("--dist")
    package.add_argument("--allow-in-tree-output", action="store_true")
    package.add_argument("--allow-dirty", action="store_true")
    verify = subparsers.add_parser("verify-all")
    verify.add_argument("--task-root", default=str(default_task_root()))
    verify.add_argument("--build-root")
    verify.add_argument("--allow-in-tree-output", action="store_true")
    verify.add_argument("--configuration", default="Debug")
    args = parser.parse_args()
    if args.command == "test":
        test_command(args)
    elif args.command == "package":
        package_command(args)
    else:
        run([sys.executable, "tools/verify_dependency_revisions.py"])
        test_args = argparse.Namespace(
            mode="full",
            task_root=args.task_root,
            build_root=args.build_root,
            allow_in_tree_output=args.allow_in_tree_output,
            configuration=args.configuration,
            obligation_profile="promotion",
        )
        test_command(test_args)
        run([sys.executable, "tools/strict_check.py"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
