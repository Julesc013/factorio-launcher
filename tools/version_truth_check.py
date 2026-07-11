from __future__ import annotations

import sys
import tomllib
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
    else:
        with canonical.open("rb") as handle:
            version = tomllib.load(handle)
        with (architecture_fitness.ROOT / "release/index/build_manifest.v1.toml").open("rb") as handle:
            build = tomllib.load(handle)
        for key in ["canonical_version", "filename_version", "channel", "build_kind", "package_revision"]:
            if build.get(key) != version.get(key):
                violations.add(f"release/index/build_manifest.v1.toml:mismatch:{key}")
    for path in architecture_fitness.first_party_sources("apps", "runtime", "include"):
        if "/generated/" in f"/{architecture_fitness.relative(path)}/":
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if '"0.1.0"' in text:
            violations.add(f"{architecture_fitness.relative(path)}:hardcoded:0.1.0")
    return violations


def main() -> int:
    return architecture_fitness.run("version_truth", detect)


if __name__ == "__main__":
    raise SystemExit(main())
