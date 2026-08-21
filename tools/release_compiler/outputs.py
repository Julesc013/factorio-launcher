# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Any

from .canonical import digest_value, domain_digest_value, pretty_json
from .compiler import OUTPUT_FILES, RESOLUTION_RECORD_FILES, SCHEMAS
from .source_observation import normalize_source_observation

try:
    import jsonschema
except ModuleNotFoundError:  # pragma: no cover - repository dependency validation owns this case
    jsonschema = None


OUTPUT_SCHEMA_FILES = {
    "composition": "resolved_composition.v1.schema.json",
    "components": "resolved_components.v1.schema.json",
    "paths": "resolved_paths.v1.schema.json",
    "entrypoints": "resolved_entrypoints.v1.schema.json",
    "authority": "resolved_authority.v1.schema.json",
    "compatibility": "resolved_compatibility.v1.schema.json",
    "package_plan": "resolved_package_plan.v1.schema.json",
    "qualification_plan": "resolved_qualification_plan.v1.schema.json",
    "claims": "resolved_claims.v1.schema.json",
    "trace": "resolution_trace.v1.schema.json",
    "resolution_set": "release_resolution_set.v1.schema.json",
    "runtime_metadata": "runtime_release_metadata.v1.schema.json",
}
RUNTIME_OUTPUT_KEYS = ("resolution_set", "runtime_metadata")


def write_resolution(output_root: Path, outputs: dict[str, dict[str, Any]]) -> Path:
    destination = Path(os.path.abspath(output_root))
    if destination.exists():
        if _linked(destination):
            raise ValueError(f"resolution output must not be a symbolic link or reparse point: {destination}")
        if not destination.is_dir():
            raise ValueError(f"resolution output exists and is not a directory: {destination}")
        if any(destination.iterdir()):
            raise ValueError(f"resolution output directory must be absent or empty: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".facman-resolution-", dir=destination.parent) as temporary:
        temporary_root = Path(temporary)
        for key, filename in OUTPUT_FILES.items():
            if key not in outputs:
                raise ValueError(f"resolution output is missing logical record {key!r}")
            (temporary_root / filename).write_text(pretty_json(outputs[key]), encoding="utf-8")
        if destination.exists():
            destination.rmdir()
        os.replace(temporary_root, destination)
    return destination


def write_runtime_projection(
    output_root: Path,
    outputs: dict[str, dict[str, Any]],
    repository_root: Path | None = None,
) -> Path:
    validate_resolution(outputs, repository_root)
    destination = Path(os.path.abspath(output_root))
    if destination.exists():
        if _linked(destination):
            raise ValueError(f"runtime metadata output must not be a symbolic link or reparse point: {destination}")
        if not destination.is_dir() or any(destination.iterdir()):
            raise ValueError(f"runtime metadata output directory must be absent or empty: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".facman-runtime-metadata-", dir=destination.parent) as temporary:
        temporary_root = Path(temporary)
        for key in RUNTIME_OUTPUT_KEYS:
            (temporary_root / OUTPUT_FILES[key]).write_text(
                pretty_json(outputs[key]),
                encoding="utf-8",
            )
        if destination.exists():
            destination.rmdir()
        os.replace(temporary_root, destination)
    return destination


def load_runtime_projection(root: Path, repository_root: Path | None = None) -> dict[str, dict[str, Any]]:
    resolved_root = Path(os.path.abspath(root))
    if _linked(resolved_root):
        raise ValueError(f"runtime metadata root must not be a symbolic link or reparse point: {resolved_root}")
    output: dict[str, dict[str, Any]] = {}
    for key in RUNTIME_OUTPUT_KEYS:
        filename = OUTPUT_FILES[key]
        path = resolved_root / filename
        if not path.is_file():
            raise ValueError(f"runtime metadata omits {filename}")
        try:
            value = json.loads(_read_stable(path).decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}: malformed JSON: {exc}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"{path}: runtime metadata record must be an object")
        output[key] = value
    resolution_set = output["resolution_set"]
    root_core = dict(resolution_set)
    root_digest = str(root_core.pop("root_digest", ""))
    if root_digest != domain_digest_value(SCHEMAS["resolution_set"], root_core):
        raise ValueError("runtime resolution-set root digest does not match")
    runtime = output["runtime_metadata"]
    runtime_core = dict(runtime)
    metadata_digest = str(runtime_core.pop("metadata_digest", ""))
    if metadata_digest != domain_digest_value(SCHEMAS["runtime_metadata"], runtime_core):
        raise ValueError("runtime metadata digest does not match")
    if runtime.get("resolution_root_digest") != root_digest:
        raise ValueError("runtime metadata does not bind the embedded resolution root")
    if repository_root is not None:
        if jsonschema is None:
            raise ValueError("jsonschema dependency is unavailable; install tools/requirements-dev.lock")
        schema_root = repository_root / "contracts" / "schema" / "release"
        for key in RUNTIME_OUTPUT_KEYS:
            schema = json.loads((schema_root / OUTPUT_SCHEMA_FILES[key]).read_text(encoding="utf-8"))
            errors = sorted(
                jsonschema.Draft202012Validator(schema).iter_errors(output[key]),
                key=lambda item: list(item.absolute_path),
            )
            if errors:
                raise ValueError(
                    "; ".join(
                        f"{key}.{'.'.join(str(part) for part in error.absolute_path) or '$'}: {error.message}"
                        for error in errors
                    )
                )
    return output


def load_resolution(root: Path) -> dict[str, dict[str, Any]]:
    resolved_root = Path(os.path.abspath(root))
    if _linked(resolved_root):
        raise ValueError(f"resolved graph root must not be a symbolic link or reparse point: {resolved_root}")
    output: dict[str, dict[str, Any]] = {}
    for key, filename in OUTPUT_FILES.items():
        path = resolved_root / filename
        if not path.is_file():
            raise ValueError(f"resolved graph is missing {filename}")
        try:
            value = json.loads(_read_stable(path).decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}: malformed JSON: {exc}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"{path}: resolved record must be an object")
        output[key] = value
    validate_resolution(output)
    return output


