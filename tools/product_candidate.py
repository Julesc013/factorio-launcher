#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Record, assemble, and verify unsigned unpublished FacMan candidates."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from tools.package.candidate_evidence import (
    ADAPTERS,
    ASSET_SUFFIXES,
    AUTHORITY,
    BUNDLE_SCHEMA,
    CANDIDATE_CLASS,
    PLATFORM_SCHEMA,
    canonical_provenance,
    file_record as asset_record,
    github_provenance,
    read_json,
    sha256_file,
    validate_equivalence,
    validate_identity,
    validate_platform_evidence,
    verify_bundle,
)


ROOT = Path(__file__).resolve().parents[1]


def external(path: Path, label: str, *, must_exist: bool) -> Path:
    if path.is_symlink():
        raise ValueError(f"{label} must not be a symbolic link")
    value = path.resolve(strict=must_exist)
    if value == ROOT or value.is_relative_to(ROOT):
        raise ValueError(f"{label} must be outside the source checkout")
    return value


def source_tree(source_revision: str) -> str:
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = subprocess.check_output(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=ROOT, text=True
    ).strip()
    if head != source_revision or dirty:
        raise ValueError("candidate source must be the exact clean requested revision")
    return subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=ROOT, text=True).strip()


def platform_record(
    root: Path,
    version: str,
    platform: str,
    source_revision: str,
    github: dict[str, str],
) -> Path:
    validate_identity(version, source_revision)
    if platform not in ASSET_SUFFIXES:
        raise ValueError(f"unsupported candidate platform: {platform!r}")
    github = canonical_provenance(github, "platform")
    root = external(root, "candidate root", must_exist=True)
    names = [f"FacMan-{version}-{suffix}" for suffix in ASSET_SUFFIXES[platform]]
    assets = [asset_record(path) for path in (root / "dist" / names[0], root / "setup" / names[1])]
    equivalence = root / "evidence" / f"{platform}-payload-equivalence.v1.json"
    equivalence_value = read_json(equivalence)
    validate_equivalence(equivalence_value, platform, assets)
    record = {
        "schema": PLATFORM_SCHEMA,
        "status": "pass",
        "candidate_class": CANDIDATE_CLASS,
        "version": version,
        "platform": platform,
        "source_revision": source_revision,
        "source_tree": source_tree(source_revision),
        "github": github,
        "assets": assets,
        "payload_equivalence": {
            "adapter": equivalence_value["adapter"],
            "profile": equivalence_value["profile"],
            "sha256": sha256_file(equivalence),
        },
        "authority": AUTHORITY,
    }
    destination = root / "evidence/product-candidate-platform.v1.json"
    with destination.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return destination


def exactly_one(root: Path, name: str) -> Path:
    matches = [path for path in root.rglob(name) if path.is_file() and not path.is_symlink()]
    if len(matches) != 1:
        raise ValueError(f"candidate input count for {name}: {len(matches)}")
    return matches[0]


def _platform_records(inputs: Path) -> dict[str, tuple[dict[str, Any], Path]]:
    paths = sorted(inputs.rglob("product-candidate-platform.v1.json"))
    if len(paths) != len(ASSET_SUFFIXES):
        raise ValueError("candidate bundle requires exactly three platform records")
    records: dict[str, tuple[dict[str, Any], Path]] = {}
    for path in paths:
        value = read_json(path)
        platform = value.get("platform")
        if not isinstance(platform, str) or platform not in ASSET_SUFFIXES or platform in records:
            raise ValueError(f"invalid or duplicate platform candidate evidence: {platform!r}")
        records[platform] = (value, path)
    if set(records) != set(ASSET_SUFFIXES):
        raise ValueError("platform candidate evidence set is incomplete")
    return records


