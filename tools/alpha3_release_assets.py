#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Assemble and verify the exact eight-asset FacMan alpha.3 draft release."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
import tomllib
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "release/index/alpha3_release_source.v1.toml"
ZIP_TIMESTAMP = (2026, 8, 31, 0, 0, 0)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(*arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def write_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def unique_file(root: Path, filename: str) -> Path:
    matches = [path for path in root.rglob(filename) if path.is_file()]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one {filename}, found {len(matches)}")
    return matches[0]


def deterministic_zip(root: Path, destination: Path) -> None:
    destination.unlink(missing_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as output:
        for path in sorted((item for item in root.rglob("*") if item.is_file()), key=lambda item: item.relative_to(root).as_posix()):
            info = zipfile.ZipInfo(path.relative_to(root).as_posix(), ZIP_TIMESTAMP)
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            output.writestr(info, path.read_bytes(), compresslevel=9)


def assemble(inputs: Path, output: Path) -> dict[str, object]:
    with SOURCE.open("rb") as stream:
        source = tomllib.load(stream)
    version = str(source["version"])
    tag = str(source["tag"])
    expected_products = [str(value) for value in source["inventory"]["product_assets"]]
    if output.exists():
        raise ValueError(f"output root must be new: {output}")
    output.mkdir(parents=True)

    products = []
    for filename in expected_products:
        source_path = unique_file(inputs, filename)
        destination = output / filename
        shutil.copy2(source_path, destination)
        products.append({
            "filename": filename,
            "bytes": destination.stat().st_size,
            "sha256": sha256(destination),
        })

    head = git("rev-parse", "HEAD")
    tree = git("rev-parse", "HEAD^{tree}")
    if git("status", "--porcelain"):
        raise ValueError("alpha.3 asset assembly requires a clean source checkout")
    if git("cat-file", "-t", tag) != "tag" or git("rev-parse", f"{tag}^{{}}") != head:
        raise ValueError("alpha.3 requires an annotated tag targeting the exact source HEAD")

    with tempfile.TemporaryDirectory(prefix="facman-alpha3-evidence-") as temporary:
        evidence = Path(temporary) / f"FacMan-{version}-evidence"
        package_evidence = evidence / "packages"
        package_evidence.mkdir(parents=True)
        evidence_sources = sorted(
            path for path in inputs.rglob("*.json")
            if path.is_file() and path.name not in {"candidate.v1.json", "release-manifest.v1.json"}
        )
        for index, path in enumerate(evidence_sources, 1):
            shutil.copy2(path, package_evidence / f"{index:02d}-{path.name}")

        release_root = evidence / "release"
        limitations = release_root / "known-limitations.md"
        limitations.parent.mkdir(parents=True)
        limitations.write_text(
            "# FacMan 0.1.0-alpha.3 known limitations\n\n"
            + "".join(f"- {item}\n" for item in source["known_limitations"]),
            encoding="utf-8",
            newline="\n",
        )
        candidate = {
            "schema": "facman.alpha3_release_candidate.v1",
            "version": version,
            "tag": tag,
            "status": "private_draft_manual_test_candidate",
            "source": {"revision": head, "tree": tree, "clean": True},
            "supersedes": {
                "version": "0.1.0-alpha.2",
                "reason": "user_facing_distribution_contract_incorrect",
                "security_withdrawal": False,
            },
            "products": products,
            "distribution": {
                "authored_asset_count": 8,
                "portable_assets": 3,
                "setup_assets": 3,
                "public_gui": "FacMan",
                "public_terminal": "facman",
                "tui": "facman tui",
            },
            "authority": {
                "public_publication": False,
                "signing": False,
                "support": False,
                "factorio_execution": False,
                "human_verdict": False,
            },
        }
        write_json(release_root / "candidate.v1.json", candidate)
        write_json(release_root / "release-manifest.v1.json", {
            "schema": "facman.alpha3_release_manifest.v1",
            "version": version,
            "tag": tag,
            "source_revision": head,
            "source_tree": tree,
            "products": products,
        })
        write_json(release_root / "tag-receipt.v1.json", {
            "schema": "facman.alpha3_tag_receipt.v1",
            "tag": tag,
            "tag_object_sha": git("rev-parse", tag),
            "source_revision": head,
            "source_tree": tree,
            "observed_at": git("show", "-s", "--format=%cI", head),
            "intended_release": "private_draft_prerelease",
        })
        (evidence / "README.md").write_text(
            "# FacMan alpha.3 evidence\n\nThis archive consolidates package, setup, source, tag, and limitation evidence. It is not a product download.\n",
            encoding="utf-8",
            newline="\n",
        )
        manifest = evidence / "MANIFEST.sha256"
        files = sorted(
            (path for path in evidence.rglob("*") if path.is_file() and path != manifest),
            key=lambda path: path.relative_to(evidence).as_posix(),
        )
        manifest.write_text(
            "".join(f"{sha256(path)}  {path.relative_to(evidence).as_posix()}\n" for path in files),
            encoding="utf-8",
            newline="\n",
        )
        evidence_archive = output / f"FacMan-{version}-evidence.zip"
        deterministic_zip(evidence.parent, evidence_archive)

    checksums = output / f"FacMan-{version}-SHA256SUMS.txt"
    checksum_inputs = sorted(
        (path for path in output.iterdir() if path.is_file() and path != checksums),
        key=lambda path: path.name,
    )
    checksums.write_text(
        "".join(f"{sha256(path)}  {path.name}\n" for path in checksum_inputs),
        encoding="utf-8",
        newline="\n",
    )
    observed = {path.name for path in output.iterdir() if path.is_file()}
    expected = set(source["inventory"]["assets"])
    if observed != expected or len(observed) != 8:
        raise ValueError(
            f"alpha.3 asset mismatch: missing={sorted(expected - observed)} "
            f"unexpected={sorted(observed - expected)}"
        )
    result = {
        "schema": "facman.alpha3_asset_set.v1",
        "status": "complete_private_draft_asset_set",
        "version": version,
        "tag": tag,
        "source_revision": head,
        "source_tree": tree,
        "asset_count": len(observed),
        "assets": {path.name: sha256(path) for path in sorted(output.iterdir()) if path.is_file()},
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


def verify(root: Path) -> None:
    with SOURCE.open("rb") as stream:
        source = tomllib.load(stream)
    expected = set(source["inventory"]["assets"])
    observed = {path.name for path in root.iterdir() if path.is_file()}
    if observed != expected or len(observed) != 8:
        raise ValueError("release root does not contain the exact eight authored assets")
    checksums = root / f"FacMan-{source['version']}-SHA256SUMS.txt"
    for line in checksums.read_text(encoding="utf-8").splitlines():
        digest, filename = line.split("  ", 1)
        if sha256(root / filename) != digest:
            raise ValueError(f"checksum mismatch: {filename}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    assemble_parser = sub.add_parser("assemble")
    assemble_parser.add_argument("--inputs", type=Path, required=True)
    assemble_parser.add_argument("--out", type=Path, required=True)
    verify_parser = sub.add_parser("verify")
    verify_parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "assemble":
        assemble(args.inputs.resolve(strict=True), args.out.resolve())
    else:
        verify(args.root.resolve(strict=True))
        print("alpha3-release-assets: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
