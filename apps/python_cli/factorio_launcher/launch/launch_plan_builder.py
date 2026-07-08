from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from factorio_launcher.core.config import product_dir
from factorio_launcher.core.workspace import load_install_ref, load_instance
from factorio_launcher.launch.command_builder import render_args


def load_launch_template(profile_id: str) -> dict[str, Any]:
    template_name = profile_id.replace("-", "_")
    path = product_dir() / "launch_templates" / f"{template_name}.toml"
    if not path.exists():
        raise FileNotFoundError(f"launch template not found: {profile_id}")
    with path.open("rb") as handle:
        return tomllib.load(handle)


def build_launch_plan(
    workspace: Path,
    instance_id: str,
    profile_id: str | None = None,
    extra_values: dict[str, str] | None = None,
) -> dict[str, Any]:
    instance = load_instance(workspace, instance_id)
    install_ref = load_install_ref(workspace, str(instance["install_ref"]))
    profile = profile_id or str(instance.get("profile") or "gui")
    template = load_launch_template(profile)
    root = Path(str(instance["local_data_root"]))
    values = {
        "config": str(root / "config" / "config.ini"),
        "mod_directory": str(root / "mods"),
        "save": str(root / "saves"),
        "output": str(root / "exports" / "map-preview.png"),
        "benchmark_ticks": "10000",
        "mod_name": "",
        "host": "",
    }
    if extra_values:
        values.update(extra_values)

    args = render_args(list(template.get("args", [])), values)
    return {
        "instance_id": instance_id,
        "profile_id": profile,
        "mode": template.get("mode", profile),
        "executable": install_ref["executable"],
        "app_dir": install_ref["app_dir"],
        "args": args,
        "preflight": [
            "verify_install_ref",
            "verify_instance_paths",
            "verify_mod_directory_is_unique",
            "acquire_instance_lock",
        ],
        "postrun": ["collect_log", "index_results"],
        "dry_run_default": True,
        "ownership": install_ref["ownership"],
        "notes": [
            "run defaults to dry-run; pass --execute to launch the executable",
            "foreign/imported installs are never repaired or uninstalled by this command",
        ],
    }
