# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Prove three-repository source closure from canonical remote-only clones."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import json_contract, repro_workspace_smoke

SCHEMA = "facman.remote_source_closure.v1"
FACTORIO_REMOTE = "https://github.com/Julesc013/factorio-launcher.git"
FACTORIO_REF = "refs/heads/dev"
PIN_PATTERN = re.compile(r"^[0-9a-f]{40}$")
REF_PATTERN = re.compile(r"^refs/heads/[A-Za-z0-9._/-]+$")
GIT_COMMAND = ("git", "-c", "core.longpaths=true")
HOSTILE_GIT_ENV_PREFIX = "GIT_"
HOSTILE_GIT_ENV_NAMES = {"SSH_ASKPASS"}
EXPECTED_OBJECT_FORMAT = "sha1"


class ClosureFailure(ValueError):
    """A source-closure invariant was not proven."""


@dataclass(frozen=True)
class SourceSpec:
    repo_id: str
    remote: str
    required_ref: str
    pin: str

    @property
    def branch(self) -> str:
        return self.required_ref.removeprefix("refs/heads/")

    @property
    def remote_tracking_ref(self) -> str:
        return f"refs/remotes/origin/{self.branch}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Clone exact FacMan, Universal Launcher, and Universal Setup source "
            "from canonical remotes, then rebuild and qualify the workspace."
        )
    )
    parser.add_argument("--factorio-pin", required=True)
    parser.add_argument("--factorio-remote", default=FACTORIO_REMOTE)
    parser.add_argument("--factorio-ref", default=FACTORIO_REF)
    parser.add_argument(
        "--clone-root",
        type=Path,
        help="Empty root for the three clones. A temporary root is used by default.",
    )
    parser.add_argument(
        "--build-root",
        type=Path,
        help="Empty out-of-tree build root. Defaults beside the clone directories.",
    )
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument(
        "--keep-clones",
        action="store_true",
        help="Keep an automatically allocated clone root after the proof.",
    )
    parser.add_argument(
        "--successor-route",
        action="store_true",
        help=(
            "Bind the accepted successor route and read-only Factorio archive "
            "identity to the remote source proof."
        ),
    )
    parser.add_argument(
        "--factorio-archive",
        type=Path,
        help="Read-only Factorio standalone archive used by --successor-route.",
    )
    args = parser.parse_args(argv)

    try:
        assert_safe_git_environment(os.environ)
        if args.successor_route != (args.factorio_archive is not None):
            raise ClosureFailure(
                "--successor-route and --factorio-archive must be supplied together"
            )
        factorio = checked_spec(
            SourceSpec(
                "factorio-launcher",
                args.factorio_remote,
                args.factorio_ref,
                args.factorio_pin,
            )
        )
        report = execute(
            factorio,
            clone_root=args.clone_root,
            build_root=args.build_root,
            keep_clones=args.keep_clones,
            factorio_archive=args.factorio_archive,
        )
        write_report(args.report.resolve(), report)
    except (ClosureFailure, OSError, subprocess.SubprocessError, tomllib.TOMLDecodeError) as exc:
        print(f"remote-source-closure: {exc}", file=sys.stderr)
        return 1
    print(f"remote-source-closure: PASS report={args.report.resolve()}")
    return 0


