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

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import (
    json_contract,
    owned_output,
    package_hash_manifest,
    package_layout_check,
    provenance_build,
)

DEFAULT_OUT = ROOT / "build" / "packages"
DEFAULT_BUILD_ROOT = ROOT / "build" / "native-smoke"
DEFAULT_DIST = ROOT / "dist"
SUPPORTED_BUILT_PROFILES = {
    "linux_portable_cli_x64",
    "macos_portable_cli_x64",
    "windows_portable_cli_x64",
    "portable_cli_x64",
    "windows_legacy_winforms_x64",
}
WORKSPACE_LOCK_PATH = ROOT / "release" / "index" / "workspace_lock.v1.toml"
DEPENDENCY_LOCK_PATH = ROOT / "release" / "index" / "dependency_lock.v1.toml"
VERSION_PATH = ROOT / "release" / "index" / "version.v1.toml"
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
BUILT_PACKAGE_SCHEMA = ROOT / "contracts" / "schema" / "release" / "built_package.v1.schema.json"


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    parser = argparse.ArgumentParser(description="Build unsigned local FacMan package roots.")
    parser.add_argument("--profile", required=True, help="release profile id, for example windows_portable_cli_x64")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="output root containing per-profile package roots")
    parser.add_argument("--build-root", default=str(DEFAULT_BUILD_ROOT), help="native CMake build root")
    parser.add_argument("--dist", default=str(DEFAULT_DIST), help="zip archive output root; use '' to disable")
    parser.add_argument("--no-clean", action="store_true", help="do not delete an existing profile package root")
    args = parser.parse_args(argv)

    try:
        package_root = build_profile(
            profile_id=args.profile,
            out_root=Path(args.out).resolve(),
            build_root=Path(args.build_root).resolve(),
            dist_root=Path(args.dist).resolve() if args.dist else None,
            clean=not args.no_clean,
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
) -> Path:
    assert_safe_output_root(out_root)
    owned_output.ensure_owned_output_root(out_root, "built-packages")
    profile_path, profile = load_profile(profile_id)
    if profile_id not in SUPPORTED_BUILT_PROFILES:
        raise ValueError(f"{profile_id}: built artifact proof is not enabled for this profile")
    if profile.get("publication") is False:
        raise ValueError(f"{profile_id}: profile is explicitly unpublished")
    assert_host_matches_profile(profile_id, profile)
    bundle_path = ROOT / str(profile.get("package_manifest", ""))
    bundle = package_layout_check.expand_bundle_manifest(bundle_path, load_toml(bundle_path), [])
    package_root = out_root / profile_id
    if clean and package_root.exists():
        owned_output.assert_owned_output_root(out_root, "built-packages")
        shutil.rmtree(package_root)
    package_root.mkdir(parents=True, exist_ok=True)

    component_records = copy_bundle_components(package_root, build_root, bundle)
    copy_support_payloads(package_root, profile, profile_path, bundle_path)
    write_package_manifest(package_root, profile_path, profile, bundle_path, bundle)
    build_info = write_build_info(package_root, profile_id, profile, bundle, build_root)
    provenance_build.write_package_sbom(package_root, build_info)
    write_platform_metadata(package_root, profile, build_root)
    validate_package_root(package_root, profile, component_records)
    package_hash_manifest.write_manifests(package_root, component_records)
    if dist_root is not None:
        artifact = write_archive(package_root, dist_root, bundle)
        provenance_build.write_artifact_provenance(package_root, artifact)
    return package_root


