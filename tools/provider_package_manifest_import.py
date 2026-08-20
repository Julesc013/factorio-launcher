# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Import installed provider-package truth into FacMan release inputs.

The importer is deliberately provider-neutral.  A reviewed policy supplies the
provider-specific ABI, state-format and inventory expectations; installed
package manifests supply the bytes and source identity.  Projection happens
only after every package and the current tracked release surfaces are coherent.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.release_compiler.canonical import domain_digest_value  # noqa: E402

IMPORT_SCHEMA = "facman.provider_package_import.v1"
POLICY_SCHEMA = "facman.provider_package_import_policy.v1"
PACKAGE_SET_DOMAIN = "facman.provider_sdk_package_set.v1"
HEX_40 = re.compile(r"^[0-9a-f]{40}$")
HEX_64 = re.compile(r"^[0-9a-f]{64}$")
FORMAT_ID = re.compile(r"^[a-z][a-z0-9_]*$")
MANIFEST_LIMIT = 4 * 1024 * 1024
SCHEMA_LIMIT = 512 * 1024
EXPECTED_PROFILES = {
    (system, linkage)
    for system in ("linux", "macos", "windows")
    for linkage in ("static", "shared")
}
INDEX_FILENAMES = (
    "workspace_lock.v1.toml",
    "dependency_lock.v1.toml",
    "providers.lock.v2.toml",
    "build_manifest.v1.toml",
    "sbom.components.v1.json",
)
TRANSACTION_DIRECTORY = ".provider-package-import-transaction.v1"
TRANSACTION_SCHEMA = "facman.provider_package_import_transaction.v1"


class ImportFailure(RuntimeError):
    """A provider package is not admissible as tracked release truth."""


@dataclass(frozen=True)
class ImportPolicy:
    provider_id: str
    manifest_provider_id: str
    manifest_schema: str
    repository: str
    source_ref: str
    package_version: str
    abi_major: int
    abi_minor: int
    abi_manifest_sha256: str
    state_formats: dict[str, dict[str, Any]]
    artifacts_sha256: dict[str, str]
    contracts_sha256: str
    contract_set: tuple[tuple[str, int, str], ...]
    contract_set_sha256: str
    public_headers_sha256: str
    configuration: str
    architecture: str
    licence: str
    required_targets: dict[str, tuple[str, ...]]

    @property
    def abi_version(self) -> str:
        return f"{self.abi_major}.{self.abi_minor}"

    @classmethod
    def load(cls, path: Path) -> "ImportPolicy":
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise ImportFailure(
                f"provider import policy is unreadable: {error}"
            ) from error
        if not isinstance(value, dict) or value.get("schema") != POLICY_SCHEMA:
            raise ImportFailure("provider import policy schema is unsupported")
        abi = _mapping(value, "abi")
        state_formats = _state_formats(value.get("state_formats"), "state_formats")
        inventory = _mapping(value, "inventory")
        targets = _mapping(value, "required_targets")
        static_targets = _string_tuple(targets.get("static"), "required_targets.static")
        shared_targets = _string_tuple(targets.get("shared"), "required_targets.shared")
        artifact_digests = inventory.get("artifacts_sha256")
        if not isinstance(artifact_digests, dict):
            raise ImportFailure(
                "provider input is missing per-profile inventory.artifacts_sha256"
            )
        policy = cls(
            provider_id=_string(value, "provider_id"),
            manifest_provider_id=_string(value, "manifest_provider_id"),
            manifest_schema=_string(value, "manifest_schema"),
            repository=_string(value, "repository"),
            source_ref=_string(value, "source_ref"),
            package_version=_string(value, "package_version"),
            abi_major=_integer(abi, "major"),
            abi_minor=_integer(abi, "minor"),
            abi_manifest_sha256=_string(abi, "manifest_sha256"),
            state_formats=state_formats,
            artifacts_sha256={
                str(key): str(digest) for key, digest in artifact_digests.items()
            },
            contracts_sha256=_string(inventory, "contracts_sha256"),
            contract_set=_inventory_entries(
                inventory.get("contract_set"), "inventory.contract_set"
            ),
            contract_set_sha256=_string(inventory, "contract_set_sha256"),
            public_headers_sha256=_string(inventory, "public_headers_sha256"),
            configuration=_string(value, "configuration"),
            architecture=_normalized_architecture(_string(value, "architecture")),
            licence=_string(value, "licence"),
            required_targets={
                "static": static_targets,
                "shared": shared_targets,
            },
        )
        if set(policy.artifacts_sha256) != {
            f"{system}/{linkage}" for system, linkage in EXPECTED_PROFILES
        }:
            raise ImportFailure(
                "policy artifact inventory must be exactly three systems by two linkages"
            )
        for profile, digest in policy.artifacts_sha256.items():
            if not HEX_64.fullmatch(digest):
                raise ImportFailure(
                    f"policy artifact inventory digest for {profile} is not SHA-256"
                )
        for label, digest in (
            ("ABI manifest", policy.abi_manifest_sha256),
            ("contract inventory", policy.contracts_sha256),
            ("selected contract set", policy.contract_set_sha256),
            ("public-header inventory", policy.public_headers_sha256),
        ):
            if not HEX_64.fullmatch(digest):
                raise ImportFailure(f"policy {label} digest is not SHA-256")
        if sha256_bytes(canonical_json_bytes(_inventory_objects(policy.contract_set))) != (
            policy.contract_set_sha256
        ):
            raise ImportFailure("policy selected contract-set digest is invalid")
        if policy.source_ref != "refs/heads/main":
            raise ImportFailure("stable provider policy must bind refs/heads/main")
        return policy


