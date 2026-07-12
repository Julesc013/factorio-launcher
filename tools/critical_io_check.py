# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import architecture_fitness


def detect() -> set[str]:
    violations: set[str] = set()
    for path in architecture_fitness.first_party_sources("runtime"):
        relative = architecture_fitness.relative(path)
        if relative.startswith(("runtime/base/", "runtime/platform/", "runtime/archive/")):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if (
            "std::ofstream" in text
            or re.search(r"std::fstream\s+[^;]+std::ios::(?:out|app|trunc)", text)
            or re.search(r"\bfopen\s*\([^,]+,\s*\"[^\"]*[wa+]", text)
        ):
            violations.add(relative)
    return violations


def main() -> int:
    return architecture_fitness.run("critical_io", detect)


if __name__ == "__main__":
    raise SystemExit(main())
