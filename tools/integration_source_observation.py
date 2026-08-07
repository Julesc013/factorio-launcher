# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Project checkout facts and workspace-bound integration source coherence."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.release_compiler.canonical import domain_digest_value, pretty_json  # noqa: E402

CHECKOUT_SCHEMA = "facman.checkout_source_observation.v1"
CHECKOUT_DOMAIN = CHECKOUT_SCHEMA
INTEGRATION_SCHEMA = "facman.integration_source_observation.v1"
INTEGRATION_DOMAIN = INTEGRATION_SCHEMA
HEX_40 = re.compile(r"^[0-9a-f]{40}$")
HEX_64 = re.compile(r"^[0-9a-f]{64}$")
PROFILE_ID = re.compile(r"^[a-z0-9_]+$")
BUILD_IDENTITY_FIELDS = (
    "facman",
    "universal_launcher",
    "universal_setup",
    "provider_mode",
    "provider_source_linkage",
    "provider_lock_kind",
    "provider_conformance_only",
    "provider_sdk_consumption_candidate",
    "provider_candidate_differs_from_tracked",
    "provider_consumption_classification",
    "provider_release_identity_coherent",
    "source_dirty",
)
AUTHORITY_CEILING = {
    "factorio_execution": False,
    "provider_adoption": False,
    "publication": False,
    "release_package": False,
    "route_promotion": False,
    "setup_mutation": False,
    "signing": False,
}


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"malformed JSON at {path}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"JSON record must be an object: {path}")
    return value


def _toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _exact_sha(value: Any, label: str, problems: list[str]) -> str:
    rendered = str(value or "")
    if HEX_40.fullmatch(rendered) is None:
        problems.append(f"{label} must be an exact Git object id")
    return rendered


def _remote_identity(value: Any) -> str:
    remote = str(value or "").strip().replace("\\", "/")
    if remote.startswith("git@github.com:"):
        remote = "https://github.com/" + remote.removeprefix("git@github.com:")
    if remote.startswith("ssh://git@github.com/"):
        remote = "https://github.com/" + remote.removeprefix("ssh://git@github.com/")
    return remote.removesuffix("/").removesuffix(".git").lower()


