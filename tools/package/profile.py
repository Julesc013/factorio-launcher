from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any


def load(root: Path, profile_id: str) -> tuple[Path, dict[str, Any]]:
    path = root / "release" / "profiles" / profile_id / "profile.toml"
    if not path.is_file():
        raise ValueError(f"unknown release profile: {profile_id}")
    with path.open("rb") as handle:
        profile = tomllib.load(handle)
    if profile.get("id") != profile_id:
        raise ValueError(f"{path}: profile id mismatch")
    return path, profile


def proof(profile: dict[str, Any]) -> dict[str, Any]:
    value = profile.get("proof", {})
    if not isinstance(value, dict):
        raise ValueError(f"{profile.get('id', '<profile>')}: proof must be a table")
    return value
