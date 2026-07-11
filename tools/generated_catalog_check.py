# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import architecture_fitness
from tools.codegen import generate_metadata


def detect() -> set[str]:
    return {f"stale:{problem.split(': ', 1)[-1]}" for problem in generate_metadata.generate(write=False)}


def main() -> int:
    return architecture_fitness.run("generated_catalog", detect)


if __name__ == "__main__":
    raise SystemExit(main())