def execute(
    factorio: SourceSpec,
    *,
    clone_root: Path | None = None,
    build_root: Path | None = None,
    keep_clones: bool = False,
    factorio_archive: Path | None = None,
) -> dict[str, Any]:
    temporary: tempfile.TemporaryDirectory[str] | None = None
    if clone_root is None:
        if keep_clones:
            resolved_clone_root = Path(
                tempfile.mkdtemp(prefix="facman-remote-source-closure-")
            ).resolve()
        else:
            temporary = tempfile.TemporaryDirectory(
                prefix="facman-remote-source-closure-"
            )
            resolved_clone_root = Path(temporary.name).resolve()
    else:
        resolved_clone_root = clone_root.resolve()
        require_empty_root(resolved_clone_root, "clone")

    try:
        resolved_build_root = (
            build_root.resolve()
            if build_root is not None
            else resolved_clone_root / "_build"
        )
        require_empty_root(resolved_build_root, "build")
        if resolved_build_root == resolved_clone_root or resolved_build_root.is_relative_to(
            resolved_clone_root / factorio.repo_id
        ):
            raise ClosureFailure("build root must remain outside every source checkout")

        repos: dict[str, Path] = {}
        observations: list[dict[str, Any]] = []
        factorio_path = resolved_clone_root / factorio.repo_id
        observations.append(clone_exact(factorio, factorio_path))
        repos[factorio.repo_id] = factorio_path

        provider_specs = provider_specs_from_lock(
            factorio_path / "release" / "index" / "workspace_lock.v1.toml"
        )
        for spec in provider_specs:
            destination = resolved_clone_root / spec.repo_id
            observations.append(clone_exact(spec, destination))
            repos[spec.repo_id] = destination

        workspace_problems = repro_workspace_smoke.check_workspace(
            repos,
            require_git=True,
        )
        workspace_problems.extend(repro_workspace_smoke.check_clean_worktrees(repos))
        if workspace_problems:
            raise ClosureFailure(
                "remote workspace boundary check failed: " + "; ".join(workspace_problems)
            )

        records: list[dict[str, object]] = []
        python_cmd = [sys.executable, "-B"]
        matrix_code = repro_workspace_smoke.run_validation_matrix(
            repos,
            python_cmd,
            resolved_build_root,
            records=records,
        )
        if matrix_code != 0:
            failed = next(
                (
                    str(record.get("label"))
                    for record in records
                    if int(record.get("exit_code", 0)) != 0
                ),
                "unknown validation step",
            )
            raise ClosureFailure(f"validation matrix failed at {failed}")

        package = prove_package(
            repos,
            resolved_build_root,
            python_cmd,
            records,
        )
        successor = (
            build_successor_observation(
                factorio_path,
                factorio,
                observations,
                package,
                factorio_archive.resolve(),
            )
            if factorio_archive is not None
            else None
        )
        final_clean = repro_workspace_smoke.check_clean_worktrees(repos)
        if final_clean:
            raise ClosureFailure(
                "source worktrees changed during proof: " + "; ".join(final_clean)
            )

        report = build_report(
            observations,
            records,
            package,
            resolved_clone_root,
            resolved_build_root,
            successor=successor,
        )
        schema_path = (
            factorio_path
            / "contracts"
            / "schema"
            / "release"
            / "remote_source_closure.v1.schema.json"
        )
        problems = json_contract.validate(report, json_contract.load_schema(schema_path))
        if problems:
            raise ClosureFailure(
                "source-closure report violates its schema: " + "; ".join(problems)
            )
        return report
    finally:
        if temporary is not None:
            temporary.cleanup()


def assert_safe_git_environment(environment: Mapping[str, str]) -> None:
    hostile = sorted(
        key
        for key, value in environment.items()
        if value
        and (
            key.upper().startswith(HOSTILE_GIT_ENV_PREFIX)
            or key.upper() in HOSTILE_GIT_ENV_NAMES
        )
    )
    if hostile:
        raise ClosureFailure(
            "hostile inherited Git environment is not allowed: " + ", ".join(hostile)
        )


def sanitized_git_environment() -> dict[str, str]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith(HOSTILE_GIT_ENV_PREFIX)
        and key.upper() not in HOSTILE_GIT_ENV_NAMES
    }
    environment.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_PROTOCOL_FROM_USER": "0",
            "GIT_ALLOW_PROTOCOL": "https",
            "GCM_INTERACTIVE": "Never",
        }
    )
    return environment


def checked_spec(spec: SourceSpec) -> SourceSpec:
    if not PIN_PATTERN.fullmatch(spec.pin):
        raise ClosureFailure(f"{spec.repo_id}: pin must be a lowercase 40-character SHA")
    if not REF_PATTERN.fullmatch(spec.required_ref):
        raise ClosureFailure(f"{spec.repo_id}: required ref must be a canonical branch ref")
    parsed = urlparse(spec.remote)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ClosureFailure(
            f"{spec.repo_id}: remote-only proof requires an absolute HTTPS remote"
        )
    return spec


def provider_specs_from_lock(path: Path) -> list[SourceSpec]:
    if not path.is_file():
        raise ClosureFailure(f"cloned FacMan workspace lock is missing: {path}")
    with path.open("rb") as handle:
        lock = tomllib.load(handle)
    components = {
        str(item.get("id", "")): item
        for item in lock.get("component", [])
        if isinstance(item, dict)
    }
    result: list[SourceSpec] = []
    for component_id, repo_id in (
        ("universal_setup", "universal-setup"),
        ("universal_launcher", "universal-launcher"),
    ):
        component = components.get(component_id)
        if component is None:
            raise ClosureFailure(f"workspace lock is missing {component_id}")
        if component.get("reachability") != "required_for_source_closure":
            raise ClosureFailure(f"{component_id}: source closure is not required by the lock")
        result.append(
            checked_spec(
                SourceSpec(
                    repo_id,
                    str(component.get("remote", "")),
                    str(component.get("required_ref", "")),
                    str(component.get("pin", "")),
                )
            )
        )
    return result


def require_empty_root(path: Path, label: str) -> None:
    if path.exists() and any(path.iterdir()):
        raise ClosureFailure(f"{label} root must be empty: {path}")
    path.mkdir(parents=True, exist_ok=True)


