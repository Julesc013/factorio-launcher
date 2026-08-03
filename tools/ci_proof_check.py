# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

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
        "fetch-depth: 0",
        "actions/setup-python@v6",
        "microsoft/setup-msbuild@v3",
        "cmake -S . -B build/native-smoke",
        "cmake --build build/native-smoke --config Debug",
        "ctest --test-dir build/native-smoke -C Debug --output-on-failure",
        "python tools/test_obligations.py --profile promotion",
        "python tools/required_package_proof.py",
        "python tools/package_reproducibility_proof.py --build-root build/native-smoke",
        "--profile windows_portable_cli_x64",
        "tools/package_hash_manifest.py --root build/packages/windows_portable_cli_x64 --verify",
        "tools/package_runtime_smoke.py --root build/packages/windows_portable_cli_x64",
        "python tools/linux_package_proof.py",
        "macos-native-cli:",
        "runs-on: macos-15-intel",
        "CMAKE_OSX_DEPLOYMENT_TARGET=13.0",
        "FACMAN_NATIVE_BUILD_ROOT: ${{ github.workspace }}/build/macos-native",
        'export TMPDIR="$RUNNER_TEMP/facman-native-tmp"',
        'echo "TMPDIR=$TMPDIR" >> "$GITHUB_ENV"',
        "Prepare no-link temporary root",
        "ctest --test-dir build/macos-native --output-on-failure",
        "python tools/macos_package_proof.py",
        "Record exact checkout and provider observation",
        "python tools/current_checkout_observation.py",
        "--provider-root universal_launcher=../universal-launcher",
        "--provider-root universal_setup=../universal-setup",
        '--expected-source-sha "$FACMAN_CI_SOURCE_SHA"',
        "--line-ending-profile lf_checkout",
        "Preserve current checkout and provider observation",
        "current-checkout-observation.v2.json",
        "current-checkout-observation.v2.md",
    ]
    for anchor in required_ci:
        if anchor not in ci:
            problems.append(f"ci.yml is missing required proof anchor: {anchor}")

    linux_native = ci.partition("  linux-native:")[2].partition("\n  linux-coverage:")[0]
    required_live_observation = [
        "FACMAN_CI_SOURCE_SHA: ${{ github.sha }}",
        "fetch-depth: 0",
        "persist-credentials: false",
        "--line-ending-profile lf_checkout",
        '--output-dir "$RUNNER_TEMP/facman-current-checkout-observation"',
        "if: always()",
        "if-no-files-found: error",
    ]
    for anchor in required_live_observation:
        if anchor not in linux_native:
            problems.append(
                f"linux-native checkout observation is missing fail-closed anchor: {anchor}"
            )
    if "github.event.pull_request.head.sha" in linux_native:
        problems.append(
            "linux-native must retain the workflow SHA and PR merge-checkout semantics"
        )
    alignment_index = linux_native.find("Align dependency revisions to workspace lock")
    observation_index = linux_native.find("Record exact checkout and provider observation")
    upload_index = linux_native.find("Preserve current checkout and provider observation")
    if not (0 <= alignment_index < observation_index < upload_index):
        problems.append(
            "linux-native must observe and preserve checkout truth after provider alignment"
        )

    if "name: security-policy" not in security:
        problems.append("security workflow must be named security-policy")
    if "name: release-policy" not in release or "unpublished-release-gate:" not in release:
        problems.append("release workflow must remain an unpublished policy gate")
    if not (ROOT / "tools" / "required_package_proof.py").is_file():
        problems.append("required Windows package proof runner is missing")
    if not (ROOT / "tools" / "package_reproducibility_proof.py").is_file():
        problems.append("required package reproducibility proof runner is missing")
    if not (ROOT / "tools" / "linux_package_proof.py").is_file():
        problems.append("required Linux package proof runner is missing")
    if not (ROOT / "tools" / "macos_package_proof.py").is_file():
        problems.append("required macOS package proof runner is missing")
    if not (ROOT / "tools" / "current_checkout_observation.py").is_file():
        problems.append("current checkout/provider observation runner is missing")
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
