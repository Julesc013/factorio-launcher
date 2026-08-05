# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Prove that unreconciled provider inputs fail the unchanged release source gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.release_compiler.canonical import domain_digest_value, pretty_json  # noqa: E402
from tools.release_compiler.compiler import load_inputs  # noqa: E402
from tools.release_compiler.source_observation import from_checkout_observation  # noqa: E402

SCHEMA = "facman.release_coherence_negative_control.v1"
DOMAIN = SCHEMA
EXPECTED_PROVIDER_IDS = {"universal_launcher", "universal_setup"}
AUTHORITY_CEILING = {
    "factorio_execution": False,
    "provider_adoption": False,
    "publication": False,
    "release_package": False,
    "route_promotion": False,
    "setup_mutation": False,
    "signing": False,
}


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("checkout observation must be a JSON object")
    return value


def _toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _provider_pins(document: dict[str, Any], key: str) -> dict[str, str]:
    rows = document.get(key)
    if not isinstance(rows, list):
        raise ValueError(f"provider record omits {key}")
    pin_key = "pin" if key == "component" else "source_revision"
    return {
        str(item.get("id")): str(item.get(pin_key, ""))
        for item in rows
        if isinstance(item, dict) and str(item.get("id")) in EXPECTED_PROVIDER_IDS
    }


def prove(
    checkout: dict[str, Any],
    workspace_lock_path: Path,
    provider_lock_path: Path,
    forbidden_source_output: Path,
    forbidden_package_output: Path,
) -> dict[str, Any]:
    workspace_before = _sha256(workspace_lock_path)
    provider_before = _sha256(provider_lock_path)
    workspace_pins = _provider_pins(_toml(workspace_lock_path), "component")
    release_pins = _provider_pins(_toml(provider_lock_path), "provider")
    if set(workspace_pins) != EXPECTED_PROVIDER_IDS or set(release_pins) != EXPECTED_PROVIDER_IDS:
        raise ValueError("negative control requires exactly both Universal provider identities")
    mismatches = {
        provider_id
        for provider_id in EXPECTED_PROVIDER_IDS
        if workspace_pins[provider_id] != release_pins[provider_id]
    }
    if mismatches != EXPECTED_PROVIDER_IDS:
        raise ValueError(
            "release-refusal negative control is stale; exact two-provider mismatch no longer exists"
        )
    for forbidden in (forbidden_source_output, forbidden_package_output):
        if forbidden.exists():
            raise ValueError(f"negative-control output must be absent before proof: {forbidden}")

    inputs = load_inputs(ROOT / "release" / "index", ROOT)
    expected_diagnostics = {
        f"source observation provider {provider_id} commit differs from lock"
        for provider_id in EXPECTED_PROVIDER_IDS
    }
    try:
        from_checkout_observation(checkout, inputs.model)
    except ValueError as error:
        diagnostics = {item.strip() for item in str(error).split(";") if item.strip()}
    else:
        raise ValueError("release source validator unexpectedly accepted unreconciled providers")
    if diagnostics != expected_diagnostics:
        raise ValueError(
            "release source validator did not produce the exact provider-mismatch refusal: "
            + "; ".join(sorted(diagnostics))
        )
    if forbidden_source_output.exists():
        raise ValueError("release source validator emitted a forbidden source observation")
    if forbidden_package_output.exists():
        raise ValueError("release source refusal emitted a forbidden release package")
    if _sha256(workspace_lock_path) != workspace_before:
        raise ValueError("release refusal changed the workspace lock")
    if _sha256(provider_lock_path) != provider_before:
        raise ValueError("release refusal changed the release-provider lock")

    core = {
        "schema": SCHEMA,
        "result": "pass_exact_release_refusal",
        "expected_provider_mismatches": sorted(mismatches),
        "diagnostics": sorted(diagnostics),
        "workspace_lock_sha256": workspace_before,
        "provider_lock_sha256": provider_before,
        "release_source_observation_created": False,
        "release_package_created": False,
        "tracked_lock_mutated": False,
        "authority_promoted": False,
        "authority": AUTHORITY_CEILING,
    }
    return {**core, "evidence_digest": domain_digest_value(DOMAIN, core)}


def write_evidence(path: Path, value: dict[str, Any]) -> Path:
    destination = path.resolve()
    if destination == ROOT or ROOT.resolve() in destination.parents:
        raise ValueError("release-refusal evidence output must be outside the source repository")
    if destination.exists():
        raise ValueError(f"release-refusal evidence output already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(pretty_json(value), encoding="utf-8")
    return destination


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Require the exact unreconciled-provider release-source refusal."
    )
    parser.add_argument("--checkout-observation", required=True)
    parser.add_argument(
        "--workspace-lock", default="release/index/workspace_lock.v1.toml"
    )
    parser.add_argument(
        "--provider-lock", default="release/index/providers.lock.v2.toml"
    )
    parser.add_argument("--evidence", required=True)
    args = parser.parse_args(argv)
    evidence_path = Path(args.evidence).resolve()
    proof_root = evidence_path.parent
    try:
        report = prove(
            _json(Path(args.checkout_observation)),
            Path(args.workspace_lock).resolve(),
            Path(args.provider_lock).resolve(),
            proof_root / "forbidden-release-source-observation.v1.json",
            proof_root / "forbidden-release-package",
        )
        destination = write_evidence(evidence_path, report)
    except (OSError, ValueError, json.JSONDecodeError, tomllib.TOMLDecodeError) as error:
        print(f"release-coherence-negative-control: {error}", file=sys.stderr)
        return 1
    print(
        "release-coherence-negative-control: exact refusal preserved "
        f"{report['evidence_digest']} -> {destination}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