def copy_bundle_components(
    package_root: Path,
    build_root: Path,
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
            copy_tree(ROOT / source_target, destination_path)
        else:
            source = resolve_source_target(source_target, build_root)
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
    profile_path: Path,
    bundle_path: Path,
) -> None:
    if profile.get("id") in {"linux_portable_cli_x64", "macos_portable_cli_x64"}:
        for name in ["PACKAGE_LAYOUT.md", "SUPPORT_POLICY.md"]:
            copy_file(
                ROOT / "docs" / "release" / name,
                package_root / "docs" / "release" / name,
            )
    else:
        copy_tree(ROOT / "docs" / "release", package_root / "docs" / "release")
    copy_tree(ROOT / "release" / "index", package_root / "release" / "index")
    if profile.get("id") not in {"linux_portable_cli_x64", "macos_portable_cli_x64"}:
        copy_tree(ROOT / "release" / "packaging", package_root / "release" / "packaging")
    profile_dir = profile_path.parent
    copy_tree(profile_dir, package_root / "release" / "profiles" / profile_dir.name)
    copy_file(ROOT / "release" / "profiles" / "profile_catalog.v1.toml", package_root / "release" / "profiles" / "profile_catalog.v1.toml")
    copy_file(bundle_path, package_root / "release" / bundle_path.relative_to(ROOT / "release"))
    copy_file(ROOT / "README.md", package_root / "docs" / "README.md")
    for license_name in string_list(profile.get("licenses")):
        source = ROOT / license_name
        copy_file(source, package_root / "licenses" / source.name)


