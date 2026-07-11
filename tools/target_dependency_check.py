# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import architecture_fitness

ALLOWED_CLI_LINKS = {"facman_client_static"}


def detect() -> set[str]:
    return {
        f"facman_cli:link:{dependency}"
        for dependency in architecture_fitness.cmake_target_links("facman_cli")
        if dependency not in ALLOWED_CLI_LINKS
    }


def main() -> int:
    return architecture_fitness.run("target_dependency", detect)


if __name__ == "__main__":
    raise SystemExit(main())
