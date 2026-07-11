# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.validators.release import _common

TOOL = "release-install-mode-check"


def main() -> int:
    try:
        problems = validate()
    except (OSError, ValueError) as exc:
        problems = [str(exc)]
    return _common.report(TOOL, problems)


def validate() -> list[str]:
    problems: list[str] = []
    modes_path = _common.index_path("install_modes")
    modes = _common.load_toml(modes_path)
    if modes.get("schema") != "facman.install_modes.v1":
        problems.append(f"{relative(modes_path)}: wrong schema")

    for mode in sorted(_common.REQUIRED_INSTALL_MODES):
        if mode not in modes or not isinstance(modes[mode], dict):
            problems.append(f"{relative(modes_path)}: missing mode table {mode}")

    portable = _common.table(modes.get("portable"))
    user = _common.table(modes.get("user"))
    system = _common.table(modes.get("system"))
    if portable.get("admin_required") is not False:
        problems.append(f"{relative(modes_path)}: portable admin_required must be false")
    if user.get("admin_required") is not False:
        problems.append(f"{relative(modes_path)}: user admin_required must be false")
    if system.get("admin_required") is not True:
        problems.append(f"{relative(modes_path)}: system admin_required must be true")
    for mode_name, table in [("portable", portable), ("user", user), ("system", system)]:
        if table.get("uninstall_preserves_workspace") is not True:
            problems.append(f"{relative(modes_path)}: {mode_name} must preserve workspace on uninstall")
    if user.get("workspace_under_install_dir_allowed") is not False:
        problems.append(f"{relative(modes_path)}: user workspace must not live under install dir")
    if system.get("workspace_under_install_dir_allowed") is not False:
        problems.append(f"{relative(modes_path)}: system workspace must not live under install dir")
    if system.get("setup_owned_files_only") is not True:
        problems.append(f"{relative(modes_path)}: system uninstall must be setup-owned files only")

    for path, profile in _common.load_profiles():
        install_modes = set(_common.string_list(profile.get("install_modes")))
        if install_modes != _common.REQUIRED_INSTALL_MODES:
            problems.append(f"{relative(path)}: install_modes must include portable, user, system")

    product_path = _common.index_path("product_manifest")
    product = _common.load_toml(product_path)
    workspace_policy = _common.table(product.get("workspace_policy"))
    if workspace_policy.get("uninstall_preserves_workspace_by_default") is not True:
        problems.append(f"{relative(product_path)}: uninstall must preserve workspace by default")
    if workspace_policy.get("install_directory_is_workspace") is not False:
        problems.append(f"{relative(product_path)}: install directory must not be the workspace")
    return problems


def relative(path: Path) -> str:
    return path.relative_to(_common.ROOT).as_posix()


if __name__ == "__main__":
    raise SystemExit(main())