def checkout_source_observation(current: dict[str, Any]) -> dict[str, Any]:
    """Return a path-free, lock-agnostic projection of one checkout observation."""
    problems: list[str] = []
    if current.get("schema") != "facman.current_checkout_observation.v2":
        problems.append("current checkout observation has the wrong schema")
    if current.get("result", {}).get("status") != "pass":
        problems.append("current checkout observation must pass before facts projection")
    source = current.get("source")
    if not isinstance(source, dict):
        source = {}
        problems.append("current checkout observation source must be an object")
    source_core = {
        "repository": "factorio-launcher",
        "commit": _exact_sha(source.get("head"), "FacMan commit", problems),
        "tree": _exact_sha(source.get("tree"), "FacMan tree", problems),
        "dirty": source.get("dirty"),
        "remote": str(source.get("origin_remote", "")),
        "canonical_ref": (
            f"refs/heads/{source['branch']}"
            if source.get("branch")
            else f"detached:{source.get('head', '')}"
        ),
    }
    if source_core["dirty"] is not False:
        problems.append("FacMan checkout must be clean")
    if not source_core["remote"]:
        problems.append("FacMan checkout remote must be present")
    if source.get("expected_ci_sha") and source.get("expected_ci_sha_match") is not True:
        problems.append("FacMan checkout does not match the exact CI source SHA")

    providers: list[dict[str, Any]] = []
    seen: set[str] = set()
    raw_providers = current.get("providers")
    if not isinstance(raw_providers, list):
        raw_providers = []
        problems.append("current checkout observation providers must be an array")
    for raw in raw_providers:
        if not isinstance(raw, dict):
            problems.append("current checkout observation contains a non-object provider")
            continue
        provider_id = str(raw.get("id", ""))
        if not provider_id or provider_id in seen:
            problems.append(f"provider identity is missing or duplicated: {provider_id!r}")
            continue
        seen.add(provider_id)
        checkout = raw.get("checkout")
        if not isinstance(checkout, dict):
            checkout = {}
            problems.append(f"{provider_id} checkout must be an object")
        provider = {
            "id": provider_id,
            "repository": str(raw.get("origin_remote", "")),
            "commit": _exact_sha(checkout.get("head"), f"{provider_id} commit", problems),
            "tree": _exact_sha(checkout.get("tree"), f"{provider_id} tree", problems),
            "dirty": checkout.get("dirty"),
            "canonical_ref": str(raw.get("local_tracking_ref", "")),
            "abi_versions": raw.get("abi_versions", []),
        }
        if raw.get("status") != "pass":
            problems.append(f"{provider_id} current checkout observation did not pass")
        if provider["dirty"] is not False:
            problems.append(f"{provider_id} checkout must be clean")
        if not provider["repository"] or not provider["canonical_ref"]:
            problems.append(f"{provider_id} remote and canonical ref must be present")
        providers.append(provider)

    policy = current.get("observation_policy")
    if not isinstance(policy, dict):
        policy = {}
        problems.append("current checkout observation policy must be an object")
    line_endings = policy.get("line_ending_profile")
    if not isinstance(line_endings, dict):
        line_endings = {}
        problems.append("current checkout line-ending profile must be an object")
    policy_digest = str(policy.get("sha256", ""))
    if HEX_64.fullmatch(policy_digest) is None:
        problems.append("checkout observation policy digest must be SHA-256")

    if problems:
        raise ValueError("; ".join(problems))
    core = {
        "schema": CHECKOUT_SCHEMA,
        "observation_class": "checkout_facts",
        "source": source_core,
        "providers": sorted(providers, key=lambda item: str(item["id"])),
        "line_ending_policy": {
            "id": str(line_endings.get("id", "")),
            "policy_digest": policy_digest,
        },
        "source_closure_proven": False,
        "authority": AUTHORITY_CEILING,
    }
    return {**core, "observation_digest": domain_digest_value(CHECKOUT_DOMAIN, core)}


def normalize_checkout_source_observation(value: dict[str, Any]) -> dict[str, Any]:
    problems: list[str] = []
    if value.get("schema") != CHECKOUT_SCHEMA:
        problems.append(f"checkout source observation schema must be {CHECKOUT_SCHEMA}")
    if value.get("observation_class") != "checkout_facts":
        problems.append("checkout source observation class must be checkout_facts")
    if value.get("authority") != AUTHORITY_CEILING:
        problems.append("checkout source observation must retain the exact authority ceiling")
    if value.get("source_closure_proven") is not False:
        problems.append("checkout facts cannot claim source closure")
    source = value.get("source", {})
    for field in ("commit", "tree"):
        _exact_sha(source.get(field), f"checkout source {field}", problems)
    if source.get("dirty") is not False:
        problems.append("checkout source must be clean")
    providers = value.get("providers")
    if not isinstance(providers, list) or not providers:
        problems.append("checkout source providers must be a non-empty array")
        providers = []
    seen: set[str] = set()
    for provider in providers:
        provider_id = str(provider.get("id", "")) if isinstance(provider, dict) else ""
        if not provider_id or provider_id in seen:
            problems.append(f"checkout provider identity is missing or duplicated: {provider_id!r}")
            continue
        seen.add(provider_id)
        _exact_sha(provider.get("commit"), f"{provider_id} commit", problems)
        _exact_sha(provider.get("tree"), f"{provider_id} tree", problems)
        if provider.get("dirty") is not False:
            problems.append(f"{provider_id} checkout must be clean")
    core = dict(value)
    actual_digest = str(core.pop("observation_digest", ""))
    if actual_digest != domain_digest_value(CHECKOUT_DOMAIN, core):
        problems.append("checkout source observation digest is invalid")
    if problems:
        raise ValueError("; ".join(problems))
    return value


