# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Prove production-capable, non-adopted FacMan provider SDK consumption."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import provider_conformance as inputs  # noqa: E402
from tools import provider_semantic_conformance as semantics  # noqa: E402
from tools.release_compiler.canonical import canonical_bytes  # noqa: E402


SCHEMA = "facman.provider_sdk_consumption_observation.v1"
OBSERVATION_STEM = "provider-sdk-consumption-observation.v1"
AUTHORITY = dict(inputs.AUTHORITY)


def _classify_phase_a(
    phase_a: Mapping[str, Any], *, skip_provider_self_conformance: bool
) -> tuple[str, list[str]]:
    expected = (
        "bounded_provider_input_development_rehearsal"
        if skip_provider_self_conformance
        else "bounded_provider_input_conformance_pass"
    )
    actual = phase_a.get("result")
    if actual != expected:
        raise ValueError(
            "SDK consumption Phase-A result is inconsistent: "
            f"expected {expected}, observed {actual!r}"
        )
    if skip_provider_self_conformance:
        return "provider_sdk_consumption_development_rehearsal", [
            "provider_self_conformance"
        ]
    return "provider_sdk_consumption_pass", []


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON record must be an object: {path}")
    return value


def _inventory(root: Path) -> dict[str, Any]:
    if not root.is_dir():
        raise ValueError(f"install root is missing: {root}")
    records: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_symlink():
            resolved = path.resolve(strict=True)
            if not resolved.is_relative_to(root.resolve()):
                raise ValueError(f"installed symlink escapes its root: {path}")
            continue
        if path.is_file():
            records.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": inputs.sha256_file(path),
                }
            )
    if not records:
        raise ValueError("FacMan candidate install inventory is empty")
    return {
        "file_count": len(records),
        "sha256": sha256_bytes(canonical_bytes(records)),
    }


def _identity_paths(
    provider_work: Path, linkage: str, *, relocated: bool
) -> tuple[dict[str, Path], dict[str, Path]]:
    specs = {spec.provider_id: spec for spec in inputs.PROVIDERS}
    if relocated:
        prefixes = {
            provider_id: provider_work / "relocated" / linkage / provider_id
            for provider_id in specs
        }
    else:
        prefixes = {
            provider_id: provider_work / "provider-install" / provider_id / linkage
            for provider_id in specs
        }
    identities = {
        provider_id: prefix
        / inputs._identity_relative_path(specs[provider_id], f"installed_{linkage}")
        for provider_id, prefix in prefixes.items()
    }
    for provider_id in sorted(prefixes):
        inputs.validate_sdk_inventory_manifest(
            prefixes[provider_id], _load_json(identities[provider_id])
        )
    return prefixes, identities


