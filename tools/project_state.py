# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import argparse
import json
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = ROOT / "release" / "index" / "project_status.v2.toml"
SUPPORT_PATH = ROOT / "release" / "index" / "support_matrix.v1.toml"
JSON_PATH = ROOT / ".aide" / "memory" / "project-state.v2.json"
LEGACY_JSON_PATH = ROOT / ".aide" / "memory" / "project-state.v1.json"
MARKDOWN_PATH = ROOT / ".aide" / "memory" / "project-state.md"

SURFACES = {
    ROOT / "README.md": "FACMAN-PROJECT-STATUS",
    ROOT / "docs" / "roadmap.md": "FACMAN-PROJECT-STATUS",
    ROOT / "docs" / "platform" / "support_matrix.md": "FACMAN-SUPPORT-STATUS",
    ROOT / "docs" / "release" / "checkpoints" / "README.md": "FACMAN-RELEASE-STATUS",
}


def load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def provider_pins() -> dict[str, dict[str, str]]:
    lock = load_toml(ROOT / "release" / "index" / "workspace_lock.v1.toml")
    return {
        component["id"]: {
            "source": component["source"],
            "revision": component["pin"],
            "pin_kind": component.get("pin_kind", "provider_revision"),
        }
        for component in lock["component"]
    }


def command_law() -> dict[str, Any]:
    catalog = json.loads(
        (ROOT / "contracts" / "generated-index" / "command_catalog.v2.json").read_text(
            encoding="utf-8"
        )
    )
    refusals = load_toml(ROOT / "contracts" / "refusal" / "refusal_codes.v1.toml")
    commands = catalog.get("commands", [])
    return {
        "contracts": len(commands),
        "registered_routes": sum(1 for command in commands if command.get("registered")),
        "schemas": len(list((ROOT / "contracts" / "schema").rglob("*.schema.json"))),
        "refusal_codes": len(refusals.get("code", [])),
        "catalog_digest": str(catalog.get("source_digest", "")),
    }


def support_platforms() -> list[dict[str, str]]:
    matrix = load_toml(SUPPORT_PATH)
    keys = (
        "id",
        "frontend_family",
        "compile_status",
        "runtime_status",
        "package_status",
        "publication_status",
        "support_status",
        "evidence_revision",
    )
    return [{key: str(platform.get(key, "")) for key in keys} for platform in matrix["platform"]]


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


def collect() -> dict[str, Any]:
    status = load_toml(STATUS_PATH)
    pins = provider_pins()
    return {
        "schema": "facman.project_state.v2",
        "product_version": status["product_version"],
        "completed_wave": {
            "id": status["completed_wave"],
            "status": "complete",
            "implementation_proof_revision": status["implementation_proof_revision"],
            "hosted_matrix_revision": status["hosted_matrix_revision"],
        },
        "current_checkpoint": status["current_checkpoint"],
        "active_work_unit": status["active_work_unit"] or None,
        "last_closed_work_unit": status.get("last_closed_work_unit", "") or None,
        "r3_8_repair": status["r3_8_repair"],
        "r3_8_public_integration": status["r3_8_public_integration"],
        "m1_managed_portable_install": status["m1_managed_portable_install"],
        "m1_public_integration": status["m1_public_integration"],
        "universal_repository_licenses": status["universal_repository_licenses"],
        "next_authority_gate": status["next_authority_gate"],
        "safe_beta": status["safe_beta"],
        "execution": status["execution"],
        "release": status["release"],
        "validation": status["validation"],
        "current_revisions": {
            "factorio_launcher": status["h1_candidate_revision"],
            "accepted_integration": status["accepted_integration_revision"],
            "universal_launcher": pins["universal_launcher"]["revision"],
            "universal_setup": pins["universal_setup"]["revision"],
        },
        "provider_pins": pins,
        "command_law": command_law(),
        "machine_protocol": {
            "transport": "bounded newline-delimited JSON over stdio",
            "status": "implemented",
            "daemon_transport": "unavailable",
        },
        "platforms": support_platforms(),
        "quarantined_capabilities": status["quarantined_capabilities"],
        "known_blockers": status["known_blockers"],
        "claim_levels": claim_levels(),
        "truth_boundaries": [
            "AIDE is development governance only and never a product dependency.",
            "Focused affected tests do not replace the full promotion matrix.",
            "Human acceptance is never inferred from automated checks.",
            "Compile, runtime, package, publication, and support status are separate claims.",
        ],
    }


