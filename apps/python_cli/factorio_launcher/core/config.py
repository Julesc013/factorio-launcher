from __future__ import annotations

import os
from pathlib import Path

from factorio_launcher import __version__

APP_NAME = "facman"
APP_VERSION = __version__
PRODUCT_ID = "factorio"


def repo_root() -> Path:
    source_path = Path(__file__).resolve()
    candidates = [Path.cwd()]
    candidates.extend(source_path.parents)
    for candidate in candidates:
        if (candidate / "content" / "factorio" / "product" / "factorio.product.toml").is_file():
            return candidate
    return Path.cwd()


def product_dir() -> Path:
    return repo_root() / "content" / "factorio"


def schema_dir() -> Path:
    return repo_root() / "contracts" / "schema"


def factorio_schema_dir() -> Path:
    return schema_dir() / "factorio"


def default_workspace() -> Path:
    env_value = os.environ.get("FACMAN_WORKSPACE") or os.environ.get("FACTORIO_LAUNCHER_WORKSPACE")
    if env_value:
        return Path(env_value).expanduser()
    return Path.home() / ".facman" / "workspace"
