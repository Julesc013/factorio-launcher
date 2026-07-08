from __future__ import annotations

import subprocess
from pathlib import Path


def run_launch_plan(plan: dict[str, object]) -> int:
    executable = str(plan["executable"])
    if executable.endswith(".stub"):
        raise RuntimeError("refusing to execute fixture stub")
    command = [executable, *[str(arg) for arg in plan["args"]]]
    completed = subprocess.run(command, cwd=Path(str(plan["app_dir"])), check=False)
    return int(completed.returncode)