def clone_exact(spec: SourceSpec, destination: Path) -> dict[str, Any]:
    if destination.exists():
        raise ClosureFailure(f"clone destination already exists: {destination}")
    run_checked(
        [
            *GIT_COMMAND,
            "clone",
            "--no-local",
            "--no-checkout",
            "--single-branch",
            "--branch",
            spec.branch,
            "--origin",
            "origin",
            spec.remote,
            str(destination),
        ],
        destination.parent,
        f"{spec.repo_id} clone",
    )
    if git_output(destination, ["remote", "get-url", "origin"]) != spec.remote:
        raise ClosureFailure(f"{spec.repo_id}: cloned origin URL differs from declared remote")
    if git_code(destination, ["cat-file", "-e", f"{spec.pin}^{{commit}}"]) != 0:
        raise ClosureFailure(
            f"{spec.repo_id}: pin {spec.pin} is not fetchable from {spec.required_ref}"
        )
    if git_code(
        destination,
        ["merge-base", "--is-ancestor", spec.pin, spec.remote_tracking_ref],
    ) != 0:
        raise ClosureFailure(
            f"{spec.repo_id}: pin {spec.pin} is not reachable from {spec.required_ref}"
        )
    run_checked(
        [*GIT_COMMAND, "checkout", "--detach", spec.pin],
        destination,
        f"{spec.repo_id} detached checkout",
    )
    isolation = inspect_git_isolation(spec, destination)
    head = git_output(destination, ["rev-parse", "HEAD"])
    if head != spec.pin:
        raise ClosureFailure(f"{spec.repo_id}: detached HEAD does not equal the exact pin")
    if git_code(destination, ["symbolic-ref", "-q", "HEAD"]) == 0:
        raise ClosureFailure(f"{spec.repo_id}: proof checkout is not detached")
    status = git_output(
        destination,
        ["status", "--porcelain=v1", "--untracked-files=all"],
    )
    if status:
        raise ClosureFailure(f"{spec.repo_id}: proof checkout is not clean")
    return {
        "id": spec.repo_id,
        "remote": spec.remote,
        "required_ref": spec.required_ref,
        "pin": spec.pin,
        "head": head,
        "tree": git_output(destination, ["rev-parse", "HEAD^{tree}"]),
        "detached": True,
        "clean": True,
        **isolation,
        "local_clone": False,
        "canonical_ref_contains_pin": True,
        "remote_ref_head": git_output(destination, ["rev-parse", spec.remote_tracking_ref]),
        "pin_equals_remote_ref_head": head
        == git_output(destination, ["rev-parse", spec.remote_tracking_ref]),
        "line_endings": line_ending_observation(destination),
    }


def inspect_git_isolation(spec: SourceSpec, destination: Path) -> dict[str, Any]:
    expected_git_dir = (destination / ".git").resolve()
    if not expected_git_dir.is_dir():
        raise ClosureFailure(f"{spec.repo_id}: expected a non-bare .git directory")

    observed_paths = {
        "git_dir": resolved_git_path(
            destination, git_output(destination, ["rev-parse", "--absolute-git-dir"])
        ),
        "common_dir": resolved_git_path(
            destination, git_output(destination, ["rev-parse", "--git-common-dir"])
        ),
        "object_dir": git_path(destination, "objects"),
        "worktree": resolved_git_path(
            destination, git_output(destination, ["rev-parse", "--show-toplevel"])
        ),
    }
    expected_paths = {
        "git_dir": expected_git_dir,
        "common_dir": expected_git_dir,
        "object_dir": (expected_git_dir / "objects").resolve(),
        "worktree": destination.resolve(),
    }
    for key, expected in expected_paths.items():
        if observed_paths[key] != expected:
            raise ClosureFailure(
                f"{spec.repo_id}: unexpected {key}: {observed_paths[key]} != {expected}"
            )

    remotes = git_output(destination, ["remote"]).splitlines()
    if remotes != ["origin"]:
        raise ClosureFailure(f"{spec.repo_id}: clone must have only the origin remote")
    fetch_refspec = git_output(
        destination, ["config", "--local", "--get-all", "remote.origin.fetch"]
    ).splitlines()
    expected_refspec = f"+{spec.required_ref}:{spec.remote_tracking_ref}"
    if fetch_refspec != [expected_refspec]:
        raise ClosureFailure(
            f"{spec.repo_id}: unexpected origin fetch refspec: {fetch_refspec}"
        )

    alternates = git_path(destination, "objects/info/alternates")
    if alternates.exists():
        raise ClosureFailure(f"{spec.repo_id}: clone unexpectedly uses Git alternates")
    replace_refs = git_output(
        destination, ["for-each-ref", "--format=%(refname)", "refs/replace"]
    )
    if replace_refs:
        raise ClosureFailure(f"{spec.repo_id}: clone unexpectedly contains replace refs")
    shallow = git_output(destination, ["rev-parse", "--is-shallow-repository"])
    if shallow != "false" or git_path(destination, "shallow").exists():
        raise ClosureFailure(f"{spec.repo_id}: shallow source ancestry is not allowed")

    promisor = optional_git_config(
        destination,
        r"^(extensions\.partialclone|remote\..*\.promisor|remote\..*\.partialclonefilter)$",
    )
    if promisor:
        raise ClosureFailure(
            f"{spec.repo_id}: partial-clone/promisor configuration is not allowed"
        )
    includes = optional_git_config(
        destination,
        r"^include(\.path|if\..*\.path)$",
    )
    if includes:
        raise ClosureFailure(f"{spec.repo_id}: Git config includes are not allowed")
    object_format = optional_git_value(
        destination, ["config", "--local", "--get", "extensions.objectFormat"]
    ) or EXPECTED_OBJECT_FORMAT
    if object_format != EXPECTED_OBJECT_FORMAT:
        raise ClosureFailure(
            f"{spec.repo_id}: unsupported Git object format {object_format!r}"
        )
    return {
        "alternates": False,
        "replace_refs": False,
        "shallow": False,
        "partial_clone": False,
        "promisor": False,
        "config_includes": False,
        "unexpected_object_directories": False,
        "hostile_git_environment": False,
        "object_format": object_format,
    }


