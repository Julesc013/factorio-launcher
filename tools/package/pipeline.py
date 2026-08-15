# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT
# ruff: noqa: E402

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
import tomllib
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import (
    json_contract,
    owned_output,
    package_hash_manifest,
    package_layout_check,
    provenance_build,
    verify_dependency_revisions,
)
from tools.package import archive as package_archive
from tools.package import components as package_components
from tools.package import manifests as package_manifests
from tools.package import platform_proof as package_platform_proof
from tools.package import profile as package_profile
from tools.package import provenance as package_provenance
from tools.package import staging as package_staging
from tools.release_compiler.compiler import load_inputs as load_release_inputs
from tools.release_compiler.compiler import resolve as resolve_release
from tools.release_compiler.outputs import (
    load_runtime_projection,
    validate_resolution,
    write_runtime_projection,
)
from tools.release_compiler.source_observation import load_source_observation
from tools.integration_source_observation import (
    load_integration_source_observation,
)

DEFAULT_OUT = ROOT / "build" / "packages"
DEFAULT_BUILD_ROOT = ROOT / "build" / "native-smoke"
DEFAULT_DIST = ROOT / "dist"
REPAIRED_PROVIDER_CANARY_CUSTODY = "unpublished_repaired_provider_canary"
REPAIRED_PROVIDER_CANARY_SCHEMA = (
    ROOT / "contracts" / "schema" / "release" / "repaired_provider_canary.v1.schema.json"
)
REPAIRED_PROVIDER_CANARY_RECORD = "repaired-provider-canary.v1.json"
HEX_REVISION = re.compile(r"^[0-9a-f]{40}$")
SUPPORTED_BUILT_PROFILES = {
    "linux_portable_cli_x64",
    "macos_portable_cli_x64",
    "windows_portable_cli_x64",
    "windows_portable_tui_x64",
    "linux_portable_tui_x64",
    "macos_portable_tui_x64",
    "portable_cli_x64",
    "windows_legacy_winforms_x64",
}
COMPOSITION_PROFILES = {
    "linux_portable_cli_x64",
    "macos_portable_cli_x64",
    "windows_portable_cli_x64",
}
WORKSPACE_LOCK_PATH = ROOT / "release" / "index" / "workspace_lock.v1.toml"
DEPENDENCY_LOCK_PATH = ROOT / "release" / "index" / "dependency_lock.v1.toml"
VERSION_PATH = ROOT / "release" / "index" / "version.v2.toml"
FORBIDDEN_FILE_MARKERS = {
    "factorio.exe",
    "Factorio.app",
    "mod_portal_credentials",
    "password",
    "steamapps",
    "token",
}
PYTHON_RUNTIME_MARKERS = {
    "__pycache__",
    ".py",
    ".pyc",
    "python.exe",
    "python3",
}
ALLOWED_RUNTIME_ROLES = {
    "runtime_required",
    "compatibility_reference",
    "documentation_only",
}
EXTERNAL_COMPONENT_TARGETS = {
    "apps/gui/windows/winforms",
}
BUILT_PACKAGE_SCHEMA = ROOT / "contracts" / "schema" / "release" / "built_package.v1.schema.json"
CMAKE_BUILD_IDENTITY_FILENAME = "facman-build-identity.v1.txt"
CMAKE_BUILD_IDENTITY_FIELDS = (
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
    "ulk_session_consumer_canary",
    "source_dirty",
)
WINDOWS_PACKAGE_PROVIDER_LINKAGE = {
    "windows_portable_cli_x64": "static",
    "windows_portable_tui_x64": "static",
    "windows_legacy_winforms_x64": "shared",
}
SHARED_RUNTIME_FILENAMES = {"ulk.dll", "usk.dll", "flb_factorio.dll"}
SHARED_RUNTIME_TARGETS = ("ulk_shared", "usk_shared", "flb_factorio_shared")
WINDOWS_PACKAGE_INSTALL_COMPONENTS = {
    "windows_portable_cli_x64": (
        "Runtime",
        "CLI",
        "Contracts",
        "Content",
        "Documentation",
        "Licenses",
    ),
    "windows_portable_tui_x64": (
        "Runtime",
        "CLI",
        "TUI",
        "Contracts",
        "Content",
        "Documentation",
        "Licenses",
    ),
    "windows_legacy_winforms_x64": (
        "Runtime",
        "CLI",
        "Contracts",
        "Content",
        "Documentation",
        "Licenses",
    ),
}


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    parser = argparse.ArgumentParser(description="Build unsigned local FacMan package roots.")
    parser.add_argument("--profile", required=True, help="release profile id, for example windows_portable_cli_x64")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="output root containing per-profile package roots")
    parser.add_argument("--build-root", default=str(DEFAULT_BUILD_ROOT), help="native CMake build root")
    parser.add_argument("--dist", default=str(DEFAULT_DIST), help="zip archive output root; use '' to disable")
    parser.add_argument("--no-clean", action="store_true", help="do not delete an existing profile package root")
    parser.add_argument("--allow-dirty", action="store_true", help="allow explicitly non-proof developer output from a dirty source tree")
    custody = parser.add_mutually_exclusive_group()
    custody.add_argument(
        "--source-observation",
        help="out-of-tree source observation required by release-eligible composition profiles",
    )
    custody.add_argument(
        "--integration-source-observation",
        help="workspace-bound, non-release integration source observation",
    )
    custody.add_argument(
        "--repaired-provider-canary-ulk",
        metavar="REVISION",
        help=(
            "exact noncanonical ULK revision for an unsigned, unpublished "
            "engineering canary"
        ),
    )
    args = parser.parse_args(argv)

    try:
        package_root = build_profile(
            profile_id=args.profile,
            out_root=Path(args.out).resolve(),
            build_root=Path(args.build_root).resolve(),
            dist_root=Path(args.dist).resolve() if args.dist else None,
            clean=not args.no_clean,
            allow_dirty=args.allow_dirty,
            source_observation_path=(
                Path(args.source_observation).resolve()
                if args.source_observation
                else None
            ),
            integration_source_observation_path=(
                Path(args.integration_source_observation).resolve()
                if args.integration_source_observation
                else None
            ),
            repaired_provider_canary_ulk=args.repaired_provider_canary_ulk,
        )
    except (OSError, ValueError, tomllib.TOMLDecodeError) as exc:
        print(f"package-build: {exc}", file=sys.stderr)
        return 1
    print(f"package-build: ok {package_root}")
    return 0


