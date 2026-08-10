# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import architecture_fitness


def _component(records: list[object], component_id: str) -> dict[str, object]:
    return next(
        (
            item
            for item in records
            if isinstance(item, dict) and item.get("id") == component_id
        ),
        {},
    )


def validate_records(
    *,
    version: dict[str, object],
    compatibility: dict[str, object],
    build: dict[str, object],
    product: dict[str, object],
    channels: dict[str, object],
    artifacts: dict[str, object],
    update: dict[str, object],
    dependency: dict[str, object],
    sbom: dict[str, object],
    status: dict[str, object],
    train: dict[str, object],
) -> set[str]:
    violations: set[str] = set()
    for key in [
        "canonical_version",
        "filename_version",
        "channel",
        "build_kind",
        "package_revision",
    ]:
        if build.get(key) != version.get(key):
            violations.add(f"release/index/build_manifest.v1.toml:mismatch:{key}")
        if compatibility.get(key) != version.get(key):
            violations.add(f"release/index/version.v1.toml:mismatch:{key}")
    for key in ["product", "semver", "component_version"]:
        if compatibility.get(key) != version.get(key):
            violations.add(f"release/index/version.v1.toml:mismatch:{key}")

    channel_id = version.get("channel")
    channel_records = channels.get("channel", [])
    selected = [
        item
        for item in channel_records
        if isinstance(item, dict) and item.get("id") == channel_id
    ]
    if len(selected) != 1:
        violations.add("release/index/channels.v1.toml:current-channel-cardinality")
    elif version.get("canonical_version") not in selected[0].get("versions", []):
        violations.add("release/index/channels.v1.toml:missing-current-version")
    occurrences = sum(
        item.get("versions", []).count(version.get("canonical_version"))
        for item in channel_records
        if isinstance(item, dict) and isinstance(item.get("versions"), list)
    )
    if occurrences != 1:
        violations.add("release/index/channels.v1.toml:version-membership-cardinality")
    if product.get("default_channel") != channel_id:
        violations.add("release/index/product.v2.toml:mismatch:default_channel")

    for key, expected in (
        ("current_version", version.get("canonical_version")),
        ("available_version", version.get("canonical_version")),
        ("channel", channel_id),
    ):
        if update.get(key) != expected:
            violations.add(f"release/index/update_report.v1.toml:mismatch:{key}")
    if status.get("product_version") != version.get("semver"):
        violations.add("release/index/project_status.v2.toml:mismatch:product_version")
    if train.get("development_base_version") != version.get("semver"):
        violations.add("release/index/version_train.v1.toml:mismatch:development_base_version")
    if train.get("tracked_contract_identity") != version.get("canonical_version"):
        violations.add("release/index/version_train.v1.toml:mismatch:tracked_contract_identity")

    prefix = f"{version.get('filename_version')}-"
    for artifact in artifacts.get("artifact", []):
        if isinstance(artifact, dict) and not str(artifact.get("filename", "")).startswith(prefix):
            violations.add(
                "release/index/artifacts.v2.toml:mismatch:filename:"
                + str(artifact.get("id", "<unknown>"))
            )
    dependency_component = _component(dependency.get("component", []), "factorio_binding")
    sbom_component = _component(sbom.get("components", []), "factorio_binding")
    for path, record in (
        ("release/index/dependency_lock.v1.toml", dependency_component),
        ("release/index/sbom.components.v1.json", sbom_component),
    ):
        if record.get("version") != version.get("component_version"):
            violations.add(f"{path}:mismatch:factorio_binding.version")
    return violations


def detect() -> set[str]:
    violations: set[str] = set()
    canonical = architecture_fitness.ROOT / "release/index/version.v2.toml"
    if not canonical.is_file():
        violations.add(f"missing:{architecture_fitness.relative(canonical)}")
    else:
        with canonical.open("rb") as handle:
            version = tomllib.load(handle)
        index = architecture_fitness.ROOT / "release/index"

        def load_toml(name: str) -> dict[str, object]:
            with (index / name).open("rb") as handle:
                return tomllib.load(handle)

        sbom = json.loads((index / "sbom.components.v1.json").read_text(encoding="utf-8"))
        violations.update(
            validate_records(
                version=version,
                compatibility=load_toml("version.v1.toml"),
                build=load_toml("build_manifest.v1.toml"),
                product=load_toml("product.v2.toml"),
                channels=load_toml("channels.v1.toml"),
                artifacts=load_toml("artifacts.v2.toml"),
                update=load_toml("update_report.v1.toml"),
                dependency=load_toml("dependency_lock.v1.toml"),
                sbom=sbom,
                status=load_toml("project_status.v2.toml"),
                train=load_toml("version_train.v1.toml"),
            )
        )
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
