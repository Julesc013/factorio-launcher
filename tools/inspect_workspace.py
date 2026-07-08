from __future__ import annotations

from pathlib import Path

from factorio_launcher.app.config import default_workspace
from factorio_launcher.app.workspace import list_install_refs, list_instances


def main() -> int:
    workspace = default_workspace()
    print(f"Workspace: {workspace}")
    print(f"Registered installs: {len(list_install_refs(workspace))}")
    print(f"Instances: {len(list_instances(workspace))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

