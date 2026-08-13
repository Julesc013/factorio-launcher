# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Prove three-repository source closure from canonical remote-only clones."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import shutil
import stat
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

try:
    import jsonschema
    from jsonschema.validators import validator_for
except ModuleNotFoundError:  # pragma: no cover - exercised on an unqualified host
    jsonschema = None
    validator_for = None

SCHEMA = "facman.remote_source_closure.v1"
FACTORIO_REMOTE = "https://github.com/Julesc013/factorio-launcher.git"
FACTORIO_REF = "refs/heads/dev"
CANONICAL_REMOTES = {
    "factorio-launcher": FACTORIO_REMOTE,
    "universal-launcher": "https://github.com/Julesc013/universal-launcher.git",
    "universal-setup": "https://github.com/Julesc013/universal-setup.git",
}
PIN_PATTERN = re.compile(r"^[0-9a-f]{40}$")
REF_PATTERN = re.compile(r"^refs/heads/[A-Za-z0-9._/-]+$")
GIT_COMMAND = ("git", "-c", "core.longpaths=true")
HOSTILE_GIT_ENV_PREFIX = "GIT_"
HOSTILE_GIT_ENV_NAMES = {"SSH_ASKPASS"}
HOSTILE_BUILD_ENV_NAMES = {
    "CC",
    "CL",
    "CFLAGS",
    "CMAKE_GENERATOR",
    "CMAKE_GENERATOR_PLATFORM",
    "CMAKE_GENERATOR_TOOLSET",
    "CMAKE_PREFIX_PATH",
    "CMAKE_TOOLCHAIN_FILE",
    "CPPFLAGS",
    "CXX",
    "CXXFLAGS",
    "DESTDIR",
    "INCLUDE",
    "LDFLAGS",
    "LIB",
    "LIBPATH",
    "MAKEFLAGS",
    "PYTHONHOME",
    "PYTHONPATH",
    "SDKROOT",
    "VCPKG_ROOT",
}
HOSTILE_BUILD_ENV_PREFIXES = (
    "CCACHE_",
    "CMAKE_",
    "CONAN_",
    "DYLD_",
    "FACMAN_",
    "FLAUNCH_",
    "SCCACHE_",
)
EXPECTED_OBJECT_FORMAT = "sha1"
PROOF_CODE_RELATIVES = (
    "tools/remote_source_closure.py",
    "tools/json_contract.py",
    "tools/repro_workspace_smoke.py",
    "tools/successor_play_route_definition_check.py",
)
ROUTE_INDEX_RELATIVE = Path("release/index/successor_play_route.index.v1.toml")
HISTORICAL_ROUTE_RELATIVE = Path("release/index/successor_play_route.v1.toml")
ACTIVE_ROUTE_RELATIVE = Path("release/index/successor_play_route.v2.toml")
ACTIVE_ROUTE_SCHEMA = "facman.successor_play_route_definition.v2"
ACTIVE_ROUTE_ID = (
    "facman.play.windows-x64.factorio-2.0.77.standalone.menu."
    "instance-isolated.successor.v2"
)
HISTORICAL_ROUTE_ID = (
    "facman.play.windows-x64.factorio-2.0.77.standalone.menu."
    "instance-isolated.successor.v1"
)
SOURCE_CLOSURE_WORK_UNIT = "FACMAN-SUCCESSOR-PLAY-SOURCE-CLOSURE-01"
SOURCE_CLOSURE_EVIDENCE_ID = "facman.successor-play.source-closure.02"
ADOPTED_ULK_REVISION = "09f0639ab6529fba2f2aa22e9bf68e5eebed0553"
STABLE_USK_REVISION = "32488fc13bd2439f9f6e52e83a97f6da345a7650"
MAX_FACTORIO_ARCHIVE_BYTES = 8 * 1024 * 1024 * 1024
MAX_FACTORIO_EXECUTABLE_BYTES = 1024 * 1024 * 1024
MAX_FACTORIO_EXECUTABLE_COMPRESSION_RATIO = 200
EXPECTED_ACTIVE_ROUTE_KEYS = {
    "schema",
    "route_id",
    "definition_work_unit",
    "definition_status",
    "base_revision",
    "base_tree",
    "canonicalization_version",
    "definition_digest",
    "immutable_after_accepted_integration",
    "predecessor_route",
    "policy",
    "selector",
    "process_provider",
    "observer_provider",
    "permit_profile",
    "workspace_root_contract",
    "packaged_backend_contract",
    "transport_hardening_contract",
    "provider_pins",
    "provider_binding",
    "future_bindings",
    "evidence_identity",
    "sequence",
    "verdict_law",
    "source_closure_workunit",
    "qualification_workunit",
    "non_goals",
    "authority",
}
EXPECTED_ROUTE_INDEX_KEYS = {
    "schema",
    "canonicalization_version",
    "index_digest",
    "selection_status",
    "current_route_id",
    "current_route_contract",
    "current_route_schema",
    "current_route_definition_digest",
    "current_route_sha256",
    "current_route_integration_revision",
    "current_route_integration_tree",
    "current_route_integration_pull_request",
    "new_evidence_target_route_id",
    "new_evidence_execution_authorized",
    "mixed_route_evidence_allowed",
    "source_closure_execution_authorized",
    "route_capability_authorized",
    "route_promotion_authorized",
    "route",
}
EXPECTED_ROUTE_INDEX_ROW_KEYS = {
    "route_id",
    "contract",
    "schema",
    "sha256",
    "definition_digest",
    "state",
    "new_evidence_target",
    "new_source_closure_evidence_allowed",
    "new_qualification_evidence_allowed",
    "route_capability_creation_allowed",
    "route_promotion_allowed",
}


