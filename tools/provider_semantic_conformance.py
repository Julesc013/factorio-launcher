# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Prove normalized FacMan semantics across exact source and installed providers."""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import os
import platform
import re
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import provider_conformance as inputs
from tools.release_compiler.canonical import canonical_bytes, domain_digest_value
from tools.release_compiler.compiler import load_inputs, resolve
from tools.release_compiler.outputs import validate_resolution
from tools.release_compiler.source_observation import synthetic_source_observation


SCHEMA = "facman.provider_semantic_conformance_observation.v1"
MODE_RESULT_SCHEMA = "facman.provider_semantic_mode_result.v1"
PROBE_SCHEMA = "facman.provider_semantic_probe.v1"
OBSERVATION_STEM = "provider-semantic-conformance-observation.v1"
CORPUS_PATH = ROOT / "tests/fixtures/provider-semantic-conformance/corpus.v1.json"
HEX_40 = re.compile(r"^[0-9a-f]{40}$")
HEX_64 = re.compile(r"^[0-9a-f]{64}$")
NORMALIZATION_POLICY = {
    "schema": "facman.provider_semantic_normalization_policy.v1",
    "allowed_differences": [
        "provider_mode",
        "provider_linkage",
        "probe_workspace",
        "build_location",
        "executable_location",
    ],
    "normalized_fields": ["provider_mode", "linkage", "workspace"],
    "material_fields_never_normalized": [
        "authority",
        "capabilities",
        "command_dispatch",
        "contract_identity",
        "effects_may_have_occurred",
        "interrupted_recovery",
        "operation_outcomes",
        "release_resolution",
        "structured_refusals",
    ],
    "unknown_absolute_paths": "refuse",
    "unknown_fields": "refuse",
    "forged_normalization_markers": "refuse",
}
SEMANTIC_CLASSES = (
    "command_dispatch",
    "operation_outcomes",
    "structured_refusals",
    "interrupted_recovery",
    "release_resolution",
    "provider_contract_identity",
)


@dataclass(frozen=True)
class Mode:
    name: str
    build_label: str
    provider_mode: str
    linkage: str
    runtime: str


MODES = (
    Mode("source_static", "source", "source", "static", "build_tree"),
    Mode("source_shared", "source_shared", "source", "shared", "build_tree"),
    Mode("installed_static", "installed_static", "installed_static", "static", "installed_prefix"),
    Mode("installed_shared", "installed_shared", "installed_shared", "shared", "installed_prefix"),
    Mode(
        "relocated_installed_static",
        "relocated_static",
        "installed_static",
        "static",
        "relocated_prefix",
    ),
    Mode(
        "relocated_installed_shared",
        "relocated_shared",
        "installed_shared",
        "shared",
        "relocated_prefix",
    ),
    Mode("private_runtime", "private_runtime", "installed_shared", "shared", "private_runtime"),
)


def sha256_bytes(value: bytes) -> str:
    import hashlib

    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return inputs.sha256_file(path)


def load_corpus(path: Path = CORPUS_PATH) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema") != "facman.provider_semantic_corpus.v1":
        raise ValueError("semantic corpus has the wrong schema")
    if value.get("corpus_id") != "facman-provider-semantic-corpus-01":
        raise ValueError("semantic corpus identity is not exact")
    expected_counts = {
        "command_dispatch": 3,
        "operation_outcomes": 8,
        "structured_refusals": 4,
    }
    for key, count in expected_counts.items():
        rows = value.get(key)
        if not isinstance(rows, list) or len(rows) != count:
            raise ValueError(f"semantic corpus {key} is incomplete")
        identities = [row.get("id") for row in rows if isinstance(row, dict)]
        if len(identities) != count or len(set(identities)) != count:
            raise ValueError(f"semantic corpus {key} identities are not exact")
    recovery = value.get("interrupted_recovery")
    if not isinstance(recovery, dict) or recovery.get("idempotent_reinspection") is not True:
        raise ValueError("semantic recovery corpus is incomplete")
    targets = value.get("release_targets")
    if not isinstance(targets, dict) or set(targets) != {"Linux", "Windows", "Darwin"}:
        raise ValueError("semantic release target map is incomplete")
    return value