def markdown(data: dict[str, Any]) -> str:
    law = data["command_law"]
    validation = data["validation"]
    revisions = data["current_revisions"]
    lines = [
        "# FacMan Project State",
        "",
        "Generated from `release/index/project_status.v2.toml`, the workspace lock,",
        "the command/refusal registries, and the support matrix. Edit those canonical",
        "inputs, then run `py -3 tools/project_state.py --write`.",
        "",
        "## Current",
        "",
        f"- product version: `{data['product_version']}`;",
        f"- completed wave: `{data['completed_wave']['id']}`;",
        f"- checkpoint: `{data['current_checkpoint']}`;",
        f"- active WorkUnit: `{data['active_work_unit'] or 'none'}`;",
        f"- last closed WorkUnit: `{data['last_closed_work_unit'] or 'none'}`;",
        f"- next authority gate: `{data['next_authority_gate']}`;",
        f"- H1 candidate: `{revisions['factorio_launcher']}`;",
        f"- accepted integration evidence: `{revisions['accepted_integration']}`;",
        f"- Universal Launcher pin: `{revisions['universal_launcher']}`;",
        f"- Universal Setup pin: `{revisions['universal_setup']}`;",
        f"- execution: `{data['execution']['status']}` / `{data['execution']['reason']}`;",
        f"- operator verdict: `{data['execution']['operator_verdict']}`;",
        f"- Safe beta: `{str(data['safe_beta']).lower()}`;",
        f"- release: `{data['release']['status']}` / `{data['release']['authenticity']}`.",
        f"- public SDK: `{data['release']['public_sdk']}`; stable compatibility is not promised.",
        f"- M1 managed portable install: `{data['m1_managed_portable_install']['status']}`; "
        f"ordinary setup apply: `{data['m1_managed_portable_install']['ordinary_setup_apply']}`.",
        f"- M1 public integration: `{data['m1_public_integration']['status']}` at canonical main "
        f"`{data['m1_public_integration']['canonical_main_revision']}`.",
        f"- Universal repository licenses: `{data['universal_repository_licenses']['status']}`; "
        f"publication authority: `{str(data['universal_repository_licenses']['publication_authority']).lower()}`.",
        "",
        "R3.7 is complete. The exact R3.7 runtime is frozen as the H1 candidate. "
        "M1 is independently fixture-proven for managed portable setup. No execution, Safe beta, "
        "stable SDK, daemon, live-target setup, networking, credential, signing, "
        "or publication authority is inferred from the completed non-execution proof.",
        "",
        "## Contract and validation identity",
        "",
        f"- command contracts: `{law['contracts']}`;",
        f"- registered routes: `{law['registered_routes']}`;",
        f"- schemas: `{law['schemas']}`;",
        f"- refusal codes: `{law['refusal_codes']}`;",
        f"- command catalog digest: `{law['catalog_digest']}`;",
        f"- accepted CI revision: `{validation['accepted_revision']}`;",
        f"- CI / CodeQL / security / schema runs: `{validation['ci_run']}` / "
        f"`{validation['code_security_run']}` / `{validation['security_policy_run']}` / "
        f"`{validation['schema_check_run']}`;",
        f"- accepted matrix counts: `{validation['native_test_count']}` native and "
        f"`{validation['python_test_count']}` Python tests.",
        "",
        "## Platform proof",
        "",
        "| Platform | Compile | Runtime | Package | Publication | Support |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    lines.extend(
        f"| `{item['id']}` | {item['compile_status']} | {item['runtime_status']} | "
        f"{item['package_status']} | {item['publication_status']} | {item['support_status']} |"
        for item in data["platforms"]
    )
    lines.extend(["", "## Quarantined capabilities", ""])
    lines.extend(f"- {value}" for value in data["quarantined_capabilities"])
    lines.extend(["", "## Known blockers", ""])
    lines.extend(f"- {value}" for value in data["known_blockers"])
    lines.extend([
        "",
        "## Authorities",
        "",
        "- canonical status: `release/index/project_status.v2.toml`;",
        "- provider revisions: `release/index/workspace_lock.v1.toml`;",
        "- platform proof: `release/index/support_matrix.v1.toml`;",
        "- claim levels and limitations: `docs/quality/safety_claim_ledger.md`;",
        "- immutable accepted evidence: `docs/release/checkpoints/`.",
        "",
    ])
    return "\n".join(lines)


