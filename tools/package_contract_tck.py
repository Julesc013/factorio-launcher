#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Validate the unified FacMan product-stage contract and runtime resource pack."""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import package_layout_check, resource_pack  # noqa: E402
from tools.package import profile as package_profile  # noqa: E402
from tools.package.archive_inventory import zip_inventory  # noqa: E402
from tools.package.payload_equivalence import (  # noqa: E402,F401
    PAYLOAD_ADAPTERS,
    FileIdentity,
    PayloadAdapterContract,
    file_inventory,
    inventory_digest,
    payload_equivalence_receipt,
    safe_inventory_path,
    sha256_file,
)


PRODUCT_PROFILES = {
    "windows_product_x64": {
        "gui": "FacMan.exe",
        "terminal": "bin/facman.exe",
        "resources": "facman.resources",
    },
    "linux_product_x64": {
        "gui": "FacMan",
        "terminal": "facman",
        "resources": "share/facman/facman.resources",
    },
    "macos_product_x64": {
        "gui": "FacMan.app/Contents/MacOS/FacMan",
        "terminal": "FacMan.app/Contents/Helpers/facman",
        "resources": "FacMan.app/Contents/Resources/facman.resources",
    },
}
FORBIDDEN_PUBLIC_NAMES = {
    "facman-tui",
    "facman-tui.exe",
    "facmand",
    "facmand.exe",
    "facman-gui-gtk",
    "facman-gui-qt",
    "facman.winforms.exe",
}
FORBIDDEN_PRODUCT_ROOTS = {
    ".aide",
    ".github",
    "build",
    "contracts",
    "content",
    "evidence",
    "include",
    "tests",
    "tools",
}
SDK_MARKERS = {"cmake", "pkgconfig", "facman-flb.pc", "facmantargets.cmake"}
CANDIDATE_RECEIPT = "release/index/alpha5_final_candidate_closeout.v1.toml"
CANDIDATE_SOURCE_REVISION = "4683ecd9a1b9ead5eb84be152760d12583da0f0e"
CANDIDATE_SOURCE_TREE = "c07938618bc0f533fd12756cba123f54b8592048"
CANDIDATE_RUN = 33603385303
CANDIDATE_ATTEMPT = 1


def load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as stream:
        return tomllib.load(stream)


