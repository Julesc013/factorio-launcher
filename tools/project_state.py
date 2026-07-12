# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import argparse
import json
import re
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = ROOT / ".aide" / "memory" / "project-state.v1.json"
MARKDOWN_PATH = ROOT / ".aide" / "memory" / "project-state.md"


def provider_pins() -> dict[str, dict[str, str]]:
    with (ROOT / "release" / "index" / "workspace_lock.v1.toml").open("rb") as handle:
        lock = tomllib.load(handle)
    return {
        component["id"]: {
            "source": component["source"],
            "revision": component["pin"],
            "pin_kind": component.get("pin_kind", "provider_revision"),
        }
        for component in lock["component"]
    }


def active_workunit() -> str | None:
    active = ROOT / ".aide" / "queue" / "active"
    tasks = sorted(path.name for path in active.iterdir() if path.is_dir()) if active.is_dir() else []
    if len(tasks) > 1:
        raise ValueError("AIDE default concurrency is one but multiple active tasks exist")
    return tasks[0] if tasks else None


def claim_levels() -> list[dict[str, str]]:
    text = (ROOT / "docs" / "quality" / "safety_claim_ledger.md").read_text(encoding="utf-8")
    rows = []
    for line in text.splitlines():
        if not line.startswith("|") or line.startswith("| ---") or "| Claim |" in line:
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) == 4:
            rows.append({"claim": cells[0], "level": cells[1], "limitation": cells[3]})
    return rows


def target_platforms() -> list[dict[str, str]]:
    result = []
    for profile_id in ("windows_portable_cli_x64", "linux_portable_cli_x64", "macos_portable_cli_x64"):
        with (ROOT / "release" / "profiles" / profile_id / "profile.toml").open("rb") as handle:
            profile = tomllib.load(handle)
        proof = profile.get("proof", {})
        result.append({
            "profile": profile_id,
            "runner": str(proof.get("runner", "")),
            "architecture": str(proof.get("architecture", profile.get("target_arch", ""))),
            "package_format": str(proof.get("package_format", profile.get("bundle", {}).get("package_type", ""))),
        })
    return result


def command_law() -> dict[str, Any]:
    catalog = json.loads((ROOT / "contracts" / "generated-index" / "command_catalog.v2.json").read_text(encoding="utf-8"))
    commands = catalog.get("commands", [])
    return {
        "contracts": len(commands),
        "registered_routes": sum(1 for command in commands if command.get("registered")),
        "schemas": len(list((ROOT / "contracts" / "schema").rglob("*.schema.json"))),
        "catalog_digest": str(catalog.get("source_digest", "")),
    }


def collect() -> dict[str, Any]:
    pins = provider_pins()
    return {
        "schema": "facman.project_state.v1",
        "current_revisions": {
            "factorio_launcher": "HEAD",
            "universal_launcher": pins["universal_launcher"]["revision"],
            "universal_setup": pins["universal_setup"]["revision"],
        },
        "current_phase": "r3.6-real-world-product-readiness",
        "current_checkpoint": "r3.5-zero-exception-productization",
        "completed_wave": {
            "id": "facman-r3.5",
            "revision": "966387280db4eb544e37f1f337c8bcf5d7cec3f4",
            "status": "complete",
        },
        "command_law": command_law(),
        "machine_protocol": {
            "transport": "bounded newline-delimited JSON over stdio",
            "status": "implemented",
            "daemon_transport": "unavailable",
        },
        "active_workunit": active_workunit(),
        "quarantined_capabilities": [
            "run.execute pending operator-supplied real Factorio verdict",
            "setup mutation",
            "network and credential operations",
            "release signing, notarization, publication, and publisher authenticity",
            "TUI and daemon publication until target-specific runtime proof",
        ],
        "claim_levels": claim_levels(),
        "provider_pins": pins,
        "target_proof_platforms": target_platforms(),
        "current_artifacts": [
            "build/Release/facman.exe (local unsigned build, when present)",
            "release/profiles/windows_portable_cli_x64/profile.toml",
            "release/profiles/linux_portable_cli_x64/profile.toml",
            "release/profiles/macos_portable_cli_x64/profile.toml",
            "docs/quality/benchmarks/baseline.v1.json",
            ".aide/history/r3.3/index.json",
            ".aide/history/r3.4/index.json",
            ".aide/history/r3.5/index.json",
            "facman-0.1.0-dev.contract-windows-cli-x64-portable.zip sha256:fba446780e5cb96c4f5afe1b03b59689e1010b2acf9de38257b2f8dc1dfed58b",
            "facman-0.1.0-dev.contract-linux-cli-x64-portable.tar.gz sha256:f36748ccf436ef1a50e6667c315761d5210d0def559c15951e0f3f4e0f6b6d74",
            "facman-0.1.0-dev.contract-macos-cli-x64-portable.tar.gz sha256:ed7479529ffe27c58ada5725c842bde8a0bf6c425d3d2accf8fe8377e0d7b706",
        ],
        "known_blockers": [
            "Real Factorio isolation remains operator-only and has no human verdict.",
            "R3.6 target proof must be rerun at the final R3.6 revision; R3.5 target proof remains revision-pinned historical evidence.",
            "AppKit remains compile-only until an actual bundle runtime invocation is recorded.",
            "Artifacts are unsigned and unpublished; integrity and provenance do not authenticate a publisher.",
            "Universal Launcher and Universal Setup licenses remain NOASSERTION pending an operator legal decision.",
        ],
        "truth_boundaries": [
            "AIDE is development governance only and never a product dependency.",
            "Focused affected tests do not replace the full promotion matrix.",
            "Human acceptance is never inferred from automated checks.",
        ],
    }


