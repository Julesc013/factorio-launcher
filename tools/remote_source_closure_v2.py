# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Canonical repository-identity envelope over the immutable v1 proof engine."""

from __future__ import annotations

import argparse
import contextlib
import os
import subprocess
import sys
import tomllib
from collections.abc import Iterator
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import remote_source_closure as v1
from tools import repository_identity


SCHEMA = "facman.remote_source_closure.v2"
SCHEMA_PATH = ROOT / "contracts/schema/release/remote_source_closure.v2.schema.json"
FACMAN_IDENTITY = repository_identity.identity("facman")
UNIVERSAL_LAUNCHER_IDENTITY = repository_identity.identity("universal_launcher")
UNIVERSAL_SETUP_IDENTITY = repository_identity.identity("universal_setup")
FACTORIO_REMOTE = FACMAN_IDENTITY.canonical_https_remote
LEGACY_FACTORIO_REMOTES = FACMAN_IDENTITY.legacy_https_remotes
FACTORIO_REF = v1.FACTORIO_REF
CANONICAL_REMOTES = {
    "factorio-launcher": FACTORIO_REMOTE,
    "universal-launcher": UNIVERSAL_LAUNCHER_IDENTITY.canonical_https_remote,
    "universal-setup": UNIVERSAL_SETUP_IDENTITY.canonical_https_remote,
}
SUCCESSOR_PROOF_PATHS = (
    "tools/remote_source_closure_v2.py",
    "tools/repro_workspace_smoke_v2.py",
    "tools/repository_identity.py",
    "release/index/repository_identity.v1.toml",
    "contracts/schema/release/remote_source_closure.v2.schema.json",
)

ClosureFailure = v1.ClosureFailure
SourceSpec = v1.SourceSpec
_VERIFY_V1_PROOF_CODE = v1.verify_loaded_proof_code


def classify_factorio_remote(remote: str) -> str | None:
    return FACMAN_IDENTITY.classifies_remote(remote)


def _verify_successor_proof_code(factorio_repo: Path) -> dict[str, dict[str, Any]]:
    result = _VERIFY_V1_PROOF_CODE(factorio_repo)
    for relative in SUCCESSOR_PROOF_PATHS:
        loaded_path = ROOT / relative
        cloned_path = factorio_repo / relative
        if not cloned_path.is_file():
            raise ClosureFailure(f"cloned successor proof code is missing: {relative}")
        loaded_sha256 = v1.sha256_file(loaded_path)
        cloned_sha256 = v1.sha256_file(cloned_path)
        if loaded_sha256 != cloned_sha256:
            raise ClosureFailure(
                f"loaded successor proof code differs from the exact FacMan clone: {relative}"
            )
    return result


@contextlib.contextmanager
def _canonical_repository_identity() -> Iterator[None]:
    original_remote = v1.FACTORIO_REMOTE
    original_remotes = v1.CANONICAL_REMOTES
    original_verifier = v1.verify_loaded_proof_code
    v1.FACTORIO_REMOTE = FACTORIO_REMOTE
    v1.CANONICAL_REMOTES = dict(CANONICAL_REMOTES)
    v1.verify_loaded_proof_code = _verify_successor_proof_code
    try:
        yield
    finally:
        v1.FACTORIO_REMOTE = original_remote
        v1.CANONICAL_REMOTES = original_remotes
        v1.verify_loaded_proof_code = original_verifier


def checked_spec(spec: SourceSpec) -> SourceSpec:
    with _canonical_repository_identity():
        return v1.checked_spec(spec)


def provider_specs_from_lock(path: Path) -> list[SourceSpec]:
    with _canonical_repository_identity():
        return v1.provider_specs_from_lock(path)


def _successor_proof_code() -> dict[str, str]:
    return {
        relative: v1.sha256_file(ROOT / relative)
        for relative in SUCCESSOR_PROOF_PATHS
    }


def _envelope(legacy_proof: dict[str, Any]) -> dict[str, Any]:
    factorio_rows = [
        row
        for row in legacy_proof.get("repositories", [])
        if isinstance(row, dict) and row.get("id") == "factorio-launcher"
    ]
    if len(factorio_rows) != 1 or factorio_rows[0].get("remote") != FACTORIO_REMOTE:
        raise ClosureFailure("v2 proof must bind the canonical FacMan remote")
    envelope = {
        "schema": SCHEMA,
        "status": "pass",
        "claim": "canonical_repository_identity_source_closure_proven",
        "repository_identity": {
            "role": FACMAN_IDENTITY.role,
            "github_repository_id": FACMAN_IDENTITY.github_repository_id,
            "canonical_slug": FACMAN_IDENTITY.canonical_slug,
            "canonical_https_remote": FACMAN_IDENTITY.canonical_https_remote,
            "observed_remote_classification": "canonical",
        },
        "successor_proof_code": _successor_proof_code(),
        "legacy_v1_engine_proof": legacy_proof,
        "authority_promotion": False,
        "factorio_execution": False,
        "permit_issuance": False,
        "publication": False,
    }
    v1.validate_source_closure_report(envelope, SCHEMA_PATH)
    return envelope


def execute(
    factorio: SourceSpec,
    *,
    clone_root: Path | None = None,
    build_root: Path | None = None,
    keep_clones: bool = False,
    factorio_archive: Path | None = None,
) -> dict[str, Any]:
    with _canonical_repository_identity():
        legacy_proof = v1.execute(
            factorio,
            clone_root=clone_root,
            build_root=build_root,
            keep_clones=keep_clones,
            factorio_archive=factorio_archive,
        )
    return _envelope(legacy_proof)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Prove canonical FacMan repository identity and exact three-repository source closure."
    )
    parser.add_argument("--factorio-pin", required=True)
    parser.add_argument("--factorio-remote", default=FACTORIO_REMOTE)
    parser.add_argument("--factorio-ref", default=FACTORIO_REF)
    parser.add_argument("--clone-root", type=Path)
    parser.add_argument("--build-root", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--keep-clones", action="store_true")
    parser.add_argument("--successor-route", action="store_true")
    parser.add_argument("--factorio-archive", type=Path)
    args = parser.parse_args(argv)
    try:
        v1.assert_safe_git_environment(os.environ)
        v1.assert_safe_build_environment(os.environ)
        if args.report.exists():
            raise ClosureFailure(
                f"report destination already exists and will not be overwritten: {args.report}"
            )
        if args.successor_route != (args.factorio_archive is not None):
            raise ClosureFailure(
                "--successor-route and --factorio-archive must be supplied together"
            )
        report = execute(
            SourceSpec(
                "factorio-launcher",
                args.factorio_remote,
                args.factorio_ref,
                args.factorio_pin,
            ),
            clone_root=args.clone_root,
            build_root=args.build_root,
            keep_clones=args.keep_clones,
            factorio_archive=args.factorio_archive,
        )
        v1.write_report(args.report.resolve(), report)
    except (ClosureFailure, OSError, subprocess.SubprocessError, tomllib.TOMLDecodeError) as exc:
        print(f"remote-source-closure-v2: {exc}", file=sys.stderr)
        return 1
    print(f"remote-source-closure-v2: PASS report={args.report.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
