from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import architecture_fitness


def detect() -> set[str]:
    required = [
        architecture_fitness.ROOT / "contracts/generated/command_catalog.v1.json",
        architecture_fitness.ROOT / "include/facman/generated/version.h",
    ]
    return {f"missing:{architecture_fitness.relative(path)}" for path in required if not path.is_file()}


def main() -> int:
    return architecture_fitness.run("generated_catalog", detect)


if __name__ == "__main__":
    raise SystemExit(main())
