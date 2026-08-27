# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import architecture_fitness


VERSION = "0.1.0-alpha.1"
CANONICAL_VERSION = f"facman-{VERSION}"
TAG = f"v{VERSION}"
CHANNEL = "alpha"
WORK_UNIT = "FACMAN-0.1.0-ALPHA.1-FINAL-INTEGRATION-01"
PHASE = "facman_0_1_0_alpha_1_final_integration"
CONTAINMENT_WORK_UNIT = "FACMAN-4.0.0-MISNUMBERING-CONTAINMENT-01"
EXPECTED_PACKAGES = [
    "facman-0.1.0-alpha.1-windows-cli-x64-portable.zip",
    "facman-0.1.0-alpha.1-windows-tui-x64-portable.zip",
    "FacMan-0.1.0-alpha.1-windows-x64-portable.zip",
]
MISNUMBERED_IDENTITY = re.compile(
    r"(?i)(?<![0-9])4\.0\.0(?![0-9])|facman[_-]4[_-]0[_-]0|4-0-0"
)
HISTORICAL_PATH_PREFIXES = (
    ".aide/history/facman-4-0-final-distribution-misnumbered-internal-candidate/",
    ".aide/queue/active/FACMAN-4.0.0-MISNUMBERING-CONTAINMENT-01/",
    "docs/release/history/facman-4.0.0-misnumbered-internal-candidate.md",
    "release/evidence/factorio-version-capability-corpus-4.0.0.v1.json",
    "release/evidence/factorio-version-family-matrix-4.0.0.v1.json",
    "release/index/misnumbering_containment.v1.toml",
    "tests/test_release_identity_coherence.py",
    "tools/release_identity_coherence_check.py",
)


def _toml(relative: str) -> dict[str, Any]:
    with (ROOT / relative).open("rb") as handle:
        return tomllib.load(handle)


def _json(relative: str) -> dict[str, Any]:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def load_records() -> dict[str, Any]:
    return {
        "version": _toml("release/index/version.v2.toml"),
        "compatibility": _toml("release/index/version.v1.toml"),
        "build": _toml("release/index/build_manifest.v1.toml"),
        "channels": _toml("release/index/channels.v1.toml"),
        "product": _toml("release/index/product.v2.toml"),
        "artifacts": _toml("release/index/artifacts.v2.toml"),
        "dependency": _toml("release/index/dependency_lock.v1.toml"),
        "sbom": _json("release/index/sbom.components.v1.json"),
        "train": _toml("release/index/version_train.v1.toml"),
        "distribution": _toml("release/index/final_distribution.v1.toml"),
        "status": _toml("release/index/project_status.v2.toml"),
        "current": _toml("release/index/current_state.v1.toml"),
        "plan": _toml("release/index/plan.v1.toml"),
        "factorio": _toml("release/index/factorio_version_families.v1.toml"),
        "alpha_source": _toml("release/index/alpha_release_source.v1.toml"),
        "ledger": _json("release/ledger/0.1.0-alpha.1/prospective-entry.v1.json"),
        "containment": _toml("release/index/misnumbering_containment.v1.toml"),
    }


def _component(records: list[Any], component_id: str) -> dict[str, Any]:
    return next(
        (
            item
            for item in records
            if isinstance(item, dict) and item.get("id") == component_id
        ),
        {},
    )


def _record(records: list[Any], record_id: str) -> dict[str, Any]:
    return next(
        (
            item
            for item in records
            if isinstance(item, dict) and item.get("id") == record_id
        ),
        {},
    )


def _expect(
    violations: set[str], path: str, actual: Any, expected: Any
) -> None:
    if actual != expected:
        violations.add(f"{path}: expected {expected!r}, got {actual!r}")