@dataclass(frozen=True)
class AcceptedPackage:
    path: Path
    root: Path
    data: dict[str, Any]
    system: str
    linkage: str
    manifest_sha256: str

    @property
    def state_formats(self) -> dict[str, dict[str, Any]]:
        provider = _mapping(self.data, "provider")
        return _normalized_provider_state_formats(provider)


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        + "\n"
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _mapping(value: dict[str, Any], key: str) -> dict[str, Any]:
    item = value.get(key)
    if not isinstance(item, dict):
        raise ImportFailure(f"provider input is missing object {key}")
    return item


def _string(value: dict[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item:
        raise ImportFailure(f"provider input is missing string {key}")
    return item


def _integer(value: dict[str, Any], key: str) -> int:
    item = value.get(key)
    if not isinstance(item, int) or isinstance(item, bool):
        raise ImportFailure(f"provider input is missing integer {key}")
    return item


def _integer_list(value: dict[str, Any], key: str) -> list[int]:
    item = value.get(key)
    if not isinstance(item, list) or any(
        not isinstance(entry, int) or isinstance(entry, bool) for entry in item
    ):
        raise ImportFailure(f"provider input is missing integer array {key}")
    return item


def _string_tuple(value: Any, label: str) -> tuple[str, ...]:
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(item, str) or not item for item in value)
    ):
        raise ImportFailure(f"provider input is missing string array {label}")
    return tuple(value)


def _format_identity(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"read_versions", "write_version"}:
        raise ImportFailure(f"provider input has invalid {label} shape")
    read_versions = _integer_list(value, "read_versions")
    write_version = _integer(value, "write_version")
    if (
        not read_versions
        or any(version < 1 for version in read_versions)
        or len(set(read_versions)) != len(read_versions)
        or write_version < 1
    ):
        raise ImportFailure(f"provider input has invalid {label} versions")
    return {
        "read_versions": list(read_versions),
        "write_version": write_version,
    }


def _state_formats(value: Any, label: str) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict) or not value:
        raise ImportFailure(f"provider input is missing object {label}")
    result: dict[str, dict[str, Any]] = {}
    for name, identity in sorted(value.items()):
        if not isinstance(name, str) or not FORMAT_ID.fullmatch(name):
            raise ImportFailure(f"provider input has invalid {label} name")
        result[name] = _format_identity(identity, f"{label}.{name}")
    return result


