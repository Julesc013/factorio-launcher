# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Build and compare all exact FacMan alpha.1 Windows packages in fresh roots."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import json_contract

STABLE_ROOT = "@FACMAN_STABLE_ROOT@"
COMPARISON_SCHEMA = (
    ROOT
    / "contracts/schema/release/alpha1_final_dev_three_root_qualification.v1.schema.json"
)
CONTRACT_SET_DEFINE = re.compile(
    r'^#define FACMAN_CONTRACT_SET_SHA256 "([0-9a-f]{64})"$', re.MULTILINE
)
PACKAGE_SPECS = (
    {
        "id": "windows_cli_x64_portable",
        "profile": "windows_portable_cli_x64",
        "filename": "facman-0.1.0-alpha.1-windows-cli-x64-portable.zip",
        "build": "static",
    },
    {
        "id": "windows_tui_x64_portable",
        "profile": "windows_portable_tui_x64",
        "filename": "facman-0.1.0-alpha.1-windows-tui-x64-portable.zip",
        "build": "static",
    },
    {
        "id": "windows_winforms_x64_portable",
        "profile": "windows_legacy_winforms_x64",
        "filename": "FacMan-0.1.0-alpha.1-windows-x64-portable.zip",
        "build": "shared",
    },
)
COMPARISON_FIELDS = (
    "source_revision",
    "source_tree",
    "contract_set_sha256",
    "state_identity",
    "package_tree_sha256",
    "archive_sha256",
    "embedded_manifest_sha256",
    "sbom_sha256",
    "provenance_sha256",
    "licence_inventory_sha256",
    "file_count",
    "uncompressed_bytes",
    "archive_bytes",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"{path} must contain a JSON object")
    return value