def _workspace_providers(lock: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if lock.get("schema") != "flaunch.workspace_lock.v1":
        raise ValueError("workspace lock has the wrong schema")
    providers = {
        str(item.get("id")): item
        for item in lock.get("component", [])
        if isinstance(item, dict) and str(item.get("id")) in {"universal_launcher", "universal_setup"}
    }
    if set(providers) != {"universal_launcher", "universal_setup"}:
        raise ValueError("workspace lock must contain exactly both Universal providers")
    return providers


def _build_identity(path: Path) -> tuple[str, dict[str, str], str]:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"compiled build identity is missing: {path}")
    raw = path.read_bytes()
    if len(raw) > 4096 or b"\0" in raw:
        raise ValueError("compiled build identity is unbounded or contains NUL")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise ValueError("compiled build identity is not strict UTF-8") from error
    identity = text.removesuffix("\r\n").removesuffix("\n")
    if "\r" in identity or "\n" in identity:
        raise ValueError("compiled build identity must be exactly one line")
    segments = identity.split(";")
    if len(segments) != len(BUILD_IDENTITY_FIELDS):
        raise ValueError("compiled build identity has missing or extra fields")
    values: dict[str, str] = {}
    for expected, segment in zip(BUILD_IDENTITY_FIELDS, segments, strict=True):
        key, separator, content = segment.partition("=")
        if separator != "=" or key != expected or not content:
            raise ValueError("compiled build identity fields are absent or out of order")
        values[key] = content
    return identity, values, hashlib.sha256(raw).hexdigest()


def _cmake_cache(path: Path) -> dict[str, str]:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"CMake cache is missing: {path}")
    if path.stat().st_size > 4 * 1024 * 1024:
        raise ValueError("CMake cache exceeds the validation budget")
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="strict").splitlines():
        if not line or line.startswith(("#", "//")) or "=" not in line or ":" not in line:
            continue
        key_and_type, content = line.split("=", 1)
        key, _ = key_and_type.split(":", 1)
        values[key] = content
    return values


def _resolved_compiler(value: str) -> Path | None:
    compiler = Path(value)
    if not compiler.is_absolute():
        return None
    try:
        resolved = compiler.resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    if not resolved.is_absolute() or resolved.is_symlink() or not resolved.is_file():
        return None
    return resolved


def _cmake_compiler(build_root: Path, cache: dict[str, str]) -> Path:
    cached = str(cache.get("CMAKE_CXX_COMPILER", ""))
    if cached:
        compiler = _resolved_compiler(cached)
        if compiler is not None:
            return compiler

    compiler_records = sorted(
        build_root.glob("CMakeFiles/*/CMakeCXXCompiler.cmake"),
        key=lambda item: item.as_posix(),
    )
    observed: set[Path] = set()
    pattern = re.compile(r'^set\(CMAKE_CXX_COMPILER "([^"]+)"\)$')
    for record in compiler_records:
        if record.is_symlink() or not record.is_file():
            raise ValueError(f"CMake compiler identity record is not a regular file: {record}")
        if record.stat().st_size > 1024 * 1024:
            raise ValueError(f"CMake compiler identity record exceeds its budget: {record}")
        for line in record.read_text(encoding="utf-8", errors="strict").splitlines():
            match = pattern.fullmatch(line)
            if match:
                observed.add(Path(match.group(1)))
    if len(observed) != 1:
        raise ValueError("CMake generated records do not identify exactly one C++ compiler")
    compiler = _resolved_compiler(str(next(iter(observed))))
    if compiler is None:
        raise ValueError(
            "CMake C++ compiler identity does not resolve to an absolute regular file"
        )
    return compiler