def build_profile(
    profile_id: str,
    out_root: Path,
    build_root: Path,
    dist_root: Path | None = DEFAULT_DIST,
    clean: bool = True,
    allow_dirty: bool = False,
    source_observation_path: Path | None = None,
    integration_source_observation_path: Path | None = None,
    repaired_provider_canary_ulk: str | None = None,
) -> Path:
    assert_safe_output_root(out_root)
    validate_output_root_ownership(out_root)
    package_provenance.require_clean(ROOT, allow_dirty)
    tracked_revisions = pinned_source_revisions()
    source_revisions = dict(tracked_revisions)
    if repaired_provider_canary_ulk is None:
        require_pinned_dependency_revisions()
        provider_class = "canonical"
    else:
        provider_class = "repaired_provider_canary"
        source_revisions = repaired_provider_canary_revisions(
            tracked_revisions,
            repaired_provider_canary_ulk,
        )
    profile_path, profile = load_profile(profile_id)
    if profile_id not in SUPPORTED_BUILT_PROFILES:
        raise ValueError(f"{profile_id}: built artifact proof is not enabled for this profile")
    if profile.get("publication") is False:
        raise ValueError(f"{profile_id}: profile is explicitly unpublished")
    if repaired_provider_canary_ulk is not None and (
        source_observation_path is not None
        or integration_source_observation_path is not None
    ):
        raise ValueError(
            "repaired-provider canary custody is mutually exclusive with release "
            "and integration source observations"
        )
    if source_observation_path is not None and integration_source_observation_path is not None:
        raise ValueError("release and integration source observations are mutually exclusive")
    integration_observation = package_integration_source_observation(
        profile_id,
        integration_source_observation_path,
    )
    source_observation = None
    if integration_observation is None:
        source_observation = package_source_observation(
            profile_id,
            source_observation_path,
            allow_dirty=allow_dirty,
        )
    owned_output.ensure_owned_output_root(out_root, "built-packages")
    assert_host_matches_profile(profile_id, profile)
    bundle_path = ROOT / str(profile.get("package_manifest", ""))
    bundle = package_layout_check.expand_bundle_manifest(bundle_path, load_toml(bundle_path), [])
    validate_build_composition(
        profile_id,
        profile,
        bundle,
        build_root,
        source_revisions=source_revisions,
        provider_class=provider_class,
    )
    package_root = out_root / profile_id
    install_root = package_staging.install_tree(
        build_root,
        out_root / ".install" / profile_id,
        components=WINDOWS_PACKAGE_INSTALL_COMPONENTS.get(profile_id),
    )
    validate_install_composition(profile_id, install_root)
    stage_external_components(install_root, build_root, bundle)
    if clean and package_root.exists():
        owned_output.assert_owned_output_root(out_root, "built-packages")
        shutil.rmtree(package_root)
    package_root.mkdir(parents=True, exist_ok=True)

    component_records = copy_bundle_components(package_root, install_root, bundle)
    copy_support_payloads(package_root, profile, install_root)
    if provider_class == "repaired_provider_canary":
        write_packaged_canary_workspace_lock(package_root, source_revisions)
    write_package_manifest(
        package_root,
        profile_path,
        profile,
        bundle_path,
        bundle,
        source_revisions=source_revisions,
    )
    if provider_class == "repaired_provider_canary":
        write_repaired_provider_canary_metadata(
            package_root,
            source_revisions,
            tracked_revisions,
            build_root,
        )
        custody_class = REPAIRED_PROVIDER_CANARY_CUSTODY
    elif integration_observation is None:
        write_release_resolution_metadata(
            package_root,
            profile_id,
            source_observation=source_observation,
        )
        custody_class = "release_resolution"
    else:
        write_integration_source_metadata(package_root, integration_observation)
        custody_class = "unpublished_integration"
    build_info = write_build_info(
        package_root,
        profile_id,
        profile,
        bundle,
        build_root,
        custody_class=custody_class,
        source_revisions=source_revisions,
        provider_class=provider_class,
    )
    provenance_build.write_package_sbom(package_root, build_info, component_records)
    write_platform_metadata(package_root, profile, build_root)
    validate_package_root(
        package_root,
        profile,
        component_records,
        custody_class=custody_class,
    )
    package_hash_manifest.write_manifests(package_root, component_records)
    if dist_root is not None:
        artifact = write_archive(package_root, dist_root, bundle)
        provenance_build.write_artifact_provenance(package_root, artifact)
    return package_root


def validate_output_root_ownership(out_root: Path) -> None:
    resolved = out_root.resolve()
    if not resolved.exists():
        return
    if not resolved.is_dir():
        raise ValueError(f"output root is not a directory: {resolved}")
    marker = resolved / owned_output.MARKER_NAME
    if marker.is_file():
        owned_output.assert_owned_output_root(resolved, "built-packages")
    elif any(resolved.iterdir()):
        raise ValueError(f"refusing unowned output root with existing content: {resolved}")


def write_release_resolution_metadata(
    package_root: Path,
    profile_id: str,
    *,
    source_observation: dict[str, Any] | None = None,
) -> None:
    if profile_id not in COMPOSITION_PROFILES:
        return
    inputs = load_release_inputs(ROOT / "release" / "index", ROOT)
    outputs = resolve_release(inputs, profile_id, source_observation)
    validate_resolution(outputs, ROOT)
    write_runtime_projection(
        package_root / "manifest" / "resolution",
        outputs,
        ROOT,
    )


def package_source_observation(
    profile_id: str,
    source_observation_path: Path | None,
    *,
    allow_dirty: bool,
) -> dict[str, Any] | None:
    if profile_id not in COMPOSITION_PROFILES:
        return None
    if source_observation_path is None:
        if allow_dirty:
            return None
        raise ValueError(
            f"{profile_id}: release-eligible package construction requires "
            "an explicit source observation"
        )
    inputs = load_release_inputs(ROOT / "release" / "index", ROOT)
    observation = load_source_observation(source_observation_path, inputs.model)
    if not allow_dirty and observation.get("release_eligible") is not True:
        raise ValueError(
            f"{profile_id}: release-oriented package construction requires "
            "a clean release-eligible source observation"
        )
    return observation


def package_integration_source_observation(
    profile_id: str,
    integration_source_observation_path: Path | None,
) -> dict[str, Any] | None:
    if integration_source_observation_path is None:
        return None
    if profile_id not in COMPOSITION_PROFILES:
        raise ValueError(
            f"{profile_id}: integration source custody is limited to composition profiles"
        )
    observation = load_integration_source_observation(
        integration_source_observation_path,
        workspace_lock_path=WORKSPACE_LOCK_PATH,
        expected_profile=profile_id,
    )
    revisions = pinned_source_revisions()
    if observation["source"]["commit"] != revisions["factorio_launcher"]:
        raise ValueError(
            f"{profile_id}: integration observation FacMan commit differs from package source"
        )
    observed = {item["id"]: item["commit"] for item in observation["providers"]}
    for provider_id in ("universal_launcher", "universal_setup"):
        if observed.get(provider_id) != revisions[provider_id]:
            raise ValueError(
                f"{profile_id}: integration observation {provider_id} commit differs "
                "from package source"
            )
    return observation