def readme_status(data: dict[str, Any]) -> str:
    law = data["command_law"]
    return "\n".join([
        "## Current Status",
        "",
        f"R3.7 is complete and `{data['current_revisions']['factorio_launcher']}` is the exact H1 candidate.",
        f"The current contract surface contains {law['contracts']} commands, {law['schemas']} schemas, "
        f"and {law['refusal_codes']} refusal codes.",
        "",
        f"The next authority gate is **{data['next_authority_gate']}**. `run.execute` remains "
        f"`{data['execution']['status']}` with `{data['execution']['reason']}`.",
        f"The operator verdict is `{data['execution']['operator_verdict']}` and Safe beta remains unpromoted.",
        f"M1 managed portable setup is `{data['m1_managed_portable_install']['status']}` in bounded fixture, "
        "disposable, and package-proof roots; ordinary live-target apply remains unavailable.",
        "Packages are unsigned and unpublished. The public C ABI and installed SDK remain experimental; "
        "neither carries a stable compatibility promise.",
    ])


def roadmap_status(data: dict[str, Any]) -> str:
    verdict = data["execution"]["operator_verdict"]
    if verdict == "Fail":
        repair = data["r3_8_repair"]
        gate_detail = [
            "The human-reviewed H1 verdict for the Steam-backed route is **Fail**.",
            "The narrow isolation repair is "
            f"`{repair['status']}` at dev integration `{repair['dev_integration_revision']}`; "
            "Steam Cloud remains a protected external domain.",
            "A standalone/manual distribution must receive its own revision-pinned reviewed H1 Pass before "
            "an R3.8 execution-candidate WorkUnit can open.",
        ]
    else:
        gate_detail = [
            "Until a reviewed operator verdict exists, execution, Safe beta, setup mutation, networking, "
            "credentials, server processes, daemon publication, signing, and publication remain unavailable.",
        ]
    return "\n".join([
        "## Current Status and Authority Gate",
        "",
        f"R3.7 is complete. The frozen H1 candidate is "
        f"`{data['current_revisions']['factorio_launcher']}` and the next authority gate is "
        f"**{data['next_authority_gate']}**.",
        "",
        "- H1 Pass may create a separate R3.8 execution-candidate branch.",
        "- H1 Fail routes to a narrow isolation-repair WorkUnit.",
        "- H1 Inconclusive routes to improved observation and a repeat.",
        "",
        *gate_detail,
        "M1 fixture-backed managed setup is complete. Ordinary live-target setup apply remains unavailable.",
        "Execution, Safe beta, networking, credentials, server processes, daemon publication, "
        "signing, and publication remain unavailable.",
        "Truth/conformance and public-boundary hardening may continue without changing the frozen H1 runtime.",
    ])


def support_status(data: dict[str, Any]) -> str:
    lines = [
        "## Current Proven Status",
        "",
        "Compile, runtime, package, publication, and support are independent claims. "
        "The evidence revision is blank where no proof is claimed.",
        "",
        "| Platform | Compile | Runtime | Package | Publication | Support | Evidence |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    lines.extend(
        f"| `{item['id']}` | {item['compile_status']} | {item['runtime_status']} | "
        f"{item['package_status']} | {item['publication_status']} | {item['support_status']} | "
        f"`{item['evidence_revision'] or '-'}` |"
        for item in data["platforms"]
    )
    return "\n".join(lines)


