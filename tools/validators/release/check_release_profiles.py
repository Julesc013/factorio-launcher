from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.validators.release import _common

TOOL = "release-profile-check"

REQUIRED_CATALOG_IDS = {
    "linux_portable_cli_x64",
    "macos_portable_cli_x64",
    "portable_cli",
    "portable_full",
    "windows_legacy_winforms_x86",
    "windows_legacy_winforms_x64",
    "windows_modern_winui_x64",
    "windows_modern_winui_arm64",
    "macos_legacy_appkit_x64",
    "macos_modern_swiftui_universal2",
    "linux_x11_gtk_x86",
    "linux_x11_gtk_x64",
    "linux_wayland_qt_x64",
    "linux_wayland_qt_arm64",
    "source",
    "offline_bundle",
}

REQUIRED_PROFILE_FIELDS = {
    "id",
    "status",
    "target_os",
    "target_arch",
    "frontend_stack",
    "minimum_os",
    "toolchain",
    "package_formats",
    "included_binaries",
    "included_libraries",
    "install_modes",
    "update_support",
    "test_requirements",
    "unsupported_features",
    "contract_backed",
}


def main() -> int:
    try:
        problems = validate()
    except (OSError, ValueError) as exc:
        problems = [str(exc)]
    return _common.report(TOOL, problems)


def validate() -> list[str]:
    problems: list[str] = []
    catalog_path = _common.PROFILE_CATALOG
    catalog_data = _common.load_toml(catalog_path)
    if catalog_data.get("schema") != "facman.release_profile_catalog.v1":
        problems.append(f"{relative(catalog_path)}: wrong schema")

    profiles = catalog_data.get("profile", [])
    if not isinstance(profiles, list) or not profiles:
        return [f"{relative(catalog_path)}: profile entries are required"]

    catalog = _common.load_profile_catalog()
    missing_catalog = REQUIRED_CATALOG_IDS - set(catalog)
    for profile_id in sorted(missing_catalog):
        problems.append(f"{relative(catalog_path)}: missing catalog profile {profile_id}")

    seen: set[str] = set()
    for profile in profiles:
        if not isinstance(profile, dict):
            problems.append(f"{relative(catalog_path)}: profile entry must be a table")
            continue
        profile_id = str(profile.get("id", ""))
        if profile_id in seen:
            problems.append(f"{relative(catalog_path)}: duplicate profile {profile_id}")
        seen.add(profile_id)
        problems.extend(validate_catalog_profile(catalog_path, profile))

    indexed_ids = {str(profile.get("id", "")) for _, profile in _common.load_profiles()}
    contract_backed_ids = {
        profile_id for profile_id, profile in catalog.items() if profile.get("contract_backed") is True
    }
    for profile_id in sorted(indexed_ids - contract_backed_ids):
        problems.append(f"release/index/release_index.v1.toml: indexed profile not contract-backed: {profile_id}")
    for profile_id in sorted(contract_backed_ids - indexed_ids):
        problems.append(f"{relative(catalog_path)}: contract-backed profile not indexed: {profile_id}")
    return problems


def validate_catalog_profile(path: Path, profile: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    profile_id = str(profile.get("id", "<missing>"))
    missing = REQUIRED_PROFILE_FIELDS - set(profile)
    if missing:
        problems.append(f"{relative(path)} profile {profile_id}: missing {sorted(missing)}")
        return problems
    install_modes = set(_common.string_list(profile.get("install_modes")))
    if install_modes != _common.REQUIRED_INSTALL_MODES:
        problems.append(f"{relative(path)} profile {profile_id}: install modes must be portable, user, system")
    if not isinstance(profile.get("contract_backed"), bool):
        problems.append(f"{relative(path)} profile {profile_id}: contract_backed must be boolean")
    if not _common.string_list(profile.get("package_formats")):
        problems.append(f"{relative(path)} profile {profile_id}: package_formats must be non-empty")
    if not _common.string_list(profile.get("test_requirements")):
        problems.append(f"{relative(path)} profile {profile_id}: test_requirements must be non-empty")
    return problems


def relative(path: Path) -> str:
    return path.relative_to(_common.ROOT).as_posix()


if __name__ == "__main__":
    raise SystemExit(main())