def artifact_identity(path: Path) -> dict[str, object]:
    if path.is_symlink():
        raise ValueError(f"equivalence artifact is linked: {path}")
    path = path.resolve(strict=True)
    if not path.is_file() or path.is_symlink() or path.stat().st_size == 0:
        raise ValueError(f"equivalence artifact is empty, missing, or linked: {path}")
    return {
        "filename": path.name,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def lifecycle_problems() -> list[str]:
    return package_profile.lifecycle_problems(ROOT)


def producer_model_problems() -> list[str]:
    policy = load_toml(ROOT / "release" / "index" / "package_producers.v1.toml")
    producers = {
        str(item.get("id", "")): item
        for item in policy.get("producer", [])
        if isinstance(item, dict)
    }
    problems: list[str] = []
    product = producers.get("platform_product_bundle", {})
    setup = producers.get("platform_self_setup", {})
    if product.get("producer_role") != "canonical_stage_owner":
        problems.append("platform_product_bundle must own the canonical stage")
    if product.get("payload_equivalence_required") is not True:
        problems.append("canonical product stages must require setup payload equivalence")
    expected_profiles = set(PRODUCT_PROFILES)
    if set(setup.get("consumes_profiles", [])) != expected_profiles:
        problems.append("platform_self_setup must consume exactly the current product profiles")
    if setup.get("producer_role") != "canonical_stage_adapter":
        problems.append("platform_self_setup must be a canonical-stage adapter")
    if setup.get("payload_equivalence_authority") != "exact_candidate_proof_recorded_non_authorizing":
        problems.append("platform_self_setup must bind the exact non-authorizing candidate proof")
    if setup.get("payload_equivalence_receipt") != CANDIDATE_RECEIPT:
        problems.append("platform_self_setup candidate proof must bind the closeout receipt")
    if not (ROOT / CANDIDATE_RECEIPT).is_file():
        problems.append("platform_self_setup candidate closeout receipt is missing")
    if setup.get("payload_equivalence_source_revision") != CANDIDATE_SOURCE_REVISION:
        problems.append("platform_self_setup candidate proof source revision differs")
    if setup.get("payload_equivalence_source_tree") != CANDIDATE_SOURCE_TREE:
        problems.append("platform_self_setup candidate proof source tree differs")
    if setup.get("payload_equivalence_candidate_run") != CANDIDATE_RUN:
        problems.append("platform_self_setup candidate proof run differs")
    if setup.get("payload_equivalence_candidate_attempt") != CANDIDATE_ATTEMPT:
        problems.append("platform_self_setup candidate proof attempt differs")
    if policy.get("release_authority") is not False:
        problems.append("package producer policy must remain non-authorizing")
    if setup.get("authority_ceiling") != "offline_operator_confirmed_app_install_only":
        problems.append("platform_self_setup authority ceiling changed")
    adapters = set(setup.get("payload_equivalence_adapters", []))
    if adapters != set(PAYLOAD_ADAPTERS):
        problems.append("platform_self_setup payload adapters differ from the TCK")
    maintenance = producers.get("maintenance_package", {})
    if maintenance.get("state") != "not_yet_admitted":
        problems.append("unassigned maintenance package must be not_yet_admitted")
    return problems


def profile_problems(profile_id: str) -> list[str]:
    expected = PRODUCT_PROFILES[profile_id]
    path = ROOT / "release" / "profiles" / profile_id / "profile.toml"
    profile = load_toml(path)
    required = profile.get("required_components", {})
    entrypoints = profile.get("entrypoints", {})
    problems: list[str] = []
    if not isinstance(required, dict) or required.get("resources") != expected["resources"]:
        problems.append(f"{profile_id}: required facman.resources path is not canonical")
    if isinstance(required, dict) and ({"contracts", "content"} & set(required)):
        problems.append(f"{profile_id}: loose contracts/content requirements are forbidden")
    if not isinstance(entrypoints, dict):
        problems.append(f"{profile_id}: entrypoints table is missing")
    else:
        if entrypoints.get("gui") != expected["gui"]:
            problems.append(f"{profile_id}: public GUI entrypoint must be {expected['gui']}")
        if entrypoints.get("cli") != expected["terminal"] or entrypoints.get("tui") != expected["terminal"]:
            problems.append(f"{profile_id}: CLI and TUI must share {expected['terminal']}")
    manifest_path = ROOT / str(profile.get("package_manifest", ""))
    bundle = package_layout_check.expand_bundle_manifest(manifest_path, load_toml(manifest_path), [])
    names = {str(item.get("name", "")) for item in bundle.get("components", [])}
    if "runtime_resources" not in names or {"contracts_schema", "factorio_content"} & names:
        problems.append(f"{profile_id}: product bundle must use only runtime_resources")
    if profile_id == "macos_product_x64":
        adapter = profile.get("terminal_adapter", {})
        if not isinstance(adapter, dict):
            problems.append(f"{profile_id}: terminal_adapter table is missing")
        else:
            expected_adapter = {
                "public_command": "facman",
                "portable_internal": expected["terminal"],
                "system_shim": "usr/local/bin/facman",
                "system_shim_target": "Applications/FacMan.app/Contents/Helpers/facman",
                "system_paths_relative_to": "installer_root",
                "case_collision_avoided": True,
            }
            for key, value in expected_adapter.items():
                if adapter.get(key) != value:
                    problems.append(f"{profile_id}: terminal adapter has invalid {key}")
    return problems


def stage_problems(stage: Path, profile_id: str) -> list[str]:
    expected = PRODUCT_PROFILES[profile_id]
    problems: list[str] = []
    stage = stage.resolve()
    if not stage.is_dir():
        return [f"{profile_id}: product stage does not exist: {stage}"]
    files = [path for path in stage.rglob("*") if path.is_file()]
    relative = [path.relative_to(stage).as_posix() for path in files]
    folded: dict[str, str] = {}
    for value in relative:
        key = value.casefold()
        if key in folded:
            problems.append(f"{profile_id}: case-fold collision: {folded[key]} and {value}")
        folded[key] = value
        leaf = Path(value).name.casefold()
        if leaf in FORBIDDEN_PUBLIC_NAMES:
            problems.append(f"{profile_id}: forbidden public executable: {value}")
        if any(part.casefold() in SDK_MARKERS for part in Path(value).parts):
            problems.append(f"{profile_id}: SDK payload is forbidden: {value}")
    top_levels = {path.name.casefold() for path in stage.iterdir()}
    for forbidden in sorted(FORBIDDEN_PRODUCT_ROOTS & top_levels):
        problems.append(f"{profile_id}: non-product root is forbidden: {forbidden}")
    for role in ("gui", "terminal", "resources"):
        if expected[role] not in relative:
            problems.append(f"{profile_id}: missing {role}: {expected[role]}")
    terminal_names = [
        value
        for value in relative
        if Path(value).name.casefold() in {"facman", "facman.exe"}
        and value != expected["gui"]
    ]
    if terminal_names != [expected["terminal"]]:
        problems.append(
            f"{profile_id}: product must expose exactly one terminal host, found {terminal_names}"
        )
    resource_path = stage / expected["resources"]
    if resource_path.is_file():
        try:
            resource_pack.verify(resource_path)
        except (OSError, ValueError) as exc:
            problems.append(f"{profile_id}: invalid facman.resources: {exc}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=sorted(PRODUCT_PROFILES))
    parser.add_argument("--stage", type=Path)
    parser.add_argument("--canonical-stage", type=Path)
    parser.add_argument("--payload-root", type=Path)
    parser.add_argument("--payload-zip", type=Path)
    parser.add_argument("--canonical-artifact", type=Path)
    parser.add_argument("--payload-artifact", type=Path)
    parser.add_argument("--adapter", choices=sorted(PAYLOAD_ADAPTERS))
    parser.add_argument("--version", default="")
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args(argv)
    problems: list[str] = []
    problems.extend(lifecycle_problems())
    problems.extend(producer_model_problems())
    selected = [args.profile] if args.profile else sorted(PRODUCT_PROFILES)
    for profile_id in selected:
        assert profile_id is not None
        problems.extend(profile_problems(profile_id))
        if args.stage is not None:
            problems.extend(stage_problems(args.stage, profile_id))
    equivalence_receipt: dict[str, Any] | None = None
    payload_sources = (args.payload_root, args.payload_zip)
    equivalence_arguments = (args.canonical_stage, *payload_sources, args.adapter)
    if any(value is not None for value in equivalence_arguments):
        if (
            args.canonical_stage is None
            or args.adapter is None
            or sum(value is not None for value in payload_sources) != 1
        ):
            problems.append(
                "payload equivalence requires --canonical-stage, --adapter, and exactly one of --payload-root or --payload-zip"
            )
        else:
            assert args.canonical_stage is not None
            assert args.adapter is not None
            adapter = PAYLOAD_ADAPTERS[args.adapter]
            if args.profile is not None and args.profile != adapter.profile_id:
                problems.append(
                    f"payload adapter {args.adapter} belongs to {adapter.profile_id}, not {args.profile}"
                )
            try:
                payload_inventory = (
                    file_inventory(args.payload_root)
                    if args.payload_root is not None
                    else zip_inventory(args.payload_zip)
                )
                equivalence_receipt = payload_equivalence_receipt(
                    file_inventory(args.canonical_stage),
                    payload_inventory,
                    adapter_id=args.adapter,
                    version=args.version,
                )
                problems.extend(str(item) for item in equivalence_receipt["problems"])
                artifacts = (args.canonical_artifact, args.payload_artifact)
                if any(value is not None for value in artifacts):
                    if not all(value is not None for value in artifacts):
                        problems.append(
                            "exact candidate receipts require both --canonical-artifact and --payload-artifact"
                        )
                    else:
                        assert args.canonical_artifact is not None
                        assert args.payload_artifact is not None
                        equivalence_receipt["canonical_artifact"] = artifact_identity(
                            args.canonical_artifact
                        )
                        equivalence_receipt["payload_artifact"] = artifact_identity(
                            args.payload_artifact
                        )
            except (OSError, ValueError) as exc:
                problems.append(str(exc))
    if any(
        value is not None for value in (args.canonical_artifact, args.payload_artifact)
    ) and equivalence_receipt is None:
        problems.append("artifact binding requires a successfully evaluated payload equivalence")
    if args.receipt is not None:
        if equivalence_receipt is None:
            problems.append("--receipt requires one successfully evaluated payload equivalence input")
        elif not problems:
            destination = args.receipt.resolve()
            if destination == ROOT or destination.is_relative_to(ROOT):
                problems.append("payload equivalence receipt must be outside the source checkout")
            elif destination.exists():
                problems.append(f"payload equivalence receipt already exists: {destination}")
            else:
                try:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination = destination.parent.resolve(strict=True) / destination.name
                    if destination == ROOT or destination.is_relative_to(ROOT):
                        raise ValueError(
                            "payload equivalence receipt parent resolves inside the source checkout"
                        )
                    with destination.open("x", encoding="utf-8", newline="\n") as stream:
                        stream.write(
                            json.dumps(equivalence_receipt, indent=2, sort_keys=True) + "\n"
                        )
                except (OSError, ValueError) as exc:
                    problems.append(f"payload equivalence receipt write failed: {exc}")
    if problems:
        for problem in problems:
            print(f"package-contract-tck: {problem}", file=sys.stderr)
        return 1
    print(f"package-contract-tck: ok ({', '.join(selected)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
