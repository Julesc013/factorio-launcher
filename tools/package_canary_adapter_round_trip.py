# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Verify a repaired-provider package root and archive are the same canary payload."""

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
from tools.release_compiler.packages import inspect_package  # noqa: E402

CANARY_MANIFEST = "manifest/repaired-provider-canary.v1.json"
AUTHORITY_FIELDS = frozenset({
    "factorio_execution",
    "provider_adoption",
    "publication",
    "release_package",
    "route_promotion",
    "setup_mutation",
    "signing",
})


def _load_canary_manifest(package_root: Path) -> dict[str, Any]:
    path = package_root / CANARY_MANIFEST
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"canary manifest cannot be read: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("canary manifest must be a JSON object")
    return value


def _validate_canary_manifest(
    value: dict[str, Any],
    expected_facman_revision: str,
    expected_ulk_revision: str,
    expected_usk_revision: str,
) -> None:
    expected = {
        "factorio_launcher": expected_facman_revision,
        "universal_launcher": expected_ulk_revision,
        "universal_setup": expected_usk_revision,
    }
    if value.get("schema") != "facman.repaired_provider_canary.v1":
        raise ValueError("package does not carry repaired-provider canary custody")
    if value.get("classification") != "noncanonical_engineering_candidate":
        raise ValueError("package canary classification is missing or changed")
    if value.get("candidate_version") != (
        "0.1.0-alpha.0+canary." + expected_facman_revision[:12]
    ):
        raise ValueError("package canary version differs from the exact FacMan source")
    if value.get("source_revisions") != expected:
        raise ValueError("package canary source revisions differ from the declared inputs")
    authority = value.get("authority")
    if not isinstance(authority, dict) or set(authority) != AUTHORITY_FIELDS:
        raise ValueError("package canary authority fields differ from the closed set")
    if any(authority.values()):
        raise ValueError("package canary must not grant authority")
    for field in ("provider_adoption", "published", "release_eligible", "signed"):
        if value.get(field) is not False:
            raise ValueError(f"package canary {field} must be false")
    if value.get("canonical_provider_pin_unchanged") is not True:
        raise ValueError("package canary must preserve the tracked canonical provider pin")


def _content_projection(inspection: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    projection = [
        {
            "path": str(entry["path"]),
            "sha256": str(entry["sha256"]),
            "size": int(entry["size"]),
        }
        for entry in inspection["entries"]
    ]
    encoded = json.dumps(
        projection, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return projection, hashlib.sha256(encoded).hexdigest()


def verify(
    package_root: Path,
    artifact: Path,
    expected_facman_revision: str,
    expected_ulk_revision: str,
    expected_usk_revision: str,
) -> dict[str, Any]:
    if not package_root.is_dir():
        raise ValueError(f"package root is missing: {package_root}")
    if not artifact.is_file() or artifact.suffix.lower() != ".zip":
        raise ValueError(f"canary artifact must be an existing ZIP: {artifact}")
    manifest_problems = package_hash_manifest.verify_manifest(package_root)
    if manifest_problems:
        raise ValueError("package root integrity failed: " + "; ".join(manifest_problems))
    manifest = _load_canary_manifest(package_root)
    _validate_canary_manifest(
        manifest,
        expected_facman_revision,
        expected_ulk_revision,
        expected_usk_revision,
    )
    root_inspection = inspect_package(package_root)
    archive_inspection = inspect_package(artifact)
    root_projection, root_digest = _content_projection(root_inspection)
    archive_projection, archive_digest = _content_projection(archive_inspection)
    if archive_projection != root_projection:
        root_paths = {str(item["path"]) for item in root_projection}
        archive_paths = {str(item["path"]) for item in archive_projection}
        raise ValueError(
            "canary ZIP is not an exact content projection of the package root: "
            f"missing={sorted(root_paths - archive_paths)} "
            f"extra={sorted(archive_paths - root_paths)}"
        )
    archive_modes = {int(item["mode"]) for item in archive_inspection["entries"]}
    if not archive_modes.issubset({0o644, 0o755}):
        raise ValueError(f"canary ZIP contains unsupported normalized modes: {archive_modes}")
    return {
        "schema": "facman.canary_package_adapter_round_trip.v1",
        "classification": "noncanonical_engineering_candidate",
        "canonical_release_verified": False,
        "verified": True,
        "entry_count": len(root_projection),
        "content_projection_sha256": root_digest,
        "archive_content_projection_sha256": archive_digest,
        "archive_sha256": archive_inspection["container_sha256"],
        "source_revisions": manifest["source_revisions"],
        "authority": manifest["authority"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--expected-facman-revision", required=True)
    parser.add_argument("--expected-ulk-revision", required=True)
    parser.add_argument("--expected-usk-revision", required=True)
    args = parser.parse_args(argv)
    try:
        report = verify(
            args.package_root.resolve(),
            args.artifact.resolve(),
            args.expected_facman_revision,
            args.expected_ulk_revision,
            args.expected_usk_revision,
        )
    except (OSError, ValueError) as exc:
        print(f"package-canary-adapter-round-trip: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    print("package-canary-adapter-round-trip: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
