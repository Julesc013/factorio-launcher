#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Emit live checkout/provider truth without writing it into tracked source."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import repository_identity

FACMAN_IDENTITY = repository_identity.identity("facman")
SCHEMA = "facman.current_checkout_observation.v2"
OUTPUT_STEM = "current-checkout-observation.v2"
POLICY_RELATIVE_PATH = Path("release/index/checkout_observation_policy.v1.toml")
SHA_PATTERN = re.compile(r"[0-9a-f]{40}")
ABI_PATTERN = re.compile(
    r"^\s*#\s*define\s+([A-Z][A-Z0-9_]*)_API_VERSION_(MAJOR|MINOR)\s+([0-9]+)\b",
    re.MULTILINE,
)
REQUIRED_PROVIDER_IDS = {"universal_launcher", "universal_setup"}
REQUIRED_ABI_IDS = {
    "universal_launcher": {"ulk", "ulu"},
    "universal_setup": {"usk", "usu"},
}

REQUIRED_POLICY = {
    "schema": "facman.checkout_observation_policy.v1",
    "id": "facman_checkout_observation_policy_v1",
    "remote_evidence_classification": "local_tracking_ref_only",
    "fetch_performed": False,
    "source_closure_proven": False,
    "lazy_fetch_allowed": False,
    "local_config_includes_allowed": False,
    "local_object_alternates_allowed": False,
    "shallow_checkout_allowed": False,
    "partial_clone_allowed": False,
}


def _load_observation_policy(
    path: Path,
    line_ending_profile: str,
) -> tuple[dict[str, Any], dict[str, str] | None, list[str]]:
    resolved = path.resolve()
    problems: list[str] = []
    data: dict[str, Any] = {}
    digest: str | None = None
    if not resolved.is_file():
        problems.append(f"checkout observation policy is missing: {resolved}")
    else:
        try:
            policy_bytes = resolved.read_bytes()
            data = tomllib.loads(policy_bytes.decode("utf-8"))
            digest = hashlib.sha256(policy_bytes).hexdigest()
        except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
            problems.append(f"cannot read checkout observation policy: {exc}")

    for key, expected in REQUIRED_POLICY.items():
        if data.get(key) != expected:
            problems.append(
                f"checkout observation policy {key} must be {expected!r}"
            )

    profiles = data.get("line_ending_profile")
    matched_profiles = [
        profile
        for profile in profiles if isinstance(profile, dict)
        and profile.get("id") == line_ending_profile
    ] if isinstance(profiles, list) else []
    effective: dict[str, str] | None = None
    if len(matched_profiles) != 1:
        problems.append(
            "checkout observation policy must define the selected line-ending "
            f"profile exactly once: {line_ending_profile!r}"
        )
    else:
        profile = matched_profiles[0]
        autocrlf = profile.get("core_autocrlf")
        eol = profile.get("core_eol")
        if autocrlf not in {"false", "input", "true"}:
            problems.append(
                "checkout observation line-ending profile core_autocrlf is invalid"
            )
        if eol not in {"lf", "native"}:
            problems.append(
                "checkout observation line-ending profile core_eol is invalid"
            )
        if autocrlf in {"false", "input", "true"} and eol in {"lf", "native"}:
            effective = {
                "id": line_ending_profile,
                "core_autocrlf": str(autocrlf),
                "core_eol": str(eol),
            }

    record = {
        "path": str(resolved),
        "schema": data.get("schema"),
        "id": data.get("id"),
        "sha256": digest,
        "remote_evidence_classification": data.get(
            "remote_evidence_classification"
        ),
        "fetch_performed": data.get("fetch_performed"),
        "fetched_at": None,
        "source_closure_proven": data.get("source_closure_proven"),
        "source_closure_proof": "requires_separate_empty_clone_fetched_proof",
        "source_closure_tool": "tools/remote_source_closure_v2.py",
        "lazy_fetch_disabled": data.get("lazy_fetch_allowed") is False,
        "line_ending_profile": effective,
    }
    if problems:
        effective = None
    return record, effective, problems


