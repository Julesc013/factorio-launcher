# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Normalize exact, out-of-tree build-source observations for release resolution."""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from tools import repository_identity

from .canonical import domain_digest_value, pretty_json


SCHEMA = "facman.source_observation.v1"
DOMAIN = SCHEMA
HEX_40 = re.compile(r"^[0-9a-f]{40}$")
HEX_64 = re.compile(r"^[0-9a-f]{64}$")
FACMAN_IDENTITY = repository_identity.identity("facman")


def _repository_identity(value: Any) -> str:
    candidate = str(value or "").strip().replace("\\", "/")
    if re.match(r"^[^/@:]+@[^/:]+:", candidate):
        host_path = candidate.split("@", 1)[1]
        host, _, path = host_path.partition(":")
        if host.casefold() != "github.com":
            return ""
        candidate = path
    elif "://" in candidate:
        parsed = urlsplit(candidate)
        if parsed.scheme != "https" or parsed.hostname != "github.com":
            return ""
        candidate = parsed.path
    candidate = candidate.strip("/")
    if candidate.casefold().endswith(".git"):
        candidate = candidate[:-4]
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", candidate):
        return ""
    return candidate.casefold()


def _facman_remote_classification(value: Any) -> str | None:
    candidate = _repository_identity(value)
    if candidate == _repository_identity(FACMAN_IDENTITY.canonical_slug):
        return "canonical"
    if candidate in {
        _repository_identity(slug) for slug in FACMAN_IDENTITY.legacy_slugs
    }:
        return "legacy_redirect"
    return None


def _source_remote_matches_policy(value: Any, expected_repository: str) -> bool:
    if _repository_identity(expected_repository) != _repository_identity(
        FACMAN_IDENTITY.canonical_slug
    ):
        return _repository_identity(value) == _repository_identity(expected_repository)
    return _facman_remote_classification(value) in {"canonical", "legacy_redirect"}


def synthetic_source_observation(model: dict[str, Any]) -> dict[str, Any]:
    """Return deterministic non-release evidence for model/unit validation only."""
    reviewed_base = str(
        model["version"].get("development_lineage", {}).get(
            "reviewed_base_revision",
            "0" * 40,
        )
    )
    providers = []
    for provider in sorted(model["providers"].get("provider", []), key=lambda row: str(row.get("id", ""))):
        provider_core = {
            "id": str(provider["id"]),
            "repository": str(provider["repository"]),
            "commit": str(provider["source_revision"]),
            "tree": "0" * 40,
            "dirty": False,
            "remote": str(provider["repository"]),
            "canonical_ref": "locked-commit-only",
            "observation_class": "synthetic_validation",
        }
        providers.append(
            {
                **provider_core,
                "observation_digest": domain_digest_value(
                    "facman.provider_source_observation.v1",
                    provider_core,
                ),
            }
        )
    core = {
        "schema": SCHEMA,
        "observation_class": "synthetic_validation",
        "repository": str(model["product"]["source_repository"]),
        "commit": reviewed_base,
        "tree": "0" * 40,
        "dirty": False,
        "canonical_ref": "reviewed-base-only",
        "remote": str(model["product"]["source_repository"]),
        "line_ending_policy": {
            "id": "synthetic_validation",
            "policy_digest": "0" * 64,
        },
        "providers": providers,
        "release_eligible": False,
    }
    return {**core, "observation_digest": domain_digest_value(DOMAIN, core)}


