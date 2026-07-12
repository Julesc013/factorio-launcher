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

MARKERS = (
    "json_escape(",
    "json_string_value(",
    'find("\\\"" + key',
    "parse_json_",
)
JSON_KEY_LITERAL = re.compile(r'\\\"[A-Za-z0-9_.-]+\\\"\s*:')
REPEATED_ESCAPE_HELPER = re.compile(r"(?:json|escape)[A-Za-z0-9_]*\s*\([^)]*\)[\s\S]{0,2000}\\\\")


def detect() -> set[str]:
    violations: set[str] = set()
    for path in architecture_fitness.first_party_sources("runtime", "apps"):
        relative = architecture_fitness.relative(path)
        if (
            "/core/json/" in f"/{relative}/"
            or "/generated/" in f"/{relative}/"
            or path.name.startswith("Generated")
            or path.name.startswith("FacManGenerated")
            or path.name.startswith("generated_")
        ):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if (
            any(marker in text for marker in MARKERS)
            or JSON_KEY_LITERAL.search(text)
            or REPEATED_ESCAPE_HELPER.search(text)
        ):
            violations.add(architecture_fitness.relative(path))
    return violations


def main() -> int:
    return architecture_fitness.run("manual_json", detect)


if __name__ == "__main__":
    raise SystemExit(main())