def load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as stream:
        value = tomllib.load(stream)
    if not isinstance(value, dict):
        raise RuntimeError(f"{path} must contain a TOML table")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run(command: list[str], *, cwd: Path, log: Path) -> None:
    print(f"[{cwd.name}] {' '.join(command[:5])}", flush=True)
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w", encoding="utf-8") as stream:
        completed = subprocess.run(
            command,
            cwd=cwd,
            stdout=stream,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
    if completed.returncode:
        lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
        log_tail = "\n".join(lines[-40:])
        raise RuntimeError(
            f"command failed ({completed.returncode}); inspect {log}: "
            f"{' '.join(command)}"
            + (f"\n--- log tail ---\n{log_tail}" if log_tail else "")
        )


def capture(command: list[str], *, cwd: Path, output: Path) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(completed.stdout, encoding="utf-8")
    return completed


def git(repository: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=repository,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError(completed.stderr.strip() or f"git {' '.join(arguments)} failed")
    return completed.stdout.strip()


def clone_exact(*, url: str, destination: Path, revision: str, branch: str, log: Path) -> None:
    run(
        [
            "git",
            "clone",
            "--no-local",
            "--no-hardlinks",
            "--no-checkout",
            "-c",
            "core.longpaths=true",
            url,
            str(destination),
        ],
        cwd=destination.parent,
        log=log,
    )
    run(
        ["git", "fetch", "--no-tags", "origin", f"{branch}:refs/remotes/origin/{branch}"],
        cwd=destination,
        log=log.with_name(f"{log.stem}-fetch.log"),
    )
    run(
        ["git", "checkout", "--detach", revision],
        cwd=destination,
        log=log.with_name(f"{log.stem}-checkout.log"),
    )
    if git(destination, "rev-parse", "HEAD") != revision:
        raise RuntimeError(f"checkout mismatch for {destination.name}")
    if git(destination, "status", "--porcelain"):
        raise RuntimeError(f"fresh checkout is dirty: {destination}")


def stable(
    *,
    python: str,
    facman: Path,
    physical_root: Path,
    command: list[str],
    receipt: Path,
    log: Path,
) -> None:
    run(
        [
            python,
            str(facman / "tools/windows_stable_build_root.py"),
            "--physical-root",
            str(physical_root),
            "--drive",
            "Q",
            "--working-directory",
            ".",
            "--report",
            str(receipt),
            "--",
            *command,
        ],
        cwd=facman,
        log=log,
    )
    record = load_json(receipt)
    if record.get("status") != "pass" or record.get("mapping_removed") is not True:
        raise RuntimeError(f"stable-root receipt is not passing: {receipt}")


def stable_command(
    args: argparse.Namespace,
    *,
    root: Path,
    facman: Path,
    evidence: Path,
    name: str,
    command: list[str],
) -> None:
    stable(
        python=args.python,
        facman=facman,
        physical_root=root,
        command=command,
        receipt=evidence / f"stable-{name}.v1.json",
        log=evidence / f"{name}.log",
    )


def provider_identities(facman: Path) -> list[dict[str, Any]]:
    provider_lock = load_toml(facman / "release/index/providers.lock.v2.toml")
    records = []
    for item in provider_lock.get("provider", []):
        if not isinstance(item, dict):
            continue
        records.append(
            {
                "id": str(item["id"]),
                "source_revision": str(item["source_revision"]),
                "source_tree": str(item["source_tree"]),
                "package_version": str(item["package_version"]),
                "package_identity": (
                    f"{item['package_identity_kind']}:{item['package_digest']}"
                ),
                "abi_version": str(item["abi_version"]),
                "abi_manifest_sha256": str(item["abi_manifest_digest"]),
                "contract_set_id": str(item["contract_set_id"]),
                "contract_digest": str(item["contract_digest"]),
            }
        )
    records.sort(key=lambda item: item["id"])
    if [item["id"] for item in records] != ["universal_launcher", "universal_setup"]:
        raise RuntimeError("provider lock must contain exactly Universal Launcher and Setup")
    return records


def contract_set_sha256(facman: Path) -> str:
    text = (facman / "runtime/core/generated/version.h").read_text(encoding="utf-8")
    match = CONTRACT_SET_DEFINE.search(text)
    if match is None:
        raise RuntimeError("generated version header omits the contract-set digest")
    return match.group(1)


def licence_inventory(package_root: Path, output: Path, profile: str) -> dict[str, Any]:
    license_root = package_root / "licenses"
    entries = [
        {
            "path": path.relative_to(package_root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        for path in sorted(item for item in license_root.rglob("*") if item.is_file())
    ]
    if not entries:
        raise RuntimeError(f"{profile}: package contains no licence inventory")
    record = {
        "schema": "facman.alpha_package_licence_inventory.v1",
        "profile": profile,
        "entries": entries,
        "authority": {"signing": False, "publication": False, "support": False},
    }
    write_json(output, record)
    return record


def package_record(
    *,
    facman: Path,
    package_root: Path,
    dist: Path,
    spec: dict[str, str],
    source_revision: str,
    source_tree: str,
) -> dict[str, Any]:
    archive = dist / spec["filename"]
    provenance = dist / f"{spec['filename']}.provenance.v1.json"
    embedded_manifest = package_root / "manifest/package.v1.toml"
    sbom = package_root / "manifest/sbom.spdx.v2.3.json"
    package_tree = package_root / "manifest/hashes.sha256"
    licence = dist / f"{spec['filename']}.licence-inventory.v1.json"
    for path in (archive, provenance, embedded_manifest, sbom, package_tree):
        if not path.is_file():
            raise RuntimeError(f"{spec['profile']}: required package evidence is absent: {path}")
    licence_inventory(package_root, licence, spec["profile"])
    files = [path for path in package_root.rglob("*") if path.is_file()]
    return {
        "id": spec["id"],
        "profile": spec["profile"],
        "filename": spec["filename"],
        "source_revision": source_revision,
        "source_tree": source_tree,
        "providers": provider_identities(facman),
        "contract_set_sha256": contract_set_sha256(facman),
        "state_identity": "facman.workspace.v1",
        "package_tree_sha256": sha256(package_tree),
        "archive_sha256": sha256(archive),
        "embedded_manifest_sha256": sha256(embedded_manifest),
        "sbom_sha256": sha256(sbom),
        "provenance_sha256": sha256(provenance),
        "licence_inventory_sha256": sha256(licence),
        "file_count": len(files),
        "uncompressed_bytes": sum(path.stat().st_size for path in files),
        "archive_bytes": archive.stat().st_size,
    }


def configure_and_build(
    args: argparse.Namespace,
    *,
    root: Path,
    facman: Path,
    evidence: Path,
    name: str,
    linkage: str,
) -> None:
    build = f"{STABLE_ROOT}\\build-{name}"
    stable_command(
        args,
        root=root,
        facman=facman,
        evidence=evidence,
        name=f"configure-{name}",
        command=[
            "cmake",
            "-S",
            f"{STABLE_ROOT}\\facman",
            "-B",
            build,
            "-G",
            args.cmake_generator,
            "-A",
            "x64",
            "-DFACMAN_BUILD_CLI=ON",
            "-DFACMAN_BUILD_TUI=ON",
            "-DFACMAN_PROVIDER_MODE=source",
            f"-DFACMAN_PROVIDER_SOURCE_LINKAGE={linkage}",
            "-DFACMAN_WARNINGS_AS_ERRORS=ON",
            f"-DFLAUNCH_UNIVERSAL_LAUNCHER_ROOT={STABLE_ROOT}\\universal-launcher",
            f"-DFLAUNCH_UNIVERSAL_SETUP_ROOT={STABLE_ROOT}\\universal-setup",
        ],
    )
    for configuration in ("Debug", "Release"):
        stable_command(
            args,
            root=root,
            facman=facman,
            evidence=evidence,
            name=f"build-{name}-{configuration.lower()}",
            command=["cmake", "--build", build, "--config", configuration, "--parallel"],
        )
        stable_command(
            args,
            root=root,
            facman=facman,
            evidence=evidence,
            name=f"ctest-{name}-{configuration.lower()}",
            command=[
                "ctest",
                "--test-dir",
                build,
                "-C",
                configuration,
                "--output-on-failure",
            ],
        )


def qualify_root(args: argparse.Namespace, root: Path, root_id: str) -> dict[str, Any]:
    evidence = root / "evidence"
    evidence.mkdir(parents=True)
    facman = root / "facman"
    ulk = root / "universal-launcher"
    usk = root / "universal-setup"
    clone_exact(
        url=args.repository_url,
        destination=facman,
        revision=args.source_revision,
        branch="dev",
        log=evidence / "clone-facman.log",
    )
    clone_exact(
        url=args.ulk_url,
        destination=ulk,
        revision=args.ulk_revision,
        branch="main",
        log=evidence / "clone-ulk.log",
    )
    clone_exact(
        url=args.usk_url,
        destination=usk,
        revision=args.usk_revision,
        branch="main",
        log=evidence / "clone-usk.log",
    )
    source_tree = git(facman, "rev-parse", f"{args.source_revision}^{{tree}}")

    checkout = evidence / "checkout"
    checkout_command = [
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
        checkout_command.append("--trust-passed-roots")
    checkout_command.extend(["--output-dir", str(checkout)])
    run(checkout_command, cwd=facman, log=evidence / "checkout-observation.log")

    coherence = evidence / "coherence"
    run(
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

    configure_and_build(
        args, root=root, facman=facman, evidence=evidence, name="static", linkage="static"
    )
    configure_and_build(
        args, root=root, facman=facman, evidence=evidence, name="shared", linkage="shared"
    )
    stable_command(
        args,
        root=root,
        facman=facman,
        evidence=evidence,
        name="winforms-release",
        command=[
            args.msbuild,
            f"{STABLE_ROOT}\\facman\\apps\\gui\\windows\\winforms\\FacMan.WinForms.csproj",
            "/t:Rebuild",
            "/p:Configuration=Release",
            "/p:Platform=x64",
            "/warnaserror",
        ],
    )

    packages: list[dict[str, Any]] = []
    for spec in PACKAGE_SPECS:
        build_root = f"{STABLE_ROOT}\\build-{spec['build']}"
        package_root = root / "packages" / spec["profile"]
        stable_command(
            args,
            root=root,
            facman=facman,
            evidence=evidence,
            name=f"package-{spec['profile']}",
            command=[
                args.python,
                f"{STABLE_ROOT}\\facman\\tools\\package_build.py",
                "--profile",
                spec["profile"],
                "--out",
                f"{STABLE_ROOT}\\packages",
                "--build-root",
                build_root,
                "--dist",
                f"{STABLE_ROOT}\\dist",
                "--source-observation",
                f"{STABLE_ROOT}\\evidence\\coherence\\release-source-observation.v1.json",
            ],
        )
        stable_command(
            args,
            root=root,
            facman=facman,
            evidence=evidence,
            name=f"hash-verify-{spec['profile']}",
            command=[
                args.python,
                f"{STABLE_ROOT}\\facman\\tools\\package_hash_manifest.py",
                "--root",
                f"{STABLE_ROOT}\\packages\\{spec['profile']}",
                "--verify",
            ],
        )
        stable_command(
            args,
            root=root,
            facman=facman,
            evidence=evidence,
            name=f"runtime-smoke-{spec['profile']}",
            command=[
                args.python,
                f"{STABLE_ROOT}\\facman\\tools\\package_runtime_smoke.py",
                "--root",
                f"{STABLE_ROOT}\\packages\\{spec['profile']}",
            ],
        )
        drift = root / "drift" / spec["profile"]
        shutil.copytree(package_root, drift)
        drift_marker = drift / "manifest/package.v1.toml"
        drift_marker.write_bytes(drift_marker.read_bytes() + b"\n# qualification drift\n")
        drift_result = capture(
            [
                args.python,
                str(facman / "tools/package_hash_manifest.py"),
                "--root",
                str(drift),
                "--verify",
            ],
            cwd=facman,
            output=evidence / f"drift-refusal-{spec['profile']}.log",
        )
        if drift_result.returncode == 0:
            raise RuntimeError(f"{root_id}/{spec['profile']}: drift verification unexpectedly passed")
        packages.append(
            package_record(
                facman=facman,
                package_root=package_root,
                dist=root / "dist",
                spec=spec,
                source_revision=args.source_revision,
                source_tree=source_tree,
            )
        )

    record = {
        "schema": "facman.alpha1_final_dev_root_qualification.v1",
        "root_id": root_id,
        "source_revision": args.source_revision,
        "source_tree": source_tree,
        "packages": packages,
        "qualification": {
            "clean_fresh_checkout": "pass",
            "source_coherence": "pass",
            "native_static_debug_release": "pass",
            "native_shared_debug_release": "pass",
            "package_runtime": "pass",
            "hash_manifest": "pass",
            "drift_refusal": "pass",
        },
        "authority": {
            "tagging": False,
            "signing": False,
            "publication": False,
            "support": False,
            "setup_mutation": False,
            "factorio_execution": False,
            "human_verdict": False,
        },
    }
    write_json(evidence / "root-qualification.v1.json", record)
    return record


def compare_records(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    baseline = {item["id"]: item for item in records[0]["packages"]}
    mismatches: list[dict[str, Any]] = []
    table_lines: list[str] = []
    for package_id, package in sorted(baseline.items()):
        for field in COMPARISON_FIELDS:
            table_lines.append(f"{package_id}\t{field}\t{package[field]}\n")
    for record in records[1:]:
        observed = {item["id"]: item for item in record["packages"]}
        for package_id in sorted(set(baseline) | set(observed)):
            if package_id not in baseline or package_id not in observed:
                mismatches.append(
                    {"root": record["root_id"], "package": package_id, "field": "presence"}
                )
                continue
            for field in COMPARISON_FIELDS:
                if observed[package_id].get(field) != baseline[package_id].get(field):
                    mismatches.append(
                        {
                            "root": record["root_id"],
                            "package": package_id,
                            "field": field,
                            "expected": baseline[package_id].get(field),
                            "observed": observed[package_id].get(field),
                        }
                    )
            if observed[package_id].get("providers") != baseline[package_id].get("providers"):
                mismatches.append(
                    {
                        "root": record["root_id"],
                        "package": package_id,
                        "field": "providers",
                    }
                )
    return mismatches, table_lines


def compare(records: list[dict[str, Any]], output: Path) -> dict[str, Any]:
    mismatches, table_lines = compare_records(records)
    table = "".join(table_lines)
    (output / "complete-package-identity-table.tsv").write_text(table, encoding="utf-8")
    baseline = records[0]
    result = {
        "schema": "facman.alpha1_final_dev_three_root_qualification.v1",
        "status": "pass" if not mismatches else "fail",
        "source_revision": baseline["source_revision"],
        "source_tree": baseline["source_tree"],
        "root_count": len(records),
        "roots": [record["root_id"] for record in records],
        "packages": baseline["packages"],
        "comparison_table_sha256": hashlib.sha256(table.encode("utf-8")).hexdigest(),
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "classification": {
            "platform": "Windows 10/11 x64",
            "support": "unsupported alpha",
            "signed": False,
            "published": False,
            "distribution": "portable",
            "accepted_real_play_routes": 0,
        },
        "qualification": {
            "fresh_roots": "pass_in_every_root",
            "native_static_debug_release": "pass_in_every_root",
            "native_shared_debug_release": "pass_in_every_root",
            "package_runtime": "pass_in_every_root",
            "hash_manifest": "pass_in_every_root",
            "drift_refusal": "pass_in_every_root",
            "byte_identical_archives": "pass_in_every_root" if not mismatches else "fail",
        },
        "authority": {
            "tagging": False,
            "signing": False,
            "publication": False,
            "support": False,
            "setup_mutation": False,
            "factorio_execution": False,
            "human_verdict": False,
        },
    }
    problems = json_contract.validate(result, json_contract.load_schema(COMPARISON_SCHEMA))
    if problems:
        raise RuntimeError("three-root qualification schema rejection: " + "; ".join(problems))
    write_json(output / "three-root-qualification.v1.json", result)
    if mismatches:
        raise RuntimeError(f"three-root comparison found {len(mismatches)} mismatches")
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--source-revision", required=True)
    value.add_argument("--output-root", type=Path, required=True)
    value.add_argument("--python", required=True)
    value.add_argument("--msbuild", required=True)
    value.add_argument("--cmake-generator", default="Visual Studio 17 2022")
    value.add_argument("--root-count", type=int, choices=(1, 3), default=3)
    value.add_argument("--trust-passed-roots", action="store_true")
    value.add_argument(
        "--repository-url", default="https://github.com/Julesc013/factorio-launcher.git"
    )
    value.add_argument(
        "--ulk-url", default="https://github.com/Julesc013/universal-launcher.git"
    )
    value.add_argument(
        "--usk-url", default="https://github.com/Julesc013/universal-setup.git"
    )
    value.add_argument(
        "--ulk-revision", default="5479939ca5cbc9ee0f901608a92012778b4752ae"
    )
    value.add_argument(
        "--usk-revision", default="d2a2aae7e61c47035c92334b0522143b4fea3880"
    )
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if os.name != "nt":
        raise RuntimeError("alpha.1 final-dev qualification requires Windows")
    if re.fullmatch(r"[0-9a-f]{40}", args.source_revision) is None:
        raise RuntimeError("source revision must be exact lowercase 40-hex")
    output = args.output_root.resolve()
    if output.exists():
        raise RuntimeError("output root must be new")
    output.mkdir(parents=True)
    records: list[dict[str, Any]] = []
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