def integration_source_observation(
    checkout: dict[str, Any],
    workspace_lock_path: Path,
    build_root: Path,
    target_profile: str,
) -> dict[str, Any]:
    checkout = normalize_checkout_source_observation(checkout)
    if PROFILE_ID.fullmatch(target_profile) is None:
        raise ValueError("target profile identity is malformed")
    profile_path = ROOT / "release" / "profiles" / target_profile / "profile.toml"
    profile = _toml(profile_path)
    if profile.get("id") != target_profile:
        raise ValueError("target profile record has the wrong identity")
    lock = _toml(workspace_lock_path)
    locked = _workspace_providers(lock)
    observed = {str(item["id"]): item for item in checkout["providers"]}
    if set(observed) != set(locked):
        raise ValueError("checkout provider set differs from the workspace lock")
    for provider_id in sorted(locked):
        if observed[provider_id].get("commit") != locked[provider_id].get("pin"):
            raise ValueError(f"checkout provider {provider_id} commit differs from workspace lock")
        if _remote_identity(observed[provider_id].get("repository")) != _remote_identity(
            locked[provider_id].get("remote")
        ):
            raise ValueError(f"checkout provider {provider_id} remote differs from workspace lock")

    _identity, compiled, identity_digest = _build_identity(
        build_root / "facman-build-identity.v1.txt"
    )
    expected_identity = {
        "facman": checkout["source"]["commit"],
        "universal_launcher": locked["universal_launcher"]["pin"],
        "universal_setup": locked["universal_setup"]["pin"],
        "provider_mode": "source",
        "provider_source_linkage": "static",
        "provider_lock_kind": "tracked",
        "provider_conformance_only": "false",
        "provider_sdk_consumption_candidate": "false",
        "provider_candidate_differs_from_tracked": "false",
        "provider_consumption_classification": "tracked_source",
        "source_dirty": "false",
    }
    for key, expected in expected_identity.items():
        if compiled.get(key) != expected:
            raise ValueError(f"compiled build identity {key} differs from integration custody")
    if compiled["provider_release_identity_coherent"] not in {"true", "false"}:
        raise ValueError("compiled release-provider coherence must be Boolean")

    cache = _cmake_cache(build_root / "CMakeCache.txt")
    for key in (
        "CMAKE_GENERATOR",
        "FACMAN_PROVIDER_MODE",
        "FACMAN_PROVIDER_SOURCE_LINKAGE",
    ):
        if not cache.get(key):
            raise ValueError(f"CMake cache omits integration toolchain field {key}")
    if cache["FACMAN_PROVIDER_MODE"] != "source":
        raise ValueError("CMake cache provider mode differs from integration custody")
    if cache["FACMAN_PROVIDER_SOURCE_LINKAGE"] != "static":
        raise ValueError("CMake cache provider linkage differs from integration custody")
    compiler = _cmake_compiler(build_root, cache)
    linkage = profile.get("linkage")
    if not isinstance(linkage, dict) or not str(linkage.get("model", "")):
        raise ValueError("target profile omits linkage identity")

    core = {
        "schema": INTEGRATION_SCHEMA,
        "observation_class": "workspace_bound_integration",
        "checkout_observation_digest": checkout["observation_digest"],
        "workspace_lock": {
            "schema": str(lock["schema"]),
            "sha256": _sha256(workspace_lock_path),
        },
        "source": checkout["source"],
        "providers": checkout["providers"],
        "compiled_build_identity": {
            "sha256": identity_digest,
            "provider_mode": compiled["provider_mode"],
            "provider_lock_kind": compiled["provider_lock_kind"],
            "provider_release_identity_coherent": (
                compiled["provider_release_identity_coherent"] == "true"
            ),
        },
        "target": {
            "profile_id": target_profile,
            "operating_system": str(profile.get("target_os", "")),
            "architecture": str(profile.get("target_arch", "")),
            "linkage_model": str(linkage["model"]),
        },
        "toolchain": {
            "generator": cache["CMAKE_GENERATOR"],
            "cxx_compiler_sha256": _sha256(compiler),
        },
        "artifact_class": "unpublished_integration_test_package",
        "integration_coherent": True,
        "release_eligible": False,
        "provider_adoption": False,
        "signing": False,
        "publication": False,
        "authority": AUTHORITY_CEILING,
    }
    return {**core, "observation_digest": domain_digest_value(INTEGRATION_DOMAIN, core)}


