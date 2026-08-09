# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import json
import os
import re
import stat
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .canonical import (
    canonical_bytes,
    digest_bytes,
    digest_value,
    domain_digest_value,
    expand_template,
    normalize_relative_path,
)
from .source_observation import normalize_source_observation, synthetic_source_observation

try:
    import jsonschema
except ModuleNotFoundError:  # pragma: no cover - exercised by the repository dependency check
    jsonschema = None


INPUT_FILES = (
    "version.v2.toml",
    "product.v2.toml",
    "components.v2.toml",
    "targets.v2.toml",
    "artifacts.v2.toml",
    "providers.lock.v2.toml",
    "support.v2.toml",
    "factorio_compatibility.v1.toml",
    "channels.v1.toml",
    "trust.v1.toml",
)
TOOLCHAIN_FILE = "toolchain.lock"
MODEL_SCHEMA = "contracts/schema/release/release_model.v2.schema.json"
RESOLUTION_RECORD_FILES = {
    "composition": "resolved-composition.v1.json",
    "components": "resolved-components.v1.json",
    "paths": "resolved-paths.v1.json",
    "entrypoints": "resolved-entrypoints.v1.json",
    "authority": "resolved-authority.v1.json",
    "compatibility": "resolved-compatibility.v1.json",
    "package_plan": "resolved-package-plan.v1.json",
    "qualification_plan": "resolved-qualification-plan.v1.json",
    "claims": "resolved-claims.v1.json",
    "trace": "resolution-trace.v1.json",
}
OUTPUT_FILES = {
    **RESOLUTION_RECORD_FILES,
    "resolution_set": "release-resolution-set.v1.json",
    "runtime_metadata": "runtime-release-metadata.v1.json",
}
SCHEMAS = {
    "composition": "facman.release_resolution.v1",
    "components": "facman.resolved_components.v1",
    "paths": "facman.resolved_paths.v1",
    "entrypoints": "facman.resolved_entrypoints.v1",
    "authority": "facman.resolved_authority.v1",
    "compatibility": "facman.resolved_compatibility.v1",
    "package_plan": "facman.resolved_package_plan.v1",
    "qualification_plan": "facman.resolved_qualification_plan.v1",
    "claims": "facman.resolved_claims.v1",
    "trace": "facman.resolution_trace.v1",
    "resolution_set": "facman.release_resolution_set.v1",
    "runtime_metadata": "facman.runtime_release_metadata.v1",
}
PATH_CLASSES = {
    "immutable_payload",
    "mutable_product_data",
    "preserved_user_data",
    "cache",
    "journal",
    "receipt",
    "rollback_material",
    "native_package_owned",
    "generated_runtime_state",
    "external_reference",
}
AUTHORITY_CAPABILITIES = {
    "factorio_execution",
    "setup_mutation",
    "network_acquisition",
    "credential_access",
    "self_update",
    "service_installation",
    "system_scope",
    "native_package_invocation",
    "workspace_migration",
}
HEX_40 = re.compile(r"^[0-9a-f]{40}$")
HEX_64 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class CompilerInputs:
    root: Path
    model: dict[str, Any]
    input_hashes: dict[str, str]


class ResolutionFailure(ValueError):
    def __init__(self, diagnostics: Iterable[dict[str, Any]]) -> None:
        ordered = sorted(
            (copy.deepcopy(item) for item in diagnostics),
            key=lambda item: (
                str(item.get("code", "")),
                tuple(str(value) for value in item.get("constraints", [])),
                str(item.get("message", "")),
            ),
        )
        self.diagnostics = ordered
        summary = "; ".join(str(item["message"]) for item in ordered)
        super().__init__(summary or "release resolution failed")


def _read_toml(path: Path) -> tuple[bytes, dict[str, Any]]:
    before = os.lstat(path)
    attributes = getattr(before, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    if stat.S_ISLNK(before.st_mode) or attributes & reparse_flag:
        raise ValueError(f"release input must not be a symbolic link or reparse point: {path}")
    if not stat.S_ISREG(before.st_mode):
        raise ValueError(f"release input must be a regular file: {path}")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    with os.fdopen(descriptor, "rb") as handle:
        opened = os.fstat(handle.fileno())
        raw = handle.read()
        after = os.fstat(handle.fileno())
    current = os.lstat(path)
    identities = {_stat_identity(item) for item in (before, opened, after, current)}
    if len(identities) != 1:
        raise ValueError(f"release input identity changed while reading: {path}")
    value = tomllib.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: TOML root must be a table")
    return raw, value


def _stat_identity(value: os.stat_result) -> tuple[int, int, int, int]:
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns)