def _candidate_command(
    facman_root: Path,
    build: Path,
    candidate_lock: Path,
    mode: semantics.Mode,
    sources: Mapping[str, inputs.ProviderSource],
    prefixes: Mapping[str, Path] | None,
    identities: Mapping[str, Path] | None,
    cmake: str,
    config: str,
    generator_platform: str | None,
    *,
    tracked_selection: bool = False,
) -> list[str]:
    command = [
        cmake,
        "-S",
        str(facman_root),
        "-B",
        str(build),
        f"-DCMAKE_BUILD_TYPE={config}",
        "-DFACMAN_BUILD_CLI=ON",
        "-DFACMAN_BUILD_TUI=OFF",
        "-DFACMAN_BUILD_DAEMON=OFF",
        "-DFACMAN_BUILD_GUI=OFF",
        "-DFACMAN_BUILD_TESTS=ON",
        "-DFACMAN_BUILD_PLAY_EVIDENCE_TOOLS=OFF",
        "-DFACMAN_WARNINGS_AS_ERRORS=ON",
        f"-DFACMAN_PROVIDER_MODE={mode.provider_mode}",
        f"-DFACMAN_PROVIDER_SOURCE_LINKAGE={mode.linkage if mode.provider_mode == 'source' else 'static'}",
        "-DFACMAN_PROVIDER_CONFORMANCE_ONLY=OFF",
        f"-DFACMAN_PROVIDER_SDK_CONSUMPTION_CANDIDATE={'OFF' if tracked_selection else 'ON'}",
    ]
    command.append(f"-DFACMAN_PROVIDER_LOCK_FILE={candidate_lock}")
    if mode.provider_mode == "source":
        command.extend(
            [
                f"-DFLAUNCH_UNIVERSAL_LAUNCHER_ROOT={sources['universal_launcher'].root}",
                f"-DFLAUNCH_UNIVERSAL_SETUP_ROOT={sources['universal_setup'].root}",
            ]
        )
    else:
        if prefixes is None or identities is None:
            raise ValueError("installed SDK candidate mode requires exact prefixes")
        inputs._validate_identity_pairing(prefixes, identities)
        command.extend(
            [
                f"-DFACMAN_UNIVERSAL_LAUNCHER_SDK_ROOT={prefixes['universal_launcher']}",
                f"-DFACMAN_UNIVERSAL_SETUP_SDK_ROOT={prefixes['universal_setup']}",
                f"-DFACMAN_UNIVERSAL_LAUNCHER_IDENTITY_FILE={identities['universal_launcher']}",
                f"-DFACMAN_UNIVERSAL_SETUP_IDENTITY_FILE={identities['universal_setup']}",
            ]
        )
    if generator_platform:
        command.extend(["-A", generator_platform])
    return command


def _build_identity(
    build: Path, *, tracked_selection: bool = False
) -> tuple[str, dict[str, str]]:
    path = build / "facman-build-identity.v1.txt"
    raw = path.read_bytes()
    text = raw.decode("utf-8", errors="strict").rstrip("\r\n")
    values: dict[str, str] = {}
    for segment in text.split(";"):
        key, separator, value = segment.partition("=")
        if separator != "=" or not key or not value or key in values:
            raise ValueError("candidate build identity is malformed")
        values[key] = value
    required = {
        "provider_lock_kind": "tracked" if tracked_selection else "sdk_candidate",
        "provider_conformance_only": "false",
        "provider_sdk_consumption_candidate": "false" if tracked_selection else "true",
        "provider_candidate_differs_from_tracked": "false",
        "provider_release_identity_coherent": "true",
    }
    for key, expected in required.items():
        if values.get(key) != expected:
            raise ValueError(f"candidate build identity {key} is not {expected}")
    return sha256_bytes(raw), values


def _runtime_environment(prefixes: Sequence[Path]) -> dict[str, str]:
    return inputs._runtime_environment(semantics._runtime_dirs(prefixes))


def _provider_runtime_files(
    runtime_files: Sequence[Path], provider_runtime_names: set[str]
) -> list[Path]:
    normalized_names = {name.casefold() for name in provider_runtime_names}
    return sorted(
        (path for path in runtime_files if path.name.casefold() in normalized_names),
        key=lambda path: path.as_posix(),
    )


def _runtime_closure(
    install_root: Path,
    mode: semantics.Mode,
    prefixes: Mapping[str, Path] | None,
    identities: Mapping[str, Mapping[str, Any]] | None,
    provider_runtime_names: set[str],
) -> dict[str, Any]:
    runtime_files = _provider_runtime_files(
        [
        path
        for path in install_root.rglob("*")
        if path.is_file() and inputs._is_runtime_library(path)
        ],
        provider_runtime_names,
    )
    actual = sorted(inputs.sha256_file(path) for path in runtime_files)
    expected: list[str] | None = []
    if mode.provider_mode == "source" and mode.linkage == "shared":
        expected = None
        if not actual:
            raise ValueError("source_shared install omitted its selected provider runtimes")
    elif mode.linkage == "shared" and prefixes is not None and identities is not None:
        expected = sorted(
            {
                inputs.sha256_file(path.resolve())
                for path in inputs._declared_shared_runtime_files(prefixes, identities)
            }
        )
    if expected is not None and actual != expected:
        raise ValueError(
            f"{mode.name} installed runtime closure differs from its selected providers"
        )
    return {
        "runtime_file_count": len(runtime_files),
        "runtime_sha256": sha256_bytes(canonical_bytes(actual)),
    }


