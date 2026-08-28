# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"

DEDUP_WORKFLOW_CLASSES = {
    "canonical-provider-packages.yml": "canonical-provider-packages",
    "ci.yml": "ci",
    "codeql.yml": "code-security",
    "provider-conformance.yml": "provider-input-conformance",
    "provider-sdk-consumption.yml": "provider-sdk-consumption",
    "schema-check.yml": "schema-check",
    "security.yml": "security-policy",
    "synthetic-product-tck.yml": "synthetic-product-tck",
}

MANUAL_WORKFLOWS = {
    "canonical-provider-packages.yml",
    "provider-conformance.yml",
    "provider-sdk-consumption.yml",
    "synthetic-product-tck.yml",
}

ACTION_PINS = {
    "actions/checkout": "d23441a48e516b6c34aea4fa41551a30e30af803",  # v6
    "actions/setup-python": "ece7cb06caefa5fff74198d8649806c4678c61a1",  # v6
    "actions/upload-artifact": "ea165f8d65b6e75b540449e92b4886f43607fa02",  # v4
    "github/codeql-action/init": "db488ddef3bf6cb639b32c2e9a7c0a7ea8271d28",  # v4
    "github/codeql-action/analyze": "db488ddef3bf6cb639b32c2e9a7c0a7ea8271d28",  # v4
    "microsoft/setup-msbuild": "30375c66a4eea26614e0d39710365f22f8b0af57",  # v3
}


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
    problems.extend(validate_event_dedup())
    problems.extend(validate_immutable_action_pins())
    problems.extend(validate_alpha_release_preflight(release))

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
        f"actions/checkout@{ACTION_PINS['actions/checkout']}",
        "fetch-depth: 0",
        f"actions/setup-python@{ACTION_PINS['actions/setup-python']}",
        f"microsoft/setup-msbuild@{ACTION_PINS['microsoft/setup-msbuild']}",
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
        "Prove atomic provider identity reconciliation",
        "python tools/provider_pin_reconciliation.py",
        "Prove exact release-source coherence and wrong-provider refusals",
        "python tools/release_coherence_proof.py",
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
            "Prove atomic provider identity reconciliation",
            "python tools/provider_pin_reconciliation.py",
            "Prove exact release-source coherence and wrong-provider refusals",
            "python tools/release_coherence_proof.py",
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
        reconciliation = job.find("Prove atomic provider identity reconciliation")
        release_coherence = job.find(
            "Prove exact release-source coherence and wrong-provider refusals"
        )
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
            0 <= observation < checkout_facts < reconciliation
            < release_coherence < integration < package_proof
        ):
            problems.append(
                f"{job_name} must observe facts, prove provider/release coherence, then consume "
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
    if "name: alpha-release" not in release or "release-source-preflight:" not in release:
        problems.append("release workflow must retain the manual alpha source preflight")
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
    if not (ROOT / "tools" / "provider_pin_reconciliation.py").is_file():
        problems.append("provider pin reconciliation runner is missing")
    if not (ROOT / "tools" / "release_coherence_proof.py").is_file():
        problems.append("positive release coherence runner is missing")
    cmake = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
    if "set(CMAKE_POSITION_INDEPENDENT_CODE ON)" not in cmake:
        problems.append("native static libraries must remain position-independent for shared ELF links")
    return problems


def validate_alpha_release_preflight(release: str | None = None) -> list[str]:
    """Require exact provider topology before release-contract validation."""

    problems: list[str] = []
    if release is None:
        release = read("release.yml", problems)

    preflight = release.partition("  release-source-preflight:")[2].partition(
        "\n  qualify-alpha-machine:"
    )[0]
    anchors = (
        "Clone exact locked provider sources",
        "git clone https://github.com/Julesc013/universal-setup.git ../universal-setup",
        "git clone https://github.com/Julesc013/universal-launcher.git ../universal-launcher",
        "Align provider sources to workspace lock",
        "python tools/verify_dependency_revisions.py --align --lock release/index/workspace_lock.v1.toml",
        "python tools/release_contract_check.py",
    )
    positions = [preflight.find(anchor) for anchor in anchors]
    if not preflight:
        problems.append("release workflow must retain the manual alpha source preflight")
    elif not all(position >= 0 for position in positions):
        problems.append(
            "alpha release preflight must materialize and align exact provider roots "
            "before release-contract validation"
        )
    elif not positions[0] < positions[3] < positions[5]:
        problems.append(
            "alpha release preflight must clone providers, align the workspace lock, "
            "then validate release contracts"
        )
    return problems


def validate_event_dedup(
    workflows: dict[str, str] | None = None,
) -> list[str]:
    """Validate the event split that prevents duplicate task-branch matrices."""

    problems: list[str] = []
    if workflows is None:
        workflows = {
            name: read(name, problems) for name in DEDUP_WORKFLOW_CLASSES
        }

    protected_push = "    branches:\n      - dev\n      - main"
    pr_key = "format('pull-request-{0}', github.event.pull_request.number)"
    protected_key = "format('protected-push-{0}', github.sha)"
    isolated_key = "format('{0}-{1}', github.event_name, github.run_id)"
    pr_only_cancel = (
        "cancel-in-progress: ${{ github.event_name == 'pull_request' }}"
    )

    for name, workflow_class in DEDUP_WORKFLOW_CLASSES.items():
        workflow = workflows.get(name, "")
        triggers = top_level_block(workflow, "on")
        push = nested_event_block(triggers, "push")
        concurrency = top_level_block(workflow, "concurrency")

        if not push:
            problems.append(f"{name} must retain a protected-branch push trigger")
        elif protected_push not in f"  push:\n{push}":
            problems.append(
                f"{name} push must be limited to the protected dev/main branches"
            )
        if "  pull_request:" not in triggers:
            problems.append(f"{name} must retain its pull_request trigger")
        for anchor in (
            f"    {workflow_class}-${{{{ github.event_name == 'pull_request'",
            pr_key,
            protected_key,
            isolated_key,
            pr_only_cancel,
        ):
            if anchor not in concurrency:
                problems.append(
                    f"{name} concurrency policy is missing anchor: {anchor}"
                )

        if name in MANUAL_WORKFLOWS and "  workflow_dispatch:" not in triggers:
            problems.append(f"{name} must retain workflow_dispatch")
        if name == "codeql.yml" and "  schedule:" not in triggers:
            problems.append("codeql.yml must retain its scheduled scan")

    release = read("release.yml", problems)
    release_triggers = top_level_block(release, "on")
    if "  push:" in release_triggers:
        problems.append("release.yml must remain manual-only before alpha authority")
    if "  workflow_dispatch:" not in release_triggers:
        problems.append("release.yml must retain workflow_dispatch")
    for anchor in (
        "contents: read",
        "environment: alpha-publication",
        "actions: read",
        "contents: write",
        "if: ${{ inputs.operation == 'publish' }}",
        "if: ${{ inputs.operation == 'qualify' }}",
        "if: ${{ inputs.operation == 'assemble-tag' }}",
        "if: ${{ inputs.operation == 'assemble-public' }}",
        "if: ${{ inputs.operation == 'tag' }}",
        "python tools/alpha_publication_gate.py",
        "python tools/alpha_tag_gate.py",
        "python tools/alpha_qualification.py",
        "python tools/alpha_asset_set.py machine",
        "python tools/alpha_asset_set.py tag",
        "python tools/alpha_asset_set.py public",
        "--operation publish",
        "publication_authority_sha256:",
        "environment: alpha-route-acceptance",
        "FACMAN_ALPHA_1_ROUTE_RECEIPT_JSON",
        "FACMAN_ALPHA_1_PUBLICATION_AUTHORITY_JSON",
        "name: facman-alpha-1-machine-assets",
        "name: facman-alpha-1-qualification-evidence",
        "name: facman-alpha-1-tag-assets",
        "name: facman-alpha-1-public-assets",
        "tag_receipt_sha256:",
        "Verify the separately gated immutable alpha tag",
        "Create one immutable unsigned annotated alpha tag",
        "Refuse public prerelease publication until separately activated",
        "facman-alpha-tag-eligibility",
        "facman-alpha-tag-receipt",
        '"repos/$GITHUB_REPOSITORY/rules/branches/dev"',
        "--github-branch-rules-json",
        '"repos/$GITHUB_REPOSITORY/rulesets?includes_parents=true&per_page=100"',
        "--github-tag-rulesets-json",
        "python tools/alpha_tag_receipt.py",
        '"repos/$GITHUB_REPOSITORY/git/tags"',
        '"repos/$GITHUB_REPOSITORY/git/refs"',
        "gh release create v0.1.0-alpha.1",
        "--verify-tag",
        "--draft",
        "--prerelease",
    ):
        if anchor not in release:
            problems.append(f"release.yml is missing least-privilege alpha anchor: {anchor}")
    return problems


def validate_immutable_action_pins(
    workflows: dict[str, str] | None = None,
) -> list[str]:
    """Require every external workflow action to use its reviewed full SHA."""

    problems: list[str] = []
    if workflows is None:
        workflows = {
            path.name: path.read_text(encoding="utf-8")
            for path in sorted(WORKFLOWS.glob("*.yml"))
        }
    for name, text in workflows.items():
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("- "):
                stripped = stripped[2:].lstrip()
            if not stripped.startswith("uses:"):
                continue
            action_ref = stripped.split("#", 1)[0].rstrip().split(None, 1)[1]
            if action_ref.startswith("./"):
                continue
            action, separator, revision = action_ref.rpartition("@")
            if not separator or action not in ACTION_PINS:
                problems.append(f"{name} uses an unreviewed external action: {action_ref}")
                continue
            if revision != ACTION_PINS[action]:
                problems.append(
                    f"{name} must pin {action} to {ACTION_PINS[action]}"
                )
    return problems


def top_level_block(text: str, key: str) -> str:
    lines = text.splitlines()
    marker = f"{key}:"
    try:
        start = lines.index(marker)
    except ValueError:
        return ""
    collected: list[str] = []
    for line in lines[start + 1 :]:
        if line and not line.startswith((" ", "\t")):
            break
        collected.append(line)
    return "\n".join(collected)


def nested_event_block(triggers: str, event: str) -> str:
    lines = triggers.splitlines()
    marker = f"  {event}:"
    try:
        start = lines.index(marker)
    except ValueError:
        return ""
    collected: list[str] = []
    for line in lines[start + 1 :]:
        if line.strip() and len(line) - len(line.lstrip()) <= 2:
            break
        collected.append(line)
    return "\n".join(collected)


def read(name: str, problems: list[str]) -> str:
    path = WORKFLOWS / name
    if not path.is_file():
        problems.append(f"missing workflow: {name}")
        return ""
    return path.read_text(encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