def load_inputs(root: Path, repository_root: Path) -> CompilerInputs:
    resolved_root = root.resolve()
    values: dict[str, Any] = {}
    hashes: dict[str, str] = {}
    locations = [(filename, resolved_root / filename) for filename in INPUT_FILES]
    locations.append(("release/toolchain.lock", repository_root / "release" / TOOLCHAIN_FILE))
    for identity, path in locations:
        if not path.is_file():
            raise ValueError(f"release input is missing: {path}")
        raw, value = _read_toml(path)
        values[identity] = value
        hashes[identity] = digest_bytes(raw)
    model = {
        "version": values["version.v2.toml"],
        "product": values["product.v2.toml"],
        "components": values["components.v2.toml"],
        "targets": values["targets.v2.toml"],
        "artifacts": values["artifacts.v2.toml"],
        "providers": values["providers.lock.v2.toml"],
        "support": values["support.v2.toml"],
        "factorio_compatibility": values["factorio_compatibility.v1.toml"],
        "channels": values["channels.v1.toml"],
        "trust": values["trust.v1.toml"],
        "toolchains": values["release/toolchain.lock"],
    }
    _validate_json_schema(model, repository_root / MODEL_SCHEMA)
    diagnostics = _semantic_model_diagnostics(model)
    if diagnostics:
        raise ResolutionFailure(diagnostics)
    return CompilerInputs(root=resolved_root, model=model, input_hashes=dict(sorted(hashes.items())))


def _validate_json_schema(value: Any, schema_path: Path) -> None:
    if jsonschema is None:
        raise ValueError("jsonschema dependency is unavailable; install tools/requirements-dev.lock")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    problems = sorted(validator.iter_errors(value), key=lambda error: list(error.absolute_path))
    if not problems:
        return
    diagnostics = []
    for error in problems:
        location = ".".join(str(part) for part in error.absolute_path) or "$"
        diagnostics.append(
            {
                "code": "input_schema_violation",
                "constraints": [location],
                "message": f"{location}: {error.message}",
            }
        )
    raise ResolutionFailure(diagnostics)


