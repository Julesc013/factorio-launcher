from __future__ import annotations

import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def validate() -> list[str]:
    problems: list[str] = []
    builder = (ROOT / "tools/provenance_build.py").read_text(encoding="utf-8")
    package_builder = (ROOT / "tools/package/pipeline.py").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    with (ROOT / "release/index/dependency_lock.v1.toml").open("rb") as handle:
        lock = tomllib.load(handle)
    components = {
        component["id"]: component
        for component in lock.get("component", [])
        if isinstance(component, dict) and component.get("id")
    }
    for component_id in ("factorio_binding", "universal_launcher", "universal_setup", "miniz", "picojson"):
        if components.get(component_id, {}).get("license") not in {"MIT", "BSD-2-Clause", "NOASSERTION"}:
            problems.append(f"dependency license truth is missing: {component_id}")
    for schema in (
        "contracts/schema/release/spdx_document.v2.3.schema.json",
        "contracts/schema/release/build_provenance.v1.schema.json",
    ):
        if not (ROOT / schema).is_file():
            problems.append(f"provenance schema is missing: {schema}")
    for anchor in (
        "SPDX-2.3",
        "source_commit_utc",
        "provenance_recorded",
        "publisher_authenticity_not_proven",
        "verify_artifact_provenance",
        "GITHUB_RUN_ID",
        "GITHUB_SHA",
    ):
        if anchor not in builder:
            problems.append(f"provenance builder anchor missing: {anchor}")
    for anchor in ("write_package_sbom(", "write_artifact_provenance("):
        if anchor not in package_builder:
            problems.append(f"package build does not emit provenance: {anchor}")
    if "*.provenance.v1.json" not in workflow:
        problems.append("Linux CI does not preserve external provenance")
    return problems


def main() -> int:
    problems = validate()
    if problems:
        for problem in problems:
            print(f"provenance-check: {problem}", file=sys.stderr)
        return 1
    print("provenance-check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