def repaired_provider_canary_revisions(
    tracked_revisions: dict[str, str],
    universal_launcher_revision: str,
) -> dict[str, str]:
    revision = universal_launcher_revision.strip().lower()
    if HEX_REVISION.fullmatch(revision) is None:
        raise ValueError(
            "repaired-provider canary ULK revision must be an exact 40-character Git id"
        )
    if revision == tracked_revisions["universal_launcher"]:
        raise ValueError(
            "repaired-provider canary ULK revision must differ from the tracked canonical pin"
        )
    revisions = dict(tracked_revisions)
    revisions["universal_launcher"] = revision
    return revisions


def candidate_version(source_revision: str) -> tuple[str, str]:
    version = load_toml(VERSION_PATH)
    semver = str(version["semver"])
    suffix = source_revision[:12]
    return (
        f"facman-{semver}+canary.{suffix}",
        f"facman-{semver}-canary.{suffix}",
    )


def write_packaged_canary_workspace_lock(
    package_root: Path,
    source_revisions: dict[str, str],
) -> None:
    path = package_root / "release" / "index" / "workspace_lock.v1.toml"
    lines = path.read_text(encoding="utf-8").splitlines()
    current_component = ""
    changed = False
    output: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('id = "') and stripped.endswith('"'):
            current_component = stripped[len('id = "'):-1]
        if current_component == "universal_launcher" and stripped.startswith('pin = "'):
            line = f'pin = "{source_revisions["universal_launcher"]}"'
            changed = True
        output.append(line)
    if not changed:
        raise ValueError("packaged canary workspace lock omits Universal Launcher")
    path.write_text("\n".join(output) + "\n", encoding="utf-8", newline="\n")


def write_repaired_provider_canary_metadata(
    package_root: Path,
    source_revisions: dict[str, str],
    tracked_revisions: dict[str, str],
    build_root: Path,
) -> None:
    identity, _values = cmake_build_identity_values(
        build_root,
        source_revisions,
        False,
        provider_class="repaired_provider_canary",
    )
    canonical_version, _filename_version = candidate_version(
        source_revisions["factorio_launcher"]
    )
    record = {
        "schema": "facman.repaired_provider_canary.v1",
        "classification": "noncanonical_engineering_candidate",
        "candidate_version": canonical_version.removeprefix("facman-"),
        "source_revisions": {
            key: source_revisions[key]
            for key in ("factorio_launcher", "universal_launcher", "universal_setup")
        },
        "canonical_provider_revisions": {
            key: tracked_revisions[key]
            for key in ("universal_launcher", "universal_setup")
        },
        "build_identity_sha256": hashlib.sha256(
            (identity + "\n").encode("utf-8")
        ).hexdigest(),
        "canonical_provider_pin_unchanged": True,
        "release_eligible": False,
        "provider_adoption": False,
        "signed": False,
        "published": False,
        "authority": {
            "factorio_execution": False,
            "provider_adoption": False,
            "publication": False,
            "release_package": False,
            "route_promotion": False,
            "setup_mutation": False,
            "signing": False,
        },
    }
    schema = json_contract.load_schema(REPAIRED_PROVIDER_CANARY_SCHEMA)
    problems = json_contract.validate(record, schema)
    if problems:
        raise ValueError(
            "repaired-provider canary metadata violates its contract: "
            + "; ".join(problems)
        )
    package_manifests.write_json(
        package_root / "manifest" / REPAIRED_PROVIDER_CANARY_RECORD,
        record,
    )


def write_integration_source_metadata(
    package_root: Path,
    integration_observation: dict[str, Any],
) -> None:
    destination = package_root / "manifest" / "integration-source-observation.v1.json"
    package_manifests.write_json(destination, integration_observation)


def require_pinned_dependency_revisions() -> None:
    problems = verify_dependency_revisions.verify(WORKSPACE_LOCK_PATH)
    if problems:
        raise ValueError(
            "package preflight requires exact Universal dependency revisions: "
            + "; ".join(problems)
        )


def stage_external_components(
    install_root: Path,
    build_root: Path,
    bundle: dict[str, Any],
) -> None:
    components = bundle.get("components", [])
    if not isinstance(components, list):
        raise ValueError("bundle components must be an array")
    for component in components:
        source_target = str(component.get("source_target", ""))
        if source_target not in EXTERNAL_COMPONENT_TARGETS:
            continue
        destination = normalize_destination(str(component.get("destination", "")))
        if not destination:
            raise ValueError(f"external component is missing destination: {component}")
        copy_file(
            resolve_source_target(source_target, build_root),
            install_root / destination,
        )


def copy_bundle_components(
    package_root: Path,
    install_root: Path,
    bundle: dict[str, Any],
) -> list[dict[str, Any]]:
    components = bundle.get("components", [])
    if not isinstance(components, list):
        raise ValueError("bundle components must be an array")
    records: list[dict[str, Any]] = []
    for component in components:
        source_target = str(component.get("source_target", ""))
        destination = normalize_destination(str(component.get("destination", "")))
        if not source_target or not destination:
            raise ValueError(f"component missing source_target or destination: {component}")
        runtime_role = str(component.get("runtime_role", ""))
        if runtime_role not in ALLOWED_RUNTIME_ROLES:
            raise ValueError(
                f"component {source_target} must declare runtime_role as one of "
                f"{', '.join(sorted(ALLOWED_RUNTIME_ROLES))}"
            )
        destination_path = package_root / destination
        if source_target in {"contracts/schema", "content/factorio"}:
            copy_tree(package_components.tree(install_root, source_target), destination_path)
        else:
            source = package_components.resolve(install_root, source_target)
            copy_file(source, destination_path)
            maybe_copy_windows_alias(source, destination_path)
        records.append(
            {
                "name": str(component.get("name", "")),
                "source_target": source_target,
                "destination": destination,
                "kind": component_kind(source_target),
                "runtime_role": runtime_role,
            }
        )
    return records


def copy_support_payloads(
    package_root: Path,
    profile: dict[str, Any],
    install_root: Path,
) -> None:
    copy_release_documents(
        install_root / "share" / "doc" / "facman" / "release",
        package_root / "docs" / "release",
    )
    copy_release_metadata(
        install_root / "share" / "facman" / "release",
        package_root / "release",
        profile,
    )
    copy_file(install_root / "share" / "doc" / "facman" / "README.md", package_root / "docs" / "README.md")
    licenses = install_root / "share" / "doc" / "facman" / "licenses"
    for license_name in string_list(profile.get("licenses")):
        copy_file(licenses / Path(license_name).name, package_root / "licenses" / Path(license_name).name)