def validate_records(records: dict[str, Any]) -> set[str]:
    violations: set[str] = set()
    version = records["version"]
    for field, expected in (
        ("semver", VERSION),
        ("canonical_version", CANONICAL_VERSION),
        ("filename_version", CANONICAL_VERSION),
        ("component_version", VERSION),
        ("channel", CHANNEL),
        ("build_kind", "release"),
    ):
        _expect(violations, f"version.{field}", version.get(field), expected)

    compatibility = records["compatibility"]
    build = records["build"]
    for source_name, source in (("compatibility", compatibility), ("build", build)):
        for field, expected in (
            ("canonical_version", CANONICAL_VERSION),
            ("filename_version", CANONICAL_VERSION),
            ("channel", CHANNEL),
            ("build_kind", "release"),
        ):
            _expect(violations, f"{source_name}.{field}", source.get(field), expected)
    _expect(violations, "compatibility.semver", compatibility.get("semver"), VERSION)
    for component_id in ("facman", "factorio_binding"):
        component = _component(build.get("component", []), component_id)
        _expect(
            violations,
            f"build.component.{component_id}.version",
            component.get("version"),
            VERSION,
        )

    channels = records["channels"].get("channel", [])
    alpha = _record(channels, CHANNEL)
    stable = _record(channels, "stable")
    _expect(violations, "channels.alpha.versions", alpha.get("versions"), [CANONICAL_VERSION])
    _expect(violations, "channels.stable.versions", stable.get("versions"), [])
    _expect(
        violations,
        "product.default_channel",
        records["product"].get("default_channel"),
        CHANNEL,
    )

    for artifact in records["artifacts"].get("artifact", []):
        if not isinstance(artifact, dict):
            continue
        filename = str(artifact.get("filename", ""))
        if not filename.lower().startswith(f"facman-{VERSION}-"):
            violations.add(
                "artifacts."
                + str(artifact.get("id", "<unknown>"))
                + f".filename: does not carry {VERSION}"
            )

    dependency = _component(records["dependency"].get("component", []), "factorio_binding")
    sbom = _component(records["sbom"].get("components", []), "factorio_binding")
    _expect(violations, "dependency.factorio_binding.version", dependency.get("version"), VERSION)
    _expect(violations, "sbom.factorio_binding.version", sbom.get("version"), VERSION)
    _expect(
        violations,
        "sbom.publisher_authenticity_proven",
        records["sbom"].get("publisher_authenticity_proven"),
        False,
    )

    train = records["train"]
    for field, expected in (
        ("current_product_target", "0.1.0"),
        ("development_base_version", VERSION),
        ("tracked_contract_identity", CANONICAL_VERSION),
        ("allocated_release_class", CHANNEL),
        ("allocated_version", VERSION),
        ("signing_authorized", False),
        ("publication_authorized", False),
    ):
        _expect(violations, f"train.{field}", train.get(field), expected)
    for field, expected in (
        ("version_allocation", True),
        ("tag_creation", True),
        ("signing", False),
        ("publication", False),
        ("stable_promotion", False),
    ):
        _expect(violations, f"train.authority.{field}", train.get("authority", {}).get(field), expected)

    distribution = records["distribution"]
    for field, expected in (
        ("version", VERSION),
        ("canonical_version", CANONICAL_VERSION),
        ("channel", CHANNEL),
        ("classification", "unsigned_unpublished_alpha_candidate"),
        ("source_work_unit", WORK_UNIT),
        ("support_claim", "unsupported_alpha"),
    ):
        _expect(violations, f"distribution.{field}", distribution.get(field), expected)
    _expect(
        violations,
        "distribution.packages",
        [item.get("filename") for item in distribution.get("artifact", [])],
        EXPECTED_PACKAGES,
    )
    authority = distribution.get("authority", {})
    if not authority or any(value is not False for value in authority.values()):
        violations.add("distribution.authority: every external effect must remain false")

    factorio = records["factorio"]
    _expect(violations, "factorio.product_target", factorio.get("product_target"), VERSION)
    qualification = distribution.get("factorio_qualification", {})
    _expect(
        violations,
        "distribution.factorio_qualification.families",
        qualification.get("families"),
        ["F100", "F110", "F200", "F210"],
    )
    _expect(
        violations,
        "distribution.factorio_qualification.exact_versions",
        qualification.get("exact_versions"),
        ["1.0.0", "1.1.110", "2.0.77", "2.1.14"],
    )
    _expect(
        violations,
        "distribution.factorio_qualification.corpus",
        qualification.get("corpus"),
        "release/evidence/factorio-version-capability-corpus-0.1.0-alpha.1.v1.json",
    )
    _expect(
        violations,
        "distribution.factorio_qualification.matrix",
        qualification.get("matrix"),
        "release/evidence/factorio-version-family-matrix-0.1.0-alpha.1.v1.json",
    )

    status = records["status"]
    current = records["current"]
    _expect(violations, "status.product_version", status.get("product_version"), VERSION)
    _expect(violations, "status.active_work_unit", status.get("active_work_unit"), WORK_UNIT)
    _expect(violations, "status.safe_beta", status.get("safe_beta"), False)
    _expect(violations, "current.product_version", current.get("product_version"), VERSION)
    _expect(violations, "current.phase", current.get("phase"), PHASE)
    _expect(violations, "current.active_work_unit", current.get("active_work_unit"), WORK_UNIT)
    _expect(violations, "current.product.release", current.get("product", {}).get("release"), "unpublished")
    _expect(violations, "current.product.safe_beta", current.get("product", {}).get("safe_beta"), False)

    plan = records["plan"]
    _expect(violations, "plan.active_release", plan.get("active_release"), "FACMAN-0.1.0-ALPHA.1")
    plan_release = _record(plan.get("release", []), "FACMAN-0.1.0-ALPHA.1")
    _expect(violations, "plan.release.version", plan_release.get("version"), VERSION)
    _expect(violations, "plan.release.status", plan_release.get("status"), "active")
    work_unit = _record(plan.get("workunit", []), WORK_UNIT)
    _expect(violations, "plan.workunit.status", work_unit.get("status"), "active")

    alpha_source = records["alpha_source"]
    ledger = records["ledger"]
    for source_name, source in (("alpha_source", alpha_source), ("ledger", ledger)):
        _expect(violations, f"{source_name}.version", source.get("version"), VERSION)
    _expect(violations, "alpha_source.canonical_version", alpha_source.get("canonical_version"), CANONICAL_VERSION)
    _expect(violations, "alpha_source.tag.name", alpha_source.get("tag", {}).get("name"), TAG)
    _expect(violations, "ledger.tag", ledger.get("tag"), TAG)
    for source_name, source in (("alpha_source", alpha_source), ("ledger", ledger)):
        source_authority = source.get("authority", {})
        if not source_authority or any(value is not False for value in source_authority.values()):
            violations.add(f"{source_name}.authority: every external effect must remain false")

    containment = records["containment"]
    _expect(violations, "containment.work_unit", containment.get("work_unit"), CONTAINMENT_WORK_UNIT)
    _expect(violations, "containment.source.head", containment.get("source", {}).get("head"), "4889816b65fe474bef8901c4be187cee4d3667c6")
    _expect(violations, "containment.source.tree", containment.get("source", {}).get("tree"), "4794913da07c964cbf356abb9d7811281b3d8b1b")
    external_state = containment.get("external_state", {})
    if not external_state or any(value is not False for value in external_state.values()):
        violations.add("containment.external_state: every external effect must remain false")
    return violations


