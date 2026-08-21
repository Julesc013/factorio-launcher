# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Prove all provider modes through the atomically reconciled tracked lock."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import platform
import sys
from pathlib import Path
from typing import Any, Mapping

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import provider_conformance as inputs  # noqa: E402
from tools import provider_sdk_consumption as consumption  # noqa: E402
from tools import provider_semantic_conformance as semantics  # noqa: E402
from tools.release_compiler.canonical import canonical_bytes  # noqa: E402


SCHEMA = "facman.provider_reconciled_consumption_observation.v1"
OBSERVATION_STEM = "provider-reconciled-consumption-observation.v1"
AUTHORITY = {
    "factorio_execution": False,
    "observer_capture": False,
    "permit_issuance": False,
    "publication": False,
    "route_promotion": False,
    "setup_mutation": False,
    "signing": False,
}


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON record must be an object: {path}")
    return value


def _validate_sdk_consumption_observation(
    path: Path, *, allow_development_rehearsal: bool
) -> tuple[dict[str, Any], bool]:
    value = _load_json(path)
    schema = _load_json(
        ROOT / "contracts/schema/release/provider_sdk_consumption.v1.schema.json"
    )
    jsonschema.Draft202012Validator(schema).validate(value)
    result = value.get("result")
    rehearsal = result == "provider_sdk_consumption_development_rehearsal"
    if result != "provider_sdk_consumption_pass" and not (
        rehearsal and allow_development_rehearsal
    ):
        raise ValueError("tracked reconciliation requires a complete SDK-consumption pass")
    if value.get("provider_adoption") is not False or value.get("provider_repin") is not False:
        raise ValueError("input SDK-consumption evidence must remain non-adopting")
    if any(value.get("authority", {}).values()):
        raise ValueError("input SDK-consumption evidence grants authority")
    return value, rehearsal


def _write_observation(output: Path, observation: Mapping[str, Any]) -> None:
    inputs.assert_path_independent_json(observation)
    rendered = json.dumps(observation, indent=2, sort_keys=True) + "\n"
    (output / f"{OBSERVATION_STEM}.json").write_text(
        rendered, encoding="utf-8", newline="\n"
    )
    lines = [
        "# Reconciled provider consumption observation",
        "",
        f"- Result: `{observation['result']}`",
        f"- FacMan: `{observation['facman']['commit']}`",
        f"- Platform: `{observation['platform']['system']} {observation['platform']['architecture']}`",
        f"- Normalized semantic SHA-256: `{observation['normalized_semantic_sha256']}`",
        "- Provider input selection: `accepted canonical set`",
        "- Release source coherent: `true`",
        "- Release eligible: `false`",
        "- Product authority: `false`",
        "",
        "## Modes",
        "",
    ]
    lines.extend(
        f"- `{item['name']}`: `{item['consumption_classification']}` — `{item['result']}`"
        for item in observation["modes"]
    )
    (output / f"{OBSERVATION_STEM}.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
    )


