# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import package_hash_manifest, provenance_build
from tools.package import pipeline, provenance, verification

DEFAULT_PROFILE = "windows_portable_cli_x64"
DEFAULT_BUILD_ROOT = ROOT / "build" / "native-smoke"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a package twice and prove byte-identical output from a clean checkout."
    )
    parser.add_argument("--profile", default=DEFAULT_PROFILE)
    parser.add_argument("--build-root", default=str(DEFAULT_BUILD_ROOT))
    args = parser.parse_args(argv)

    try:
        report = prove(args.profile, Path(args.build_root).resolve())
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"package-reproducibility-proof: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    print("package-reproducibility-proof: ok")
    return 0


def prove(profile_id: str, build_root: Path) -> dict[str, Any]:
    provenance.require_clean(ROOT, allow_dirty=False)
    if not build_root.is_dir():
        raise ValueError(f"native build root is missing: {build_root}")

    with tempfile.TemporaryDirectory(prefix="facman-package-repro-proof-") as tmp:
        proof_root = Path(tmp)
        first = build_once(profile_id, build_root, proof_root / "first")
        second = build_once(profile_id, build_root, proof_root / "second")
        report = compare_builds(profile_id, first, second)
    return report


def build_once(profile_id: str, build_root: Path, root: Path) -> dict[str, Path]:
    out_root = root / "packages"
    dist_root = root / "dist"
    package_root = pipeline.build_profile(
        profile_id=profile_id,
        out_root=out_root,
        build_root=build_root,
        dist_root=dist_root,
        allow_dirty=False,
    )
    artifacts = [
        path
        for path in dist_root.iterdir()
        if path.is_file() and archive_suffix(path) in {".zip", ".tar.gz"}
    ]
    if len(artifacts) != 1:
        raise ValueError(f"expected exactly one package artifact, found {len(artifacts)}")
    artifact = artifacts[0]
    return {
        "package": package_root,
        "artifact": artifact,
        "provenance": artifact.with_name(artifact.name + ".provenance.v1.json"),
        "sbom": package_root / "manifest" / "sbom.spdx.v2.3.json",
    }


def compare_builds(
    profile_id: str,
    first: dict[str, Path],
    second: dict[str, Path],
) -> dict[str, Any]:
    for label, build in (("first", first), ("second", second)):
        problems = package_hash_manifest.verify_manifest(build["package"])
        if problems:
            raise ValueError(f"{label} package hash closure failed: {'; '.join(problems)}")
        problems = provenance_build.verify_artifact_provenance(
            build["provenance"],
            build["artifact"],
            build["package"],
        )
        if problems:
            raise ValueError(f"{label} package provenance failed: {'; '.join(problems)}")

    first_tree = tree_snapshot(first["package"])
    second_tree = tree_snapshot(second["package"])
    if first_tree != second_tree:
        changed = sorted(set(first_tree) ^ set(second_tree))
        changed.extend(
            path
            for path in sorted(set(first_tree) & set(second_tree))
            if first_tree[path] != second_tree[path]
        )
        raise ValueError("package tree is not reproducible: " + ", ".join(changed[:10]))

    artifact_digest = verification.require_identical(first["artifact"], second["artifact"])
    provenance_digest = verification.require_identical(
        first["provenance"], second["provenance"]
    )
    sbom_digest = verification.require_identical(first["sbom"], second["sbom"])
    build_info = json.loads(
        (first["package"] / "manifest" / "build_info.v1.json").read_text(encoding="utf-8")
    )
    return {
        "schema": "facman.package_reproducibility_proof.v1",
        "status": "pass",
        "claim": "complete_selected_package_is_byte_reproducible",
        "profile_id": profile_id,
        "artifact": file_identity(first["artifact"], artifact_digest),
        "provenance": file_identity(first["provenance"], provenance_digest),
        "sbom": file_identity(first["sbom"], sbom_digest),
        "package_tree": {
            "file_count": len(first_tree),
            "sha256": snapshot_digest(first_tree),
        },
        "source_revisions": build_info["source_revisions"],
        "source_dirty": build_info["source_dirty"],
        "authenticity": "publisher_authenticity_not_proven",
        "execution_authority": "unchanged_not_authorized",
        "h1_inference": "none",
    }


def tree_snapshot(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): verification.sha256(path)
        for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix())
        if path.is_file()
    }


def snapshot_digest(snapshot: dict[str, str]) -> str:
    payload = json.dumps(snapshot, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def file_identity(path: Path, digest: str) -> dict[str, Any]:
    return {"name": path.name, "size": path.stat().st_size, "sha256": digest}


def archive_suffix(path: Path) -> str:
    return ".tar.gz" if path.name.endswith(".tar.gz") else path.suffix.lower()


if __name__ == "__main__":
    raise SystemExit(main())