def copy_release_documents(source: Path, destination: Path) -> None:
    if not source.is_dir():
        raise ValueError(f"missing release-document directory: {source}")
    destination.mkdir(parents=True, exist_ok=True)
    # Nested checkpoint evidence is repository provenance, not product documentation.
    for path in sorted(source.iterdir(), key=lambda item: item.name):
        if path.is_symlink():
            raise ValueError(f"release document must not be linked: {path}")
        if path.is_file():
            copy_file(path, destination / path.name)


def copy_release_metadata(
    source: Path, destination: Path, profile: dict[str, Any]
) -> None:
    release_index_path = source / "index" / "release_index.v1.toml"
    release_index = load_toml(release_index_path)
    references = {
        "release/index/release_index.v1.toml",
        str(profile.get("package_manifest", "")),
    }
    for value in release_index.values():
        if isinstance(value, str) and value.startswith("release/"):
            references.add(value)
        elif isinstance(value, list):
            references.update(
                item for item in value if isinstance(item, str) and item.startswith("release/")
            )
    for relative in sorted(references):
        normalized = normalize_destination(relative)
        if not normalized.startswith("release/"):
            raise ValueError(f"release metadata path must remain under release/: {relative}")
        destination_relative = PurePosixPath(normalized).relative_to("release")
        copy_file(
            source.joinpath(*destination_relative.parts),
            destination.joinpath(*destination_relative.parts),
        )


def write_package_manifest(
    package_root: Path,
    profile_path: Path,
    profile: dict[str, Any],
    bundle_path: Path,
    bundle: dict[str, Any],
    *,
    source_revisions: dict[str, str] | None = None,
) -> None:
    manifest = package_root / "manifest"
    manifest.mkdir(parents=True, exist_ok=True)
    revisions = source_revisions or pinned_source_revisions()
    data = {
        "schema": "facman.built_package.v1",
        "profile_id": profile["id"],
        "lane": profile["lane"],
        "target_os": profile["target_os"],
        "target_arch": profile["target_arch"],
        "package_type": bundle.get("package_type", ""),
        "entrypoint": bundle.get("entrypoint", ""),
        "linkage_model": bundle.get("linkage_model", ""),
        "release_profile": profile_path.relative_to(ROOT).as_posix(),
        "package_manifest": bundle_path.relative_to(ROOT).as_posix(),
        "workspace_lock": WORKSPACE_LOCK_PATH.relative_to(ROOT).as_posix(),
        "source_revision": revisions["factorio_launcher"],
        "proof_baseline_revision": revisions["factorio_binding"],
        "universal_launcher_revision": revisions["universal_launcher"],
        "universal_setup_revision": revisions["universal_setup"],
        "artifact_level": "built-artifact",
        "signed": False,
        "published": False,
        "source_dirty": git_dirty(),
        "python_runtime": False,
        "bundles_factorio_binaries": False,
    }
    schema = json_contract.load_schema(BUILT_PACKAGE_SCHEMA)
    problems = json_contract.validate(data, schema)
    if problems:
        raise ValueError(f"built package manifest violates its contract: {'; '.join(problems)}")
    lines = [f"{key} = {toml_scalar(value)}" for key, value in data.items()]
    (manifest / "package.v1.toml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_build_info(
    package_root: Path,
    profile_id: str,
    profile: dict[str, Any],
    bundle: dict[str, Any],
    build_root: Path,
    *,
    custody_class: str = "release_resolution",
    source_revisions: dict[str, str] | None = None,
    provider_class: str = "canonical",
) -> dict[str, Any]:
    build_index = load_toml(VERSION_PATH)
    revisions = source_revisions or pinned_source_revisions()
    source_dirty = git_dirty()
    canonical_version = str(build_index["canonical_version"])
    filename_version = str(build_index["filename_version"])
    if provider_class == "repaired_provider_canary":
        canonical_version, filename_version = candidate_version(
            revisions["factorio_launcher"]
        )
    info = {
        "schema": "facman.package_build_info.v1",
        "profile_id": profile_id,
        "artifact_level": "built-artifact",
        "canonical_version": canonical_version,
        "filename_version": filename_version,
        "source_commit": revisions["factorio_launcher"],
        "source_timestamp_policy": "source_commit_utc",
        "source_timestamp_utc": provenance_build.source_commit_timestamp(
            revisions["factorio_launcher"]
        ),
        "source_dirty": source_dirty,
        "source_state_sha256": source_state_digest(),
        "build_identity": cmake_build_identity(
            build_root,
            revisions,
            source_dirty,
            provider_class=provider_class,
        ),
        "source_revisions": {
            "factorio_launcher": revisions["factorio_launcher"],
            "universal_launcher": revisions["universal_launcher"],
            "universal_setup": revisions["universal_setup"],
        },
        "target_os": profile.get("target_os"),
        "target_arch": profile.get("target_arch"),
        "package_type": bundle.get("package_type"),
        "signed": False,
        "published": False,
        "source_custody_class": custody_class,
        "integration_coherent": custody_class in {
            "unpublished_integration",
            REPAIRED_PROVIDER_CANARY_CUSTODY,
        },
        "release_eligible": False,
        "provider_adoption": False,
        "toolchain": toolchain_identity(profile, build_root),
    }
    package_manifests.write_json(package_root / "manifest" / "build_info.v1.json", info)
    return info


def cmake_build_identity(
    build_root: Path,
    source_revisions: dict[str, str],
    source_dirty: bool,
    *,
    provider_class: str = "canonical",
) -> str:
    identity, _values = cmake_build_identity_values(
        build_root,
        source_revisions,
        source_dirty,
        provider_class=provider_class,
    )
    return identity


