#!/usr/bin/env python3
"""Build and compare the exact FacMan alpha.2 Windows package set in fresh roots."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import alpha_qualification as common


VERSION = "0.1.0-alpha.2"
PORTABLE_SPECS = (
    {
        "id": "windows_cli_x64_portable",
        "profile": "windows_portable_cli_x64",
        "filename": f"facman-{VERSION}-windows-cli-x64-portable.zip",
        "build": "static",
    },
    {
        "id": "windows_tui_x64_portable",
        "profile": "windows_portable_tui_x64",
        "filename": f"facman-{VERSION}-windows-tui-x64-portable.zip",
        "build": "static",
    },
    {
        "id": "windows_winforms_x64_portable",
        "profile": "windows_legacy_winforms_x64",
        "filename": f"FacMan-{VERSION}-windows-x64-portable.zip",
        "build": "shared",
    },
)
SETUP_FIELDS = (
    "facman_source_revision",
    "source_dirty",
    "universal_setup_revision",
    "default_scope",
    "offline",
    "automatic_update",
    "factorio_mutation",
    "workspace_preserved",
    "payload",
    "setup_executable",
    "portable_input",
    "record_sha256",
)


def _clone_inputs(args: argparse.Namespace, root: Path, evidence: Path) -> tuple[Path, Path, Path]:
    facman = root / "facman"
    ulk = root / "universal-launcher"
    usk = root / "universal-setup"
    common.clone_exact(
        url=args.repository_url,
        destination=facman,
        revision=args.source_revision,
        branch=args.source_branch,
        log=evidence / "clone-facman.log",
    )
    common.clone_exact(
        url=args.ulk_url,
        destination=ulk,
        revision=args.ulk_revision,
        branch="main",
        log=evidence / "clone-ulk.log",
    )
    common.clone_exact(
        url=args.usk_url,
        destination=usk,
        revision=args.usk_revision,
        branch="main",
        log=evidence / "clone-usk.log",
    )
    return facman, ulk, usk


def _source_coherence(
    args: argparse.Namespace,
    *,
    facman: Path,
    ulk: Path,
    usk: Path,
    evidence: Path,
) -> None:
    checkout = evidence / "checkout"
    command = [
        args.python,
        str(facman / "tools/current_checkout_observation.py"),
        "--repository-root",
        str(facman),
        "--provider-root",
        f"universal_launcher={ulk}",
        "--provider-root",
        f"universal_setup={usk}",
        "--expected-source-sha",
        args.source_revision,
        "--line-ending-profile",
        "windows_checkout",
    ]
    if args.trust_passed_roots:
        command.append("--trust-passed-roots")
    command.extend(["--output-dir", str(checkout)])
    common.run(command, cwd=facman, log=evidence / "checkout-observation.log")
    coherence = evidence / "coherence"
    common.run(
        [
            args.python,
            str(facman / "tools/release_coherence_proof.py"),
            "--checkout-observation",
            str(checkout / "current-checkout-observation.v2.json"),
            "--workspace-lock",
            str(facman / "release/index/workspace_lock.v1.toml"),
            "--provider-lock",
            str(facman / "release/index/providers.lock.v2.toml"),
            "--source-observation",
            str(coherence / "release-source-observation.v1.json"),
            "--evidence",
            str(coherence / "release-coherence-proof.v1.json"),
        ],
        cwd=facman,
        log=evidence / "release-coherence.log",
    )


def _build_portables(
    args: argparse.Namespace,
    *,
    root: Path,
    facman: Path,
    evidence: Path,
    source_tree: str,
) -> list[dict[str, Any]]:
    packages: list[dict[str, Any]] = []
    for spec in PORTABLE_SPECS:
        build_root = f"{common.STABLE_ROOT}\\build-{spec['build']}"
        common.stable_command(
            args,
            root=root,
            facman=facman,
            evidence=evidence,
            name=f"package-{spec['profile']}",
            command=[
                args.python,
                f"{common.STABLE_ROOT}\\facman\\tools\\package_build.py",
                "--profile",
                str(spec["profile"]),
                "--out",
                f"{common.STABLE_ROOT}\\packages",
                "--build-root",
                build_root,
                "--dist",
                f"{common.STABLE_ROOT}\\dist",
                "--source-observation",
                f"{common.STABLE_ROOT}\\evidence\\coherence\\release-source-observation.v1.json",
            ],
        )
        common.stable_command(
            args,
            root=root,
            facman=facman,
            evidence=evidence,
            name=f"hash-verify-{spec['profile']}",
            command=[
                args.python,
                f"{common.STABLE_ROOT}\\facman\\tools\\package_hash_manifest.py",
                "--root",
                f"{common.STABLE_ROOT}\\packages\\{spec['profile']}",
                "--verify",
            ],
        )
        common.stable_command(
            args,
            root=root,
            facman=facman,
            evidence=evidence,
            name=f"runtime-smoke-{spec['profile']}",
            command=[
                args.python,
                f"{common.STABLE_ROOT}\\facman\\tools\\package_runtime_smoke.py",
                "--root",
                f"{common.STABLE_ROOT}\\packages\\{spec['profile']}",
            ],
        )
        packages.append(
            common.package_record(
                facman=facman,
                package_root=root / "packages" / str(spec["profile"]),
                dist=root / "dist",
                spec=spec,
                source_revision=args.source_revision,
                source_tree=source_tree,
            )
        )
    return packages


def _build_setup(
    args: argparse.Namespace,
    *,
    root: Path,
    facman: Path,
    evidence: Path,
) -> dict[str, Any]:
    common.stable_command(
        args,
        root=root,
        facman=facman,
        evidence=evidence,
        name="self-setup-package",
        command=[
            args.python,
            f"{common.STABLE_ROOT}\\facman\\tools\\self_setup_package.py",
            "--portable",
            f"{common.STABLE_ROOT}\\dist\\FacMan-{VERSION}-windows-x64-portable.zip",
            "--setup-exe",
            f"{common.STABLE_ROOT}\\build-static\\Release\\FacManSetup.exe",
            "--out",
            f"{common.STABLE_ROOT}\\self-setup-dist",
        ],
    )
    payload = root / "self-setup-dist" / f"facman-{VERSION}-windows-x64-self-setup-payload.zip"
    setup_exe = root / "self-setup-dist" / f"FacManSetup-{VERSION}-windows-x64.exe"
    record_path = root / "self-setup-dist" / f"facman-{VERSION}-self-setup-package.v1.json"
    common.stable_command(
        args,
        root=root,
        facman=facman,
        evidence=evidence,
        name="self-setup-packaged-lifecycle",
        command=[
            args.python,
            f"{common.STABLE_ROOT}\\facman\\tests\\integration\\facman_self_setup_lifecycle.py",
            "--setup-exe",
            f"{common.STABLE_ROOT}\\self-setup-dist\\{setup_exe.name}",
            "--payload",
            f"{common.STABLE_ROOT}\\self-setup-dist\\{payload.name}",
        ],
    )
    record = common.load_json(record_path)
    record["record_sha256"] = common.sha256(record_path)
    return record


def qualify_root(args: argparse.Namespace, root: Path, root_id: str) -> dict[str, Any]:
    evidence = root / "evidence"
    evidence.mkdir(parents=True)
    facman, ulk, usk = _clone_inputs(args, root, evidence)
    source_tree = common.git(facman, "rev-parse", f"{args.source_revision}^{{tree}}")
    _source_coherence(args, facman=facman, ulk=ulk, usk=usk, evidence=evidence)
    common.configure_and_build(
        args, root=root, facman=facman, evidence=evidence, name="static", linkage="static"
    )
    common.configure_and_build(
        args, root=root, facman=facman, evidence=evidence, name="shared", linkage="shared"
    )
    common.stable_command(
        args,
        root=root,
        facman=facman,
        evidence=evidence,
        name="winforms-release",
        command=[
            args.msbuild,
            f"{common.STABLE_ROOT}\\facman\\apps\\gui\\windows\\winforms\\FacMan.WinForms.csproj",
            "/t:Rebuild",
            "/p:Configuration=Release",
            "/p:Platform=x64",
            "/warnaserror",
        ],
    )
    packages = _build_portables(
        args, root=root, facman=facman, evidence=evidence, source_tree=source_tree
    )
    setup = _build_setup(args, root=root, facman=facman, evidence=evidence)
    record = {
        "schema": "facman.alpha2_root_qualification.v1",
        "root_id": root_id,
        "source_revision": args.source_revision,
        "source_tree": source_tree,
        "packages": packages,
        "self_setup": setup,
        "qualification": {
            "clean_fresh_checkout": "pass",
            "source_coherence": "pass",
            "native_static_debug_release": "pass",
            "native_shared_debug_release": "pass",
            "portable_package_runtime": "pass",
            "self_setup_packaged_lifecycle": "pass",
        },
        "authority": {
            "tagging": False,
            "signing": False,
            "public_publication": False,
            "support": False,
            "factorio_execution": False,
            "human_verdict": False,
        },
    }
    common.write_json(evidence / "root-qualification.v1.json", record)
    return record


def compare(records: list[dict[str, Any]], output: Path) -> dict[str, Any]:
    mismatches, table_lines = common.compare_records(records)
    baseline_setup = records[0]["self_setup"]
    for field in SETUP_FIELDS:
        table_lines.append(f"windows_x64_self_setup\t{field}\t{json.dumps(baseline_setup[field], sort_keys=True)}\n")
    for record in records[1:]:
        for field in SETUP_FIELDS:
            if record["self_setup"].get(field) != baseline_setup.get(field):
                mismatches.append(
                    {
                        "root": record["root_id"],
                        "package": "windows_x64_self_setup",
                        "field": field,
                        "expected": baseline_setup.get(field),
                        "observed": record["self_setup"].get(field),
                    }
                )
    table = "".join(table_lines)
    (output / "complete-package-identity-table.tsv").write_text(table, encoding="utf-8")
    baseline = records[0]
    result = {
        "schema": "facman.alpha2_three_root_qualification.v1",
        "status": "pass" if not mismatches else "fail",
        "version": VERSION,
        "source_revision": baseline["source_revision"],
        "source_tree": baseline["source_tree"],
        "root_count": len(records),
        "roots": [record["root_id"] for record in records],
        "packages": baseline["packages"],
        "self_setup": baseline_setup,
        "comparison_table_sha256": hashlib.sha256(table.encode("utf-8")).hexdigest(),
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "classification": {
            "platform": "Windows 10/11 x64",
            "support": "unsupported private alpha",
            "signed": False,
            "public": False,
            "distribution": "portable_and_supplied_payload_self_setup",
            "accepted_real_play_routes": 0,
        },
        "qualification": {
            "fresh_roots": "pass_in_every_root",
            "native_static_debug_release": "pass_in_every_root",
            "native_shared_debug_release": "pass_in_every_root",
            "portable_runtime": "pass_in_every_root",
            "self_setup_lifecycle": "pass_in_every_root",
            "byte_identical_archives_and_setup": "pass_in_every_root" if not mismatches else "fail",
        },
        "authority": {
            "tagging": False,
            "signing": False,
            "public_publication": False,
            "support": False,
            "factorio_execution": False,
            "human_verdict": False,
        },
    }
    common.write_json(output / "three-root-qualification.v1.json", result)
    if mismatches:
        raise RuntimeError(f"three-root comparison found {len(mismatches)} mismatches")
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


def parser() -> argparse.ArgumentParser:
    value = common.parser()
    value.description = __doc__
    value.set_defaults(source_branch="dev")
    value.add_argument("--source-branch", choices=("dev", "main"), default="dev")
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if os.name != "nt":
        raise RuntimeError("alpha.2 qualification requires Windows")
    if re.fullmatch(r"[0-9a-f]{40}", args.source_revision) is None:
        raise RuntimeError("source revision must be exact lowercase 40-hex")
    output = args.output_root.resolve()
    if output.exists():
        raise RuntimeError("output root must be new")
    output.mkdir(parents=True)
    records = []
    for index in range(1, args.root_count + 1):
        root = output / f"root{index}"
        root.mkdir()
        records.append(qualify_root(args, root, f"root{index}"))
    if args.root_count == 3:
        compare(records, output)
    else:
        print(json.dumps(records[0], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
