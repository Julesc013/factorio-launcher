from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from factorio_launcher.app.config import product_dir
from factorio_launcher.app.workspace import (
    instance_root,
    load_install_ref,
    save_instance,
    utc_now,
)
from factorio_launcher.factorio.discovery.detect_install import slugify

INSTANCE_DIRS = [
    "config",
    "mods",
    "saves",
    "scenarios",
    "script-output",
    "logs",
    "crash",
    "exports",
    "cache",
    "locks",
]


def load_instance_template(template_id: str) -> dict[str, Any]:
    path = product_dir() / "instance-templates" / f"{template_id}.toml"
    if not path.exists():
        raise FileNotFoundError(f"instance template not found: {template_id}")
    with path.open("rb") as handle:
        return tomllib.load(handle)


def create_instance(
    workspace: Path,
    name: str,
    install_id: str,
    template_id: str = "vanilla",
    instance_id: str | None = None,
) -> dict[str, Any]:
    install_ref = load_install_ref(workspace, install_id)
    template = load_instance_template(template_id)
    actual_id = slugify(instance_id or name)
    root = instance_root(workspace, actual_id)
    if (root / "instance.manifest.json").exists():
        raise FileExistsError(f"instance already exists: {actual_id}")

    for rel in INSTANCE_DIRS:
        (root / rel).mkdir(parents=True, exist_ok=True)

    config_ini = root / "config" / "config.ini"
    config_path = root / "config" / "config-path.cfg"
    if not config_ini.exists():
        config_ini.write_text("[path]\n", encoding="utf-8", newline="\n")
    if not config_path.exists():
        config_path.write_text(
            f"read-data={install_ref['app_dir']}\nwrite-data={root}\n",
            encoding="utf-8",
            newline="\n",
        )

    instance = {
        "instance_id": actual_id,
        "display_name": name,
        "install_ref": install_id,
        "factorio_version": install_ref.get("version"),
        "local_data_root": str(root),
        "profile": template.get("profile", "gui"),
        "modset": None,
        "template": template_id,
        "created_at": utc_now(),
        "save_policy": {
            "backup_before_launch": bool(template.get("backup_before_launch", True)),
            "shared_writable": False,
        },
        "account_ref": None,
        "concurrency": {
            "allow_parallel": True,
            "requires_unique_mod_dir": True,
            "requires_unique_save_lock": True,
        },
        "export_policy": {
            "include_saves": "ask",
            "include_mods": True,
            "redact_tokens": True,
        },
    }
    save_instance(workspace, instance)
    return instance