def bundle(
    inputs: Path,
    output: Path,
    version: str,
    source_revision: str,
    github: dict[str, str],
    platform_job: str,
) -> Path:
    validate_identity(version, source_revision)
    github = canonical_provenance(github, "bundle")
    platform_github = github_provenance(
        github["repository"], github["workflow_ref"], github["run_id"],
        github["run_attempt"], platform_job,
    )
    if github["job"] == platform_job:
        raise ValueError("candidate platform and bundle jobs must be distinct")
    inputs = external(inputs, "candidate input root", must_exist=True)
    output = external(output, "candidate bundle root", must_exist=False)
    if output.exists():
        raise ValueError(f"candidate bundle root already exists: {output}")
    tree = source_tree(source_revision)
    records = _platform_records(inputs)
    output.mkdir(parents=True)

    assets: list[dict[str, object]] = []
    for suffixes in ASSET_SUFFIXES.values():
        for suffix in suffixes:
            name = f"FacMan-{version}-{suffix}"
            destination = output / name
            shutil.copy2(exactly_one(inputs, name), destination)
            assets.append(asset_record(destination))
    asset_index = {str(item["filename"]): item for item in assets}

    evidence: list[dict[str, object]] = []
    for platform, suffixes in ASSET_SUFFIXES.items():
        value, record_path = records[platform]
        platform_assets = [asset_index[f"FacMan-{version}-{suffix}"] for suffix in suffixes]
        equivalence_path = exactly_one(inputs, f"{platform}-payload-equivalence.v1.json")
        equivalence = read_json(equivalence_path)
        validate_equivalence(equivalence, platform, platform_assets)
        validate_platform_evidence(
            value, platform, version, source_revision, tree, platform_github,
            platform_assets, sha256_file(equivalence_path),
        )
        for source, name in (
            (record_path, f"{platform}-candidate-evidence.v1.json"),
            (equivalence_path, f"{platform}-payload-equivalence.v1.json"),
        ):
            destination = output / name
            shutil.copy2(source, destination)
            evidence.append(asset_record(destination))

    evidence.sort(key=lambda item: str(item["filename"]))
    checksum = output / "SHA256SUMS"
    checksum.write_text(
        "".join(f"{item['sha256']}  {item['filename']}\n" for item in assets + evidence),
        encoding="utf-8", newline="\n",
    )
    record = {
        "schema": BUNDLE_SCHEMA,
        "status": "pass",
        "candidate_class": CANDIDATE_CLASS,
        "version": version,
        "source_revision": source_revision,
        "source_tree": tree,
        "github": github,
        "platform_job": platform_job,
        "assets": assets,
        "evidence": evidence,
        "checksum": asset_record(checksum),
        "payload_equivalence_adapters": list(ADAPTERS.values()),
        "authority": AUTHORITY,
    }
    destination = output / "product-candidate-bundle.v1.json"
    with destination.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(record, indent=2, sort_keys=True) + "\n")
    verify_bundle(output)
    return destination


def add_github_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repository", required=True)
    parser.add_argument("--workflow-ref", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-attempt", required=True)
    parser.add_argument("--job", required=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    platform_parser = commands.add_parser("platform-record")
    platform_parser.add_argument("--root", required=True, type=Path)
    platform_parser.add_argument("--version", required=True)
    platform_parser.add_argument("--platform", required=True, choices=sorted(ASSET_SUFFIXES))
    platform_parser.add_argument("--source-revision", required=True)
    add_github_arguments(platform_parser)
    bundle_parser = commands.add_parser("bundle")
    bundle_parser.add_argument("--inputs", required=True, type=Path)
    bundle_parser.add_argument("--output", required=True, type=Path)
    bundle_parser.add_argument("--version", required=True)
    bundle_parser.add_argument("--source-revision", required=True)
    bundle_parser.add_argument("--platform-job", required=True)
    add_github_arguments(bundle_parser)
    verify_parser = commands.add_parser("verify")
    verify_parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "verify":
            root = external(args.root, "candidate bundle root", must_exist=True)
            verify_bundle(root)
            result = root / "product-candidate-bundle.v1.json"
            verb = "verified"
        else:
            github = github_provenance(
                args.repository, args.workflow_ref, args.run_id, args.run_attempt, args.job
            )
            if args.command == "platform-record":
                result = platform_record(
                    args.root, args.version, args.platform, args.source_revision, github
                )
            else:
                result = bundle(
                    args.inputs, args.output, args.version, args.source_revision,
                    github, args.platform_job,
                )
            verb = "wrote"
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError,
            subprocess.CalledProcessError) as exc:
        print(f"product-candidate: {exc}")
        return 1
    print(f"product-candidate: {verb} {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