def normalize_source_observation(
    value: dict[str, Any],
    model: dict[str, Any],
) -> dict[str, Any]:
    observation = copy.deepcopy(value)
    problems: list[str] = []
    if observation.get("schema") != SCHEMA:
        problems.append(f"source observation schema must be {SCHEMA}")
    observation_class = observation.get("observation_class")
    if observation_class not in {"build_source", "synthetic_validation"}:
        problems.append("source observation class must be build_source or synthetic_validation")
    expected_repository = str(model["product"]["source_repository"])
    if observation.get("repository") != expected_repository:
        problems.append("source observation repository differs from product policy")
    for field in ("commit", "tree"):
        if not HEX_40.fullmatch(str(observation.get(field, ""))):
            problems.append(f"source observation {field} must be an exact Git object id")
    if not isinstance(observation.get("dirty"), bool):
        problems.append("source observation dirty state must be Boolean")
    if not str(observation.get("canonical_ref", "")):
        problems.append("source observation canonical_ref must be non-empty")
    if not str(observation.get("remote", "")):
        problems.append("source observation remote must be non-empty")
    elif observation.get("release_eligible") is True and not _source_remote_matches_policy(
        observation.get("remote"), expected_repository
    ):
        problems.append("release-eligible source observation remote differs from product policy")
    line_endings = observation.get("line_ending_policy")
    if not isinstance(line_endings, dict):
        problems.append("source observation line-ending policy must be an object")
    else:
        if not str(line_endings.get("id", "")):
            problems.append("source observation line-ending policy id must be non-empty")
        if not HEX_64.fullmatch(str(line_endings.get("policy_digest", ""))):
            problems.append("source observation line-ending policy digest must be SHA-256")

    expected_providers = {
        str(item["id"]): item
        for item in model["providers"].get("provider", [])
        if isinstance(item, dict)
    }
    providers = observation.get("providers")
    actual_providers: dict[str, dict[str, Any]] = {}
    if not isinstance(providers, list):
        problems.append("source observation providers must be an array")
        providers = []
    for provider in providers:
        if not isinstance(provider, dict):
            problems.append("source observation contains a non-object provider")
            continue
        provider_id = str(provider.get("id", ""))
        if not provider_id or provider_id in actual_providers:
            problems.append(f"source observation provider identity is missing or duplicated: {provider_id!r}")
            continue
        actual_providers[provider_id] = provider
        expected = expected_providers.get(provider_id)
        if expected is None:
            problems.append(f"source observation contains undeclared provider {provider_id}")
            continue
        if provider.get("repository") != expected.get("repository"):
            problems.append(f"source observation provider {provider_id} repository differs from lock")
        if observation.get("release_eligible") is True and _repository_identity(
            provider.get("remote")
        ) != _repository_identity(expected.get("repository")):
            problems.append(
                f"release-eligible source observation provider {provider_id} remote differs from lock"
            )
        if provider.get("commit") != expected.get("source_revision"):
            problems.append(f"source observation provider {provider_id} commit differs from lock")
        for field in ("commit", "tree"):
            if not HEX_40.fullmatch(str(provider.get(field, ""))):
                problems.append(f"source observation provider {provider_id} {field} is not exact")
        if not isinstance(provider.get("dirty"), bool):
            problems.append(f"source observation provider {provider_id} dirty state must be Boolean")
        if not str(provider.get("canonical_ref", "")):
            problems.append(
                f"source observation provider {provider_id} canonical_ref must be non-empty"
            )
        provider_core = dict(provider)
        provider_digest = str(provider_core.pop("observation_digest", ""))
        expected_digest = domain_digest_value(
            "facman.provider_source_observation.v1",
            provider_core,
        )
        if provider_digest != expected_digest:
            problems.append(f"source observation provider {provider_id} digest is invalid")
    if set(actual_providers) != set(expected_providers):
        problems.append("source observation provider set differs from the provider lock")

    core = dict(observation)
    actual_digest = str(core.pop("observation_digest", ""))
    expected_digest = domain_digest_value(DOMAIN, core)
    if actual_digest != expected_digest:
        problems.append("source observation digest is invalid")
    release_eligible = observation.get("release_eligible")
    if not isinstance(release_eligible, bool):
        problems.append("source observation release_eligible must be Boolean")
    if observation_class == "synthetic_validation" and release_eligible is not False:
        problems.append("synthetic source observations cannot be release eligible")
    if release_eligible and (
        observation_class != "build_source"
        or observation.get("dirty") is not False
        or any(provider.get("dirty") is not False for provider in actual_providers.values())
    ):
        problems.append("release-eligible source observation must bind clean build-source checkouts")
    if problems:
        raise ValueError("; ".join(problems))
    observation["providers"] = [actual_providers[key] for key in sorted(actual_providers)]
    return observation


