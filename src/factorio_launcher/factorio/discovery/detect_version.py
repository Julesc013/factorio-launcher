from __future__ import annotations

import json
from pathlib import Path


def detect_version(app_dir: Path) -> str | None:
    candidates = [
        app_dir / "data" / "base" / "info.json",
        app_dir / "Contents" / "data" / "base" / "info.json",
    ]
    for candidate in candidates:
        if candidate.is_file():
            try:
                with candidate.open("r", encoding="utf-8") as handle:
                    data = json.load(handle)
            except (OSError, json.JSONDecodeError):
                return None
            version = data.get("version")
            return version if isinstance(version, str) else None
    return None

