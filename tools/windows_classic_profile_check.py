# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Validate the non-authorizing post-C1 Windows Classic preparation."""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.universal_delivery_programme_check import WINDOWS_CLASSIC_GATES  # noqa: E402

INDEX = ROOT / "release" / "index"
WINFORMS = ROOT / "apps" / "gui" / "windows" / "winforms"

AUTHORITY_CEILING = {
    "provider_adoption": False,
    "setup_mutation": False,
    "factorio_execution": False,
    "signing": False,
    "publication": False,
    "route_promotion": False,
    "support_claim": False,
}
PACKAGE_AUTHORITY_CEILING = {**AUTHORITY_CEILING, "setup_mutation": True}

TARGET_PROFILES = {
    "win_x64_c1": ("net48", "x86_64", "implemented_reference"),
    "win_x64_primary": ("net48", "x86_64", "later"),
    "win_x86_compat": ("net40", "x86", "later"),
}

QUALIFICATION_HOSTS = {
    "windows_xp_sp3_x86",
    "windows_vista_sp2_x86",
    "windows_vista_sp2_x64_via_wow64",
    "windows_7_sp1",
    "windows_8_1",
    "windows_10",
    "windows_11",
}

DOCUMENT_ANCHORS = {
    "product": (
        "Status: ratified post-C1 product direction; non-authorizing",
        "one shared Windows Forms shell source",
        "Whole-product qualification law",
        "Compilation alone produces no support status.",
    ),
    "architecture": (
        "Status: ratified post-C1 architecture; no implementation authority",
        "ShellSnapshot",
        "SemanticAction",
        "Common Controls v6",
    ),
    "generation": (
        "Status: non-authoritative rendering and fixture reference",
        "Generated images and code are proposals",
        "Do not depict Play, Setup, publication, or signing as already authorized.",
    ),
}


def _toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def load_inputs() -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, str],
    str,
    str,
    list[str],
]:
    documents = {
        "product": (ROOT / "docs" / "product" / "windows_classic_profile.md").read_text(
            encoding="utf-8"
        ),
        "architecture": (
            ROOT / "docs" / "architecture" / "winforms_architecture.md"
        ).read_text(encoding="utf-8"),
        "generation": (
            ROOT / "docs" / "design" / "winforms_generation_brief.md"
        ).read_text(encoding="utf-8"),
    }
    source_paths = [
        path.relative_to(ROOT).as_posix()
        for path in WINFORMS.rglob("*")
        if path.is_dir()
    ]
    return (
        _toml(INDEX / "windows_target_profiles.v1.toml"),
        _toml(INDEX / "windows_package_profiles.v1.toml"),
        _toml(INDEX / "windows_qualification.v1.toml"),
        _toml(INDEX / "plan.v1.toml"),
        _toml(INDEX / "release_index.v1.toml"),
        documents,
        (WINFORMS / "FacMan.WinForms.csproj").read_text(encoding="utf-8"),
        (WINFORMS / "app.manifest").read_text(encoding="utf-8"),
        source_paths,
    )


def _validate_authority(document: dict[str, Any], label: str, problems: list[str]) -> None:
    expected = PACKAGE_AUTHORITY_CEILING if label == "packages" else AUTHORITY_CEILING
    if document.get("authority") != expected:
        problems.append(f"{label} must retain the exact non-authorizing authority ceiling")


