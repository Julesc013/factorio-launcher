from __future__ import annotations

import argparse
import json
import sys
import tempfile
import tomllib
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import package_manifest_check, package_skeleton_build

REQUIRED_CAPABILITIES_FALSE = {
    "setup_mutation",
    "network_download",
    "mod_portal_download",
    "server_execution",
    "devtool_execution",
    "auto_update",
}

SECRET_FILENAME_MARKERS = {
    "credential",
    "mod_portal_credentials",
    "password",
    "secret",
    "token",
}


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = []
    parser = argparse.ArgumentParser(description="Validate generated FacMan package skeleton layouts.")
    parser.add_argument("--root", help="existing package skeleton root to validate")
    args = parser.parse_args(argv)

    if args.root:
        root = Path(args.root).resolve()
        problems = validate_root(root)
        count = count_profile_skeletons(root)
    else:
        with tempfile.TemporaryDirectory(prefix="facman-package-skeleton-") as tmp:
            root = Path(tmp) / "package-skeletons"
            package_skeleton_build.materialize_all(root, clean=True)
            problems = validate_root(root)
            count = count_profile_skeletons(root)

    if problems:
        for problem in problems:
            print(f"package-skeleton-check: {problem}", file=sys.stderr)
        return 1
    print(f"package-skeleton-check: ok ({count} skeletons)")
    return 0


def validate_root(root: Path) -> list[str]:
    problems: list[str] = []
    if not root.is_dir():
        return [f"{root}: skeleton root missing"]
    profiles = package_skeleton_build.load_profiles()
    for profile_path, profile in profiles:
        profile_id = str(profile.get("id", ""))
        skeleton_root = root / profile_id
        problems.extend(validate_profile_skeleton(root, skeleton_root, profile_path, profile))
    problems.extend(validate_no_forbidden_files(root))
    return problems


def validate_profile_skeleton(
    all_skeletons_root: Path,
    skeleton_root: Path,
    profile_path: Path,
    profile: dict[str, Any],
) -> list[str]:
    profile_id = str(profile.get("id", ""))
    problems: list[str] = []
    if not skeleton_root.is_dir():
        return [f"{profile_id}: skeleton directory missing under {all_skeletons_root}"]

    support = package_skeleton_build.support_paths(profile)
    for label, relative in support.items():
        path = skeleton_root / relative
        if not path.is_dir():
            problems.append(f"{profile_id}: missing {label} directory {relative}")

    manifest_dir = skeleton_root / support["manifest"]
    skeleton_json = manifest_dir / "skeleton.v1.json"
    package_toml = manifest_dir / "package.v1.toml"
    components_toml = manifest_dir / "components.v1.toml"
    for path in [skeleton_json, package_toml, components_toml]:
        if not path.is_file():
            problems.append(f"{profile_id}: missing manifest file {path.relative_to(skeleton_root).as_posix()}")

    marker = load_json(skeleton_json, problems)
    components = load_components(components_toml, problems)
    if marker:
        problems.extend(validate_skeleton_marker(profile_id, profile_path, profile, support, marker))
    if components:
        problems.extend(validate_component_manifest(profile_id, skeleton_root, components))

    problems.extend(validate_entrypoints(profile_id, skeleton_root, profile))
    problems.extend(validate_capabilities(profile_id, profile, marker))
    problems.extend(validate_platform_rules(profile_id, skeleton_root, profile, marker))
    return problems


def validate_skeleton_marker(
    profile_id: str,
    profile_path: Path,
    profile: dict[str, Any],
    support: dict[str, str],
    marker: dict[str, Any],
) -> list[str]:
    problems: list[str] = []
    if marker.get("schema") != "facman.package_skeleton.v1":
        problems.append(f"{profile_id}: skeleton marker has wrong schema")
    if marker.get("real_artifact") is not False:
        problems.append(f"{profile_id}: skeleton marker must set real_artifact false")
    if marker.get("purpose") != "layout validation only":
        problems.append(f"{profile_id}: skeleton marker must be layout validation only")
    if marker.get("profile_id") != profile_id:
        problems.append(f"{profile_id}: skeleton marker profile_id mismatch")
    expected_profile = profile_path.relative_to(ROOT).as_posix()
    if marker.get("release_profile") != expected_profile:
        problems.append(f"{profile_id}: skeleton marker release_profile mismatch")
    if marker.get("support_paths") != support:
        problems.append(f"{profile_id}: skeleton marker support_paths mismatch")
    if marker.get("entrypoints") != package_skeleton_build.table(profile.get("entrypoints")):
        problems.append(f"{profile_id}: skeleton marker entrypoints mismatch")
    return problems


