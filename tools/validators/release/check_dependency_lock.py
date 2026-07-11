from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.validators.release import _common

TOOL = "release-dependency-lock-check"

REQUIRED_COMPONENTS = {
    "factorio_binding",
    "miniz",
    "universal_launcher",
    "universal_setup",
}

FORBIDDEN_FLOATING_PINS = {
    "",
    "latest",
    "main",
    "master",
    "dev",
    "head",
    "BUILD_TIME",
}

REQUIRED_ABI_KEYS = {"flb", "ulk", "ulu", "usk", "usu"}


def main() -> int:
    try:
        problems = validate()
    except (OSError, ValueError) as exc:
        problems = [str(exc)]
    return _common.report(TOOL, problems)


def validate() -> list[str]:
    problems: list[str] = []
    lock_path = _common.index_path("dependency_lock")
    lock = _common.load_toml(lock_path)
    if lock.get("schema") != "facman.dependency_lock.v1":
        problems.append(f"{relative(lock_path)}: wrong schema")
    if lock.get("global_runtime_required") is not False:
        problems.append(f"{relative(lock_path)}: global_runtime_required must be false")

    components = component_map(lock.get("component"))
    for required in sorted(REQUIRED_COMPONENTS - set(components)):
        problems.append(f"{relative(lock_path)}: missing component {required}")
    for component_id, component in sorted(components.items()):
        problems.extend(validate_component(lock_path, component_id, component))
    setup = components.get("universal_setup", {})
    launcher = components.get("universal_launcher", {})
    if setup.get("install_mutation_authority") is not True:
        problems.append(f"{relative(lock_path)}: universal_setup must own install mutation")
    if launcher.get("install_mutation_authority") is not False:
        problems.append(f"{relative(lock_path)}: universal_launcher must not own install mutation")
    problems.extend(validate_miniz_component(lock_path, components.get("miniz", {})))

    build_path = _common.index_path("build_manifest")
    build = _common.load_toml(build_path)
    abi_versions = _common.table(build.get("abi_versions"))
    for key in sorted(REQUIRED_ABI_KEYS):
        if not isinstance(abi_versions.get(key), int) or abi_versions[key] < 1:
            problems.append(f"{relative(build_path)}: missing ABI version {key}")

    product_path = _common.index_path("product_manifest")
    product = _common.load_toml(product_path)
    if product.get("global_runtime_required") is not False:
        problems.append(f"{relative(product_path)}: global_runtime_required must be false")
    if product.get("package_model") != "self_contained_product_distribution":
        problems.append(f"{relative(product_path)}: package_model must be self-contained")
    return problems


def validate_component(path: Path, component_id: str, component: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    prefix = f"{relative(path)} component {component_id}"
    pin = str(component.get("pin", "")).lower()
    if pin in FORBIDDEN_FLOATING_PINS:
        problems.append(f"{prefix}: pin must not be floating")
    if component.get("bundled") is not True:
        problems.append(f"{prefix}: bundled must be true")
    if not isinstance(component.get("abi_version"), int) or component["abi_version"] < 1:
        problems.append(f"{prefix}: abi_version must be a positive integer")
    version = str(component.get("version", "")).strip()
    if not version:
        problems.append(f"{prefix}: version is required")
    elif version in FORBIDDEN_FLOATING_PINS:
        problems.append(f"{prefix}: version must not be floating")
    return problems


def validate_miniz_component(path: Path, component: dict[str, Any]) -> list[str]:
    prefix = f"{relative(path)} component miniz"
    expected = {
        "kind": "archive_runtime",
        "version": "3.1.2",
        "pin": "77d0dce8627735138c51770d1799a1ef48f2117d",
        "source": "https://github.com/richgel999/miniz",
        "source_archive": "miniz-3.1.2.zip",
        "source_archive_sha256": "f0446d863f9c19926ad9483c523fdc42e42b8d4a6a431d27e09d49c79a140d9a",
        "license": "MIT",
    }
    problems: list[str] = []
    for key, value in expected.items():
        if component.get(key) != value:
            problems.append(f"{prefix}: {key} must equal {value}")
    if component.get("runtime_network") is not False:
        problems.append(f"{prefix}: runtime_network must be false")
    if component.get("transitive_runtime_dependencies") != []:
        problems.append(f"{prefix}: transitive_runtime_dependencies must be empty")
    if component.get("install_mutation_authority") is not False:
        problems.append(f"{prefix}: install_mutation_authority must be false")
    return problems


def component_map(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, list):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for item in value:
        if isinstance(item, dict):
            component_id = str(item.get("id", ""))
            if component_id:
                result[component_id] = item
    return result


def relative(path: Path) -> str:
    return path.relative_to(_common.ROOT).as_posix()


if __name__ == "__main__":
    raise SystemExit(main())
