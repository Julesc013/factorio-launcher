from __future__ import annotations

import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PACKAGING = ROOT / "release" / "packaging"

COMPONENT_FIELDS = {
    "name",
    "source_target",
    "destination",
    "required_platform",
    "architecture",
    "hash",
    "signature_policy",
    "extraction_policy",
    "runtime_search_path",
    "license_notice",
}


def main() -> int:
    problems: list[str] = []
    manifests = sorted(PACKAGING.glob("**/*.toml"))
    if not manifests:
        problems.append("no packaging manifests found")
    for path in manifests:
        problems.extend(validate_manifest(path))
    problems.extend(validate_windows_single_exe_policy())
    if problems:
        for problem in problems:
            print(f"package-check: {problem}", file=sys.stderr)
        return 1
    print(f"package-check: ok ({len(manifests)} manifests)")
    return 0


def load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def validate_manifest(path: Path) -> list[str]:
    try:
        manifest = load_toml(path)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return [f"{path}: {exc}"]

    problems: list[str] = []
    schema = str(manifest.get("schema", ""))
    if not schema.startswith("facman.packaging."):
        problems.append(f"{path}: schema must use facman.packaging namespace")

    if manifest.get("python_runtime") is True:
        problems.append(f"{path}: production package must not depend on Python runtime")
    if manifest.get("bundles_factorio_binaries") is True:
        problems.append(f"{path}: must not bundle Factorio binaries")

    if schema == "facman.packaging.bundle_manifest.v1":
        problems.extend(validate_bundle_manifest(path, manifest))
    if schema == "facman.packaging.contract_catalog.v1":
        problems.extend(validate_contract_catalog(path, manifest))
    return problems


def validate_bundle_manifest(path: Path, manifest: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    for key in ["artifact_id", "platform", "package_type"]:
        if not manifest.get(key):
            problems.append(f"{path}: missing {key}")

    components = manifest.get("components", [])
    base_manifest = manifest.get("base_manifest")
    if not components and not base_manifest:
        problems.append(f"{path}: bundle manifest needs components or base_manifest")

    if components:
        names = {str(component.get("name", "")) for component in components}
        for component in components:
            missing = COMPONENT_FIELDS - set(component)
            if missing:
                problems.append(f"{path}: component {component.get('name', '<unnamed>')} missing {sorted(missing)}")
        required = {"contracts_schema", "factorio_content"}
        if not required.issubset(names):
            problems.append(f"{path}: component set must include contracts_schema and factorio_content")
        if any(name.endswith("_shared") for name in names):
            for required_shared in ["ulk_shared", "usk_shared", "flb_factorio_shared"]:
                if required_shared not in names:
                    problems.append(f"{path}: missing {required_shared}")

    platform = manifest.get("platform")
    package_type = manifest.get("package_type")
    if platform == "windows" and package_type == "self_extracting_bootstrapper":
        if manifest.get("extraction_policy") != "localappdata_versioned_runtime":
            problems.append(f"{path}: Windows single EXE must extract to versioned LOCALAPPDATA runtime")
    if platform == "macos" and components:
        for component in components:
            destination = str(component.get("destination", ""))
            source_target = str(component.get("source_target", ""))
            is_resource = "/Contents/Resources/" in destination
            is_data = source_target.startswith("content/") or source_target == "contracts/schema"
            if is_resource and not is_data:
                problems.append(f"{path}: executable/library component in Contents/Resources: {destination}")
    return problems


def validate_windows_single_exe_policy() -> list[str]:
    path = PACKAGING / "windows" / "extract_policy.v1.toml"
    if not path.is_file():
        return [f"{path}: missing extract policy"]
    data = load_toml(path)
    problems: list[str] = []
    if data.get("forbid_temp_execution") is not True:
        problems.append(f"{path}: forbid_temp_execution must be true")
    extract_root = str(data.get("extract_root", ""))
    if "%TEMP%" in extract_root.upper():
        problems.append(f"{path}: extract_root must not use TEMP")
    if "%LOCALAPPDATA%" not in extract_root.upper():
        problems.append(f"{path}: extract_root must use LOCALAPPDATA")
    return problems


def validate_contract_catalog(path: Path, manifest: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    required_profiles = manifest.get("required_profiles", [])
    profiles = manifest.get("profile", [])
    if not isinstance(required_profiles, list) or not required_profiles:
        problems.append(f"{path}: required_profiles must be a non-empty array")
    if not isinstance(profiles, list) or not profiles:
        problems.append(f"{path}: profile entries must be non-empty")
        return problems

    seen = {str(profile.get("id", "")) for profile in profiles}
    for profile_id in sorted(str(item) for item in required_profiles):
        if profile_id not in seen:
            problems.append(f"{path}: missing package profile {profile_id}")

    required_fields = {
        "id",
        "package_kind",
        "minimum_os",
        "architecture",
        "included_executables",
        "included_libraries",
        "contracts_path",
        "content_path",
        "licenses",
        "frontend_manifest",
        "package_manifest",
        "support_matrix",
        "unsupported_commands",
    }
    for profile in profiles:
        profile_id = profile.get("id", "<unnamed>")
        missing = required_fields - set(profile)
        if missing:
            problems.append(f"{path}: profile {profile_id} missing {sorted(missing)}")
            continue
        for path_key in ["contracts_path", "content_path", "frontend_manifest", "package_manifest", "support_matrix"]:
            referenced = ROOT / str(profile[path_key])
            if not referenced.exists():
                problems.append(f"{path}: profile {profile_id} missing {path_key}: {profile[path_key]}")
        for license_path in profile["licenses"]:
            if not (ROOT / str(license_path)).is_file():
                problems.append(f"{path}: profile {profile_id} missing license {license_path}")
        if not isinstance(profile["unsupported_commands"], list):
            problems.append(f"{path}: profile {profile_id} unsupported_commands must be an array")
    return problems


if __name__ == "__main__":
    raise SystemExit(main())
