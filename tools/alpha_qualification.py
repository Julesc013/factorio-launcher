# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Build and compare the exact FacMan alpha candidate in fresh Windows roots."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

TARGET = "windows_winforms_technical_preview_x64"
ARTIFACT = "windows_winforms_technical_preview_zip"
STABLE_ROOT = "@FACMAN_STABLE_ROOT@"


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


def run(command: list[str], *, cwd: Path, log: Path) -> None:
    print(f"[{cwd.name}] {' '.join(command[:4])}", flush=True)
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
        raise RuntimeError(
            f"command failed ({completed.returncode}); inspect {log}: "
            f"{' '.join(command)}"
        )


def capture(
    command: list[str], *, cwd: Path, output: Path
) -> subprocess.CompletedProcess[str]:
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


def clone_exact(
    *, url: str, destination: Path, revision: str, branch: str, log: Path
) -> None:
    run(
        [
            "git",
            "clone",
            "--no-local",
            "--no-hardlinks",
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
    observed = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=destination, text=True
    ).strip()
    if observed != revision:
        raise RuntimeError(f"checkout mismatch for {destination.name}: {observed}")
    dirty = subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=destination, text=True
    ).strip()
    if dirty:
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


def exactly_one(paths: list[Path], label: str) -> Path:
    if len(paths) != 1:
        raise RuntimeError(f"expected one {label}, found {len(paths)}")
    return paths[0]


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
    run(
        checkout_command,
        cwd=facman,
        log=evidence / "checkout-observation.log",
    )

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

    build = root / "build"
    stable(
        python=args.python,
        facman=facman,
        physical_root=root,
        command=[
            "cmake",
            "-S",
            f"{STABLE_ROOT}\\facman",
            "-B",
            f"{STABLE_ROOT}\\build",
            "-G",
            args.cmake_generator,
            "-A",
            "x64",
            "-DFACMAN_BUILD_CLI=ON",
            "-DFACMAN_BUILD_TUI=ON",
            "-DFACMAN_PROVIDER_MODE=source",
            "-DFACMAN_PROVIDER_SOURCE_LINKAGE=static",
            "-DFACMAN_WARNINGS_AS_ERRORS=ON",
            f"-DFLAUNCH_UNIVERSAL_LAUNCHER_ROOT={STABLE_ROOT}\\universal-launcher",
            f"-DFLAUNCH_UNIVERSAL_SETUP_ROOT={STABLE_ROOT}\\universal-setup",
        ],
        receipt=evidence / "stable-configure.v1.json",
        log=evidence / "configure.log",
    )
    stable(
        python=args.python,
        facman=facman,
        physical_root=root,
        command=[
            "cmake",
            "--build",
            f"{STABLE_ROOT}\\build",
            "--config",
            "Release",
            "--parallel",
            "--target",
            "facman_cli",
        ],
        receipt=evidence / "stable-cli-build.v1.json",
        log=evidence / "cli-build.log",
    )
    stable(
        python=args.python,
        facman=facman,
        physical_root=root,
        command=[
            args.msbuild,
            f"{STABLE_ROOT}\\facman\\apps\\gui\\windows\\winforms\\FacMan.WinForms.csproj",
            "/t:Rebuild",
            "/p:Configuration=Release",
            "/p:Platform=x64",
            "/warnaserror",
        ],
        receipt=evidence / "stable-winforms-build.v1.json",
        log=evidence / "winforms-build.log",
    )

    cli = build / "Release/facman.exe"
    winforms = facman / "apps/gui/windows/winforms/bin/Release/FacMan.WinForms.exe"
    if not cli.is_file() or not winforms.is_file():
        raise RuntimeError(f"expected Release binaries are absent in {root_id}")

    resolution = root / "resolution"
    source_observation = coherence / "release-source-observation.v1.json"
    release = [args.python, str(facman / "tools/facman_release.py")]
    run(
        [
            *release,
            "--input-root",
            str(facman / "release/index"),
            "--source-observation",
            str(source_observation),
            "resolve",
            "--target",
            TARGET,
            "--output",
            str(resolution),
        ],
        cwd=facman,
        log=evidence / "resolve.log",
    )
    plan = load_json(resolution / "resolved-package-plan.v1.json")
    artifact_record = next(
        item for item in plan["artifacts"] if item.get("id") == ARTIFACT
    )
    archive_name = str(artifact_record["filename"])

    stage = root / "stage"
    run(
        [
            *release,
            "stage",
            "--resolution",
            str(resolution),
            "--artifact",
            ARTIFACT,
            "--source-root",
            str(facman),
            "--source",
            f"facman_cli={cli}",
            "--source",
            f"facman_winforms={winforms}",
            "--output",
            str(stage),
        ],
        cwd=facman,
        log=evidence / "stage.log",
    )
    staged_cli = stage / "bin/facman.exe"
    for name, command in (
        ("product-inspect", [str(staged_cli), "product", "inspect", "--json"]),
        ("package-verify-intact", [str(staged_cli), "package", "verify", "--json"]),
    ):
        completed = capture(command, cwd=stage, output=evidence / f"{name}.json")
        if completed.returncode:
            raise RuntimeError(f"{name} failed in {root_id}")

    drift = root / "stage-drift"
    shutil.copytree(stage, drift)
    marker = drift / "content/factorio/discovery/headless.toml"
    marker.write_bytes(marker.read_bytes() + b"\n# alpha.1 qualification drift\n")
    drift_result = capture(
        [str(drift / "bin/facman.exe"), "package", "verify", "--json"],
        cwd=drift,
        output=evidence / "package-verify-drift.json",
    )
    if drift_result.returncode == 0 or "refused_before_effects" not in drift_result.stdout:
        raise RuntimeError(f"drift control did not refuse before effects in {root_id}")

    dist = root / "dist"
    run(
        [
            *release,
            "archive",
            "--resolution",
            str(resolution),
            "--artifact",
            ARTIFACT,
            "--stage",
            str(stage),
            "--output",
            str(dist),
        ],
        cwd=facman,
        log=evidence / "archive.log",
    )
    archive = dist / archive_name
    assurance = dist / "assurance"
    run(
        [
            *release,
            "assure-candidate",
            "--resolution",
            str(resolution),
            "--artifact",
            ARTIFACT,
            "--stage",
            str(stage),
            "--archive",
            str(archive),
            "--output",
            str(assurance),
        ],
        cwd=facman,
        log=evidence / "assure.log",
    )
    sbom = exactly_one(list(assurance.glob("*.sbom.spdx.v2.3.json")), "candidate SBOM")
    provenance = exactly_one(
        list(assurance.glob("*.provenance.v1.json")), "candidate provenance"
    )
    run(
        [
            *release,
            "verify-package",
            "--resolution",
            str(resolution),
            "--artifact",
            ARTIFACT,
            "--package",
            str(archive),
        ],
        cwd=facman,
        log=evidence / "verify-package.log",
    )
    run(
        [
            *release,
            "verify-candidate-assurance",
            "--resolution",
            str(resolution),
            "--artifact",
            ARTIFACT,
            "--stage",
            str(stage),
            "--archive",
            str(archive),
            "--sbom",
            str(sbom),
            "--provenance",
            str(provenance),
        ],
        cwd=facman,
        log=evidence / "verify-assurance.log",
    )
    return {
        "id": root_id,
        "root": root,
        "cli": cli,
        "winforms": winforms,
        "resolution": resolution,
        "stage": stage,
        "dist": dist,
        "archive": archive,
        "sbom": sbom,
        "provenance": provenance,
        "checkout": checkout / "current-checkout-observation.v2.json",
        "coherence": coherence / "release-coherence-proof.v1.json",
    }