def _normalized_provider_state_formats(
    provider: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    available = [
        name
        for name in ("journal", "state_format", "state_formats")
        if name in provider
    ]
    if len(available) != 1:
        raise ImportFailure(
            "provider package must expose exactly one recognized state-format shape"
        )
    if available[0] == "journal":
        return {
            "session_journal": _format_identity(
                provider["journal"], "provider.journal"
            )
        }
    if available[0] == "state_format":
        return {
            "state_format": _format_identity(
                provider["state_format"], "provider.state_format"
            )
        }
    return _state_formats(provider["state_formats"], "provider.state_formats")


def _inventory_entries(
    value: Any, label: str
) -> tuple[tuple[str, int, str], ...]:
    if not isinstance(value, list) or not value:
        raise ImportFailure(f"provider input is missing inventory array {label}")
    entries: list[tuple[str, int, str]] = []
    for item in value:
        if not isinstance(item, dict) or set(item) != {"path", "size", "sha256"}:
            raise ImportFailure(f"provider input has invalid inventory entry in {label}")
        path = _string(item, "path")
        size = _integer(item, "size")
        digest = _string(item, "sha256")
        if size < 0 or not HEX_64.fullmatch(digest):
            raise ImportFailure(f"provider input has invalid inventory value in {label}")
        entries.append((path, size, digest))
    if len({entry[0] for entry in entries}) != len(entries):
        raise ImportFailure(f"provider input has duplicate inventory path in {label}")
    if entries != sorted(entries, key=lambda entry: entry[0]):
        raise ImportFailure(f"provider input inventory is not path-sorted: {label}")
    return tuple(entries)


def _inventory_objects(
    entries: tuple[tuple[str, int, str], ...]
) -> list[dict[str, Any]]:
    return [
        {"path": path, "sha256": digest, "size": size}
        for path, size, digest in entries
    ]


def _normalized_system(value: str) -> str:
    aliases = {
        "darwin": "macos",
        "linux": "linux",
        "macos": "macos",
        "windows": "windows",
    }
    result = aliases.get(value.casefold())
    if result is None:
        raise ImportFailure(
            f"provider package has unsupported operating system {value!r}"
        )
    return result


def _normalized_architecture(value: str) -> str:
    aliases = {
        "amd64": "x86_64",
        "x64": "x86_64",
        "x86_64": "x86_64",
    }
    result = aliases.get(value.casefold())
    if result is None:
        raise ImportFailure(f"provider package has unsupported architecture {value!r}")
    return result


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON member: {key}")
        result[key] = value
    return result


def _load_json_object(path: Path, label: str, limit: int) -> dict[str, Any]:
    try:
        if path.is_symlink() or not path.is_file():
            raise OSError("not a regular non-link file")
        raw = path.read_bytes()
        if len(raw) > limit:
            raise ValueError(f"exceeds {limit} bytes")
        value = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_pairs
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        raise ImportFailure(f"{label} is unreadable: {path}: {error}") from error
    if not isinstance(value, dict):
        raise ImportFailure(f"{label} root must be an object: {path}")
    return value


def _load_manifest(path: Path) -> dict[str, Any]:
    return _load_json_object(path, "provider package manifest", MANIFEST_LIMIT)


def _safe_inventory_path(root: Path, relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts or not candidate.parts:
        raise ImportFailure(f"provider artifact path is unsafe: {relative!r}")
    resolved_root = root.resolve()
    resolved = (resolved_root / candidate).resolve()
    if resolved == resolved_root or resolved_root not in resolved.parents:
        raise ImportFailure(f"provider artifact escapes package root: {relative!r}")
    return resolved


def _verify_inventory(
    root: Path, manifest_path: Path, inventory: dict[str, Any]
) -> None:
    artifacts = inventory.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise ImportFailure("provider package artifact inventory is empty")
    if sha256_bytes(canonical_json_bytes(artifacts)) != inventory.get(
        "artifacts_sha256"
    ):
        raise ImportFailure("provider package artifact inventory digest is invalid")
    recorded: set[str] = set()
    for item in artifacts:
        if not isinstance(item, dict):
            raise ImportFailure(
                "provider package artifact inventory contains a non-object"
            )
        relative = _string(item, "path")
        if relative in recorded:
            raise ImportFailure(f"provider package artifact is duplicated: {relative}")
        recorded.add(relative)
        path = _safe_inventory_path(root, relative)
        if not path.is_file() or path.is_symlink():
            raise ImportFailure(
                f"provider package artifact is missing or unsafe: {relative}"
            )
        if path.stat().st_size != _integer(item, "size"):
            raise ImportFailure(f"provider package artifact size changed: {relative}")
        digest = _string(item, "sha256")
        if not HEX_64.fullmatch(digest) or sha256_file(path) != digest:
            raise ImportFailure(f"provider package artifact bytes changed: {relative}")
    manifest_resolved = manifest_path.resolve()
    actual = {
        path.relative_to(root.resolve()).as_posix()
        for path in root.resolve().rglob("*")
        if path.is_file() and path.resolve() != manifest_resolved
    }
    if actual != recorded:
        missing = sorted(recorded - actual)
        changed = sorted(actual - recorded)
        detail = f"missing={missing}, unrecorded={changed}"
        raise ImportFailure(
            f"provider package artifact inventory is not exact: {detail}"
        )


def _verify_named_inventory(
    inventory: dict[str, Any], name: str, expected_digest: str
) -> None:
    entries = inventory.get(name)
    digest = inventory.get(f"{name}_sha256")
    normalized = _inventory_entries(entries, f"manifest.inventories.{name}")
    if sha256_bytes(canonical_json_bytes(entries)) != digest:
        raise ImportFailure(f"provider package {name} inventory digest is invalid")
    if digest != expected_digest:
        raise ImportFailure(f"provider package {name} inventory differs from policy")
    artifacts = _inventory_entries(
        inventory.get("artifacts"), "manifest.inventories.artifacts"
    )
    if not set(normalized).issubset(set(artifacts)):
        raise ImportFailure(f"provider package {name} inventory is not an artifact subset")


def _verify_selected_contract_set(
    inventory: dict[str, Any], policy: ImportPolicy
) -> None:
    contracts = set(
        _inventory_entries(
            inventory.get("contracts"), "manifest.inventories.contracts"
        )
    )
    if not set(policy.contract_set).issubset(contracts):
        raise ImportFailure("provider selected contract set differs from policy")


def _validate_provider_native_schema(
    data: dict[str, Any], package_root: Path, inventory: dict[str, Any]
) -> None:
    contracts = inventory.get("contracts")
    if not isinstance(contracts, list):
        raise ImportFailure("provider package contracts inventory is absent")
    candidates = [
        item
        for item in contracts
        if isinstance(item, dict)
        and isinstance(item.get("path"), str)
        and item["path"].endswith("/provider_package_manifest.v1.schema.json")
    ]
    if len(candidates) != 1:
        raise ImportFailure(
            "provider package must contain exactly one native manifest schema"
        )
    schema_path = _safe_inventory_path(package_root, candidates[0]["path"])
    schema = _load_json_object(
        schema_path, "provider-native manifest schema", SCHEMA_LIMIT
    )
    if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        raise ImportFailure("provider-native manifest schema draft is unsupported")
    try:
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.Draft202012Validator(schema).validate(data)
    except jsonschema.SchemaError as error:
        raise ImportFailure(
            f"provider-native manifest schema is invalid: {error.message}"
        ) from error
    except jsonschema.ValidationError as error:
        location = ".".join(str(item) for item in error.absolute_path) or "<root>"
        raise ImportFailure(
            f"provider-native schema rejected manifest at {location}: {error.message}"
        ) from error


def _git_output(root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=root,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise ImportFailure(f"provider source Git check failed: {detail}")
    return completed.stdout.strip()


def verify_policy_custody(
    path: Path,
    facman_revision: str,
    repository_root: Path = ROOT,
) -> None:
    """Require policy bytes owned by the exact FacMan release context."""
    if not HEX_40.fullmatch(facman_revision):
        raise ImportFailure("FacMan release/compiler context is not a full commit")
    try:
        root = repository_root.resolve(strict=True)
        unresolved = path.absolute()
        resolved = path.resolve(strict=True)
        policy_root = (
            root / "release" / "policies" / "provider-package-import"
        ).resolve(strict=True)
    except OSError as error:
        raise ImportFailure(
            "provider import policy must be a regular file under the FacMan-owned policy root"
        ) from error

    reparse_attribute = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)

    def is_link_or_reparse(candidate: Path) -> bool:
        attributes = getattr(candidate.lstat(), "st_file_attributes", 0)
        return candidate.is_symlink() or bool(attributes & reparse_attribute)

    try:
        if is_link_or_reparse(unresolved) or not resolved.is_file():
            raise ImportFailure("provider import policy path cannot traverse a link")
        cursor = unresolved.parent
        reached_root = False
        while True:
            if is_link_or_reparse(cursor):
                raise ImportFailure("provider import policy path cannot traverse a link")
            if os.path.samefile(cursor, root):
                reached_root = True
                break
            parent = cursor.parent
            if parent == cursor:
                break
            cursor = parent
        if not reached_root or not os.path.samefile(unresolved.parent, policy_root):
            raise ImportFailure(
                "provider import policy must be a regular file under the FacMan-owned policy root"
            )
    except ImportFailure:
        raise
    except OSError as error:
        raise ImportFailure(
            "provider import policy must be a regular file under the FacMan-owned policy root"
        ) from error

    try:
        identity_matches = [
            candidate
            for candidate in policy_root.iterdir()
            if candidate.is_file() and os.path.samefile(candidate, resolved)
        ]
    except OSError as error:
        raise ImportFailure(
            "provider import policy must be a regular file under the FacMan-owned policy root"
        ) from error
    if len(identity_matches) != 1:
        raise ImportFailure(
            "provider import policy must have one canonical name in the FacMan-owned policy root"
        )
    canonical_policy = identity_matches[0]
    relative = (
        Path("release")
        / "policies"
        / "provider-package-import"
        / canonical_policy.name
    ).as_posix()
    commit = _git_output(root, "rev-parse", f"{facman_revision}^{{commit}}")
    if commit != facman_revision:
        raise ImportFailure("FacMan policy context does not resolve to the exact commit")
    try:
        owned_blob = _git_output(root, "rev-parse", f"{facman_revision}:{relative}")
        working_blob = _git_output(
            root, "hash-object", "--path", relative, str(resolved)
        )
    except ImportFailure as error:
        raise ImportFailure(
            "provider import policy bytes are not owned by the exact FacMan release context"
        ) from error
    if owned_blob != working_blob:
        raise ImportFailure(
            "provider import policy bytes are not owned by the exact FacMan release context"
        )


def verify_protected_source(
    source_root: Path,
    protected_ref: str,
    commit: str,
    tree: str,
) -> None:
    if not HEX_40.fullmatch(commit) or not HEX_40.fullmatch(tree):
        raise ImportFailure("provider source commit or tree is not a full Git identity")
    protected_commit = _git_output(
        source_root, "rev-parse", f"{protected_ref}^{{commit}}"
    )
    if protected_commit != commit:
        raise ImportFailure(
            "provider package source is not the exact accepted protected-main tip"
        )
    actual_tree = _git_output(source_root, "rev-parse", f"{commit}^{{tree}}")
    if actual_tree != tree:
        raise ImportFailure("provider package source tree differs from Git")
    _git_output(source_root, "merge-base", "--is-ancestor", commit, protected_ref)


def accept_package(
    manifest_path: Path,
    package_root: Path,
    policy: ImportPolicy,
    source_root: Path,
    protected_ref: str,
) -> AcceptedPackage:
    if protected_ref != policy.source_ref:
        raise ImportFailure("provider protected ref must be the policy-owned stable ref")
    data = _load_manifest(manifest_path)
    if data.get("schema") != policy.manifest_schema:
        raise ImportFailure("provider package manifest schema differs from policy")
    inventory = _mapping(data, "inventories")
    _verify_inventory(package_root, manifest_path, inventory)
    _verify_named_inventory(inventory, "contracts", policy.contracts_sha256)
    _verify_named_inventory(
        inventory,
        "public_headers",
        policy.public_headers_sha256,
    )
    _verify_selected_contract_set(inventory, policy)
    _validate_provider_native_schema(data, package_root, inventory)
    source = _mapping(data, "source")
    provider = _mapping(data, "provider")
    package = _mapping(data, "package")
    qualification = _mapping(data, "qualification")
    licence = _mapping(data, "licence")
    commit = _string(source, "commit")
    tree = _string(source, "tree")
    if _string(source, "repository") != policy.repository:
        raise ImportFailure("provider package repository differs from policy")
    if _string(source, "ref") != policy.source_ref:
        raise ImportFailure("provider package source ref is not stable main")
    verify_protected_source(source_root, protected_ref, commit, tree)
    if _string(provider, "id") != policy.manifest_provider_id:
        raise ImportFailure("provider package id differs from policy")
    if _string(provider, "package_version") != policy.package_version:
        raise ImportFailure("provider package version differs from policy")
    abi = _mapping(provider, "c_abi")
    expected_abi = (policy.abi_major, policy.abi_minor, policy.abi_manifest_sha256)
    actual_abi = (
        _integer(abi, "major"),
        _integer(abi, "minor"),
        _string(abi, "manifest_sha256"),
    )
    if actual_abi != expected_abi:
        raise ImportFailure("provider ABI identity differs from policy")
    state_formats = _normalized_provider_state_formats(provider)
    if set(state_formats) != set(policy.state_formats):
        raise ImportFailure("provider state-format set differs from policy")
    for name, expected in policy.state_formats.items():
        actual = state_formats[name]
        if actual["read_versions"] != expected["read_versions"]:
            raise ImportFailure(
                f"provider {name} state reader versions differ from policy"
            )
        if actual["write_version"] != expected["write_version"]:
            raise ImportFailure(
                f"provider {name} state writer version differs from policy"
            )
    if qualification.get("tck_revision") != commit:
        raise ImportFailure("provider qualification revision differs from source")
    if _string(licence, "expression") != policy.licence:
        raise ImportFailure("provider package licence differs from policy")
    system = _normalized_system(_string(package, "os"))
    architecture = _normalized_architecture(_string(package, "architecture"))
    linkage = _string(package, "linkage").casefold()
    if architecture != policy.architecture:
        raise ImportFailure("provider package architecture differs from policy")
    if _string(package, "configuration") != policy.configuration:
        raise ImportFailure("provider package configuration differs from policy")
    if linkage not in ("static", "shared"):
        raise ImportFailure(
            "provider import requires an exact static or shared package"
        )
    if (
        inventory.get("artifacts_sha256")
        != policy.artifacts_sha256[f"{system}/{linkage}"]
    ):
        raise ImportFailure("provider artifact inventory differs from profile policy")
    targets = set(_string_tuple(package.get("installed_targets"), "installed_targets"))
    if not set(policy.required_targets[linkage]).issubset(targets):
        raise ImportFailure(
            f"provider {linkage} package omits required installed targets"
        )
    return AcceptedPackage(
        path=manifest_path.resolve(),
        root=package_root.resolve(),
        data=data,
        system=system,
        linkage=linkage,
        manifest_sha256=sha256_file(manifest_path),
    )


def accept_matrix(
    manifests: Iterable[Path],
    package_roots: Iterable[Path],
    policy: ImportPolicy,
    source_root: Path,
    protected_ref: str,
) -> list[AcceptedPackage]:
    manifest_list = list(manifests)
    root_list = list(package_roots)
    if len(manifest_list) != len(root_list):
        raise ImportFailure("each provider manifest requires one package root")
    packages = [
        accept_package(path, root, policy, source_root, protected_ref)
        for path, root in zip(manifest_list, root_list, strict=True)
    ]
    keys = {(package.system, package.linkage) for package in packages}
    if len(keys) != len(packages):
        raise ImportFailure(
            "provider package matrix repeats a platform/linkage profile"
        )
    if keys != EXPECTED_PROFILES:
        raise ImportFailure(
            "provider package matrix is not exactly three systems by two linkages"
        )
    common = {
        canonical_json_bytes(
            {
                "source": package.data["source"],
                "provider": package.data["provider"],
                "qualification": package.data["qualification"],
            }
        )
        for package in packages
    }
    if len(common) != 1:
        raise ImportFailure(
            "provider package matrix mixes provider revisions or contracts"
        )
    return sorted(packages, key=lambda item: (item.system, item.linkage))


def _toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ImportFailure(
            f"tracked release input is unreadable: {path}: {error}"
        ) from error


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ImportFailure(
            f"tracked release input is unreadable: {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise ImportFailure(f"tracked release input root must be an object: {path}")
    return value


def load_release_inputs(index_root: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for filename in INDEX_FILENAMES:
        path = index_root / filename
        result[filename] = _json(path) if path.suffix == ".json" else _toml(path)
    return result


def _row(rows: Any, identity: str, label: str) -> dict[str, Any]:
    if not isinstance(rows, list):
        raise ImportFailure(f"tracked {label} records are not an array")
    matches = [
        item for item in rows if isinstance(item, dict) and item.get("id") == identity
    ]
    if len(matches) != 1:
        raise ImportFailure(
            f"tracked {label} must contain exactly one {identity} record"
        )
    return matches[0]


def verify_current_surface_coherence(
    values: dict[str, dict[str, Any]], provider_id: str
) -> None:
    workspace = _row(
        values["workspace_lock.v1.toml"].get("component"), provider_id, "workspace"
    )
    dependency = _row(
        values["dependency_lock.v1.toml"].get("component"), provider_id, "dependency"
    )
    provider = _row(
        values["providers.lock.v2.toml"].get("provider"), provider_id, "provider"
    )
    build = _row(
        values["build_manifest.v1.toml"].get("component"), provider_id, "build"
    )
    sbom = _row(
        values["sbom.components.v1.json"].get("components"), provider_id, "SBOM"
    )
    versions = {
        str(dependency.get("version", "")),
        str(provider.get("package_version", "")),
        str(build.get("version", "")),
        str(sbom.get("version", "")),
    }
    if len(versions) != 1 or "" in versions:
        raise ImportFailure(
            "tracked provider package versions are manually stale or mixed"
        )
    revisions = {
        str(workspace.get("pin", "")),
        str(dependency.get("pin", "")),
        str(provider.get("source_revision", "")),
        str(sbom.get("commit", "")),
    }
    trees = {
        str(workspace.get("tree", "")),
        str(dependency.get("tree", "")),
        str(provider.get("source_tree", "")),
        str(sbom.get("tree", "")),
    }
    if len(revisions) != 1 or "" in revisions or len(trees) != 1 or "" in trees:
        raise ImportFailure(
            "tracked provider source identities are manually stale or mixed"
        )
    cmake_version = provider.get("cmake_package_version")
    if not isinstance(cmake_version, str) or not cmake_version:
        raise ImportFailure(
            "tracked provider omits the generated CMake package version"
        )


def _profile_record(
    package: AcceptedPackage,
    policy: ImportPolicy,
    evidence_revision: str,
) -> dict[str, Any]:
    data = package.data
    source = data["source"]
    provider = data["provider"]
    inventory = data["inventories"]
    metadata = {
        "schema": data["schema"],
        "source": source,
        "provider": provider,
        "package": data["package"],
        "qualification": data["qualification"],
        "licence": data["licence"],
    }
    return {
        "provider_id": policy.provider_id,
        "system": package.system,
        "architecture": policy.architecture,
        "linkage": package.linkage,
        "consumption_mode": f"installed_{package.linkage}",
        "source_revision": source["commit"],
        "source_tree": source["tree"],
        "package_version": provider["package_version"],
        "identity_sha256": package.manifest_sha256,
        "metadata_sha256": sha256_bytes(canonical_json_bytes(metadata)),
        "inventory_manifest_sha256": sha256_bytes(canonical_json_bytes(inventory)),
        "inventory_sha256": inventory["artifacts_sha256"],
        "abi_manifest_sha256": provider["c_abi"]["manifest_sha256"],
        "contract_digest": policy.contract_set_sha256,
        "evidence_facman_revision": evidence_revision,
        "authorizing": False,
    }


def project_release_inputs(
    current: dict[str, dict[str, Any]],
    packages: list[AcceptedPackage],
    policy: ImportPolicy,
    evidence_revision: str,
) -> dict[str, dict[str, Any]]:
    if not HEX_40.fullmatch(evidence_revision):
        raise ImportFailure("FacMan release/compiler context is not a full commit")
    verify_current_surface_coherence(current, policy.provider_id)
    projected = json.loads(json.dumps(current))
    first = packages[0].data
    source = first["source"]
    workspace = _row(
        projected["workspace_lock.v1.toml"]["component"],
        policy.provider_id,
        "workspace",
    )
    dependency = _row(
        projected["dependency_lock.v1.toml"]["component"],
        policy.provider_id,
        "dependency",
    )
    provider_lock = projected["providers.lock.v2.toml"]
    provider = _row(provider_lock["provider"], policy.provider_id, "provider")
    build = _row(
        projected["build_manifest.v1.toml"]["component"],
        policy.provider_id,
        "build",
    )
    sbom = _row(
        projected["sbom.components.v1.json"]["components"],
        policy.provider_id,
        "SBOM",
    )
    prior_revision = provider["source_revision"]
    if prior_revision == source["commit"]:
        prior_revision = provider["prior_source_revision"]
    workspace.update(
        pin=source["commit"],
        tree=source["tree"],
        required_ref=policy.source_ref,
    )
    dependency.update(
        version=policy.package_version,
        abi_version=policy.abi_major,
        abi_contract_version=policy.abi_version,
        pin=source["commit"],
        tree=source["tree"],
    )
    build.update(version=policy.package_version, abi_version=policy.abi_major)
    sbom.update(
        version=policy.package_version,
        commit=source["commit"],
        tree=source["tree"],
    )
    replacement = [
        _profile_record(package, policy, evidence_revision) for package in packages
    ]
    untouched = [
        row
        for row in provider_lock["sdk_package"]
        if row.get("provider_id") != policy.provider_id
    ]
    all_packages = sorted(
        [*untouched, *replacement],
        key=lambda row: (
            str(row.get("system", "")),
            str(row.get("provider_id", "")),
            str(row.get("linkage", "")),
        ),
    )
    provider_lock["sdk_package"] = all_packages
    evidence_revisions = {
        row.get("evidence_facman_revision") for row in all_packages
    }
    if len(evidence_revisions) == 1:
        only_revision = next(iter(evidence_revisions))
        if isinstance(only_revision, str) and HEX_40.fullmatch(only_revision):
            provider_lock["sdk_qualification_evidence_revision"] = only_revision
    provider.update(
        source_revision=source["commit"],
        source_tree=source["tree"],
        package_version=policy.package_version,
        cmake_package_version=policy.package_version,
        abi_version=policy.abi_version,
        abi_manifest_digest=policy.abi_manifest_sha256,
        contract_digest=policy.contract_set_sha256,
        prior_source_revision=prior_revision,
    )
    for provider_row in provider_lock["provider"]:
        rows = [
            row
            for row in all_packages
            if row.get("provider_id") == provider_row.get("id")
        ]
        provider_row["package_digest"] = domain_digest_value(PACKAGE_SET_DOMAIN, rows)
    return projected


def _toml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list) and all(not isinstance(item, dict) for item in value):
        return "[" + ", ".join(_toml_scalar(item) for item in value) + "]"
    raise ImportFailure(f"cannot render tracked TOML value: {value!r}")


def _render_toml_table(
    value: dict[str, Any],
    path: tuple[str, ...],
    header: str | None,
) -> list[str]:
    lines: list[str] = []
    if header is not None:
        lines.append(header)
    for key, item in value.items():
        if isinstance(item, dict) or (
            isinstance(item, list) and item and isinstance(item[0], dict)
        ):
            continue
        lines.append(f"{key} = {_toml_scalar(item)}")
    for key, item in value.items():
        child_path = (*path, key)
        dotted = ".".join(child_path)
        if isinstance(item, dict):
            if lines:
                lines.append("")
            lines.extend(_render_toml_table(item, child_path, f"[{dotted}]"))
        elif isinstance(item, list) and item and isinstance(item[0], dict):
            for row in item:
                if not isinstance(row, dict):
                    raise ImportFailure(f"mixed TOML array at {dotted}")
                if lines:
                    lines.append("")
                lines.extend(_render_toml_table(row, child_path, f"[[{dotted}]]"))
    return lines


def render_toml(value: dict[str, Any]) -> bytes:
    return ("\n".join(_render_toml_table(value, (), None)).rstrip() + "\n").encode(
        "utf-8"
    )


def render_release_inputs(values: dict[str, dict[str, Any]]) -> dict[str, bytes]:
    output: dict[str, bytes] = {}
    for filename in INDEX_FILENAMES:
        value = values[filename]
        output[filename] = (
            json.dumps(value, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"
            if filename.endswith(".json")
            else render_toml(value)
        )
    return output


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_durable(path: Path, value: bytes) -> None:
    staging = path.with_name(f".{path.name}.durable.tmp")
    if staging.exists() or staging.is_symlink():
        raise ImportFailure(f"durable staging path already exists: {staging}")
    try:
        with staging.open("xb") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(staging, path)
        _fsync_directory(path.parent)
    except OSError as error:
        raise ImportFailure(f"durable write failed for {path}: {error}") from error
    finally:
        staging.unlink(missing_ok=True)


def _transaction_root(index_root: Path) -> Path:
    return index_root / TRANSACTION_DIRECTORY


def _transaction_journal(
    index_root: Path,
    state: str,
    completed: list[str],
    originals: dict[str, str],
    replacements: dict[str, str],
) -> bytes:
    return canonical_json_bytes(
        {
            "schema": TRANSACTION_SCHEMA,
            "index_root_sha256": sha256_bytes(
                str(index_root.resolve()).encode("utf-8")
            ),
            "state": state,
            "completed": completed,
            "originals": originals,
            "replacements": replacements,
        }
    )


def _load_transaction(index_root: Path) -> tuple[Path, dict[str, Any]]:
    transaction = _transaction_root(index_root)
    journal_path = transaction / "journal.v1.json"
    if transaction.is_symlink() or not transaction.is_dir() or journal_path.is_symlink():
        raise ImportFailure("provider import recovery transaction is missing or unsafe")
    if not journal_path.is_file() or journal_path.stat().st_size > 65536:
        raise ImportFailure("provider import recovery journal size is invalid")
    try:
        value = json.loads(journal_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ImportFailure(
            f"provider import recovery journal is unreadable: {error}"
        ) from error
    expected = {
        "schema", "index_root_sha256", "state", "completed", "originals",
        "replacements",
    }
    if not isinstance(value, dict) or set(value) != expected:
        raise ImportFailure("provider import recovery journal shape is invalid")
    filenames = set(INDEX_FILENAMES)
    if (
        value.get("schema") != TRANSACTION_SCHEMA
        or value.get("index_root_sha256")
        != sha256_bytes(str(index_root.resolve()).encode("utf-8"))
        or value.get("state") not in {
            "preparing", "prepared", "applying", "rollback_required"
        }
        or not isinstance(value.get("completed"), list)
        or value["completed"] != list(INDEX_FILENAMES[: len(value["completed"])])
        or (
            value["state"] in {"preparing", "prepared", "rollback_required"}
            and value["completed"]
        )
        or (value["state"] == "applying" and not value["completed"])
        or not isinstance(value.get("originals"), dict)
        or not isinstance(value.get("replacements"), dict)
    ):
        raise ImportFailure("provider import recovery journal identity is invalid")
    if value["state"] == "preparing":
        if value["originals"] or value["replacements"]:
            raise ImportFailure("provider import preparation journal is invalid")
    elif (
        set(value["originals"]) != filenames
        or set(value["replacements"]) != filenames
        or any(
            not HEX_64.fullmatch(str(digest))
            for digest in value["originals"].values()
        )
        or any(
            not HEX_64.fullmatch(str(digest))
            for digest in value["replacements"].values()
        )
    ):
        raise ImportFailure("provider import recovery journal digests are invalid")
    return transaction, value


def recover_release_transaction(index_root: Path) -> None:
    """Restore every original projection from a validated retained backup."""
    transaction, journal = _load_transaction(index_root)
    if journal["state"] == "preparing":
        shutil.rmtree(transaction)
        _fsync_directory(index_root)
        return
    backup_root = transaction / "original"
    if backup_root.is_symlink() or not backup_root.is_dir():
        raise ImportFailure("provider import recovery backup root is unsafe")
    if {path.name for path in backup_root.iterdir()} != set(INDEX_FILENAMES):
        raise ImportFailure("provider import recovery backup set is not exact")
    for filename in INDEX_FILENAMES:
        backup = backup_root / filename
        if backup.is_symlink() or not backup.is_file():
            raise ImportFailure(f"provider import recovery backup is missing: {filename}")
        value = backup.read_bytes()
        if sha256_bytes(value) != journal["originals"][filename]:
            raise ImportFailure(f"provider import recovery backup changed: {filename}")
    for filename in INDEX_FILENAMES:
        _write_durable(index_root / filename, (backup_root / filename).read_bytes())
    for filename in INDEX_FILENAMES:
        if sha256_file(index_root / filename) != journal["originals"][filename]:
            raise ImportFailure(f"provider import recovery verification failed: {filename}")
    shutil.rmtree(transaction)
    _fsync_directory(index_root)


def _apply_release_transaction(
    index_root: Path,
    rendered: dict[str, bytes],
    replace_target: Any = os.replace,
    expected_original: dict[str, bytes] | None = None,
) -> None:
    transaction = _transaction_root(index_root)
    if transaction.exists() or transaction.is_symlink():
        raise ImportFailure(
            "provider import recovery is required before another check or apply"
        )
    try:
        transaction.mkdir()
    except FileExistsError as error:
        raise ImportFailure(
            "provider import operation or recovery is already active"
        ) from error
    try:
        _write_durable(
            transaction / "journal.v1.json",
            _transaction_journal(index_root, "preparing", [], {}, {}),
        )
    except Exception:
        shutil.rmtree(transaction, ignore_errors=True)
        _fsync_directory(index_root)
        raise
    original_root = transaction / "original"
    staged_root = transaction / "staged"
    original_root.mkdir()
    staged_root.mkdir()
    try:
        originals: dict[str, str] = {}
        replacements: dict[str, str] = {}
        original_values: dict[str, bytes] = {}
        for filename in INDEX_FILENAMES:
            target = index_root / filename
            if target.is_symlink() or not target.is_file():
                raise ImportFailure(
                    f"tracked release projection is missing or unsafe: {filename}"
                )
            original_values[filename] = target.read_bytes()
            if (
                expected_original is not None
                and original_values[filename] != expected_original[filename]
            ):
                raise ImportFailure(
                    f"tracked release projection changed after projection: {filename}"
                )
            originals[filename] = sha256_bytes(original_values[filename])
            replacements[filename] = sha256_bytes(rendered[filename])
        for filename in INDEX_FILENAMES:
            _write_durable(original_root / filename, original_values[filename])
            _write_durable(staged_root / filename, rendered[filename])
        completed: list[str] = []
        _write_durable(
            transaction / "journal.v1.json",
            _transaction_journal(
                index_root, "prepared", completed, originals, replacements
            ),
        )
    except Exception as error:
        shutil.rmtree(transaction, ignore_errors=True)
        _fsync_directory(index_root)
        if isinstance(error, ImportFailure):
            raise error
        raise ImportFailure(
            f"provider import preparation failed before release inputs changed: {error}"
        ) from error
    try:
        for filename in INDEX_FILENAMES:
            replace_target(staged_root / filename, index_root / filename)
            _fsync_directory(index_root)
            completed.append(filename)
            _write_durable(
                transaction / "journal.v1.json",
                _transaction_journal(
                    index_root, "applying", completed, originals, replacements
                ),
            )
        for filename in INDEX_FILENAMES:
            if sha256_file(index_root / filename) != replacements[filename]:
                raise ImportFailure(
                    f"provider import replacement verification failed: {filename}"
                )
    except Exception as error:
        try:
            _write_durable(
                transaction / "journal.v1.json",
                _transaction_journal(
                    index_root, "rollback_required", [], originals, replacements
                ),
            )
            recover_release_transaction(index_root)
        except Exception as recovery_error:
            raise ImportFailure(
                "provider import apply failed and durable recovery is required: "
                f"apply={error}; recovery={recovery_error}"
            ) from error
        if isinstance(error, ImportFailure):
            raise error
        raise ImportFailure(
            f"provider import apply failed and was rolled back: {error}"
        ) from error
    shutil.rmtree(transaction)
    _fsync_directory(index_root)


def verify_or_apply(
    index_root: Path,
    rendered: dict[str, bytes],
    apply: bool,
    replace_target: Any = os.replace,
    expected_original: dict[str, bytes] | None = None,
) -> None:
    transaction = _transaction_root(index_root)
    if transaction.exists() or transaction.is_symlink():
        raise ImportFailure(
            "provider import recovery is required before another check or apply"
        )
    differences = [
        filename
        for filename, expected in rendered.items()
        if not (index_root / filename).is_file()
        or (index_root / filename).read_bytes() != expected
    ]
    if not apply:
        if differences:
            raise ImportFailure(
                "generated provider release inputs differ: " + ", ".join(differences)
            )
        return
    _apply_release_transaction(
        index_root,
        rendered,
        replace_target,
        expected_original,
    )


def _summary(
    packages: list[AcceptedPackage],
    policy: ImportPolicy,
    evidence_revision: str,
    rendered: dict[str, bytes],
) -> dict[str, Any]:
    source = packages[0].data["source"]
    return {
        "schema": IMPORT_SCHEMA,
        "result": "accepted",
        "provider_id": policy.provider_id,
        "source": source,
        "package_version": policy.package_version,
        "abi_version": policy.abi_version,
        "state_formats": packages[0].state_formats,
        "profiles": [
            {
                "system": package.system,
                "linkage": package.linkage,
                "manifest_sha256": package.manifest_sha256,
            }
            for package in packages
        ],
        "facman_release_context": evidence_revision,
        "generated": {
            filename: sha256_bytes(value)
            for filename, value in sorted(rendered.items())
        },
        "authorizing": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate or verify FacMan provider identity surfaces."
    )
    parser.add_argument("--policy", type=Path)
    parser.add_argument("--manifest", type=Path, action="append")
    parser.add_argument("--package-root", type=Path, action="append")
    parser.add_argument("--provider-source-root", type=Path)
    parser.add_argument("--protected-ref")
    parser.add_argument("--release-index", type=Path, required=True)
    parser.add_argument("--facman-revision")
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument("--check", action="store_true")
    operation.add_argument("--apply", action="store_true")
    operation.add_argument("--recover", action="store_true")
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.recover:
            recover_release_transaction(args.release_index)
            print(json.dumps({
                "schema": TRANSACTION_SCHEMA,
                "result": "recovered",
                "release_index": str(args.release_index.resolve()),
            }, indent=2, sort_keys=True))
            return 0
        required = {
            "--policy": args.policy,
            "--manifest": args.manifest,
            "--package-root": args.package_root,
            "--provider-source-root": args.provider_source_root,
            "--protected-ref": args.protected_ref,
            "--facman-revision": args.facman_revision,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            parser.error("check/apply requires " + ", ".join(missing))
        verify_policy_custody(args.policy, args.facman_revision)
        policy = ImportPolicy.load(args.policy)
        if args.policy.name != f"{policy.provider_id}.v1.json":
            raise ImportFailure(
                "provider import policy filename must match its provider identity"
            )
        packages = accept_matrix(
            args.manifest,
            args.package_root,
            policy,
            args.provider_source_root,
            args.protected_ref,
        )
        current = load_release_inputs(args.release_index)
        projected = project_release_inputs(
            current,
            packages,
            policy,
            args.facman_revision,
        )
        rendered = render_release_inputs(projected)
        verify_or_apply(
            args.release_index,
            rendered,
            args.apply,
            expected_original=render_release_inputs(current),
        )
        summary = _summary(packages, policy, args.facman_revision, rendered)
        encoded = json.dumps(summary, indent=2, sort_keys=True) + "\n"
        if args.evidence:
            args.evidence.parent.mkdir(parents=True, exist_ok=True)
            _write_durable(args.evidence, encoded.encode("utf-8"))
        print(encoded, end="")
        return 0
    except ImportFailure as error:
        print(f"provider-package-import: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
