# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Check the production WinForms package/backend identity boundary."""

from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WINFORMS = ROOT / "apps/gui/windows/winforms"
HARNESS = ROOT / "tests/winforms_backend_identity_harness"


def validate_source() -> list[str]:
    problems: list[str] = []
    identity = (WINFORMS / "PackagedBackendIdentity.cs").read_text(encoding="utf-8")
    client = (WINFORMS / "CliProcessClient.cs").read_text(encoding="utf-8")
    process = (WINFORMS / "WindowsContainedProcess.cs").read_text(encoding="utf-8")
    production_project = (WINFORMS / "FacMan.WinForms.csproj").read_text(
        encoding="utf-8"
    )
    provider_identity = (WINFORMS / "ProviderIdentity.cs").read_text(encoding="utf-8")
    tracked_provider_identity = (
        WINFORMS / "provider_identity.tracked.v1.txt"
    ).read_text(encoding="utf-8")
    transport_harness_project = (
        HARNESS.parent / "winforms_transport_harness" / "FacMan.Transport.Harness.csproj"
    )
    harness_project = transport_harness_project.read_text(encoding="utf-8")
    form = (WINFORMS / "MainForm.cs").read_text(encoding="utf-8")
    live_store = (WINFORMS / "C1LivePresentationStore.cs").read_text(encoding="utf-8")
    for anchor in (
        "GetModuleFileName",
        "FileFlagOpenReparsePoint",
        "GetFileInformationByHandle",
        "GetFinalPathNameByHandle",
        "QueryFullProcessImageName",
        "OpenDirectoryChain",
        "FileShareRead",
        "manifest/package.v1.toml",
        "components.v1.json",
        "manifest/hashes.sha256",
        "manifest/stage.v1.json",
        "release-resolution-set.v1.json",
        "runtime-release-metadata.v1.json",
        "facman.stage_manifest.v1",
        "windows_winforms_technical_preview_x64",
        "CanonicalJson",
        "bin/facman.exe",
        "Sha256File",
        "GeneratedCommandCatalog.CommandCatalogSha256",
        "GeneratedCommandCatalog.ContractSetSha256",
        "facman.backend_identity.v1",
        "flb.factorio",
        "facman.transport_request.v2",
        "facman.transport_response.v2",
        "run.execute",
    ):
        if anchor not in identity:
            problems.append(f"PackagedBackendIdentity.cs missing identity anchor: {anchor}")
    for anchor in (
        "frontend_backend_identity_unavailable",
        "PackagedBackendIdentity.OpenProduction",
        "backend.ValidateHandshake",
        "backend.RevalidateImmediatelyBeforeProcessCreation",
    ):
        if anchor not in client:
            problems.append(f"CliProcessClient.cs missing identity gate: {anchor}")
    if "revalidateImmediatelyBeforeCreateProcess();" not in process:
        problems.append("WindowsContainedProcess does not revalidate inside the CreateProcess boundary")
    if "validateCreatedSuspendedProcess(processHandle);" not in process:
        problems.append("WindowsContainedProcess does not bind the suspended process image")

    production = "\n".join((client, form, live_store))
    for forbidden in (
        'Environment.GetEnvironmentVariable("FACMAN_CLI")',
        "ResolveExecutable(",
        "AppDomain.CurrentDomain.BaseDirectory",
        'return "facman";',
        "BrowseCliPath(",
    ):
        if forbidden in production:
            problems.append(f"production backend substitution remains: {forbidden}")
    for source, token in (
        (identity, "OpenUntrustedTransportTest"),
        (client, "internal CliProcessClient("),
    ):
        position = source.find(token)
        guard = source.rfind("#if FACMAN_TRANSPORT_HARNESS", 0, position)
        end = source.find("#endif", guard)
        if position < 0 or guard < 0 or end < position:
            problems.append(f"the synthetic transport seam is not harness-guarded: {token}")
    if "FACMAN_TRANSPORT_HARNESS" in production_project:
        problems.append("the ordinary WinForms project enables the transport-harness bypass")
    if "FACMAN_TRANSPORT_HARNESS" not in harness_project:
        problems.append("the transport harness does not explicitly enable its synthetic seam")

    with (ROOT / "release/index/workspace_lock.v1.toml").open("rb") as handle:
        lock = tomllib.load(handle)
    pins = {row["id"]: row["pin"] for row in lock["component"]}
    for component_id in ("universal_launcher", "universal_setup"):
        if pins[component_id] not in tracked_provider_identity:
            problems.append(f"WinForms tracked provider identity is stale: {component_id}")
    for anchor in (
        "FacManProviderIdentityFile",
        "provider_identity.tracked.v1.txt",
        "FacMan.WinForms.ProviderIdentity.v1",
        '<Compile Include="ProviderIdentity.cs" />',
    ):
        if anchor not in production_project:
            problems.append(f"WinForms project omits provider identity binding: {anchor}")
    for anchor in (
        "repaired_provider_canary",
        "UniversalLauncherRevision",
        "UniversalSetupRevision",
        "GetManifestResourceStream",
        "new UTF8Encoding(false, true)",
    ):
        if anchor not in provider_identity:
            problems.append(f"WinForms provider identity parser is incomplete: {anchor}")
    return problems


def run_package_harness(package_root: Path, work_dir: Path | None = None) -> int:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from tools.winforms_identity_runtime import run
    return run(package_root, work_dir)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path)
    parser.add_argument("--work-dir", type=Path, help="fresh directory inside an existing owned task root")
    args = parser.parse_args(argv)
    problems = validate_source()
    if problems:
        for problem in problems:
            print(f"winforms-backend-identity-check: {problem}", file=sys.stderr)
        return 1
    if args.package is not None:
        package = args.package.resolve()
        if not package.is_dir():
            print(
                f"winforms-backend-identity-check: package root is absent: {package}",
                file=sys.stderr,
            )
            return 1
        result = run_package_harness(package, args.work_dir)
        if result:
            return result
    print("winforms-backend-identity-check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
