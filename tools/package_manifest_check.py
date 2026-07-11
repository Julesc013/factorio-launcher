from __future__ import annotations

import sys
import tomllib
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import package_layout_check

INDEX = ROOT / "release" / "index"
PROFILES = ROOT / "release" / "profiles"

REQUIRED_PROFILE_IDS = {
    "linux_portable_cli_x64",
    "macos_portable_cli_x64",
    "windows_portable_cli_x64",
    "windows_legacy_winforms_x64",
    "macos_legacy_appkit_x64",
    "linux_x11_gtk_x64",
    "portable_cli_x64",
    "portable_tui_x64",
}

ALLOWED_PACKAGE_TYPES = {
    "portable_zip",
    "installer",
    "app_bundle",
    "dmg",
    "appimage",
    "tarball",
    "source_archive",
    "self_extracting_bootstrapper",
}

REQUIRED_INSTALL_MODES = {"portable", "user", "system"}

DEFERRED_CAPABILITIES = {
    "setup_mutation",
    "network_download",
    "mod_portal_download",
    "server_execution",
    "devtool_execution",
    "auto_update",
}

GUI_MARKERS = {
    "winforms",
    "winui",
    "appkit",
    "swiftui",
    "gtk",
    "qt",
    "FacMan.app",
    "facman-gui",
}

FORBIDDEN_PAYLOAD_MARKERS = {
    "factorio.exe",
    "Factorio.app",
    "steamapps",
    "mod_portal_credentials",
    "password",
    "token",
}


def main() -> int:
    problems: list[str] = []
    profile_paths = sorted(PROFILES.glob("*/profile.toml"))
    profiles_by_id: dict[str, dict[str, Any]] = {}

    for path in profile_paths:
        data = load_toml(path, problems)
        if data is None:
            continue
        profile_id = str(data.get("id", ""))
        if profile_id:
            profiles_by_id[profile_id] = data
        problems.extend(validate_profile(path, data))

    missing_profiles = REQUIRED_PROFILE_IDS - set(profiles_by_id)
    for profile_id in sorted(missing_profiles):
        problems.append(f"missing required release profile {profile_id}")

    problems.extend(validate_release_index(profiles_by_id))

    if problems:
        for problem in problems:
            print(f"package-manifest-check: {problem}", file=sys.stderr)
        return 1
    print(f"package-manifest-check: ok ({len(profile_paths)} release profiles)")
    return 0


def load_toml(path: Path, problems: list[str]) -> dict[str, Any] | None:
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        problems.append(f"{path}: {exc}")
        return None


def validate_release_index(profiles_by_id: dict[str, dict[str, Any]]) -> list[str]:
    problems: list[str] = []
    release_index = load_toml(INDEX / "release_index.v1.toml", problems)
    package_manifest = load_toml(INDEX / "package_manifest.v1.toml", problems)
    support_matrix = load_toml(INDEX / "support_matrix.v1.toml", problems)
    distribution_lanes = load_toml(INDEX / "distribution_lanes.v1.toml", problems)
    if not release_index or not package_manifest or not support_matrix or not distribution_lanes:
        return problems

    if release_index.get("schema") != "facman.release_index.v1":
        problems.append("release/index/release_index.v1.toml: wrong schema")
    if package_manifest.get("schema") != "facman.package_manifest.v1":
        problems.append("release/index/package_manifest.v1.toml: wrong schema")
    if support_matrix.get("schema") != "facman.support_matrix.v1":
        problems.append("release/index/support_matrix.v1.toml: wrong schema")
    if distribution_lanes.get("schema") != "facman.distribution_lane.v1":
        problems.append("release/index/distribution_lanes.v1.toml: wrong schema")

    profile_paths = string_list(package_manifest.get("release_profiles"))
    index_profile_paths = string_list(release_index.get("profiles"))
    if set(profile_paths) != set(index_profile_paths):
        problems.append("release index profiles must match package manifest profiles")
    for relative in sorted(set(profile_paths + index_profile_paths)):
        problems.extend(validate_existing_repo_path("release index profile", relative))

    required_paths = string_list(package_manifest.get("required_paths"))
    if not required_paths:
        problems.append("release/index/package_manifest.v1.toml: required_paths must be non-empty")
    for relative in required_paths:
        problems.extend(validate_existing_repo_path("package required path", relative))

    forbidden_payloads = set(string_list(package_manifest.get("forbidden_payloads")))
    missing_markers = FORBIDDEN_PAYLOAD_MARKERS - forbidden_payloads
    for marker in sorted(missing_markers):
        problems.append(f"release/index/package_manifest.v1.toml: missing forbidden payload marker {marker}")

    matrix_ids = {str(item.get("id", "")) for item in support_matrix.get("platform", [])}
    lane_ids = {str(item.get("id", "")) for item in distribution_lanes.get("lane", [])}
    for profile_id in sorted(REQUIRED_PROFILE_IDS):
        if profile_id not in matrix_ids:
            problems.append(f"release/index/support_matrix.v1.toml: missing {profile_id}")
        if profile_id not in lane_ids:
            problems.append(f"release/index/distribution_lanes.v1.toml: missing {profile_id}")
        if profile_id not in profiles_by_id:
            continue
        profile = profiles_by_id[profile_id]
        if profile_id not in profile_path_ids(profile_paths):
            problems.append(f"release/index/package_manifest.v1.toml: missing profile path for {profile_id}")
        lane = next((item for item in distribution_lanes.get("lane", []) if item.get("id") == profile_id), None)
        if lane:
            problems.extend(validate_lane_matches_profile(profile_id, lane, profile))

    return problems