def _rows(model: dict[str, Any], section: str, key: str) -> list[dict[str, Any]]:
    value = model[section].get(key, [])
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _unique_index(
    rows: list[dict[str, Any]],
    label: str,
    diagnostics: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for row in rows:
        identity = str(row.get("id", ""))
        if identity in output:
            diagnostics.append(
                {
                    "code": "duplicate_identity",
                    "constraints": [f"{label}:{identity}"],
                    "message": f"duplicate {label} identity {identity!r}",
                }
            )
        else:
            output[identity] = row
    return output


def _semantic_model_diagnostics(model: dict[str, Any]) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    components = _unique_index(_rows(model, "components", "component"), "component", diagnostics)
    targets = _unique_index(_rows(model, "targets", "target"), "target", diagnostics)
    artifacts = _unique_index(_rows(model, "artifacts", "artifact"), "artifact", diagnostics)
    providers = _unique_index(_rows(model, "providers", "provider"), "provider", diagnostics)
    toolchains = _unique_index(_rows(model, "toolchains", "toolchain"), "toolchain", diagnostics)
    support = _unique_index(_rows(model, "support", "support"), "support", diagnostics)
    channels = _unique_index(_rows(model, "channels", "channel"), "channel", diagnostics)

    product_id = str(model["product"].get("product_id", ""))
    if model["version"].get("product_id") != product_id:
        diagnostics.append(_reference_error("version.product_id", str(model["version"].get("product_id")), product_id))
    default_channel = str(model["product"].get("default_channel", ""))
    if default_channel not in channels:
        diagnostics.append(_missing_reference("product.default_channel", default_channel, "channel"))
    version_revision = str(
        model["version"].get("development_lineage", {}).get(
            "reviewed_base_revision",
            "",
        )
    )
    if not HEX_40.fullmatch(version_revision):
        diagnostics.append(
            _format_error(
                "version.development_lineage.reviewed_base_revision",
                "40 lowercase hexadecimal characters",
            )
        )

    for provider_id, provider in providers.items():
        if not HEX_40.fullmatch(str(provider.get("source_revision", ""))):
            diagnostics.append(_format_error(f"provider:{provider_id}.source_revision", "40 lowercase hexadecimal characters"))
        for field in ("contract_digest", "package_digest"):
            if not HEX_64.fullmatch(str(provider.get(field, ""))):
                diagnostics.append(_format_error(f"provider:{provider_id}.{field}", "64 lowercase hexadecimal characters"))

    sdk_packages = _dicts(model["providers"].get("sdk_package"))
    sdk_keys: set[tuple[str, str, str, str]] = set()
    sdk_by_provider: dict[str, list[dict[str, Any]]] = {
        provider_id: [] for provider_id in providers
    }
    for package in sdk_packages:
        provider_id = str(package.get("provider_id", ""))
        key = (
            provider_id,
            str(package.get("system", "")),
            str(package.get("architecture", "")),
            str(package.get("linkage", "")),
        )
        if key in sdk_keys:
            diagnostics.append(
                _format_error(
                    f"sdk_package:{'/'.join(key)}",
                    "one unique provider/system/architecture/linkage record",
                )
            )
            continue
        sdk_keys.add(key)
        provider = providers.get(provider_id)
        if provider is None:
            diagnostics.append(
                _missing_reference("sdk_package.provider_id", provider_id, "provider")
            )
            continue
        sdk_by_provider[provider_id].append(package)
        expected = {
            "source_revision": provider.get("source_revision"),
            "source_tree": provider.get("source_tree"),
            "package_version": provider.get("package_version"),
            "abi_manifest_sha256": provider.get("abi_manifest_digest"),
            "contract_digest": provider.get("contract_digest"),
            "consumption_mode": f"installed_{package.get('linkage', '')}",
            "authorizing": False,
        }
        for field, value in expected.items():
            if package.get(field) != value:
                diagnostics.append(
                    _format_error(
                        f"sdk_package:{'/'.join(key)}.{field}",
                        "the exact selected provider identity",
                    )
                )
    for provider_id, provider in providers.items():
        expected_digest = domain_digest_value(
            "facman.provider_sdk_package_set.v1",
            sdk_by_provider.get(provider_id, []),
        )
        if provider.get("package_digest") != expected_digest:
            diagnostics.append(
                _format_error(
                    f"provider:{provider_id}.package_digest",
                    "the domain-separated SDK package evidence set",
                )
            )

    path_destinations: list[tuple[str, str, str]] = []
    for component_id, component in components.items():
        for dependency in _strings(component.get("dependencies")):
            if dependency not in components:
                diagnostics.append(_missing_reference(f"component:{component_id}.dependencies", dependency, "component"))
        provider_id = str(component.get("provider", ""))
        if provider_id and provider_id not in providers:
            diagnostics.append(_missing_reference(f"component:{component_id}.provider", provider_id, "provider"))
        for path in _dicts(component.get("path")):
            path_id = str(path.get("id", ""))
            path_class = str(path.get("ownership_class", ""))
            if path_class not in PATH_CLASSES:
                diagnostics.append(_format_error(f"path:{component_id}/{path_id}.ownership_class", "recognized path ownership class"))
            destination = str(path.get("destination", ""))
            path_destinations.append((component_id, path_id, destination))
        unknown_authority = sorted(set(_strings(component.get("authority_capabilities"))) - AUTHORITY_CAPABILITIES)
        if unknown_authority:
            diagnostics.append(
                {
                    "code": "unknown_authority_capability",
                    "constraints": [f"component:{component_id}", *unknown_authority],
                    "message": f"component {component_id!r} uses unknown authority capabilities: {', '.join(unknown_authority)}",
                }
            )

    for target_id, target in targets.items():
        if str(target.get("toolchain", "")) not in toolchains:
            diagnostics.append(_missing_reference(f"target:{target_id}.toolchain", str(target.get("toolchain", "")), "toolchain"))
        if str(target.get("support", "")) not in support:
            diagnostics.append(_missing_reference(f"target:{target_id}.support", str(target.get("support", "")), "support"))
        for component_id in _strings(target.get("root_components")):
            if component_id not in components:
                diagnostics.append(_missing_reference(f"target:{target_id}.root_components", component_id, "component"))
        for artifact_id in _strings(target.get("artifacts")):
            if artifact_id not in artifacts:
                diagnostics.append(_missing_reference(f"target:{target_id}.artifacts", artifact_id, "artifact"))

    for artifact_id, artifact in artifacts.items():
        target_id = str(artifact.get("target_id", ""))
        if target_id not in targets:
            diagnostics.append(_missing_reference(f"artifact:{artifact_id}.target_id", target_id, "target"))
        capabilities = _dicts(artifact.get("capability"))
        capability_ids = [str(item.get("id", "")) for item in capabilities]
        duplicates = sorted({item for item in capability_ids if capability_ids.count(item) > 1})
        if duplicates:
            diagnostics.append(
                {
                    "code": "duplicate_authority_capability",
                    "constraints": [f"artifact:{artifact_id}", *duplicates],
                    "message": f"artifact {artifact_id!r} repeats authority capabilities: {', '.join(duplicates)}",
                }
            )
        unknown = sorted(set(capability_ids) - AUTHORITY_CAPABILITIES)
        if unknown:
            diagnostics.append(
                {
                    "code": "unknown_authority_capability",
                    "constraints": [f"artifact:{artifact_id}", *unknown],
                    "message": f"artifact {artifact_id!r} uses unknown authority capabilities: {', '.join(unknown)}",
                }
            )
    return diagnostics


def _reference_error(field: str, actual: str, expected: str) -> dict[str, Any]:
    return {
        "code": "identity_mismatch",
        "constraints": [field, expected],
        "message": f"{field} is {actual!r}; expected {expected!r}",
    }


def _missing_reference(field: str, value: str, kind: str) -> dict[str, Any]:
    return {
        "code": "missing_reference",
        "constraints": [field, f"{kind}:{value}"],
        "message": f"{field} references unknown {kind} {value!r}",
    }


def _format_error(field: str, expected: str) -> dict[str, Any]:
    return {
        "code": "invalid_identity_format",
        "constraints": [field],
        "message": f"{field} must use {expected}",
    }


def _dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def resolve(
    inputs: CompilerInputs,
    target_id: str,
    source_observation: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    model = inputs.model
    observed_source = normalize_source_observation(
        source_observation or synthetic_source_observation(model),
        model,
    )
    components = {str(row["id"]): row for row in _rows(model, "components", "component")}
    targets = {str(row["id"]): row for row in _rows(model, "targets", "target")}
    artifacts = {str(row["id"]): row for row in _rows(model, "artifacts", "artifact")}
    providers = {str(row["id"]): row for row in _rows(model, "providers", "provider")}
    toolchains = {str(row["id"]): row for row in _rows(model, "toolchains", "toolchain")}
    support_records = {str(row["id"]): row for row in _rows(model, "support", "support")}
    if target_id not in targets:
        raise ResolutionFailure(
            [{
                "code": "unknown_target",
                "constraints": [f"target:{target_id}"],
                "message": f"unknown target {target_id!r}",
            }]
        )
    target = copy.deepcopy(targets[target_id])
    selected, selection_trace = _resolve_component_closure(components, target)
    variables = {str(key): str(value) for key, value in dict(target.get("variables", {})).items()}
    resolved_components = _resolve_components(
        selected,
        target,
        toolchains[str(target["toolchain"])],
        providers,
        inputs,
    )
    resolved_paths = _resolve_paths(selected, variables)
    resolved_entrypoints = _resolve_entrypoints(model, selected, variables)
    selected_artifacts = [copy.deepcopy(artifacts[item]) for item in _strings(target.get("artifacts"))]
    resolved_authority = _resolve_authority(selected, selected_artifacts)
    resolved_package_plan = _resolve_package_plan(selected_artifacts, variables)
    resolved_compatibility = _resolve_compatibility(model, target, support_records[str(target["support"])])
    resolved_qualification = _resolve_qualification(selected, selected_artifacts, target, support_records[str(target["support"])])
    resolved_claims = _resolve_claims(model, target, support_records[str(target["support"])])
    trace = _resolve_trace(components, selected, selection_trace, target)
    base = _common_base(model, target_id)
    outputs: dict[str, dict[str, Any]] = {
        "components": {**base, "components": resolved_components},
        "paths": {**base, "paths": resolved_paths},
        "entrypoints": {**base, "entrypoints": resolved_entrypoints},
        "authority": {**base, **resolved_authority},
        "compatibility": {**base, **resolved_compatibility},
        "package_plan": {**base, "artifacts": resolved_package_plan},
        "qualification_plan": {**base, **resolved_qualification},
        "claims": {**base, "claims": resolved_claims},
        "trace": {**base, "events": trace},
    }
    for key, value in outputs.items():
        value["schema"] = SCHEMAS[key]
    graph_core = {
        "canonicalization": "facman.canonical_json.v1",
        "input_hashes": inputs.input_hashes,
        "outputs": outputs,
        "providers": [copy.deepcopy(providers[key]) for key in sorted(providers)],
        "target": target,
        "toolchain": copy.deepcopy(toolchains[str(target["toolchain"])]),
        "source_observation": observed_source,
    }
    resolution_digest = digest_value(graph_core)
    composition = {
        **base,
        "schema": SCHEMAS["composition"],
        "canonicalization": "facman.canonical_json.v1",
        "resolution_digest": resolution_digest,
        "product": {
            "id": str(model["product"]["product_id"]),
            "name": str(model["product"]["product_name"]),
            "version": str(model["version"]["canonical_version"]),
            "source_repository": str(model["product"]["source_repository"]),
            "reviewed_base_revision": str(
                model["version"]["development_lineage"]["reviewed_base_revision"]
            ),
            "implementation_revision": str(observed_source["commit"]),
            "build_tree": str(observed_source["tree"]),
            "dirty": bool(observed_source["dirty"]),
            "source_observation_digest": str(observed_source["observation_digest"]),
        },
        "target": target,
        "toolchain": copy.deepcopy(toolchains[str(target["toolchain"])]),
        "providers": [copy.deepcopy(providers[key]) for key in sorted(providers)],
        "source_observation": copy.deepcopy(observed_source),
        "input_hashes": inputs.input_hashes,
        "graph": {
            "component_count": len(resolved_components),
            "path_count": len(resolved_paths),
            "entrypoint_count": len(resolved_entrypoints),
            "artifact_count": len(resolved_package_plan),
        },
        "output_digests": {
            RESOLUTION_RECORD_FILES[key]: domain_digest_value(SCHEMAS[key], value)
            for key, value in sorted(outputs.items())
        },
    }
    outputs["composition"] = composition
    for value in outputs.values():
        value["resolution_digest"] = resolution_digest
    record_digests = {
        RESOLUTION_RECORD_FILES[key]: domain_digest_value(SCHEMAS[key], outputs[key])
        for key in sorted(RESOLUTION_RECORD_FILES)
    }
    source_summary = {
        "reviewed_base_revision": str(
            model["version"]["development_lineage"]["reviewed_base_revision"]
        ),
        "implementation_revision": str(observed_source["commit"]),
        "build_tree": str(observed_source["tree"]),
        "dirty": bool(observed_source["dirty"]),
        "release_eligible": bool(observed_source["release_eligible"]),
        "providers": [
            {
                "id": str(provider["id"]),
                "commit": str(provider["commit"]),
                "tree": str(provider["tree"]),
                "dirty": bool(provider["dirty"]),
                "observation_digest": str(provider["observation_digest"]),
            }
            for provider in observed_source["providers"]
        ],
    }
    input_set_digest = domain_digest_value(
        "facman.release_input_set.v1",
        {
            "input_hashes": inputs.input_hashes,
            "source_observation_digest": observed_source["observation_digest"],
        },
    )
    resolution_set_core = {
        **base,
        "schema": SCHEMAS["resolution_set"],
        "compiler_contract": "facman.release_compiler.v1",
        "canonicalization": "facman.canonical_json.v1",
        "input_set_digest": input_set_digest,
        "source_observation_digest": str(observed_source["observation_digest"]),
        "source": source_summary,
        "toolchain_observation": {
            "id": str(target["toolchain"]),
            "environment_digest": str(
                toolchains[str(target["toolchain"])]["environment_digest"]
            ),
        },
        "records": record_digests,
    }
    resolution_set = {
        **resolution_set_core,
        "root_digest": domain_digest_value(
            SCHEMAS["resolution_set"],
            resolution_set_core,
        ),
    }
    runtime_core = {
        **base,
        "schema": SCHEMAS["runtime_metadata"],
        "resolution_root_digest": resolution_set["root_digest"],
        "source_observation_digest": str(observed_source["observation_digest"]),
        "release_eligible": bool(observed_source["release_eligible"]),
        "provider_locks": [
            {
                key: provider[key]
                for key in (
                    "id",
                    "repository",
                    "source_revision",
                    "source_tree",
                    "package_version",
                    "package_identity_kind",
                    "package_digest",
                    "abi_version",
                    "abi_manifest_digest",
                    "contract_set_id",
                    "contract_digest",
                    "consumption_mode",
                    "supported_consumption_modes",
                    "maturity",
                    "sdk_adoption",
                )
            }
            for provider in composition["providers"]
        ],
        "entrypoints": copy.deepcopy(outputs["entrypoints"]["entrypoints"]),
        "authority": {
            key: copy.deepcopy(outputs["authority"][key])
            for key in (
                "product_authority_granted",
                "artifacts",
            )
        },
        "compatibility": {
            key: copy.deepcopy(outputs["compatibility"][key])
            for key in ("support", "transitions")
        },
        "claims": copy.deepcopy(outputs["claims"]["claims"]),
        "licence_paths": [
            "licenses/LICENSE",
            "licenses/THIRD_PARTY_NOTICES.md",
        ],
    }
    runtime_metadata = {
        **runtime_core,
        "metadata_digest": domain_digest_value(
            SCHEMAS["runtime_metadata"],
            runtime_core,
        ),
    }
    outputs["resolution_set"] = resolution_set
    outputs["runtime_metadata"] = runtime_metadata
    return {key: outputs[key] for key in OUTPUT_FILES}


def _common_base(model: dict[str, Any], target_id: str) -> dict[str, Any]:
    return {
        "schema": "pending",
        "target_id": target_id,
        "product_id": str(model["product"]["product_id"]),
        "product_version": str(model["version"]["canonical_version"]),
    }


def _resolve_component_closure(
    components: dict[str, dict[str, Any]],
    target: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    selected: dict[str, dict[str, Any]] = {}
    trace: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    capabilities = set(_strings(target.get("capabilities")))
    visiting: list[str] = []

    def visit(component_id: str, requested_by: str) -> None:
        if component_id in selected:
            trace.append({"action": "reuse", "component_id": component_id, "reason": requested_by})
            return
        if component_id in visiting:
            start = visiting.index(component_id)
            cycle = visiting[start:] + [component_id]
            diagnostics.append(
                {
                    "code": "component_cycle",
                    "constraints": [f"component:{item}" for item in cycle],
                    "message": "component dependency cycle: " + " -> ".join(cycle),
                }
            )
            return
        component = components.get(component_id)
        if component is None:
            diagnostics.append(_missing_reference(requested_by, component_id, "component"))
            return
        missing = sorted(set(_strings(component.get("requires_capabilities"))) - capabilities)
        if missing:
            diagnostics.append(
                {
                    "code": "missing_target_capability",
                    "constraints": [f"component:{component_id}", f"target:{target['id']}", *[f"capability:{item}" for item in missing]],
                    "message": f"component {component_id!r} requires target capabilities: {', '.join(missing)}",
                }
            )
            return
        visiting.append(component_id)
        for dependency in sorted(_strings(component.get("dependencies"))):
            visit(dependency, f"component:{component_id}.dependencies")
        visiting.pop()
        selected[component_id] = copy.deepcopy(component)
        trace.append({"action": "select", "component_id": component_id, "reason": requested_by})

    for component_id in sorted(_strings(target.get("root_components"))):
        visit(component_id, f"target:{target['id']}.root_components")
    if diagnostics:
        raise ResolutionFailure(diagnostics)
    return dict(sorted(selected.items())), trace


def _resolve_components(
    selected: dict[str, dict[str, Any]],
    target: dict[str, Any],
    toolchain: dict[str, Any],
    providers: dict[str, dict[str, Any]],
    inputs: CompilerInputs,
) -> list[dict[str, Any]]:
    output = []
    for component_id, component in selected.items():
        provider_id = str(component.get("provider", ""))
        provider = providers.get(provider_id) if provider_id else None
        identity_input = {
            "component": component,
            "input_hashes": inputs.input_hashes,
            "product_reviewed_base_revision": inputs.model["version"][
                "development_lineage"
            ]["reviewed_base_revision"],
            "provider": provider,
            "target": target,
            "toolchain": toolchain,
        }
        output.append(
            {
                "id": component_id,
                "identity": digest_value(identity_input),
                "kind": str(component["kind"]),
                "owner": str(component["owner"]),
                "provider": provider_id or None,
                "dependencies": sorted(_strings(component.get("dependencies"))),
                "build_options": dict(sorted(dict(component.get("build_options", {})).items())),
                "authority_capabilities": sorted(_strings(component.get("authority_capabilities"))),
            }
        )
    return output


def _resolve_paths(
    selected: dict[str, dict[str, Any]],
    variables: dict[str, str],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for component_id, component in selected.items():
        for source_path in _dicts(component.get("path")):
            path_id = str(source_path["id"])
            qualified_id = f"{component_id}/{path_id}"
            if qualified_id in seen_ids:
                diagnostics.append(
                    {
                        "code": "duplicate_path_identity",
                        "constraints": [qualified_id],
                        "message": f"duplicate resolved path identity {qualified_id!r}",
                    }
                )
                continue
            seen_ids.add(qualified_id)
            try:
                destination = normalize_relative_path(
                    expand_template(str(source_path["destination"]), variables, field=f"path:{qualified_id}.destination"),
                    field=f"path:{qualified_id}.destination",
                )
                source = expand_template(str(source_path["source"]), variables, field=f"path:{qualified_id}.source")
            except ValueError as exc:
                diagnostics.append(
                    {
                        "code": "invalid_path",
                        "constraints": [qualified_id],
                        "message": str(exc),
                    }
                )
                continue
            record = {
                "id": qualified_id,
                "component_owner": component_id,
                "source": source,
                "destination": destination,
                "source_kind": str(source_path["source_kind"]),
                "mode": int(source_path["mode"]),
                "ownership_class": str(source_path["ownership_class"]),
                "creation_phase": str(source_path["creation_phase"]),
                "mutation_authority": str(source_path["mutation_authority"]),
                "verify_behavior": str(source_path["verify_behavior"]),
                "repair_behavior": str(source_path["repair_behavior"]),
                "update_behavior": str(source_path["update_behavior"]),
                "rollback_behavior": str(source_path["rollback_behavior"]),
                "uninstall_behavior": str(source_path["uninstall_behavior"]),
                "preservation_behavior": str(source_path["preservation_behavior"]),
            }
            if source_path.get("content_sha256"):
                record["content_sha256"] = str(source_path["content_sha256"])
            output.append(record)
    output.sort(key=lambda item: (str(item["destination"]), str(item["id"])))
    for index, first in enumerate(output):
        first_path = str(first["destination"])
        for second in output[index + 1:]:
            second_path = str(second["destination"])
            if second_path == first_path or second_path.startswith(first_path + "/"):
                diagnostics.append(
                    {
                        "code": "overlapping_path_ownership",
                        "constraints": [str(first["id"]), str(second["id"])],
                        "message": f"resolved paths overlap at {first_path!r} and {second_path!r}",
                    }
                )
    if diagnostics:
        raise ResolutionFailure(diagnostics)
    return output


def _resolve_entrypoints(
    model: dict[str, Any],
    selected: dict[str, dict[str, Any]],
    variables: dict[str, str],
) -> list[dict[str, Any]]:
    output = []
    for entrypoint in _dicts(model["product"].get("entrypoint")):
        component_id = str(entrypoint["component"])
        if component_id not in selected:
            continue
        path = normalize_relative_path(
            expand_template(str(entrypoint["path"]), variables, field=f"entrypoint:{entrypoint['id']}.path"),
            field=f"entrypoint:{entrypoint['id']}.path",
        )
        output.append(
            {
                "id": str(entrypoint["id"]),
                "component": component_id,
                "path": path,
                "intent": str(entrypoint["intent"]),
                "capabilities": sorted(_strings(entrypoint.get("capabilities"))),
            }
        )
    return sorted(output, key=lambda item: str(item["id"]))


def _resolve_authority(
    selected: dict[str, dict[str, Any]],
    artifacts: list[dict[str, Any]],
) -> dict[str, Any]:
    component_capabilities = set()
    for component in selected.values():
        component_capabilities.update(_strings(component.get("authority_capabilities")))
    diagnostics: list[dict[str, Any]] = []
    records = []
    for artifact in artifacts:
        artifact_id = str(artifact["id"])
        ceiling = set(_strings(artifact.get("authority_ceiling")))
        policy = {str(item["id"]): item for item in _dicts(artifact.get("capability"))}
        omitted = sorted(component_capabilities - ceiling)
        if omitted:
            diagnostics.append(
                {
                    "code": "authority_ceiling_exceeded",
                    "constraints": [f"artifact:{artifact_id}", *[f"capability:{item}" for item in omitted]],
                    "message": f"artifact {artifact_id!r} omits payload authority from its ceiling: {', '.join(omitted)}",
                }
            )
        capabilities = []
        for capability_id in sorted(AUTHORITY_CAPABILITIES):
            item = policy.get(capability_id, {})
            present = capability_id in component_capabilities
            declared_present = bool(item.get("present_in_payload", False))
            if declared_present != present:
                diagnostics.append(
                    {
                        "code": "authority_presence_mismatch",
                        "constraints": [f"artifact:{artifact_id}", f"capability:{capability_id}"],
                        "message": f"artifact {artifact_id!r} declares {capability_id!r} present={declared_present}, resolved payload present={present}",
                    }
                )
            enabled = bool(item.get("enabled_by_default", False))
            authorized = bool(item.get("currently_authorized", False))
            if (enabled or authorized) and not present:
                diagnostics.append(
                    {
                        "code": "authority_without_payload",
                        "constraints": [f"artifact:{artifact_id}", f"capability:{capability_id}"],
                        "message": f"artifact {artifact_id!r} enables or authorizes absent capability {capability_id!r}",
                    }
                )
            capabilities.append(
                {
                    "id": capability_id,
                    "present_in_payload": present,
                    "enabled_by_default": enabled,
                    "requires_human_confirmation": bool(item.get("requires_human_confirmation", False)),
                    "requires_credential_or_provider": bool(item.get("requires_credential_or_provider", False)),
                    "currently_authorized": authorized,
                }
            )
        records.append(
            {
                "artifact_id": artifact_id,
                "ceiling": sorted(ceiling),
                "capabilities": capabilities,
            }
        )
    if diagnostics:
        raise ResolutionFailure(diagnostics)
    return {"artifacts": records, "product_authority_granted": False}


def _resolve_package_plan(
    artifacts: list[dict[str, Any]],
    variables: dict[str, str],
) -> list[dict[str, Any]]:
    output = []
    for artifact in artifacts:
        integration = []
        for item in _dicts(artifact.get("integration")):
            integration.append(
                {
                    "path": normalize_relative_path(
                        expand_template(str(item["path"]), variables, field=f"artifact:{artifact['id']}.integration.path"),
                        field=f"artifact:{artifact['id']}.integration.path",
                    ),
                    "kind": str(item["kind"]),
                    "owner": str(item["owner"]),
                    "source": str(item["source"]),
                }
            )
        output.append(
            {
                "id": str(artifact["id"]),
                "adapter": str(artifact["adapter"]),
                "format": str(artifact["format"]),
                "filename": expand_template(str(artifact["filename"]), variables, field=f"artifact:{artifact['id']}.filename"),
                "integration_overlay": sorted(integration, key=lambda item: str(item["path"])),
                "payload_changes_permitted": False,
                "required_verification": sorted(_strings(artifact.get("required_verification"))),
            }
        )
    return output


def _resolve_compatibility(
    model: dict[str, Any],
    target: dict[str, Any],
    support: dict[str, Any],
) -> dict[str, Any]:
    target_id = str(target["id"])
    transitions = []
    for transition in _rows(model, "factorio_compatibility", "transition"):
        target_ids = _strings(transition.get("target_ids"))
        if target_id not in target_ids:
            continue
        transitions.append(copy.deepcopy(transition))
    return {
        "support": {
            "id": str(support["id"]),
            "status": str(support["status"]),
            "minimum_host": str(target["minimum_host"]),
            "release_authorized": bool(support["release_authorized"]),
        },
        "transitions": sorted(transitions, key=lambda item: str(item["id"])),
    }


def _resolve_qualification(
    selected: dict[str, dict[str, Any]],
    artifacts: list[dict[str, Any]],
    target: dict[str, Any],
    support: dict[str, Any],
) -> dict[str, Any]:
    tests = set(_strings(target.get("required_tests")))
    tests.update(_strings(support.get("required_tests")))
    for component in selected.values():
        tests.update(_strings(component.get("qualification")))
    for artifact in artifacts:
        tests.update(_strings(artifact.get("required_verification")))
    return {
        "environment": str(target["qualification_environment"]),
        "obligations": sorted(tests),
        "evidence": sorted(_strings(support.get("qualification_evidence"))),
        "qualified": bool(support.get("release_authorized", False)),
    }


def _resolve_claims(
    model: dict[str, Any],
    target: dict[str, Any],
    support: dict[str, Any],
) -> list[dict[str, Any]]:
    supported_claims = set(_strings(support.get("claims")))
    output = []
    for claim in _dicts(model["product"].get("claim")):
        claim_id = str(claim["id"])
        if claim_id not in supported_claims:
            continue
        output.append(
            {
                "id": claim_id,
                "statement": str(claim["statement"]),
                "support_class": str(claim["support_class"]),
                "required_evidence": sorted(_strings(claim.get("required_evidence"))),
                "established": bool(support.get("release_authorized", False)),
                "target_id": str(target["id"]),
            }
        )
    return sorted(output, key=lambda item: str(item["id"]))


def _resolve_trace(
    components: dict[str, dict[str, Any]],
    selected: dict[str, dict[str, Any]],
    selection_trace: list[dict[str, Any]],
    target: dict[str, Any],
) -> list[dict[str, Any]]:
    output = list(selection_trace)
    for component_id in sorted(set(components) - set(selected)):
        output.append(
            {
                "action": "exclude",
                "component_id": component_id,
                "reason": f"not reachable from target:{target['id']}.root_components",
            }
        )
    return output


def explain(outputs: dict[str, dict[str, Any]], component_id: str | None = None) -> dict[str, Any]:
    events = outputs["trace"]["events"]
    if component_id is not None:
        events = [event for event in events if event.get("component_id") == component_id]
    return {
        "schema": "facman.release_explanation.v1",
        "resolution_digest": outputs["composition"]["resolution_digest"],
        "target_id": outputs["composition"]["target_id"],
        "component_id": component_id,
        "events": events,
    }


def diff_resolutions(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    left_paths = _identity_map(left, "paths", "id")
    right_paths = _identity_map(right, "paths", "id")
    left_components = _identity_map(left, "components", "id")
    right_components = _identity_map(right, "components", "id")
    return {
        "schema": "facman.release_resolution_diff.v1",
        "left_digest": str(left.get("resolution_digest", "")),
        "right_digest": str(right.get("resolution_digest", "")),
        "components": _map_diff(left_components, right_components),
        "paths": _map_diff(left_paths, right_paths),
        "changed": canonical_bytes(left) != canonical_bytes(right),
    }


def _identity_map(value: dict[str, Any], key: str, identity: str) -> dict[str, dict[str, Any]]:
    rows = value.get(key, [])
    if not isinstance(rows, list):
        return {}
    return {str(item[identity]): item for item in rows if isinstance(item, dict) and identity in item}


def _map_diff(left: dict[str, dict[str, Any]], right: dict[str, dict[str, Any]]) -> dict[str, Any]:
    left_ids = set(left)
    right_ids = set(right)
    return {
        "added": sorted(right_ids - left_ids),
        "removed": sorted(left_ids - right_ids),
        "changed": sorted(identity for identity in left_ids & right_ids if canonical_bytes(left[identity]) != canonical_bytes(right[identity])),
    }
