from __future__ import annotations

import sys
import tomllib
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PACKAGING = ROOT / "release" / "packaging"

WRAPPER_PACKAGE_TYPES = {
    "appimage",
    "installer",
    "self_extracting_bootstrapper",
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

FORBIDDEN_PAYLOAD_MARKERS = {
    "factorio.exe",
    "Factorio.app",
    "steamapps",
    "mod_portal_credentials",
    "password",
    "token",
}

GUI_TOOLKIT_MARKERS = {
    "winforms",
    "winui",
    "appkit",
    "swiftui",
    "gtk",
    "qt",
    "FacMan.exe",
    "FacMan.app",
    "facman-gui",
}


def main() -> int:
    problems: list[str] = []
    manifests = sorted(PACKAGING.glob("**/*.toml"))
    bundle_manifests = [path for path in manifests if load_schema(path) == "facman.packaging.bundle_manifest.v1"]
    if not bundle_manifests:
        problems.append("no bundle manifests found")
    for path in bundle_manifests:
        problems.extend(validate_bundle_layout(path))
    if problems:
        for problem in problems:
            print(f"package-layout-check: {problem}", file=sys.stderr)
        return 1
    print(f"package-layout-check: ok ({len(bundle_manifests)} bundle manifests)")
    return 0


def load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def load_schema(path: Path) -> str:
    try:
        return str(load_toml(path).get("schema", ""))
    except (OSError, tomllib.TOMLDecodeError):
        return ""


def validate_bundle_layout(path: Path) -> list[str]:
    try:
        manifest = load_toml(path)
        expanded = expand_bundle_manifest(path, manifest, [])
    except (OSError, tomllib.TOMLDecodeError, ValueError) as exc:
        return [f"{path}: {exc}"]

    problems: list[str] = []
    package_type = str(expanded.get("package_type", ""))
    entrypoint = str(expanded.get("entrypoint", ""))
    platform = str(expanded.get("platform", ""))
    components = expanded.get("components", [])
    if not isinstance(components, list) or not components:
        return [f"{path}: expanded bundle has no components"]
    if package_type not in ALLOWED_PACKAGE_TYPES:
        problems.append(f"{path}: unsupported package_type {package_type}")
    if expanded.get("bundles_factorio_binaries") is not False:
        problems.append(f"{path}: bundles_factorio_binaries must be false")

    normalized_destinations: dict[str, str] = {}
    component_names: set[str] = set()
    for component in components:
        name = str(component.get("name", ""))
        source_target = str(component.get("source_target", ""))
        destination = str(component.get("destination", ""))
        license_notice = str(component.get("license_notice", ""))
        component_names.add(name)
        for label, value in [
            (f"component {name} source_target", source_target),
            (f"component {name} destination", destination),
            (f"component {name} license_notice", license_notice),
        ]:
            problems.extend(validate_no_forbidden_payload_marker(path, label, value))
        destination_problem = validate_relative_layout_path(path, f"component {name} destination", destination)
        if destination_problem:
            problems.append(destination_problem)
            continue
        if "/" in source_target or "\\" in source_target:
            source_problem = validate_relative_layout_path(path, f"component {name} source_target", source_target)
            if source_problem:
                problems.append(source_problem)
        if not license_notice:
            problems.append(f"{path}: component {name} missing license_notice")
        elif not (ROOT / license_notice).is_file():
            problems.append(f"{path}: component {name} license_notice does not exist: {license_notice}")
        normalized = normalize_layout_path(destination)
        if normalized in normalized_destinations:
            first = normalized_destinations[normalized]
            problems.append(f"{path}: duplicate package destination {normalized}: {first} and {name}")
        normalized_destinations[normalized] = name

    if "contracts_schema" not in component_names:
        problems.append(f"{path}: expanded layout missing contracts_schema component")
    if "factorio_content" not in component_names:
        problems.append(f"{path}: expanded layout missing factorio_content component")
    problems.extend(validate_named_destination_contains(path, components, "contracts_schema", "contracts/schema"))
    problems.extend(validate_named_destination_contains(path, components, "factorio_content", "content/factorio"))
    if platform == "portable" or expanded.get("gui_stack_required") is False:
        problems.extend(validate_no_gui_toolkit_leak(path, components))

    if not entrypoint:
        problems.append(f"{path}: expanded layout missing entrypoint")
    else:
        entrypoint_problem = validate_relative_layout_path(path, "entrypoint", entrypoint)
        if entrypoint_problem:
            problems.append(entrypoint_problem)
        elif normalize_layout_path(entrypoint) not in normalized_destinations and package_type not in WRAPPER_PACKAGE_TYPES:
            problems.append(f"{path}: entrypoint {entrypoint} is not a component destination")

    return problems


def expand_bundle_manifest(path: Path, manifest: dict[str, Any], stack: list[Path]) -> dict[str, Any]:
    if path in stack:
        chain = " -> ".join(item.as_posix() for item in [*stack, path])
        raise ValueError(f"base_manifest cycle: {chain}")
    expanded = dict(manifest)
    base_manifest = manifest.get("base_manifest")
    if base_manifest:
        base_path = ROOT / str(base_manifest)
        base = expand_bundle_manifest(base_path, load_toml(base_path), [*stack, path])
        merged = dict(base)
        merged.update({key: value for key, value in manifest.items() if key != "base_manifest"})
        if not manifest.get("components"):
            merged["components"] = base.get("components", [])
        expanded = merged
    return expanded


def validate_relative_layout_path(path: Path, label: str, value: str) -> str | None:
    if not value:
        return f"{path}: {label} is empty"
    if "\\" in value:
        return f"{path}: {label} must use portable forward slashes: {value}"
    if ":" in value:
        return f"{path}: {label} must not contain drive or URI separators: {value}"
    normalized = normalize_layout_path(value)
    pure = PurePosixPath(normalized)
    if pure.is_absolute():
        return f"{path}: {label} must be relative: {value}"
    if any(part in ("", ".", "..") for part in pure.parts):
        return f"{path}: {label} must not contain empty/current/parent path segments: {value}"
    return None


def normalize_layout_path(value: str) -> str:
    return value.rstrip("/")


def validate_named_destination_contains(
    path: Path,
    components: list[dict[str, Any]],
    name: str,
    expected_fragment: str,
) -> list[str]:
    matches = [component for component in components if str(component.get("name", "")) == name]
    if not matches:
        return []
    destination = normalize_layout_path(str(matches[0].get("destination", "")))
    if expected_fragment not in destination:
        return [f"{path}: {name} destination must contain {expected_fragment}: {destination}"]
    return []


def validate_no_forbidden_payload_marker(path: Path, label: str, value: str) -> list[str]:
    lowered = value.lower()
    return [
        f"{path}: {label} contains forbidden payload marker {marker}"
        for marker in sorted(FORBIDDEN_PAYLOAD_MARKERS)
        if marker.lower() in lowered
    ]


def validate_no_gui_toolkit_leak(path: Path, components: list[dict[str, Any]]) -> list[str]:
    problems: list[str] = []
    for component in components:
        name = str(component.get("name", ""))
        for key in ["name", "source_target", "destination", "runtime_search_path"]:
            value = str(component.get(key, ""))
            lowered = value.lower()
            for marker in sorted(GUI_TOOLKIT_MARKERS):
                if marker.lower() in lowered:
                    problems.append(f"{path}: CLI/TUI-only bundle leaks GUI marker in {name}.{key}: {value}")
    return problems


if __name__ == "__main__":
    raise SystemExit(main())