def optional_git_config(repo: Path, pattern: str) -> list[str]:
    value = optional_git_value(
        repo,
        ["config", "--local", "--get-regexp", pattern],
    )
    return value.splitlines() if value else []


def optional_git_value(repo: Path, args: Sequence[str]) -> str:
    result = subprocess.run(
        [*GIT_COMMAND, *args],
        cwd=repo,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=sanitized_git_environment(),
        stdin=subprocess.DEVNULL,
    )
    if result.returncode not in {0, 1}:
        raise ClosureFailure(
            f"{repo.name} git {' '.join(args)} failed: {result.stderr.strip()}"
        )
    return result.stdout.strip()


def resolved_git_path(repo: Path, value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (repo / path).resolve()


def line_ending_observation(repo: Path) -> dict[str, Any]:
    attributes = repo / ".gitattributes"
    tracked_attributes = git_code(
        repo, ["ls-files", "--error-unmatch", ".gitattributes"]
    )
    if not attributes.is_file() or tracked_attributes != 0:
        raise ClosureFailure(f"{repo.name}: tracked .gitattributes policy is required")
    eol_inventory = git_output(repo, ["ls-files", "--eol"])
    return {
        "attributes_path": ".gitattributes",
        "attributes_sha256": sha256_file(attributes),
        "tracked_eol_inventory_sha256": hashlib.sha256(
            (eol_inventory + "\n").encode("utf-8")
        ).hexdigest(),
        "core_autocrlf": optional_git_value(
            repo, ["config", "--local", "--get", "core.autocrlf"]
        )
        or "unset",
    }


def build_successor_observation(
    factorio_repo: Path,
    factorio_spec: SourceSpec,
    repositories: list[dict[str, Any]],
    package: dict[str, Any],
    factorio_archive: Path,
) -> dict[str, Any]:
    definition_path = factorio_repo / "release/index/successor_play_route.v1.toml"
    if not definition_path.is_file():
        raise ClosureFailure("accepted successor route definition is missing")
    with definition_path.open("rb") as handle:
        definition = tomllib.load(handle)
    expected_definition_digest = canonical_digest(
        {key: value for key, value in definition.items() if key != "definition_digest"}
    )
    if definition.get("definition_digest") != expected_definition_digest:
        raise ClosureFailure("successor route definition digest does not match its content")
    source_closure = definition.get("source_closure_workunit", {})
    if source_closure.get("id") != "FACMAN-SUCCESSOR-PLAY-SOURCE-CLOSURE-01":
        raise ClosureFailure("successor route names the wrong source-closure WorkUnit")
    if definition.get("future_bindings", {}).get("assignment_mutates_route_definition"):
        raise ClosureFailure("source-closure assignment must not mutate the route definition")
    if any(bool(value) for value in definition.get("authority", {}).values()):
        raise ClosureFailure("accepted successor route unexpectedly grants authority")

    observed_pins = {
        str(item["id"]).replace("-", "_"): str(item["pin"])
        for item in repositories
        if item["id"] != "factorio-launcher"
    }
    declared_pins = {
        key: str(value)
        for key, value in definition.get("provider_pins", {}).items()
        if key in {"universal_launcher", "universal_setup"}
    }
    if observed_pins != declared_pins:
        raise ClosureFailure(
            "successor route provider pins differ from remote source observations"
        )

    factorio_identity = observe_factorio_archive(factorio_archive, definition)
    selector = definition.get("selector", {})
    instance_spec = {
        "schema": "facman.successor_source_instance_spec.v1",
        "route_id": definition.get("route_id"),
        "platform": selector.get("platform"),
        "architecture": selector.get("architecture"),
        "factorio_version": selector.get("factorio_version"),
        "distribution": selector.get("distribution"),
        "launch_intent": selector.get("launch_intent"),
        "isolation_mode": selector.get("isolation_mode"),
        "content_capability": selector.get("content_capability"),
        "mod_state": selector.get("mod_state"),
        "account_requirement": selector.get("account_requirement"),
        "credential_requirement": selector.get("credential_requirement"),
        "network_requirement": selector.get("network_requirement"),
    }
    instance_spec_digest = canonical_digest(instance_spec)
    workspace_contract = definition.get("workspace_root_contract", {})
    workspace_checkpoint = factorio_repo / str(workspace_contract.get("checkpoint", ""))
    if not workspace_checkpoint.is_file():
        raise ClosureFailure("workspace-root authority checkpoint is missing")
    workspace_authority = {
        "work_unit": workspace_contract.get("work_unit"),
        "marker_schema": workspace_contract.get("marker_schema"),
        "required_state": workspace_contract.get("required_state"),
        "required_root_binding": workspace_contract.get("required_root_binding"),
        "revalidate_before_dispatch": workspace_contract.get(
            "revalidate_before_dispatch"
        ),
        "checkpoint_sha256": sha256_file(workspace_checkpoint),
        "materialized_workspace_observed": False,
    }
    instance_binding = {
        "schema": "facman.successor_source_instance_binding.v1",
        "state": "source_observed_not_materialized",
        "instance_spec_digest": instance_spec_digest,
        "factorio_archive_sha256": factorio_identity["archive_sha256"],
        "factorio_executable_sha256": factorio_identity["executable_sha256"],
        "candidate_package_sha256": package["artifact_sha256"],
        "candidate_manifest_sha256": package["manifest_sha256"],
        "workspace_authority_digest": canonical_digest(workspace_authority),
        "setup_mutation": False,
    }
    instance_binding_digest = canonical_digest(instance_binding)
    readiness = {
        "schema": "facman.successor_source_readiness.v1",
        "state": "source_inputs_closed_not_qualified",
        "instance_spec_digest": instance_spec_digest,
        "instance_binding_digest": instance_binding_digest,
        "source_reconstructible": True,
        "provider_pins_reachable": True,
        "candidate_package_verified": True,
        "factorio_archive_observed": True,
        "stage_created": False,
        "qualification_required": True,
    }
    readiness_digest = canonical_digest(readiness)

    contract_paths = [
        "contracts/schema/release/remote_source_closure.v1.schema.json",
        "tests/test_remote_source_closure.py",
        "tools/remote_source_closure.py",
    ]
    test_contracts = {
        relative: sha256_file(factorio_repo / relative) for relative in contract_paths
    }
    factorio_observation = next(
        item for item in repositories if item["id"] == "factorio-launcher"
    )
    canonical_ref = factorio_spec.required_ref in {
        "refs/heads/main",
        "refs/heads/dev",
    }
    closure_scope = (
        "canonical_ref"
        if canonical_ref and factorio_observation["pin_equals_remote_ref_head"]
        else "task_ref_rehearsal"
    )
    core = {
        "schema": "facman.successor_play_source_closure.v1",
        "status": (
            "canonical_source_closure_passed"
            if closure_scope == "canonical_ref"
            else "task_ref_reconstruction_passed"
        ),
        "closure_scope": closure_scope,
        "canonical_gate_satisfied": closure_scope == "canonical_ref",
        "source_closure_id": "facman.successor-play.source-closure.01",
        "route": {
            "route_id": definition.get("route_id"),
            "definition_digest": definition.get("definition_digest"),
            "definition_file_sha256": sha256_file(definition_path),
            "immutable": True,
        },
        "candidate": {
            "package": package["artifact"],
            "package_sha256": package["artifact_sha256"],
            "manifest_sha256": package["manifest_sha256"],
            "stage_manifest_sha256": package["stage_manifest_sha256"],
            "resolution_root_digest": package["resolution_root_digest"],
            "source_observation_digest": package["source_observation_digest"],
        },
        "factorio": factorio_identity,
        "instance": {
            "spec": instance_spec,
            "spec_digest": instance_spec_digest,
            "binding": instance_binding,
            "binding_digest": instance_binding_digest,
            "readiness": readiness,
            "readiness_digest": readiness_digest,
        },
        "workspace_root_authority": workspace_authority,
        "test_contracts": test_contracts,
        "test_contracts_digest": canonical_digest(test_contracts),
        "authority": {
            "provider_repin": False,
            "factorio_execution": False,
            "observer_capture": False,
            "stage_authority": False,
            "prepare": False,
            "permit_issuance": False,
            "setup_mutation": False,
            "credential_access": False,
            "signing": False,
            "publication": False,
            "route_capability": False,
            "route_promotion": False,
        },
    }
    return {**core, "source_closure_digest": canonical_digest(core)}


def observe_factorio_archive(
    archive: Path, definition: dict[str, Any]
) -> dict[str, Any]:
    if not archive.is_file():
        raise ClosureFailure(f"Factorio archive is missing: {archive}")
    expected_version = str(definition.get("selector", {}).get("factorio_version", ""))
    expected_suffix = f"/bin/x64/factorio.exe"
    try:
        with zipfile.ZipFile(archive) as package:
            matches = [
                item
                for item in package.infolist()
                if item.filename.replace("\\", "/").endswith(expected_suffix)
                and f"Factorio_{expected_version}/" in item.filename.replace("\\", "/")
            ]
            if len(matches) != 1:
                raise ClosureFailure(
                    "Factorio archive must contain exactly one expected x64 executable"
                )
            executable = matches[0]
            if executable.flag_bits & 0x1:
                raise ClosureFailure("encrypted Factorio executable is not allowed")
            with package.open(executable, "r") as handle:
                executable_sha256 = sha256_stream(handle)
    except (zipfile.BadZipFile, OSError) as exc:
        raise ClosureFailure(f"cannot inspect Factorio archive: {exc}") from exc
    return {
        "archive": archive.name,
        "archive_size": archive.stat().st_size,
        "archive_sha256": sha256_file(archive),
        "executable_member": executable.filename.replace("\\", "/"),
        "executable_size": executable.file_size,
        "executable_sha256": executable_sha256,
        "version": expected_version,
        "distribution": definition.get("selector", {}).get("distribution"),
        "read_only_observation": True,
        "executed": False,
    }


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
            "utf-8"
        )
    ).hexdigest()


