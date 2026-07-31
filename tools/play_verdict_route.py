# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Closed route and qualification bindings for operator-only Play evidence."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping


QUALIFICATION_SCHEMA_V1 = "facman.play_candidate_qualification_binding.v1"
QUALIFICATION_SCHEMA_V2 = "facman.play_candidate_qualification_binding.v2"
QUALIFICATION_SCHEMA_V3 = "facman.play_candidate_qualification_binding.v3"
QUALIFICATION_SCHEMA_V4 = "facman.play_candidate_qualification_binding.v4"
QUALIFICATION_SCHEMA = QUALIFICATION_SCHEMA_V4
CANONICALIZATION = "facman.sorted-json.v1"
LOWERCASE_SHA256 = re.compile(r"^[0-9a-f]{64}$")
LOWERCASE_COMMIT = re.compile(r"^[0-9a-f]{40}$")


class RouteBindingError(RuntimeError):
    pass


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def digest_value(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


@dataclass(frozen=True)
class PlayVerdictRoute:
    route_id: str
    work_unit: str
    preflight_schema: str
    policy_digest: str
    policy_filename: str
    plan_schema: str
    packet_schema: str
    observation_schema: str
    human_observation_schema: str
    observation_provider_revision: str
    isolation_mode: str
    instance_id: str
    operation_prefix: str
    writable_paths: tuple[tuple[str, str], ...]
    protected_ids: frozenset[str]
    qualification_schema: str = QUALIFICATION_SCHEMA_V1
    required_artifacts: frozenset[str] = frozenset(
        {"facman", "candidate_smoke", "verdict_harness", "cmake_cache"}
    )

    def writable_mapping(self) -> Mapping[str, str]:
        return MappingProxyType(dict(self.writable_paths))


HERMETIC_VERDICT03 = PlayVerdictRoute(
    route_id="gate4c-hermetic-verdict03",
    work_unit="FACMAN-HERMETIC-STANDALONE-PLAY-VERDICT-03",
    preflight_schema="factorio.hermetic_play_verdict_preflight.v1",
    policy_digest=(
        "6fde31f26d57e23d67c01dd598cb869a"
        "4914d11711868b46d4f817709455e7a2"
    ),
    policy_filename="hermetic_standalone_play_policy.v1.canonical.json",
    plan_schema="factorio.hermetic_play_candidate_plan.v1",
    packet_schema="factorio.play_candidate_evidence_packet.v1",
    observation_schema="factorio.play_candidate_observation.v1",
    human_observation_schema="factorio.gate4c_human_observation.v1",
    observation_provider_revision="bound-observation-artifact.v1",
    isolation_mode="hermetic",
    instance_id="gate-4c-disposable-2-0-77",
    operation_prefix="gate4c-verdict03-",
    writable_paths=(
        ("instance.config", "{instance}/config"),
        ("instance.locks", "{instance}/locks"),
        ("instance.logs", "{instance}/logs"),
        ("instance.mods", "{instance}/mods"),
        ("instance.saves", "{instance}/saves"),
        ("instance.state", "{instance}/state"),
        ("operation.record", "{workspace}/operations/{operation}"),
        ("operation.temporary", "{workspace}/temporary/{operation}"),
    ),
    protected_ids=frozenset(
        {
            "effects.external_filesystem",
            "effects.external_registry",
            "facman.package",
            "factorio.appdata",
            "factorio.default_user_data",
            "factorio.localappdata",
            "factorio.programdata",
            "factorio.source_material",
            "host.external_unobserved",
            "installation.selected",
            "installation.siblings",
            "instances.other",
            "registry.factorio",
            "registry.factorio_uninstall",
            "registry.steam",
            "steam.cloud_cache",
            "steam.install_roots",
            "steam.userdata",
        }
    ),
)


INSTANCE_ISOLATED_REVALIDATION = PlayVerdictRoute(
    route_id="windows-instance-isolated-revalidation",
    work_unit="FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-REVALIDATION-04",
    preflight_schema="factorio.instance_isolated_play_verdict_preflight.v2",
    policy_digest=(
        "8d8189a9e8fc9ff7e479f7dda1adf0ea"
        "516bed2878046468022b2da8355e2432"
    ),
    policy_filename=(
        "windows_instance_isolated_play_policy.v1.canonical.json"
    ),
    plan_schema="factorio.instance_isolated_play_candidate_plan.v1",
    packet_schema="factorio.instance_isolated_play_candidate_packet.v1",
    observation_schema=(
        "factorio.instance_isolated_play_candidate_observation.v1"
    ),
    human_observation_schema=(
        "factorio.instance_isolated_human_observation.v2"
    ),
    observation_provider_revision="gate4c-etw-file-registry-process.v6",
    isolation_mode="instance_isolated",
    instance_id="instance-isolated-disposable-2-0-77",
    operation_prefix="gate4c-instance-isolated-",
    writable_paths=(
        ("instance.closure", "{instance}"),
        ("operation.record", "{workspace}/operations/{operation}"),
        ("operation.temporary", "{workspace}/temporary/{operation}"),
        (
            "operation.observer_artifacts",
            "{workspace}/temporary/{operation}/observer-artifacts",
        ),
        (
            "operation.candidate_artifacts",
            "{workspace}/temporary/{operation}/candidate-artifacts",
        ),
        (
            "operation.audit_record",
            "{workspace}/operations/{operation}/audit-record",
        ),
        (
            "operation.process_logs",
            "{workspace}/temporary/{operation}/process-logs",
        ),
    ),
    protected_ids=frozenset(
        {
            "installation.selected",
            "installation.siblings",
            "instances.other",
            "factorio.default_user_data",
            "factorio.appdata",
            "factorio.localappdata",
            "factorio.programdata",
            "steam.installation",
            "steam.userdata",
            "facman.package",
            "factorio.source_artifacts",
            "registry.factorio_uninstall",
        }
    ),
    qualification_schema=QUALIFICATION_SCHEMA_V4,
    required_artifacts=frozenset(
        {
            "facman",
            "candidate_smoke",
            "verdict_harness",
            "evidence_probe",
            "cmake_cache",
        }
    ),
)


_ROUTES = MappingProxyType(
    {
        route.route_id: route
        for route in (HERMETIC_VERDICT03, INSTANCE_ISOLATED_REVALIDATION)
    }
)
_WORK_UNITS = MappingProxyType(
    {route.work_unit: route for route in _ROUTES.values()}
)


def route_by_id(route_id: str) -> PlayVerdictRoute:
    try:
        return _ROUTES[route_id]
    except KeyError as exc:
        raise RouteBindingError(f"unsupported Play verdict route: {route_id}") from exc


def route_for_work_unit(work_unit: str) -> PlayVerdictRoute:
    try:
        return _WORK_UNITS[work_unit]
    except KeyError as exc:
        raise RouteBindingError(
            f"unsupported Play verdict WorkUnit: {work_unit}"
        ) from exc


@dataclass(frozen=True)
class SourceComponentBinding:
    revision: str
    required_ref: str


@dataclass(frozen=True)
class ArtifactBinding:
    relative_path: str
    size: int
    sha256: str


@dataclass(frozen=True)
class CandidateQualificationBinding:
    route_id: str
    work_unit: str
    factorio_launcher: SourceComponentBinding
    universal_launcher: SourceComponentBinding
    universal_setup: SourceComponentBinding
    artifacts: tuple[tuple[str, ArtifactBinding], ...]
    factorio_version: str
    factorio_sha256: str
    factorio_signer: str
    instance_id: str
    instance_spec_digest: str
    instance_binding_digest: str
    instance_readiness_digest: str
    qualification_digest: str

    def artifact_mapping(self) -> Mapping[str, ArtifactBinding]:
        return MappingProxyType(dict(self.artifacts))


def _closed_object(
    value: Any,
    keys: set[str],
    context: str,
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise RouteBindingError(f"{context} is not a closed object")
    return value


def _digest(value: Any, context: str) -> str:
    if not isinstance(value, str) or LOWERCASE_SHA256.fullmatch(value) is None:
        raise RouteBindingError(f"{context} is not lowercase SHA-256")
    return value


def _component(value: Any, context: str) -> SourceComponentBinding:
    item = _closed_object(value, {"revision", "required_ref"}, context)
    revision = item["revision"]
    required_ref = item["required_ref"]
    if (
        not isinstance(revision, str)
        or LOWERCASE_COMMIT.fullmatch(revision) is None
        or not isinstance(required_ref, str)
        or not required_ref.startswith("origin/")
    ):
        raise RouteBindingError(f"{context} is malformed")
    return SourceComponentBinding(revision, required_ref)


def load_qualification_binding(
    path: Path,
    route: PlayVerdictRoute,
) -> CandidateQualificationBinding:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RouteBindingError(f"qualification binding is unreadable: {exc}") from exc
    return parse_qualification_binding(value, route)


def parse_qualification_binding(
    value: Any,
    route: PlayVerdictRoute,
) -> CandidateQualificationBinding:
    root = _closed_object(
        value,
        {
            "schema",
            "canonicalization_version",
            "route_id",
            "work_unit",
            "source_binding",
            "artifacts",
            "factorio",
            "instance",
            "qualification_digest",
        },
        "qualification binding",
    )
    claimed = _digest(root["qualification_digest"], "qualification digest")
    core = dict(root)
    core.pop("qualification_digest")
    if (
        root["schema"] != route.qualification_schema
        or root["canonicalization_version"] != CANONICALIZATION
        or root["route_id"] != route.route_id
        or root["work_unit"] != route.work_unit
        or digest_value(core) != claimed
    ):
        raise RouteBindingError("qualification binding identity is invalid")
    source = _closed_object(
        root["source_binding"],
        {"factorio_launcher", "universal_launcher", "universal_setup"},
        "qualification source binding",
    )
    artifacts_value = root["artifacts"]
    if (
        not isinstance(artifacts_value, dict)
        or set(artifacts_value) != route.required_artifacts
    ):
        raise RouteBindingError("qualification artifact binding is not exact")
    artifacts: list[tuple[str, ArtifactBinding]] = []
    for name, raw in sorted(artifacts_value.items()):
        item = _closed_object(
            raw,
            {"relative_path", "size", "sha256"},
            f"qualification artifact {name}",
        )
        relative_path = item["relative_path"]
        size = item["size"]
        if (
            not isinstance(relative_path, str)
            or not relative_path
            or Path(relative_path).is_absolute()
            or ".." in Path(relative_path).parts
            or not isinstance(size, int)
            or isinstance(size, bool)
            or size <= 0
        ):
            raise RouteBindingError(
                f"qualification artifact {name} has an unsafe identity"
            )
        artifacts.append(
            (
                name,
                ArtifactBinding(
                    relative_path,
                    size,
                    _digest(item["sha256"], f"qualification artifact {name}"),
                ),
            )
        )
    factorio = _closed_object(
        root["factorio"],
        {"version", "sha256", "signer"},
        "qualification Factorio binding",
    )
    instance = _closed_object(
        root["instance"],
        {
            "instance_id",
            "spec_digest",
            "binding_digest",
            "readiness_digest",
        },
        "qualification Instance binding",
    )
    if (
        factorio["version"] != "2.0.77"
        or not isinstance(factorio["signer"], str)
        or not factorio["signer"]
        or instance["instance_id"] != route.instance_id
    ):
        raise RouteBindingError("qualification product or Instance binding changed")
    return CandidateQualificationBinding(
        route_id=route.route_id,
        work_unit=route.work_unit,
        factorio_launcher=_component(
            source["factorio_launcher"], "FacMan source binding"
        ),
        universal_launcher=_component(
            source["universal_launcher"], "ULK source binding"
        ),
        universal_setup=_component(
            source["universal_setup"], "USK source binding"
        ),
        artifacts=tuple(artifacts),
        factorio_version=factorio["version"],
        factorio_sha256=_digest(
            factorio["sha256"], "qualification Factorio digest"
        ),
        factorio_signer=factorio["signer"],
        instance_id=instance["instance_id"],
        instance_spec_digest=_digest(
            instance["spec_digest"], "qualification Instance spec digest"
        ),
        instance_binding_digest=_digest(
            instance["binding_digest"], "qualification Instance binding digest"
        ),
        instance_readiness_digest=_digest(
            instance["readiness_digest"],
            "qualification Instance readiness digest",
        ),
        qualification_digest=claimed,
    )
