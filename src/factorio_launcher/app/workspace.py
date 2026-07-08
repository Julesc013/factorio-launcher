from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

WORKSPACE_VERSION = 1

WORKSPACE_DIRS = [
    "installs/installed_state",
    "instances",
    "modsets",
    "saves",
    "profiles",
    "accounts",
    "cache/downloads",
    "cache/mods",
    "cache/mod_portal",
    "cache/versions",
    "cache/checksums",
    "audit",
    "diagnostics/reports",
]


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_workspace(workspace: Path) -> Path:
    workspace = workspace.expanduser().resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    for rel in WORKSPACE_DIRS:
        (workspace / rel).mkdir(parents=True, exist_ok=True)
    manifest = workspace / "workspace.manifest.json"
    if not manifest.exists():
        write_json(
            manifest,
            {
                "workspace_version": WORKSPACE_VERSION,
                "created_at": utc_now(),
                "product_id": "factorio",
                "portable": False,
            },
        )
    return workspace


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
        handle.write("\n")


def install_ref_path(workspace: Path, install_id: str) -> Path:
    return ensure_workspace(workspace) / "installs" / "installed_state" / f"{install_id}.json"


def instance_root(workspace: Path, instance_id: str) -> Path:
    return ensure_workspace(workspace) / "instances" / instance_id


def instance_manifest_path(workspace: Path, instance_id: str) -> Path:
    return instance_root(workspace, instance_id) / "instance.manifest.json"


def list_json_records(directory: Path) -> list[dict[str, Any]]:
    if not directory.exists():
        return []
    records: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.json")):
        records.append(read_json(path))
    return records


def list_install_refs(workspace: Path) -> list[dict[str, Any]]:
    root = ensure_workspace(workspace) / "installs" / "installed_state"
    return list_json_records(root)


def load_install_ref(workspace: Path, install_id: str) -> dict[str, Any]:
    path = install_ref_path(workspace, install_id)
    if not path.exists():
        raise FileNotFoundError(f"install ref not found: {install_id}")
    return read_json(path)


def save_install_ref(workspace: Path, install_ref: dict[str, Any]) -> Path:
    return write_record(install_ref_path(workspace, install_ref["install_id"]), install_ref)


def list_instances(workspace: Path) -> list[dict[str, Any]]:
    root = ensure_workspace(workspace) / "instances"
    records: list[dict[str, Any]] = []
    for path in sorted(root.glob("*/instance.manifest.json")):
        records.append(read_json(path))
    return records


def load_instance(workspace: Path, instance_id: str) -> dict[str, Any]:
    path = instance_manifest_path(workspace, instance_id)
    if not path.exists():
        raise FileNotFoundError(f"instance not found: {instance_id}")
    return read_json(path)


def save_instance(workspace: Path, instance: dict[str, Any]) -> Path:
    return write_record(instance_manifest_path(workspace, instance["instance_id"]), instance)


def write_record(path: Path, record: dict[str, Any]) -> Path:
    write_json(path, record)
    return path