def inventory(record: dict[str, Any]) -> dict[str, tuple[int, str]]:
    paths = {
        "native/facman.exe": record["cli"],
        "native/FacMan.WinForms.exe": record["winforms"],
    }
    for key in ("resolution", "stage", "dist"):
        base: Path = record[key]
        for path in sorted(item for item in base.rglob("*") if item.is_file()):
            paths[f"{key}/{path.relative_to(base).as_posix()}"] = path
    return {name: (path.stat().st_size, sha256(path)) for name, path in paths.items()}


def compare(args: argparse.Namespace, records: list[dict[str, Any]], output: Path) -> None:
    inventories = [inventory(record) for record in records]
    baseline = inventories[0]
    mismatches: list[dict[str, object]] = []
    for index, observed in enumerate(inventories[1:], start=2):
        for name in sorted(set(baseline) | set(observed)):
            if baseline.get(name) != observed.get(name):
                mismatches.append(
                    {
                        "root": f"root{index}",
                        "path": name,
                        "expected": baseline.get(name),
                        "observed": observed.get(name),
                    }
                )
    table = "".join(
        f"{name}\t{size}\t{digest}\n"
        for name, (size, digest) in sorted(baseline.items())
    )
    (output / "complete-byte-table.tsv").write_text(table, encoding="utf-8")
    provenance = load_json(records[0]["provenance"])
    source = provenance["source"]
    comparison = {
        "schema": "facman.canonical_v2_three_root_comparison.v1",
        "source_revision": source["revision"],
        "source_tree": source["tree"],
        "universal_launcher_revision": args.ulk_revision,
        "universal_setup_revision": args.usk_revision,
        "source_observation_digest": provenance["resolution"][
            "source_observation_digest"
        ],
        "coherence_evidence_digest": load_json(records[0]["coherence"])[
            "evidence_digest"
        ],
        "resolution_root_digest": provenance["resolution"]["root_digest"],
        "stage_digest": provenance["stage"]["stage_digest"],
        "archive_sha256": provenance["artifact"]["sha256"],
        "sbom_sha256": sha256(records[0]["sbom"]),
        "provenance_sha256": sha256(records[0]["provenance"]),
        "table_sha256": hashlib.sha256(table.encode("utf-8")).hexdigest(),
        "roots": [
            {
                "id": record["id"],
                "file_count": len(observed),
                "total_bytes": sum(size for size, _ in observed.values()),
            }
            for record, observed in zip(records, inventories)
        ],
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "qualification": {
            "stable_root_build": "pass_in_every_root",
            "native_package_verify": "pass_in_every_root",
            "drift_refusal": "pass_in_every_root",
            "archive_verify": "pass_in_every_root",
            "assurance_verify": "pass_in_every_root",
        },
        "authority": {
            "tagging": False,
            "signing": False,
            "publication": False,
            "support": False,
            "setup_mutation": False,
            "factorio_execution": False,
        },
    }
    (output / "three-root-comparison.v1.json").write_text(
        json.dumps(comparison, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if mismatches:
        raise RuntimeError(f"three-root comparison found {len(mismatches)} mismatches")
    print(json.dumps(comparison, indent=2, sort_keys=True))


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
        raise RuntimeError("alpha.1 qualification requires Windows")
    if len(args.source_revision) != 40:
        raise RuntimeError("source revision must be exact 40-hex")
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
        compare(args, records, output)
    else:
        record = records[0]
        print(
            json.dumps(
                {
                    "status": "single_root_preflight_pass",
                    "source_revision": args.source_revision,
                    "archive": str(record["archive"]),
                    "archive_sha256": sha256(record["archive"]),
                    "authority": "none",
                },
                indent=2,
                sort_keys=True,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
