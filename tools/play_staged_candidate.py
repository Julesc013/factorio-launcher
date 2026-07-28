# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Closed binding for a qualified candidate's final evidence workspace."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from tools.play_verdict_route import (
    CandidateQualificationBinding,
    PlayVerdictRoute,
    digest_value,
)


SCHEMA = "factorio.instance_isolated_staged_candidate_binding.v1"
KEYS = {
    "schema",
    "route_id",
    "work_unit",
    "qualification_digest",
    "workspace",
    "instance",
    "projection_digests",
    "authority_promotion",
    "factorio_execution",
    "permit_issuance",
    "observer_capture",
    "human_verdict",
    "staged_candidate_digest",
}
INSTANCE_KEYS = {
    "instance_id",
    "spec_digest",
    "binding_digest",
    "readiness_digest",
}
PROJECTION_KEYS = {
    "inspection",
    "description",
    "readiness",
    "launch_preflight",
}
AUTHORITY_KEYS = {
    "authority_promotion",
    "factorio_execution",
    "permit_issuance",
    "observer_capture",
    "human_verdict",
}


class StagedCandidateError(RuntimeError):
    pass


def _absolute(path: Path) -> Path:
    return Path(os.path.abspath(path))


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def build_staged_candidate(
    projections: dict[str, Any],
    *,
    workspace: Path,
    qualification: CandidateQualificationBinding,
    route: PlayVerdictRoute,
) -> dict[str, Any]:
    inspection = projections.get("inspection")
    description = projections.get("description")
    readiness = projections.get("readiness")
    launch = projections.get("launch_preflight")
    if not all(
        isinstance(value, dict)
        for value in (inspection, description, readiness, launch)
    ):
        raise StagedCandidateError(
            "staged Instance projections are not complete"
        )
    instance = {
        "instance_id": inspection.get("instance_id"),
        "spec_digest": description.get("instance_spec", {}).get(
            "spec_digest"
        ),
        "binding_digest": description.get("instance_binding", {}).get(
            "binding_digest"
        ),
        "readiness_digest": readiness.get("readiness_digest"),
    }
    if (
        instance["instance_id"] != qualification.instance_id
        or instance["spec_digest"] != qualification.instance_spec_digest
        or not all(
            _is_sha256(instance[key])
            for key in (
                "spec_digest",
                "binding_digest",
                "readiness_digest",
            )
        )
    ):
        raise StagedCandidateError(
            "staged Instance identity is not qualification-derived"
        )
    core: dict[str, Any] = {
        "schema": SCHEMA,
        "route_id": route.route_id,
        "work_unit": route.work_unit,
        "qualification_digest": qualification.qualification_digest,
        "workspace": str(_absolute(workspace)),
        "instance": instance,
        "projection_digests": {
            "inspection": digest_value(inspection),
            "description": digest_value(description),
            "readiness": digest_value(readiness),
            "launch_preflight": digest_value(launch),
        },
        **{key: False for key in AUTHORITY_KEYS},
    }
    return {
        **core,
        "staged_candidate_digest": digest_value(core),
    }


def parse_staged_candidate(
    value: dict[str, Any],
    *,
    task_root: Path,
    qualification: CandidateQualificationBinding,
    route: PlayVerdictRoute,
) -> dict[str, Any]:
    if set(value) != KEYS:
        raise StagedCandidateError(
            "staged candidate binding is not a closed record"
        )
    instance = value.get("instance")
    projections = value.get("projection_digests")
    if (
        value.get("schema") != SCHEMA
        or value.get("route_id") != route.route_id
        or value.get("work_unit") != route.work_unit
        or value.get("qualification_digest")
        != qualification.qualification_digest
        or _absolute(Path(str(value.get("workspace", ""))))
        != _absolute(task_root) / "workspace"
        or not isinstance(instance, dict)
        or set(instance) != INSTANCE_KEYS
        or instance.get("instance_id") != qualification.instance_id
        or instance.get("spec_digest")
        != qualification.instance_spec_digest
        or not all(
            _is_sha256(instance.get(key))
            for key in (
                "spec_digest",
                "binding_digest",
                "readiness_digest",
            )
        )
        or not isinstance(projections, dict)
        or set(projections) != PROJECTION_KEYS
        or not all(_is_sha256(item) for item in projections.values())
        or any(value.get(key) is not False for key in AUTHORITY_KEYS)
    ):
        raise StagedCandidateError(
            "staged candidate binding identity is invalid"
        )
    core = {
        key: item
        for key, item in value.items()
        if key != "staged_candidate_digest"
    }
    if (
        not _is_sha256(value.get("staged_candidate_digest"))
        or value["staged_candidate_digest"] != digest_value(core)
    ):
        raise StagedCandidateError(
            "staged candidate binding digest is invalid"
        )
    return value