def write_package_manifest(
    package_root: Path,
    profile_path: Path,
    profile: dict[str, Any],
    bundle_path: Path,
    bundle: dict[str, Any],
) -> None:
    manifest = package_root / "manifest"
    manifest.mkdir(parents=True, exist_ok=True)
    revisions = pinned_source_revisions()
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
) -> dict[str, Any]:
    build_index = load_toml(VERSION_PATH)
    source_revisions = pinned_source_revisions()
    info = {
        "schema": "facman.package_build_info.v1",
        "profile_id": profile_id,
        "artifact_level": "built-artifact",
        "canonical_version": build_index["canonical_version"],
        "filename_version": build_index["filename_version"],
        "source_commit": source_revisions["factorio_launcher"],
        "source_timestamp_policy": "source_commit_utc",
        "source_timestamp_utc": provenance_build.source_commit_timestamp(
            source_revisions["factorio_launcher"]
        ),
        "source_dirty": git_dirty(),
        "source_state_sha256": source_state_digest(),
        "source_revisions": {
            "factorio_launcher": source_revisions["factorio_launcher"],
            "universal_launcher": source_revisions["universal_launcher"],
            "universal_setup": source_revisions["universal_setup"],
        },
        "target_os": profile.get("target_os"),
        "target_arch": profile.get("target_arch"),
        "package_type": bundle.get("package_type"),
        "signed": False,
        "published": False,
        "toolchain": toolchain_identity(profile, build_root),
    }
    (package_root / "manifest" / "build_info.v1.json").write_text(
        json.dumps(info, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return info


def toolchain_identity(profile: dict[str, Any], build_root: Path) -> dict[str, str]:
    if profile.get("target_os") == "linux":
        return linux_toolchain_identity()
    if profile.get("target_os") == "macos":
        return macos_toolchain_identity(build_root)
    cache = cmake_cache_values(build_root / "CMakeCache.txt")
    generator = cache.get("CMAKE_GENERATOR", "unknown")
    linker = cache.get("CMAKE_LINKER", "unknown")
    return {
        "runner": os.environ.get("ImageOS", f"{sys.platform}-local"),
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


def linux_toolchain_identity() -> dict[str, str]:
    identity = {
        "runner": "ubuntu-24.04",
        "machine": platform.machine(),
        "libc": " ".join(platform.libc_ver()).strip(),
        "compiler": first_line(run_capture(["c++", "--version"])),
        "linker": first_line(run_capture(["ld", "--version"])),
    }
    if identity["libc"] != "glibc 2.39":
        raise ValueError(
            "linux_portable_cli_x64: declared Ubuntu 24.04 glibc 2.39 baseline "
            f"does not match runner identity {identity['libc']!r}"
        )
    return identity


def macos_toolchain_identity(build_root: Path) -> dict[str, str]:
    cache = cmake_cache_values(build_root / "CMakeCache.txt")
    deployment_target = cache.get("CMAKE_OSX_DEPLOYMENT_TARGET", "")
    if deployment_target != "13.0":
        raise ValueError(
            "macos_portable_cli_x64: CMake deployment target must be exactly 13.0, "
            f"got {deployment_target!r}"
        )
    machine = platform.machine().lower()
    if machine not in {"x86_64", "amd64"}:
        raise ValueError(f"macos_portable_cli_x64: Intel x64 runner required, got {machine}")
    return {
        "runner": "macos-15-intel",
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
        write_macos_platform_metadata(package_root, build_root)
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
    allowed = {
        "ld-linux-x86-64.so.2",
        "libc.so.6",
        "libdl.so.2",
        "libgcc_s.so.1",
        "libm.so.6",
        "libpthread.so.0",
        "librt.so.1",
        "libstdc++.so.6",
    }
    unexpected = sorted(set(needed) - allowed)
    if unexpected:
        raise ValueError(
            "linux_portable_cli_x64: unexpected dynamic dependencies: "
            + ", ".join(unexpected)
        )
    metadata = {
        "schema": "facman.linux_linkage_proof.v1",
        "profile_id": "linux_portable_cli_x64",
        "runner": "ubuntu-24.04",
        "architecture": "x86_64",
        "elf_machine": "Advanced Micro Devices X86-64",
        "linkage_model": "project_static_system_dynamic",
        "needed": needed,
        "allowed_needed": sorted(allowed),
        "rpath": None,
        "runpath": None,
        "ldd": [line.strip() for line in ldd.splitlines() if line.strip()],
        "toolchain": linux_toolchain_identity(),
    }
    schema = json_contract.load_schema(
        ROOT / "contracts" / "schema" / "release" / "linux_linkage_proof.v1.schema.json"
    )
    problems = json_contract.validate(metadata, schema)
    if problems:
        raise ValueError("Linux linkage metadata violates its contract: " + "; ".join(problems))
    (package_root / "manifest" / "linux_linkage.v1.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_macos_platform_metadata(package_root: Path, build_root: Path) -> None:
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
    allowed_prefixes = ["/System/Library/Frameworks/", "/usr/lib/"]
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
    if deployment_target != "13.0":
        raise ValueError(
            "macos_portable_cli_x64: Mach-O deployment target must be 13.0, "
            f"got {deployment_target!r}"
        )
    sdk_match = re.search(r"\bsdk\s+([0-9.]+)", load_commands)
    sdk = sdk_match.group(1) if sdk_match else run_capture(["xcrun", "--show-sdk-version"]).strip()
    toolchain = macos_toolchain_identity(build_root)
    metadata = {
        "schema": "facman.macos_linkage_proof.v1",
        "profile_id": "macos_portable_cli_x64",
        "runner": "macos-15-intel",
        "architecture": "x86_64",
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
    (package_root / "manifest" / "macos_linkage.v1.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


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
) -> None:
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
        roots = [ROOT / "apps" / "gui" / "windows" / "winforms" / "bin" / "Debug"]
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
    build_index = load_toml(VERSION_PATH)
    version = str(build_index["filename_version"])
    artifact_template = str(bundle.get("artifact_id", package_root.name))
    version_prefix = artifact_template.split("<version>", 1)[0]
    replacement = version
    if version_prefix and version.lower().startswith(version_prefix.lower()):
        replacement = version[len(version_prefix):]
    artifact_id = artifact_template.replace("<version>", replacement)
    archive_base = dist_root / artifact_id
    package_type = str(bundle.get("package_type", ""))
    archive_format = "gztar" if package_type == "tarball" else "zip"
    archive_suffix = ".tar.gz" if archive_format == "gztar" else ".zip"
    archive_path = Path(str(archive_base) + archive_suffix)
    if archive_path.exists():
        archive_path.unlink()
    shutil.make_archive(str(archive_base), archive_format, root_dir=package_root)
    return archive_path


def load_profile(profile_id: str) -> tuple[Path, dict[str, Any]]:
    profile_path = ROOT / "release" / "profiles" / profile_id / "profile.toml"
    if not profile_path.is_file():
        raise ValueError(f"unknown release profile: {profile_id}")
    profile = load_toml(profile_path)
    if profile.get("id") != profile_id:
        raise ValueError(f"{profile_path}: profile id mismatch")
    return profile_path, profile


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
    target_arch = str(profile.get("target_arch", ""))
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
