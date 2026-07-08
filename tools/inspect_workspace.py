from __future__ import annotations

import json
import os
from pathlib import Path


def default_workspace() -> Path:
    explicit = os.environ.get("FACMAN_WORKSPACE") or os.environ.get("FACTORIO_LAUNCHER_WORKSPACE")
    if explicit:
        return Path(explicit)
    return Path.home() / ".facman" / "workspace"


def count_json_files(path: Path) -> int:
    if not path.is_dir():
        return 0
    return sum(1 for child in path.iterdir() if child.is_file() and child.suffix == ".json")


def count_instances(workspace: Path) -> int:
    instances = workspace / "instances"
    if not instances.is_dir():
        return 0
    return sum(1 for child in instances.iterdir() if (child / "instance.manifest.json").is_file())


def main() -> int:
    workspace = default_workspace()
    report = {
        "workspace": str(workspace),
        "registered_installs": count_json_files(workspace / "installs" / "installed_state"),
        "instances": count_instances(workspace),
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