def release_status(data: dict[str, Any]) -> str:
    return "\n".join([
        "## Current Boundary",
        "",
        f"The accepted non-execution product wave is `{data['completed_wave']['id']}`. "
        f"The exact H1 candidate is `{data['current_revisions']['factorio_launcher']}` and "
        f"the operator verdict remains `{data['execution']['operator_verdict']}`.",
        "",
        f"Execution is `{data['execution']['status']}`; Safe beta is "
        f"`{str(data['safe_beta']).lower()}`; release status is `{data['release']['status']}`; "
        f"authenticity is `{data['release']['authenticity']}`. Green structural, package, or CI "
        "checks do not enlarge those claims.",
    ])


def surface_content(path: Path, data: dict[str, Any]) -> str:
    if path == ROOT / "README.md":
        return readme_status(data)
    if path == ROOT / "docs" / "roadmap.md":
        return roadmap_status(data)
    if path == ROOT / "docs" / "platform" / "support_matrix.md":
        return support_status(data)
    return release_status(data)


def replace_managed(text: str, marker: str, content: str) -> str:
    begin = f"<!-- {marker}:BEGIN -->"
    end = f"<!-- {marker}:END -->"
    if text.count(begin) != 1 or text.count(end) != 1:
        raise ValueError(f"managed section {marker} must have exactly one begin/end pair")
    prefix, remainder = text.split(begin, 1)
    _old, suffix = remainder.split(end, 1)
    return f"{prefix}{begin}\n{content.rstrip()}\n{end}{suffix}"


def rendered_surfaces(data: dict[str, Any]) -> dict[Path, str]:
    return {
        path: replace_managed(
            path.read_text(encoding="utf-8"), marker, surface_content(path, data)
        )
        for path, marker in SURFACES.items()
    }


