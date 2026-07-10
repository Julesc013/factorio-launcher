from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import owned_output, package_hash_manifest, package_layout_check

DEFAULT_OUT = ROOT / "build" / "packages"
DEFAULT_BUILD_ROOT = ROOT / "build" / "native-smoke"
DEFAULT_DIST = ROOT / "dist"
SUPPORTED_BUILT_PROFILES = {
    "windows_portable_cli_x64",
    "portable_cli_x64",
    "portable_tui_x64",
    "windows_legacy_winforms_x64",
}
WORKSPACE_LOCK_PATH = ROOT / "release" / "index" / "workspace_lock.v1.toml"
DEPENDENCY_LOCK_PATH = ROOT / "release" / "index" / "dependency_lock.v1.toml"
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
    write_build_info(package_root, profile_id, profile, bundle)
    validate_package_root(package_root, profile, component_records)
    package_hash_manifest.write_manifests(package_root, component_records)
    if dist_root is not None:
        write_archive(package_root, dist_root, bundle)
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
                "runtime_role": str(component.get("runtime_role", "runtime_required")),
            }
        )
    return records


def copy_support_payloads(
    package_root: Path,
    profile: dict[str, Any],
    profile_path: Path,
    bundle_path: Path,
) -> None:
    copy_tree(ROOT / "docs" / "release", package_root / "docs" / "release")
    copy_tree(ROOT / "release" / "index", package_root / "release" / "index")
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
    lines = [
        'schema = "facman.built_package.v1"',
        f'profile_id = "{profile["id"]}"',
        f'lane = "{profile["lane"]}"',
        f'target_os = "{profile["target_os"]}"',
        f'target_arch = "{profile["target_arch"]}"',
        f'package_type = "{bundle.get("package_type", "")}"',
        f'entrypoint = "{bundle.get("entrypoint", "")}"',
        f'linkage_model = "{bundle.get("linkage_model", "unspecified")}"',
        f'release_profile = "{profile_path.relative_to(ROOT).as_posix()}"',
        f'package_manifest = "{bundle_path.relative_to(ROOT).as_posix()}"',
        'artifact_level = "built-artifact"',
        "signed = false",
        "published = false",
        "python_runtime = false",
        "bundles_factorio_binaries = false",
        "",
    ]
    (manifest / "package.v1.toml").write_text("\n".join(lines), encoding="utf-8")


def write_build_info(
    package_root: Path,
    profile_id: str,
    profile: dict[str, Any],
    bundle: dict[str, Any],
) -> None:
    build_index = load_toml(ROOT / "release" / "index" / "build_manifest.v1.toml")
    source_revisions = pinned_source_revisions()
    info = {
        "schema": "facman.package_build_info.v1",
        "profile_id": profile_id,
        "artifact_level": "built-artifact",
        "canonical_version": build_index.get("canonical_version", "facman-0.1.0+dev"),
        "filename_version": build_index.get("filename_version", "facman-0.1.0-dev"),
        "source_commit": git_commit(),
        "source_revisions": {
            "factorio_launcher": source_revisions["factorio_binding"],
            "universal_launcher": source_revisions["universal_launcher"],
            "universal_setup": source_revisions["universal_setup"],
        },
        "target_os": profile.get("target_os"),
        "target_arch": profile.get("target_arch"),
        "package_type": bundle.get("package_type"),
        "signed": False,
        "published": False,
    }
    (package_root / "manifest" / "build_info.v1.json").write_text(
        json.dumps(info, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


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
        roots = [build_root, build_root / "Debug"]
    for root in roots:
        for name in names:
            candidate = root / name
            if candidate.is_file():
                return candidate
    for name in names:
        matches = sorted(build_root.rglob(name))
        if matches:
            return matches[0]
    raise ValueError(f"missing built artifact for {source_target}; tried {', '.join(names)} under {build_root}")


def pinned_source_revisions() -> dict[str, str]:
    values = {
        "factorio_binding": git_commit(ROOT),
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


def write_archive(package_root: Path, dist_root: Path, bundle: dict[str, Any]) -> None:
    owned_output.ensure_owned_output_root(dist_root, "package-archives")
    build_index = load_toml(ROOT / "release" / "index" / "build_manifest.v1.toml")
    version = str(build_index.get("filename_version", "facman-0.1.0-dev"))
    artifact_template = str(bundle.get("artifact_id", package_root.name))
    version_prefix = artifact_template.split("<version>", 1)[0]
    replacement = version
    if version_prefix and version.lower().startswith(version_prefix.lower()):
        replacement = version[len(version_prefix):]
    artifact_id = artifact_template.replace("<version>", replacement)
    archive_base = dist_root / artifact_id
    if archive_base.with_suffix(".zip").exists():
        archive_base.with_suffix(".zip").unlink()
    shutil.make_archive(str(archive_base), "zip", root_dir=package_root)


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
    if profile_id == "windows_portable_cli_x64":
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


if __name__ == "__main__":
    raise SystemExit(main())