def _configure_build_install_probe(
    facman_root: Path,
    work: Path,
    candidate_lock: Path,
    mode: semantics.Mode,
    sources: Mapping[str, inputs.ProviderSource],
    prefixes: Mapping[str, Path] | None,
    identity_paths: Mapping[str, Path] | None,
    environment: Mapping[str, str],
    runner: inputs.CommandRunner,
    cmake: str,
    config: str,
    generator_platform: str | None,
    *,
    tracked_selection: bool = False,
    directory_prefix: str = "candidate",
    semantic_workspace_root: Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
    build = work / f"{directory_prefix}-build" / mode.name
    install = work / f"{directory_prefix}-install" / mode.name
    runner.run(
        f"{mode.name}-configure",
        _candidate_command(
            facman_root,
            build,
            candidate_lock,
            mode,
            sources,
            prefixes,
            identity_paths,
            cmake,
            config,
            generator_platform,
            tracked_selection=tracked_selection,
        ),
        facman_root,
    )
    build_targets = [
        "facman_cli",
        "facman_provider_semantic_probe",
        "flb_factorio_shared",
    ]
    runner.run(
        f"{mode.name}-build",
        [
            cmake,
            "--build",
            str(build),
            "--config",
            config,
            "--parallel",
            "--target",
            *build_targets,
        ],
        facman_root,
    )
    runner.run(
        f"{mode.name}-install",
        [cmake, "--install", str(build), "--config", config, "--prefix", str(install)],
        facman_root,
    )
    workspace = (
        semantic_workspace_root / mode.name
        if semantic_workspace_root is not None
        else work / "semantic-workspaces" / mode.name
    )
    raw = semantics._run_probe(build, mode, workspace, environment, config, runner)
    normalized = semantics.validate_and_normalize_probe(
        raw, mode, workspace, semantics.load_corpus()
    )
    identity_sha, identity = _build_identity(
        build, tracked_selection=tracked_selection
    )
    return (
        {
            "raw_probe_sha256": sha256_bytes(canonical_bytes(raw)),
            "normalized": normalized,
        },
        {**_inventory(install), "build_identity_sha256": identity_sha},
        identity,
    )


def _write_observation(output: Path, observation: Mapping[str, Any]) -> None:
    inputs.assert_path_independent_json(observation)
    rendered = json.dumps(observation, indent=2, sort_keys=True) + "\n"
    (output / f"{OBSERVATION_STEM}.json").write_text(
        rendered, encoding="utf-8", newline="\n"
    )
    lines = [
        "# Provider SDK consumption observation",
        "",
        f"- Result: `{observation['result']}`",
        f"- FacMan: `{observation['facman']['commit']}`",
        f"- Platform: `{observation['platform']['system']} {observation['platform']['architecture']}`",
        f"- Normalized semantic SHA-256: `{observation['normalized_semantic_sha256']}`",
        "- Provider adoption: `false`",
        "- Release eligible: `false`",
        "- Product authority: `false`",
        "",
        "## Modes",
        "",
    ]
    lines.extend(
        f"- `{item['name']}`: `{item['result']}` — install `{item['install']['sha256']}`"
        for item in observation["modes"]
    )
    (output / f"{OBSERVATION_STEM}.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
    )


def _negative_controls(
    facman_root: Path,
    work: Path,
    candidate_lock: Path,
    sources: Mapping[str, inputs.ProviderSource],
    runner: inputs.CommandRunner,
    cmake: str,
    config: str,
    generator_platform: str | None,
) -> dict[str, str]:
    base = [
        cmake,
        "-S",
        str(facman_root),
        f"-DCMAKE_BUILD_TYPE={config}",
        f"-DFACMAN_PROVIDER_LOCK_FILE={candidate_lock}",
        "-DFACMAN_BUILD_TESTS=OFF",
        "-DFACMAN_BUILD_PLAY_EVIDENCE_TOOLS=OFF",
    ]
    platform_args = ["-A", generator_platform] if generator_platform else []
    controls = {
        "ambient_sdk_fallback": [
            *base,
            "-B",
            str(work / "negative/ambient-sdk-fallback"),
            "-DFACMAN_PROVIDER_MODE=installed_static",
            "-DFACMAN_PROVIDER_SDK_CONSUMPTION_CANDIDATE=ON",
            *platform_args,
        ],
        "candidate_lock_without_candidate_mode": [
            *base,
            "-B",
            str(work / "negative/candidate-lock-without-mode"),
            "-DFACMAN_PROVIDER_MODE=source",
            f"-DFLAUNCH_UNIVERSAL_LAUNCHER_ROOT={sources['universal_launcher'].root}",
            f"-DFLAUNCH_UNIVERSAL_SETUP_ROOT={sources['universal_setup'].root}",
            *platform_args,
        ],
        "conformance_mode_with_sdk_lock": [
            *base,
            "-B",
            str(work / "negative/conformance-with-sdk-lock"),
            "-DFACMAN_PROVIDER_MODE=source",
            "-DFACMAN_PROVIDER_CONFORMANCE_ONLY=ON",
            f"-DFLAUNCH_UNIVERSAL_LAUNCHER_ROOT={sources['universal_launcher'].root}",
            f"-DFLAUNCH_UNIVERSAL_SETUP_ROOT={sources['universal_setup'].root}",
            *platform_args,
        ],
    }
    for name, command in controls.items():
        runner.run(name, command, facman_root, expect_failure=True)
    return {name: "refused" for name in controls}


def execute(
    facman_root: Path,
    ulk_root: Path,
    usk_root: Path,
    work_dir: Path,
    output_dir: Path,
    *,
    cmake: str = "cmake",
    config: str = "Release",
    generator_platform: str | None = None,
    skip_provider_self_conformance: bool = False,
) -> dict[str, Any]:
    source_roots = [facman_root.resolve(), ulk_root.resolve(), usk_root.resolve()]
    output = inputs._external_directory(output_dir, source_roots, "output-dir")
    work = inputs._external_directory(work_dir, [*source_roots, output], "work-dir")
    runner = inputs.CommandRunner(output)
    phase_a_output = output / "provider-input-phase-a"
    provider_work = work / "provider-input"
    phase_a = inputs.execute(
        facman_root,
        ulk_root,
        usk_root,
        provider_work,
        phase_a_output,
        cmake=cmake,
        config=config,
        generator_platform=generator_platform,
        skip_provider_self_conformance=skip_provider_self_conformance,
    )
    result, required_skips = _classify_phase_a(
        phase_a,
        skip_provider_self_conformance=skip_provider_self_conformance,
    )
    roots = {
        "universal_launcher": ulk_root.resolve(),
        "universal_setup": usk_root.resolve(),
    }
    sources = {
        source.spec.provider_id: source
        for source in (
            inputs.observe_provider(spec, roots[spec.provider_id], runner)
            for spec in inputs.PROVIDERS
        )
    }
    expected_sources = phase_a.get("canonical_provider_sources")
    if expected_sources != inputs.canonical_provider_source_records(sources):
        raise ValueError("Phase-A evidence and live canonical provider sources disagree")
    truth_sets, lock_digests = inputs.provider_truth_sets(facman_root, sources)
    candidate_lock = work / "candidate/provider-sdk-consumption-lock.v1.toml"
    candidate_lock.parent.mkdir(parents=True, exist_ok=True)
    candidate_lock.write_text(
        inputs.candidate_lock_text(
            list(sources.values()),
            truth_sets["tracked_consumed"],
            candidate_class="sdk_consumption",
        ),
        encoding="utf-8",
        newline="\n",
    )

    prefix_sets: dict[tuple[str, bool], dict[str, Path]] = {}
    identity_sets: dict[tuple[str, bool], dict[str, Path]] = {}
    identity_values: dict[tuple[str, bool], dict[str, dict[str, Any]]] = {}
    for linkage in ("static", "shared"):
        for relocated in (False, True):
            prefixes, identity_paths = _identity_paths(
                provider_work, linkage, relocated=relocated
            )
            prefix_sets[(linkage, relocated)] = prefixes
            identity_sets[(linkage, relocated)] = identity_paths
            identity_values[(linkage, relocated)] = {
                provider_id: _load_json(path)
                for provider_id, path in identity_paths.items()
            }

    private_runtime, original_runtime = inputs._copy_private_runtime(
        prefix_sets[("shared", True)],
        identity_values[("shared", True)],
        work,
    )
    provider_runtime_names = {path.name for path in original_runtime}
    mode_semantics: dict[str, dict[str, Any]] = {}
    mode_records: list[dict[str, Any]] = []
    provider_roots = [ulk_root.resolve(), usk_root.resolve()]
    original_prefixes = [
        path for key, value in prefix_sets.items() if not key[1] for path in value.values()
    ]
    for mode in semantics.MODES:
        relocated = mode.name.startswith("relocated_") or mode.name == "private_runtime"
        prefixes = None
        identity_paths = None
        identity_value = None
        environment: dict[str, str] = {}
        if mode.provider_mode != "source":
            prefixes = prefix_sets[(mode.linkage, relocated)]
            identity_paths = identity_sets[(mode.linkage, relocated)]
            identity_value = identity_values[(mode.linkage, relocated)]
            environment = _runtime_environment(list(prefixes.values()))
        if mode.name == "source_shared":
            environment = _runtime_environment([work / "candidate-build" / mode.name])
        if mode.name == "private_runtime":
            environment = inputs._runtime_environment([private_runtime])

        def run_mode() -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
            return _configure_build_install_probe(
                facman_root,
                work,
                candidate_lock,
                mode,
                sources,
                prefixes,
                identity_paths,
                environment,
                runner,
                cmake,
                config,
                generator_platform,
            )

        if mode.provider_mode == "source":
            probe, install, build_identity = run_mode()
        elif relocated:
            with semantics.hidden_directories(provider_roots), semantics.hidden_directories(
                original_prefixes
            ):
                probe, install, build_identity = run_mode()
        else:
            with semantics.hidden_directories(provider_roots):
                probe, install, build_identity = run_mode()
        if mode.name == "private_runtime":
            with inputs._hidden_runtime_files(original_runtime), semantics.hidden_directories(
                list(prefixes.values()) if prefixes else []
            ):
                workspace = work / "semantic-workspaces-private-closure" / mode.name
                raw = semantics._run_probe(
                    work / "candidate-build" / mode.name,
                    mode,
                    workspace,
                    environment,
                    config,
                    runner,
                )
                probe["normalized"] = semantics.validate_and_normalize_probe(
                    raw, mode, workspace, semantics.load_corpus()
                )
                probe["raw_probe_sha256"] = sha256_bytes(canonical_bytes(raw))

        normalized = {
            **probe["normalized"],
            "release_resolution": semantics._release_projection(semantics.load_corpus()),
            "provider_contract_identity": semantics._provider_contract_projection(phase_a),
        }
        mode_semantics[mode.name] = normalized
        closure = _runtime_closure(
            work / "candidate-install" / mode.name,
            mode,
            prefixes,
            identity_value,
            provider_runtime_names,
        )
        expected_classification = (
            f"sdk_candidate_{mode.provider_mode}"
        )
        if build_identity.get("provider_mode") != mode.provider_mode or build_identity.get(
            "provider_consumption_classification"
        ) != expected_classification:
            raise ValueError(f"{mode.name} candidate build classification is inconsistent")
        mode_records.append(
            {
                "name": mode.name,
                "provider_mode": mode.provider_mode,
                "linkage": mode.linkage,
                "runtime_closure": mode.runtime,
                "raw_probe_sha256": probe["raw_probe_sha256"],
                "normalized_semantic_sha256": sha256_bytes(canonical_bytes(normalized)),
                "install": {**install, **closure},
                "result": "pass",
            }
        )

    normalized_digest = semantics.compare_semantics(mode_semantics)
    workspace_lock = facman_root / "release/index/workspace_lock.v1.toml"
    providers_lock = facman_root / "release/index/providers.lock.v2.toml"
    if inputs.sha256_file(workspace_lock) != lock_digests["workspace_lock_sha256"]:
        raise ValueError("workspace lock changed during SDK consumption")
    if inputs.sha256_file(providers_lock) != lock_digests["release_provider_lock_sha256"]:
        raise ValueError("release-provider lock changed during SDK consumption")
    facman_commit = semantics._git_value(facman_root, "HEAD", runner)
    facman_tree = semantics._git_value(facman_root, "HEAD^{tree}", runner)
    phase_a_path = phase_a_output / "provider-conformance-observation.v1.json"
    negative_controls = _negative_controls(
        facman_root,
        work,
        candidate_lock,
        sources,
        runner,
        cmake,
        config,
        generator_platform,
    )
    negative_controls.update(
        {
            "missing_shared_runtime": phase_a["negative_controls"]["missing_shared_runtime"],
            "partial_sdk_tree": phase_a["negative_controls"]["partial_sdk_tree"],
            "stale_relocation_metadata": phase_a["negative_controls"]["stale_relocation_metadata"],
            "undeclared_runtime_dependency": phase_a["negative_controls"]["undeclared_runtime_dependency"],
        }
    )
    observation: dict[str, Any] = {
        "schema": SCHEMA,
        "observed_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "result": result,
        "facman": {"commit": facman_commit, "tree": facman_tree},
        "platform": {
            "system": platform.system(),
            "architecture": platform.machine(),
            "runner_os": os.environ.get("RUNNER_OS", "local"),
            "runner_arch": os.environ.get("RUNNER_ARCH", platform.machine()),
        },
        "providers": [
            {"id": provider_id, **record}
            for provider_id, record in sorted(expected_sources.items())
        ],
        "provider_input_observation": {
            "path": "provider-input-phase-a/provider-conformance-observation.v1.json",
            "sha256": inputs.sha256_file(phase_a_path),
        },
        "tracked_lock_records": phase_a["tracked_lock_records"],
        "candidate_lock": {
            "sha256": inputs.sha256_file(candidate_lock),
            "sdk_consumption_candidate": True,
            "candidate_not_adopted": True,
            "release_eligible": False,
            "tracked_lock_mutated": False,
        },
        "modes": mode_records,
        "normalized_semantic_sha256": normalized_digest,
        "negative_controls": negative_controls,
        "required_skips": required_skips,
        "source_mode_rollback_proven": True,
        "installed_modes_source_independent": True,
        "tracked_lock_mutated": False,
        "provider_adoption": False,
        "provider_repin": False,
        "release_eligible": False,
        "authority": dict(AUTHORITY),
    }
    inputs.validate_authority(observation["authority"])
    _write_observation(output, observation)
    return observation


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--facman-root", type=Path, default=ROOT)
    parser.add_argument("--ulk-root", type=Path, required=True)
    parser.add_argument("--usk-root", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cmake", default="cmake")
    parser.add_argument("--config", default="Release")
    parser.add_argument("--platform", dest="generator_platform")
    parser.add_argument("--skip-provider-self-conformance", action="store_true")
    args = parser.parse_args(argv)
    try:
        observation = execute(
            args.facman_root.resolve(),
            args.ulk_root.resolve(),
            args.usk_root.resolve(),
            args.work_dir.resolve(),
            args.output_dir.resolve(),
            cmake=args.cmake,
            config=args.config,
            generator_platform=args.generator_platform,
            skip_provider_self_conformance=args.skip_provider_self_conformance,
        )
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        print(f"provider-sdk-consumption: {error}", file=sys.stderr)
        return 1
    print(
        f"provider-sdk-consumption: {observation['result']} "
        f"{observation['normalized_semantic_sha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
