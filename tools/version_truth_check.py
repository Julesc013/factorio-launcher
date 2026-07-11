from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import architecture_fitness


def detect() -> set[str]:
    violations: set[str] = set()
    canonical = architecture_fitness.ROOT / "release/index/version.v1.toml"
    if not canonical.is_file():
        violations.add(f"missing:{architecture_fitness.relative(canonical)}")
    for path in architecture_fitness.first_party_sources("apps", "runtime", "include"):
        text = path.read_text(encoding="utf-8", errors="replace")
        if '"0.1.0"' in text:
            violations.add(f"{architecture_fitness.relative(path)}:hardcoded:0.1.0")
    return violations


def main() -> int:
    return architecture_fitness.run("version_truth", detect)


if __name__ == "__main__":
    raise SystemExit(main())