def validate_profile(path: Path, profile: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    required_fields = {
        "schema",
        "id",
        "lane",
        "target_os",
        "target_arch",
        "minimum_os",
        "package_types",
        "install_modes",
        "package_manifest",
        "frontend_manifest",
        "support_matrix",
        "contracts_path",
        "content_path",
        "licenses",
    }
    missing = required_fields - set(profile)
    if missing:
        problems.append(f"{path}: missing {sorted(missing)}")
        return problems
    if profile.get("schema") != "facman.release_profile.v1":
        problems.append(f"{path}: schema must be facman.release_profile.v1")

    profile_id = str(profile.get("id", ""))
    if path.parent.name != profile_id:
        problems.append(f"{path}: profile id must match directory name")

    package_types = set(string_list(profile.get("package_types")))
    unknown_package_types = package_types - ALLOWED_PACKAGE_TYPES
    for package_type in sorted(unknown_package_types):
        problems.append(f"{path}: unsupported package type {package_type}")

    install_modes = set(string_list(profile.get("install_modes")))
    if install_modes != REQUIRED_INSTALL_MODES:
        problems.append(f"{path}: install_modes must be portable, user, and system")

    if profile.get("bundles_factorio_binaries") is not False:
        problems.append(f"{path}: bundles_factorio_binaries must be false")
    if profile.get("credential_storage") is not False:
        problems.append(f"{path}: credential_storage must be false")

    for key in [
        "package_manifest",
        "frontend_manifest",
        "support_matrix",
        "release_index",
        "contracts_path",
        "content_path",
    ]:
        value = str(profile.get(key, ""))
        problems.extend(validate_existing_repo_path(f"{path} {key}", value))

    for license_path in string_list(profile.get("licenses")):
        problems.extend(validate_existing_repo_path(f"{path} license", license_path))

    frontends = table(profile.get("frontends"))
    entrypoints = table(profile.get("entrypoints"))
    required_components = table(profile.get("required_components"))
    capabilities = table(profile.get("capabilities"))
    unsupported = table(profile.get("unsupported"))

    problems.extend(validate_frontends(path, frontends, entrypoints))
    problems.extend(validate_required_components(path, required_components))
    problems.extend(validate_capabilities(path, capabilities, unsupported))
    problems.extend(validate_path_values(path, profile))
    problems.extend(validate_no_gui_leak(path, frontends, profile))
    problems.extend(validate_package_manifest_alignment(path, profile, entrypoints, required_components))
    return problems


def validate_frontends(path: Path, frontends: dict[str, Any], entrypoints: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    if not frontends:
        problems.append(f"{path}: frontends table is required")
    if not entrypoints:
        problems.append(f"{path}: entrypoints table is required")
    required = set(frontends)
    missing = required - set(entrypoints)
    if missing:
        problems.append(f"{path}: entrypoints missing {sorted(missing)}")
    for frontend_path in frontends.values():
        if not (ROOT / str(frontend_path)).exists():
            problems.append(f"{path}: frontend path does not exist: {frontend_path}")
    return problems


def validate_required_components(path: Path, required_components: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    required = {
        "binaries",
        "libraries",
        "contracts",
        "content",
        "licenses",
        "frontend_manifest",
        "package_manifest",
        "support_matrix",
    }
    missing = required - set(required_components)
    if missing:
        problems.append(f"{path}: required_components missing {sorted(missing)}")
    if not string_list(required_components.get("binaries")):
        problems.append(f"{path}: required_components.binaries must be non-empty")
    if not isinstance(required_components.get("libraries", []), list):
        problems.append(f"{path}: required_components.libraries must be an array")
    if not string_list(required_components.get("licenses")):
        problems.append(f"{path}: required_components.licenses must be non-empty")
    return problems


def validate_capabilities(
    path: Path,
    capabilities: dict[str, Any],
    unsupported: dict[str, Any],
) -> list[str]:
    problems: list[str] = []
    unsupported_features = set(string_list(unsupported.get("features")))
    for capability in sorted(DEFERRED_CAPABILITIES):
        if capabilities.get(capability) is not False:
            problems.append(f"{path}: capability {capability} must be explicitly false")
        if capability not in unsupported_features:
            problems.append(f"{path}: unsupported.features must include {capability}")
    if not string_list(unsupported.get("commands")):
        problems.append(f"{path}: unsupported.commands must be non-empty")
    return problems


def validate_path_values(path: Path, profile: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    for label, value in iter_string_values(profile):
        if label.endswith(".schema"):
            continue
        if looks_like_path(value):
            path_problem = validate_relative_path(path, label, value)
            if path_problem:
                problems.append(path_problem)
    return problems


def validate_no_gui_leak(path: Path, frontends: dict[str, Any], profile: dict[str, Any]) -> list[str]:
    if "gui" in frontends:
        return []
    problems: list[str] = []
    for label, value in iter_string_values(profile):
        if any(marker.lower() in value.lower() for marker in GUI_MARKERS):
            problems.append(f"{path}: CLI/TUI-only profile leaks GUI marker in {label}: {value}")
    return problems


def validate_package_manifest_alignment(
    path: Path,
    profile: dict[str, Any],
    entrypoints: dict[str, Any],
    required_components: dict[str, Any],
) -> list[str]:
    problems: list[str] = []
    package_manifest_path = ROOT / str(profile.get("package_manifest", ""))
    bundle = load_toml(package_manifest_path, problems)
    if not bundle:
        return problems
    try:
        expanded = package_layout_check.expand_bundle_manifest(package_manifest_path, bundle, [])
    except (OSError, tomllib.TOMLDecodeError, ValueError) as exc:
        return [f"{path}: cannot expand package manifest: {exc}"]

    if expanded.get("schema") != "facman.packaging.bundle_manifest.v1":
        problems.append(f"{path}: package_manifest must point at a bundle manifest")
        return problems
    if expanded.get("bundles_factorio_binaries") is not False:
        problems.append(f"{path}: package manifest must not bundle Factorio binaries")
    package_type = str(expanded.get("package_type", ""))
    if package_type not in set(string_list(profile.get("package_types"))):
        problems.append(f"{path}: package_types must include bundle package_type {package_type}")

    destinations = {
        package_layout_check.normalize_layout_path(str(component.get("destination", "")))
        for component in expanded.get("components", [])
    }
    for binary in string_list(required_components.get("binaries")):
        if package_layout_check.normalize_layout_path(binary) not in destinations:
            problems.append(f"{path}: required binary not present in package layout: {binary}")
    for library in string_list(required_components.get("libraries")):
        if package_layout_check.normalize_layout_path(library) not in destinations:
            problems.append(f"{path}: required library not present in package layout: {library}")
    for role, entrypoint in entrypoints.items():
        normalized = package_layout_check.normalize_layout_path(str(entrypoint))
        if normalized not in destinations:
            problems.append(f"{path}: {role} entrypoint missing from package layout: {entrypoint}")
    return problems


def validate_lane_matches_profile(
    profile_id: str,
    lane: dict[str, Any],
    profile: dict[str, Any],
) -> list[str]:
    problems: list[str] = []
    for key in ["target_os", "target_arch"]:
        if str(lane.get(key, "")) != str(profile.get(key, "")):
            problems.append(f"release/index/distribution_lanes.v1.toml: {profile_id} {key} mismatch")
    lane_types = set(string_list(lane.get("package_types")))
    profile_types = set(string_list(profile.get("package_types")))
    if lane_types != profile_types:
        problems.append(f"release/index/distribution_lanes.v1.toml: {profile_id} package_types mismatch")
    if set(string_list(lane.get("install_modes"))) != set(string_list(profile.get("install_modes"))):
        problems.append(f"release/index/distribution_lanes.v1.toml: {profile_id} install_modes mismatch")
    return problems


def validate_existing_repo_path(label: str, value: str) -> list[str]:
    if not value:
        return [f"{label}: path is empty"]
    path_problem = validate_relative_path(Path(label.split(":")[0]), label, value)
    if path_problem:
        return [path_problem]
    if not (ROOT / value).exists():
        return [f"{label}: missing {value}"]
    return []


def validate_relative_path(path: Path, label: str, value: str) -> str | None:
    if "\\" in value:
        return f"{path}: {label} must use forward slashes: {value}"
    if ":" in value:
        return f"{path}: {label} must not contain drive or URI separators: {value}"
    pure = PurePosixPath(value)
    if pure.is_absolute():
        return f"{path}: {label} must be relative: {value}"
    if any(part in ("", ".", "..") for part in pure.parts):
        return f"{path}: {label} must not contain empty/current/parent segments: {value}"
    return None


def iter_string_values(value: Any, prefix: str = "") -> list[tuple[str, str]]:
    values: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            next_prefix = f"{prefix}.{key}" if prefix else str(key)
            values.extend(iter_string_values(item, next_prefix))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            values.extend(iter_string_values(item, f"{prefix}[{index}]"))
    elif isinstance(value, str):
        values.append((prefix, value))
    return values


def looks_like_path(value: str) -> bool:
    return "/" in value or "\\" in value or value.endswith((".toml", ".md", ".exe"))


def profile_path_ids(profile_paths: list[str]) -> set[str]:
    return {PurePosixPath(path).parent.name for path in profile_paths}


def string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def table(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


if __name__ == "__main__":
    raise SystemExit(main())
