# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Exercise bounded conformance of exact Universal provider inputs.

This is a non-authorizing build-and-observation harness.  It deliberately uses
an out-of-tree candidate lock rather than changing FacMan's tracked provider
pins.  It never invokes Factorio, a Setup apply operation, permit handling,
signing, publication, or route promotion.

Stable inputs are exact commits reachable from the provider's current canonical
``main``.  They do not have to remain the tip of that branch after a separately
reviewed provider promotion.
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tomllib
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
OBSERVATION_STEM = "provider-conformance-observation.v1"
IDENTITY_SCHEMA = "facman.provider_sdk_identity.v1"
INVENTORY_SCHEMA = "facman.provider_sdk_inventory.v1"
LOCK_SCHEMA = "facman.provider_conformance_lock.v1"

AUTHORITY: dict[str, bool] = {
    "credentials": False,
    "factorio_execution": False,
    "observer_capture": False,
    "permit_issuance": False,
    "product_execution": False,
    "provider_adoption": False,
    "route_promotion": False,
    "setup_mutation": False,
    "signing": False,
    "publication": False,
}
AUTHORITY_KEYS = frozenset(AUTHORITY)
TOOLCHAIN_KEYS = frozenset(
    {
        "cmake",
        "generator",
        "generator_platform",
        "generator_toolset",
        "system",
        "processor",
        "pointer_bits",
        "configuration",
        "c_compiler_id",
        "c_compiler_version",
        "c_compiler_target",
        "cxx_compiler_id",
        "cxx_compiler_version",
        "cxx_compiler_target",
        "sysroot",
        "msvc_runtime_library",
    }
)

STABLE_CTESTS = (
    "facman_abi_layout_smoke",
    "facman_client_smoke",
    "fl_json_core_smoke",
    "flb_command_bridge_smoke",
)

READ_ONLY_CLI_PROBES = (
    ("product_inspect", ("product", "inspect", "--json")),
    ("command_graph_inspect", ("command-graph", "inspect", "--json")),
)

PENDING_SEMANTIC_EQUIVALENCE: dict[str, str] = {
    "operation_outcome_equivalence": "pending_not_fabricated",
    "structured_refusal_equivalence": "pending_not_fabricated",
    "interrupted_recovery_projection_equivalence": "pending_not_fabricated",
    "release_resolution_root_equivalence": "pending_not_fabricated",
}


@dataclass(frozen=True)
class ProviderSpec:
    provider_id: str
    display_name: str
    source_name: str
    repository: str
    remote: str
    canonical_commit: str
    cmake_prefix: str
    package_name: str
    package_version: str
    exported_targets: tuple[str, ...]
    abi_relative_path: str
    installed_data_name: str
    contract_set_id: str
    contract_digest: str


PROVIDERS = (
    ProviderSpec(
        provider_id="universal_launcher",
        display_name="Universal Launcher",
        source_name="universal-launcher",
        repository="Julesc013/universal-launcher",
        remote="https://github.com/Julesc013/universal-launcher.git",
        canonical_commit="09f0639ab6529fba2f2aa22e9bf68e5eebed0553",
        cmake_prefix="ULK",
        package_name="UniversalLauncher",
        package_version="1.8.0",
        exported_targets=(
            "UniversalLauncher::Headers",
            "UniversalLauncher::CoreStatic",
            "UniversalLauncher::CoreShared",
        ),
        abi_relative_path="contracts/abi/ulk_c_abi.v1.toml",
        installed_data_name="universal-launcher",
        contract_set_id="ulk_contract_set_1_9",
        contract_digest="b9e39e83dc1ae85755dce4f5f61d23bc438a0e81882313c04ca00f5eff661e4e",
    ),
    ProviderSpec(
        provider_id="universal_setup",
        display_name="Universal Setup",
        source_name="universal-setup",
        repository="Julesc013/universal-setup",
        remote="https://github.com/Julesc013/universal-setup.git",
        canonical_commit="32488fc13bd2439f9f6e52e83a97f6da345a7650",
        cmake_prefix="USK",
        package_name="UniversalSetup",
        package_version="1.0.0",
        exported_targets=(
            "UniversalSetup::Headers",
            "UniversalSetup::CoreStatic",
            "UniversalSetup::CoreShared",
        ),
        abi_relative_path="contracts/abi/usk_c_abi.v1.toml",
        installed_data_name="universal-setup",
        contract_set_id="usk_product_package_contract_set_1",
        contract_digest="1e2f45c6292909abfee1119a09d464f573a84047f24c22ee57e9224f44464c71",
    ),
)


