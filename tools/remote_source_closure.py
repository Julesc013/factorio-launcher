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
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence
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
    args = parser.parse_args(argv)

    try:
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
    alternates = git_path(destination, "objects/info/alternates")
    if alternates.exists():
        raise ClosureFailure(f"{spec.repo_id}: clone unexpectedly uses Git alternates")
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
        "alternates": False,
        "local_clone": False,
        "canonical_ref_contains_pin": True,
    }


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
    return {
        "profile_id": profile,
        "package_file_count": sum(1 for path in package_root.rglob("*") if path.is_file()),
        "artifact": artifact.name,
        "artifact_size": artifact.stat().st_size,
        "artifact_sha256": sha256_file(artifact),
        "provenance": provenance.name,
        "provenance_sha256": sha256_file(provenance),
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
    return {
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