def cmake_build_identity_values(
    build_root: Path,
    source_revisions: dict[str, str],
    source_dirty: bool,
    *,
    provider_class: str = "canonical",
) -> tuple[str, dict[str, str]]:
    path = build_root / CMAKE_BUILD_IDENTITY_FILENAME
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"exact CMake build identity is missing: {path}")
    try:
        text = path.read_bytes().decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise ValueError("CMake build identity is not strict UTF-8") from error
    if len(text) > 4096 or "\x00" in text:
        raise ValueError(
            "CMake build identity must be one bounded LF- or CRLF-terminated line"
        )
    if text.endswith("\r\n"):
        identity = text[:-2]
    elif text.endswith("\n"):
        identity = text[:-1]
    else:
        raise ValueError(
            "CMake build identity must be one bounded LF- or CRLF-terminated line"
        )
    if "\r" in identity or "\n" in identity:
        raise ValueError(
            "CMake build identity must be one bounded LF- or CRLF-terminated line"
        )
    segments = identity.split(";")
    if len(segments) != len(CMAKE_BUILD_IDENTITY_FIELDS):
        raise ValueError("CMake build identity has missing or extra fields")
    values: dict[str, str] = {}
    for expected_key, segment in zip(CMAKE_BUILD_IDENTITY_FIELDS, segments, strict=True):
        key, separator, value = segment.partition("=")
        if separator != "=" or key != expected_key or not value:
            raise ValueError(
                "CMake build identity fields are absent, empty, duplicated, or out of order"
            )
        values[key] = value

    expected_values = {
        "facman": source_revisions["factorio_launcher"],
        "universal_launcher": source_revisions["universal_launcher"],
        "universal_setup": source_revisions["universal_setup"],
        "source_dirty": str(source_dirty).lower(),
    }
    for key, expected in expected_values.items():
        if values[key] != expected:
            raise ValueError(f"CMake build identity {key} differs from package custody")
    if provider_class == "canonical":
        required_provider_state = {
            "provider_mode": "source",
            "provider_lock_kind": "tracked",
            "provider_conformance_only": "false",
            "provider_sdk_consumption_candidate": "false",
            "provider_candidate_differs_from_tracked": "false",
            "provider_consumption_classification": "tracked_source",
            "ulk_session_consumer_canary": "false",
        }
    elif provider_class == "repaired_provider_canary":
        required_provider_state = {
            "provider_mode": "source",
            "provider_lock_kind": "sdk_candidate",
            "provider_conformance_only": "false",
            "provider_sdk_consumption_candidate": "true",
            "provider_candidate_differs_from_tracked": "true",
            "provider_consumption_classification": "sdk_candidate_source",
            "provider_release_identity_coherent": "false",
            "ulk_session_consumer_canary": "false",
        }
    else:
        raise ValueError(f"unknown package provider class: {provider_class}")
    for key, expected in required_provider_state.items():
        if values[key] != expected:
            raise ValueError(
                f"package construction requires exact {provider_class} provider identity; "
                f"{key}={values[key]!r}"
            )
    if values["provider_source_linkage"] not in {"static", "shared"}:
        raise ValueError(
            "CMake build identity provider source linkage must be static or shared"
        )
    if values["provider_release_identity_coherent"] not in {"true", "false"}:
        raise ValueError(
            "CMake build identity provider release coherence must be Boolean"
        )
    return identity, values


def validate_build_composition(
    profile_id: str,
    profile: dict[str, Any],
    bundle: dict[str, Any],
    build_root: Path,
    *,
    source_revisions: dict[str, str] | None = None,
    provider_class: str = "canonical",
) -> None:
    expected_linkage = WINDOWS_PACKAGE_PROVIDER_LINKAGE.get(profile_id)
    if expected_linkage is None:
        return
    linkage = table(profile.get("linkage"))
    declared_linkage = str(linkage.get("provider_source_linkage", ""))
    if declared_linkage != expected_linkage:
        raise ValueError(
            f"{profile_id}: package profile/build-root composition requires "
            f"provider source linkage {expected_linkage}; profile declares "
            f"{declared_linkage or '<missing>'}"
        )
    if str(linkage.get("model", "")) != str(bundle.get("linkage_model", "")):
        raise ValueError(
            f"{profile_id}: package profile and bundle linkage models differ"
        )
    cache = cmake_cache_values(build_root / "CMakeCache.txt")
    provider_mode = cache.get("FACMAN_PROVIDER_MODE", "")
    cache_linkage = cache.get("FACMAN_PROVIDER_SOURCE_LINKAGE", "")
    if provider_mode != "source" or cache_linkage != expected_linkage:
        raise ValueError(
            f"{profile_id}: invalid package/build-root composition; expected "
            f"FACMAN_PROVIDER_MODE=source and "
            f"FACMAN_PROVIDER_SOURCE_LINKAGE={expected_linkage}, got "
            f"mode={provider_mode or '<missing>'} and "
            f"linkage={cache_linkage or '<missing>'}"
        )
    _identity, identity_values = cmake_build_identity_values(
        build_root,
        source_revisions or pinned_source_revisions(),
        git_dirty(),
        provider_class=provider_class,
    )
    identity_linkage = identity_values["provider_source_linkage"]
    if identity_linkage != cache_linkage:
        raise ValueError(
            f"{profile_id}: mixed static/shared build identities; CMake cache "
            f"declares {cache_linkage} but exact build identity declares "
            f"{identity_linkage}"
        )


def validate_distinct_build_roots(static_root: Path, shared_root: Path) -> None:
    static_resolved = static_root.resolve()
    shared_resolved = shared_root.resolve()
    aliased = static_resolved == shared_resolved
    if not aliased and static_resolved.exists() and shared_resolved.exists():
        aliased = os.path.samefile(static_resolved, shared_resolved)
    if aliased:
        raise ValueError(
            "static and shared Windows package build roots must be distinct"
        )


def validate_install_composition(profile_id: str, install_root: Path) -> None:
    expected_linkage = WINDOWS_PACKAGE_PROVIDER_LINKAGE.get(profile_id)
    if expected_linkage is None:
        return
    installed_runtime_files = {
        path.name.lower()
        for path in install_root.rglob("*")
        if path.is_file() and path.name.lower() in SHARED_RUNTIME_FILENAMES
    }
    if expected_linkage == "static" and installed_runtime_files:
        raise ValueError(
            f"{profile_id}: static install closure contains unselected shared "
            f"runtime files: {', '.join(sorted(installed_runtime_files))}"
        )
    if expected_linkage == "shared":
        for target in SHARED_RUNTIME_TARGETS:
            package_components.resolve(install_root, target)
    validate_contract_schema_inventory(install_root)


def validate_contract_schema_inventory(install_root: Path) -> None:
    expected_root = ROOT / "contracts" / "schema"
    installed_root = install_root / "share" / "facman" / "contracts" / "schema"
    if not installed_root.is_dir():
        raise ValueError("shared/static install closure is missing contracts/schema")
    expected = {
        path.relative_to(expected_root).as_posix()
        for path in expected_root.rglob("*")
        if path.is_file()
    }
    installed = {
        path.relative_to(installed_root).as_posix()
        for path in installed_root.rglob("*")
        if path.is_file()
    }
    if installed != expected:
        missing = sorted(expected - installed)
        unexpected = sorted(installed - expected)
        detail = []
        if missing:
            detail.append("missing=" + ",".join(missing[:5]))
        if unexpected:
            detail.append("unexpected=" + ",".join(unexpected[:5]))
        raise ValueError(
            "contracts/schema inventory differs from the canonical package "
            "manifest tree: " + "; ".join(detail)
        )


def toolchain_identity(profile: dict[str, Any], build_root: Path) -> dict[str, str]:
    if profile.get("target_os") == "linux":
        return linux_toolchain_identity(profile)
    if profile.get("target_os") == "macos":
        return macos_toolchain_identity(profile, build_root)
    cache = cmake_cache_values(build_root / "CMakeCache.txt")
    proof = table(profile.get("proof"))
    generator = cache.get("CMAKE_GENERATOR", "unknown")
    linker = cache.get("CMAKE_LINKER", "unknown")
    return {
        "runner": os.environ.get("ImageOS", str(proof.get("runner", f"{sys.platform}-local"))),
        "machine": platform.machine(),
        "operating_system": platform.platform(),
        "generator": generator,
        "compiler": cache.get("CMAKE_CXX_COMPILER", f"C++ via {generator}"),
        "linker": tool_path_identity(linker),
    }