def from_checkout_observation(
    checkout: dict[str, Any],
    model: dict[str, Any],
) -> dict[str, Any]:
    """Project a full checkout report into path-free release source custody."""
    if checkout.get("schema") != "facman.current_checkout_observation.v2":
        raise ValueError("checkout observation has the wrong schema")
    if checkout.get("result", {}).get("status") != "pass":
        raise ValueError("checkout observation must pass before release projection")
    source = checkout.get("source", {})
    expected_source = str(model["product"]["source_repository"])
    if not _source_remote_matches_policy(source.get("origin_remote"), expected_source):
        raise ValueError("checkout source origin remote differs from product policy")
    remote_classification = _facman_remote_classification(source.get("origin_remote"))
    identity_fields = {
        "repository_role": FACMAN_IDENTITY.role,
        "github_repository_id": FACMAN_IDENTITY.github_repository_id,
        "canonical_slug": FACMAN_IDENTITY.canonical_slug,
        "canonical_https_remote": FACMAN_IDENTITY.canonical_https_remote,
        "origin_remote_classification": remote_classification,
    }
    for field, expected in identity_fields.items():
        if source.get(field) != expected:
            raise ValueError(
                f"checkout source requires exact {field} repository identity"
            )
    if source.get("dirty") is not False:
        raise ValueError("checkout source must be clean before release projection")
    policy = checkout.get("observation_policy", {})
    profile = policy.get("line_ending_profile") or {}
    providers = []
    locked = {
        str(item["id"]): item
        for item in model["providers"].get("provider", [])
        if isinstance(item, dict)
    }
    observed_rows = checkout.get("providers", [])
    if not isinstance(observed_rows, list):
        raise ValueError("checkout provider observations must be an array")
    observed_ids = [str(item.get("id", "")) for item in observed_rows if isinstance(item, dict)]
    if len(observed_ids) != len(observed_rows) or len(set(observed_ids)) != len(observed_ids):
        raise ValueError("checkout provider observations are malformed or duplicated")
    if set(observed_ids) != set(locked):
        raise ValueError("checkout provider set differs from the provider lock")
    for observed in observed_rows:
        provider_id = str(observed.get("id", ""))
        expected = locked.get(provider_id)
        provider_checkout = observed.get("checkout", {})
        if observed.get("status") != "pass":
            raise ValueError(f"checkout provider {provider_id} did not pass observation")
        if observed.get("remote_matches_lock") is not True:
            raise ValueError(f"checkout provider {provider_id} remote does not match the lock")
        if _repository_identity(observed.get("origin_remote")) != _repository_identity(
            expected["repository"]
        ):
            raise ValueError(f"checkout provider {provider_id} origin remote differs from the lock")
        expected_revision = str(expected.get("source_revision", ""))
        expected_tree = str(expected.get("source_tree", ""))
        if observed.get("pin") != expected_revision:
            raise ValueError(f"checkout provider {provider_id} pin differs from the lock")
        if provider_checkout.get("head") != expected_revision:
            raise ValueError(f"checkout provider {provider_id} commit differs from the lock")
        if provider_checkout.get("tree") != expected_tree:
            raise ValueError(f"checkout provider {provider_id} tree differs from the lock")
        if observed.get("required_ref") != "refs/heads/main":
            raise ValueError(f"checkout provider {provider_id} must use refs/heads/main")
        if provider_checkout.get("dirty") is not False:
            raise ValueError(f"checkout provider {provider_id} must be clean")
        provider_core = {
            "id": provider_id,
            "repository": str(expected["repository"]),
            "commit": expected_revision,
            "tree": expected_tree,
            "dirty": provider_checkout.get("dirty"),
            "remote": str(observed.get("origin_remote", "")),
            "canonical_ref": str(observed.get("required_ref", "")),
            "observation_class": "build_source",
        }
        providers.append(
            {
                **provider_core,
                "observation_digest": domain_digest_value(
                    "facman.provider_source_observation.v1",
                    provider_core,
                ),
            }
        )
    core = {
        "schema": SCHEMA,
        "observation_class": "build_source",
        "repository": str(model["product"]["source_repository"]),
        "commit": str(source.get("head", "")),
        "tree": str(source.get("tree", "")),
        "dirty": source.get("dirty"),
        "canonical_ref": (
            f"refs/heads/{source['branch']}"
            if source.get("branch")
            else f"detached:{source.get('head', '')}"
        ),
        "remote": str(source.get("origin_remote", "")),
        "line_ending_policy": {
            "id": str(profile.get("id", "")),
            "policy_digest": str(policy.get("sha256", "")),
        },
        "providers": sorted(providers, key=lambda item: str(item["id"])),
        "release_eligible": True,
    }
    return normalize_source_observation(
        {**core, "observation_digest": domain_digest_value(DOMAIN, core)},
        model,
    )


def load_source_observation(path: Path, model: dict[str, Any]) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"source observation is malformed: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("source observation must be a JSON object")
    return normalize_source_observation(value, model)


def write_source_observation(path: Path, value: dict[str, Any], repository_root: Path) -> Path:
    destination = path.resolve()
    source_root = repository_root.resolve()
    if destination == source_root or source_root in destination.parents:
        raise ValueError("source observation output must be outside the source repository")
    if destination.exists():
        raise ValueError(f"source observation output already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(pretty_json(value), encoding="utf-8")
    return destination