def normalize_integration_source_observation(
    value: dict[str, Any],
    *,
    workspace_lock_path: Path | None = None,
    expected_profile: str | None = None,
) -> dict[str, Any]:
    problems: list[str] = []
    if value.get("schema") != INTEGRATION_SCHEMA:
        problems.append(f"integration source observation schema must be {INTEGRATION_SCHEMA}")
    if value.get("observation_class") != "workspace_bound_integration":
        problems.append("integration source observation has the wrong class")
    required_false = ("release_eligible", "provider_adoption", "signing", "publication")
    for field in required_false:
        if value.get(field) is not False:
            problems.append(f"integration source observation {field} must be false")
    if value.get("integration_coherent") is not True:
        problems.append("integration source observation must declare integration_coherent=true")
    if value.get("authority") != AUTHORITY_CEILING:
        problems.append("integration source observation must retain the exact authority ceiling")
    if value.get("artifact_class") != "unpublished_integration_test_package":
        problems.append("integration source observation has the wrong artifact class")
    checkout_digest = str(value.get("checkout_observation_digest", ""))
    if HEX_64.fullmatch(checkout_digest) is None:
        problems.append("integration checkout-observation digest must be SHA-256")

    source = value.get("source")
    if not isinstance(source, dict):
        source = {}
        problems.append("integration source must be an object")
    for field in ("commit", "tree"):
        _exact_sha(source.get(field), f"integration source {field}", problems)
    if source.get("dirty") is not False:
        problems.append("integration source must be clean")
    if not source.get("remote") or not source.get("canonical_ref"):
        problems.append("integration source remote and canonical ref must be present")

    providers = value.get("providers")
    if not isinstance(providers, list):
        providers = []
        problems.append("integration providers must be an array")
    observed: dict[str, dict[str, Any]] = {}
    for provider in providers:
        if not isinstance(provider, dict):
            problems.append("integration providers must contain only objects")
            continue
        provider_id = str(provider.get("id", ""))
        if not provider_id or provider_id in observed:
            problems.append(f"integration provider identity is missing or duplicated: {provider_id!r}")
            continue
        observed[provider_id] = provider
        _exact_sha(provider.get("commit"), f"integration {provider_id} commit", problems)
        _exact_sha(provider.get("tree"), f"integration {provider_id} tree", problems)
        if provider.get("dirty") is not False:
            problems.append(f"integration {provider_id} checkout must be clean")
        if not provider.get("repository") or not provider.get("canonical_ref"):
            problems.append(f"integration {provider_id} remote and canonical ref must be present")
    if set(observed) != {"universal_launcher", "universal_setup"}:
        problems.append("integration observation must contain exactly both Universal providers")

    compiled = value.get("compiled_build_identity")
    if not isinstance(compiled, dict):
        compiled = {}
        problems.append("integration compiled build identity must be an object")
    if HEX_64.fullmatch(str(compiled.get("sha256", ""))) is None:
        problems.append("integration compiled build identity digest must be SHA-256")
    if compiled.get("provider_mode") != "source":
        problems.append("integration compiled provider mode must be source")
    if compiled.get("provider_lock_kind") != "tracked":
        problems.append("integration compiled provider lock kind must be tracked")
    if not isinstance(compiled.get("provider_release_identity_coherent"), bool):
        problems.append("integration compiled release-provider coherence must be Boolean")

    target = value.get("target")
    if not isinstance(target, dict):
        target = {}
        problems.append("integration target must be an object")
    if expected_profile and target.get("profile_id") != expected_profile:
        problems.append("integration source observation target profile differs from package")
    for field in ("profile_id", "operating_system", "architecture", "linkage_model"):
        if not target.get(field):
            problems.append(f"integration target omits {field}")

    toolchain = value.get("toolchain")
    if not isinstance(toolchain, dict):
        toolchain = {}
        problems.append("integration toolchain must be an object")
    if not toolchain.get("generator"):
        problems.append("integration toolchain generator must be present")
    if HEX_64.fullmatch(str(toolchain.get("cxx_compiler_sha256", ""))) is None:
        problems.append("integration compiler digest must be SHA-256")

    lock = value.get("workspace_lock")
    if not isinstance(lock, dict):
        lock = {}
        problems.append("integration workspace lock must be an object")
    if lock.get("schema") != "flaunch.workspace_lock.v1":
        problems.append("integration workspace lock has the wrong schema")
    if HEX_64.fullmatch(str(lock.get("sha256", ""))) is None:
        problems.append("integration workspace-lock digest must be SHA-256")
    if workspace_lock_path is not None:
        if lock.get("sha256") != _sha256(workspace_lock_path):
            problems.append("integration source observation workspace-lock digest is stale")
        try:
            locked = _workspace_providers(_toml(workspace_lock_path))
        except (OSError, ValueError, tomllib.TOMLDecodeError) as error:
            problems.append(str(error))
        else:
            for provider_id in sorted(set(observed) & set(locked)):
                if observed[provider_id].get("commit") != locked[provider_id].get("pin"):
                    problems.append(
                        f"integration provider {provider_id} commit differs from workspace lock"
                    )
                if _remote_identity(observed[provider_id].get("repository")) != _remote_identity(
                    locked[provider_id].get("remote")
                ):
                    problems.append(
                        f"integration provider {provider_id} remote differs from workspace lock"
                    )
    core = dict(value)
    actual_digest = str(core.pop("observation_digest", ""))
    if actual_digest != domain_digest_value(INTEGRATION_DOMAIN, core):
        problems.append("integration source observation digest is invalid")
    if problems:
        raise ValueError("; ".join(problems))
    return value