def validate(
    targets: dict[str, Any],
    packages: dict[str, Any],
    qualification: dict[str, Any],
    plan: dict[str, Any],
    release_index: dict[str, Any],
    documents: dict[str, str],
    project: str,
    manifest: str,
    source_paths: list[str],
) -> list[str]:
    problems: list[str] = []

    expected_schemas = {
        "targets": "facman.windows_target_profiles.v1",
        "packages": "facman.windows_package_profiles.v1",
        "qualification": "facman.windows_qualification.v1",
    }
    for label, document in (
        ("targets", targets),
        ("packages", packages),
        ("qualification", qualification),
    ):
        if document.get("schema") != expected_schemas[label]:
            problems.append(f"Windows {label} record has the wrong schema")
        expected_status = (
            "alpha2_candidate_non_authorizing"
            if label == "packages"
            else "prepared_non_authorizing"
        )
        if document.get("status") != expected_status:
            problems.append(f"Windows {label} record must remain {expected_status}")
        _validate_authority(document, label, problems)

    index_paths = {
        "windows_target_profiles": "release/index/windows_target_profiles.v1.toml",
        "windows_package_profiles": "release/index/windows_package_profiles.v1.toml",
        "windows_qualification": "release/index/windows_qualification.v1.toml",
    }
    for key, value in index_paths.items():
        if release_index.get(key) != value:
            problems.append(f"release index must bind {key} to {value}")

    profiles = {item.get("id"): item for item in targets.get("managed_host_profile", [])}
    if set(profiles) != set(TARGET_PROFILES):
        problems.append("Windows target profiles must remain the exact C1, x64, and x86 set")
    for profile_id, expected in TARGET_PROFILES.items():
        profile = profiles.get(profile_id, {})
        actual = (
            profile.get("framework_target"),
            profile.get("architecture"),
            profile.get("planning_state"),
        )
        if actual != expected:
            problems.append(f"{profile_id} framework, architecture, or planning state drifted")
        if profile.get("source_family") != "shared_winforms_shell":
            problems.append(f"{profile_id} must use the shared WinForms shell source")
        if profile.get("support_status") != "none" or profile.get("release_authorized") is not False:
            problems.append(f"{profile_id} cannot acquire support or release authority from planning")
    compatibility = profiles.get("win_x86_compat", {})
    if compatibility.get("minimum_xp_runtime_objective") != "net_framework_4_0_3":
        problems.append("win_x86_compat must retain the bounded .NET Framework 4.0.3 objective")
    if compatibility.get("legacy_build_toolchain_required") is not True:
        problems.append("win_x86_compat must require a separately reviewed legacy toolchain")
    if targets.get("common_controls_v6_evidence") != "exact_built_binary_verification_required":
        problems.append("Common Controls v6 must remain an exact-built-binary evidence obligation")

    expected_dimensions = [
        "target_profile",
        "product_composition",
        "package_projection",
        "support_claim",
        "release_resolution",
    ]
    if packages.get("dimensions") != expected_dimensions:
        problems.append("Windows package dimensions must remain orthogonal and ordered")
    if packages.get("frontend_is_distribution_identity") is not False:
        problems.append("frontend cannot become a Windows distribution identity")
    if "install_modes" in packages or "frontend_family" in packages:
        problems.append("Windows package profiles cannot encode frontend-specific install modes")
    if packages.get("portable_projection_has_install_mode") is not False:
        problems.append("portable package projections cannot acquire an install mode")
    if packages.get("installation_mode_owner") != "universal_setup_plan":
        problems.append("Universal Setup plans must remain the installation-mode owner")

    compositions = {
        item.get("id"): item for item in packages.get("product_composition", [])
    }
    desktop = compositions.get("windows_desktop", {})
    for capability in (
        "native_shell",
        "cli_backend",
        "contracts",
        "provider_runtime",
        "recovery_material",
    ):
        if capability not in desktop.get("capabilities", []):
            problems.append(f"Windows desktop composition omits {capability}")
    for projection in packages.get("package_projection", []):
        projection_id = projection.get("id", "<projection>")
        if projection.get("release_authorized") is not False:
            problems.append(f"{projection_id} cannot acquire release authority")
        if projection.get("publication_authorized") is not False:
            problems.append(f"{projection_id} cannot acquire publication authority")
        alpha2_setup = projection_id in {
            "win_x64_primary_setup_exe",
            "win_x64_primary_self_setup_payload",
        }
        if projection.get("setup_mutation") is not alpha2_setup:
            problems.append(f"{projection_id} has the wrong bounded Setup mutation capability")
        if alpha2_setup:
            if projection.get("status") != "alpha2_candidate":
                problems.append(f"{projection_id} must remain an alpha2 candidate")
            expected_requirement = (
                "exact_sibling_self_setup_payload_and_operator_yes"
                if projection_id == "win_x64_primary_setup_exe"
                else "exact_hash_verified_by_facman_setup"
            )
            if projection.get("activation_requirement") != expected_requirement:
                problems.append(f"{projection_id} has the wrong alpha2 activation requirement")
        elif projection.get("package_type") == "setup_executable":
            if projection.get("status") != "deferred":
                problems.append(f"{projection_id} must remain deferred")
            if projection.get("activation_requirement") != "production_ready_usk_lifecycle":
                problems.append(f"{projection_id} must depend on a production-ready USK lifecycle")

    if qualification.get("whole_product_closure_required") is not True:
        problems.append("Windows qualification must cover the whole product closure")
    if qualification.get("compile_is_support_evidence") is not False:
        problems.append("compilation cannot become Windows support evidence")
    if qualification.get("managed_host_is_support_evidence") is not False:
        problems.append("the managed host alone cannot become Windows support evidence")
    rows = {
        item.get("id"): item for item in qualification.get("host_qualification", [])
    }
    if set(rows) != QUALIFICATION_HOSTS:
        problems.append("Windows qualification must retain the exact prepared host set")
    for host_id, row in rows.items():
        if row.get("qualification_status") != "unqualified":
            problems.append(f"{host_id} cannot be qualified by a planning record")
        if row.get("support_status") != "none" or row.get("evidence") != []:
            problems.append(f"{host_id} cannot acquire support or evidence from planning")
        if row.get("release_authorized") is not False:
            problems.append(f"{host_id} cannot acquire release authority")

    workunits = {item.get("id") for item in plan.get("workunit", [])}
    later = {item.get("id"): item for item in plan.get("later", [])}
    misplaced = sorted(WINDOWS_CLASSIC_GATES & workunits)
    if misplaced:
        problems.append("Windows Classic gates cannot enter active work: " + ", ".join(misplaced))
    missing = sorted(WINDOWS_CLASSIC_GATES - set(later))
    if missing:
        problems.append("canonical plan omits Windows Classic gates: " + ", ".join(missing))
    for workunit_id in sorted(WINDOWS_CLASSIC_GATES & set(later)):
        if "C1 is release-proven" not in str(later[workunit_id].get("trigger", "")):
            problems.append(f"{workunit_id} must remain gated on release-proven C1")

    for label, anchors in DOCUMENT_ANCHORS.items():
        content = " ".join(documents.get(label, "").split())
        for anchor in anchors:
            if anchor not in content:
                problems.append(f"Windows {label} document is missing anchor: {anchor}")

    for marker in ("<TargetFrameworkVersion>v4.8</TargetFrameworkVersion>", "<PlatformTarget>x64</PlatformTarget>"):
        if marker not in project:
            problems.append(f"current C1 project must remain unchanged at {marker}")
    for marker in ('level="asInvoker"', ">PerMonitorV2</dpiAwareness>"):
        if marker not in manifest:
            problems.append(f"current C1 manifest must retain {marker}")

    forbidden_parts = {"xp", "vista", "win7plus"}
    for path in source_paths:
        if forbidden_parts & {part.lower() for part in Path(path).parts}:
            problems.append(f"operating-system-named WinForms source family is forbidden: {path}")

    return problems


def detect() -> list[str]:
    try:
        return validate(*load_inputs())
    except (OSError, tomllib.TOMLDecodeError, ValueError) as error:
        return [str(error)]


def main() -> int:
    problems = detect()
    if problems:
        for problem in problems:
            print(f"windows-classic-profile-check: {problem}", file=sys.stderr)
        return 1
    print(
        "windows-classic-profile-check: ok "
        f"({len(TARGET_PROFILES)} profiles, {len(QUALIFICATION_HOSTS)} hosts, "
        f"{len(WINDOWS_CLASSIC_GATES)} later gates)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