def _run_git(
    root: Path,
    *args: str,
    line_ending_policy: dict[str, str],
    trust_root: bool = False,
) -> subprocess.CompletedProcess[str]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith("GIT_")
    }
    environment.update(
        {
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_NO_REPLACE_OBJECTS": "1",
            "GIT_NO_LAZY_FETCH": "1",
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_TERMINAL_PROMPT": "0",
        }
    )
    command = [
        "git",
        "--no-optional-locks",
        "-c",
        "core.fsmonitor=false",
        "-c",
        "core.useReplaceRefs=false",
        "-c",
        "core.ignoreStat=false",
        "-c",
        f"core.autocrlf={line_ending_policy['core_autocrlf']}",
        "-c",
        f"core.eol={line_ending_policy['core_eol']}",
    ]
    if trust_root:
        command.extend(["-c", f"safe.directory={root}"])
    command.extend(args)
    return subprocess.run(
        command,
        cwd=root,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def _git_text(
    root: Path,
    *args: str,
    line_ending_policy: dict[str, str],
    trust_root: bool = False,
) -> str | None:
    completed = _run_git(
        root,
        *args,
        line_ending_policy=line_ending_policy,
        trust_root=trust_root,
    )
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def _observe_checkout(
    root: Path,
    label: str,
    *,
    line_ending_policy: dict[str, str],
    trust_root: bool = False,
) -> tuple[dict[str, Any], list[str]]:
    problems: list[str] = []
    resolved = root.resolve()
    observation: dict[str, Any] = {
        "root": str(resolved),
        "head": None,
        "tree": None,
        "branch": None,
        "detached": None,
        "dirty": None,
        "origin_remote": None,
        "index_flags_clean": None,
        "evidence_safety": {
            "status": "unknown",
            "local_config_includes": [],
            "object_alternates": [],
            "shallow": None,
            "partial_clone_config": [],
            "promisor_pack_markers": [],
            "lazy_fetch_disabled": True,
        },
    }
    if not resolved.is_dir():
        problems.append(f"{label}: repository root does not exist: {resolved}")
        return observation, problems

    safety = observation["evidence_safety"]
    config_keys_set: set[str] = set()
    config_inspection_failed = False
    config_scopes = ["--local"]
    worktree_config_result = _run_git(
        resolved,
        "config",
        "--local",
        "--no-includes",
        "--bool",
        "--get",
        "extensions.worktreeConfig",
        line_ending_policy=line_ending_policy,
        trust_root=trust_root,
    )
    if worktree_config_result.returncode == 0:
        worktree_config_value = worktree_config_result.stdout.strip()
        if worktree_config_value == "true":
            config_scopes.append("--worktree")
        elif worktree_config_value != "false":
            config_inspection_failed = True
            problems.append(
                f"{label}: extensions.worktreeConfig has an invalid Boolean value"
            )
    elif worktree_config_result.returncode != 1:
        config_inspection_failed = True
        problems.append(
            f"{label}: cannot inspect extensions.worktreeConfig"
        )

    for config_scope in config_scopes:
        config_keys_result = _run_git(
            resolved,
            "config",
            config_scope,
            "--no-includes",
            "--name-only",
            "--get-regexp",
            ".*",
            line_ending_policy=line_ending_policy,
            trust_root=trust_root,
        )
        if config_keys_result.returncode in {0, 1}:
            config_keys_set.update(
                key.strip()
                for key in config_keys_result.stdout.splitlines()
                if key.strip()
            )
        else:
            config_inspection_failed = True
            problems.append(
                f"{label}: cannot inspect repository Git config scope "
                f"{config_scope}"
            )
    config_keys = sorted(config_keys_set)

    include_keys = [
        key
        for key in config_keys
        if key.lower() == "include.path"
        or (
            key.lower().startswith("includeif.")
            and key.lower().endswith(".path")
        )
    ]
    safety["local_config_includes"] = include_keys
    if include_keys:
        problems.append(
            f"{label}: repository-local Git config includes are forbidden: "
            + ", ".join(include_keys)
        )
    if config_inspection_failed or include_keys:
        safety["status"] = "fail"
        return observation, problems

    partial_clone_keys = [
        key
        for key in config_keys
        if key.lower() == "extensions.partialclone"
        or re.fullmatch(
            r"remote\..+\.(?:promisor|partialclonefilter)",
            key,
            re.IGNORECASE,
        )
    ]
    safety["partial_clone_config"] = partial_clone_keys
    if partial_clone_keys:
        problems.append(
            f"{label}: partial-clone or promisor Git config is forbidden: "
            + ", ".join(partial_clone_keys)
        )

    for alternate_name in ("alternates", "http-alternates"):
        alternate_raw_path = _git_text(
            resolved,
            "rev-parse",
            "--git-path",
            f"objects/info/{alternate_name}",
            line_ending_policy=line_ending_policy,
            trust_root=trust_root,
        )
        if alternate_raw_path is None:
            problems.append(
                f"{label}: cannot resolve repository-local {alternate_name} path"
            )
            continue
        alternate_path = Path(alternate_raw_path)
        if not alternate_path.is_absolute():
            alternate_path = resolved / alternate_path
        try:
            entries = [
                entry.strip()
                for entry in alternate_path.read_text(
                    encoding="utf-8", errors="replace"
                ).splitlines()
                if entry.strip()
            ] if alternate_path.is_file() else []
        except OSError as exc:
            problems.append(f"{label}: cannot inspect {alternate_name}: {exc}")
            entries = []
        if entries:
            safety["object_alternates"].append(
                {
                    "kind": alternate_name,
                    "path": str(alternate_path.resolve()),
                    "entry_count": len(entries),
                }
            )
    if safety["object_alternates"]:
        problems.append(f"{label}: repository-local object alternates are forbidden")

    shallow_result = _run_git(
        resolved,
        "rev-parse",
        "--is-shallow-repository",
        line_ending_policy=line_ending_policy,
        trust_root=trust_root,
    )
    if shallow_result.returncode != 0 or shallow_result.stdout.strip() not in {
        "true",
        "false",
    }:
        problems.append(f"{label}: cannot determine shallow-repository state")
    else:
        safety["shallow"] = shallow_result.stdout.strip() == "true"
        if safety["shallow"]:
            problems.append(f"{label}: shallow repositories are forbidden")

    pack_raw_path = _git_text(
        resolved,
        "rev-parse",
        "--git-path",
        "objects/pack",
        line_ending_policy=line_ending_policy,
        trust_root=trust_root,
    )
    if pack_raw_path is None:
        problems.append(f"{label}: cannot resolve repository object-pack path")
    else:
        pack_path = Path(pack_raw_path)
        if not pack_path.is_absolute():
            pack_path = resolved / pack_path
        try:
            safety["promisor_pack_markers"] = sorted(
                marker.name for marker in pack_path.glob("*.promisor")
            ) if pack_path.is_dir() else []
        except OSError as exc:
            problems.append(f"{label}: cannot inspect promisor pack markers: {exc}")
        if safety["promisor_pack_markers"]:
            problems.append(f"{label}: promisor object packs are forbidden")

    safety["status"] = "pass" if not problems else "fail"
    if safety["status"] != "pass":
        return observation, problems

    head = _git_text(
        resolved,
        "rev-parse",
        "--verify",
        "HEAD^{commit}",
        line_ending_policy=line_ending_policy,
        trust_root=trust_root,
    )
    if head is None or SHA_PATTERN.fullmatch(head) is None:
        problems.append(f"{label}: cannot resolve an exact Git HEAD")
    else:
        observation["head"] = head

    tree = _git_text(
        resolved,
        "rev-parse",
        "--verify",
        "HEAD^{tree}",
        line_ending_policy=line_ending_policy,
        trust_root=trust_root,
    )
    if tree is None or SHA_PATTERN.fullmatch(tree) is None:
        problems.append(f"{label}: cannot resolve the exact Git tree")
    else:
        observation["tree"] = tree

    origin_remote = _git_text(
        resolved,
        "config",
        "--local",
        "--no-includes",
        "--get",
        "remote.origin.url",
        line_ending_policy=line_ending_policy,
        trust_root=trust_root,
    )
    observation["origin_remote"] = (
        _redact_remote(origin_remote) if origin_remote is not None else "unconfigured"
    )

    branch = _git_text(
        resolved,
        "symbolic-ref",
        "--quiet",
        "--short",
        "HEAD",
        line_ending_policy=line_ending_policy,
        trust_root=trust_root,
    )
    observation["branch"] = branch or None
    observation["detached"] = branch is None

    status = _git_text(
        resolved,
        "status",
        "--porcelain=v1",
        "--untracked-files=normal",
        line_ending_policy=line_ending_policy,
        trust_root=trust_root,
    )
    if status is None:
        problems.append(f"{label}: cannot inspect worktree cleanliness")
    else:
        observation["dirty"] = bool(status)
    index_entries = _git_text(
        resolved,
        "ls-files",
        "-v",
        line_ending_policy=line_ending_policy,
        trust_root=trust_root,
    )
    if index_entries is None:
        problems.append(f"{label}: cannot inspect index flags")
    else:
        special_entries = [
            line for line in index_entries.splitlines() if line and line[0] != "H"
        ]
        observation["index_flags_clean"] = not special_entries
        if special_entries:
            problems.append(
                f"{label}: index contains assume-unchanged, skip-worktree, or "
                "nonstandard entries"
            )
    return observation, problems


def _normalize_remote(value: str, repository_root: Path) -> str:
    candidate = value.strip().replace("\\", "/")
    if not candidate:
        return ""
    if re.match(r"^[A-Za-z]:/", candidate) or candidate.startswith(("/", "./", "../")):
        path = Path(candidate)
        if not path.is_absolute():
            path = repository_root / path
        return os.path.normcase(str(path.resolve())).replace("\\", "/").rstrip("/")
    if re.match(r"^[^/@:]+@[^/:]+:", candidate):
        user_host, path = candidate.split(":", 1)
        candidate = f"ssh://{user_host}/{path}"
    parts = urlsplit(candidate)
    if parts.scheme:
        normalized_path = parts.path.rstrip("/")
        if normalized_path.endswith(".git"):
            normalized_path = normalized_path[:-4]
        return urlunsplit(
            (
                parts.scheme.lower(),
                parts.netloc.rsplit("@", 1)[-1].lower(),
                normalized_path,
                "",
                "",
            )
        )
    return candidate.rstrip("/")


def _redact_remote(value: str) -> str:
    candidate = value.strip()
    if re.match(r"^[^/@:]+@[^/:]+:", candidate):
        return candidate.split("@", 1)[1]
    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://", candidate):
        parts = urlsplit(candidate)
        return urlunsplit(
            (
                parts.scheme,
                parts.netloc.rsplit("@", 1)[-1],
                parts.path,
                "",
                "",
            )
        )
    return candidate


def _discover_abi_versions(
    root: Path,
    label: str,
    revision: str,
    *,
    line_ending_policy: dict[str, str],
    trust_root: bool = False,
) -> tuple[list[dict[str, Any]], list[str]]:
    values: dict[str, dict[str, int]] = {}
    sources: dict[str, set[str]] = {}
    problems: list[str] = []
    tree = _git_text(
        root,
        "ls-tree",
        "-r",
        "--name-only",
        revision,
        "--",
        "include",
        line_ending_policy=line_ending_policy,
        trust_root=trust_root,
    )
    if tree is None:
        return [], [f"{label}: cannot enumerate public headers from locked pin"]

    headers = sorted(
        item for item in tree.splitlines() if item.startswith("include/") and item.endswith(".h")
    )
    if not headers:
        return [], [f"{label}: locked pin has no public headers"]
    for header in headers:
        text = _git_text(
            root,
            "show",
            f"{revision}:{header}",
            line_ending_policy=line_ending_policy,
            trust_root=trust_root,
        )
        if text is None:
            problems.append(f"{label}: cannot read pinned ABI header {header}")
            continue
        for prefix, part, raw_value in ABI_PATTERN.findall(text):
            key = part.lower()
            value = int(raw_value)
            prior = values.setdefault(prefix, {}).get(key)
            if prior is not None and prior != value:
                problems.append(
                    f"{label}: conflicting {prefix} ABI {key} values {prior} and {value}"
                )
                continue
            values[prefix][key] = value
            sources.setdefault(prefix, set()).add(header)

    versions: list[dict[str, Any]] = []
    for prefix in sorted(values):
        parts = values[prefix]
        if "major" not in parts or "minor" not in parts:
            problems.append(f"{label}: incomplete {prefix} ABI version declaration")
            continue
        major = parts["major"]
        minor = parts["minor"]
        versions.append(
            {
                "id": prefix.lower(),
                "major": major,
                "minor": minor,
                "version": f"{major}.{minor}",
                "sources": sorted(sources[prefix]),
            }
        )
    if not versions:
        problems.append(f"{label}: no complete public ABI version declarations found")
    return versions, problems


def _provider_components(lock: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    problems: list[str] = []
    raw_components = lock.get("component")
    if not isinstance(raw_components, list):
        return [], ["workspace lock has no component array"]
    providers: list[dict[str, Any]] = []
    seen_provider_ids: set[str] = set()
    for raw in raw_components:
        if not isinstance(raw, dict):
            problems.append("workspace lock contains a non-table component")
            continue
        if not any(raw.get(key) for key in ("remote", "required_ref", "reachability")):
            continue
        component: dict[str, Any] = {
            key: str(raw.get(key, "")).strip()
            for key in (
                "id",
                "source",
                "pin",
                "remote",
                "required_ref",
                "reachability",
            )
        }
        validation_problems: list[str] = []
        label = component["id"] or "<unnamed>"
        if not component["id"]:
            validation_problems.append("workspace lock contains a provider without an id")
        if SHA_PATTERN.fullmatch(component["pin"]) is None:
            validation_problems.append(
                f"workspace lock provider {label} has no exact pin"
            )
        if not component["remote"]:
            validation_problems.append(
                f"workspace lock provider {label} has no declared remote"
            )
        if component["required_ref"] != "refs/heads/main":
            validation_problems.append(
                f"workspace lock provider {label} required_ref is not refs/heads/main"
            )
        if component["reachability"] != "required_for_source_closure":
            validation_problems.append(
                f"workspace lock provider {label} does not carry the required "
                "source-closure reachability policy"
            )
        problems.extend(validation_problems)
        component["_validation_problems"] = validation_problems
        if component["id"]:
            if component["id"] in seen_provider_ids:
                duplicate_problem = (
                    f"workspace lock contains duplicate provider {component['id']}"
                )
                problems.append(duplicate_problem)
                component["_validation_problems"].append(duplicate_problem)
                for prior in providers:
                    if prior["id"] == component["id"]:
                        prior["_validation_problems"].append(duplicate_problem)
            seen_provider_ids.add(component["id"])
            providers.append(component)
    providers.sort(key=lambda item: item["id"])
    missing = REQUIRED_PROVIDER_IDS - {provider["id"] for provider in providers}
    for component_id in sorted(missing):
        problems.append(f"workspace lock is missing required provider {component_id}")
    return providers, problems


def _observe_provider(
    component: dict[str, Any],
    root: Path | None,
    *,
    line_ending_policy: dict[str, str],
    trust_root: bool = False,
) -> tuple[dict[str, Any], list[str]]:
    component_id = component["id"]
    label = f"provider {component_id}"
    observation: dict[str, Any] = {
        "id": component_id,
        "source": component["source"],
        "pin": component["pin"],
        "declared_remote": _redact_remote(component["remote"]),
        "required_ref": component["required_ref"],
        "reachability_policy": component["reachability"],
        "remote_evidence": {
            "classification": "local_tracking_ref_only",
            "fetch_performed": False,
            "fetched_at": None,
            "source_closure_proven": False,
        },
        "local_tracking_ref": None,
        "local_tracking_ref_head": None,
        "origin_remote": None,
        "remote_matches_lock": None,
        "checkout": {
            "root": str(root.resolve()) if root is not None else None,
            "head": None,
            "branch": None,
            "detached": None,
            "dirty": None,
            "index_flags_clean": None,
            "evidence_safety": {
                "status": "unknown",
                "local_config_includes": [],
                "object_alternates": [],
                "shallow": None,
                "partial_clone_config": [],
                "promisor_pack_markers": [],
                "lazy_fetch_disabled": True,
            },
        },
        "pin_object_present": None,
        "pin_checkout": None,
        "pin_reachable_from_local_tracking_ref": None,
        "abi_source_revision": component["pin"],
        "abi_versions": [],
        "status": "fail",
    }
    problems = list(component.get("_validation_problems", []))
    if root is None:
        problems.append(f"{label}: no sibling root was passed")
        return observation, problems

    resolved = root.resolve()
    checkout, checkout_problems = _observe_checkout(
        resolved,
        label,
        line_ending_policy=line_ending_policy,
        trust_root=trust_root,
    )
    observation["checkout"] = checkout
    problems.extend(checkout_problems)
    if not resolved.is_dir():
        return observation, problems
    if checkout["evidence_safety"]["status"] != "pass":
        return observation, problems

    origin_remote = _git_text(
        resolved,
        "config",
        "--local",
        "--no-includes",
        "--get",
        "remote.origin.url",
        line_ending_policy=line_ending_policy,
        trust_root=trust_root,
    )
    observation["origin_remote"] = (
        _redact_remote(origin_remote) if origin_remote is not None else None
    )
    if origin_remote is None:
        problems.append(f"{label}: cannot resolve origin remote")
    else:
        remote_matches = _normalize_remote(
            origin_remote, resolved
        ) == _normalize_remote(component["remote"], resolved)
        observation["remote_matches_lock"] = remote_matches
        if not remote_matches:
            problems.append(f"{label}: origin remote does not match the workspace lock")

    pin = component["pin"]
    pin_object = _run_git(
        resolved,
        "cat-file",
        "-e",
        f"{pin}^{{commit}}",
        line_ending_policy=line_ending_policy,
        trust_root=trust_root,
    )
    pin_present = pin_object.returncode == 0
    observation["pin_object_present"] = pin_present
    if not pin_present:
        problems.append(f"{label}: locked pin is not present in the sibling repository")

    head = checkout.get("head")
    pin_checkout = head == pin if head is not None else False
    observation["pin_checkout"] = pin_checkout
    if not pin_checkout:
        problems.append(f"{label}: checkout HEAD does not equal the locked pin")
    if checkout.get("dirty") is True:
        problems.append(f"{label}: checkout is dirty")

    required_ref = component["required_ref"]
    local_tracking_ref: str | None = None
    if required_ref.startswith("refs/heads/"):
        local_tracking_ref = (
            "refs/remotes/origin/" + required_ref.removeprefix("refs/heads/")
        )
        observation["local_tracking_ref"] = local_tracking_ref
        local_tracking_head = _git_text(
            resolved,
            "rev-parse",
            "--verify",
            f"{local_tracking_ref}^{{commit}}",
            line_ending_policy=line_ending_policy,
            trust_root=trust_root,
        )
        observation["local_tracking_ref_head"] = local_tracking_head
        if local_tracking_head is None:
            problems.append(f"{label}: local origin tracking ref is unavailable")
        elif pin_present:
            reachable = _run_git(
                resolved,
                "merge-base",
                "--is-ancestor",
                pin,
                local_tracking_ref,
                line_ending_policy=line_ending_policy,
                trust_root=trust_root,
            ).returncode == 0
            observation["pin_reachable_from_local_tracking_ref"] = reachable
            if not reachable:
                problems.append(
                    f"{label}: locked pin is not reachable from local origin/main "
                    "tracking evidence"
                )

    if pin_present:
        abi_versions, abi_problems = _discover_abi_versions(
            resolved,
            label,
            pin,
            line_ending_policy=line_ending_policy,
            trust_root=trust_root,
        )
    else:
        abi_versions = []
        abi_problems = [f"{label}: cannot inspect ABI declarations without locked pin"]
    observation["abi_versions"] = abi_versions
    problems.extend(abi_problems)
    missing_abis = REQUIRED_ABI_IDS.get(component_id, set()) - {
        abi["id"] for abi in abi_versions
    }
    for abi_id in sorted(missing_abis):
        problems.append(f"{label}: required public ABI {abi_id} is not declared")
    observation["status"] = "pass" if not problems else "fail"
    return observation, problems


def collect_observation(
    repository_root: Path,
    workspace_lock: Path,
    provider_roots: dict[str, Path],
    *,
    line_ending_profile: str = "lf_checkout",
    observation_policy: Path | None = None,
    expected_source_sha: str | None = None,
    observed_at_utc: str | None = None,
    trust_passed_roots: bool = False,
) -> dict[str, Any]:
    repository_root = repository_root.resolve()
    workspace_lock = workspace_lock.resolve()
    if observation_policy is None:
        observation_policy = repository_root / POLICY_RELATIVE_PATH
    policy_record, line_ending_policy, problems = _load_observation_policy(
        observation_policy,
        line_ending_profile,
    )

    if line_ending_policy is None:
        observed_at = observed_at_utc or datetime.now(timezone.utc).isoformat(
            timespec="seconds"
        ).replace("+00:00", "Z")
        unique_problems = list(dict.fromkeys(problems))
        return {
            "schema": SCHEMA,
            "observed_at_utc": observed_at,
            "git_ownership_mode": (
                "explicit_exact_roots" if trust_passed_roots else "owner_verified"
            ),
            "observation_policy": policy_record,
            "remote_evidence": {
                "classification": policy_record[
                    "remote_evidence_classification"
                ],
                "fetch_performed": policy_record["fetch_performed"],
                "fetched_at": None,
                "source_closure_proven": policy_record[
                    "source_closure_proven"
                ],
                "source_closure_proof": policy_record["source_closure_proof"],
                "source_closure_tool": policy_record["source_closure_tool"],
            },
            "source": {
                "root": str(repository_root),
                "head": None,
                "tree": None,
                "branch": None,
                "detached": None,
                "dirty": None,
                "origin_remote": None,
                "index_flags_clean": None,
                "evidence_safety": {
                    "status": "unknown",
                    "local_config_includes": [],
                    "object_alternates": [],
                    "shallow": None,
                    "partial_clone_config": [],
                    "promisor_pack_markers": [],
                    "lazy_fetch_disabled": True,
                },
                "expected_ci_sha": expected_source_sha,
                "expected_ci_sha_match": None,
            },
            "workspace_lock": {
                "path": str(workspace_lock),
                "schema": None,
                "sha256": None,
            },
            "providers": [],
            "result": {
                "status": "fail",
                "problem_count": len(unique_problems),
                "problems": unique_problems,
            },
        }

    source, source_problems = _observe_checkout(
        repository_root,
        "factorio-launcher",
        line_ending_policy=line_ending_policy,
        trust_root=trust_passed_roots,
    )
    problems.extend(source_problems)
    expected = expected_source_sha.strip().lower() if expected_source_sha else None
    expected_match: bool | None = None
    if expected is not None:
        if SHA_PATTERN.fullmatch(expected) is None:
            problems.append("factorio-launcher: expected CI SHA is not an exact Git revision")
            expected_match = False
        else:
            expected_match = source.get("head") == expected
            if not expected_match:
                problems.append("factorio-launcher: checkout HEAD does not match expected CI SHA")
    if source.get("dirty") is True:
        problems.append("factorio-launcher: checkout is dirty")
    source["expected_ci_sha"] = expected
    source["expected_ci_sha_match"] = expected_match
    source["repository_role"] = FACMAN_IDENTITY.role
    source["github_repository_id"] = FACMAN_IDENTITY.github_repository_id
    source["canonical_slug"] = FACMAN_IDENTITY.canonical_slug
    source["canonical_https_remote"] = FACMAN_IDENTITY.canonical_https_remote
    source["origin_remote_classification"] = FACMAN_IDENTITY.classifies_remote(
        str(source.get("origin_remote", ""))
    )

    lock_data: dict[str, Any] = {}
    lock_digest: str | None = None
    if not workspace_lock.is_file():
        problems.append(f"workspace lock is missing: {workspace_lock}")
    else:
        try:
            lock_bytes = workspace_lock.read_bytes()
            lock_data = tomllib.loads(lock_bytes.decode("utf-8"))
            lock_digest = hashlib.sha256(lock_bytes).hexdigest()
            if lock_data.get("schema") != "flaunch.workspace_lock.v1":
                problems.append("workspace lock has the wrong schema")
        except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
            problems.append(f"cannot read workspace lock: {exc}")

    components, component_problems = _provider_components(lock_data)
    problems.extend(component_problems)
    declared_ids = {component["id"] for component in components}
    for component_id in sorted(set(provider_roots) - declared_ids):
        problems.append(f"provider root was passed for undeclared component {component_id}")

    providers = []
    for component in components:
        provider, provider_problems = _observe_provider(
            component,
            provider_roots.get(component["id"]),
            line_ending_policy=line_ending_policy,
            trust_root=trust_passed_roots,
        )
        providers.append(provider)
        problems.extend(provider_problems)

    observed_at = observed_at_utc or datetime.now(timezone.utc).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")
    unique_problems = list(dict.fromkeys(problems))
    return {
        "schema": SCHEMA,
        "observed_at_utc": observed_at,
        "git_ownership_mode": (
            "explicit_exact_roots" if trust_passed_roots else "owner_verified"
        ),
        "observation_policy": policy_record,
        "remote_evidence": {
            "classification": policy_record["remote_evidence_classification"],
            "fetch_performed": policy_record["fetch_performed"],
            "fetched_at": None,
            "source_closure_proven": policy_record["source_closure_proven"],
            "source_closure_proof": policy_record["source_closure_proof"],
            "source_closure_tool": policy_record["source_closure_tool"],
        },
        "source": source,
        "workspace_lock": {
            "path": str(workspace_lock),
            "schema": lock_data.get("schema") if lock_data else None,
            "sha256": lock_digest,
        },
        "providers": providers,
        "result": {
            "status": "pass" if not unique_problems else "fail",
            "problem_count": len(unique_problems),
            "problems": unique_problems,
        },
    }


def canonical_json(observation: dict[str, Any]) -> str:
    return json.dumps(
        observation,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ) + "\n"


def _display(value: Any) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, bool):
        return str(value).lower()
    return str(value).replace("|", "\\|").replace("\n", " ")


def markdown(observation: dict[str, Any]) -> str:
    source = observation["source"]
    lock = observation["workspace_lock"]
    policy = observation["observation_policy"]
    remote_evidence = observation["remote_evidence"]
    result = observation["result"]
    line_endings = policy["line_ending_profile"] or {}
    lines = [
        "# Current checkout and provider observation",
        "",
        f"- Schema: `{observation['schema']}`",
        f"- Observed at: `{observation['observed_at_utc']}`",
        f"- Git ownership mode: `{observation['git_ownership_mode']}`",
        f"- Overall status: **{result['status']}**",
        "",
        "This file is generated after checkout. It is not tracked project-state truth and",
        "does not grant execution, mutation, signing, publication, or route authority.",
        "The provider ref evidence is local tracking-ref evidence only: this run performs",
        "no fetch and does not prove remote source closure. Use the separate empty-clone",
        "fetched source-closure proof for that claim.",
        "",
        "## Observation policy",
        "",
        f"- Policy: `{_display(policy['path'])}`",
        f"- Policy schema: `{_display(policy['schema'])}`",
        f"- Policy SHA-256: `{_display(policy['sha256'])}`",
        f"- Line-ending profile: `{_display(line_endings.get('id'))}`",
        f"- Effective core.autocrlf: `{_display(line_endings.get('core_autocrlf'))}`",
        f"- Effective core.eol: `{_display(line_endings.get('core_eol'))}`",
        f"- Remote evidence classification: `{_display(remote_evidence['classification'])}`",
        f"- Fetch performed: `{_display(remote_evidence['fetch_performed'])}`",
        "- Fetched at: `null`",
        f"- Source closure proven: `{_display(remote_evidence['source_closure_proven'])}`",
        f"- Source-closure tool: `{_display(remote_evidence['source_closure_tool'])}`",
        "",
        "## FacMan checkout",
        "",
        "| Root | HEAD | Branch | Detached | Dirty | Expected CI SHA | Match |",
        "| --- | --- | --- | --- | --- | --- | --- |",
        f"| `{_display(source['root'])}` | `{_display(source['head'])}` | "
        f"`{_display(source['branch'])}` | {_display(source['detached'])} | "
        f"{_display(source['dirty'])} | `{_display(source['expected_ci_sha'])}` | "
        f"{_display(source['expected_ci_sha_match'])} |",
        "",
        f"- Evidence-safety preflight: **{_display(source['evidence_safety']['status'])}**",
        f"- Shallow: `{_display(source['evidence_safety']['shallow'])}`",
        "- Local config includes: "
        f"`{_display(', '.join(source['evidence_safety']['local_config_includes']) or 'none')}`",
        "- Object alternates: "
        f"`{_display(len(source['evidence_safety']['object_alternates']))}`",
        "- Partial-clone config: "
        f"`{_display(', '.join(source['evidence_safety']['partial_clone_config']) or 'none')}`",
        "- Promisor pack markers: "
        f"`{_display(', '.join(source['evidence_safety']['promisor_pack_markers']) or 'none')}`",
        "",
        "## Workspace lock",
        "",
        f"- Path: `{_display(lock['path'])}`",
        f"- Schema: `{_display(lock['schema'])}`",
        f"- SHA-256: `{_display(lock['sha256'])}`",
        "",
        "## Providers",
        "",
    ]
    for provider in observation["providers"]:
        checkout = provider["checkout"]
        lines.extend(
            [
                f"### {provider['id']}",
                "",
                f"- Status: **{provider['status']}**",
                f"- Consumed pin: `{_display(provider['pin'])}`",
                f"- Checkout HEAD: `{_display(checkout['head'])}`",
                f"- Checkout pin match: `{_display(provider['pin_checkout'])}`",
                f"- Checkout dirty: `{_display(checkout['dirty'])}`",
                f"- Evidence-safety preflight: **{_display(checkout['evidence_safety']['status'])}**",
                f"- Shallow: `{_display(checkout['evidence_safety']['shallow'])}`",
                f"- Declared remote: `{_display(provider['declared_remote'])}`",
                f"- Observed origin: `{_display(provider['origin_remote'])}`",
                f"- Remote matches lock: `{_display(provider['remote_matches_lock'])}`",
                "- Ref evidence classification: "
                f"`{_display(provider['remote_evidence']['classification'])}`",
                f"- Fetch performed: `{_display(provider['remote_evidence']['fetch_performed'])}`",
                "- Fetched at: `null`",
                f"- Local tracking ref: `{_display(provider['local_tracking_ref'])}`",
                "- Local tracking ref HEAD: "
                f"`{_display(provider['local_tracking_ref_head'])}`",
                "- Pin reachable from local tracking ref: "
                f"`{_display(provider['pin_reachable_from_local_tracking_ref'])}`",
                f"- ABI source revision: `{_display(provider['abi_source_revision'])}`",
                "",
                "| ABI | Version | Declaration source |",
                "| --- | --- | --- |",
            ]
        )
        if provider["abi_versions"]:
            for abi in provider["abi_versions"]:
                lines.append(
                    f"| `{abi['id']}` | `{abi['version']}` | "
                    f"`{', '.join(abi['sources'])}` |"
                )
        else:
            lines.append("| unknown | unknown | unavailable |")
        lines.append("")

    lines.extend(["## Problems", ""])
    if result["problems"]:
        lines.extend(f"- {problem}" for problem in result["problems"])
    else:
        lines.append("- None.")
    lines.append("")
    return "\n".join(lines)


def _parse_provider_roots(
    values: list[str],
    base: Path,
) -> tuple[dict[str, Path], list[str]]:
    roots: dict[str, Path] = {}
    problems: list[str] = []
    for value in values:
        component_id, separator, raw_path = value.partition("=")
        component_id = component_id.strip()
        raw_path = raw_path.strip()
        if not separator or not component_id or not raw_path:
            problems.append(f"invalid --provider-root value: {value!r}; expected ID=PATH")
            continue
        if component_id in roots:
            problems.append(f"duplicate --provider-root component: {component_id}")
            continue
        path = Path(raw_path)
        roots[component_id] = (
            (base / path).resolve() if not path.is_absolute() else path.resolve()
        )
    return roots, problems


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate versioned live checkout/provider observation artifacts."
    )
    parser.add_argument("--repository-root", default=str(ROOT))
    parser.add_argument(
        "--workspace-lock",
        default="release/index/workspace_lock.v1.toml",
    )
    parser.add_argument(
        "--provider-root",
        action="append",
        default=[],
        metavar="ID=PATH",
        help="Passed sibling root; repeat once for each provider in the workspace lock.",
    )
    parser.add_argument(
        "--expected-source-sha",
        default=os.environ.get("FACMAN_CI_SOURCE_SHA"),
    )
    parser.add_argument(
        "--line-ending-profile",
        required=True,
        choices=("lf_checkout", "windows_checkout"),
        help="Explicit tracked-policy profile for every evidence-producing Git read.",
    )
    parser.add_argument("--output-dir", required=True)
    parser.add_argument(
        "--trust-passed-roots",
        action="store_true",
        help=(
            "Explicitly trust only the passed source/provider roots when Git "
            "reports a different filesystem owner; recorded in the artifact."
        ),
    )
    args = parser.parse_args(argv)

    repository_root = Path(args.repository_root).resolve()
    workspace_lock = Path(args.workspace_lock)
    if not workspace_lock.is_absolute():
        workspace_lock = repository_root / workspace_lock
    output_dir = Path(args.output_dir).resolve()
    provider_roots, parse_problems = _parse_provider_roots(
        args.provider_root,
        repository_root,
    )
    if parse_problems:
        for problem in parse_problems:
            print(f"current-checkout-observation: {problem}", file=sys.stderr)
        return 2
    observed_roots = [repository_root, *provider_roots.values()]
    if any(_is_within(output_dir, root) for root in observed_roots):
        print(
            "current-checkout-observation: --output-dir must be outside every "
            "observed source/provider checkout",
            file=sys.stderr,
        )
        return 2

    observation = collect_observation(
        repository_root,
        workspace_lock,
        provider_roots,
        line_ending_profile=args.line_ending_profile,
        expected_source_sha=args.expected_source_sha,
        trust_passed_roots=args.trust_passed_roots,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{OUTPUT_STEM}.json"
    markdown_path = output_dir / f"{OUTPUT_STEM}.md"
    json_path.write_text(canonical_json(observation), encoding="utf-8")
    markdown_path.write_text(markdown(observation), encoding="utf-8")
    print(f"current-checkout-observation: wrote {json_path}")
    print(f"current-checkout-observation: wrote {markdown_path}")
    if observation["result"]["status"] != "pass":
        for problem in observation["result"]["problems"]:
            print(f"current-checkout-observation: {problem}", file=sys.stderr)
        return 1
    print("current-checkout-observation: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