def _linked(path: Path) -> bool:
    identity = os.lstat(path)
    attributes = getattr(identity, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return stat.S_ISLNK(identity.st_mode) or bool(attributes & reparse_flag)


def _read_stable(path: Path) -> bytes:
    before = os.lstat(path)
    if _linked(path) or not stat.S_ISREG(before.st_mode):
        raise ValueError(f"resolved graph record must be a regular no-follow file: {path}")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    with os.fdopen(descriptor, "rb") as handle:
        opened = os.fstat(handle.fileno())
        raw = handle.read()
        after = os.fstat(handle.fileno())
    current = os.lstat(path)
    identities = {
        (item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns)
        for item in (before, opened, after, current)
    }
    if len(identities) != 1:
        raise ValueError(f"resolved graph record changed while reading: {path}")
    return raw


def validate_resolution(
    outputs: dict[str, dict[str, Any]],
    repository_root: Path | None = None,
) -> None:
    problems: list[str] = []
    for key in OUTPUT_FILES:
        value = outputs.get(key)
        if not isinstance(value, dict):
            problems.append(f"missing output record {key!r}")
            continue
        if value.get("schema") != SCHEMAS[key]:
            problems.append(f"{key}: expected schema {SCHEMAS[key]!r}")
        for field in ("target_id", "product_id", "product_version"):
            if not isinstance(value.get(field), str) or not value[field]:
                problems.append(f"{key}: missing non-empty {field}")
        if key in RESOLUTION_RECORD_FILES:
            if not isinstance(value.get("resolution_digest"), str) or not value["resolution_digest"]:
                problems.append(f"{key}: missing non-empty resolution_digest")
    if problems:
        raise ValueError("; ".join(problems))

    if repository_root is not None:
        if jsonschema is None:
            raise ValueError("jsonschema dependency is unavailable; install tools/requirements-dev.lock")
        schema_root = repository_root / "contracts" / "schema" / "release"
        for key, filename in OUTPUT_SCHEMA_FILES.items():
            schema = json.loads((schema_root / filename).read_text(encoding="utf-8"))
            for error in sorted(
                jsonschema.Draft202012Validator(schema).iter_errors(outputs[key]),
                key=lambda item: list(item.absolute_path),
            ):
                location = ".".join(str(part) for part in error.absolute_path) or "$"
                problems.append(f"{key}.{location}: {error.message}")

    composition = outputs["composition"]
    resolution_digest = str(composition["resolution_digest"])
    common = {
        field: str(composition[field])
        for field in ("target_id", "product_id", "product_version", "resolution_digest")
    }
    for key in RESOLUTION_RECORD_FILES:
        value = outputs[key]
        for field, expected in common.items():
            if value.get(field) != expected:
                problems.append(f"{key}: {field} does not match resolved composition")

    output_digests = composition.get("output_digests")
    if not isinstance(output_digests, dict):
        problems.append("composition: output_digests must be an object")
        output_digests = {}
    core_outputs: dict[str, dict[str, Any]] = {}
    for key, filename in RESOLUTION_RECORD_FILES.items():
        if key == "composition":
            continue
        record = dict(outputs[key])
        record.pop("resolution_digest", None)
        actual = domain_digest_value(SCHEMAS[key], record)
        if output_digests.get(filename) != actual:
            problems.append(f"{key}: content digest does not match resolved composition")
        core_outputs[key] = record
    graph_core = {
        "canonicalization": composition.get("canonicalization"),
        "input_hashes": composition.get("input_hashes"),
        "outputs": core_outputs,
        "providers": composition.get("providers"),
        "source_observation": composition.get("source_observation"),
        "target": composition.get("target"),
        "toolchain": composition.get("toolchain"),
    }
    if digest_value(graph_core) != resolution_digest:
        problems.append("composition: resolution digest does not match canonical graph core")

    try:
        source_observation = normalize_source_observation(
            composition.get("source_observation", {}),
            {
                "version": {
                    "development_lineage": {
                        "reviewed_base_revision": composition.get("product", {}).get(
                            "reviewed_base_revision",
                            "",
                        )
                    }
                },
                "product": {
                    "source_repository": composition.get("product", {}).get(
                        "source_repository",
                        "",
                    )
                },
                "providers": {"provider": composition.get("providers", [])},
            },
        )
    except ValueError as exc:
        problems.append(f"composition: invalid source observation: {exc}")
        source_observation = {}

    resolution_set = outputs["resolution_set"]
    record_digests = {
        filename: domain_digest_value(SCHEMAS[key], outputs[key])
        for key, filename in sorted(RESOLUTION_RECORD_FILES.items())
    }
    if resolution_set.get("records") != record_digests:
        problems.append("resolution-set: child record digests do not match")
    if resolution_set.get("source_observation_digest") != source_observation.get(
        "observation_digest"
    ):
        problems.append("resolution-set: source observation digest does not match")
    expected_input_set_digest = domain_digest_value(
        "facman.release_input_set.v1",
        {
            "input_hashes": composition.get("input_hashes"),
            "source_observation_digest": source_observation.get("observation_digest"),
        },
    )
    if resolution_set.get("input_set_digest") != expected_input_set_digest:
        problems.append("resolution-set: input set digest does not match")
    resolution_set_core = dict(resolution_set)
    actual_root_digest = str(resolution_set_core.pop("root_digest", ""))
    if actual_root_digest != domain_digest_value(
        SCHEMAS["resolution_set"],
        resolution_set_core,
    ):
        problems.append("resolution-set: root digest does not match")

    runtime_metadata = outputs["runtime_metadata"]
    if runtime_metadata.get("resolution_root_digest") != actual_root_digest:
        problems.append("runtime-metadata: resolution root digest does not match")
    if runtime_metadata.get("source_observation_digest") != source_observation.get(
        "observation_digest"
    ):
        problems.append("runtime-metadata: source observation digest does not match")
    if runtime_metadata.get("release_eligible") is not source_observation.get(
        "release_eligible"
    ):
        problems.append("runtime-metadata: release eligibility differs from source observation")
    runtime_core = dict(runtime_metadata)
    actual_metadata_digest = str(runtime_core.pop("metadata_digest", ""))
    if actual_metadata_digest != domain_digest_value(
        SCHEMAS["runtime_metadata"],
        runtime_core,
    ):
        problems.append("runtime-metadata: metadata digest does not match")
    if problems:
        raise ValueError("; ".join(problems))
