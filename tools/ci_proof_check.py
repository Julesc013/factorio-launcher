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
        "python tools/package_reproducibility_proof.py",
        "Remove checkout-owned temporary credential includes",
        "python tools/ci_checkout_credential_scrub.py",
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
        "Project lock-agnostic checkout source facts",
        "python tools/integration_source_observation.py checkout",
        "Prove exact release-source refusal without outputs",
        "python tools/release_coherence_negative_control.py",
        "Project integration source coherence",
        "python tools/integration_source_observation.py integration",
        "--checkout-observation",
        "--integration-source-observation",
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

    platform_jobs = {
        "linux-native": linux_native,
        "windows-native-package": ci.partition("  windows-native-package:")[2].partition(
            "\n  macos-archive-core:"
        )[0],
        "macos-native-cli": ci.partition("  macos-native-cli:")[2].partition(
            "\n  appkit-compile:"
        )[0],
    }
    windows_native = platform_jobs["windows-native-package"]
    scrub_anchors = (
        "Remove checkout-owned temporary credential includes",
        "python tools/ci_checkout_credential_scrub.py",
        "--repo .",
        '--runner-temp "$env:RUNNER_TEMP"',
    )
    for anchor in scrub_anchors:
        if windows_native.count(anchor) != 1:
            problems.append(
                "windows-native-package must contain exactly one credential "
                f"scrub anchor: {anchor}"
            )
    credential_scrub = windows_native.find(
        "Remove checkout-owned temporary credential includes"
    )
    windows_observation = windows_native.find(
        "Record exact checkout and provider observation"
    )
    if not (0 <= credential_scrub < windows_observation):
        problems.append(
            "windows-native-package must scrub only checkout-owned credentials "
            "before source observation"
        )
    scrub_step = windows_native.partition(
        "- name: Remove checkout-owned temporary credential includes"
    )[2].partition("\n      - name: Record exact checkout and provider observation")[0]
    if "continue-on-error" in scrub_step:
        problems.append(
            "windows-native-package credential scrub must remain fail-closed"
        )
    for job_name, job in platform_jobs.items():
        for anchor in (
            "Record exact checkout and provider observation",
            "Preserve current checkout and provider observation",
            "Project lock-agnostic checkout source facts",
            "python tools/integration_source_observation.py checkout",
            "Prove exact release-source refusal without outputs",
            "python tools/release_coherence_negative_control.py",
            "Project integration source coherence",
            "python tools/integration_source_observation.py integration",
            "--checkout-observation",
            "--integration-source-observation",
        ):
            if anchor not in job:
                problems.append(
                    f"{job_name} source-custody package proof is missing anchor: {anchor}"
                )
        observation = job.find("Record exact checkout and provider observation")
        checkout_facts = job.find("Project lock-agnostic checkout source facts")
        release_refusal = job.find("Prove exact release-source refusal without outputs")
        integration = job.find("Project integration source coherence")
        package_proof = min(
            (
                index
                for index in (
                    job.find("linux_package_proof.py"),
                    job.find("macos_package_proof.py"),
                    job.find("package_reproducibility_proof.py"),
                )
                if index >= 0
            ),
            default=-1,
        )
        if not (
            0 <= observation < checkout_facts < release_refusal < integration < package_proof
        ):
            problems.append(
                f"{job_name} must observe facts, prove release refusal, then consume "
                "integration custody in order"
            )
        if "python tools/facman_release.py source-observation" in job:
            problems.append(
                f"{job_name} general integration CI cannot project release source coherence"
            )
        for release_producer in (
            "python tools/facman_release.py package",
            "python tools/windows_c1_release_candidate.py",
            "windows-c1-release-candidate-",
        ):
            if release_producer in job:
                problems.append(
                    f"{job_name} general integration CI cannot construct a release candidate: "
                    f"{release_producer}"
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
    if not (ROOT / "tools" / "ci_checkout_credential_scrub.py").is_file():
        problems.append("checkout-owned credential scrub runner is missing")
    if not (ROOT / "tools" / "integration_source_observation.py").is_file():
        problems.append("integration source observation runner is missing")
    if not (ROOT / "tools" / "release_coherence_negative_control.py").is_file():
        problems.append("release coherence negative-control runner is missing")
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
