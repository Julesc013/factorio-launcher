from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from factorio_launcher.core.config import product_dir


def product_manifest_path() -> Path:
    return product_dir() / "product" / "factorio.product.toml"


def load_product_manifest() -> dict[str, Any]:
    path = product_manifest_path()
    with path.open("rb") as handle:
        manifest = tomllib.load(handle)
    return manifest