def normalization_policy_digest() -> str:
    return domain_digest_value(
        "facman.provider_semantic_normalization_policy.v1",
        NORMALIZATION_POLICY,
    )


def _contains_marker(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_contains_marker(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_marker(item) for item in value)
    return isinstance(value, str) and re.search(r"<[^<>]+>", value) is not None


def validate_and_normalize_probe(
    value: Mapping[str, Any], mode: Mode, workspace: Path, corpus: Mapping[str, Any]
) -> dict[str, Any]:
    if set(value) != {"schema", "provider_mode", "linkage", "workspace", "semantics"}:
        raise ValueError("semantic probe contains unknown or missing fields")
    if value.get("schema") != PROBE_SCHEMA:
        raise ValueError("semantic probe has the wrong schema")
    if value.get("provider_mode") != mode.name or value.get("linkage") != mode.linkage:
        raise ValueError("semantic probe mode/linkage identity differs from its invocation")
    if value.get("workspace") != str(workspace):
        raise ValueError("semantic probe workspace is not the exact approved workspace")
    if _contains_marker(value):
        raise ValueError("forged normalization marker is forbidden")
    semantics = value.get("semantics")
    if not isinstance(semantics, dict) or set(semantics) != {
        "command_dispatch",
        "operation_outcomes",
        "structured_refusals",
        "interrupted_recovery",
    }:
        raise ValueError("semantic probe classes are incomplete or unknown")
    inputs.assert_path_independent_json(semantics)

    command_expectations = {row["id"]: row for row in corpus["command_dispatch"]}
    operation_expectations = {row["id"]: row for row in corpus["operation_outcomes"]}
    refusal_expectations = {row["id"]: row for row in corpus["structured_refusals"]}
    actual_commands = _rows_by_id(semantics["command_dispatch"], "command dispatch")
    actual_operations = _rows_by_id(semantics["operation_outcomes"], "operation outcomes")
    actual_refusals = _rows_by_id(semantics["structured_refusals"], "structured refusals")
    if set(actual_commands) != set(command_expectations):
        raise ValueError("semantic command corpus differs from the reviewed corpus")
    if set(actual_operations) != set(operation_expectations):
        raise ValueError("semantic operation corpus differs from the reviewed corpus")
    if set(actual_refusals) != set(refusal_expectations):
        raise ValueError("semantic refusal corpus differs from the reviewed corpus")
    for identity, expected in command_expectations.items():
        actual = actual_commands[identity]
        if actual.get("command") != expected["command"] or actual.get("status") != expected["expected_status"]:
            raise ValueError(f"command semantic result differs for {identity}")
    for identity, expected in operation_expectations.items():
        actual = actual_operations[identity]
        if actual.get("terminal_outcome") != expected["outcome"] or actual.get(
            "effects_may_have_occurred"
        ) is not expected["effects_may_have_occurred"]:
            raise ValueError(f"operation semantic result differs for {identity}")
        if not actual.get("operation_id") or not actual.get("attempt_id"):
            raise ValueError(f"operation semantic identity is missing for {identity}")
    for identity, expected in refusal_expectations.items():
        actual = actual_refusals[identity]
        for key in (
            "code",
            "owner",
            "safe_next_action",
            "effect_classification",
            "diagnostic_category",
        ):
            if actual.get(key) != expected[key]:
                raise ValueError(f"structured refusal {identity} differs at {key}")
        if not actual.get("reason"):
            raise ValueError(f"structured refusal {identity} has no reason")
    if semantics["interrupted_recovery"] != corpus["interrupted_recovery"]:
        raise ValueError("interrupted recovery projection differs from the reviewed corpus")
    return copy.deepcopy(semantics)


def _rows_by_id(value: Any, label: str) -> dict[str, dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    output: dict[str, dict[str, Any]] = {}
    for row in value:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            raise ValueError(f"{label} contains an invalid row")
        identity = row["id"]
        if identity in output:
            raise ValueError(f"{label} contains a duplicate identity")
        output[identity] = row
    return output


def compare_semantics(results: Mapping[str, Mapping[str, Any]]) -> str:
    if set(results) != {mode.name for mode in MODES}:
        raise ValueError("semantic result mode set is incomplete")
    digests = {
        name: sha256_bytes(canonical_bytes(value)) for name, value in results.items()
    }
    if len(set(digests.values())) != 1:
        baseline = MODES[0].name
        changed = sorted(name for name in results if digests[name] != digests[baseline])
        raise ValueError(f"normalized semantic results differ across modes: {changed}")
    return next(iter(digests.values()))


def negative_controls(baseline: Mapping[str, Any]) -> dict[str, str]:
    def must_differ(name: str, mutate: Any) -> None:
        candidates = {mode.name: copy.deepcopy(baseline) for mode in MODES}
        mutate(candidates[MODES[-1].name])
        try:
            compare_semantics(candidates)
        except ValueError:
            controls[name] = "refused"
            return
        raise ValueError(f"semantic negative control was accepted: {name}")

    controls: dict[str, str] = {}
    must_differ(
        "changed_command_availability",
        lambda value: value["command_dispatch"][0].__setitem__("status", "refused"),
    )
    must_differ(
        "changed_operation_outcome",
        lambda value: value["operation_outcomes"][0].__setitem__(
            "terminal_outcome", "outcome_unknown"
        ),
    )
    must_differ(
        "changed_effects_classification",
        lambda value: value["operation_outcomes"][0].__setitem__(
            "effects_may_have_occurred", True
        ),
    )
    must_differ(
        "changed_refusal_code",
        lambda value: value["structured_refusals"][0].__setitem__("code", "forged"),
    )
    must_differ(
        "changed_recovery_action",
        lambda value: value["interrupted_recovery"].__setitem__(
            "available_recovery_action", "apply_without_review"
        ),
    )
    must_differ(
        "changed_release_resolution_root",
        lambda value: value["release_resolution"].__setitem__("root_digest", "0" * 64),
    )
    must_differ(
        "changed_provider_contract_identity",
        lambda value: value["provider_contract_identity"][0].__setitem__(
            "contract_digest", "0" * 64
        ),
    )
    must_differ(
        "changed_authority",
        lambda value: value["release_resolution"]["authority"].__setitem__(
            "product_authority_granted", True
        ),
    )
    return controls


def normalization_negative_controls(
    raw_probe: Mapping[str, Any],
    mode: Mode,
    workspace: Path,
    corpus: Mapping[str, Any],
) -> dict[str, str]:
    controls: dict[str, str] = {}

    def must_refuse(name: str, candidate: Mapping[str, Any]) -> None:
        try:
            validate_and_normalize_probe(candidate, mode, workspace, corpus)
        except ValueError:
            controls[name] = "refused"
            return
        raise ValueError(f"normalization negative control was accepted: {name}")

    unknown_path = copy.deepcopy(raw_probe)
    unknown_path["semantics"]["structured_refusals"][0]["reason"] = str(
        workspace / "forbidden-leak"
    )
    must_refuse("unknown_absolute_path", unknown_path)
    unknown_field = copy.deepcopy(raw_probe)
    unknown_field["future_mode_field"] = "unreviewed"
    must_refuse("unknown_mode_dependent_field", unknown_field)
    forged_marker = copy.deepcopy(raw_probe)
    forged_marker["workspace"] = "<mode-workspace>"
    must_refuse("forged_normalization_marker", forged_marker)
    return controls


def _git_value(root: Path, argument: str, runner: inputs.CommandRunner) -> str:
    return runner.run(
        f"facman-{argument.replace('^', '-tree')}",
        ["git", "-c", f"safe.directory={root}", "-C", str(root), "rev-parse", argument],
        root,
    ).output.strip()


def _find_probe(build: Path, config: str) -> Path:
    names = {"facman_provider_semantic_probe", "facman_provider_semantic_probe.exe"}
    candidates = [path for path in build.rglob("*") if path.is_file() and path.name in names]
    if not candidates:
        raise ValueError(f"semantic probe was not produced by {build.name}")
    candidates.sort(
        key=lambda path: (
            0 if config.casefold() in {part.casefold() for part in path.parts} else 1,
            len(path.parts),
            path.as_posix(),
        )
    )
    return candidates[0]


def _runtime_dirs(prefixes: Sequence[Path]) -> list[Path]:
    return [
        directory
        for prefix in prefixes
        for directory in (prefix / "bin", prefix / "lib", prefix / "lib64")
        if directory.is_dir()
    ]


def _build_tree_runtime_dirs(build: Path) -> list[Path]:
    directories = {
        path.parent.resolve()
        for path in build.rglob("*")
        if (path.is_file() or path.is_symlink()) and inputs._is_runtime_library(path)
    }
    return sorted(directories, key=lambda path: path.as_posix())


@contextmanager
def hidden_directories(paths: Sequence[Path]) -> Iterator[None]:
    moved: list[tuple[Path, Path]] = []
    try:
        for path in paths:
            resolved = path.resolve()
            hidden = resolved.with_name(resolved.name + ".facman-semantic-hidden")
            if not resolved.is_dir() or os.path.lexists(hidden):
                raise ValueError(f"semantic hidden-directory boundary is invalid: {resolved.name}")
            resolved.rename(hidden)
            moved.append((resolved, hidden))
        yield
    finally:
        for original, hidden in reversed(moved):
            if os.path.lexists(hidden):
                hidden.rename(original)


def _build_probe(build: Path, mode: Mode, cmake: str, config: str, runner: inputs.CommandRunner) -> None:
    runner.run(
        f"semantic-{mode.name}-build",
        [
            cmake,
            "--build",
            str(build),
            "--config",
            config,
            "--parallel",
            "--target",
            "facman_provider_semantic_probe",
        ],
        ROOT,
    )


def _run_probe(
    build: Path,
    mode: Mode,
    workspace: Path,
    environment: Mapping[str, str],
    config: str,
    runner: inputs.CommandRunner,
) -> dict[str, Any]:
    result = runner.run(
        f"semantic-{mode.name}-probe",
        [
            str(_find_probe(build, config)),
            "--workspace",
            str(workspace),
            "--mode",
            mode.name,
            "--linkage",
            mode.linkage,
        ],
        ROOT,
        environment=environment,
    )
    return inputs.extract_last_json_object(result.output)


def _release_projection(corpus: Mapping[str, Any]) -> dict[str, Any]:
    system = platform.system()
    target = corpus["release_targets"].get(system)
    if not isinstance(target, str):
        raise ValueError(f"semantic release model has no target for {system}")
    compiler_inputs = load_inputs(ROOT / "release/index", ROOT)
    observation = synthetic_source_observation(compiler_inputs.model)
    outputs = resolve(compiler_inputs, target, observation)
    validate_resolution(outputs, ROOT)
    authority = outputs["authority"]
    if authority.get("product_authority_granted") is not False:
        raise ValueError("semantic release projection promoted product authority")
    return {
        "target_id": target,
        "observation_class": "synthetic_validation",
        "root_digest": outputs["resolution_set"]["root_digest"],
        "composition": outputs["composition"],
        "components": outputs["components"],
        "entrypoints": outputs["entrypoints"],
        "paths": outputs["paths"],
        "authority": authority,
        "claims": outputs["claims"],
        "compatibility": outputs["compatibility"],
        "package_plan": outputs["package_plan"],
        "qualification_plan": outputs["qualification_plan"],
    }


def _provider_contract_projection(phase_a: Mapping[str, Any]) -> list[dict[str, Any]]:
    records = []
    for provider_id, provider in sorted(phase_a["canonical_provider_sources"].items()):
        sdk = phase_a["provider_identities"][f"{provider_id}_installed_static"]
        records.append(
            {
                "id": provider_id,
                "source_commit": provider["commit"],
                "source_tree": provider["tree"],
                "package_version": sdk["package_version"],
                "abi_version": sdk["abi_version"],
                "contract_set_id": sdk["contract_set_id"],
                "contract_digest": sdk["contract_digest"],
            }
        )
    return sorted(records, key=lambda item: item["id"])


def _sdk_identity_projection(phase_a: Mapping[str, Any], linkage: str) -> list[dict[str, Any]]:
    values = []
    for provider_id in ("universal_launcher", "universal_setup"):
        key = f"{provider_id}_installed_{linkage}"
        record = phase_a["provider_identities"][key]
        values.append(
            {
                "id": provider_id,
                "identity_sha256": record["sha256"],
                "inventory_sha256": record["install_inventory_sha256"],
                "abi_manifest_sha256": record["abi_manifest_sha256"],
                "contract_bundle_sha256": record["contract_bundle_sha256"],
            }
        )
    return values


def _write_mode_result(
    output: Path,
    mode: Mode,
    raw_probe_sha256: str,
    semantics: Mapping[str, Any],
) -> tuple[str, int]:
    value = {
        "schema": MODE_RESULT_SCHEMA,
        "mode": mode.name,
        "provider_mode": mode.provider_mode,
        "linkage": mode.linkage,
        "runtime_closure": mode.runtime,
        "raw_result_sha256": raw_probe_sha256,
        "normalized_semantic_sha256": sha256_bytes(canonical_bytes(semantics)),
        "semantics": semantics,
        "authority": dict(inputs.AUTHORITY),
    }
    inputs.validate_authority(value["authority"])
    inputs.assert_path_independent_json(value)
    destination = output / "semantic-results" / f"{mode.name}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(value, indent=2, sort_keys=True) + "\n"
    destination.write_text(rendered, encoding="utf-8", newline="\n")
    return sha256_bytes(rendered.encode("utf-8")), len(rendered.encode("utf-8"))


def _markdown(observation: Mapping[str, Any]) -> str:
    lines = [
        "# Provider semantic conformance observation",
        "",
        f"- Result: `{observation['result']}`",
        f"- FacMan: `{observation['facman']['commit']}`",
        f"- Platform: `{observation['platform']['system']} {observation['platform']['architecture']}`",
        f"- Corpus SHA-256: `{observation['corpus']['sha256']}`",
        f"- Normalized semantic SHA-256: `{observation['normalized_semantic_sha256']}`",
        "- Required skips: `0`",
        "- Provider adoption: `false`",
        "- Release eligible: `false`",
        "- Factorio execution: `false`",
        "- Setup mutation: `false`",
        "- Signing/publication: `false`",
        "",
        "## Modes",
        "",
    ]
    for value in observation["modes"]:
        lines.append(
            f"- `{value['name']}`: `pass` — raw `{value['raw_result_sha256']}`, normalized `{value['normalized_semantic_sha256']}`"
        )
    lines.extend(["", "## Semantic classes", ""])
    for name, result in observation["semantic_classes"].items():
        lines.append(f"- `{name}`: `{result}`")
    lines.extend(["", "## Negative controls", ""])
    for name, result in sorted(observation["negative_controls"].items()):
        lines.append(f"- `{name}`: `{result}`")
    lines.append("")
    return "\n".join(lines)


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
    work = inputs._external_directory(work_dir, source_roots + [output], "work-dir")
    phase_a_output = output / "provider-input-phase-a"
    phase_a = inputs.execute(
        facman_root,
        ulk_root,
        usk_root,
        work,
        phase_a_output,
        cmake=cmake,
        config=config,
        generator_platform=generator_platform,
        skip_provider_self_conformance=skip_provider_self_conformance,
    )
    if phase_a.get("result") != "bounded_provider_input_conformance_pass":
        raise ValueError("semantic conformance requires a complete Phase-A provider-input pass")
    corpus = load_corpus()
    runner = inputs.CommandRunner(output)
    roots_by_id = {
        "universal_launcher": ulk_root.resolve(),
        "universal_setup": usk_root.resolve(),
    }
    provider_sources = {
        source.spec.provider_id: source
        for source in (
            inputs.observe_provider(spec, roots_by_id[spec.provider_id], runner)
            for spec in inputs.PROVIDERS
        )
    }
    candidate_lock = work / "candidate/provider-conformance-lock.v1.toml"
    source_shared = work / "facman-build/source_shared"
    source_shared_command = inputs._facman_configure_command(
        facman_root,
        source_shared,
        candidate_lock,
        "source",
        cmake,
        config,
        generator_platform,
        provider_sources,
    )
    source_shared_command.append("-DFACMAN_PROVIDER_SOURCE_LINKAGE=shared")
    runner.run("semantic-source-shared-configure", source_shared_command, facman_root)

    builds = {mode.name: work / "facman-build" / mode.build_label for mode in MODES}
    _build_probe(builds["source_static"], MODES[0], cmake, config, runner)
    _build_probe(builds["source_shared"], MODES[1], cmake, config, runner)

    provider_roots = [ulk_root.resolve(), usk_root.resolve()]
    original_prefixes = [
        work / "provider-install" / provider_id / linkage
        for provider_id in ("universal_launcher", "universal_setup")
        for linkage in ("static", "shared")
    ]
    relocated_prefixes = [
        work / "relocated" / linkage / provider_id
        for linkage in ("static", "shared")
        for provider_id in ("universal_launcher", "universal_setup")
    ]
    with hidden_directories(provider_roots):
        _build_probe(builds["installed_static"], MODES[2], cmake, config, runner)
        _build_probe(builds["installed_shared"], MODES[3], cmake, config, runner)
        with hidden_directories(original_prefixes):
            _build_probe(builds["relocated_installed_static"], MODES[4], cmake, config, runner)
            _build_probe(builds["relocated_installed_shared"], MODES[5], cmake, config, runner)
            _build_probe(builds["private_runtime"], MODES[6], cmake, config, runner)

    environments: dict[str, dict[str, str]] = {
        "source_static": {},
        "source_shared": inputs._runtime_environment(_build_tree_runtime_dirs(source_shared)),
        "installed_static": inputs._runtime_environment(
            _runtime_dirs([work / "provider-install" / provider / "static" for provider in roots_by_id])
        ),
        "installed_shared": inputs._runtime_environment(
            _runtime_dirs([work / "provider-install" / provider / "shared" for provider in roots_by_id])
        ),
        "relocated_installed_static": inputs._runtime_environment(
            _runtime_dirs([work / "relocated/static" / provider for provider in roots_by_id])
        ),
        "relocated_installed_shared": inputs._runtime_environment(
            _runtime_dirs([work / "relocated/shared" / provider for provider in roots_by_id])
        ),
        "private_runtime": inputs._runtime_environment([work / "private-runtime"]),
    }
    raw_probes: dict[str, dict[str, Any]] = {}
    for mode in MODES[:2]:
        workspace = work / "semantic-workspaces" / mode.name
        raw_probes[mode.name] = _run_probe(
            builds[mode.name], mode, workspace, environments[mode.name], config, runner
        )
    with hidden_directories(provider_roots):
        for mode in MODES[2:4]:
            workspace = work / "semantic-workspaces" / mode.name
            raw_probes[mode.name] = _run_probe(
                builds[mode.name], mode, workspace, environments[mode.name], config, runner
            )
        with hidden_directories(original_prefixes):
            for mode in MODES[4:6]:
                workspace = work / "semantic-workspaces" / mode.name
                raw_probes[mode.name] = _run_probe(
                    builds[mode.name], mode, workspace, environments[mode.name], config, runner
                )
            with hidden_directories(relocated_prefixes):
                mode = MODES[6]
                workspace = work / "semantic-workspaces" / mode.name
                raw_probes[mode.name] = _run_probe(
                    builds[mode.name], mode, workspace, environments[mode.name], config, runner
                )

    release_projection = _release_projection(corpus)
    provider_contracts = _provider_contract_projection(phase_a)
    normalized: dict[str, dict[str, Any]] = {}
    mode_records: list[dict[str, Any]] = []
    for mode in MODES:
        workspace = work / "semantic-workspaces" / mode.name
        raw = raw_probes[mode.name]
        native_semantics = validate_and_normalize_probe(raw, mode, workspace, corpus)
        semantics = {
            **native_semantics,
            "release_resolution": copy.deepcopy(release_projection),
            "provider_contract_identity": copy.deepcopy(provider_contracts),
        }
        inputs.assert_path_independent_json(semantics)
        normalized[mode.name] = semantics
        raw_digest = sha256_bytes(canonical_bytes(raw))
        result_sha, result_bytes = _write_mode_result(
            output, mode, raw_digest, semantics
        )
        linkage = mode.linkage
        mode_records.append(
            {
                "name": mode.name,
                "provider_mode": mode.provider_mode,
                "linkage": linkage,
                "runtime_closure": mode.runtime,
                "toolchain": phase_a["provider_toolchains"][linkage],
                "sdk_identities": _sdk_identity_projection(phase_a, linkage),
                "raw_result_sha256": raw_digest,
                "normalized_semantic_sha256": sha256_bytes(canonical_bytes(semantics)),
                "result_record": {
                    "path": f"semantic-results/{mode.name}.json",
                    "sha256": result_sha,
                    "bytes": result_bytes,
                },
                "result": "pass",
            }
        )
    normalized_digest = compare_semantics(normalized)
    controls = negative_controls(normalized[MODES[0].name])
    controls.update(
        normalization_negative_controls(
            raw_probes[MODES[0].name],
            MODES[0],
            work / "semantic-workspaces" / MODES[0].name,
            corpus,
        )
    )
    facman_commit = _git_value(facman_root, "HEAD", runner)
    facman_tree = _git_value(facman_root, "HEAD^{tree}", runner)
    if not HEX_40.fullmatch(facman_commit) or not HEX_40.fullmatch(facman_tree):
        raise ValueError("FacMan semantic source identity is malformed")
    phase_a_json = phase_a_output / "provider-conformance-observation.v1.json"
    observation = {
        "schema": SCHEMA,
        "observed_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "result": "provider_semantic_conformance_pass",
        "full_semantic_conformance": True,
        "facman": {"commit": facman_commit, "tree": facman_tree},
        "platform": {
            "system": platform.system(),
            "architecture": platform.machine(),
            "runner_os": os.environ.get("RUNNER_OS", "local"),
            "runner_arch": os.environ.get("RUNNER_ARCH", platform.machine()),
        },
        "providers": [
            {"id": provider_id, **record}
            for provider_id, record in sorted(
                phase_a["canonical_provider_sources"].items()
            )
        ],
        "provider_input_observation": {
            "path": "provider-input-phase-a/provider-conformance-observation.v1.json",
            "sha256": sha256_file(phase_a_json),
        },
        "tracked_lock_records": phase_a["tracked_lock_records"],
        "candidate_lock": phase_a["candidate_lock"],
        "corpus": {
            "id": corpus["corpus_id"],
            "path": CORPUS_PATH.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(CORPUS_PATH),
        },
        "normalization_policy": {
            "schema": NORMALIZATION_POLICY["schema"],
            "sha256": normalization_policy_digest(),
            "allowed_differences": NORMALIZATION_POLICY["allowed_differences"],
        },
        "modes": mode_records,
        "semantic_classes": {name: "pass" for name in SEMANTIC_CLASSES},
        "normalized_semantic_sha256": normalized_digest,
        "negative_controls": controls,
        "required_skips": [],
        "tracked_lock_mutated": False,
        "provider_adoption": False,
        "provider_repin": False,
        "release_eligible": False,
        "authority": dict(inputs.AUTHORITY),
    }
    inputs.validate_authority(observation["authority"])
    inputs.assert_path_independent_json(observation)
    rendered = json.dumps(observation, indent=2, sort_keys=True) + "\n"
    (output / f"{OBSERVATION_STEM}.json").write_text(
        rendered, encoding="utf-8", newline="\n"
    )
    (output / f"{OBSERVATION_STEM}.md").write_text(
        _markdown(observation), encoding="utf-8", newline="\n"
    )
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
    parser.add_argument(
        "--skip-provider-self-conformance",
        action="store_true",
        help="Development-only; a closing hosted run must not use this flag.",
    )
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
        print(f"provider-semantic-conformance: {error}", file=sys.stderr)
        return 1
    print(
        "provider-semantic-conformance: pass "
        f"{observation['normalized_semantic_sha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
