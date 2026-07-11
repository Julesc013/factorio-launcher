from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


def main() -> int:
    problems = validate()
    if problems:
        for problem in problems:
            print(f"ci-proof-check: {problem}", file=sys.stderr)
        return 1
    print("ci-proof-check: ok")
    return 0


def validate() -> list[str]:
    problems: list[str] = []
    ci = read("ci.yml", problems)
    security = read("security.yml", problems)
    schema = read("schema-check.yml", problems)
    release = read("release.yml", problems)
    all_workflows = "\n".join([ci, security, schema, release])

    forbidden = [
        "actions/checkout@v4",
        "actions/setup-python@v5",
        "microsoft/setup-msbuild@v2",
        "runs-on: macos-13",
        "python -m build",
    ]
    for anchor in forbidden:
        if anchor in all_workflows:
            problems.append(f"retired CI action or false release command remains: {anchor}")

    required_ci = [
        "linux-native:",
        "runs-on: ubuntu-24.04",
        "windows-native-package:",
        "runs-on: windows-2022",
        "actions/checkout@v6",
        "actions/setup-python@v6",
        "microsoft/setup-msbuild@v3",
        "cmake -S . -B build/native-smoke",
        "cmake --build build/native-smoke --config Debug",
        "ctest --test-dir build/native-smoke -C Debug --output-on-failure",
        "python -m unittest discover -s tests -v",
        "python tools/required_package_proof.py",
        "--profile windows_portable_cli_x64",
        "tools/package_hash_manifest.py --root build/packages/windows_portable_cli_x64 --verify",
        "tools/package_runtime_smoke.py --root build/packages/windows_portable_cli_x64",
        "python tools/linux_package_proof.py",
        "macos-native-cli:",
        "runs-on: macos-15-intel",
        "CMAKE_OSX_DEPLOYMENT_TARGET=13.0",
        "ctest --test-dir build/macos-native --output-on-failure",
        "python tools/macos_package_proof.py",
    ]
    for anchor in required_ci:
        if anchor not in ci:
            problems.append(f"ci.yml is missing required proof anchor: {anchor}")

    if "name: security-policy" not in security:
        problems.append("security workflow must be named security-policy")
    if "name: release-policy" not in release or "unpublished-release-gate:" not in release:
        problems.append("release workflow must remain an unpublished policy gate")
    if not (ROOT / "tools" / "required_package_proof.py").is_file():
        problems.append("required Windows package proof runner is missing")
    if not (ROOT / "tools" / "linux_package_proof.py").is_file():
        problems.append("required Linux package proof runner is missing")
    if not (ROOT / "tools" / "macos_package_proof.py").is_file():
        problems.append("required macOS package proof runner is missing")
    cmake = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
    if "set(CMAKE_POSITION_INDEPENDENT_CODE ON)" not in cmake:
        problems.append("native static libraries must remain position-independent for shared ELF links")
    return problems


def read(name: str, problems: list[str]) -> str:
    path = WORKFLOWS / name
    if not path.is_file():
        problems.append(f"missing workflow: {name}")
        return ""
    return path.read_text(encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