class ClosureFailure(ValueError):
    """A source-closure invariant was not proven."""


@dataclass(frozen=True)
class SourceSpec:
    repo_id: str
    remote: str
    required_ref: str
    pin: str
    tree: str | None = None

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
        assert_safe_build_environment(os.environ)
        if args.report.exists():
            raise ClosureFailure(
                f"report destination already exists and will not be overwritten: {args.report}"
            )
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
    assert_safe_git_environment(os.environ)
    assert_safe_build_environment(os.environ)
    factorio = checked_spec(factorio)
    resolved_factorio_archive: Path | None = None
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

        proof_code = verify_loaded_proof_code(factorio_path)
        schema_validator = verify_jsonschema_dependency(factorio_path)
        route_selection = None
        if factorio_archive is not None:
            validate_cloned_route_contracts(factorio_path)
            route_selection = selected_successor_route(
                factorio_path,
                require_execution_authority=True,
            )
            resolved_factorio_archive = resolve_factorio_archive(factorio_archive)
            preflight_factorio_archive(
                resolved_factorio_archive,
                route_selection[1],
            )

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
        workspace_problems.extend(
            repro_workspace_smoke.check_clean_worktrees(
                repos,
                environment=sanitized_git_environment(),
            )
        )
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
                resolved_factorio_archive,
                route_selection=route_selection,
            )
            if resolved_factorio_archive is not None
            else None
        )
        final_clean = repro_workspace_smoke.check_clean_worktrees(
            repos,
            environment=sanitized_git_environment(),
        )
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
            proof_code=proof_code,
            schema_validator=schema_validator,
        )
        schema_path = (
            factorio_path
            / "contracts"
            / "schema"
            / "release"
            / "remote_source_closure.v1.schema.json"
        )
        validate_source_closure_report(report, schema_path)
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


def assert_safe_build_environment(environment: Mapping[str, str]) -> None:
    hostile = sorted(
        key
        for key, value in environment.items()
        if value
        and (
            key.upper() in HOSTILE_BUILD_ENV_NAMES
            or key.upper().startswith(HOSTILE_BUILD_ENV_PREFIXES)
        )
    )
    if hostile:
        raise ClosureFailure(
            "build-affecting inherited environment is not allowed: "
            + ", ".join(hostile)
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
            "GIT_ATTR_NOSYSTEM": "1",
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
    if not is_canonical_branch_ref(spec.required_ref):
        raise ClosureFailure(f"{spec.repo_id}: required ref must be a canonical branch ref")
    if spec.tree is not None and not PIN_PATTERN.fullmatch(spec.tree):
        raise ClosureFailure(f"{spec.repo_id}: tree must be a lowercase 40-character SHA")
    parsed = urlparse(spec.remote)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or bool(parsed.query)
        or bool(parsed.fragment)
    ):
        raise ClosureFailure(
            f"{spec.repo_id}: remote-only proof requires a credential-free absolute HTTPS remote"
        )
    expected_remote = CANONICAL_REMOTES.get(spec.repo_id)
    if expected_remote is None or spec.remote != expected_remote:
        raise ClosureFailure(
            f"{spec.repo_id}: remote differs from the canonical repository"
        )
    return spec