def sha256_stream(handle: Any) -> str:
    digest = hashlib.sha256()
    for block in iter(lambda: handle.read(1024 * 1024), b""):
        digest.update(block)
    return digest.hexdigest()


def prove_package(
    repos: dict[str, Path],
    build_root: Path,
    python_cmd: Sequence[str],
    records: list[dict[str, object]],
) -> dict[str, Any]:
    factorio = repos["factorio-launcher"]
    native_build = repro_workspace_smoke.repo_build_dir(build_root, "factorio-launcher")
    package_root_parent = build_root / "_package" / "packages"
    dist_root = build_root / "_package" / "dist"
    profile = package_profile()
    env = repro_workspace_smoke.validation_environment(
        repos,
        {
            name: repro_workspace_smoke.repo_build_dir(build_root, name)
            for name in repro_workspace_smoke.REPO_NAMES
        },
    )
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["FACMAN_NATIVE_CONFIGURATION"] = "Debug"

    required_package_tests = prove_required_package_obligations(
        factorio,
        native_build,
        build_root,
        python_cmd,
        env,
        records,
    )
    pipeline = [
        *python_cmd,
        "tools/package/pipeline.py",
        "--profile",
        profile,
        "--out",
        str(package_root_parent),
        "--build-root",
        str(native_build),
        "--dist",
        str(dist_root),
    ]
    require_step(
        "factorio-launcher package pipeline",
        factorio,
        pipeline,
        env,
        records,
    )
    package_root = package_root_parent / profile
    require_step(
        "factorio-launcher package runtime smoke",
        factorio,
        [
            *python_cmd,
            "tools/package_runtime_smoke.py",
            "--root",
            str(package_root),
        ],
        env,
        records,
    )

    archives = [
        path
        for path in dist_root.iterdir()
        if path.is_file() and (path.suffix == ".zip" or path.name.endswith(".tar.gz"))
    ]
    if len(archives) != 1:
        raise ClosureFailure(f"package proof expected one archive, found {len(archives)}")
    artifact = archives[0]
    provenance = artifact.with_name(artifact.name + ".provenance.v1.json")
    if not provenance.is_file():
        raise ClosureFailure("package proof did not produce artifact provenance")
    require_step(
        "factorio-launcher provenance verification",
        factorio,
        [
            *python_cmd,
            "tools/provenance_build.py",
            "--provenance",
            str(provenance),
            "--artifact",
            str(artifact),
            "--package-root",
            str(package_root),
        ],
        env,
        records,
    )

    extracted = build_root / "_package" / "extracted"
    extracted.mkdir(parents=True)
    shutil.unpack_archive(str(artifact), str(extracted))
    require_step(
        "factorio-launcher archived package runtime smoke",
        factorio,
        [
            *python_cmd,
            "tools/package_runtime_smoke.py",
            "--root",
            str(extracted),
        ],
        env,
        records,
    )
    build_info = json.loads(
        (package_root / "manifest" / "build_info.v1.json").read_text(encoding="utf-8")
    )
    source_revisions = exact_package_source_revisions(repos, build_info)
    package_manifest = package_root / "manifest" / "package.v1.toml"
    stage_manifest_path = package_root / "manifest" / "stage.v1.json"
    resolution_set_path = (
        package_root / "manifest" / "resolution" / "release-resolution-set.v1.json"
    )
    runtime_metadata_path = (
        package_root / "manifest" / "resolution" / "runtime-release-metadata.v1.json"
    )
    identity_paths = {
        "package manifest": package_manifest,
        "stage manifest": stage_manifest_path,
        "resolution set": resolution_set_path,
        "runtime metadata": runtime_metadata_path,
    }
    missing_identity = [
        label for label, path in identity_paths.items() if not path.is_file()
    ]
    if missing_identity:
        raise ClosureFailure(
            "package proof omitted exact release identity: " + ", ".join(missing_identity)
        )
    stage_manifest = json.loads(stage_manifest_path.read_text(encoding="utf-8"))
    resolution_set = json.loads(resolution_set_path.read_text(encoding="utf-8"))
    runtime_metadata = json.loads(runtime_metadata_path.read_text(encoding="utf-8"))
    resolution_root_digest = str(resolution_set.get("root_digest", ""))
    if stage_manifest.get("resolution_root_digest") != resolution_root_digest:
        raise ClosureFailure("stage manifest does not bind the package resolution root")
    if runtime_metadata.get("resolution_root_digest") != resolution_root_digest:
        raise ClosureFailure("runtime metadata does not bind the package resolution root")
    return {
        "profile_id": profile,
        "package_file_count": sum(1 for path in package_root.rglob("*") if path.is_file()),
        "artifact": artifact.name,
        "artifact_size": artifact.stat().st_size,
        "artifact_sha256": sha256_file(artifact),
        "provenance": provenance.name,
        "provenance_sha256": sha256_file(provenance),
        "manifest": "manifest/package.v1.toml",
        "manifest_sha256": sha256_file(package_manifest),
        "build_info_sha256": sha256_file(
            package_root / "manifest" / "build_info.v1.json"
        ),
        "stage_manifest": "manifest/stage.v1.json",
        "stage_manifest_sha256": sha256_file(stage_manifest_path),
        "stage_digest": str(stage_manifest.get("stage_digest", "")),
        "resolution_root_digest": resolution_root_digest,
        "source_observation_digest": str(
            resolution_set.get("source_observation_digest", "")
        ),
        "runtime_metadata_sha256": sha256_file(runtime_metadata_path),
        "runtime_metadata_digest": str(runtime_metadata.get("metadata_digest", "")),
        "runtime_smoke": "pass",
        "archive_runtime_smoke": "pass",
        "provenance_verification": "pass",
        "installed_sdk_proof": installed_sdk_passed(records),
        "required_package_tests": required_package_tests,
        "required_package_skips": 0,
        "source_revisions": source_revisions,
        "toolchain": build_info.get("toolchain", {}),
        "signed": False,
        "published": False,
    }


