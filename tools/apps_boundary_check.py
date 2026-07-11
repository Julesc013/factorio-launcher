from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import architecture_fitness

FORBIDDEN_INCLUDE_PREFIXES = (
    "fl_archive",
    "fl_path_",
    "fl_runtime_",
    "fl_transaction",
    "flb_factorio_",
    "usk/",
)


def detect() -> set[str]:
    violations: set[str] = set()
    for path in architecture_fitness.first_party_sources("apps/cli"):
        rel = architecture_fitness.relative(path)
        for include in architecture_fitness.include_names(path):
            if include.startswith(FORBIDDEN_INCLUDE_PREFIXES):
                violations.add(f"{rel}:include:{include}")
        text = path.read_text(encoding="utf-8", errors="replace")
        if "std::filesystem" in text:
            violations.add(f"{rel}:filesystem")
        if "std::ofstream" in text or "std::fstream" in text:
            violations.add(f"{rel}:persistence")
        if "CreateProcess" in text or "fork(" in text or "execv" in text:
            violations.add(f"{rel}:process")
    return violations


def main() -> int:
    return architecture_fitness.run("apps_boundary", detect)


if __name__ == "__main__":
    raise SystemExit(main())