def is_canonical_branch_ref(value: str) -> bool:
    if not REF_PATTERN.fullmatch(value):
        return False
    branch = value.removeprefix("refs/heads/")
    parts = branch.split("/")
    return not (
        not branch
        or branch.startswith(".")
        or branch.endswith(("/", "."))
        or "//" in branch
        or ".." in branch
        or "@{" in branch
        or any(not part or part.startswith(".") or part.endswith(".lock") for part in parts)
    )


def provider_specs_from_lock(path: Path) -> list[SourceSpec]:
    if not path.is_file():
        raise ClosureFailure(f"cloned FacMan workspace lock is missing: {path}")
    with path.open("rb") as handle:
        lock = tomllib.load(handle)
    if lock.get("schema") != "flaunch.workspace_lock.v1":
        raise ClosureFailure("workspace lock has the wrong schema")
    rows = lock.get("component", [])
    if not isinstance(rows, list) or any(not isinstance(item, dict) for item in rows):
        raise ClosureFailure("workspace lock components are malformed")
    ids = [str(item.get("id", "")) for item in rows]
    if len(ids) != len(set(ids)):
        raise ClosureFailure("workspace lock contains duplicate component identities")
    components = {str(item.get("id", "")): item for item in rows}
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
        if component.get("required_ref") != "refs/heads/main":
            raise ClosureFailure(f"{component_id}: source closure requires provider main")
        expected_remote = CANONICAL_REMOTES[repo_id]
        if component.get("remote") != expected_remote:
            raise ClosureFailure(f"{component_id}: workspace lock remote is not canonical")
        result.append(
            checked_spec(
                SourceSpec(
                    repo_id,
                    str(component.get("remote", "")),
                    str(component.get("required_ref", "")),
                    str(component.get("pin", "")),
                    str(component.get("tree", "")),
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
    tree = git_output(destination, ["rev-parse", "HEAD^{tree}"])
    if spec.tree is not None and tree != spec.tree:
        raise ClosureFailure(f"{spec.repo_id}: checkout tree differs from the workspace lock")
    return {
        "id": spec.repo_id,
        "remote": spec.remote,
        "required_ref": spec.required_ref,
        "pin": spec.pin,
        "head": head,
        "tree": tree,
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


def verify_loaded_proof_code(factorio_repo: Path) -> dict[str, dict[str, Any]]:
    loaded_sources = {
        "tools/remote_source_closure.py": Path(__file__).resolve(strict=True),
        "tools/json_contract.py": Path(str(json_contract.__file__)).resolve(strict=True),
        "tools/repro_workspace_smoke.py": Path(
            str(repro_workspace_smoke.__file__)
        ).resolve(strict=True),
        "tools/successor_play_route_definition_check.py": (
            ROOT / "tools/successor_play_route_definition_check.py"
        ).resolve(strict=True),
    }
    result: dict[str, dict[str, Any]] = {}
    for relative, loaded_path in loaded_sources.items():
        cloned_path = factorio_repo / relative
        if not cloned_path.is_file():
            raise ClosureFailure(f"cloned proof code is missing: {relative}")
        loaded_sha256 = sha256_file(loaded_path)
        cloned_sha256 = sha256_file(cloned_path)
        if loaded_sha256 != cloned_sha256:
            raise ClosureFailure(
                f"loaded proof code differs from the exact FacMan clone: {relative}"
            )
        result[relative] = {
            "loaded_sha256": loaded_sha256,
            "cloned_sha256": cloned_sha256,
            "identical": True,
        }
    return result


def verify_jsonschema_dependency(factorio_repo: Path) -> dict[str, Any]:
    if jsonschema is None or validator_for is None:
        raise ClosureFailure(
            "jsonschema dependency is unavailable; install tools/requirements-dev.lock"
        )
    requirements = factorio_repo / "tools/requirements-dev.lock"
    if not requirements.is_file():
        raise ClosureFailure("cloned development dependency lock is missing")
    expected_versions = {}
    for line in requirements.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "==" not in stripped:
            continue
        name, version = stripped.split("==", 1)
        expected_versions[name.casefold()] = version
    mismatches = []
    for name, expected in sorted(expected_versions.items()):
        try:
            actual_version = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            actual_version = "missing"
        if actual_version != expected:
            mismatches.append(f"{name} expected {expected}, got {actual_version}")
    actual = importlib.metadata.version("jsonschema")
    if not expected_versions or mismatches:
        raise ClosureFailure(
            "schema-validation dependencies differ from the exact FacMan development lock: "
            + "; ".join(mismatches)
        )
    return {
        "name": "jsonschema",
        "version": actual,
        "dependency_count": len(expected_versions),
        "requirements_lock_sha256": sha256_file(requirements),
    }


def validate_cloned_route_contracts(factorio_repo: Path) -> None:
    """Run the exact cloned route validator before any provider or build work."""
    validator = factorio_repo / "tools/successor_play_route_definition_check.py"
    if not validator.is_file():
        raise ClosureFailure("cloned successor route validator is missing")
    run_checked(
        [sys.executable, "-B", str(validator)],
        factorio_repo,
        "cloned successor route contract validation",
    )


def validate_source_closure_report(report: dict[str, Any], schema_path: Path) -> None:
    """Apply the complete Draft 2020-12 contract, including refs and oneOf."""
    if jsonschema is None or validator_for is None:
        raise ClosureFailure(
            "jsonschema dependency is unavailable; install tools/requirements-dev.lock"
        )
    schema = json_contract.load_schema(schema_path)
    try:
        validator_type = validator_for(schema)
        validator_type.check_schema(schema)
        problems = sorted(
            validator_type(schema).iter_errors(report),
            key=lambda error: tuple(str(part) for part in error.absolute_path),
        )
    except jsonschema.exceptions.SchemaError as exc:
        raise ClosureFailure(f"source-closure schema is invalid: {exc.message}") from exc
    if problems:
        rendered = []
        for problem in problems:
            leaves = list(schema_error_leaves(problem))
            for leaf in leaves:
                location = ".".join(str(part) for part in leaf.absolute_path) or "$"
                rendered.append(f"{location}: {leaf.message}")
        raise ClosureFailure(
            "source-closure report violates its schema: " + "; ".join(rendered)
        )


def schema_error_leaves(error: Any) -> list[Any]:
    if not error.context:
        return [error]
    result = []
    for child in error.context:
        result.extend(schema_error_leaves(child))
    return result


def selected_successor_route(
    factorio_repo: Path,
    *,
    require_execution_authority: bool = True,
) -> tuple[Path, dict[str, Any], Path, dict[str, Any], str]:
    index_path = factorio_repo / ROUTE_INDEX_RELATIVE
    if not index_path.is_file():
        raise ClosureFailure("successor route selection index is missing")
    with index_path.open("rb") as handle:
        route_index = tomllib.load(handle)

    if set(route_index) != EXPECTED_ROUTE_INDEX_KEYS:
        raise ClosureFailure("successor route index contract is incomplete or open")
    if route_index.get("schema") != "facman.successor_play_route_index.v1":
        raise ClosureFailure("successor route index has the wrong schema")
    if route_index.get("canonicalization_version") != "facman.sorted-json.v1":
        raise ClosureFailure("successor route index canonicalization drifted")
    expected_index_digest = canonical_digest(
        {key: value for key, value in route_index.items() if key != "index_digest"}
    )
    if route_index.get("index_digest") != expected_index_digest:
        raise ClosureFailure("successor route index digest does not match its content")
    if route_index.get("mixed_route_evidence_allowed") is not False:
        raise ClosureFailure("successor route index must forbid mixed-route evidence")
    if route_index.get("route_capability_authorized") is not False:
        raise ClosureFailure("successor route index unexpectedly grants route capability")
    if route_index.get("route_promotion_authorized") is not False:
        raise ClosureFailure("successor route index unexpectedly grants route promotion")
    if (
        route_index.get("selection_status")
        != "one_integrated_current_definition_no_product_authority"
    ):
        raise ClosureFailure("successor route index selection status is invalid")

    selected_contract = route_index.get("current_route_contract")
    if selected_contract != ACTIVE_ROUTE_RELATIVE.as_posix():
        raise ClosureFailure("successor route index does not select route v2")
    definition_path = factorio_repo / ACTIVE_ROUTE_RELATIVE
    if not definition_path.is_file():
        raise ClosureFailure("selected successor route definition is missing")
    with definition_path.open("rb") as handle:
        definition = tomllib.load(handle)

    if set(definition) != EXPECTED_ACTIVE_ROUTE_KEYS:
        raise ClosureFailure("selected successor route contract is incomplete or open")
    if definition.get("schema") != ACTIVE_ROUTE_SCHEMA:
        raise ClosureFailure("selected successor route has the wrong schema")
    if definition.get("route_id") != ACTIVE_ROUTE_ID:
        raise ClosureFailure("selected successor route has the wrong identity")
    expected_definition_digest = canonical_digest(
        {key: value for key, value in definition.items() if key != "definition_digest"}
    )
    if definition.get("definition_digest") != expected_definition_digest:
        raise ClosureFailure("successor route definition digest does not match its content")
    definition_sha256 = sha256_file(definition_path)
    if route_index.get("current_route_id") != ACTIVE_ROUTE_ID:
        raise ClosureFailure("successor route index and selected definition disagree")
    if route_index.get("current_route_schema") != ACTIVE_ROUTE_SCHEMA:
        raise ClosureFailure("successor route index selects an unsupported route schema")
    if route_index.get("current_route_definition_digest") != expected_definition_digest:
        raise ClosureFailure("successor route index has the wrong definition digest")
    if route_index.get("current_route_sha256") != definition_sha256:
        raise ClosureFailure("successor route index has the wrong definition file hash")
    if route_index.get("new_evidence_target_route_id") != ACTIVE_ROUTE_ID:
        raise ClosureFailure("successor route index selects mixed-route new evidence")

    routes = route_index.get("route")
    if (
        not isinstance(routes, list)
        or len(routes) != 2
        or any(
            not isinstance(route, dict)
            or set(route) != EXPECTED_ROUTE_INDEX_ROW_KEYS
            for route in routes
        )
    ):
        raise ClosureFailure("successor route index rows are incomplete or open")
    route_ids = [str(route.get("route_id", "")) for route in routes]
    if route_ids != [HISTORICAL_ROUTE_ID, ACTIVE_ROUTE_ID]:
        raise ClosureFailure("successor route index rows are duplicated or reordered")
    indexed_routes = {str(route["route_id"]): route for route in routes}
    historical_route = indexed_routes[HISTORICAL_ROUTE_ID]
    historical_path = factorio_repo / HISTORICAL_ROUTE_RELATIVE
    if not historical_path.is_file():
        raise ClosureFailure("historical successor route definition is missing")
    with historical_path.open("rb") as handle:
        historical_definition = tomllib.load(handle)
    historical_digest = canonical_digest(
        {
            key: value
            for key, value in historical_definition.items()
            if key != "definition_digest"
        }
    )
    if (
        historical_definition.get("schema")
        != "facman.successor_play_route_definition.v1"
        or historical_definition.get("route_id") != HISTORICAL_ROUTE_ID
        or historical_definition.get("definition_digest") != historical_digest
        or historical_definition.get("immutable_after_accepted_integration") is not True
    ):
        raise ClosureFailure("historical successor route definition is invalid")
    historical_sha256 = sha256_file(historical_path)
    expected_historical = {
        "route_id": HISTORICAL_ROUTE_ID,
        "contract": HISTORICAL_ROUTE_RELATIVE.as_posix(),
        "schema": "facman.successor_play_route_definition.v1",
        "sha256": historical_sha256,
        "definition_digest": historical_digest,
        "state": "historical_predecessor_superseded_for_new_evidence",
        "new_evidence_target": False,
        "new_source_closure_evidence_allowed": False,
        "new_qualification_evidence_allowed": False,
        "route_capability_creation_allowed": False,
        "route_promotion_allowed": False,
    }
    if historical_route != expected_historical:
        raise ClosureFailure("successor route index does not preserve route v1 exactly")
    predecessor = definition.get("predecessor_route")
    if not isinstance(predecessor, dict) or predecessor != {
        "route_id": HISTORICAL_ROUTE_ID,
        "schema": "facman.successor_play_route_definition.v1",
        "contract": HISTORICAL_ROUTE_RELATIVE.as_posix(),
        "sha256": historical_sha256,
        "definition_digest": historical_digest,
        "state": "historical_predecessor_superseded_for_new_evidence",
        "authority_reused": False,
    }:
        raise ClosureFailure("successor route v2 does not bind route v1 exactly")

    selected_route = indexed_routes[ACTIVE_ROUTE_ID]
    if (
        selected_route.get("contract") != ACTIVE_ROUTE_RELATIVE.as_posix()
        or selected_route.get("schema") != ACTIVE_ROUTE_SCHEMA
        or selected_route.get("sha256") != definition_sha256
        or selected_route.get("definition_digest") != expected_definition_digest
        or selected_route.get("new_evidence_target") is not True
        or selected_route.get("state")
        != "current_integrated_non_authorizing_definition"
        or selected_route.get("new_qualification_evidence_allowed") is not False
        or selected_route.get("route_capability_creation_allowed") is not False
        or selected_route.get("route_promotion_allowed") is not False
    ):
        raise ClosureFailure("successor route index does not admit the selected route")
    if require_execution_authority and (
        route_index.get("new_evidence_execution_authorized") is not True
        or route_index.get("source_closure_execution_authorized") is not True
        or selected_route.get("new_source_closure_evidence_allowed") is not True
    ):
        raise ClosureFailure("successor source-closure execution is not authorized")

    provider_pins = definition.get("provider_pins", {})
    workspace_lock = factorio_repo / "release/index/workspace_lock.v1.toml"
    provider_lock = factorio_repo / "release/index/providers.lock.v2.toml"
    live_locks_match_route = (
        workspace_lock.is_file()
        and provider_lock.is_file()
        and provider_pins.get("workspace_lock_sha256") == sha256_file(workspace_lock)
        and provider_pins.get("provider_lock_sha256") == sha256_file(provider_lock)
    )
    adoption_invalidates_live_locks = False
    if not live_locks_match_route and workspace_lock.is_file() and provider_lock.is_file():
        project_path = factorio_repo / "release/index/project_status.v2.toml"
        if project_path.is_file():
            project = tomllib.loads(project_path.read_text(encoding="utf-8"))
            workspace = tomllib.loads(workspace_lock.read_text(encoding="utf-8"))
            convergence = project.get("provider_convergence", {})
            live_pins = {
                str(row.get("id", "")): str(row.get("pin", ""))
                for row in workspace.get("component", [])
                if isinstance(row, dict)
            }
            adoption_invalidates_live_locks = (
                live_pins.get("universal_launcher") == ADOPTED_ULK_REVISION
                and live_pins.get("universal_setup") == STABLE_USK_REVISION
                and convergence.get("universal_launcher_consumed_pin")
                    == ADOPTED_ULK_REVISION
                and convergence.get("active_route_integration")
                    == "invalidated_by_ulk_provider_adoption"
                and convergence.get("accepted_play_routes") == 0
                and convergence.get("factorio_execution") is False
            )
    if (
        provider_pins.get("source") != "release/index/workspace_lock.v1.toml"
        or provider_pins.get("provider_lock")
        != "release/index/providers.lock.v2.toml"
        or provider_pins.get("required_ref") != "refs/heads/main"
        or provider_pins.get("provider_repin") is not False
        or not workspace_lock.is_file()
        or not provider_lock.is_file()
        or (not live_locks_match_route and not adoption_invalidates_live_locks)
    ):
        raise ClosureFailure("successor route provider-lock binding is invalid")

    bindings = definition.get("provider_binding", [])
    if not isinstance(bindings, list) or any(
        not isinstance(binding, dict) for binding in bindings
    ):
        raise ClosureFailure("successor route provider bindings are malformed")
    binding_ids = [str(binding.get("id", "")) for binding in bindings]
    if binding_ids != ["universal_launcher", "universal_setup"]:
        raise ClosureFailure("successor route provider bindings are duplicated or incomplete")
    with provider_lock.open("rb") as handle:
        provider_lock_record = tomllib.load(handle)
    provider_rows = provider_lock_record.get("provider", [])
    if not isinstance(provider_rows, list) or any(
        not isinstance(provider, dict) for provider in provider_rows
    ):
        raise ClosureFailure("provider lock provider records are malformed")
    provider_ids = [str(provider.get("id", "")) for provider in provider_rows]
    if provider_ids != ["universal_launcher", "universal_setup"]:
        raise ClosureFailure("provider lock identities are duplicated or incomplete")
    locked_providers = {str(provider["id"]): provider for provider in provider_rows}
    compared_provider_fields = (
        "source_revision",
        "source_tree",
        "package_version",
        "package_digest",
        "abi_version",
        "abi_manifest_digest",
        "contract_set_id",
        "contract_digest",
    )
    for binding in bindings:
        provider_id = str(binding["id"])
        locked = locked_providers[provider_id]
        if binding.get("authorizing") is not False:
            raise ClosureFailure(f"successor route provider {provider_id} is authorizing")
        if provider_pins.get(provider_id) != binding.get("source_revision"):
            raise ClosureFailure(f"successor route provider {provider_id} pin is inconsistent")
        if not adoption_invalidates_live_locks:
            for field in compared_provider_fields:
                if binding.get(field) != locked.get(field):
                    raise ClosureFailure(
                        f"successor route provider {provider_id} {field} differs from lock"
                    )
    if adoption_invalidates_live_locks:
        ulk = locked_providers["universal_launcher"]
        usk = locked_providers["universal_setup"]
        if (
            ulk.get("source_revision") != ADOPTED_ULK_REVISION
            or ulk.get("sdk_adoption") != "accepted_exact_main_session_provider"
            or usk.get("source_revision") != STABLE_USK_REVISION
            or usk.get("sdk_adoption") != "accepted_non_authorizing_input"
        ):
            raise ClosureFailure(
                "successor route invalidation does not bind the exact closed-authority provider adoption"
            )

    source_closure = definition.get("source_closure_workunit", {})
    if source_closure.get("id") != SOURCE_CLOSURE_WORK_UNIT:
        raise ClosureFailure("successor route names the wrong source-closure WorkUnit")
    source_identities = [
        identity
        for identity in definition.get("evidence_identity", [])
        if isinstance(identity, dict) and identity.get("role") == "source_closure"
    ]
    if len(source_identities) != 1:
        raise ClosureFailure("successor route must reserve one source-closure identity")
    source_closure_id = str(source_identities[0].get("id", ""))
    if (
        source_closure_id != SOURCE_CLOSURE_EVIDENCE_ID
        or source_identities[0].get("state") != "reserved_uncreated"
        or source_identities[0].get("assigned_by") != SOURCE_CLOSURE_WORK_UNIT
    ):
        raise ClosureFailure("successor route source-closure identity is invalid")

    if definition.get("future_bindings", {}).get("assignment_mutates_route_definition"):
        raise ClosureFailure("source-closure assignment must not mutate the route definition")
    if any(bool(value) for value in definition.get("authority", {}).values()):
        raise ClosureFailure("accepted successor route unexpectedly grants authority")

    return definition_path, definition, index_path, route_index, source_closure_id


def build_successor_observation(
    factorio_repo: Path,
    factorio_spec: SourceSpec,
    repositories: list[dict[str, Any]],
    package: dict[str, Any],
    factorio_archive: Path,
    *,
    route_selection: tuple[
        Path, dict[str, Any], Path, dict[str, Any], str
    ]
    | None = None,
) -> dict[str, Any]:
    (
        definition_path,
        definition,
        route_index_path,
        _route_index,
        source_closure_id,
    ) = route_selection or selected_successor_route(factorio_repo)
    expected_definition_digest = canonical_digest(
        {key: value for key, value in definition.items() if key != "definition_digest"}
    )
    if definition.get("definition_digest") != expected_definition_digest:
        raise ClosureFailure("successor route definition digest does not match its content")
    if definition.get("future_bindings", {}).get("assignment_mutates_route_definition"):
        raise ClosureFailure("source-closure assignment must not mutate the route definition")
    if any(bool(value) for value in definition.get("authority", {}).values()):
        raise ClosureFailure("accepted successor route unexpectedly grants authority")

    observed_providers = {
        str(item["id"]).replace("-", "_"): {
            "source_revision": str(item["pin"]),
            "source_tree": str(item["tree"]),
        }
        for item in repositories
        if item["id"] != "factorio-launcher"
    }
    declared_providers = {
        str(binding["id"]): {
            "source_revision": str(binding["source_revision"]),
            "source_tree": str(binding["source_tree"]),
        }
        for binding in definition.get("provider_binding", [])
        if isinstance(binding, dict)
    }
    if observed_providers != declared_providers:
        raise ClosureFailure(
            "successor route provider revisions or trees differ from remote source observations"
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
        *PROOF_CODE_RELATIVES,
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
        "source_closure_id": source_closure_id,
        "route": {
            "route_id": definition.get("route_id"),
            "definition_contract": ACTIVE_ROUTE_RELATIVE.as_posix(),
            "definition_digest": definition.get("definition_digest"),
            "definition_file_sha256": sha256_file(definition_path),
            "selection_index_sha256": sha256_file(route_index_path),
            "source_closure_evidence_id": source_closure_id,
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


def _factorio_executable_info(
    package: zipfile.ZipFile,
    definition: dict[str, Any],
) -> zipfile.ZipInfo:
    expected_version = str(definition.get("selector", {}).get("factorio_version", ""))
    expected_member = f"Factorio_{expected_version}/bin/x64/factorio.exe"
    matches = [
        item
        for item in package.infolist()
        if item.filename == expected_member
    ]
    if len(matches) != 1:
        raise ClosureFailure(
            "Factorio archive must contain exactly one expected x64 executable"
        )
    executable = matches[0]
    if executable.is_dir() or executable.file_size <= 0:
        raise ClosureFailure("Factorio executable member must be a non-empty file")
    unix_mode = executable.external_attr >> 16
    file_type = stat.S_IFMT(unix_mode)
    if file_type not in (0, stat.S_IFREG):
        raise ClosureFailure("Factorio executable member must be a regular file")
    if executable.flag_bits & 0x1:
        raise ClosureFailure("encrypted Factorio executable is not allowed")
    if executable.file_size > MAX_FACTORIO_EXECUTABLE_BYTES:
        raise ClosureFailure("Factorio executable exceeds the source-closure size budget")
    if executable.compress_size <= 0:
        raise ClosureFailure("Factorio executable has an invalid compressed size")
    ratio = executable.file_size / executable.compress_size
    if ratio > MAX_FACTORIO_EXECUTABLE_COMPRESSION_RATIO:
        raise ClosureFailure("Factorio executable exceeds the compression-ratio budget")
    return executable


def preflight_factorio_archive(archive: Path, definition: dict[str, Any]) -> None:
    if not archive.is_file() or archive.is_symlink():
        raise ClosureFailure(f"Factorio archive is missing: {archive}")
    if archive.stat().st_size <= 0 or archive.stat().st_size > MAX_FACTORIO_ARCHIVE_BYTES:
        raise ClosureFailure("Factorio archive exceeds the source-closure size budget")
    try:
        with zipfile.ZipFile(archive) as package:
            _factorio_executable_info(package, definition)
    except (zipfile.BadZipFile, OSError) as exc:
        raise ClosureFailure(f"cannot inspect Factorio archive: {exc}") from exc


def resolve_factorio_archive(archive: Path) -> Path:
    absolute_archive = Path(os.path.abspath(archive))
    if archive.is_symlink():
        raise ClosureFailure("Factorio archive path indirection is not allowed")
    resolved_archive = archive.resolve(strict=True)
    if absolute_archive != resolved_archive:
        raise ClosureFailure("Factorio archive path indirection is not allowed")
    return resolved_archive


def observe_factorio_archive(
    archive: Path, definition: dict[str, Any]
) -> dict[str, Any]:
    preflight_factorio_archive(archive, definition)
    expected_version = str(definition.get("selector", {}).get("factorio_version", ""))
    try:
        with zipfile.ZipFile(archive) as package:
            executable = _factorio_executable_info(package, definition)
            with package.open(executable, "r") as handle:
                executable_sha256 = sha256_stream(
                    handle,
                    max_bytes=MAX_FACTORIO_EXECUTABLE_BYTES,
                )
    except (zipfile.BadZipFile, OSError) as exc:
        raise ClosureFailure(f"cannot inspect Factorio archive: {exc}") from exc
    return {
        "archive": archive.name,
        "archive_size": archive.stat().st_size,
        "archive_sha256": sha256_file(archive),
        "executable_member": executable.filename,
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


def sha256_stream(handle: Any, *, max_bytes: int | None = None) -> str:
    digest = hashlib.sha256()
    total = 0
    for block in iter(lambda: handle.read(1024 * 1024), b""):
        total += len(block)
        if max_bytes is not None and total > max_bytes:
            raise ClosureFailure("stream exceeds the source-closure size budget")
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
    proof_code: dict[str, dict[str, Any]] | None = None,
    schema_validator: dict[str, Any] | None = None,
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
        "proof_profile": "facman.remote_source_closure.hardened.v2",
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
            **({"proof_code": proof_code} if proof_code is not None else {}),
            **(
                {"schema_validator": schema_validator}
                if schema_validator is not None
                else {}
            ),
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
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
    except FileExistsError as exc:
        raise ClosureFailure(
            f"report destination already exists and will not be overwritten: {path}"
        ) from exc


if __name__ == "__main__":
    raise SystemExit(main())