def validate_source_bindings() -> set[str]:
    violations: set[str] = set()
    header = (ROOT / "runtime/core/generated/version.h").read_text(encoding="utf-8")
    for macro, expected in (
        ("FACMAN_VERSION_SEMVER", VERSION),
        ("FACMAN_VERSION_CANONICAL", CANONICAL_VERSION),
        ("FACMAN_VERSION_FILENAME", CANONICAL_VERSION),
        ("FACMAN_VERSION_COMPONENT", VERSION),
    ):
        if f'#define {macro} "{expected}"' not in header:
            violations.add(f"runtime/core/generated/version.h:{macro}: missing {expected}")

    cli = (ROOT / "apps/cli/command_dispatch.cpp").read_text(encoding="utf-8")
    tui = (ROOT / "apps/tui/tui_host.cpp").read_text(encoding="utf-8")
    if "FACMAN_VERSION_SEMVER" not in cli or 'command == "--version"' not in cli:
        violations.add("apps/cli/command_dispatch.cpp: --version is not bound to generated identity")
    if "FACMAN_VERSION_SEMVER" not in tui or 'value == "--version"' not in tui:
        violations.add("apps/tui/tui_host.cpp: --version is not bound to generated identity")

    cmake = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
    if re.search(
        r"project\s*\(\s*facman\s+VERSION\s+0\.1\.0\b",
        cmake,
        re.DOTALL | re.IGNORECASE,
    ) is None:
        violations.add("CMakeLists.txt: numeric project version is not 0.1.0")
    return violations


def tracked_and_untracked_files() -> list[Path]:
    completed = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    return [ROOT / line for line in completed.stdout.splitlines() if (ROOT / line).is_file()]


def misnumbered_line_is_allowed(relative: str, line: str) -> bool:
    if relative.startswith(HISTORICAL_PATH_PREFIXES):
        return True
    remainder = line.replace(CONTAINMENT_WORK_UNIT, "").replace("\\", "")
    return MISNUMBERED_IDENTITY.search(remainder) is None


def detect_misnumbered_identity() -> set[str]:
    violations: set[str] = set()
    for path in tracked_and_untracked_files():
        relative = path.relative_to(ROOT).as_posix()
        if relative.startswith((".git/", ".aide.local/", "build/", "dist/", "out/", "tmp/")):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if MISNUMBERED_IDENTITY.search(relative) and not relative.startswith(HISTORICAL_PATH_PREFIXES):
            violations.add(f"{relative}: misnumbered identity in active path")
        for line_number, line in enumerate(text.splitlines(), start=1):
            normalized = line.replace("\\", "")
            if MISNUMBERED_IDENTITY.search(normalized) and not misnumbered_line_is_allowed(relative, line):
                violations.add(f"{relative}:{line_number}: active misnumbered identity")
    return violations


def detect() -> set[str]:
    violations = validate_records(load_records())
    violations.update(validate_source_bindings())
    violations.update(detect_misnumbered_identity())
    return violations


def main() -> int:
    return architecture_fitness.run("release_identity_coherence", detect)


if __name__ == "__main__":
    raise SystemExit(main())