def validate_status(status: dict[str, Any]) -> list[str]:
    problems = []
    if status.get("schema") != "facman.project_status.v2":
        problems.append("canonical status has the wrong schema")
    if status.get("completed_wave") != "r3.7":
        problems.append("canonical status must record completed R3.7")
    if status.get("next_authority_gate") != "H1":
        problems.append("canonical status must route the next authority gate to H1")
    if status.get("safe_beta") is not False:
        problems.append("canonical status must not promote Safe beta")
    repair_id = "FACMAN-R3.8-STEAM-EXTERNAL-STATE-ISOLATION-REPAIR-01"
    m1_closeout_id = "M1-PUBLIC-INTEGRATION-PROOF-01"
    if status.get("active_work_unit") == repair_id:
        problems.append("closed R3.8 repair must not remain the active WorkUnit")
    if status.get("last_closed_work_unit") != m1_closeout_id:
        problems.append("canonical status must bind the closed M1 WU12 WorkUnit")
    repair = status.get("r3_8_repair", {})
    if repair.get("status") != "closed":
        problems.append("canonical status must record the R3.8 repair as closed")
    if repair.get("operator_verdict") != "Fail":
        problems.append("R3.8 repair closeout must preserve the operator H1 Fail")
    if repair.get("standalone_manual_isolation") != "unproven":
        problems.append("R3.8 repair closeout must keep standalone/manual isolation unproven")
    if repair.get("authority_promotion") is not False:
        problems.append("R3.8 repair closeout must not promote authority")
    integration = status.get("r3_8_public_integration", {})
    if integration.get("status") != "accepted":
        problems.append("canonical status must record accepted R3.8 public integration proof")
    if integration.get("authority_promotion") is not False:
        problems.append("R3.8 public integration proof must not promote authority")
    if not integration.get("main_dev_synchronized_at_proof"):
        problems.append("R3.8 public integration proof must bind synchronized main/dev ancestry")
    m1 = status.get("m1_managed_portable_install", {})
    if m1.get("status") != "fixture_proven":
        problems.append("canonical status must record fixture-proven M1 managed setup")
    if m1.get("ordinary_setup_apply") != "unavailable_pending_live_target_acceptance":
        problems.append("canonical status must keep ordinary setup apply unavailable")
    if m1.get("authority_promotion") is not False:
        problems.append("M1 closeout must not promote execution or live-target authority")
    m1_integration = status.get("m1_public_integration", {})
    if m1_integration.get("status") != "accepted":
        problems.append("canonical status must record accepted M1 public integration proof")
    if m1_integration.get("canonical_main_revision") != status.get("accepted_integration_revision"):
        problems.append("M1 public integration must bind the accepted canonical main revision")
    if m1_integration.get("dev_tree_identity") != m1_integration.get("main_tree_identity"):
        problems.append("M1 dev and main integration trees must be identical")
    if m1_integration.get("checkpoint_tree_identity") != m1_integration.get("main_tree_identity"):
        problems.append("M1 checkpoint and canonical main trees must be identical")
    if not m1_integration.get("main_dev_synchronized_at_proof"):
        problems.append("M1 public integration must bind canonical main ancestry into dev")
    if m1_integration.get("authority_promotion") is not False:
        problems.append("M1 public integration proof must not promote authority")
    licenses = status.get("universal_repository_licenses", {})
    if licenses.get("status") != "accepted_mit":
        problems.append("Universal repository license decision must record accepted MIT")
    if licenses.get("spdx_license_expression") != "MIT":
        problems.append("Universal repository license expression must be MIT")
    if licenses.get("publication_authority") is not False:
        problems.append("Universal repository licensing must not imply publication authority")
    execution = status.get("execution", {})
    if execution.get("status") != "unavailable":
        problems.append("canonical status must keep execution unavailable")
    verdict = execution.get("operator_verdict")
    if verdict not in {"pending", "Fail"}:
        problems.append("canonical status may record only pending or the reviewed H1 Fail before promotion")
    if verdict == "Fail" and not execution.get("proof"):
        problems.append("canonical H1 Fail must bind a sanitized proof record")
    return problems


def validate() -> list[str]:
    problems = validate_status(load_toml(STATUS_PATH))
    data = collect()
    expected_json = json.dumps(data, indent=2, sort_keys=True) + "\n"
    expected_markdown = markdown(data)
    if not JSON_PATH.is_file() or JSON_PATH.read_text(encoding="utf-8") != expected_json:
        problems.append("machine state is stale; run python tools/project_state.py --write")
    if LEGACY_JSON_PATH.exists():
        problems.append("legacy project-state.v1.json remains; project-state.v2.json is authoritative")
    if not MARKDOWN_PATH.is_file() or MARKDOWN_PATH.read_text(encoding="utf-8") != expected_markdown:
        problems.append("human state is stale; run python tools/project_state.py --write")
    try:
        surfaces = rendered_surfaces(data)
    except ValueError as exc:
        problems.append(str(exc))
    else:
        for path, expected in surfaces.items():
            if path.read_text(encoding="utf-8") != expected:
                problems.append(f"{path.relative_to(ROOT)} generated status is stale")
    required_platform_fields = {
        "compile_status",
        "runtime_status",
        "package_status",
        "publication_status",
        "support_status",
        "evidence_revision",
    }
    for platform in load_toml(SUPPORT_PATH).get("platform", []):
        missing = required_platform_fields - set(platform)
        if missing:
            problems.append(
                f"support platform {platform.get('id', '<unknown>')} lacks {sorted(missing)}"
            )
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate FacMan project truth from canonical data.")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    data = collect()
    if args.write:
        JSON_PATH.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        MARKDOWN_PATH.write_text(markdown(data), encoding="utf-8")
        for path, rendered in rendered_surfaces(data).items():
            path.write_text(rendered, encoding="utf-8")
        print("project-state: wrote machine state and generated human surfaces")
        return 0
    problems = validate()
    if problems:
        for problem in problems:
            print(f"project-state: {problem}")
        return 1
    print("project-state: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
