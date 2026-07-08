from __future__ import annotations

import os
from pathlib import Path

from factorio_launcher import __version__

APP_NAME = "factorio-launcher"
APP_VERSION = __version__
PRODUCT_ID = "factorio"


def repo_root() -> Path:
    candidates = [
        Path.cwd(),
        Path(__file__).resolve().parents[3],
    ]
    for candidate in candidates:
        if (candidate / "factorio" / "product" / "factorio.product.toml").is_file():
            return candidate
    return Path.cwd()


def product_dir() -> Path:
    return repo_root() / "factorio" / "product"


def schema_dir() -> Path:
    return repo_root() / "schemas"


def factorio_schema_dir() -> Path:
    return repo_root() / "factorio" / "schemas"


def default_workspace() -> Path:
    env_value = os.environ.get("FACTORIO_LAUNCHER_WORKSPACE")
    if env_value:
        return Path(env_value).expanduser()
    return Path.home() / ".factorio-launcher" / "workspace"
