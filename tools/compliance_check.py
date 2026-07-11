# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import hashlib
import json
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import apply_spdx_headers

LOCK = ROOT / "release" / "index" / "dependency_lock.v1.toml"
SEED = ROOT / "release" / "index" / "sbom.components.v1.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalized_notice(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n").rstrip("\n")


def validate() -> list[str]:
    problems = apply_spdx_headers.missing()
    with LOCK.open("rb") as handle:
        lock = tomllib.load(handle)
    components = {
        str(component["id"]): component
        for component in lock.get("component", [])
        if isinstance(component, dict) and component.get("id")
    }
    seed = json.loads(SEED.read_text(encoding="utf-8"))
    seed_components = {str(component["id"]): component for component in seed["components"]}
    if set(seed_components) != set(components):
        problems.append("SBOM seed and dependency lock component identities differ")
    for component_id, component in components.items():
        if seed_components.get(component_id, {}).get("license") != component.get("license"):
            problems.append(f"SBOM seed license differs from dependency lock: {component_id}")
    for provider in ("universal_launcher", "universal_setup"):
        if components.get(provider, {}).get("license") != "NOASSERTION":
            problems.append(f"provider license must remain NOASSERTION pending operator choice: {provider}")
    miniz = components.get("miniz", {})
    hashes = {
        "miniz_c_sha256": ROOT / "external" / "miniz" / "miniz.c",
        "miniz_h_sha256": ROOT / "external" / "miniz" / "miniz.h",
        "license_file_sha256": ROOT / "external" / "miniz" / "LICENSE",
    }
    for field, path in hashes.items():
        if sha256(path) != miniz.get(field):
            problems.append(f"Miniz {field} does not match the vendored file")
    notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    for anchor in ("Miniz 3.1.2", "external/miniz/LICENSE", "PicoJSON", "external/picojson/LICENSE"):
        if anchor not in notices:
            problems.append(f"third-party notice is missing: {anchor}")
    reuse = (ROOT / "REUSE.toml").read_text(encoding="utf-8")
    for anchor in ("SPDX-PackageName", "external/miniz/**", "external/picojson/**", "NOASSERTION"):
        if anchor == "NOASSERTION":
            continue
        if anchor not in reuse:
            problems.append(f"REUSE metadata is missing: {anchor}")
    for license_file in ("LICENSES/MIT.txt", "LICENSES/BSD-2-Clause.txt"):
        if not (ROOT / license_file).is_file():
            problems.append(f"REUSE license text is missing: {license_file}")
    for packaged_notice, upstream_notice in (
        ("LICENSES/Miniz.txt", "external/miniz/LICENSE"),
        ("LICENSES/PicoJSON.txt", "external/picojson/LICENSE"),
    ):
        if not (ROOT / packaged_notice).is_file():
            problems.append(f"packaged dependency notice is missing: {packaged_notice}")
        elif normalized_notice(ROOT / packaged_notice) != normalized_notice(ROOT / upstream_notice):
            problems.append(f"packaged dependency notice differs from upstream: {packaged_notice}")
    security = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
    for anchor in ("GitHub security advisory", "7 calendar days", "Supported versions"):
        if anchor not in security:
            problems.append(f"vulnerability policy is missing: {anchor}")
    support = (ROOT / "docs" / "release" / "SUPPORT_POLICY.md").read_text(encoding="utf-8")
    for anchor in ("Current default branch", "Historical R2/R3 checkpoints", "no stable supported release"):
        if anchor not in support:
            problems.append(f"supported-version policy is missing: {anchor}")
    decision = ROOT / "docs" / "quality" / "operator-decisions" / "universal-repository-license.md"
    if not decision.is_file() or "pending operator decision" not in decision.read_text(encoding="utf-8"):
        problems.append("Universal repository license operator decision is missing")
    builder = (ROOT / "tools" / "provenance_build.py").read_text(encoding="utf-8")
    for anchor in ("built_component_package", "verify_sbom_component_coverage", '"CONTAINS"'):
        if anchor not in builder:
            problems.append(f"SBOM built-component closure is missing: {anchor}")
    return problems


def main() -> int:
    problems = validate()
    if problems:
        for problem in problems:
            print(f"compliance-check: {problem}", file=sys.stderr)
        return 1
    print(f"compliance-check: ok ({len(apply_spdx_headers.tracked_sources())} SPDX source files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
