from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
IMPACT_PATH = ROOT / "contracts" / "policy" / "test_impact.v1.json"


def run(command: list[str], *, env: dict[str, str] | None = None) -> None:
    print("+ " + " ".join(command), flush=True)
    completed = subprocess.run(command, cwd=ROOT, env=env, check=False)
    if completed.returncode:
        raise SystemExit(completed.returncode)


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


def native_executable(build_root: Path) -> Path | None:
    for relative in ("Debug/facman.exe", "Release/facman.exe", "facman.exe", "facman"):
        candidate = build_root / relative
        if candidate.is_file():
            return candidate
    return None


def ensure_native(build_root: Path, configuration: str, targets: list[str]) -> None:
    if not (build_root / "CMakeCache.txt").is_file():
        run(["cmake", "-S", ".", "-B", str(build_root), "-DFACMAN_BUILD_TESTS=ON"])
    command = ["cmake", "--build", str(build_root), "--config", configuration, "--parallel"]
    if targets and "*" not in targets:
        command.extend(["--target", *targets])
    run(command)


def run_native(build_root: Path, configuration: str, targets: list[str], label: str | None = None) -> None:
    ensure_native(build_root, configuration, targets)
    command = ["ctest", "--test-dir", str(build_root), "-C", configuration, "--output-on-failure"]
    if label:
        command.extend(["-L", label])
    elif targets and "*" not in targets:
        command.extend(["-R", "^(" + "|".join(targets) + ")$"])
    run(command)


def run_python(modules: list[str], build_root: Path) -> None:
    if not modules:
        return
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    executable = native_executable(build_root)
    if executable:
        env["FACMAN_NATIVE_CLI"] = str(executable.resolve())
        env["FACMAN_CLI_EXE"] = str(executable.resolve())
    run([sys.executable, "-m", "unittest", "-v", *modules], env=env)


def test_command(args: argparse.Namespace) -> None:
    impact = load_impact()
    build_root = Path(args.build_root)
    if args.mode == "full":
        run_native(build_root, args.configuration, ["*"])
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
        executable = native_executable(build_root)
        if executable:
            env["FACMAN_NATIVE_CLI"] = str(executable.resolve())
            env["FACMAN_CLI_EXE"] = str(executable.resolve())
        run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"], env=env)
        return
    if args.mode == "fast":
        run_native(build_root, args.configuration, [], "fast-unit")
        run_python(impact["fast_python"], build_root)
        return
    if args.mode == "category":
        if args.category == "operator":
            print(impact["operator"]["message"])
            raise SystemExit(2)
        run_native(build_root, args.configuration, [], args.category)
        run_python(impact["category_python"][args.category], build_root)
        return
    paths = changed_paths(args.base)
    selection = affected(impact, paths)
    print(json.dumps({"changed_paths": paths, "selection": selection}, indent=2))
    if not paths:
        print("No changed paths; running the deterministic fast suite.")
        run_native(build_root, args.configuration, [], "fast-unit")
        run_python(impact["fast_python"], build_root)
        return
    run_native(build_root, args.configuration, selection["native_targets"])
    run_python(selection["python_tests"], build_root)
    for validator in selection["strict_validators"]:
        run([sys.executable, validator])


def package_command(args: argparse.Namespace) -> None:
    command = [
        sys.executable,
        "tools/package_build.py",
        "--profile",
        args.profile,
        "--out",
        args.out,
        "--build-root",
        args.build_root,
        "--dist",
        args.dist,
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
    test.add_argument("--build-root", default="build/native-smoke")
    test.add_argument("--configuration", default="Debug")
    package = subparsers.add_parser("package")
    package.add_argument("--profile", required=True)
    package.add_argument("--out", default="build/packages")
    package.add_argument("--build-root", default="build/native-smoke")
    package.add_argument("--dist", default="dist")
    package.add_argument("--allow-dirty", action="store_true")
    verify = subparsers.add_parser("verify-all")
    verify.add_argument("--build-root", default="build/native-smoke")
    verify.add_argument("--configuration", default="Debug")
    args = parser.parse_args()
    if args.command == "test":
        test_command(args)
    elif args.command == "package":
        package_command(args)
    else:
        test_args = argparse.Namespace(mode="full", build_root=args.build_root, configuration=args.configuration)
        test_command(test_args)
        run([sys.executable, "tools/strict_check.py"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