def execute(
    facman_root: Path,
    ulk_root: Path,
    usk_root: Path,
    provider_work_dir: Path,
    sdk_observation_path: Path,
    work_dir: Path,
    output_dir: Path,
    *,
    cmake: str = "cmake",
    config: str = "Release",
    generator_platform: str | None = None,
    allow_development_rehearsal: bool = False,
    resume_existing_work: bool = False,
) -> dict[str, Any]:
    source_roots = [facman_root.resolve(), ulk_root.resolve(), usk_root.resolve()]
    output = inputs._external_directory(output_dir, source_roots, "output-dir")
    if resume_existing_work:
        work = work_dir.resolve()
        if not work.is_dir():
            raise ValueError("--resume-existing-work requires an existing work directory")
        for protected_root in [*source_roots, output]:
            protected = protected_root.resolve()
            if (
                work == protected
                or work.is_relative_to(protected)
                or protected.is_relative_to(work)
            ):
                raise ValueError("resumed work directory overlaps a source or output root")
    else:
        work = inputs._external_directory(work_dir, [*source_roots, output], "work-dir")
    provider_work = provider_work_dir.resolve()
    if not provider_work.is_dir():
        raise ValueError(f"provider SDK work directory is missing: {provider_work}")
    sdk_observation_path = sdk_observation_path.resolve()
    sdk_observation, development_rehearsal = _validate_sdk_consumption_observation(
        sdk_observation_path,
        allow_development_rehearsal=allow_development_rehearsal,
    )
    phase_a_path = (
        sdk_observation_path.parent
        / str(sdk_observation["provider_input_observation"]["path"])
    ).resolve()
    if inputs.sha256_file(phase_a_path) != sdk_observation["provider_input_observation"]["sha256"]:
        raise ValueError("SDK-consumption evidence does not bind its Phase-A observation")
    phase_a = _load_json(phase_a_path)

    runner = inputs.CommandRunner(output)
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
    expected_sources = inputs.canonical_provider_source_records(sources)
    observed_sources = {
        str(row["id"]): {
            key: row[key]
            for key in ("commit", "tree", "remote", "canonical_main_ref")
        }
        for row in sdk_observation["providers"]
    }
    if observed_sources != expected_sources:
        raise ValueError("live provider sources differ from accepted SDK-consumption evidence")

    tracked_lock = facman_root / "release/index/workspace_lock.v1.toml"
    release_lock = facman_root / "release/index/providers.lock.v2.toml"
    lock_sha_before = {
        "workspace": inputs.sha256_file(tracked_lock),
        "release_provider": inputs.sha256_file(release_lock),
    }

    prefix_sets: dict[tuple[str, bool], dict[str, Path]] = {}
    identity_sets: dict[tuple[str, bool], dict[str, Path]] = {}
    identity_values: dict[tuple[str, bool], dict[str, dict[str, Any]]] = {}
    for linkage in ("static", "shared"):
        for relocated in (False, True):
            prefixes, identities = consumption._identity_paths(
                provider_work, linkage, relocated=relocated
            )
            prefix_sets[(linkage, relocated)] = prefixes
            identity_sets[(linkage, relocated)] = identities
            identity_values[(linkage, relocated)] = {
                provider_id: _load_json(path)
                for provider_id, path in identities.items()
            }
            for provider_id, identity_path in identities.items():
                phase_a_key = f"{provider_id}_installed_{linkage}"
                phase_a_identity = phase_a.get("provider_identities", {}).get(
                    phase_a_key, {}
                )
                if inputs.sha256_file(identity_path) != phase_a_identity.get("sha256"):
                    raise ValueError(
                        f"live {phase_a_key} SDK identity differs from Phase-A evidence"
                    )

    private_runtime, original_runtime = inputs._copy_private_runtime(
        prefix_sets[("shared", True)], identity_values[("shared", True)], work
    )
    provider_runtime_names = {path.name for path in original_runtime}
    semantic_workspace_root = work / "semantic-workspace-runs" / output.name
    provider_roots = [ulk_root.resolve(), usk_root.resolve()]
    original_prefixes = [
        path
        for key, value in prefix_sets.items()
        if not key[1]
        for path in value.values()
    ]
    mode_semantics: dict[str, dict[str, Any]] = {}
    mode_records: list[dict[str, Any]] = []
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
            environment = consumption._runtime_environment(list(prefixes.values()))
        if mode.name == "source_shared":
            environment = consumption._runtime_environment(
                [work / "reconciled-build" / mode.name]
            )
        if mode.name == "private_runtime":
            environment = inputs._runtime_environment([private_runtime])

        def run_mode() -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
            return consumption._configure_build_install_probe(
                facman_root,
                work,
                tracked_lock,
                mode,
                sources,
                prefixes,
                identity_paths,
                environment,
                runner,
                cmake,
                config,
                generator_platform,
                tracked_selection=True,
                directory_prefix="reconciled",
                semantic_workspace_root=semantic_workspace_root,
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
            if prefixes is None:
                raise ValueError("private-runtime mode has no installed prefixes")
            with inputs._hidden_runtime_files(original_runtime), semantics.hidden_directories(
                list(prefixes.values())
            ):
                workspace = semantic_workspace_root / "private-closure" / mode.name
                raw = semantics._run_probe(
                    work / "reconciled-build" / mode.name,
                    mode,
                    workspace,
                    environment,
                    config,
                    runner,
                )
                probe["normalized"] = semantics.validate_and_normalize_probe(
                    raw, mode, workspace, semantics.load_corpus()
                )
                probe["raw_probe_sha256"] = consumption.sha256_bytes(
                    canonical_bytes(raw)
                )

        normalized = {
            **probe["normalized"],
            "release_resolution": semantics._release_projection(semantics.load_corpus()),
            "provider_contract_identity": semantics._provider_contract_projection(phase_a),
        }
        mode_semantics[mode.name] = normalized
        closure = consumption._runtime_closure(
            work / "reconciled-install" / mode.name,
            mode,
            prefixes,
            identity_value,
            provider_runtime_names,
        )
        expected_classification = (
            "tracked_source"
            if mode.provider_mode == "source"
            else f"tracked_adopted_{mode.provider_mode}"
        )
        if (
            build_identity.get("provider_mode") != mode.provider_mode
            or build_identity.get("provider_consumption_classification")
            != expected_classification
        ):
            raise ValueError(
                f"{mode.name} tracked build classification is inconsistent"
            )
        mode_records.append(
            {
                "name": mode.name,
                "provider_mode": mode.provider_mode,
                "linkage": mode.linkage,
                "runtime_closure": mode.runtime,
                "consumption_classification": expected_classification,
                "raw_probe_sha256": probe["raw_probe_sha256"],
                "normalized_semantic_sha256": consumption.sha256_bytes(
                    canonical_bytes(normalized)
                ),
                "install": {**install, **closure},
                "result": "pass",
            }
        )

    normalized_digest = semantics.compare_semantics(mode_semantics)
    lock_sha_after = {
        "workspace": inputs.sha256_file(tracked_lock),
        "release_provider": inputs.sha256_file(release_lock),
    }
    if lock_sha_after != lock_sha_before:
        raise ValueError("tracked provider locks changed during reconciled consumption")
    facman_commit = semantics._git_value(facman_root, "HEAD", runner)
    facman_tree = semantics._git_value(facman_root, "HEAD^{tree}", runner)
    observation: dict[str, Any] = {
        "schema": SCHEMA,
        "observed_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "result": (
            "provider_reconciled_consumption_development_rehearsal"
            if development_rehearsal
            else "provider_reconciled_consumption_pass"
        ),
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
        "sdk_consumption_observation": {
            "path": "provider-sdk-consumption-observation.v1.json",
            "sha256": inputs.sha256_file(sdk_observation_path),
        },
        "tracked_lock_records": {
            "workspace": {
                "path": "release/index/workspace_lock.v1.toml",
                "sha256": lock_sha_before["workspace"],
            },
            "release_provider": {
                "path": "release/index/providers.lock.v2.toml",
                "sha256": lock_sha_before["release_provider"],
            },
        },
        "modes": mode_records,
        "normalized_semantic_sha256": normalized_digest,
        "source_mode_rollback_proven": True,
        "installed_modes_source_independent": True,
        "provider_input_selection": "accepted_canonical_provider_set",
        "provider_input_adopted": True,
        "provider_repin": True,
        "release_source_coherent": True,
        "release_eligible": False,
        "resumed_work": resume_existing_work,
        "required_skips": (
            ["provider_self_conformance"] if development_rehearsal else []
        ),
        "authority": dict(AUTHORITY),
    }
    if any(observation["authority"].values()):
        raise ValueError("reconciled consumption observation grants authority")
    _write_observation(output, observation)
    return observation


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--facman-root", type=Path, default=ROOT)
    parser.add_argument("--ulk-root", type=Path, required=True)
    parser.add_argument("--usk-root", type=Path, required=True)
    parser.add_argument("--provider-work-dir", type=Path, required=True)
    parser.add_argument("--sdk-observation", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cmake", default="cmake")
    parser.add_argument("--config", default="Release")
    parser.add_argument("--platform", dest="generator_platform")
    parser.add_argument("--allow-development-rehearsal", action="store_true")
    parser.add_argument("--resume-existing-work", action="store_true")
    args = parser.parse_args(argv)
    try:
        observation = execute(
            args.facman_root.resolve(),
            args.ulk_root.resolve(),
            args.usk_root.resolve(),
            args.provider_work_dir.resolve(),
            args.sdk_observation.resolve(),
            args.work_dir.resolve(),
            args.output_dir.resolve(),
            cmake=args.cmake,
            config=args.config,
            generator_platform=args.generator_platform,
            allow_development_rehearsal=args.allow_development_rehearsal,
            resume_existing_work=args.resume_existing_work,
        )
    except (
        OSError,
        RuntimeError,
        ValueError,
        json.JSONDecodeError,
        jsonschema.ValidationError,
    ) as error:
        print(f"provider-reconciled-consumption: {error}", file=sys.stderr)
        return 1
    print(
        "provider-reconciled-consumption: pass "
        f"{observation['normalized_semantic_sha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