def validate_component_manifest(
    profile_id: str,
    skeleton_root: Path,
    components: list[dict[str, Any]],
) -> list[str]:
    problems: list[str] = []
    seen_destinations: dict[str, str] = {}
    for component in components:
        name = str(component.get("name", "<unnamed>"))
        destination = str(component.get("destination", ""))
        placeholder = str(component.get("placeholder", ""))
        path_problem = validate_relative_path(profile_id, f"component {name} destination", destination)
        if path_problem:
            problems.append(path_problem)
        placeholder_problem = validate_relative_path(profile_id, f"component {name} placeholder", placeholder)
        if placeholder_problem:
            problems.append(placeholder_problem)
        normalized = destination.rstrip("/")
        if normalized in seen_destinations:
            problems.append(
                f"{profile_id}: duplicate package destination {normalized}: "
                f"{seen_destinations[normalized]} and {name}"
            )
        seen_destinations[normalized] = name
        if placeholder and not (skeleton_root / placeholder).exists():
            problems.append(f"{profile_id}: component {name} placeholder missing: {placeholder}")
    return problems


def validate_entrypoints(profile_id: str, skeleton_root: Path, profile: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    entrypoints = package_skeleton_build.table(profile.get("entrypoints"))
    for role, relative in entrypoints.items():
        placeholder = placeholder_path_for(skeleton_root, str(relative))
        if not placeholder.is_file():
            problems.append(f"{profile_id}: missing {role} entrypoint placeholder {relative}.placeholder")
    return problems


def validate_capabilities(
    profile_id: str,
    profile: dict[str, Any],
    marker: dict[str, Any] | None,
) -> list[str]:
    problems: list[str] = []
    profile_capabilities = package_skeleton_build.table(profile.get("capabilities"))
    marker_capabilities = package_skeleton_build.table(marker.get("capabilities")) if marker else {}
    for capability in sorted(REQUIRED_CAPABILITIES_FALSE):
        if profile_capabilities.get(capability) is not False:
            problems.append(f"{profile_id}: profile capability {capability} must remain false")
        if marker and marker_capabilities.get(capability) is not False:
            problems.append(f"{profile_id}: skeleton capability {capability} must remain false")
    return problems


def validate_platform_rules(
    profile_id: str,
    skeleton_root: Path,
    profile: dict[str, Any],
    marker: dict[str, Any] | None,
) -> list[str]:
    problems: list[str] = []
    target_os = str(profile.get("target_os", ""))
    entrypoints = package_skeleton_build.table(marker.get("entrypoints")) if marker else {}
    if target_os == "linux" and "gui" in entrypoints:
        gui_entrypoint = str(entrypoints.get("gui", ""))
        if gui_entrypoint != "usr/bin/facman-gui-gtk":
            problems.append(f"{profile_id}: Linux GTK gui entrypoint must be usr/bin/facman-gui-gtk")
    if target_os == "macos" and "gui" in package_skeleton_build.table(profile.get("frontends")):
        resources = skeleton_root / "FacMan.app" / "Contents" / "Resources"
        allowed = {
            resources / "contracts",
            resources / "content",
            resources / "docs",
            resources / "licenses",
            resources / "manifest",
            resources / "release",
        }
        for placeholder in resources.rglob("*.placeholder"):
            if not any(parent == placeholder or parent in placeholder.parents for parent in allowed):
                relative = placeholder.relative_to(skeleton_root).as_posix()
                problems.append(f"{profile_id}: executable/library placeholder under Resources: {relative}")
    return problems


def validate_no_forbidden_files(root: Path) -> list[str]:
    problems: list[str] = []
    forbidden = set(package_manifest_check.FORBIDDEN_PAYLOAD_MARKERS) | SECRET_FILENAME_MARKERS
    for path in root.rglob("*"):
        if not path.exists():
            continue
        relative = path.relative_to(root).as_posix()
        leaf = path.name.lower()
        for marker in sorted(forbidden):
            lowered = marker.lower()
            if lowered in leaf or lowered in relative.lower():
                problems.append(f"{relative}: forbidden package skeleton payload marker {marker}")
    return problems


def placeholder_path_for(root: Path, relative: str) -> Path:
    path = root / relative
    return path.with_name(f"{path.name}.placeholder")


def load_json(path: Path, problems: list[str]) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        problems.append(f"{path}: {exc}")
        return None
    return data if isinstance(data, dict) else None


def load_components(path: Path, problems: list[str]) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        problems.append(f"{path}: {exc}")
        return []
    components = data.get("component", [])
    if not isinstance(components, list):
        problems.append(f"{path}: component entries must be an array")
        return []
    return [component for component in components if isinstance(component, dict)]


def validate_relative_path(profile_id: str, label: str, value: str) -> str | None:
    if not value:
        return f"{profile_id}: {label} is empty"
    if "\\" in value:
        return f"{profile_id}: {label} must use forward slashes: {value}"
    if ":" in value:
        return f"{profile_id}: {label} must not contain drive or URI separators: {value}"
    pure = PurePosixPath(value)
    if pure.is_absolute():
        return f"{profile_id}: {label} must be relative: {value}"
    if any(part in ("", ".", "..") for part in pure.parts):
        return f"{profile_id}: {label} must not contain empty/current/parent segments: {value}"
    return None


def count_profile_skeletons(root: Path) -> int:
    if not root.is_dir():
        return 0
    return sum(1 for path in root.iterdir() if path.is_dir())


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