def prove_required_package_obligations(
    factorio: Path,
    native_build: Path,
    build_root: Path,
    python_cmd: Sequence[str],
    env: dict[str, str],
    records: list[dict[str, object]],
) -> int:
    if os.name == "nt":
        label = "factorio-launcher required Windows package proof"
        require_step(
            label,
            factorio,
            [*python_cmd, "tools/required_package_proof.py"],
            env,
            records,
        )
        return windows_required_package_test_count(
            str(records[-1].get("output", ""))
        )

    required_root = build_root / "_required_package_proof"
    required_out = required_root / "packages"
    required_dist = required_root / "dist"
    evidence = required_root / "evidence.v1.json"
    if sys.platform.startswith("linux"):
        tool = "tools/linux_package_proof.py"
        label = "factorio-launcher required Linux package proof"
    elif sys.platform == "darwin":
        tool = "tools/macos_package_proof.py"
        label = "factorio-launcher required macOS package proof"
    else:
        raise ClosureFailure(f"no required package proof for host {sys.platform}")
    require_step(
        label,
        factorio,
        [
            *python_cmd,
            tool,
            "--build-root",
            str(native_build),
            "--out",
            str(required_out),
            "--dist",
            str(required_dist),
            "--evidence",
            str(evidence),
        ],
        env,
        records,
    )
    proof = json.loads(evidence.read_text(encoding="utf-8"))
    if proof.get("required_skips") != 0:
        raise ClosureFailure(f"{label} did not prove zero required skips")
    checks = proof.get("checks")
    if not isinstance(checks, list) or not checks:
        raise ClosureFailure(f"{label} did not record its required checks")
    return len(checks)


