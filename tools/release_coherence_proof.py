# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Prove exact positive release-source coherence and wrong-provider refusals."""

from __future__ import annotations

import argparse
import copy
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

SCHEMA = "facman.release_coherence_proof.v1"
EXPECTED_PROVIDER_IDS = {"universal_launcher", "universal_setup"}
AUTHORITY = {
    "factorio_execution": False,
    "observer_capture": False,
    "permit_issuance": False,
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
) -> tuple[dict[str, Any], dict[str, Any]]:
    workspace_before = _sha256(workspace_lock_path)
    provider_before = _sha256(provider_lock_path)
    workspace_pins = _provider_pins(_toml(workspace_lock_path), "component")
    release_pins = _provider_pins(_toml(provider_lock_path), "provider")
    if set(workspace_pins) != EXPECTED_PROVIDER_IDS or set(release_pins) != EXPECTED_PROVIDER_IDS:
        raise ValueError("positive proof requires exactly both Universal provider identities")
    if workspace_pins != release_pins:
        raise ValueError("positive release-coherence proof requires atomically reconciled pins")

    inputs = load_inputs(ROOT / "release" / "index", ROOT)
    source_observation = from_checkout_observation(checkout, inputs.model)
    if source_observation.get("release_eligible") is not True:
        raise ValueError("exact release-source projection is not release eligible")

    refusals: dict[str, str] = {}
    for index, provider_id in enumerate(sorted(EXPECTED_PROVIDER_IDS)):
        wrong = copy.deepcopy(checkout)
        observed = next(
            (
                item
                for item in wrong.get("providers", [])
                if isinstance(item, dict) and item.get("id") == provider_id
            ),
            None,
        )
        if observed is None:
            raise ValueError(f"checkout observation omits {provider_id}")
        provider_checkout = observed.get("checkout")
        if not isinstance(provider_checkout, dict):
            raise ValueError(f"checkout observation omits {provider_id} checkout facts")
        provider_checkout["head"] = ("0" if index == 0 else "f") * 40
        expected = f"checkout provider {provider_id} commit differs from the lock"
        try:
            from_checkout_observation(wrong, inputs.model)
        except ValueError as error:
            diagnostics = {item.strip() for item in str(error).split(";") if item.strip()}
        else:
            raise ValueError(f"wrong-provider negative unexpectedly accepted {provider_id}")
        if diagnostics != {expected}:
            raise ValueError(
                f"wrong-provider negative for {provider_id} produced unexpected diagnostics: "
                + "; ".join(sorted(diagnostics))
            )
        refusals[provider_id] = expected

    if _sha256(workspace_lock_path) != workspace_before:
        raise ValueError("release-coherence proof changed the workspace lock")
    if _sha256(provider_lock_path) != provider_before:
        raise ValueError("release-coherence proof changed the release-provider lock")

    core = {
        "schema": SCHEMA,
        "result": "pass_exact_release_coherence",
        "source_observation_digest": source_observation["observation_digest"],
        "provider_revisions": dict(sorted(workspace_pins.items())),
        "wrong_provider_refusals": dict(sorted(refusals.items())),
        "workspace_lock_sha256": workspace_before,
        "provider_lock_sha256": provider_before,
        "release_source_observation_created": True,
        "release_package_created": False,
        "tracked_lock_mutated": False,
        "authority_promoted": False,
        "authority": dict(AUTHORITY),
    }
    return source_observation, {
        **core,
        "evidence_digest": domain_digest_value(SCHEMA, core),
    }


def _external_destination(path: Path, label: str) -> Path:
    destination = path.resolve()
    source = ROOT.resolve()
    if destination == source or source in destination.parents:
        raise ValueError(f"{label} must be written outside the source repository")
    if destination.exists():
        raise ValueError(f"{label} already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    return destination


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout-observation", required=True, type=Path)
    parser.add_argument(
        "--workspace-lock", type=Path, default=ROOT / "release/index/workspace_lock.v1.toml"
    )
    parser.add_argument(
        "--provider-lock", type=Path, default=ROOT / "release/index/providers.lock.v2.toml"
    )
    parser.add_argument("--source-observation", required=True, type=Path)
    parser.add_argument("--evidence", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        source, evidence = prove(
            _json(args.checkout_observation),
            args.workspace_lock.resolve(),
            args.provider_lock.resolve(),
        )
        source_path = _external_destination(args.source_observation, "release source observation")
        evidence_path = _external_destination(args.evidence, "release coherence evidence")
        source_path.write_text(pretty_json(source), encoding="utf-8")
        evidence_path.write_text(pretty_json(evidence), encoding="utf-8")
    except (OSError, ValueError, json.JSONDecodeError, tomllib.TOMLDecodeError) as error:
        print(f"release-coherence-proof: {error}", file=sys.stderr)
        return 1
    print(f"release-coherence-proof: pass {evidence['evidence_digest']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