def markdown(data: dict[str, Any]) -> str:
    active = data["active_workunit"] or "none"
    lines = [
        "# FacMan Project State",
        "",
        "Generated from `.aide/memory/project-state.v1.json`; edit the generator or canonical repo truth, not this file.",
        "",
        "## Current",
        "",
        f"- phase: `{data['current_phase']}`;",
        f"- checkpoint: `{data['current_checkpoint']}`;",
        f"- active WorkUnit: `{active}`;",
        "- FacMan revision: live `HEAD` (resolve with `git rev-parse HEAD`);",
        f"- Universal Launcher pin: `{data['current_revisions']['universal_launcher']}`;",
        f"- Universal Setup pin: `{data['current_revisions']['universal_setup']}`.",
        "",
        "R3.5 is the architecture endpoint: it records zero manual-JSON and critical-I/O "
        "exceptions, 51 command contracts, 49 registered routes, 122 schemas, generated "
        "command law, a typed Setup gateway, and a bounded machine protocol. R3.6 uses "
        "that foundation for real discovery and frontend product readiness rather than "
        "another repository-wide redesign. The public C ABI remains experimental and "
        "all recorded packages remain unsigned and unpublished.",
        "",
        "## Frozen R3.5 proof",
        "",
        f"- completed wave revision: `{data['completed_wave']['revision']}`;",
        f"- command catalog digest: `{data['command_law']['catalog_digest']}`;",
        f"- machine protocol: {data['machine_protocol']['transport']} ({data['machine_protocol']['status']});",
        "",
        "## Quarantined capabilities",
        "",
    ]
    lines.extend(f"- {value}" for value in data["quarantined_capabilities"])
    lines.extend(["", "## Proof platforms", ""])
    lines.extend(
        f"- `{item['profile']}`: runner `{item['runner']}`, architecture `{item['architecture']}`, format `{item['package_format']}`;"
        for item in data["target_proof_platforms"]
    )
    lines.extend(["", "## Known blockers", ""])
    lines.extend(f"- {value}" for value in data["known_blockers"])
    lines.extend([
        "",
        "## Authorities",
        "",
        "- claim levels and limitations: `docs/quality/safety_claim_ledger.md`;",
        "- provider revisions: `release/index/workspace_lock.v1.toml`;",
        "- active/next queue: `.aide/queue/index.yaml`;",
        "- immutable completed evidence: `.aide/history/<checkpoint>/index.json`;",
        "- affected validation: `contracts/policy/test_impact.v1.json`.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate compact FacMan project truth for AIDE and humans.")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    data = collect()
    rendered_json = json.dumps(data, indent=2, sort_keys=True) + "\n"
    rendered_markdown = markdown(data)
    if args.write:
        JSON_PATH.write_text(rendered_json, encoding="utf-8")
        MARKDOWN_PATH.write_text(rendered_markdown, encoding="utf-8")
        print("project-state: wrote machine and human state")
        return 0
    problems = []
    if not JSON_PATH.is_file() or JSON_PATH.read_text(encoding="utf-8") != rendered_json:
        problems.append("machine state is stale; run python tools/project_state.py --write")
    if not MARKDOWN_PATH.is_file() or MARKDOWN_PATH.read_text(encoding="utf-8") != rendered_markdown:
        problems.append("human state is stale; run python tools/project_state.py --write")
    if problems:
        for problem in problems:
            print(f"project-state: {problem}")
        return 1
    print("project-state: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
