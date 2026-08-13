# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Qualify the exact promoted, non-adopted ULK main session journal in FacMan.

The harness reconstructs provider SDKs, issues path-independent engineering
identity sidecars, and exercises the real FacMan LastRunProvider through source,
installed, shared, static, and relocated modes. It never changes tracked locks
or grants provider-adoption, execution, Setup, signing, or publication authority.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import provider_conformance as provider  # noqa: E402


ULK_REVISION = "09f0639ab6529fba2f2aa22e9bf68e5eebed0553"
ULK_TREE = "d877bfa3a86158f65705facf757e8700a067d077"
ULK_PACKAGE_VERSION = "1.9.0"
ULK_ABI_VERSION = "1.9"
USK_REVISION = "32488fc13bd2439f9f6e52e83a97f6da345a7650"
USK_TREE = "12fe757b1fc2ae78768a8cf912d03835f46ca65b"
SCHEMA = "facman.ulk_session_consumer_canary_observation.v1"


class Runner:
    def __init__(self, log_dir: Path) -> None:
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def run(
        self,
        label: str,
        command: Sequence[str],
        cwd: Path,
        *,
        environment: Mapping[str, str] | None = None,
        expect_failure: bool = False,
    ) -> provider.CommandResult:
        env = os.environ.copy()
        if environment:
            env.update(environment)
        completed = subprocess.run(
            [str(value) for value in command],
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        payload = (
            f"returncode: {completed.returncode}\n"
            f"command: {list(command)!r}\n\n{completed.stdout}"
        )
        (self.log_dir / f"{label}.log").write_text(
            payload, encoding="utf-8", newline="\n"
        )
        succeeded = completed.returncode == 0
        if succeeded == expect_failure:
            expectation = "failure" if expect_failure else "success"
            raise RuntimeError(f"{label} did not produce expected {expectation}")
        return provider.CommandResult(
            completed.returncode, completed.stdout, f"logs/{label}.log"
        )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git(root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-c", f"safe.directory={root}", "-C", str(root), *arguments],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="strict",
        check=False,
    )
    if completed.returncode != 0:
        raise ValueError(f"git {' '.join(arguments)} failed: {completed.stderr.strip()}")
    return completed.stdout.strip()


def source(
    spec: provider.ProviderSpec,
    root: Path,
    revision: str,
    tree: str,
    required_ref: str,
) -> provider.ProviderSource:
    resolved = root.resolve()
    if git(resolved, "rev-parse", "HEAD") != revision:
        raise ValueError(f"{spec.provider_id} checkout has the wrong revision")
    if git(resolved, "rev-parse", "HEAD^{tree}") != tree:
        raise ValueError(f"{spec.provider_id} checkout has the wrong tree")
    if git(resolved, "remote", "get-url", "origin") != spec.remote:
        raise ValueError(f"{spec.provider_id} checkout has the wrong origin")
    remote_ref = required_ref.replace("refs/heads/", "refs/remotes/origin/", 1)
    if git(resolved, "rev-parse", f"{remote_ref}^{{commit}}") != revision:
        raise ValueError(f"{spec.provider_id} required remote ref is not exact")
    if git(resolved, "status", "--porcelain=v1", "--untracked-files=all"):
        raise ValueError(f"{spec.provider_id} checkout is dirty")
    return provider.ProviderSource(spec, resolved, revision, tree)


def candidate_lock(sources: Mapping[str, provider.ProviderSource]) -> str:
    refs = {
        "universal_launcher": "refs/heads/main",
        "universal_setup": "refs/heads/main",
    }
    lines = [
        'schema = "facman.provider_conformance_lock.v1"',
        'id = "facman_provider_conformance_candidate_v1"',
        "conformance_only = true",
        "sdk_consumption_candidate = false",
        "candidate_not_adopted = true",
        "release_eligible = false",
        "tracked_lock_mutated = false",
        "candidate_differs_from_tracked = true",
        "",
    ]
    for provider_id in sorted(sources):
        selected = sources[provider_id]
        lines.extend(
            [
                "[[component]]",
                f'id = "{provider_id}"',
                f'source = "{selected.spec.source_name}"',
                f'pin = "{selected.commit}"',
                f'tree = "{selected.tree}"',
                f'remote = "{selected.spec.remote}"',
                f'required_ref = "{refs[provider_id]}"',
                "",
            ]
        )
    lines.append("[authority]")
    lines.extend(f"{name} = false" for name in sorted(provider.AUTHORITY))
    return "\n".join(lines) + "\n"


def ulk_identity(
    selected: provider.ProviderSource,
    prefix: Path,
    mode: str,
    toolchain: Mapping[str, Any],
) -> dict[str, Any]:
    spec = selected.spec
    source_abi = selected.root / spec.abi_relative_path
    abi_relative = provider._installed_abi_relative(spec)
    installed_abi = prefix / abi_relative
    if sha256_file(source_abi) != sha256_file(installed_abi):
        raise ValueError("ULK installed ABI manifest differs from exact source")
    abi_version = provider._abi_version(provider._read_toml(installed_abi))
    if abi_version != ULK_ABI_VERSION:
        raise ValueError(f"ULK candidate ABI is {abi_version}, expected {ULK_ABI_VERSION}")
    contracts = provider._installed_contract_root(spec, prefix)
    contract_inventory = provider._relative_inventory(contracts)
    if contract_inventory != provider._public_contract_inventory(contracts):
        raise ValueError("ULK installed contract bundle is not schema-only")
    contract_identity = provider._inventory_entries_identity(contract_inventory)
    inventory_relative = provider._inventory_manifest_relative_path(spec, mode).as_posix()
    inventory_path = prefix / inventory_relative
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    install_identity = provider.inventory_identity(
        prefix, provider._inventory_exclusions(spec, mode)
    )
    if inventory.get("files_sha256") != install_identity["sha256"]:
        raise ValueError("ULK SDK inventory manifest is inconsistent")
    metadata = provider._installed_package_config(spec, prefix)
    identity: dict[str, Any] = {
        "schema": provider.IDENTITY_SCHEMA,
        "provider_id": spec.provider_id,
        "repository": spec.repository,
        "canonical_main_ref": "refs/heads/main",
        "source": {
            "commit": selected.commit,
            "tree": selected.tree,
            "remote": spec.remote,
        },
        "consumption": {"mode": mode, "linkage": mode.removeprefix("installed_")},
        "package": {
            "name": spec.package_name,
            "version": ULK_PACKAGE_VERSION,
            "metadata_relative_path": metadata.relative_to(prefix).as_posix(),
            "metadata_sha256": sha256_file(metadata),
            "exported_targets": list(spec.exported_targets),
        },
        "abi": {
            "version": abi_version,
            "manifest_relative_path": abi_relative,
            "manifest_sha256": sha256_file(installed_abi),
        },
        "contracts": {
            "contract_set_id": "ulk_session_consumer_canary_1_9",
            "bundle_sha256": contract_identity["sha256"],
            "inventory_sha256": contract_identity["sha256"],
            "file_count": contract_identity["file_count"],
        },
        "install": {
            "root": ".",
            "inventory_sha256": install_identity["sha256"],
            "file_count": install_identity["file_count"],
            "inventory_manifest_relative_path": inventory_relative,
            "inventory_manifest_sha256": sha256_file(inventory_path),
        },
        "toolchain": dict(toolchain),
        "authority": dict(provider.AUTHORITY),
    }
    provider.validate_authority(identity["authority"])
    provider.validate_toolchain(identity["toolchain"])
    provider.assert_path_independent_json(identity)
    provider.validate_sdk_inventory_manifest(prefix, identity)
    return identity


def cmake_base(
    facman_root: Path,
    build: Path,
    lock: Path,
    mode: str,
    config: str,
    platform_name: str | None,
) -> list[str]:
    command = [
        "cmake", "-S", str(facman_root), "-B", str(build),
        f"-DCMAKE_BUILD_TYPE={config}",
        "-DFACMAN_BUILD_CLI=ON",
        "-DFACMAN_BUILD_TUI=OFF",
        "-DFACMAN_BUILD_DAEMON=OFF",
        "-DFACMAN_BUILD_GUI=OFF",
        "-DFACMAN_BUILD_TESTS=ON",
        "-DFACMAN_BUILD_PLAY_EVIDENCE_TOOLS=OFF",
        "-DFACMAN_WARNINGS_AS_ERRORS=ON",
        f"-DFACMAN_PROVIDER_MODE={mode}",
        "-DFACMAN_PROVIDER_CONFORMANCE_ONLY=ON",
        "-DFACMAN_PROVIDER_SDK_CONSUMPTION_CANDIDATE=OFF",
        "-DFACMAN_ULK_SESSION_CONSUMER_CANARY=ON",
        f"-DFACMAN_PROVIDER_LOCK_FILE={lock}",
    ]
    if platform_name:
        command.extend(["-A", platform_name])
    return command


def run_facman_mode(
    label: str,
    facman_root: Path,
    work: Path,
    lock: Path,
    sources: Mapping[str, provider.ProviderSource],
    config: str,
    platform_name: str | None,
    runner: Runner,
    *,
    mode: str,
    linkage: str,
    prefixes: Mapping[str, Path] | None = None,
    identities: Mapping[str, Path] | None = None,
) -> dict[str, Any]:
    build = work / "facman-build" / label
    command = cmake_base(facman_root, build, lock, mode, config, platform_name)
    command.append(f"-DFACMAN_PROVIDER_SOURCE_LINKAGE={linkage if mode == 'source' else 'static'}")
    if mode == "source":
        command.extend(
            [
                f"-DFLAUNCH_UNIVERSAL_LAUNCHER_ROOT={sources['universal_launcher'].root}",
                f"-DFLAUNCH_UNIVERSAL_SETUP_ROOT={sources['universal_setup'].root}",
            ]
        )
    else:
        if prefixes is None or identities is None:
            raise ValueError("installed mode lacks SDK prefixes or identities")
        command.extend(
            [
                f"-DFACMAN_UNIVERSAL_LAUNCHER_SDK_ROOT={prefixes['universal_launcher']}",
                f"-DFACMAN_UNIVERSAL_SETUP_SDK_ROOT={prefixes['universal_setup']}",
                f"-DFACMAN_UNIVERSAL_LAUNCHER_IDENTITY_FILE={identities['universal_launcher']}",
                f"-DFACMAN_UNIVERSAL_SETUP_IDENTITY_FILE={identities['universal_setup']}",
            ]
        )
    runner.run(f"{label}-configure", command, facman_root)
    targets = [
        "facman_ulk_session_last_run_canary_smoke",
        "facman_presentation_service_smoke",
    ]
    runner.run(
        f"{label}-build",
        ["cmake", "--build", str(build), "--config", config, "--parallel", "--target", *targets],
        facman_root,
    )
    environment: dict[str, str] = {}
    if linkage == "shared":
        runtime_dirs = [build / config]
        if prefixes:
            runtime_dirs.extend(prefix / "bin" for prefix in prefixes.values())
        environment["PATH"] = os.pathsep.join(str(path) for path in runtime_dirs) + os.pathsep + os.environ.get("PATH", "")
    runner.run(
        f"{label}-test",
        [
            "ctest", "--test-dir", str(build), "-C", config,
            "-R", "^(facman_ulk_session_last_run_canary_smoke|facman_presentation_service_smoke)$",
            "--output-on-failure",
        ],
        facman_root,
        environment=environment,
    )
    identity_text = (build / "facman-build-identity.v1.txt").read_text(encoding="utf-8")
    if "ulk_session_consumer_canary=true" not in identity_text:
        raise ValueError(f"{label} build identity omitted the canary classification")
    return {
        "result": "pass",
        "provider_mode": mode,
        "linkage": linkage,
        "build_identity_sha256": sha256_file(build / "facman-build-identity.v1.txt"),
    }


def execute(args: argparse.Namespace) -> dict[str, Any]:
    facman_root = args.facman_root.resolve()
    ulk_root = args.ulk_root.resolve()
    usk_root = args.usk_root.resolve()
    work = args.work_dir.resolve()
    output = args.output_dir.resolve()
    for external in (work, output):
        if external == facman_root or external.is_relative_to(facman_root):
            raise ValueError("work and output directories must be outside the FacMan source")
    if work.exists() and any(work.iterdir()):
        raise ValueError("work directory must be absent or empty")
    if output.exists() and any(output.iterdir()):
        raise ValueError("output directory must be absent or empty")
    work.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    runner = Runner(output / "logs")

    stable_ulk = provider.PROVIDERS[0]
    stable_usk = provider.PROVIDERS[1]
    canary_ulk = replace(
        stable_ulk,
        canonical_commit=ULK_REVISION,
        package_version=ULK_PACKAGE_VERSION,
        contract_set_id="ulk_session_consumer_canary_1_9",
    )
    sources = {
        "universal_launcher": source(
            canary_ulk, ulk_root, ULK_REVISION, ULK_TREE, "refs/heads/main"
        ),
        "universal_setup": source(
            stable_usk, usk_root, USK_REVISION, USK_TREE, "refs/heads/main"
        ),
    }
    lock = work / "candidate" / "provider-conformance-lock.v1.toml"
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(candidate_lock(sources), encoding="utf-8", newline="\n")

    tracked_lock = facman_root / "release" / "index" / "workspace_lock.v1.toml"
    tracked_before = sha256_file(tracked_lock)
    if not args.skip_ulk_self_conformance:
        runner.run(
            "ulk-sdk-full",
            [
                sys.executable,
                str(ulk_root / "tools" / "cmake_sdk_conformance.py"),
                "--work-dir", str(work / "ulk-sdk-full"),
                "--config", args.config,
                "--phase", "full",
                *(["--platform", args.platform] if args.platform else []),
            ],
            ulk_root,
        )

    prefixes: dict[str, dict[str, Path]] = {"static": {}, "shared": {}}
    identity_paths: dict[str, dict[str, Path]] = {"static": {}, "shared": {}}
    identity_records: dict[str, Any] = {}
    for linkage in ("static", "shared"):
        builds: dict[str, Path] = {}
        for selected in sources.values():
            prefix, build = provider.install_provider_sdk(
                selected,
                linkage,
                work,
                "cmake",
                args.config,
                args.platform,
                runner,
            )
            prefixes[linkage][selected.spec.provider_id] = prefix
            builds[selected.spec.provider_id] = build
        toolchain = provider.cmake_toolchain("cmake", args.config, builds, runner)
        for provider_id, selected in sources.items():
            mode = f"installed_{linkage}"
            prefix = prefixes[linkage][provider_id]
            provider.create_sdk_inventory_manifest(prefix, selected.spec, mode)
            identity = (
                ulk_identity(selected, prefix, mode, toolchain)
                if provider_id == "universal_launcher"
                else provider.build_provider_identity(selected, prefix, mode, toolchain)
            )
            path = prefix / provider._identity_relative_path(selected.spec, mode)
            provider.write_identity(path, identity)
            identity_paths[linkage][provider_id] = path
            identity_records[f"{provider_id}_{mode}"] = {
                "identity_sha256": sha256_file(path),
                "metadata_sha256": identity["package"]["metadata_sha256"],
                "inventory_manifest_sha256": identity["install"][
                    "inventory_manifest_sha256"
                ],
                "inventory_sha256": identity["install"]["inventory_sha256"],
                "package_version": identity["package"]["version"],
                "abi_version": identity["abi"]["version"],
                "abi_manifest_sha256": identity["abi"]["manifest_sha256"],
                "contract_digest": identity["contracts"]["bundle_sha256"],
            }

    modes: dict[str, Any] = {}
    for linkage in ("static", "shared"):
        modes[f"source_{linkage}"] = run_facman_mode(
            f"source-{linkage}", facman_root, work, lock, sources,
            args.config, args.platform, runner,
            mode="source", linkage=linkage,
        )
        modes[f"installed_{linkage}"] = run_facman_mode(
            f"installed-{linkage}", facman_root, work, lock, sources,
            args.config, args.platform, runner,
            mode=f"installed_{linkage}", linkage=linkage,
            prefixes=prefixes[linkage], identities=identity_paths[linkage],
        )

        relocated = {
            provider_id: work / "relocated" / linkage / provider_id
            for provider_id in sources
        }
        relocated_identities: dict[str, Path] = {}
        for provider_id in sources:
            shutil.copytree(prefixes[linkage][provider_id], relocated[provider_id])
            relocated_identities[provider_id] = relocated[provider_id] / identity_paths[linkage][provider_id].relative_to(prefixes[linkage][provider_id])
        modes[f"relocated_{linkage}"] = run_facman_mode(
            f"relocated-{linkage}", facman_root, work, lock, sources,
            args.config, args.platform, runner,
            mode=f"installed_{linkage}", linkage=linkage,
            prefixes=relocated, identities=relocated_identities,
        )

    wrong_build = work / "negative" / "tracked-lock"
    wrong_command = cmake_base(
        facman_root, wrong_build, tracked_lock, "source", args.config, args.platform
    )
    wrong_command.extend(
        [
            "-DFACMAN_PROVIDER_SOURCE_LINKAGE=static",
            f"-DFLAUNCH_UNIVERSAL_LAUNCHER_ROOT={ulk_root}",
            f"-DFLAUNCH_UNIVERSAL_SETUP_ROOT={usk_root}",
        ]
    )
    runner.run("negative-tracked-lock", wrong_command, facman_root, expect_failure=True)

    if sha256_file(tracked_lock) != tracked_before:
        raise ValueError("tracked FacMan provider lock changed during the canary")
    observation: dict[str, Any] = {
        "schema": SCHEMA,
        "observed_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "result": "exact_consumer_canary_pass",
        "facman_revision": git(facman_root, "rev-parse", "HEAD"),
        "facman_tree": git(facman_root, "rev-parse", "HEAD^{tree}"),
        "platform": {
            "system": {
                "Darwin": "macos",
                "Linux": "linux",
                "Windows": "windows",
            }.get(platform.system(), platform.system().lower()),
            "architecture": platform.machine(),
            "runner_os": os.environ.get("RUNNER_OS", "local"),
            "runner_arch": os.environ.get("RUNNER_ARCH", platform.machine()),
        },
        "providers": {
            "universal_launcher": {
                "revision": ULK_REVISION,
                "tree": ULK_TREE,
                "required_ref": "refs/heads/main",
                "package_version": ULK_PACKAGE_VERSION,
                "abi_version": ULK_ABI_VERSION,
            },
            "universal_setup": {
                "revision": USK_REVISION,
                "tree": USK_TREE,
                "required_ref": "refs/heads/main",
            },
        },
        "candidate_lock_sha256": sha256_file(lock),
        "tracked_lock_sha256": tracked_before,
        "tracked_lock_mutated": False,
        "candidate_not_adopted": True,
        "release_eligible": False,
        "provider_identities": identity_records,
        "modes": modes,
        "fault_scope": [
            "no_record", "valid_completion", "unknown_exit_code",
            "outcome_unknown", "recovery_required", "running_record",
            "corrupt_record", "future_schema", "missing_journal",
            "unicode_root", "bounded_two_call_read", "restart_persistence",
            "multiple_bounded_records", "presentation_revision_change",
        ],
        "skips": ["ulk_self_conformance"] if args.skip_ulk_self_conformance else [],
        "no_effect_statement": (
            "No provider pin, protected ref, Factorio process, Setup state, release, "
            "signature, publication, or support classification was changed."
        ),
        "authority": dict(provider.AUTHORITY),
    }
    provider.validate_authority(observation["authority"])
    provider.assert_path_independent_json(observation)
    observation_path = output / "ulk-session-consumer-canary-observation.v1.json"
    observation_path.write_text(
        json.dumps(observation, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({"result": observation["result"], "evidence": str(observation_path)}))
    return observation


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--facman-root", type=Path, default=ROOT)
    parser.add_argument("--ulk-root", type=Path, required=True)
    parser.add_argument("--usk-root", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--config", default="Debug")
    parser.add_argument("--platform")
    parser.add_argument("--skip-ulk-self-conformance", action="store_true")
    args = parser.parse_args(argv)
    try:
        execute(args)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        print(f"ulk-session-consumer-canary: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
