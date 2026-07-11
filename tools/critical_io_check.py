# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import architecture_fitness


def detect() -> set[str]:
    violations: set[str] = set()
    for path in architecture_fitness.first_party_sources("runtime/archive", "runtime/transaction", "runtime/factorio"):
        text = path.read_text(encoding="utf-8", errors="replace")
        if "std::ofstream" in text:
            violations.add(architecture_fitness.relative(path))
    return violations


def main() -> int:
    return architecture_fitness.run("critical_io", detect)


if __name__ == "__main__":
    raise SystemExit(main())