def windows_required_package_test_count(output: str) -> int:
    match = re.search(r"required-package-proof: ok \((\d+) tests, zero skips\)", output)
    if not match:
        raise ClosureFailure("could not extract the required Windows package test count")
    return int(match.group(1))


def exact_package_source_revisions(
    repos: dict[str, Path],
    build_info: dict[str, Any],
) -> dict[str, str]:
    source_revisions = build_info.get("source_revisions")
    if not isinstance(source_revisions, dict):
        raise ClosureFailure("package build identity has no source_revisions object")
    expected_revisions = {
        "factorio_launcher": git_output(
            repos["factorio-launcher"], ["rev-parse", "HEAD"]
        ),
        "universal_launcher": git_output(
            repos["universal-launcher"], ["rev-parse", "HEAD"]
        ),
        "universal_setup": git_output(
            repos["universal-setup"], ["rev-parse", "HEAD"]
        ),
    }
    if source_revisions != expected_revisions:
        raise ClosureFailure(
            "package source revisions differ from the exact proof checkouts: "
            f"expected {expected_revisions}, got {source_revisions}"
        )
    return {str(key): str(value) for key, value in source_revisions.items()}


def require_step(
    label: str,
    cwd: Path,
    command: Sequence[str],
    env: dict[str, str],
    records: list[dict[str, object]],
) -> None:
    code = repro_workspace_smoke.run_step(
        label,
        cwd,
        command,
        env,
        records=records,
    )
    if code != 0:
        raise ClosureFailure(f"{label} failed")