@dataclass(frozen=True)
class ProviderSource:
    spec: ProviderSpec
    root: Path
    commit: str
    tree: str


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    output: str
    log_relative_path: str


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative_inventory(
    root: Path, excluded_relative_paths: Sequence[str] = ()
) -> list[dict[str, Any]]:
    if not root.is_dir():
        raise ValueError(f"inventory root is not a directory: {root}")
    excluded = set(excluded_relative_paths)
    entries: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        relative = path.relative_to(root).as_posix()
        if relative in excluded:
            continue
        if path.is_symlink():
            target = os.readlink(path)
            if Path(target).is_absolute() or ".." in Path(target).parts:
                raise ValueError(f"SDK contains an escaping link: {relative}")
            payload = target.encode("utf-8")
            entries.append(
                {
                    "path": relative,
                    "bytes": len(payload),
                    "sha256": sha256_bytes(payload),
                }
            )
        elif path.is_file():
            entries.append(
                {
                    "path": relative,
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    return entries


def inventory_identity(
    root: Path, excluded_relative_paths: Sequence[str] = ()
) -> dict[str, Any]:
    entries = _relative_inventory(root, excluded_relative_paths)
    return _inventory_entries_identity(entries)


def _inventory_entries_identity(entries: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "file_count": len(entries),
        "sha256": sha256_bytes(canonical_json_bytes(entries)),
    }


def _public_contract_inventory(root: Path) -> list[dict[str, Any]]:
    entries = _relative_inventory(root)
    public_entries = [
        entry for entry in entries if str(entry.get("path", "")).endswith(".json")
    ]
    if not public_entries:
        raise ValueError(f"public contract bundle contains no JSON schemas: {root}")
    return public_entries


def _looks_absolute(value: str) -> bool:
    if value.startswith("/") or value.startswith("\\\\"):
        return True
    return re.match(r"^[A-Za-z]:[\\/]", value) is not None


def assert_path_independent_json(value: Any, location: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            assert_path_independent_json(child, f"{location}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            assert_path_independent_json(child, f"{location}[{index}]")
    elif isinstance(value, str) and _looks_absolute(value):
        raise ValueError(f"absolute path is forbidden at {location}")


def validate_authority(value: Any) -> None:
    if not isinstance(value, Mapping):
        raise ValueError("authority must be an exact table")
    if set(value) != AUTHORITY_KEYS:
        raise ValueError("authority key set is not exact")
    if any(item is not False for item in value.values()):
        raise ValueError("every authority value must be Boolean false")


def validate_toolchain(value: Any) -> None:
    if not isinstance(value, Mapping) or set(value) != TOOLCHAIN_KEYS:
        raise ValueError("toolchain key set is not exact")
    if value.get("pointer_bits") not in {32, 64} or isinstance(
        value.get("pointer_bits"), bool
    ):
        raise ValueError("toolchain pointer_bits must be the number 32 or 64")
    for key in TOOLCHAIN_KEYS - {"pointer_bits"}:
        if not isinstance(value.get(key), str) or not value[key]:
            raise ValueError(f"toolchain {key} must be a nonempty string")


def _read_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        value = tomllib.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a TOML table")
    return value


def _abi_version(manifest: Mapping[str, Any]) -> str:
    major = manifest.get("abi_major")
    minor = manifest.get("abi_minor")
    if not isinstance(major, int) or not isinstance(minor, int):
        raise ValueError("ABI manifest must contain integer abi_major and abi_minor")
    return f"{major}.{minor}"


def _installed_abi_relative(spec: ProviderSpec) -> str:
    return f"share/{spec.installed_data_name}/contracts/abi/{Path(spec.abi_relative_path).name}"


def _installed_contract_root(spec: ProviderSpec, prefix: Path) -> Path:
    return prefix / "share" / spec.installed_data_name / "contracts" / "schema"


def _installed_package_config(spec: ProviderSpec, prefix: Path) -> Path:
    matches = list(prefix.rglob(f"{spec.package_name}Config.cmake"))
    if len(matches) != 1:
        raise ValueError(
            f"{spec.provider_id} installed SDK must contain exactly one package config"
        )
    return matches[0]


def _identity_relative_path(spec: ProviderSpec, mode: str) -> Path:
    return (
        Path("share")
        / "facman"
        / "provider-identities"
        / f"{spec.source_name}.{mode}.json"
    )


def _inventory_manifest_relative_path(spec: ProviderSpec, mode: str) -> Path:
    return (
        Path("share")
        / "facman"
        / "provider-identities"
        / f"{spec.source_name}.{mode}.inventory.v1.json"
    )


def _inventory_exclusions(spec: ProviderSpec, mode: str) -> list[str]:
    return sorted(
        (
            _identity_relative_path(spec, mode).as_posix(),
            _inventory_manifest_relative_path(spec, mode).as_posix(),
        )
    )


def create_sdk_inventory_manifest(
    prefix: Path, spec: ProviderSpec, mode: str
) -> tuple[Path, dict[str, Any]]:
    if mode not in {"installed_static", "installed_shared"}:
        raise ValueError(f"unsupported inventory mode: {mode}")
    exclusions = _inventory_exclusions(spec, mode)
    files = _relative_inventory(prefix, exclusions)
    manifest: dict[str, Any] = {
        "schema": INVENTORY_SCHEMA,
        "provider_id": spec.provider_id,
        "consumption": {
            "mode": mode,
            "linkage": mode.removeprefix("installed_"),
        },
        "excludes": exclusions,
        "files": files,
        "files_sha256": sha256_bytes(canonical_json_bytes(files)),
    }
    assert_path_independent_json(manifest)
    path = prefix / _inventory_manifest_relative_path(spec, mode)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(manifest) + b"\n")
    return path, manifest


def validate_sdk_inventory_manifest(prefix: Path, identity: Mapping[str, Any]) -> None:
    install = identity.get("install")
    if not isinstance(install, Mapping):
        raise ValueError("SDK identity install record is missing")
    relative = install.get("inventory_manifest_relative_path")
    if not isinstance(relative, str) or _looks_absolute(relative):
        raise ValueError("SDK inventory manifest path must be exact and relative")
    relative_path = Path(relative)
    if ".." in relative_path.parts or "\\" in relative:
        raise ValueError("SDK inventory manifest path escapes the SDK")
    manifest_path = prefix / relative_path
    if not manifest_path.is_file():
        raise ValueError("SDK inventory manifest is missing")
    if sha256_file(manifest_path) != install.get("inventory_manifest_sha256"):
        raise ValueError("SDK inventory manifest digest differs from identity")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("schema") != INVENTORY_SCHEMA:
        raise ValueError("SDK inventory manifest schema is invalid")
    if manifest.get("provider_id") != identity.get("provider_id"):
        raise ValueError("SDK inventory manifest names the wrong provider")
    if manifest.get("consumption") != identity.get("consumption"):
        raise ValueError("SDK inventory manifest names the wrong consumption mode")
    provider_id = identity.get("provider_id")
    specs = {spec.provider_id: spec for spec in PROVIDERS}
    if provider_id not in specs:
        raise ValueError("SDK identity names an unknown provider")
    consumption = identity.get("consumption")
    if not isinstance(consumption, Mapping):
        raise ValueError("SDK identity consumption record is missing")
    mode = consumption.get("mode")
    if not isinstance(mode, str):
        raise ValueError("SDK identity consumption mode is missing")
    excludes = manifest.get("excludes")
    expected_excludes = _inventory_exclusions(specs[provider_id], mode)
    if excludes != expected_excludes:
        raise ValueError("SDK inventory manifest exclusions are not exact")
    files = manifest.get("files")
    if not isinstance(files, list):
        raise ValueError("SDK inventory manifest files must be an array")
    files_sha256 = sha256_bytes(canonical_json_bytes(files))
    if manifest.get("files_sha256") != files_sha256:
        raise ValueError("SDK inventory manifest files digest is invalid")
    if install.get("inventory_sha256") != files_sha256:
        raise ValueError("SDK identity inventory digest differs from manifest")
    live_files = _relative_inventory(prefix, excludes)
    if files != live_files:
        raise ValueError("SDK live install inventory differs from manifest")
    if install.get("file_count") != len(live_files):
        raise ValueError("SDK live install inventory count differs from identity")
    if install.get("inventory_sha256") != sha256_bytes(
        canonical_json_bytes(live_files)
    ):
        raise ValueError("SDK live install inventory digest differs from identity")


def build_provider_identity(
    source: ProviderSource,
    prefix: Path,
    mode: str,
    toolchain: Mapping[str, Any],
) -> dict[str, Any]:
    if mode not in {"installed_static", "installed_shared"}:
        raise ValueError(f"unsupported identity mode: {mode}")
    spec = source.spec
    package_path = source.root / "release" / "index" / "sdk_package_workunit.v1.toml"
    package = _read_toml(package_path)
    if package.get("package_version") != spec.package_version:
        raise ValueError(f"{spec.provider_id} package version is not canonical")
    targets = tuple(package.get("exported_targets", ()))
    if targets != spec.exported_targets:
        raise ValueError(f"{spec.provider_id} exported target set is not canonical")

    source_abi = source.root / spec.abi_relative_path
    installed_abi_relative = _installed_abi_relative(spec)
    installed_abi = prefix / Path(installed_abi_relative)
    if not source_abi.is_file() or not installed_abi.is_file():
        raise ValueError(f"{spec.provider_id} ABI manifest is missing")
    if sha256_file(source_abi) != sha256_file(installed_abi):
        raise ValueError(
            f"{spec.provider_id} installed ABI manifest differs from source"
        )
    abi_version = _abi_version(_read_toml(source_abi))

    source_contracts = source.root / "contracts" / "schema"
    installed_contracts = _installed_contract_root(spec, prefix)
    source_contract_inventory = _public_contract_inventory(source_contracts)
    installed_contract_inventory = _relative_inventory(installed_contracts)
    if installed_contract_inventory != _public_contract_inventory(installed_contracts):
        raise ValueError(
            f"{spec.provider_id} installed contract bundle contains non-schema files"
        )
    if source_contract_inventory != installed_contract_inventory:
        raise ValueError(
            f"{spec.provider_id} installed contract bundle differs from source"
        )
    installed_contract_identity = _inventory_entries_identity(
        installed_contract_inventory
    )

    inventory_relative = _inventory_manifest_relative_path(spec, mode).as_posix()
    inventory_path = prefix / inventory_relative
    if not inventory_path.is_file():
        raise ValueError(f"{spec.provider_id} SDK inventory manifest is missing")
    inventory_manifest = json.loads(inventory_path.read_text(encoding="utf-8"))
    if not isinstance(inventory_manifest, dict):
        raise ValueError(f"{spec.provider_id} SDK inventory manifest is malformed")
    if inventory_manifest.get("schema") != INVENTORY_SCHEMA:
        raise ValueError(f"{spec.provider_id} SDK inventory manifest schema is wrong")
    if inventory_manifest.get("provider_id") != spec.provider_id:
        raise ValueError(f"{spec.provider_id} SDK inventory manifest provider is wrong")
    expected_consumption = {
        "mode": mode,
        "linkage": mode.removeprefix("installed_"),
    }
    if inventory_manifest.get("consumption") != expected_consumption:
        raise ValueError(f"{spec.provider_id} SDK inventory manifest mode is wrong")
    if inventory_manifest.get("excludes") != _inventory_exclusions(spec, mode):
        raise ValueError(f"{spec.provider_id} SDK inventory exclusions are not exact")
    installed_files = inventory_manifest.get("files")
    if not isinstance(installed_files, list) or not installed_files:
        raise ValueError(f"{spec.provider_id} SDK inventory is empty or malformed")
    if installed_files != _relative_inventory(
        prefix, _inventory_exclusions(spec, mode)
    ):
        raise ValueError(f"{spec.provider_id} live SDK inventory differs from manifest")
    install_identity = inventory_identity(prefix, _inventory_exclusions(spec, mode))
    if inventory_manifest.get("files_sha256") != install_identity["sha256"]:
        raise ValueError(f"{spec.provider_id} SDK inventory files digest is wrong")
    identity = {
        "schema": IDENTITY_SCHEMA,
        "provider_id": spec.provider_id,
        "repository": spec.repository,
        "canonical_main_ref": "refs/heads/main",
        "source": {
            "commit": source.commit,
            "tree": source.tree,
            "remote": spec.remote,
        },
        "consumption": {
            "mode": mode,
            "linkage": mode.removeprefix("installed_"),
        },
        "package": {
            "name": spec.package_name,
            "version": spec.package_version,
            "metadata_relative_path": _installed_package_config(spec, prefix)
            .relative_to(prefix)
            .as_posix(),
            "metadata_sha256": sha256_file(_installed_package_config(spec, prefix)),
            "exported_targets": list(spec.exported_targets),
        },
        "abi": {
            "version": abi_version,
            "manifest_relative_path": installed_abi_relative,
            "manifest_sha256": sha256_file(installed_abi),
        },
        "contracts": {
            "contract_set_id": spec.contract_set_id,
            "bundle_sha256": spec.contract_digest,
            "inventory_sha256": installed_contract_identity["sha256"],
            "file_count": installed_contract_identity["file_count"],
        },
        "install": {
            "root": ".",
            "inventory_sha256": install_identity["sha256"],
            "file_count": install_identity["file_count"],
            "inventory_manifest_relative_path": inventory_relative,
            "inventory_manifest_sha256": sha256_file(inventory_path),
        },
        "toolchain": dict(toolchain),
        "authority": dict(AUTHORITY),
    }
    validate_authority(identity["authority"])
    validate_toolchain(identity["toolchain"])
    assert_path_independent_json(identity)
    validate_sdk_inventory_manifest(prefix, identity)
    return identity


def candidate_lock_text(
    sources: Sequence[ProviderSource],
    tracked_consumed: Mapping[str, Mapping[str, Any]],
    *,
    candidate_class: str = "conformance",
) -> str:
    if {source.spec.provider_id for source in sources} != {
        "universal_launcher",
        "universal_setup",
    } or len(sources) != 2:
        raise ValueError("candidate lock requires exactly the two canonical providers")
    candidate_pins = {source.spec.provider_id: source.commit for source in sources}
    tracked_pins = {
        provider_id: record.get("pin")
        for provider_id, record in tracked_consumed.items()
    }
    if set(tracked_pins) != set(candidate_pins):
        raise ValueError("tracked lock must name exactly the two canonical providers")
    if candidate_class not in {"conformance", "sdk_consumption"}:
        raise ValueError("provider candidate class is not recognized")
    candidate_differs = candidate_pins != tracked_pins
    if candidate_class == "conformance":
        schema = "facman.provider_conformance_lock.v1"
        candidate_id = "facman_provider_conformance_candidate_v1"
        conformance_only = True
        sdk_consumption_candidate = False
    else:
        schema = "facman.provider_sdk_consumption_lock.v1"
        candidate_id = "facman_provider_sdk_consumption_candidate_v1"
        conformance_only = False
        sdk_consumption_candidate = True
    lines = [
        f'schema = "{schema}"',
        f'id = "{candidate_id}"',
        f"conformance_only = {str(conformance_only).lower()}",
        f"sdk_consumption_candidate = {str(sdk_consumption_candidate).lower()}",
        "candidate_not_adopted = true",
        "release_eligible = false",
        "tracked_lock_mutated = false",
        f"candidate_differs_from_tracked = {str(candidate_differs).lower()}",
        "",
    ]
    for source in sorted(sources, key=lambda item: item.spec.provider_id):
        spec = source.spec
        lines.extend(
            [
                "[[component]]",
                f'id = "{spec.provider_id}"',
                f'source = "{spec.source_name}"',
                f'pin = "{source.commit}"',
                f'tree = "{source.tree}"',
                f'remote = "{spec.remote}"',
                'required_ref = "refs/heads/main"',
                "",
            ]
        )
    lines.append("[authority]")
    lines.extend(f"{key} = false" for key in sorted(AUTHORITY))
    return "\n".join(lines) + "\n"


def canonical_provider_source_records(
    sources: Mapping[str, ProviderSource],
) -> dict[str, dict[str, str]]:
    return {
        provider_id: {
            "commit": source.commit,
            "tree": source.tree,
            "remote": source.spec.remote,
            "canonical_main_ref": "refs/heads/main",
        }
        for provider_id, source in sorted(sources.items())
    }


def provider_truth_sets(
    facman_root: Path,
    sources: Mapping[str, ProviderSource],
) -> tuple[dict[str, Any], dict[str, str]]:
    expected_ids = {spec.provider_id for spec in PROVIDERS}
    if set(sources) != expected_ids:
        raise ValueError("canonical candidates must name exactly the two providers")

    workspace_path = facman_root / "release" / "index" / "workspace_lock.v1.toml"
    release_path = facman_root / "release" / "index" / "providers.lock.v2.toml"
    workspace = _read_toml(workspace_path)
    release = _read_toml(release_path)
    if workspace.get("schema") != "flaunch.workspace_lock.v1":
        raise ValueError("tracked workspace lock schema is not canonical")
    if release.get("schema") != "facman.providers_lock.v2":
        raise ValueError("authored release-provider lock schema is not canonical")

    tracked_entries = workspace.get("component")
    release_entries = release.get("provider")
    if not isinstance(tracked_entries, list) or not isinstance(release_entries, list):
        raise ValueError("provider lock files do not contain provider arrays")

    tracked: dict[str, Any] = {}
    for entry in tracked_entries:
        if not isinstance(entry, dict) or entry.get("id") not in expected_ids:
            continue
        provider_id = str(entry["id"])
        if provider_id in tracked:
            raise ValueError(f"workspace lock repeats {provider_id}")
        tracked[provider_id] = {
            "pin": entry.get("pin"),
            "source": entry.get("source"),
            "remote": entry.get("remote"),
            "required_ref": entry.get("required_ref"),
        }

    authored: dict[str, Any] = {}
    authored_fields = (
        "source_revision",
        "package_version",
        "package_identity_kind",
        "package_digest",
        "abi_version",
        "contract_set_id",
        "contract_digest",
        "consumption_mode",
    )
    for entry in release_entries:
        if not isinstance(entry, dict) or entry.get("id") not in expected_ids:
            continue
        provider_id = str(entry["id"])
        if provider_id in authored:
            raise ValueError(f"release-provider lock repeats {provider_id}")
        authored[provider_id] = {
            "repository": entry.get("repository"),
            **{field: entry.get(field) for field in authored_fields},
        }

    if set(tracked) != expected_ids or set(authored) != expected_ids:
        raise ValueError(
            "provider lock files must name each canonical provider exactly once"
        )
    for provider_id, record in tracked.items():
        spec = sources[provider_id].spec
        if record["source"] != spec.source_name or record["remote"] != spec.remote:
            raise ValueError(
                f"workspace lock identity for {provider_id} is not canonical"
            )
        if record["required_ref"] != "refs/heads/main":
            raise ValueError(
                f"workspace lock ref for {provider_id} is not canonical main"
            )
        if not isinstance(record["pin"], str) or not re.fullmatch(
            r"[0-9a-f]{40}", record["pin"]
        ):
            raise ValueError(f"workspace lock pin for {provider_id} is malformed")
    for provider_id, record in authored.items():
        spec = sources[provider_id].spec
        if record["repository"] != spec.repository:
            raise ValueError(f"release-provider repository for {provider_id} is wrong")
        for field, value in record.items():
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"release-provider {provider_id} field {field} is missing"
                )

    canonical = canonical_provider_source_records(sources)
    truth_sets = {
        "tracked_consumed": dict(sorted(tracked.items())),
        "authored_release_provider": dict(sorted(authored.items())),
        "canonical_candidate": canonical,
    }
    assert_path_independent_json(truth_sets)
    return truth_sets, {
        "workspace_lock_sha256": sha256_file(workspace_path),
        "release_provider_lock_sha256": sha256_file(release_path),
    }


def negative_identity_variants(
    ulk_identity: Mapping[str, Any],
    usk_identity: Mapping[str, Any],
) -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
    """Return deterministic identity-only fail-closed controls."""

    variants: list[tuple[str, dict[str, Any], dict[str, Any]]] = []

    def mutate(
        name: str,
        provider: str,
        dotted_path: tuple[str, ...],
        value: Any,
    ) -> None:
        ulk = copy.deepcopy(dict(ulk_identity))
        usk = copy.deepcopy(dict(usk_identity))
        target = ulk if provider == "ulk" else usk
        node: dict[str, Any] = target
        for part in dotted_path[:-1]:
            node = node[part]
        node[dotted_path[-1]] = value
        variants.append((name, ulk, usk))

    mutate("wrong_ulk_source_commit", "ulk", ("source", "commit"), "0" * 40)
    mutate("wrong_usk_source_commit", "usk", ("source", "commit"), "f" * 40)
    mutate("wrong_source_tree", "ulk", ("source", "tree"), "1" * 40)
    mutate("wrong_package_version", "ulk", ("package", "version"), "999.0.0")
    mutate("wrong_package_metadata", "usk", ("package", "metadata_sha256"), "2" * 64)
    mutate("wrong_abi_version", "ulk", ("abi", "version"), "99.0")
    mutate("wrong_abi_manifest", "usk", ("abi", "manifest_sha256"), "3" * 64)
    mutate("wrong_contract_bundle", "ulk", ("contracts", "bundle_sha256"), "4" * 64)
    mutate("wrong_processor", "usk", ("toolchain", "processor"), "wrong-processor")
    mutate("stale_relative_install_root", "ulk", ("install", "root"), "../stale")
    mutate(
        "injected_absolute_install_root", "usk", ("install", "root"), "/injected/sdk"
    )
    mutate("authority_escalation", "ulk", ("authority", "product_execution"), True)

    missing_ulk = copy.deepcopy(dict(ulk_identity))
    missing_usk = copy.deepcopy(dict(usk_identity))
    del missing_ulk["authority"]["publication"]
    variants.append(("missing_authority_key", missing_ulk, missing_usk))

    unknown_ulk = copy.deepcopy(dict(ulk_identity))
    unknown_usk = copy.deepcopy(dict(usk_identity))
    unknown_usk["authority"]["unknown_authority"] = False
    variants.append(("unknown_authority_key", unknown_ulk, unknown_usk))

    swapped_ulk = copy.deepcopy(dict(usk_identity))
    swapped_usk = copy.deepcopy(dict(ulk_identity))
    variants.append(("swapped_provider_identities", swapped_ulk, swapped_usk))
    return variants


def extract_last_json_object(output: str) -> dict[str, Any]:
    for line in reversed(output.splitlines()):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise ValueError("command did not emit a JSON object")


_PROVIDER_MODES = frozenset({"source", "installed_static", "installed_shared"})
_PROVIDER_CONSUMPTION_BY_MODE = {
    "source": "conformance_source",
    "installed_static": "conformance_rehearsal_installed_static",
    "installed_shared": "conformance_rehearsal_installed_shared",
}
_CONTRACT_ID_POLICIES = {
    "request_id": (r"request-[0-9a-f]{32}", "<request-id>"),
    "operation_id": (r"op-[0-9a-f]{32}", "<operation-id>"),
    "attempt_id": (r"attempt-[0-9a-f]{32}", "<attempt-id>"),
}
_NORMALIZATION_KINDS = frozenset(
    {
        "mode",
        "build_identity",
        "build_root",
        "loader",
        "address",
        *_CONTRACT_ID_POLICIES,
    }
)
_SCHEMA_NORMALIZATION_POLICIES: dict[str, dict[tuple[str, ...], str]] = {
    "facman.transport_response.v2": {
        ("request_id",): "request_id",
        ("operation", "operation_id"): "operation_id",
        ("operation", "attempt_id"): "attempt_id",
        ("payload", "backend_identity", "build", "build_identity"): (
            "build_identity"
        ),
    },
    "factorio.product.v1": {
        ("backend_identity", "build", "build_identity"): "build_identity",
    },
    "facman.backend_identity.v1": {
        ("build", "build_identity"): "build_identity",
    },
    # Internal comparator fixture/schema for explicitly declared portable
    # build/loader observations. Production schemas get no implicit fields.
    "facman.provider_conformance_comparison.v1": {
        ("provider_mode",): "mode",
        ("build_root",): "build_root",
        ("loader", "runtime_path"): "loader",
        ("loader", "loaded_address"): "address",
    },
}
_ABSOLUTE_PATH_FRAGMENT = re.compile(
    r"(?<![A-Za-z0-9_:/.])(?:[A-Za-z]:[\\/]|\\\\|//|/(?!/))"
)
_NORMALIZATION_TOKEN = re.compile(r"<[A-Za-z][A-Za-z0-9_.-]*>")


def normalize_build_identity(value: str) -> str:
    """Validate and normalize the two mode-dependent build-identity segments."""

    parts = value.split(";")
    mode_matches = [
        index for index, part in enumerate(parts) if part.startswith("provider_mode=")
    ]
    classification_matches = [
        index
        for index, part in enumerate(parts)
        if part.startswith("provider_consumption_classification=")
    ]
    if len(mode_matches) != 1:
        raise ValueError(
            "build_identity must contain exactly one provider_mode segment"
        )
    if len(classification_matches) != 1:
        raise ValueError(
            "build_identity must contain exactly one "
            "provider_consumption_classification segment"
        )
    mode_index = mode_matches[0]
    classification_index = classification_matches[0]
    mode = parts[mode_index].removeprefix("provider_mode=")
    if mode not in _PROVIDER_MODES:
        raise ValueError("build_identity provider_mode is not recognized")
    classification = parts[classification_index].removeprefix(
        "provider_consumption_classification="
    )
    expected_classification = _PROVIDER_CONSUMPTION_BY_MODE[mode]
    if classification != expected_classification:
        raise ValueError(
            "build_identity provider_mode/provider_consumption_classification "
            "pair is inconsistent"
        )
    parts[mode_index] = "provider_mode=<normalized>"
    parts[classification_index] = "provider_consumption_classification=<normalized>"
    return ";".join(parts)


def _contains_absolute_path(value: str) -> bool:
    return _ABSOLUTE_PATH_FRAGMENT.search(value) is not None


def _normalize_declared_path(
    value: str, replacements: Sequence[tuple[str, str]]
) -> str:
    """Normalize one declared path only when it is rooted beneath an approved root."""

    if _NORMALIZATION_TOKEN.search(value):
        raise ValueError("normalization tokens are forbidden in source observations")
    for root_text, token in replacements:
        windows_root = bool(
            re.match(r"^[A-Za-z]:[\\/]", root_text)
            or root_text.startswith(("\\\\", "//"))
        )
        candidate = value.replace("\\", "/") if windows_root else value
        root = root_text.replace("\\", "/") if windows_root else root_text
        root = root.rstrip("/")
        compared_candidate = candidate.casefold() if windows_root else candidate
        compared_root = root.casefold() if windows_root else root
        if compared_candidate == compared_root:
            return token
        prefix = compared_root + "/"
        if not compared_candidate.startswith(prefix):
            continue
        suffix = candidate[len(root) + 1 :]
        parts = suffix.split("/")
        if not suffix or any(part in {"", ".", ".."} for part in parts):
            raise ValueError("declared path contains a non-canonical suffix")
        return token + "/" + "/".join(parts)
    if _contains_absolute_path(value):
        raise ValueError("declared path is outside every approved root")
    return value


def normalize_semantic_value(
    value: Any,
    roots: Mapping[str, Path],
    *,
    field_policies: Mapping[tuple[str, ...], str] | None = None,
) -> Any:
    """Normalize only schema-declared fields and reject unknown host paths."""

    replacements: list[tuple[str, str]] = []
    for name, root in roots.items():
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]*", name):
            raise ValueError(f"invalid normalization root name: {name}")
        resolved = str(root.resolve())
        replacements.append((resolved, f"<{name}>"))
        replacements.append((resolved.replace("\\", "/"), f"<{name}>"))
    replacements.sort(key=lambda item: len(item[0]), reverse=True)

    schema = value.get("schema") if isinstance(value, dict) else None
    policies = dict(_SCHEMA_NORMALIZATION_POLICIES.get(str(schema), {}))
    if field_policies:
        for path, kind in field_policies.items():
            if kind not in _NORMALIZATION_KINDS:
                raise ValueError(f"unknown semantic normalization kind: {kind}")
            policies[path] = kind

    def normalize(child: Any, path: tuple[str, ...] = ()) -> Any:
        if isinstance(child, dict):
            return {
                key: normalize(item, (*path, key))
                for key, item in sorted(child.items())
            }
        if isinstance(child, list):
            return [normalize(item, (*path, "[]")) for item in child]
        if isinstance(child, str):
            text = child.replace("\r\n", "\n")
            policy = policies.get(path)
            if policy == "build_identity":
                text = normalize_build_identity(text)
            elif policy == "mode":
                if text not in _PROVIDER_MODES:
                    raise ValueError("declared provider mode is not recognized")
                text = "<provider-mode>"
            elif policy in {"build_root", "loader"}:
                return _normalize_declared_path(text, replacements)
            elif policy == "address":
                if not re.fullmatch(r"0x[0-9A-Fa-f]{6,16}", text):
                    raise ValueError("declared loader address is malformed")
                text = "<address>"
            elif policy in _CONTRACT_ID_POLICIES:
                pattern, token = _CONTRACT_ID_POLICIES[policy]
                if not re.fullmatch(pattern, text):
                    raise ValueError(f"declared {policy} is malformed")
                text = token
            if _contains_absolute_path(text):
                rendered = ".".join(path) or "$"
                raise ValueError(
                    f"unknown absolute path is forbidden in semantic field {rendered}"
                )
            return text
        return child

    return normalize(value)


def _safe_label(value: str) -> str:
    label = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-.")
    if not label:
        raise ValueError("empty command label")
    return label


class CommandRunner:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.log_dir = output_dir / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.counter = 0

    def run(
        self,
        label: str,
        command: Sequence[str],
        cwd: Path,
        *,
        environment: Mapping[str, str] | None = None,
        expect_failure: bool = False,
    ) -> CommandResult:
        self.counter += 1
        log_name = f"{self.counter:03d}-{_safe_label(label)}.log"
        env = dict(os.environ)
        env.update(
            {
                "GIT_NO_LAZY_FETCH": "1",
                "GIT_TERMINAL_PROMPT": "0",
            }
        )
        if environment:
            env.update(environment)
        completed = subprocess.run(
            list(command),
            cwd=cwd,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
        )
        header = f"returncode: {completed.returncode}\ncommand: {list(command)!r}\n\n"
        (self.log_dir / log_name).write_text(
            header + completed.stdout,
            encoding="utf-8",
            errors="replace",
            newline="\n",
        )
        succeeded = completed.returncode == 0
        if expect_failure == succeeded:
            expectation = "failure" if expect_failure else "success"
            raise RuntimeError(
                f"{label} did not produce expected {expectation}; see logs/{log_name}"
            )
        return CommandResult(completed.returncode, completed.stdout, f"logs/{log_name}")


def _external_directory(path: Path, source_roots: Sequence[Path], label: str) -> Path:
    resolved = path.resolve()
    for root in source_roots:
        source = root.resolve()
        if (
            resolved == source
            or resolved.is_relative_to(source)
            or source.is_relative_to(resolved)
        ):
            raise ValueError(f"--{label} must be outside every source checkout")
    if resolved.exists() and any(resolved.iterdir()):
        raise ValueError(f"--{label} must be absent or empty")
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _git_command(root: Path, *arguments: str) -> list[str]:
    return [
        "git",
        "-c",
        f"safe.directory={root.resolve()}",
        "-C",
        str(root),
        *arguments,
    ]


def observe_provider(
    spec: ProviderSpec, root: Path, runner: CommandRunner
) -> ProviderSource:
    if not root.is_dir():
        raise ValueError(f"{spec.display_name} checkout does not exist")
    head = runner.run(
        f"{spec.provider_id}-head",
        _git_command(root, "rev-parse", "HEAD"),
        ROOT,
    ).output.strip()
    if head != spec.canonical_commit:
        raise ValueError(f"{spec.display_name} HEAD is not the exact provider input commit")
    remote = runner.run(
        f"{spec.provider_id}-remote",
        _git_command(root, "remote", "get-url", "origin"),
        ROOT,
    ).output.strip()
    if remote != spec.remote:
        raise ValueError(
            f"{spec.display_name} origin does not match the canonical HTTPS remote"
        )
    runner.run(
        f"{spec.provider_id}-main",
        _git_command(root, "rev-parse", "refs/remotes/origin/main"),
        ROOT,
    ).output.strip()
    try:
        runner.run(
            f"{spec.provider_id}-main-reachability",
            _git_command(
                root, "merge-base", "--is-ancestor", head, "refs/remotes/origin/main"
            ),
            ROOT,
        )
    except RuntimeError as error:
        raise ValueError(
            f"{spec.display_name} exact provider input is not reachable from origin/main"
        ) from error
    tree = runner.run(
        f"{spec.provider_id}-head-tree",
        _git_command(root, "rev-parse", "HEAD^{tree}"),
        ROOT,
    ).output.strip()
    status = runner.run(
        f"{spec.provider_id}-clean",
        _git_command(root, "status", "--porcelain=v1", "--untracked-files=all"),
        ROOT,
    ).output.strip()
    if status:
        raise ValueError(f"{spec.display_name} checkout is not clean")
    return ProviderSource(spec=spec, root=root.resolve(), commit=head, tree=tree)


def _cmake_cache(build: Path) -> dict[str, str]:
    cache_path = build / "CMakeCache.txt"
    if not cache_path.is_file():
        raise ValueError(f"provider build cache is missing: {build.name}")
    values: dict[str, str] = {}
    for line in cache_path.read_text(encoding="utf-8", errors="strict").splitlines():
        match = re.match(r"^([^:#=]+):[^=]*=(.*)$", line)
        if match:
            values[match.group(1)] = match.group(2)
    return values


def _generated_cmake_value(build: Path, key: str, filename: str) -> str:
    value = _optional_generated_cmake_value(build, key, filename)
    if value == "none":
        raise ValueError(f"provider build must expose one exact nonempty {key}")
    return value


def _optional_generated_cmake_value(build: Path, key: str, filename: str) -> str:
    values: set[str] = set()
    pattern = re.compile(
        rf"set\(\s*{re.escape(key)}\s+(?:\"([^\"]*)\"|([^\s\)]+))\s*\)"
    )
    for path in sorted((build / "CMakeFiles").rglob(filename)):
        text = path.read_text(encoding="utf-8", errors="strict")
        for quoted, unquoted in pattern.findall(text):
            value = quoted or unquoted
            values.add(value or "none")
    if len(values) > 1:
        raise ValueError(
            f"provider build must expose one exact {key}; observed {sorted(values)!r}"
        )
    return next(iter(values), "none")


def _cache_value_or_none(cache: Mapping[str, str], key: str) -> str:
    return cache.get(key) or "none"


def _cache_or_generated_value(
    cache: Mapping[str, str], build: Path, key: str, filename: str
) -> str:
    cached = _cache_value_or_none(cache, key)
    generated = _optional_generated_cmake_value(build, key, filename)
    if cached != "none" and generated != "none" and cached != generated:
        raise ValueError(f"provider cache/generated values disagree on {key}")
    return cached if cached != "none" else generated


def _provider_build_toolchain(build: Path, config: str) -> dict[str, Any]:
    cache = _cmake_cache(build)
    generator = cache.get("CMAKE_GENERATOR", "")
    configurations = cache.get("CMAKE_CONFIGURATION_TYPES", "")
    if configurations:
        if config not in configurations.split(";"):
            raise ValueError("requested configuration is absent from provider build")
    elif cache.get("CMAKE_BUILD_TYPE") != config:
        raise ValueError("provider build type differs from requested configuration")
    pointer_bytes = _generated_cmake_value(
        build, "CMAKE_C_SIZEOF_DATA_PTR", "CMakeCCompiler.cmake"
    )
    try:
        pointer_bits = int(pointer_bytes) * 8
    except ValueError as error:
        raise ValueError("provider pointer size is not numeric") from error
    record: dict[str, Any] = {
        "generator": generator,
        "generator_platform": _cache_value_or_none(cache, "CMAKE_GENERATOR_PLATFORM"),
        "generator_toolset": _cache_value_or_none(cache, "CMAKE_GENERATOR_TOOLSET"),
        "system": _generated_cmake_value(
            build, "CMAKE_SYSTEM_NAME", "CMakeSystem.cmake"
        ),
        "processor": _generated_cmake_value(
            build, "CMAKE_SYSTEM_PROCESSOR", "CMakeSystem.cmake"
        ),
        "pointer_bits": pointer_bits,
        "configuration": config,
        "c_compiler_id": _generated_cmake_value(
            build, "CMAKE_C_COMPILER_ID", "CMakeCCompiler.cmake"
        ),
        "c_compiler_version": _generated_cmake_value(
            build, "CMAKE_C_COMPILER_VERSION", "CMakeCCompiler.cmake"
        ),
        "c_compiler_target": _cache_or_generated_value(
            cache, build, "CMAKE_C_COMPILER_TARGET", "CMakeCCompiler.cmake"
        ),
        "sysroot": _cache_value_or_none(cache, "CMAKE_SYSROOT"),
        "msvc_runtime_library": _cache_value_or_none(
            cache, "CMAKE_MSVC_RUNTIME_LIBRARY"
        ),
    }
    if not generator:
        raise ValueError("provider build generator is missing")
    return record


def cmake_toolchain(
    cmake: str,
    config: str,
    builds: Mapping[str, Path],
    runner: CommandRunner,
) -> dict[str, Any]:
    if set(builds) != {spec.provider_id for spec in PROVIDERS}:
        raise ValueError("bounded toolchain observation requires both provider caches")
    records = {
        provider_id: _provider_build_toolchain(build, config)
        for provider_id, build in builds.items()
    }
    first = records["universal_launcher"]
    for field in (
        "generator",
        "generator_platform",
        "generator_toolset",
        "system",
        "processor",
        "pointer_bits",
        "configuration",
        "c_compiler_id",
        "c_compiler_version",
        "c_compiler_target",
        "sysroot",
        "msvc_runtime_library",
    ):
        values = {record[field] for record in records.values()}
        if len(values) != 1:
            raise ValueError(f"provider build toolchains disagree on {field}")

    usk_build = builds["universal_setup"]
    version_output = runner.run("cmake-version", [cmake, "--version"], ROOT).output
    first_line = version_output.splitlines()[0].strip()
    toolchain = {
        "cmake": first_line,
        **first,
        "cxx_compiler_id": _generated_cmake_value(
            usk_build, "CMAKE_CXX_COMPILER_ID", "CMakeCXXCompiler.cmake"
        ),
        "cxx_compiler_version": _generated_cmake_value(
            usk_build, "CMAKE_CXX_COMPILER_VERSION", "CMakeCXXCompiler.cmake"
        ),
        "cxx_compiler_target": _cache_or_generated_value(
            _cmake_cache(usk_build),
            usk_build,
            "CMAKE_CXX_COMPILER_TARGET",
            "CMakeCXXCompiler.cmake",
        ),
    }
    validate_toolchain(toolchain)
    return toolchain


def _provider_configure_command(
    source: ProviderSource,
    build: Path,
    prefix: Path,
    linkage: str,
    cmake: str,
    config: str,
    generator_platform: str | None,
) -> list[str]:
    provider_prefix = source.spec.cmake_prefix
    command = [
        cmake,
        "-S",
        str(source.root),
        "-B",
        str(build),
        f"-DCMAKE_BUILD_TYPE={config}",
        f"-DCMAKE_INSTALL_PREFIX={prefix}",
        f"-D{provider_prefix}_BUILD_APPS=OFF",
        f"-D{provider_prefix}_BUILD_TESTS=OFF",
        f"-D{provider_prefix}_BUILD_STATIC=ON",
        f"-D{provider_prefix}_BUILD_SHARED=ON",
    ]
    if provider_prefix == "USK":
        command.append("-DUSK_BUILD_FUZZERS=OFF")
    if os.name == "nt":
        command.append(
            "-DCMAKE_MSVC_RUNTIME_LIBRARY="
            "MultiThreaded$<$<CONFIG:Debug>:Debug>"
        )
    if generator_platform:
        command.extend(["-A", generator_platform])
    return command


def install_provider_sdk(
    source: ProviderSource,
    linkage: str,
    work_dir: Path,
    cmake: str,
    config: str,
    generator_platform: str | None,
    runner: CommandRunner,
) -> tuple[Path, Path]:
    build = work_dir / "provider-build" / source.spec.provider_id / linkage
    prefix = work_dir / "provider-install" / source.spec.provider_id / linkage
    runner.run(
        f"{source.spec.provider_id}-{linkage}-configure",
        _provider_configure_command(
            source, build, prefix, linkage, cmake, config, generator_platform
        ),
        ROOT,
    )
    runner.run(
        f"{source.spec.provider_id}-{linkage}-build",
        [cmake, "--build", str(build), "--config", config, "--parallel"],
        ROOT,
    )
    runner.run(
        f"{source.spec.provider_id}-{linkage}-install",
        [cmake, "--install", str(build), "--config", config],
        ROOT,
    )
    if not prefix.is_dir():
        raise ValueError(
            f"{source.spec.display_name} {linkage} install was not created"
        )
    return prefix, build


def scan_installed_metadata(prefix: Path, forbidden_roots: Sequence[Path]) -> int:
    suffixes = {".cmake", ".h", ".hpp", ".json", ".md", ".toml", ".txt"}
    forbidden: list[str] = []
    for root in forbidden_roots:
        text = str(root.resolve())
        forbidden.extend((text, text.replace("\\", "/")))
    scanned = 0
    for path in prefix.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in suffixes:
            continue
        scanned += 1
        text = path.read_text(encoding="utf-8", errors="ignore")
        lowered = text.casefold()
        for root in forbidden:
            if root.casefold() in lowered:
                raise ValueError(
                    f"installed metadata leaks an absolute source/build/install path: {path.name}"
                )
    return scanned


def run_provider_self_conformance(
    source: ProviderSource,
    work_dir: Path,
    config: str,
    generator_platform: str | None,
    runner: CommandRunner,
) -> dict[str, Any]:
    command = [
        sys.executable,
        "tools/cmake_sdk_conformance.py",
        "--work-dir",
        str(work_dir / "provider-self" / source.spec.provider_id),
        "--config",
        config,
        "--phase",
        "full",
    ]
    if generator_platform:
        command.extend(["--platform", generator_platform])
    result = runner.run(
        f"{source.spec.provider_id}-self-conformance",
        command,
        source.root,
    )
    parsed = extract_last_json_object(result.output)
    if parsed.get("phase") != "full":
        raise ValueError(
            f"{source.spec.display_name} did not report its requested provider phase"
        )
    return parsed


def write_identity(path: Path, identity: Mapping[str, Any]) -> None:
    assert_path_independent_json(identity)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(identity, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _validate_identity_pairing(
    prefixes: Mapping[str, Path], identities: Mapping[str, Path]
) -> None:
    if set(prefixes) != set(identities):
        raise ValueError("SDK prefixes and identity sidecars name different providers")
    for provider_id, prefix in prefixes.items():
        resolved_prefix = prefix.resolve()
        resolved_identity = identities[provider_id].resolve()
        if not resolved_identity.is_relative_to(resolved_prefix):
            raise ValueError(
                f"{provider_id} identity sidecar must be inside its selected SDK root"
            )


def _facman_configure_command(
    facman_root: Path,
    build: Path,
    candidate_lock: Path,
    provider_mode: str,
    cmake: str,
    config: str,
    generator_platform: str | None,
    sources: Mapping[str, ProviderSource],
    prefixes: Mapping[str, Path] | None = None,
    identities: Mapping[str, Path] | None = None,
) -> list[str]:
    command = [
        cmake,
        "-S",
        str(facman_root),
        "-B",
        str(build),
        f"-DCMAKE_BUILD_TYPE={config}",
        "-DFACMAN_BUILD_CLI=ON",
        "-DFACMAN_BUILD_TUI=OFF",
        "-DFACMAN_BUILD_DAEMON=OFF",
        "-DFACMAN_BUILD_GUI=OFF",
        "-DFACMAN_BUILD_TESTS=ON",
        "-DFACMAN_BUILD_PLAY_EVIDENCE_TOOLS=OFF",
        "-DFACMAN_WARNINGS_AS_ERRORS=ON",
        f"-DFACMAN_PROVIDER_MODE={provider_mode}",
        f"-DFACMAN_PROVIDER_LOCK_FILE={candidate_lock}",
        "-DFACMAN_PROVIDER_CONFORMANCE_ONLY=ON",
    ]
    if provider_mode == "source":
        command.extend(
            [
                f"-DFLAUNCH_UNIVERSAL_LAUNCHER_ROOT={sources['universal_launcher'].root}",
                f"-DFLAUNCH_UNIVERSAL_SETUP_ROOT={sources['universal_setup'].root}",
            ]
        )
    else:
        if prefixes is None or identities is None:
            raise ValueError(
                "installed provider modes require prefixes and identity files"
            )
        _validate_identity_pairing(prefixes, identities)
        command.extend(
            [
                f"-DFACMAN_UNIVERSAL_LAUNCHER_SDK_ROOT={prefixes['universal_launcher']}",
                f"-DFACMAN_UNIVERSAL_SETUP_SDK_ROOT={prefixes['universal_setup']}",
                f"-DFACMAN_UNIVERSAL_LAUNCHER_IDENTITY_FILE={identities['universal_launcher']}",
                f"-DFACMAN_UNIVERSAL_SETUP_IDENTITY_FILE={identities['universal_setup']}",
            ]
        )
    if generator_platform:
        command.extend(["-A", generator_platform])
    return command


def _is_runtime_library(path: Path) -> bool:
    name = path.name.casefold()
    return (
        name.endswith(".dll")
        or name.endswith(".dylib")
        or re.search(r"\.so(?:\..+)?$", name) is not None
    )


def _runtime_shaped_files(prefix: Path) -> list[Path]:
    files: list[Path] = []
    for directory in (prefix / "bin", prefix / "lib", prefix / "lib64"):
        if not directory.is_dir():
            continue
        files.extend(
            path
            for path in directory.rglob("*")
            if (path.is_file() or path.is_symlink()) and _is_runtime_library(path)
        )
    return sorted(files, key=lambda path: path.as_posix())


def _declared_shared_runtime_files(
    prefixes: Mapping[str, Path],
    identities: Mapping[str, Mapping[str, Any]],
) -> list[Path]:
    if set(prefixes) != {spec.provider_id for spec in PROVIDERS} or set(
        identities
    ) != set(prefixes):
        raise ValueError("private runtime requires both exact provider SDK identities")

    declared: list[Path] = []
    for spec in PROVIDERS:
        prefix = prefixes[spec.provider_id]
        identity = identities[spec.provider_id]
        package = identity.get("package")
        toolchain = identity.get("toolchain")
        if not isinstance(package, Mapping) or not isinstance(toolchain, Mapping):
            raise ValueError(
                f"{spec.provider_id} identity lacks package/toolchain data"
            )
        shared_target = f"{spec.package_name}::CoreShared"
        if package.get("exported_targets") != list(spec.exported_targets):
            raise ValueError(f"{spec.provider_id} exported targets are not exact")
        metadata_relative = package.get("metadata_relative_path")
        config = toolchain.get("configuration")
        if not isinstance(metadata_relative, str) or not isinstance(config, str):
            raise ValueError(f"{spec.provider_id} runtime declaration is incomplete")
        metadata = prefix / Path(metadata_relative)
        if not metadata.is_file() or not metadata.resolve().is_relative_to(
            prefix.resolve()
        ):
            raise ValueError(f"{spec.provider_id} package metadata is outside its SDK")

        locations: list[tuple[str, str]] = []
        block_pattern = re.compile(
            rf"set_target_properties\(\s*\"?{re.escape(shared_target)}\"?\s+"
            rf"PROPERTIES(?P<body>.*?)\n\s*\)",
            re.DOTALL,
        )
        location_pattern = re.compile(
            r"IMPORTED_LOCATION(?:_([A-Za-z0-9_]+))?\s+"
            r'"\$\{_IMPORT_PREFIX\}/([^"\r\n]+)"'
        )
        target_files = sorted(metadata.parent.glob("*Targets*.cmake"))
        if not target_files:
            raise ValueError(
                f"{spec.provider_id} installed targets metadata is missing"
            )
        for target_file in target_files:
            text = target_file.read_text(encoding="utf-8", errors="strict")
            for block in block_pattern.finditer(text):
                for suffix, relative in location_pattern.findall(block.group("body")):
                    locations.append((suffix.upper(), relative))

        exact_config = {
            relative for suffix, relative in locations if suffix == config.upper()
        }
        fallback = {
            relative for suffix, relative in locations if suffix in {"", "NOCONFIG"}
        }
        selected = exact_config or fallback
        if len(selected) != 1:
            raise ValueError(
                f"{spec.provider_id} CoreShared must declare one runtime location for {config}"
            )
        relative = next(iter(selected))
        if (
            _looks_absolute(relative)
            or "\\" in relative
            or ".." in Path(relative).parts
            or ";" in relative
        ):
            raise ValueError(f"{spec.provider_id} runtime location is not portable")
        location = prefix / Path(relative)
        if not location.is_file() or not location.resolve().is_relative_to(
            prefix.resolve()
        ):
            raise ValueError(f"{spec.provider_id} declared runtime artifact is missing")
        if not _is_runtime_library(location):
            raise ValueError(
                f"{spec.provider_id} declared artifact is not a runtime library"
            )

        resolved_location = location.resolve()
        closure_paths = [resolved_location, location.absolute()]
        for sibling in location.parent.iterdir():
            if sibling.is_symlink() and sibling.resolve() == resolved_location:
                closure_paths.append(sibling.absolute())
        closure = set(closure_paths)
        seen_physical_names: set[tuple[str, str]] = set()
        for runtime_path in closure_paths:
            physical_name = (
                os.path.normcase(runtime_path.name),
                os.path.normcase(str(runtime_path.resolve())),
            )
            if physical_name in seen_physical_names:
                continue
            seen_physical_names.add(physical_name)
            declared.append(runtime_path)

        runtime_candidates = {path.absolute() for path in _runtime_shaped_files(prefix)}
        undeclared = sorted(
            runtime_candidates - set(closure), key=lambda path: path.as_posix()
        )
        if undeclared:
            names = ", ".join(path.name for path in undeclared)
            raise ValueError(
                f"{spec.provider_id} SDK has undeclared runtime artifacts: {names}"
            )

    unique = {path.absolute(): path for path in declared}
    return [unique[key] for key in sorted(unique, key=lambda path: path.as_posix())]


def _runtime_environment(runtime_dirs: Sequence[Path]) -> dict[str, str]:
    path_value = os.pathsep.join(str(path) for path in runtime_dirs)
    environment: dict[str, str] = {
        "PATH": path_value + os.pathsep + os.environ.get("PATH", ""),
    }
    if platform.system() == "Linux":
        environment["LD_LIBRARY_PATH"] = path_value
    elif platform.system() == "Darwin":
        environment["DYLD_LIBRARY_PATH"] = path_value
    return environment


@contextmanager
def _hidden_runtime_files(paths: Sequence[Path]) -> Iterator[None]:
    moved: list[tuple[Path, Path]] = []
    try:
        for path in paths:
            hidden = path.with_name(path.name + ".facman-conformance-hidden")
            if os.path.lexists(hidden):
                raise ValueError(f"runtime hide target already exists: {hidden.name}")
            path.rename(hidden)
            moved.append((path, hidden))
        yield
    finally:
        for original, hidden in reversed(moved):
            if os.path.lexists(hidden):
                hidden.rename(original)


def _find_facman_cli(build: Path, config: str) -> Path:
    names = {"facman", "facman.exe"}
    candidates = [
        path
        for path in build.rglob("*")
        if path.is_file() and path.name.lower() in names
    ]
    if not candidates:
        raise ValueError("FacMan CLI executable was not produced")
    candidates.sort(
        key=lambda path: (
            0 if config.casefold() in {part.casefold() for part in path.parts} else 1,
            len(path.parts),
            path.as_posix(),
        )
    )
    return candidates[0]


def _ctest_names(
    build: Path,
    config: str,
    runner: CommandRunner,
    label: str,
) -> set[str]:
    result = runner.run(
        f"{label}-ctest-inventory",
        ["ctest", "--test-dir", str(build), "-C", config, "--show-only=json-v1"],
        ROOT,
    )
    parsed = json.loads(result.output)
    return {
        item["name"]
        for item in parsed.get("tests", [])
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }


def _run_facman_semantics(
    label: str,
    build: Path,
    config: str,
    environment: Mapping[str, str],
    roots: Mapping[str, Path],
    runner: CommandRunner,
) -> dict[str, Any]:
    names = _ctest_names(build, config, runner, label)
    missing = sorted(set(STABLE_CTESTS) - names)
    if missing:
        raise ValueError(f"stable CTest subset is missing: {', '.join(missing)}")
    pattern = "^(" + "|".join(re.escape(name) for name in STABLE_CTESTS) + ")$"
    runner.run(
        f"{label}-ctest",
        [
            "ctest",
            "--test-dir",
            str(build),
            "-C",
            config,
            "--output-on-failure",
            "--no-tests=error",
            "-R",
            pattern,
        ],
        ROOT,
        environment=environment,
    )
    cli = _find_facman_cli(build, config)
    comparison_roots = dict(roots)
    comparison_roots["facman-mode-build"] = build
    probes: dict[str, Any] = {}
    for name, arguments in READ_ONLY_CLI_PROBES:
        result = runner.run(
            f"{label}-{name}",
            [str(cli), *arguments],
            ROOT,
            environment=environment,
        )
        parsed = json.loads(result.output)
        probes[name] = normalize_semantic_value(parsed, comparison_roots)
    semantics = {
        "ctest": {name: "pass" for name in STABLE_CTESTS},
        "read_only_cli": probes,
    }
    assert_path_independent_json(semantics)
    return semantics


def _build_facman_mode(
    label: str,
    provider_mode: str,
    facman_root: Path,
    work_dir: Path,
    candidate_lock: Path,
    sources: Mapping[str, ProviderSource],
    cmake: str,
    config: str,
    generator_platform: str | None,
    runner: CommandRunner,
    *,
    prefixes: Mapping[str, Path] | None = None,
    identities: Mapping[str, Path] | None = None,
    environment: Mapping[str, str] | None = None,
) -> tuple[Path, dict[str, Any]]:
    build = work_dir / "facman-build" / label
    command = _facman_configure_command(
        facman_root,
        build,
        candidate_lock,
        provider_mode,
        cmake,
        config,
        generator_platform,
        sources,
        prefixes,
        identities,
    )
    runner.run(f"facman-{label}-configure", command, facman_root)
    runner.run(
        f"facman-{label}-build",
        [
            cmake,
            "--build",
            str(build),
            "--config",
            config,
            "--parallel",
            "--target",
            "facman_cli",
            *STABLE_CTESTS,
        ],
        facman_root,
    )
    semantic_roots = {
        "facman-source": facman_root,
        "conformance-work": work_dir,
        "ulk-source": sources["universal_launcher"].root,
        "usk-source": sources["universal_setup"].root,
    }
    semantics = _run_facman_semantics(
        label,
        build,
        config,
        environment or {},
        semantic_roots,
        runner,
    )
    return build, semantics


def _write_negative_identities(
    prefixes: Mapping[str, Path],
    ulk: Mapping[str, Any],
    usk: Mapping[str, Any],
) -> tuple[Path, Path]:
    specs = {spec.provider_id: spec for spec in PROVIDERS}
    ulk_path = prefixes["universal_launcher"] / _identity_relative_path(
        specs["universal_launcher"], "installed_static"
    )
    usk_path = prefixes["universal_setup"] / _identity_relative_path(
        specs["universal_setup"], "installed_static"
    )
    ulk_path.parent.mkdir(parents=True, exist_ok=True)
    usk_path.parent.mkdir(parents=True, exist_ok=True)
    # Negative controls intentionally may violate the path-independent law.
    ulk_path.write_text(
        json.dumps(ulk, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    usk_path.write_text(
        json.dumps(usk, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return ulk_path, usk_path


def run_identity_negative_controls(
    facman_root: Path,
    work_dir: Path,
    candidate_lock: Path,
    sources: Mapping[str, ProviderSource],
    prefixes: Mapping[str, Path],
    identities: Mapping[str, dict[str, Any]],
    cmake: str,
    config: str,
    generator_platform: str | None,
    runner: CommandRunner,
) -> dict[str, str]:
    results: dict[str, str] = {}
    for name, ulk, usk in negative_identity_variants(
        identities["universal_launcher"], identities["universal_setup"]
    ):
        control_prefixes: dict[str, Path] = {}
        for provider_id, prefix in prefixes.items():
            copied = work_dir / "negative-sdk" / name / provider_id
            shutil.copytree(prefix, copied)
            control_prefixes[provider_id] = copied
        ulk_path, usk_path = _write_negative_identities(control_prefixes, ulk, usk)
        build = work_dir / "negative-build" / name
        command = _facman_configure_command(
            facman_root,
            build,
            candidate_lock,
            "installed_static",
            cmake,
            config,
            generator_platform,
            sources,
            control_prefixes,
            {
                "universal_launcher": ulk_path,
                "universal_setup": usk_path,
            },
        )
        runner.run(f"negative-{name}", command, facman_root, expect_failure=True)
        results[name] = "refused"
    return results


def run_partial_sdk_control(
    facman_root: Path,
    work_dir: Path,
    candidate_lock: Path,
    sources: Mapping[str, ProviderSource],
    prefixes: Mapping[str, Path],
    identity_paths: Mapping[str, Path],
    cmake: str,
    config: str,
    generator_platform: str | None,
    runner: CommandRunner,
) -> str:
    control_prefixes: dict[str, Path] = {}
    for provider_id, prefix in prefixes.items():
        copied = work_dir / "negative-sdk" / "partial-sdk-tree" / provider_id
        shutil.copytree(prefix, copied)
        control_prefixes[provider_id] = copied
    partial = control_prefixes["universal_launcher"]
    config_files = list(partial.rglob("UniversalLauncherConfig.cmake"))
    if len(config_files) != 1:
        raise ValueError("could not identify the installed ULK package config")
    config_files[0].unlink()
    control_identity_paths = {
        provider_id: control_prefixes[provider_id]
        / identity_paths[provider_id].relative_to(prefixes[provider_id])
        for provider_id in prefixes
    }
    command = _facman_configure_command(
        facman_root,
        work_dir / "negative-build" / "partial-sdk",
        candidate_lock,
        "installed_static",
        cmake,
        config,
        generator_platform,
        sources,
        control_prefixes,
        control_identity_paths,
    )
    runner.run("negative-partial-sdk", command, facman_root, expect_failure=True)
    return "refused"


def run_stale_relocation_metadata_control(
    facman_root: Path,
    work_dir: Path,
    candidate_lock: Path,
    sources: Mapping[str, ProviderSource],
    prefixes: Mapping[str, Path],
    identity_paths: Mapping[str, Path],
    cmake: str,
    config: str,
    generator_platform: str | None,
    runner: CommandRunner,
) -> str:
    control_prefixes: dict[str, Path] = {}
    for provider_id, prefix in prefixes.items():
        copied = work_dir / "negative-sdk" / "stale-relocation-metadata" / provider_id
        shutil.copytree(prefix, copied)
        control_prefixes[provider_id] = copied
    ulk_prefix = control_prefixes["universal_launcher"]
    metadata_files = list(ulk_prefix.rglob("UniversalLauncherConfig.cmake"))
    if len(metadata_files) != 1:
        raise ValueError("could not identify relocated ULK package metadata")
    metadata = metadata_files[0]
    metadata.write_text(
        metadata.read_text(encoding="utf-8")
        + f'\nset(FACMAN_STALE_PROVIDER_PREFIX "{prefixes["universal_launcher"].as_posix()}")\n',
        encoding="utf-8",
        newline="\n",
    )
    control_identity_paths = {
        provider_id: control_prefixes[provider_id]
        / identity_paths[provider_id].relative_to(prefixes[provider_id])
        for provider_id in prefixes
    }
    command = _facman_configure_command(
        facman_root,
        work_dir / "negative-build" / "stale-relocation-metadata",
        candidate_lock,
        "installed_static",
        cmake,
        config,
        generator_platform,
        sources,
        control_prefixes,
        control_identity_paths,
    )
    result = runner.run(
        "negative-stale-relocation-metadata",
        command,
        facman_root,
        expect_failure=True,
    )
    if not any(
        marker in result.output
        for marker in (
            "package metadata digest does not match its identity",
            "inventory file content disagrees",
            "live install inventory",
        )
    ):
        raise RuntimeError("stale relocation metadata failed for an unintended reason")
    return "refused"


def run_undeclared_runtime_dependency_control(
    prefixes: Mapping[str, Path],
    identities: Mapping[str, Mapping[str, Any]],
    work_dir: Path,
) -> str:
    control_prefixes: dict[str, Path] = {}
    for provider_id, prefix in prefixes.items():
        copied = work_dir / "negative-sdk" / "undeclared-runtime" / provider_id
        shutil.copytree(prefix, copied)
        control_prefixes[provider_id] = copied
    if platform.system() == "Windows":
        relative = Path("bin") / "facman_undeclared_dependency.dll"
    elif platform.system() == "Darwin":
        relative = Path("lib") / "libfacman_undeclared_dependency.dylib"
    else:
        relative = Path("lib") / "libfacman_undeclared_dependency.so"
    injected = control_prefixes["universal_launcher"] / relative
    injected.parent.mkdir(parents=True, exist_ok=True)
    injected.write_bytes(b"undeclared-runtime-negative-control\n")
    try:
        _declared_shared_runtime_files(control_prefixes, identities)
    except ValueError as error:
        if "undeclared runtime artifacts" not in str(error):
            raise
        return "refused"
    raise ValueError("undeclared runtime dependency was accepted")


def _relocate_prefixes(
    prefixes: Mapping[str, Path], work_dir: Path, linkage: str
) -> dict[str, Path]:
    relocated: dict[str, Path] = {}
    for provider_id, prefix in prefixes.items():
        target = work_dir / "relocated" / linkage / provider_id
        shutil.copytree(prefix, target)
        if inventory_identity(prefix) != inventory_identity(target):
            raise ValueError(
                f"{provider_id} {linkage} relocation changed SDK inventory"
            )
        relocated[provider_id] = target
    return relocated


def _copy_private_runtime(
    prefixes: Mapping[str, Path],
    identities: Mapping[str, Mapping[str, Any]],
    work_dir: Path,
) -> tuple[Path, list[Path]]:
    runtime = work_dir / "private-runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    source_files = _declared_shared_runtime_files(prefixes, identities)
    if not source_files:
        raise ValueError(
            "shared provider install produced no private-runtime artifacts"
        )
    names: set[str] = set()
    for source in source_files:
        if source.name in names:
            raise ValueError(f"private-runtime artifact name collision: {source.name}")
        names.add(source.name)
        shutil.copy2(source, runtime / source.name)
    return runtime, source_files


def _markdown(observation: Mapping[str, Any]) -> str:
    modes = observation.get("modes", {})
    negatives = observation.get("negative_controls", {})
    candidate_difference = observation.get(
        "candidate_differs_from_tracked", "not_observed"
    )
    if isinstance(candidate_difference, bool):
        candidate_difference = str(candidate_difference).lower()
    lines = [
        "# Bounded canonical provider-input conformance observation",
        "",
        f"- Result: `{observation.get('result', 'fail')}`",
        f"- Canonical provider inputs: `{str(observation.get('canonical_inputs', False)).lower()}`",
        f"- Full semantic conformance: `{str(observation.get('full_semantic_conformance', False)).lower()}`",
        "- Tracked provider lock mutated: `false`",
        f"- Candidate differs from tracked pins: `{candidate_difference}`",
        "- Candidate adopted: `false`",
        "- Release eligible: `false`",
        "- Factorio execution: `false`",
        "- Setup mutation: `false`",
        "- Signing/publication: `false`",
        "",
        "## Consumption modes",
        "",
    ]
    for name in (
        "source",
        "installed_static",
        "installed_shared",
        "relocated_static",
        "relocated_shared",
        "private_runtime",
    ):
        value = modes.get(name, {})
        lines.append(f"- `{name}`: `{value.get('result', 'not_run')}`")
    lines.extend(["", "## Negative controls", ""])
    for name, result in sorted(negatives.items()):
        lines.append(f"- `{name}`: `{result}`")
    lines.extend(
        [
            "",
            "Semantic equality is bounded to provider self-conformance, the stable",
            "FacMan CTest subset, and read-only CLI inspection. Operation outcomes,",
            "structured refusals, interrupted recovery projections, and the",
            "release-resolution root each remain `pending_not_fabricated`.",
            "Private-runtime closure covers declared provider imported locations",
            "and their same-target symlink aliases; it is not a general OS closure.",
            "",
        ]
    )
    return "\n".join(lines)


def _bounded_success_classification(
    skip_provider_self_conformance: bool,
) -> dict[str, Any]:
    return {
        "result": (
            "bounded_provider_input_development_rehearsal"
            if skip_provider_self_conformance
            else "bounded_provider_input_conformance_pass"
        ),
        "canonical_inputs": True,
        "full_semantic_conformance": False,
    }


def write_observation(output_dir: Path, observation: Mapping[str, Any]) -> None:
    assert_path_independent_json(observation)
    (output_dir / f"{OBSERVATION_STEM}.json").write_text(
        json.dumps(observation, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (output_dir / f"{OBSERVATION_STEM}.md").write_text(
        _markdown(observation),
        encoding="utf-8",
        newline="\n",
    )


def execute(
    facman_root: Path,
    ulk_root: Path,
    usk_root: Path,
    work_dir: Path,
    output_dir: Path,
    *,
    cmake: str = "cmake",
    config: str = "Release",
    generator_platform: str | None = None,
    skip_provider_self_conformance: bool = False,
) -> dict[str, Any]:
    source_roots = [facman_root.resolve(), ulk_root.resolve(), usk_root.resolve()]
    output = _external_directory(output_dir, source_roots, "output-dir")
    work = _external_directory(work_dir, source_roots + [output], "work-dir")
    runner = CommandRunner(output)
    roots_by_id = {
        "universal_launcher": ulk_root.resolve(),
        "universal_setup": usk_root.resolve(),
    }
    sources_list = [
        observe_provider(spec, roots_by_id[spec.provider_id], runner)
        for spec in PROVIDERS
    ]
    sources = {source.spec.provider_id: source for source in sources_list}
    truth_sets, lock_digests = provider_truth_sets(facman_root, sources)
    candidate_differs = {
        provider_id: source.commit for provider_id, source in sources.items()
    } != {
        provider_id: record["pin"]
        for provider_id, record in truth_sets["tracked_consumed"].items()
    }
    candidate_lock = work / "candidate" / "provider-conformance-lock.v1.toml"
    candidate_lock.parent.mkdir(parents=True, exist_ok=True)
    candidate_lock.write_text(
        candidate_lock_text(sources_list, truth_sets["tracked_consumed"]),
        encoding="utf-8",
        newline="\n",
    )
    self_conformance: dict[str, Any] = {}
    if skip_provider_self_conformance:
        self_conformance = {
            provider_id: {"result": "skipped_by_explicit_development_flag"}
            for provider_id in sources
        }
    else:
        for source in sources_list:
            parsed = run_provider_self_conformance(
                source, work, config, generator_platform, runner
            )
            self_conformance[source.spec.provider_id] = normalize_semantic_value(
                parsed, {"conformance-work": work, "provider-source": source.root}
            )

    prefixes_by_linkage: dict[str, dict[str, Path]] = {"static": {}, "shared": {}}
    identities_by_linkage: dict[str, dict[str, dict[str, Any]]] = {
        "static": {},
        "shared": {},
    }
    identity_paths_by_linkage: dict[str, dict[str, Path]] = {"static": {}, "shared": {}}
    evidence_identity_paths_by_linkage: dict[str, dict[str, Path]] = {
        "static": {},
        "shared": {},
    }
    evidence_inventory_paths_by_linkage: dict[str, dict[str, Path]] = {
        "static": {},
        "shared": {},
    }
    toolchains_by_linkage: dict[str, dict[str, Any]] = {}
    metadata_scan_count: dict[str, int] = {}
    for linkage in ("static", "shared"):
        builds: dict[str, Path] = {}
        for source in sources_list:
            prefix, build = install_provider_sdk(
                source,
                linkage,
                work,
                cmake,
                config,
                generator_platform,
                runner,
            )
            prefixes_by_linkage[linkage][source.spec.provider_id] = prefix
            builds[source.spec.provider_id] = build
            metadata_scan_count[f"{source.spec.provider_id}_{linkage}"] = (
                scan_installed_metadata(
                    prefix,
                    [source.root, work, prefix],
                )
            )
        toolchain = cmake_toolchain(cmake, config, builds, runner)
        toolchains_by_linkage[linkage] = toolchain
        for source in sources_list:
            prefix = prefixes_by_linkage[linkage][source.spec.provider_id]
            mode = f"installed_{linkage}"
            inventory_path, _ = create_sdk_inventory_manifest(prefix, source.spec, mode)
            identity = build_provider_identity(source, prefix, mode, toolchain)
            identity_path = prefix / _identity_relative_path(source.spec, mode)
            evidence_stem = (
                f"{source.spec.source_name}.{mode}."
                f"{toolchain['system'].lower()}.{_safe_label(toolchain['processor']).lower()}."
                f"{config.lower()}"
            )
            evidence_identity_path = (
                output / "identities" / f"{evidence_stem}.identity.json"
            )
            evidence_inventory_path = (
                output / "identities" / f"{evidence_stem}.inventory.v1.json"
            )
            write_identity(identity_path, identity)
            write_identity(evidence_identity_path, identity)
            evidence_inventory_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(inventory_path, evidence_inventory_path)
            identities_by_linkage[linkage][source.spec.provider_id] = identity
            identity_paths_by_linkage[linkage][source.spec.provider_id] = identity_path
            evidence_identity_paths_by_linkage[linkage][source.spec.provider_id] = (
                evidence_identity_path
            )
            evidence_inventory_paths_by_linkage[linkage][source.spec.provider_id] = (
                evidence_inventory_path
            )

    if toolchains_by_linkage["static"] != toolchains_by_linkage["shared"]:
        raise ValueError("provider toolchain identity changed between SDK build modes")

    relocated = {
        linkage: _relocate_prefixes(prefixes_by_linkage[linkage], work, linkage)
        for linkage in ("static", "shared")
    }
    relocated_identity_paths = {
        linkage: {
            provider_id: relocated[linkage][provider_id]
            / identity_paths_by_linkage[linkage][provider_id].relative_to(
                prefixes_by_linkage[linkage][provider_id]
            )
            for provider_id in sources
        }
        for linkage in ("static", "shared")
    }

    modes: dict[str, dict[str, Any]] = {}
    _, source_semantics = _build_facman_mode(
        "source",
        "source",
        facman_root,
        work,
        candidate_lock,
        sources,
        cmake,
        config,
        generator_platform,
        runner,
    )
    modes["source"] = {"result": "pass", "semantics": source_semantics}

    installed_builds: dict[str, Path] = {}
    for linkage in ("static", "shared"):
        provider_mode = f"installed_{linkage}"
        runtime_dirs = [
            path
            for prefix in prefixes_by_linkage[linkage].values()
            for path in (prefix / "bin", prefix / "lib", prefix / "lib64")
            if path.is_dir()
        ]
        build, semantics = _build_facman_mode(
            provider_mode,
            provider_mode,
            facman_root,
            work,
            candidate_lock,
            sources,
            cmake,
            config,
            generator_platform,
            runner,
            prefixes=prefixes_by_linkage[linkage],
            identities=identity_paths_by_linkage[linkage],
            environment=_runtime_environment(runtime_dirs),
        )
        installed_builds[linkage] = build
        modes[provider_mode] = {"result": "pass", "semantics": semantics}

        relocated_label = f"relocated_{linkage}"
        relocated_dirs = [
            path
            for prefix in relocated[linkage].values()
            for path in (prefix / "bin", prefix / "lib", prefix / "lib64")
            if path.is_dir()
        ]
        _, relocated_semantics = _build_facman_mode(
            relocated_label,
            provider_mode,
            facman_root,
            work,
            candidate_lock,
            sources,
            cmake,
            config,
            generator_platform,
            runner,
            prefixes=relocated[linkage],
            identities=relocated_identity_paths[linkage],
            environment=_runtime_environment(relocated_dirs),
        )
        modes[relocated_label] = {"result": "pass", "semantics": relocated_semantics}

    private_runtime, original_shared_runtime = _copy_private_runtime(
        relocated["shared"], identities_by_linkage["shared"], work
    )
    private_runtime_records = [
        {
            "name": path.name,
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in sorted(private_runtime.iterdir(), key=lambda item: item.name)
        if path.is_file()
    ]
    private_build = work / "facman-build" / "private_runtime"
    private_command = _facman_configure_command(
        facman_root,
        private_build,
        candidate_lock,
        "installed_shared",
        cmake,
        config,
        generator_platform,
        sources,
        relocated["shared"],
        relocated_identity_paths["shared"],
    )
    runner.run("facman-private-runtime-configure", private_command, facman_root)
    runner.run(
        "facman-private-runtime-build",
        [
            cmake,
            "--build",
            str(private_build),
            "--config",
            config,
            "--parallel",
            "--target",
            "facman_cli",
            *STABLE_CTESTS,
        ],
        facman_root,
    )
    private_env = _runtime_environment([private_runtime])
    semantic_roots = {
        "facman-source": facman_root,
        "conformance-work": work,
        "ulk-source": sources["universal_launcher"].root,
        "usk-source": sources["universal_setup"].root,
    }
    with _hidden_runtime_files(original_shared_runtime):
        private_semantics = _run_facman_semantics(
            "private-runtime",
            private_build,
            config,
            private_env,
            semantic_roots,
            runner,
        )
        cli = _find_facman_cli(private_build, config)
        missing_runtime_env = dict(private_env)
        missing_runtime_env["PATH"] = os.environ.get("PATH", "")
        missing_runtime_env.pop("LD_LIBRARY_PATH", None)
        missing_runtime_env.pop("DYLD_LIBRARY_PATH", None)
        runner.run(
            "negative-missing-shared-runtime",
            [str(cli), "product", "inspect", "--json"],
            facman_root,
            environment=missing_runtime_env,
            expect_failure=True,
        )
    modes["private_runtime"] = {"result": "pass", "semantics": private_semantics}

    semantic_digests = {
        name: sha256_bytes(canonical_json_bytes(value["semantics"]))
        for name, value in modes.items()
    }
    if len(set(semantic_digests.values())) != 1:
        raise ValueError("normalized FacMan semantics differ across provider modes")

    negative_controls = run_identity_negative_controls(
        facman_root,
        work,
        candidate_lock,
        sources,
        prefixes_by_linkage["static"],
        identities_by_linkage["static"],
        cmake,
        config,
        generator_platform,
        runner,
    )
    negative_controls["partial_sdk_tree"] = run_partial_sdk_control(
        facman_root,
        work,
        candidate_lock,
        sources,
        prefixes_by_linkage["static"],
        identity_paths_by_linkage["static"],
        cmake,
        config,
        generator_platform,
        runner,
    )
    negative_controls["stale_relocation_metadata"] = (
        run_stale_relocation_metadata_control(
            facman_root,
            work,
            candidate_lock,
            sources,
            prefixes_by_linkage["static"],
            identity_paths_by_linkage["static"],
            cmake,
            config,
            generator_platform,
            runner,
        )
    )
    negative_controls["undeclared_runtime_dependency"] = (
        run_undeclared_runtime_dependency_control(
            relocated["shared"], identities_by_linkage["shared"], work
        )
    )
    negative_controls["missing_shared_runtime"] = "refused"

    identity_records: dict[str, Any] = {}
    for linkage in ("static", "shared"):
        for provider_id, identity in identities_by_linkage[linkage].items():
            key = f"{provider_id}_installed_{linkage}"
            relative = (
                evidence_identity_paths_by_linkage[linkage][provider_id]
                .relative_to(output)
                .as_posix()
            )
            inventory_relative = (
                evidence_inventory_paths_by_linkage[linkage][provider_id]
                .relative_to(output)
                .as_posix()
            )
            identity_records[key] = {
                "path": relative,
                "sha256": sha256_file(
                    evidence_identity_paths_by_linkage[linkage][provider_id]
                ),
                "package_version": identity["package"]["version"],
                "inventory_manifest": {
                    "path": inventory_relative,
                    "sha256": sha256_file(
                        evidence_inventory_paths_by_linkage[linkage][provider_id]
                    ),
                },
                "install_inventory_sha256": identity["install"]["inventory_sha256"],
                "abi_version": identity["abi"]["version"],
                "abi_manifest_sha256": identity["abi"]["manifest_sha256"],
                "contract_set_id": identity["contracts"]["contract_set_id"],
                "contract_digest": identity["contracts"]["bundle_sha256"],
                "contract_bundle_sha256": identity["contracts"]["bundle_sha256"],
            }

    workspace_lock_path = facman_root / "release" / "index" / "workspace_lock.v1.toml"
    release_provider_lock_path = (
        facman_root / "release" / "index" / "providers.lock.v2.toml"
    )
    if sha256_file(workspace_lock_path) != lock_digests["workspace_lock_sha256"]:
        raise ValueError("tracked workspace lock was mutated during conformance")
    if (
        sha256_file(release_provider_lock_path)
        != lock_digests["release_provider_lock_sha256"]
    ):
        raise ValueError(
            "authored release-provider lock was mutated during conformance"
        )

    observation: dict[str, Any] = {
        "schema": "facman.provider_conformance_observation.v1",
        "observed_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        **_bounded_success_classification(skip_provider_self_conformance),
        "canonical_provider_sources": canonical_provider_source_records(sources),
        "provider_truth_sets": truth_sets,
        "tracked_lock_records": {
            "workspace": {
                "path": "release/index/workspace_lock.v1.toml",
                "sha256": lock_digests["workspace_lock_sha256"],
            },
            "release_provider": {
                "path": "release/index/providers.lock.v2.toml",
                "sha256": lock_digests["release_provider_lock_sha256"],
            },
        },
        "candidate_lock": {
            "token": "<conformance-work>/candidate/provider-conformance-lock.v1.toml",
            "sha256": sha256_file(candidate_lock),
            "conformance_only": True,
            "tracked_lock_mutated": False,
            "candidate_differs_from_tracked": candidate_differs,
            "candidate_not_adopted": True,
            "release_eligible": False,
        },
        "provider_self_conformance": self_conformance,
        "provider_identities": identity_records,
        "provider_toolchains": toolchains_by_linkage,
        "private_runtime_artifacts": private_runtime_records,
        "installed_metadata_files_scanned": metadata_scan_count,
        "modes": modes,
        "normalized_semantic_sha256": next(iter(semantic_digests.values())),
        "semantic_scope": {
            "provider_self_conformance_scope": "bounded_provider_owned_phase",
            "stable_ctest_subset": list(STABLE_CTESTS),
            "read_only_cli_probes": [name for name, _ in READ_ONLY_CLI_PROBES],
            "private_runtime_dependency_scope": (
                "declared_provider_imported_locations_and_symlink_aliases"
            ),
            **PENDING_SEMANTIC_EQUIVALENCE,
        },
        "negative_controls": negative_controls,
        "tracked_lock_mutated": False,
        "candidate_differs_from_tracked": candidate_differs,
        "candidate_not_adopted": True,
        "release_eligible": False,
        "authority": dict(AUTHORITY),
    }
    validate_authority(observation["authority"])
    write_observation(output, observation)
    print(f"provider-input-conformance: bounded pass; evidence: {output}")
    return observation


def _failure_observation(error: Exception, roots: Mapping[str, Path]) -> dict[str, Any]:
    normalized = normalize_semantic_value(
        str(error), roots, field_policies={(): "build_root"}
    )
    return {
        "schema": "facman.provider_conformance_observation.v1",
        "observed_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "result": "bounded_provider_input_conformance_fail",
        "canonical_inputs": False,
        "full_semantic_conformance": False,
        "failure": normalized,
        "tracked_lock_mutated": False,
        "candidate_not_adopted": True,
        "release_eligible": False,
        "authority": dict(AUTHORITY),
        "modes": {},
        "negative_controls": {},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--facman-root", type=Path, default=ROOT)
    parser.add_argument("--ulk-root", type=Path, required=True)
    parser.add_argument("--usk-root", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cmake", default="cmake")
    parser.add_argument("--config", default="Release")
    parser.add_argument("--platform", dest="generator_platform")
    parser.add_argument(
        "--skip-provider-self-conformance",
        action="store_true",
        help="Development-only speed option; the hosted bounded run must not use it.",
    )
    args = parser.parse_args(argv)
    output = args.output_dir.resolve()
    try:
        execute(
            args.facman_root.resolve(),
            args.ulk_root.resolve(),
            args.usk_root.resolve(),
            args.work_dir.resolve(),
            output,
            cmake=args.cmake,
            config=args.config,
            generator_platform=args.generator_platform,
            skip_provider_self_conformance=args.skip_provider_self_conformance,
        )
    except (
        OSError,
        ValueError,
        RuntimeError,
        json.JSONDecodeError,
        tomllib.TOMLDecodeError,
    ) as error:
        roots = {
            "facman-source": args.facman_root,
            "ulk-source": args.ulk_root,
            "usk-source": args.usk_root,
            "conformance-work": args.work_dir,
            "evidence-output": args.output_dir,
        }
        resolved_sources = [
            args.facman_root.resolve(),
            args.ulk_root.resolve(),
            args.usk_root.resolve(),
        ]
        safely_external = all(
            output != source
            and not output.is_relative_to(source)
            and not source.is_relative_to(output)
            for source in resolved_sources
        )
        owned_or_absent = not output.exists() or (output / "logs").is_dir()
        if safely_external and owned_or_absent:
            try:
                output.mkdir(parents=True, exist_ok=True)
                write_observation(output, _failure_observation(error, roots))
            except (OSError, ValueError):
                pass
        print(f"provider-input-conformance: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