def cmake_cache_values(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise ValueError(f"toolchain cache is missing: {path}")
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line or line.startswith(("#", "//")) or "=" not in line or ":" not in line:
            continue
        key_and_type, value = line.split("=", 1)
        key, _type = key_and_type.split(":", 1)
        values[key] = value
    return values


def tool_path_identity(value: str) -> str:
    if value == "unknown":
        return value
    normalized = value.replace("\\", "/")
    parts = [part for part in normalized.split("/") if part]
    name = parts[-1] if parts else value
    versions = [part for part in parts if re.fullmatch(r"\d+(?:\.\d+){1,3}", part)]
    return name + (f" {versions[-1]}" if versions else "")


def linux_toolchain_identity(profile: dict[str, Any]) -> dict[str, str]:
    proof = table(profile.get("proof"))
    identity = {
        "runner": str(proof.get("runner", "")),
        "machine": platform.machine(),
        "libc": " ".join(platform.libc_ver()).strip(),
        "compiler": first_line(run_capture(["c++", "--version"])),
        "linker": first_line(run_capture(["ld", "--version"])),
    }
    expected_libc = str(proof.get("libc_baseline", "")).replace("_", " ")
    if identity["libc"] != expected_libc:
        raise ValueError(
            "linux_portable_cli_x64: declared Ubuntu 24.04 glibc 2.39 baseline "
            f"does not match runner identity {identity['libc']!r}"
        )
    return identity


def macos_toolchain_identity(profile: dict[str, Any], build_root: Path) -> dict[str, str]:
    proof = table(profile.get("proof"))
    cache = cmake_cache_values(build_root / "CMakeCache.txt")
    deployment_target = cache.get("CMAKE_OSX_DEPLOYMENT_TARGET", "")
    expected_deployment = str(proof.get("deployment_target", ""))
    if deployment_target != expected_deployment:
        raise ValueError(
            "macos_portable_cli_x64: CMake deployment target must be exactly 13.0, "
            f"got {deployment_target!r}"
        )
    machine = platform.machine().lower()
    if machine not in {"x86_64", "amd64"}:
        raise ValueError(f"macos_portable_cli_x64: Intel x64 runner required, got {machine}")
    return {
        "runner": str(proof.get("runner", "")),
        "machine": platform.machine(),
        "operating_system": platform.platform(),
        "generator": cache.get("CMAKE_GENERATOR", "unknown"),
        "compiler": first_line(run_capture([cache.get("CMAKE_CXX_COMPILER", "c++"), "--version"])),
        "linker": first_line(run_capture(["ld", "-v"])),
        "deployment_target": deployment_target,
        "sdk": run_capture(["xcrun", "--show-sdk-version"]).strip(),
    }


def write_platform_metadata(
    package_root: Path,
    profile: dict[str, Any],
    build_root: Path,
) -> None:
    if profile.get("target_os") == "macos":
        write_macos_platform_metadata(package_root, profile, build_root)
        return
    if profile.get("target_os") != "linux":
        return
    executable = package_root / "bin" / "facman"
    header = run_capture(["readelf", "-h", str(executable)])
    dynamic = run_capture(["readelf", "-d", str(executable)])
    ldd = run_capture(["ldd", str(executable)])
    if "Advanced Micro Devices X86-64" not in header:
        raise ValueError("linux_portable_cli_x64: ELF machine is not x86-64")
    if "(RPATH)" in dynamic or "(RUNPATH)" in dynamic:
        raise ValueError("linux_portable_cli_x64: source/build RPATH or RUNPATH is forbidden")
    needed = sorted(set(re.findall(r"Shared library: \[(.*?)\]", dynamic)))
    proof = table(profile.get("proof"))
    allowed = package_platform_proof.allowed_dependencies(profile)
    unexpected = sorted(set(needed) - allowed)
    if unexpected:
        raise ValueError(
            "linux_portable_cli_x64: unexpected dynamic dependencies: "
            + ", ".join(unexpected)
        )
    metadata = {
        "schema": "facman.linux_linkage_proof.v1",
        "profile_id": "linux_portable_cli_x64",
        "runner": str(proof.get("runner", "")),
        "architecture": str(proof.get("architecture", "")),
        "elf_machine": "Advanced Micro Devices X86-64",
        "linkage_model": "project_static_system_dynamic",
        "needed": needed,
        "allowed_needed": sorted(allowed),
        "rpath": None,
        "runpath": None,
        "ldd": [line.strip() for line in ldd.splitlines() if line.strip()],
        "toolchain": linux_toolchain_identity(profile),
    }
    schema = json_contract.load_schema(
        ROOT / "contracts" / "schema" / "release" / "linux_linkage_proof.v1.schema.json"
    )
    problems = json_contract.validate(metadata, schema)
    if problems:
        raise ValueError("Linux linkage metadata violates its contract: " + "; ".join(problems))
    package_manifests.write_json(package_root / "manifest" / "linux_linkage.v1.json", metadata)


def write_macos_platform_metadata(package_root: Path, profile: dict[str, Any], build_root: Path) -> None:
    proof = table(profile.get("proof"))
    executable = package_root / "bin" / "facman"
    raw_file_identity = run_capture(["file", str(executable)]).strip()
    identity_prefix, separator, file_identity = raw_file_identity.partition(":")
    if separator != ":" or Path(identity_prefix) != executable:
        raise ValueError("macos_portable_cli_x64: file tool did not identify the packaged executable")
    file_identity = file_identity.strip()
    architectures = run_capture(["lipo", "-archs", str(executable)]).split()
    if architectures != ["x86_64"]:
        raise ValueError(
            "macos_portable_cli_x64: Mach-O architecture must be exactly x86_64, "
            f"got {architectures}"
        )
    if file_identity != "Mach-O 64-bit executable x86_64":
        raise ValueError("macos_portable_cli_x64: file identity is not an x86_64 Mach-O executable")

    otool_libraries = run_capture(["otool", "-L", str(executable)])
    dependencies = sorted(
        {
            line.strip().split(" (", 1)[0]
            for line in otool_libraries.splitlines()[1:]
            if line.strip()
        }
    )
    allowed_prefixes = string_list(proof.get("allowed_system_dependency_prefixes"))
    unexpected = [
        dependency
        for dependency in dependencies
        if not any(dependency.startswith(prefix) for prefix in allowed_prefixes)
    ]
    if not dependencies:
        raise ValueError("macos_portable_cli_x64: no system dynamic dependencies were recorded")
    if unexpected:
        raise ValueError(
            "macos_portable_cli_x64: unexpected dynamic dependencies: "
            + ", ".join(unexpected)
        )

    load_commands = run_capture(["otool", "-l", str(executable)])
    if re.search(r"^\s*cmd LC_RPATH\s*$", load_commands, flags=re.MULTILINE):
        raise ValueError("macos_portable_cli_x64: LC_RPATH is forbidden")
    deployment = re.search(r"\bminos\s+([0-9.]+)", load_commands)
    if deployment is None:
        deployment = re.search(
            r"cmd LC_VERSION_MIN_MACOSX.*?\bversion\s+([0-9.]+)",
            load_commands,
            flags=re.DOTALL,
        )
    deployment_target = deployment.group(1) if deployment else ""
    expected_deployment = str(proof.get("deployment_target", ""))
    if deployment_target != expected_deployment:
        raise ValueError(
            "macos_portable_cli_x64: Mach-O deployment target must be 13.0, "
            f"got {deployment_target!r}"
        )
    sdk_match = re.search(r"\bsdk\s+([0-9.]+)", load_commands)
    sdk = sdk_match.group(1) if sdk_match else run_capture(["xcrun", "--show-sdk-version"]).strip()
    toolchain = macos_toolchain_identity(profile, build_root)
    metadata = {
        "schema": "facman.macos_linkage_proof.v1",
        "profile_id": "macos_portable_cli_x64",
        "runner": str(proof.get("runner", "")),
        "architecture": str(proof.get("architecture", "")),
        "file_identity": file_identity,
        "linkage_model": "project_static_system_dynamic",
        "deployment_target": deployment_target,
        "sdk": sdk,
        "dependencies": dependencies,
        "allowed_dependency_prefixes": allowed_prefixes,
        "rpath": None,
        "toolchain": toolchain,
    }
    schema = json_contract.load_schema(
        ROOT / "contracts" / "schema" / "release" / "macos_linkage_proof.v1.schema.json"
    )
    problems = json_contract.validate(metadata, schema)
    if problems:
        raise ValueError("macOS linkage metadata violates its contract: " + "; ".join(problems))
    package_manifests.write_json(package_root / "manifest" / "macos_linkage.v1.json", metadata)


def run_capture(command: list[str]) -> str:
    completed = subprocess.run(
        command,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if completed.returncode != 0:
        raise ValueError(
            f"required tool failed ({completed.returncode}): {' '.join(command)}: "
            f"{completed.stdout.strip()}"
        )
    return completed.stdout


def first_line(value: str) -> str:
    return value.splitlines()[0].strip() if value.splitlines() else "unknown"


def validate_package_root(
    package_root: Path,
    profile: dict[str, Any],
    component_records: list[dict[str, Any]],
    *,
    custody_class: str = "release_resolution",
) -> None:
    profile_id = str(profile.get("id", ""))
    canary_record = package_root / "manifest" / REPAIRED_PROVIDER_CANARY_RECORD
    if custody_class == REPAIRED_PROVIDER_CANARY_CUSTODY:
        try:
            canary = json.loads(canary_record.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError("repaired-provider canary metadata is malformed") from error
        problems = json_contract.validate(
            canary,
            json_contract.load_schema(REPAIRED_PROVIDER_CANARY_SCHEMA),
        )
        if problems:
            raise ValueError(
                "repaired-provider canary metadata violates its contract: "
                + "; ".join(problems)
            )
        if (package_root / "manifest" / "resolution").exists():
            raise ValueError(
                f"{profile_id}: repaired-provider canary must not contain canonical "
                "release resolution metadata"
            )
    elif canary_record.exists():
        raise ValueError(
            f"{profile_id}: canonical or integration package contains canary-only custody"
        )
    if profile_id in COMPOSITION_PROFILES:
        load_resolution_root = package_root / "manifest" / "resolution"
        integration_record = (
            package_root / "manifest" / "integration-source-observation.v1.json"
        )
        if custody_class == "unpublished_integration":
            if load_resolution_root.exists():
                raise ValueError(
                    f"{profile_id}: integration package must not contain release resolution metadata"
                )
            load_integration_source_observation(
                integration_record,
                workspace_lock_path=WORKSPACE_LOCK_PATH,
                expected_profile=profile_id,
            )
        else:
            if integration_record.exists():
                raise ValueError(
                    f"{profile_id}: release-oriented package contains integration-only custody"
                )
            if not load_resolution_root.is_dir():
                raise ValueError(f"{profile_id}: package omits resolved composition metadata")
            embedded = load_runtime_projection(load_resolution_root, ROOT)
            if embedded["runtime_metadata"].get("target_id") != profile_id:
                raise ValueError(f"{profile_id}: embedded resolution has the wrong target identity")
    for relative in required_paths(profile):
        if not (package_root / normalize_destination(relative)).exists():
            raise ValueError(f"{profile['id']}: missing required package path {relative}")
    for record in component_records:
        if not (package_root / str(record["destination"])).exists():
            raise ValueError(f"{profile['id']}: missing component {record['destination']}")
    for path in package_root.rglob("*"):
        relative = path.relative_to(package_root).as_posix()
        lowered = relative.lower()
        for marker in FORBIDDEN_FILE_MARKERS:
            if marker.lower() in lowered:
                raise ValueError(f"{profile['id']}: forbidden package payload marker {marker}: {relative}")
        if path.is_file():
            for marker in PYTHON_RUNTIME_MARKERS:
                if marker in lowered:
                    raise ValueError(f"{profile['id']}: Python runtime marker is not allowed: {relative}")


def required_paths(profile: dict[str, Any]) -> list[str]:
    required = table(profile.get("required_components"))
    paths = []
    for key in ["binaries", "libraries"]:
        paths.extend(string_list(required.get(key)))
    for license_name in string_list(required.get("licenses")):
        paths.append(f"licenses/{Path(license_name).name}")
    for key in ["contracts", "content"]:
        value = required.get(key)
        if value:
            paths.append(str(value))
    paths.extend(["docs", "release", "manifest/package.v1.toml"])
    return paths


def resolve_source_target(source_target: str, build_root: Path) -> Path:
    names = source_target_candidates(source_target)
    if source_target == "apps/gui/windows/winforms":
        names = ["FacMan.WinForms.exe"]
        output_root = ROOT / "apps" / "gui" / "windows" / "winforms" / "bin"
        roots = [output_root / "Release", output_root / "Debug"]
    else:
        configurations = ["Release", "Debug", "RelWithDebInfo", "MinSizeRel"]
        roots = [build_root, *[build_root / configuration for configuration in configurations]]
        for dependency in ["universal-launcher", "universal-setup"]:
            roots.extend(build_root / dependency / configuration for configuration in configurations)
    for root in roots:
        for name in names:
            candidate = root / name
            if candidate.is_file():
                return candidate
    searched = ", ".join(str(root / name) for root in roots for name in names)
    raise ValueError(f"missing built artifact for {source_target}; deterministic candidates: {searched}")


def pinned_source_revisions() -> dict[str, str]:
    values = {
        "factorio_launcher": git_commit(ROOT),
        "factorio_binding": "unknown",
        "universal_launcher": "unknown",
        "universal_setup": "unknown",
    }
    locked = _load_workspace_lock()
    for component in locked:
        component_id = component.get("id")
        pin = component.get("pin", "")
        if component_id in values and pin:
            values[component_id] = pin
    missing = [component_id for component_id, pin in values.items() if not pin or pin == "unknown"]
    if missing:
        raise ValueError(f"missing pinned source revisions for {', '.join(sorted(missing))}")
    return values


def _load_workspace_lock() -> list[dict[str, Any]]:
    if not WORKSPACE_LOCK_PATH.is_file():
        raise ValueError(f"package build requires a workspace lock: {WORKSPACE_LOCK_PATH}")
    data = load_toml(WORKSPACE_LOCK_PATH)
    components = data.get("component")
    if not isinstance(components, list):
        raise ValueError("workspace lock component list is missing")
    return components


def source_target_candidates(source_target: str) -> list[str]:
    return {
        "facman_cli": ["facman.exe", "facman"],
        "facman_tui": ["facman-tui.exe", "facman-tui"],
        "facman_daemon": ["facmand.exe", "facmand"],
        "ulk_shared": ["ulk.dll", "libulk.so", "libulk.dylib"],
        "usk_shared": ["usk.dll", "libusk.so", "libusk.dylib"],
        "flb_factorio_shared": ["flb_factorio.dll", "libflb_factorio.so", "libflb_factorio.dylib"],
    }.get(source_target, [source_target])


def component_kind(source_target: str) -> str:
    if source_target in {"contracts/schema", "content/factorio"}:
        return "contracts" if source_target.startswith("contracts") else "content"
    if source_target.endswith("_shared"):
        return "runtime_library"
    if source_target == "facman_daemon":
        return "daemon"
    return "frontend"


def maybe_copy_windows_alias(source: Path, destination: Path) -> None:
    if source.suffix.lower() != ".exe" or destination.suffix:
        return
    alias = destination.with_name(destination.name + ".exe")
    if not alias.exists():
        copy_file(source, alias)


def write_archive(package_root: Path, dist_root: Path, bundle: dict[str, Any]) -> Path:
    owned_output.ensure_owned_output_root(dist_root, "package-archives")
    build_info = json.loads(
        (package_root / "manifest" / "build_info.v1.json").read_text(encoding="utf-8")
    )
    version = str(build_info["filename_version"])
    artifact_template = str(bundle.get("artifact_id", package_root.name))
    version_prefix = artifact_template.split("<version>", 1)[0]
    replacement = version
    if version_prefix and version.lower().startswith(version_prefix.lower()):
        replacement = version[len(version_prefix):]
    artifact_id = artifact_template.replace("<version>", replacement)
    archive_base = dist_root / artifact_id
    package_type = str(bundle.get("package_type", ""))
    archive_suffix = ".tar.gz" if package_type == "tarball" else ".zip"
    archive_path = Path(str(archive_base) + archive_suffix)
    return package_archive.write(package_root, archive_path, package_type, build_info["source_timestamp_utc"])


def load_profile(profile_id: str) -> tuple[Path, dict[str, Any]]:
    return package_profile.load(ROOT, profile_id)


def normalize_destination(value: str) -> str:
    if "\\" in value or ":" in value:
        raise ValueError(f"package destination must be relative and portable: {value}")
    pure = PurePosixPath(value.rstrip("/"))
    if pure.is_absolute() or any(part in ("", ".", "..") for part in pure.parts):
        raise ValueError(f"package destination must not escape package root: {value}")
    return pure.as_posix()


def copy_tree(source: Path, destination: Path) -> None:
    if not source.is_dir():
        raise ValueError(f"missing source directory: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination, dirs_exist_ok=True)


def copy_file(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise ValueError(f"missing source file: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    if os.name != "nt" and source.stat().st_mode & 0o111:
        destination.chmod(destination.stat().st_mode | 0o755)


def assert_safe_output_root(path: Path) -> None:
    resolved = path.resolve()
    repo_root = ROOT.resolve()
    if resolved == repo_root:
        raise ValueError("refusing to clean repository root")
    if repo_root in resolved.parents and "build" not in resolved.parts:
        raise ValueError(f"refusing to clean non-build repository path: {resolved}")


def assert_host_matches_profile(profile_id: str, profile: dict[str, Any]) -> None:
    target_os = str(profile.get("target_os", ""))
    if target_os == "windows" and os.name != "nt":
        raise ValueError(f"{profile_id}: Windows built-artifact proof must run on Windows")
    if target_os == "linux" and not sys.platform.startswith("linux"):
        raise ValueError(f"{profile_id}: Linux built-artifact proof must run on Linux")
    if target_os == "macos" and sys.platform != "darwin":
        raise ValueError(f"{profile_id}: macOS built-artifact proof must run on macOS")
    if profile_id in {
        "windows_portable_cli_x64",
        "linux_portable_cli_x64",
        "macos_portable_cli_x64",
        "windows_portable_tui_x64",
        "linux_portable_tui_x64",
        "macos_portable_tui_x64",
    }:
        machine = platform.machine().lower()
        if machine not in {"amd64", "x86_64"}:
            raise ValueError(f"{profile_id}: x64 proof cannot run on host architecture {machine}")


def find_dependency_repo(name: str) -> Path:
    candidates = [
        ROOT / "external" / name,
        ROOT.parent / name,
        ROOT.parents[1] / "Universal" / name,
        ROOT.parents[1] / name,
    ]
    for candidate in candidates:
        if (candidate / ".git").exists():
            return candidate
    return candidates[0]


def git_commit(repo: Path = ROOT) -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return completed.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def table(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def git_dirty(repo: Path = ROOT) -> bool:
    completed = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=normal"],
        cwd=repo,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.returncode != 0 or bool(completed.stdout.strip())


def source_state_digest(repo: Path = ROOT) -> str:
    digest = hashlib.sha256()
    diff = subprocess.run(
        ["git", "diff", "--binary", "HEAD"],
        cwd=repo,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if diff.returncode != 0:
        raise ValueError("cannot hash the source diff for provenance")
    digest.update(diff.stdout)
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
        cwd=repo,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if untracked.returncode != 0:
        raise ValueError("cannot list untracked source files for provenance")
    for encoded in sorted(item for item in untracked.stdout.split(b"\0") if item):
        path = repo / encoded.decode("utf-8")
        digest.update(b"\0path\0" + encoded + b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def toml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    raise ValueError(f"built package manifest value is not a supported scalar: {value!r}")


if __name__ == "__main__":
    raise SystemExit(main())