def package_profile() -> str:
    machine = platform.machine().lower()
    if machine not in {"amd64", "x86_64"}:
        raise ClosureFailure(f"source-closure package proof requires x64, got {machine}")
    if os.name == "nt":
        return "windows_portable_cli_x64"
    if sys.platform == "darwin":
        return "macos_portable_cli_x64"
    if sys.platform.startswith("linux"):
        return "linux_portable_cli_x64"
    raise ClosureFailure(f"unsupported source-closure package host: {sys.platform}")


def build_report(
    repositories: list[dict[str, Any]],
    records: list[dict[str, object]],
    package: dict[str, Any],
    clone_root: Path,
    build_root: Path,
    *,
    successor: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tests = test_counts(records)
    steps = [
        {
            "label": str(record["label"]),
            "status": "pass" if int(record["exit_code"]) == 0 else "fail",
            "command": [str(value) for value in record["command"]],
        }
        for record in records
    ]
    report = {
        "schema": SCHEMA,
        "status": "pass",
        "observed_at_utc": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "claim": "remote_source_closure_proven",
        "authority_promotion": False,
        "factorio_execution": False,
        "permit_issuance": False,
        "publication": False,
        "clone_policy": {
            "empty_directories": True,
            "git_clone_no_local": True,
            "git_core_longpaths": True,
            "https_remotes_only": True,
            "preexisting_objects": False,
            "alternates": False,
            "replace_refs": False,
            "shallow_repositories": False,
            "partial_clone_or_promisor": False,
            "config_includes": False,
            "unexpected_object_directories": False,
            "hostile_inherited_git_environment": False,
            "system_and_global_config_disabled": True,
            "detached_exact_checkouts": True,
        },
        "repositories": repositories,
        "workspace": {
            "clone_root": str(clone_root),
            "build_root": str(build_root),
            "paths_are_local_observations": True,
            "source_worktrees_clean_after_validation": True,
        },
        "tooling": {
            "git": command_version(["git", "--version"]),
            "cmake": command_version(["cmake", "--version"]),
            "python": sys.version.splitlines()[0],
            "host": platform.platform(),
        },
        "validation": {
            "steps": steps,
            "test_counts": tests,
            "strict_repositories": [
                "factorio-launcher",
                "universal-launcher",
                "universal-setup",
            ],
            "aide_lite": "pass",
        },
        "package": package,
    }
    if successor is not None:
        report["successor"] = successor
    return report


def test_counts(records: list[dict[str, object]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        label = str(record.get("label", ""))
        output = str(record.get("output", ""))
        if label.endswith(" ctest"):
            match = re.search(r"0 tests failed out of (\d+)", output)
            if match:
                counts[label.removesuffix(" ctest") + "_native"] = int(match.group(1))
        elif label == "factorio-launcher unittest":
            match = re.search(r"Ran (\d+) tests", output)
            if match:
                counts["factorio-launcher_python"] = int(match.group(1))
    required = {
        "universal-launcher_native",
        "universal-setup_native",
        "factorio-launcher_native",
        "factorio-launcher_python",
    }
    missing = sorted(required - counts.keys())
    if missing:
        raise ClosureFailure("could not extract required test counts: " + ", ".join(missing))
    return counts


def installed_sdk_passed(records: list[dict[str, object]]) -> bool:
    return any(
        record.get("label") == "factorio-launcher ctest"
        and "facman_installed_sdk_smoke" in str(record.get("output", ""))
        and int(record.get("exit_code", 1)) == 0
        for record in records
    )


def command_version(command: Sequence[str]) -> str:
    result = subprocess.run(
        command,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if result.returncode != 0:
        raise ClosureFailure(f"cannot resolve tool identity: {' '.join(command)}")
    return result.stdout.splitlines()[0].strip()


def run_checked(
    command: Sequence[str],
    cwd: Path,
    label: str,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=cwd,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        env=sanitized_git_environment(),
    )
    if result.returncode != 0:
        detail = result.stdout.strip()
        raise ClosureFailure(f"{label} failed: {detail}")
    return result


def git_output(repo: Path, args: Sequence[str]) -> str:
    return run_checked(
        [*GIT_COMMAND, *args],
        repo,
        f"{repo.name} git {' '.join(args)}",
    ).stdout.strip()


def git_code(repo: Path, args: Sequence[str]) -> int:
    return subprocess.run(
        [*GIT_COMMAND, *args],
        cwd=repo,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        env=sanitized_git_environment(),
    ).returncode


def git_path(repo: Path, value: str) -> Path:
    raw = git_output(repo, ["rev-parse", "--git-path", value])
    path = Path(raw)
    return path if path.is_absolute() else (repo / path).resolve()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
