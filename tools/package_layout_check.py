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
    components = expanded.get("components", [])
    if not isinstance(components, list) or not components:
        return [f"{path}: expanded bundle has no components"]

    normalized_destinations: dict[str, str] = {}
    component_names: set[str] = set()
    for component in components:
        name = str(component.get("name", ""))
        destination = str(component.get("destination", ""))
        component_names.add(name)
        destination_problem = validate_relative_layout_path(path, f"component {name} destination", destination)
        if destination_problem:
            problems.append(destination_problem)
            continue
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


if __name__ == "__main__":
    raise SystemExit(main())