def load_checkout_source_observation(path: Path) -> dict[str, Any]:
    return normalize_checkout_source_observation(_json(path))


def load_integration_source_observation(
    path: Path,
    *,
    workspace_lock_path: Path | None = None,
    expected_profile: str | None = None,
) -> dict[str, Any]:
    return normalize_integration_source_observation(
        _json(path),
        workspace_lock_path=workspace_lock_path,
        expected_profile=expected_profile,
    )


def write_observation(path: Path, value: dict[str, Any]) -> Path:
    destination = path.resolve()
    if destination == ROOT or ROOT.resolve() in destination.parents:
        raise ValueError("source-truth observation output must be outside the source repository")
    if destination.exists():
        raise ValueError(f"source-truth observation output already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(pretty_json(value), encoding="utf-8")
    return destination


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Project bounded FacMan source-truth records.")
    commands = parser.add_subparsers(dest="command", required=True)
    checkout = commands.add_parser("checkout", help="project path-free checkout facts")
    checkout.add_argument("--current-observation", required=True)
    checkout.add_argument("--output", required=True)
    integration = commands.add_parser(
        "integration", help="prove workspace-lock-bound integration coherence"
    )
    integration.add_argument("--checkout-observation", required=True)
    integration.add_argument(
        "--workspace-lock", default="release/index/workspace_lock.v1.toml"
    )
    integration.add_argument("--build-root", required=True)
    integration.add_argument("--target-profile", required=True)
    integration.add_argument("--output", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "checkout":
            value = checkout_source_observation(_json(Path(args.current_observation)))
        else:
            value = integration_source_observation(
                load_checkout_source_observation(Path(args.checkout_observation)),
                Path(args.workspace_lock).resolve(),
                Path(args.build_root).resolve(),
                str(args.target_profile),
            )
        destination = write_observation(Path(args.output), value)
    except (OSError, ValueError, tomllib.TOMLDecodeError) as error:
        print(f"integration-source-observation: {error}", file=sys.stderr)
        return 1
    print(f"integration-source-observation: {value['observation_digest']} -> {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
