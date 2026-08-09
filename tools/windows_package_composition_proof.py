# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import package_hash_manifest  # noqa: E402
from tools.package import pipeline  # noqa: E402


STATIC_PROFILES = (
    "windows_portable_cli_x64",
    "windows_portable_tui_x64",
)
SHARED_PROFILE = "windows_legacy_winforms_x64"
LOCK_PATHS = {
    "workspace_lock": ROOT / "release" / "index" / "workspace_lock.v1.toml",
    "provider_lock": ROOT / "release" / "index" / "providers.lock.v2.toml",
    "route_v1": ROOT / "release" / "index" / "successor_play_route.v1.toml",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Prove the exact static/shared Windows package composition."
    )
    parser.add_argument("--static-build-root", required=True)
    parser.add_argument("--shared-build-root", required=True)
    parser.add_argument("--static-package-root", required=True)
    parser.add_argument("--tui-package-root", required=True)
    parser.add_argument("--shared-package-root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        report = prove(
            Path(args.static_build_root).resolve(),
            Path(args.shared_build_root).resolve(),
            {
                STATIC_PROFILES[0]: Path(args.static_package_root).resolve(),
                STATIC_PROFILES[1]: Path(args.tui_package_root).resolve(),
                SHARED_PROFILE: Path(args.shared_package_root).resolve(),
            },
        )
        output = Path(args.output).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    except (OSError, ValueError) as exc:
        print(f"windows-package-composition-proof: {exc}", file=sys.stderr)
        return 1
    summary = {
        "status": report["status"],
        "build_roots": report["build_roots"],
        "packages": {
            profile_id: {
                "file_count": evidence["file_count"],
                "tree_sha256": evidence["tree_sha256"],
            }
            for profile_id, evidence in report["packages"].items()
        },
        "governing_digests": report["governing_digests"],
        "authority": report["authority"],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    print("windows-package-composition-proof: ok")
    return 0


def prove(
    static_build_root: Path,
    shared_build_root: Path,
    package_roots: dict[str, Path],
) -> dict[str, Any]:
    pipeline.validate_distinct_build_roots(static_build_root, shared_build_root)
    revisions = pipeline.pinned_source_revisions()
    source_dirty = pipeline.git_dirty()
    static_identity, static_values = pipeline.cmake_build_identity_values(
        static_build_root, revisions, source_dirty
    )
    shared_identity, shared_values = pipeline.cmake_build_identity_values(
        shared_build_root, revisions, source_dirty
    )
    for key in static_values:
        if key == "provider_source_linkage":
            continue
        if static_values[key] != shared_values[key]:
            raise ValueError(
                "static/shared exact build identities differ outside provider linkage: "
                f"{key}"
            )
    if static_values["provider_source_linkage"] != "static":
        raise ValueError("static root exact build identity is not static")
    if shared_values["provider_source_linkage"] != "shared":
        raise ValueError("shared root exact build identity is not shared")
    compare_toolchain_cache(static_build_root, shared_build_root)

    packages = {}
    for profile_id, package_root in package_roots.items():
        build_root = (
            shared_build_root if profile_id == SHARED_PROFILE else static_build_root
        )
        _profile_path, profile = pipeline.load_profile(profile_id)
        bundle_path = ROOT / str(profile["package_manifest"])
        bundle = pipeline.load_toml(bundle_path)
        pipeline.validate_build_composition(profile_id, profile, bundle, build_root)
        evidence = package_evidence(profile_id, package_root, profile)
        expected_identity = shared_identity if profile_id == SHARED_PROFILE else static_identity
        if evidence["build_identity_sha256"] != sha256_bytes(
            expected_identity.encode("utf-8")
        ):
            raise ValueError(
                f"{profile_id}: package and selected build-root identities differ"
            )
        packages[profile_id] = evidence

    for profile_id in STATIC_PROFILES:
        leaked = sorted(
            path.relative_to(package_roots[profile_id]).as_posix()
            for path in package_roots[profile_id].rglob("*")
            if path.is_file()
            and path.name.lower() in pipeline.SHARED_RUNTIME_FILENAMES
        )
        if leaked:
            raise ValueError(
                f"{profile_id}: static package contains shared runtimes: "
                + ", ".join(leaked)
            )
    shared_names = {
        path.name.lower()
        for path in package_roots[SHARED_PROFILE].rglob("*")
        if path.is_file()
    }
    missing_shared = sorted(pipeline.SHARED_RUNTIME_FILENAMES - shared_names)
    if missing_shared:
        raise ValueError(
            "WinForms shared package omits runtime files: "
            + ", ".join(missing_shared)
        )
    validate_package_schema_inventory(package_roots[SHARED_PROFILE])

    return {
        "schema": "facman.windows_package_composition_proof.v1",
        "status": "pass",
        "source_revisions": revisions,
        "build_roots": {
            "static": {
                "root_name": static_build_root.name,
                "provider_source_linkage": "static",
                "build_identity_sha256": sha256_bytes(static_identity.encode("utf-8")),
            },
            "shared": {
                "root_name": shared_build_root.name,
                "provider_source_linkage": "shared",
                "build_identity_sha256": sha256_bytes(shared_identity.encode("utf-8")),
            },
            "identical_except_provider_source_linkage": True,
        },
        "packages": packages,
        "governing_digests": {
            name: sha256_file(path) for name, path in LOCK_PATHS.items()
        },
        "authority": {
            "merge": False,
            "main_promotion": False,
            "provider_identity_change": False,
            "route_change": False,
            "factorio_execution": False,
            "setup_mutation": False,
            "permit_issue": False,
            "signing": False,
            "publication": False,
        },
    }


def compare_toolchain_cache(static_root: Path, shared_root: Path) -> None:
    static = pipeline.cmake_cache_values(static_root / "CMakeCache.txt")
    shared = pipeline.cmake_cache_values(shared_root / "CMakeCache.txt")
    for key in (
        "CMAKE_GENERATOR",
        "CMAKE_GENERATOR_PLATFORM",
        "CMAKE_CXX_COMPILER",
        "CMAKE_VS_PLATFORM_NAME",
        "FACMAN_BUILD_CLI",
        "FACMAN_BUILD_TUI",
    ):
        if static.get(key) != shared.get(key):
            raise ValueError(f"static/shared toolchain or target identity differs: {key}")


def package_evidence(
    profile_id: str, package_root: Path, profile: dict[str, Any]
) -> dict[str, Any]:
    if not package_root.is_dir():
        raise ValueError(f"{profile_id}: package root is missing: {package_root}")
    problems = package_hash_manifest.verify_manifest(package_root)
    if problems:
        raise ValueError(f"{profile_id}: package hash closure failed: {'; '.join(problems)}")
    for relative in pipeline.required_paths(profile):
        if not (package_root / pipeline.normalize_destination(relative)).exists():
            raise ValueError(f"{profile_id}: missing required package path {relative}")
    build_info_path = package_root / "manifest" / "build_info.v1.json"
    build_info = json.loads(build_info_path.read_text(encoding="utf-8"))
    if build_info.get("profile_id") != profile_id:
        raise ValueError(f"{profile_id}: build info has the wrong profile identity")
    snapshot = {
        path.relative_to(package_root).as_posix(): sha256_file(path)
        for path in sorted(
            package_root.rglob("*"),
            key=lambda item: item.relative_to(package_root).as_posix(),
        )
        if path.is_file()
    }
    return {
        "file_count": len(snapshot),
        "tree_sha256": sha256_bytes(
            json.dumps(snapshot, separators=(",", ":"), sort_keys=True).encode("utf-8")
        ),
        "inventory": sorted(snapshot),
        "build_identity_sha256": sha256_bytes(
            str(build_info["build_identity"]).encode("utf-8")
        ),
        "hash_manifest": "pass",
    }


def validate_package_schema_inventory(package_root: Path) -> None:
    expected_root = ROOT / "contracts" / "schema"
    actual_root = package_root / "contracts" / "schema"
    if not actual_root.is_dir():
        raise ValueError("WinForms package is missing contracts/schema")
    expected = {
        path.relative_to(expected_root).as_posix()
        for path in expected_root.rglob("*")
        if path.is_file()
    }
    actual = {
        path.relative_to(actual_root).as_posix()
        for path in actual_root.rglob("*")
        if path.is_file()
    }
    if actual != expected:
        raise ValueError("WinForms contracts/schema inventory is not exact")


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
