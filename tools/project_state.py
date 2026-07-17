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
        "m2_live_portable_setup": status["m2_live_portable_setup"],
        "m2_wu1_target_policy": status["m2_wu1_target_policy"],
        "m2_wu2_public_lifecycle": status["m2_wu2_public_lifecycle"],
        "m2_wu3_live_evidence": status["m2_wu3_live_evidence"],
        "m2_wu4_live_acceptance": status["m2_wu4_live_acceptance"],
        "m2_wu5_interruption_recovery": status["m2_wu5_interruption_recovery"],
        "m2_wu6_launcher_handoff": status["m2_wu6_launcher_handoff"],
        "m2_wu7_facman_live_portable_workflow": status["m2_wu7_facman_live_portable_workflow"],
        "m2_wu8_generated_frontend_workflow": status["m2_wu8_generated_frontend_workflow"],
        "m2_wu9_cross_platform_adversarial_proof": status["m2_wu9_cross_platform_adversarial_proof"],
        "m2_wu10_operator_live_target_verdict": status["m2_wu10_operator_live_target_verdict"],
        "m2_wu10_automated_acceptance_policy": status["m2_wu10_automated_acceptance_policy"],
        "m2_wu10_automated_acceptance_result_attempt": status["m2_wu10_automated_acceptance_result_attempt"],
        "m2_wu10_machine_acceptance_candidate": status["m2_wu10_machine_acceptance_candidate"],
        "m2_wu10_machine_acceptance_result": status["m2_wu10_machine_acceptance_result"],
        "m2_closeout_candidate": status["m2_closeout_candidate"],
        "m3_existing_portable_adoption": status["m3_existing_portable_adoption"],
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
        f"- M2 live portable setup: `{data['m2_live_portable_setup']['status']}`; "
        f"technical acceptance: `{data['m2_live_portable_setup']['technical_acceptance']}`; "
        f"human review: `{data['m2_live_portable_setup']['human_review']}`; "
        f"ordinary live apply: `{data['m2_live_portable_setup']['ordinary_live_apply']}`.",
        f"- M2-WU1 target policy: `{data['m2_wu1_target_policy']['status']}` at Universal Setup "
        f"main `{data['m2_wu1_target_policy']['universal_setup_main_revision']}`; "
        f"mutation authority: `{str(data['m2_wu1_target_policy']['mutation_authority']).lower()}`.",
        f"- M2-WU2 public lifecycle: `{data['m2_wu2_public_lifecycle']['status']}`; "
        f"operator verdict: `{data['m2_wu2_public_lifecycle']['operator_verdict']}`; "
        f"execution authority: `{str(data['m2_wu2_public_lifecycle']['execution_authority']).lower()}`.",
        f"- M2-WU3 live evidence: `{data['m2_wu3_live_evidence']['status']}` at Universal Setup main "
        f"`{data['m2_wu3_live_evidence']['universal_setup_main_revision']}`; operator verdict: "
        f"`{data['m2_wu3_live_evidence']['operator_verdict']}`; automated verdict authority: "
        f"`{str(data['m2_wu3_live_evidence']['automation_can_record_operator_verdict']).lower()}`.",
        f"- M2-WU4 live acceptance: `{data['m2_wu4_live_acceptance']['status']}` at Universal Setup main "
        f"`{data['m2_wu4_live_acceptance']['universal_setup_main_revision']}`; run: "
        f"`{data['m2_wu4_live_acceptance']['run_id']}`; operator verdict: "
        f"`{data['m2_wu4_live_acceptance']['operator_verdict']}`.",
        f"- M2-WU5 interruption recovery: `{data['m2_wu5_interruption_recovery']['status']}` at Universal Setup main "
        f"`{data['m2_wu5_interruption_recovery']['universal_setup_main_revision']}`; run: "
        f"`{data['m2_wu5_interruption_recovery']['run_id']}`; operator verdict: "
        f"`{data['m2_wu5_interruption_recovery']['operator_verdict']}`.",
        f"- M2-WU6 Launcher handoff: `{data['m2_wu6_launcher_handoff']['status']}` at Universal Launcher main "
        f"`{data['m2_wu6_launcher_handoff']['universal_launcher_main_revision']}`; recovery status: "
        f"`{data['m2_wu6_launcher_handoff']['dependent_instance_status']}`; operator verdict: "
        f"`{data['m2_wu6_launcher_handoff']['operator_verdict']}`.",
        f"- M2-WU7 FacMan portable workflow: `{data['m2_wu7_facman_live_portable_workflow']['status']}`; "
        f"plan: `{data['m2_wu7_facman_live_portable_workflow']['setup_command']}`; apply: "
        f"`{data['m2_wu7_facman_live_portable_workflow']['ordinary_live_apply']}`; operator verdict: "
        f"`{data['m2_wu7_facman_live_portable_workflow']['operator_verdict']}`.",
        f"- M2-WU8 generated frontend workflow: `{data['m2_wu8_generated_frontend_workflow']['status']}`; "
        f"clients: `{', '.join(data['m2_wu8_generated_frontend_workflow']['clients'])}`; apply: "
        f"`{data['m2_wu8_generated_frontend_workflow']['ordinary_live_apply']}`; operator verdict: "
        f"`{data['m2_wu8_generated_frontend_workflow']['operator_verdict']}`.",
        f"- M2-WU9 adversarial proof: `{data['m2_wu9_cross_platform_adversarial_proof']['status']}`; "
        f"cases: `{data['m2_wu9_cross_platform_adversarial_proof']['case_count']}`; Setup main: "
        f"`{data['m2_wu9_cross_platform_adversarial_proof']['universal_setup_main_revision']}`; operator verdict: "
        f"`{data['m2_wu9_cross_platform_adversarial_proof']['operator_verdict']}`.",
        f"- M2-WU10 operator acceptance: `{data['m2_wu10_operator_live_target_verdict']['status']}`; "
        f"run: `{data['m2_wu10_operator_live_target_verdict']['run_id']}`; operator verdict: "
        f"`{data['m2_wu10_operator_live_target_verdict']['operator_verdict']}`.",
        f"- M2-WU10 automated acceptance policy: `{data['m2_wu10_automated_acceptance_policy']['status']}`; "
        f"technical acceptance: `{data['m2_wu10_automated_acceptance_policy']['technical_acceptance']}`; "
        f"human review: `{data['m2_wu10_automated_acceptance_policy']['human_review']}`.",
        f"- M2-WU10 first automated result attempt: "
        f"`{data['m2_wu10_automated_acceptance_result_attempt']['status']}`; verifier: "
        f"`{data['m2_wu10_automated_acceptance_result_attempt']['verifier_result']}`; MachinePass: "
        f"`{str(data['m2_wu10_automated_acceptance_result_attempt']['machine_pass']).lower()}`.",
        f"- M2-WU10 corrected acceptance candidate: "
        f"`{data['m2_wu10_machine_acceptance_candidate']['status']}`; evidence: "
        f"`{data['m2_wu10_machine_acceptance_candidate']['evidence_result']}`; MachinePass: "
        f"`{str(data['m2_wu10_machine_acceptance_candidate']['machine_pass']).lower()}`.",
        f"- M2-WU10 machine acceptance result: "
        f"`{data['m2_wu10_machine_acceptance_result']['status']}`; human review: "
        f"`{data['m2_wu10_machine_acceptance_result']['human_review']}`; managed setup: "
        f"`{data['m2_wu10_machine_acceptance_result']['local_managed_portable_setup']}`.",
        f"- M2 closeout: `{data['m2_closeout_candidate']['status']}`; dev merge: "
        f"`{data['m2_closeout_candidate']['wu10_dev_merge_revision']}`; canonical main: "
        f"`{data['m2_closeout_candidate']['canonical_main_revision']}`.",
        f"- M3 existing-portable adoption: `{data['m3_existing_portable_adoption']['status']}`; "
        f"scope: `{data['m3_existing_portable_adoption']['scope']}`; adoption apply: "
        f"`{str(data['m3_existing_portable_adoption']['adoption_apply']).lower()}`.",
        f"- Universal repository licenses: `{data['universal_repository_licenses']['status']}`; "
        f"publication authority: `{str(data['universal_repository_licenses']['publication_authority']).lower()}`.",
        "",
        "R3.7, M1, and the bounded M2 technical wave are complete. The exact R3.7 runtime is "
        "frozen as the H1 candidate. M2-WU10 records a bounded MachinePass for "
        "newly created policy-approved managed targets. No execution, Safe beta, stable SDK, "
        "daemon, real-Factorio archive, existing-installation, networking, credential, signing, "
        "or publication authority is inferred from that synthetic proof.",
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
    if status.get("completed_wave") != "m2":
        problems.append("canonical status must record completed M2 technical wave")
    if status.get("next_authority_gate") != "H1":
        problems.append("canonical status must route the next authority gate to H1")
    if status.get("safe_beta") is not False:
        problems.append("canonical status must not promote Safe beta")
    repair_id = "FACMAN-R3.8-STEAM-EXTERNAL-STATE-ISOLATION-REPAIR-01"
    latest_wu10_id = "M2-WU10-AUTOMATED-ACCEPTANCE-RESULT-02"
    m2_closeout_id = "M2-CLOSEOUT-CANONICAL-PROMOTION-01"
    if status.get("active_work_unit") == repair_id:
        problems.append("closed R3.8 repair must not remain the active WorkUnit")
    if status.get("active_work_unit") == m2_closeout_id:
        if status.get("last_closed_work_unit") != latest_wu10_id:
            problems.append("active M2 closeout must preserve WU10 as the latest closed WorkUnit")
    elif status.get("active_work_unit"):
        problems.append("only the M2 closeout WorkUnit may be active")
    elif status.get("last_closed_work_unit") != m2_closeout_id:
        problems.append("closed M2 closeout must be the latest closed WorkUnit")
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
    m2 = status.get("m2_live_portable_setup", {})
    if m2.get("status") != "complete_machine_pass_pending_canonical_promotion":
        problems.append("M2 must remain complete with canonical promotion pending")
    if m2.get("technical_acceptance") != "MachinePass":
        problems.append("M2 technical acceptance must record the bounded MachinePass")
    if m2.get("human_review") != "not_required_for_synthetic_non_executable_lane":
        problems.append("M2 synthetic human-review policy changed")
    if m2.get("ordinary_live_apply") != "candidate_within_machine_accepted_policy_scope":
        problems.append("M2 ordinary setup must remain only a bounded MachinePass candidate")
    if m2.get("execution_authority") is not False or m2.get("h1_inference") != "none":
        problems.append("M2 must not promote execution or infer H1")
    closeout = status.get("m2_closeout_candidate", {})
    if [
        closeout.get("status"), closeout.get("work_unit"),
        closeout.get("wu10_pull_request"), closeout.get("wu10_dev_merge_revision"),
        closeout.get("technical_acceptance"), closeout.get("human_review"),
        closeout.get("result_sha256"), closeout.get("canonical_main_revision"),
        closeout.get("local_managed_portable_setup"),
    ] != [
        "machine_pass_closeout_pending_exact_dev_and_main_promotion",
        "M2-CLOSEOUT-CANONICAL-PROMOTION-01", 28,
        "5250db1d17ac330f5ae0b672ccc7466431a1e4a2", "MachinePass",
        "not_required_for_synthetic_non_executable_lane",
        "a4a00a3f77b394f988a71f9eaa86de3c9c9b74a4051d1c2e3ad38f60b9ad8efa",
        "pending_dev_to_main_promotion", "candidate",
    ]:
        problems.append("M2 closeout candidate identity or scope changed")
    if closeout.get("local_validation") not in {"pending_complete_matrix", "pass_complete_matrix"}:
        problems.append("M2 closeout must record a recognized local validation state")
    for key in [
        "factorio_archive_acceptance", "existing_factorio_mutation",
        "existing_installation_adoption", "steam_mutation", "steam_cloud_mutation",
        "network", "credentials", "registry", "shortcuts", "elevation",
        "system_wide_installation", "run_execute", "signing", "publication",
    ]:
        if closeout.get(key) is not False:
            problems.append(f"M2 closeout must keep {key} excluded")
    if closeout.get("h1_inference") != "none":
        problems.append("M2 closeout must not infer H1")
    m3 = status.get("m3_existing_portable_adoption", {})
    if [
        m3.get("status"), m3.get("scope"), m3.get("existing_portable_inspection"),
        m3.get("adoption_plan"), m3.get("adoption_apply"),
        m3.get("deletion_authority"), m3.get("existing_installation_mutation"),
        m3.get("steam_adoption"), m3.get("steam_mutation"), m3.get("run_execute"),
    ] != [
        "authorized_next_wave_pending_m2_canonical_promotion",
        "read_only_and_plan_only", True, True, False, False, False, False, False, False,
    ]:
        problems.append("M3 must remain authorized-next, read-only, and plan-only")
    m2_wu1 = status.get("m2_wu1_target_policy", {})
    if m2_wu1.get("status") != "accepted_dev_integration_proof":
        problems.append("M2-WU1 target policy must record the accepted dev integration proof")
    if m2_wu1.get("mutation_authority") is not False:
        problems.append("M2-WU1 target policy must not grant mutation authority")
    if m2_wu1.get("operator_verdict") != "pending":
        problems.append("M2-WU1 automation must preserve the pending human verdict")
    if m2_wu1.get("execution_authority") is not False or m2_wu1.get("h1_inference") != "none":
        problems.append("M2-WU1 must not promote execution or infer H1")
    m2_wu2 = status.get("m2_wu2_public_lifecycle", {})
    if m2_wu2.get("status") not in {
        "provider_integrated_candidate",
        "implementation_proven_pending_dev_integration",
        "accepted_dev_integration_proof",
    }:
        problems.append("M2-WU2 public lifecycle must record a recognized monotonic proof state")
    if m2_wu2.get("universal_setup_main_revision") != "aa4d8cec93f265893f246d217ee94c03073899a3":
        problems.append("M2-WU2 must preserve its accepted historical Universal Setup main revision")
    if m2_wu2.get("plan_commands_read_only") is not True or m2_wu2.get("apply_requires_exact_plan") is not True:
        problems.append("M2-WU2 must retain read-only planning and exact-plan apply")
    if m2_wu2.get("operator_verdict") != "pending":
        problems.append("M2-WU2 automation must preserve the pending human verdict")
    if m2_wu2.get("recovery_apply") != "unavailable_pending_wu5":
        problems.append("M2-WU2 must not overstate restart-safe recovery apply")
    if m2_wu2.get("execution_authority") is not False or m2_wu2.get("h1_inference") != "none":
        problems.append("M2-WU2 must not promote execution or infer H1")
    m2_wu3 = status.get("m2_wu3_live_evidence", {})
    if m2_wu3.get("status") not in {
        "provider_integrated_candidate",
        "implementation_proven_pending_dev_integration",
        "accepted_dev_integration_proof",
    }:
        problems.append("M2-WU3 live evidence must record a recognized monotonic proof state")
    if m2_wu3.get("status") == "accepted_dev_integration_proof":
        if m2_wu3.get("facman_reviewed_pr") != 16:
            problems.append("M2-WU3 accepted integration must bind reviewed PR 16")
        if m2_wu3.get("facman_task_tree_identity") != m2_wu3.get("facman_dev_tree_identity"):
            problems.append("M2-WU3 task and reviewed dev merge must preserve identical trees")
        for field in (
            "facman_task_head_revision",
            "facman_dev_integration_revision",
            "facman_dev_ci_run",
            "facman_dev_code_security_run",
            "facman_dev_security_policy_run",
        ):
            if not m2_wu3.get(field):
                problems.append(f"M2-WU3 accepted integration must bind {field}")
    if m2_wu3.get("universal_setup_main_revision") != "fbbeb762f25921ae05945206fd0c004a52239c13":
        problems.append("M2-WU3 must preserve its accepted historical Universal Setup revision")
    if m2_wu3.get("operator_verdict") != "pending" or m2_wu3.get("automation_can_record_operator_verdict") is not False:
        problems.append("M2-WU3 automation must preserve a separate pending operator verdict")
    if m2_wu3.get("setup_owned_evidence_write") is not True:
        problems.append("M2-WU3 evidence writes must remain setup-owned")
    if m2_wu3.get("plan_pre_snapshot") is not True or m2_wu3.get("capture_recomputes_post_snapshot") is not True:
        problems.append("M2-WU3 must bind plan pre-state and independently recomputed post-state")
    if m2_wu3.get("ordinary_live_apply") != "unavailable_pending_operator_acceptance":
        problems.append("M2-WU3 must not promote ordinary live apply before a human Pass")
    if m2_wu3.get("execution_authority") is not False or m2_wu3.get("h1_inference") != "none":
        problems.append("M2-WU3 must not promote execution or infer H1")
    m2_wu4 = status.get("m2_wu4_live_acceptance", {})
    if m2_wu4.get("status") not in {
        "provider_integrated_live_run_proven_pending_dev_integration",
        "accepted_dev_integration_proof_pending_operator_verdict",
    }:
        problems.append("M2-WU4 live acceptance must record a recognized monotonic proof state")
    if m2_wu4.get("status") == "accepted_dev_integration_proof_pending_operator_verdict":
        expected_wu4_integration = {
            "facman_reviewed_pr": 18,
            "facman_task_head_revision": "a286b5c42736e1a4189030a51e9b1e5c397552eb",
            "facman_task_tree": "8027f6fe9a54e1b845842934d21fa142895b50f9",
            "facman_dev_integration_revision": "5563e3b8de4363d1d42cc2ba6f5829aed0c7405e",
            "facman_dev_tree": "8027f6fe9a54e1b845842934d21fa142895b50f9",
            "facman_dev_ci_run": "29337542209",
            "facman_dev_code_security_run": "29337541636",
            "facman_dev_security_policy_run": "29337541937",
        }
        if any(m2_wu4.get(key) != value for key, value in expected_wu4_integration.items()):
            problems.append("accepted M2-WU4 integration must bind PR 18, identical trees, and exact-dev workflows")
    if m2_wu4.get("universal_setup_main_revision") != "9b8196437e41e45bd8d5a613246dabe5b8cdb968":
        problems.append("M2-WU4 must preserve its accepted historical Universal Setup revision")
    if m2_wu4.get("universal_setup_runner_revision") != "6209385f25db1824bcbb7ec599cf2152606be89b":
        problems.append("M2-WU4 must bind the exact live runner revision")
    if m2_wu4.get("acceptance_root") != r"D:\FacMan-Live-Acceptance\M2":
        problems.append("M2-WU4 must remain confined to the authorized acceptance root")
    if m2_wu4.get("run_summary_sha256") != "0d42f22f40aa2b92df49b8bd872db9ad2367c5000d615a6d982f25e4ee0a0507":
        problems.append("M2-WU4 must bind the retained live summary identity")
    if m2_wu4.get("evidence_packet_count") != 4 or m2_wu4.get("journal_count") != 4:
        problems.append("M2-WU4 must bind four operation packets and four completed journals")
    if m2_wu4.get("native_test_count") != 39 or m2_wu4.get("python_test_count") != 339:
        problems.append("M2-WU4 must bind the complete local native and Python proof counts")
    if m2_wu4.get("required_windows_package_tests") != 14 or m2_wu4.get("required_windows_package_skips") != 0:
        problems.append("M2-WU4 must bind the required zero-skip Windows package proof")
    if m2_wu4.get("synthetic_archive_contains_executable_code") is not False:
        problems.append("M2-WU4 autonomous archive must remain non-executable synthetic content")
    if m2_wu4.get("cross_volume_move") != "not_attempted_no_second_authorized_volume":
        problems.append("M2-WU4 must not overstate cross-volume proof")
    if m2_wu4.get("operator_verdict") != "pending" or m2_wu4.get("automation_can_record_operator_verdict") is not False:
        problems.append("M2-WU4 automation must preserve a separate pending operator verdict")
    if m2_wu4.get("ordinary_live_apply") != "unavailable_pending_operator_acceptance":
        problems.append("M2-WU4 must not promote ordinary live apply before a human Pass")
    if m2_wu4.get("recovery_apply") != "unavailable_pending_wu5":
        problems.append("M2-WU4 must not promote recovery apply before WU5")
    if m2_wu4.get("execution_authority") is not False or m2_wu4.get("h1_inference") != "none":
        problems.append("M2-WU4 must not promote execution or infer H1")
    m2_wu5 = status.get("m2_wu5_interruption_recovery", {})
    if m2_wu5.get("status") not in {
        "provider_integrated_live_run_proven_pending_dev_integration",
        "accepted_dev_integration_proof_pending_operator_verdict",
    }:
        problems.append("M2-WU5 interruption recovery must record a recognized monotonic proof state")
    if m2_wu5.get("status") == "accepted_dev_integration_proof_pending_operator_verdict":
        expected_wu5_integration = {
            "facman_reviewed_pr": 19,
            "facman_task_head_revision": "a6cfe28c704df68025094f29be85f8961f745cd1",
            "facman_task_tree": "0bc4e45755a3547b2d6ccde68a1693e2c970ee67",
            "facman_dev_integration_revision": "f4b02ac022ee676ca5fdd5d8f31b44709a2c3277",
            "facman_dev_tree": "0bc4e45755a3547b2d6ccde68a1693e2c970ee67",
            "facman_dev_ci_run": "29341098765",
            "facman_dev_code_security_run": "29341101347",
            "facman_dev_security_policy_run": "29341100659",
        }
        if any(m2_wu5.get(key) != value for key, value in expected_wu5_integration.items()):
            problems.append("accepted M2-WU5 integration must bind PR 19, identical trees, and exact-dev workflows")
    if m2_wu5.get("universal_setup_main_revision") != "e1ce68e9593ae8d9a35cc0821b5e42c798524453":
        problems.append("M2-WU5 must retain its exact historical Universal Setup provider pin")
    if m2_wu5.get("acceptance_root") != r"D:\FacMan-Live-Acceptance\M2":
        problems.append("M2-WU5 must remain confined to the authorized acceptance root")
    if m2_wu5.get("run_summary_sha256") != "c64ddfaa38bde351002d2840999b3ba74173cde8c76d3e6aa21891b5d169f6c1":
        problems.append("M2-WU5 must bind the retained interruption summary identity")
    if [m2_wu5.get(key) for key in ("case_count", "unchanged_count", "rolled_back_count", "completed_count", "recovery_required_count")] != [11, 1, 4, 3, 3]:
        problems.append("M2-WU5 must bind the complete eleven-case outcome partition")
    if m2_wu5.get("native_test_count") != 40 or m2_wu5.get("python_test_count") != 339:
        problems.append("M2-WU5 must bind the complete local native and Python proof counts")
    if m2_wu5.get("required_windows_package_tests") != 14 or m2_wu5.get("required_windows_package_skips") != 0:
        problems.append("M2-WU5 must bind the required zero-skip Windows package proof")
    if m2_wu5.get("public_recovery_apply") != "exact_staged_rollback_only":
        problems.append("M2-WU5 must not overstate public recovery apply")
    if m2_wu5.get("operator_verdict") != "pending" or m2_wu5.get("automation_can_record_operator_verdict") is not False:
        problems.append("M2-WU5 automation must preserve a separate pending operator verdict")
    if m2_wu5.get("ordinary_live_apply") != "unavailable_pending_operator_acceptance":
        problems.append("M2-WU5 must not promote ordinary live apply before a human Pass")
    if m2_wu5.get("execution_authority") is not False or m2_wu5.get("h1_inference") != "none":
        problems.append("M2-WU5 must not promote execution or infer H1")
    m2_wu6 = status.get("m2_wu6_launcher_handoff", {})
    if m2_wu6.get("status") not in {
        "provider_integrated_local_handoff_proven_pending_dev_integration",
        "accepted_dev_integration_proof_pending_operator_verdict",
    }:
        problems.append("M2-WU6 Launcher handoff must record a recognized monotonic proof state")
    if m2_wu6.get("universal_launcher_main_revision") != provider_pins()["universal_launcher"]["revision"]:
        problems.append("M2-WU6 must bind the exact current Universal Launcher provider pin")
    if m2_wu6.get("launcher_abi_version") != "1.3" or m2_wu6.get("facman_binding_abi_version") != "1.3":
        problems.append("M2-WU6 must bind the additive Launcher and FacMan ABI 1.3 integration")
    if m2_wu6.get("recovery_without_install_reference") is not True:
        problems.append("M2-WU6 must preserve recovery-required state before an install reference exists")
    if m2_wu6.get("dependent_instance_status") != "managed_install_recovery_required" or m2_wu6.get("launch_plan_status") != "stale":
        problems.append("M2-WU6 must expose structured recovery status and stale launch plans")
    if m2_wu6.get("launcher_can_mutate_setup") is not False or m2_wu6.get("setup_mutation_owner") != "universal-setup":
        problems.append("M2-WU6 must keep setup mutation authority outside Universal Launcher")
    if m2_wu6.get("native_test_count") != 41 or m2_wu6.get("python_test_count") != 339:
        problems.append("M2-WU6 must bind the complete local native and Python proof counts")
    if m2_wu6.get("required_windows_package_tests") != 14 or m2_wu6.get("required_windows_package_skips") != 0:
        problems.append("M2-WU6 must bind the required zero-skip Windows package proof")
    if m2_wu6.get("package_tree_file_count") != 390:
        problems.append("M2-WU6 must bind the complete reproducible selected package tree")
    if m2_wu6.get("operator_verdict") != "pending" or m2_wu6.get("automation_can_record_operator_verdict") is not False:
        problems.append("M2-WU6 automation must preserve a separate pending operator verdict")
    if m2_wu6.get("ordinary_live_apply") != "unavailable_pending_operator_acceptance":
        problems.append("M2-WU6 must not promote ordinary live apply before a human Pass")
    if m2_wu6.get("execution_authority") is not False or m2_wu6.get("h1_inference") != "none":
        problems.append("M2-WU6 must not promote execution or infer H1")
    m2_wu7 = status.get("m2_wu7_facman_live_portable_workflow", {})
    if m2_wu7.get("status") not in {
        "provider_integrated_local_plan_proven_pending_dev_integration_and_operator_verdict",
        "accepted_dev_integration_proof_pending_operator_verdict",
    }:
        problems.append("M2-WU7 FacMan workflow must record a recognized monotonic proof state")
    if m2_wu7.get("status") == "accepted_dev_integration_proof_pending_operator_verdict":
        expected_integration = {
            "facman_task_head_revision": "1b029ead969e3b68387fcbaef71458ba99f0c33e",
            "facman_task_tree": "a638e5d078a28751fa12ede205b48595986e5b0f",
            "facman_pull_request": 21,
            "facman_dev_integration_revision": "37c83c6538822a57bf96e03f03c48536f2b97e47",
            "facman_dev_tree": "a638e5d078a28751fa12ede205b48595986e5b0f",
            "facman_dev_ci_run": "29347961199",
            "facman_dev_codeql_run": "29347961372",
            "facman_dev_security_policy_run": "29347960097",
        }
        if any(m2_wu7.get(key) != value for key, value in expected_integration.items()):
            problems.append("M2-WU7 accepted dev integration proof must bind exact immutable task, tree, PR, and workflow identities")
    if m2_wu7.get("universal_setup_revision") != "e1ce68e9593ae8d9a35cc0821b5e42c798524453" or m2_wu7.get("universal_launcher_revision") != "7bd4425f0c35414f738159b45d8bec42edf70235":
        problems.append("M2-WU7 must retain its exact historical Universal provider pins")
    if m2_wu7.get("setup_command") != "install_local.plan" or m2_wu7.get("target_class") != "operator_acceptance":
        problems.append("M2-WU7 must route the bounded operator-acceptance install plan")
    if m2_wu7.get("plan_is_read_only") is not True or m2_wu7.get("plan_binds_source_recipe_target_and_provider") is not True:
        problems.append("M2-WU7 must bind a read-only complete provider plan")
    if m2_wu7.get("default_refusal") != "live_target_acceptance_required" or m2_wu7.get("apply_refusal") != "live_target_acceptance_required" or m2_wu7.get("apply_enabled") is not False:
        problems.append("M2-WU7 must keep every apply behind the human live-target gate")
    if m2_wu7.get("native_test_count") != 41 or m2_wu7.get("python_test_count") != 339:
        problems.append("M2-WU7 must bind the complete native and Python proof counts")
    if m2_wu7.get("required_windows_package_tests") != 14 or m2_wu7.get("required_windows_package_skips") != 0:
        problems.append("M2-WU7 must bind the required zero-skip Windows package proof")
    if m2_wu7.get("package_tree_file_count") != 391:
        problems.append("M2-WU7 must bind the complete reproducible selected package tree")
    if m2_wu7.get("operator_verdict") != "pending" or m2_wu7.get("automation_can_record_operator_verdict") is not False:
        problems.append("M2-WU7 automation must preserve a separate pending operator verdict")
    if m2_wu7.get("ordinary_live_apply") != "unavailable_pending_operator_acceptance":
        problems.append("M2-WU7 must not promote ordinary live apply before a human Pass")
    if m2_wu7.get("execution_authority") is not False or m2_wu7.get("h1_inference") != "none":
        problems.append("M2-WU7 must not promote execution or infer H1")
    m2_wu8 = status.get("m2_wu8_generated_frontend_workflow", {})
    if m2_wu8.get("status") not in {
        "four_frontend_workflow_proven_pending_dev_integration_and_operator_verdict",
        "four_frontend_workflow_and_package_proven_pending_dev_integration_and_operator_verdict",
        "accepted_dev_integration_proof_pending_operator_verdict",
    }:
        problems.append("M2-WU8 must record a recognized monotonic workflow proof state")
    if m2_wu8.get("workflow_schema") != "facman.setup_workflow.v1" or m2_wu8.get("workflow_id") != "live_portable_setup":
        problems.append("M2-WU8 must bind the canonical generated setup workflow")
    if m2_wu8.get("implementation_revision") != "991ff78c5cc349dfcd8400f585d319b830d2c922":
        problems.append("M2-WU8 must bind the exact generated workflow implementation revision")
    if m2_wu8.get("policy_owner") != "universal-setup" or m2_wu8.get("frontend_policy") is not False:
        problems.append("M2-WU8 must keep mutation policy out of every frontend")
    if m2_wu8.get("clients") != ["cli", "tui", "winforms", "appkit"]:
        problems.append("M2-WU8 must bind the four generated client consumers")
    if m2_wu8.get("workflow_step_count") != 10 or m2_wu8.get("always_visible_field_count") != 4 or m2_wu8.get("warning_count") != 4:
        problems.append("M2-WU8 must preserve the complete reviewed sequence, visible identities, and warnings")
    if m2_wu8.get("confirmation_literal") != "APPLY" or m2_wu8.get("recovery_required_is_distinct") is not True:
        problems.append("M2-WU8 must label exact confirmation and recovery-required state")
    if m2_wu8.get("apply_refusal") != "live_target_acceptance_required" or m2_wu8.get("apply_enabled") is not False:
        problems.append("M2-WU8 must keep live apply behind the human acceptance gate")
    if m2_wu8.get("native_test_count") != 41 or m2_wu8.get("python_test_count") != 340 or m2_wu8.get("python_opt_in_skip_count") != 1:
        problems.append("M2-WU8 must bind the complete local native and Python proof counts")
    if m2_wu8.get("status") in {
        "four_frontend_workflow_and_package_proven_pending_dev_integration_and_operator_verdict",
        "accepted_dev_integration_proof_pending_operator_verdict",
    }:
        if m2_wu8.get("validation_remediation_revision") != "d59d22a27b088e75931eb3ff8005e59a20ff806e":
            problems.append("M2-WU8 must bind the supervision deadline remediation revision")
        if m2_wu8.get("required_windows_package_tests") != 14 or m2_wu8.get("required_windows_package_skips") != 0:
            problems.append("M2-WU8 must bind the required zero-skip Windows package proof")
        if m2_wu8.get("package_proof_revision") != "d59d22a27b088e75931eb3ff8005e59a20ff806e" or m2_wu8.get("package_tree_file_count") != 392:
            problems.append("M2-WU8 must bind the clean selected package source and complete tree")
    if m2_wu8.get("operator_verdict") != "pending" or m2_wu8.get("automation_can_record_operator_verdict") is not False:
        problems.append("M2-WU8 automation must preserve the separate pending operator verdict")
    if m2_wu8.get("ordinary_live_apply") != "unavailable_pending_operator_acceptance":
        problems.append("M2-WU8 must not promote ordinary live apply before a human Pass")
    if m2_wu8.get("execution_authority") is not False or m2_wu8.get("h1_inference") != "none":
        problems.append("M2-WU8 must not promote execution or infer H1")
    m2_wu9 = status.get("m2_wu9_cross_platform_adversarial_proof", {})
    if m2_wu9.get("status") not in {
        "active",
        "provider_integrated_cross_platform_proof_pending_facman_dev_integration_and_operator_verdict",
        "facman_local_proof_passed_pending_dev_integration_and_operator_verdict",
        "accepted_dev_integration_proof_pending_operator_verdict",
    }:
        problems.append("M2-WU9 must record a recognized monotonic adversarial proof state")
    if m2_wu9.get("universal_setup_main_revision") != provider_pins()["universal_setup"]["revision"]:
        problems.append("M2-WU9 must bind the exact current Universal Setup provider pin")
    if m2_wu9.get("universal_setup_task_tree") != m2_wu9.get("universal_setup_main_tree"):
        problems.append("M2-WU9 reviewed Setup task and main merge trees must be identical")
    if [m2_wu9.get("case_count"), m2_wu9.get("setup_owned_case_count"), m2_wu9.get("consumer_case_count")] != [16, 15, 1]:
        problems.append("M2-WU9 must bind the complete sixteen-case ownership partition")
    if m2_wu9.get("required_platforms") != ["windows", "linux", "macos"]:
        problems.append("M2-WU9 must require Windows, Linux, and macOS evidence")
    if m2_wu9.get("target_ancestor_identity_bound") is not True:
        problems.append("M2-WU9 must retain the target ancestor identity remediation")
    if m2_wu9.get("status") in {
        "facman_local_proof_passed_pending_dev_integration_and_operator_verdict",
        "accepted_dev_integration_proof_pending_operator_verdict",
    }:
        if m2_wu9.get("facman_native_test_count") != 41 or m2_wu9.get("facman_python_test_count") != 344:
            problems.append("M2-WU9 must bind the complete local native and Python proof counts")
        if m2_wu9.get("python_opt_in_skip_count") != 1:
            problems.append("M2-WU9 must retain the explicit opt-in performance skip count")
        if m2_wu9.get("required_windows_package_tests") != 14 or m2_wu9.get("required_windows_package_skips") != 0:
            problems.append("M2-WU9 must bind the required zero-skip Windows package proof")
        if m2_wu9.get("facman_hosted_ci_remediation_revision") != "77a39becc55109240abd3ee38227ded666a883fe":
            problems.append("M2-WU9 must bind the Windows checkout identity remediation")
        if m2_wu9.get("package_proof_revision") != "77a39becc55109240abd3ee38227ded666a883fe" or m2_wu9.get("package_tree_file_count") != 395:
            problems.append("M2-WU9 must bind its exact clean package source and complete tree")
        if m2_wu9.get("publisher_authenticity") != "not_proven":
            problems.append("M2-WU9 must not infer publisher authenticity from reproducibility")
    if m2_wu9.get("status") == "accepted_dev_integration_proof_pending_operator_verdict":
        if m2_wu9.get("facman_reviewed_pr") != 23:
            problems.append("M2-WU9 must bind reviewed FacMan PR 23")
        if m2_wu9.get("facman_task_tree") != m2_wu9.get("facman_dev_integration_tree"):
            problems.append("M2-WU9 task and dev integration trees must be identical")
        if [
            m2_wu9.get("dev_ci_run"),
            m2_wu9.get("dev_code_security_run"),
            m2_wu9.get("dev_security_policy_run"),
            m2_wu9.get("dev_schema_check_run"),
        ] != ["29361218441", "29361218988", "29361218569", "29361219348"]:
            problems.append("M2-WU9 must bind the complete successful exact-dev workflow set")
    if m2_wu9.get("operator_verdict") != "pending" or m2_wu9.get("automation_can_record_operator_verdict") is not False:
        problems.append("M2-WU9 automation must preserve the separate pending operator verdict")
    if m2_wu9.get("ordinary_live_apply") != "unavailable_pending_operator_acceptance":
        problems.append("M2-WU9 must not promote ordinary live apply before a human Pass")
    if m2_wu9.get("execution_authority") is not False or m2_wu9.get("h1_inference") != "none":
        problems.append("M2-WU9 must not promote execution or infer H1")
    m2_wu10 = status.get("m2_wu10_operator_live_target_verdict", {})
    if m2_wu10.get("status") not in {
        "historical_machine_evidence_ready_pending_operator_verdict",
        "operator_verdict_recorded",
    }:
        problems.append("M2-WU10 must record a recognized operator-acceptance state")
    if m2_wu10.get("acceptance_root") != r"D:\FacMan-Live-Acceptance\M2":
        problems.append("M2-WU10 must bind only the authorized acceptance root")
    if m2_wu10.get("universal_setup_main_revision") != provider_pins()["universal_setup"]["revision"]:
        problems.append("M2-WU10 must bind the exact current Universal Setup provider pin")
    if m2_wu10.get("verdict_choices") != ["Pass", "Fail", "Inconclusive"]:
        problems.append("M2-WU10 must expose the complete human verdict set")
    if m2_wu10.get("record_schema") != "factorio.m2_operator_acceptance_record.v1":
        problems.append("M2-WU10 must bind the reviewed acceptance record contract")
    if [
        m2_wu10.get("lifecycle_step_count"),
        m2_wu10.get("evidence_packet_count"),
        m2_wu10.get("retained_file_count"),
        m2_wu10.get("retained_directory_count"),
        m2_wu10.get("retained_total_bytes"),
        m2_wu10.get("retained_reparse_point_count"),
    ] != [10, 4, 26, 14, 40105, 0]:
        problems.append("M2-WU10 must bind the complete retained lifecycle tree")
    if [m2_wu10.get("audit_event_count"), m2_wu10.get("final_committed_closure"), m2_wu10.get("final_recovery_status")] != [5, "removed", "not_required"]:
        problems.append("M2-WU10 must bind the final audit, closure, and recovery state")
    if [m2_wu10.get("old_root"), m2_wu10.get("current_root")] != ["retained_for_review", "removed_by_clean_uninstall"]:
        problems.append("M2-WU10 must preserve the reviewed move and uninstall result")
    if [m2_wu10.get("interruption_run_id"), m2_wu10.get("interruption_case_count")] != ["m2wu5-20260714-01", 11]:
        problems.append("M2-WU10 must include the accepted interruption and recovery proof")
    if [m2_wu10.get("native_test_count"), m2_wu10.get("python_test_count"), m2_wu10.get("python_opt_in_skip_count"), m2_wu10.get("schema_count")] != [41, 345, 1, 231]:
        problems.append("M2-WU10 must bind the complete local native, Python, and schema proof counts")
    if m2_wu10.get("hosted_validation_revision") != "980d5b9e3113a673782d6efde74291b0c477f14b" or m2_wu10.get("draft_pull_request") != 25:
        problems.append("M2-WU10 must bind the reviewed draft and exact hosted validation revision")
    if [
        m2_wu10.get("task_push_ci_run"),
        m2_wu10.get("task_push_code_security_run"),
        m2_wu10.get("task_push_security_policy_run"),
        m2_wu10.get("task_push_schema_check_run"),
        m2_wu10.get("task_pr_ci_run"),
        m2_wu10.get("task_pr_code_security_run"),
        m2_wu10.get("task_pr_security_policy_run"),
        m2_wu10.get("task_pr_schema_check_run"),
    ] != [
        "29364492582", "29364492665", "29364491886", "29364492053",
        "29364494313", "29364495679", "29364495081", "29364494922",
    ]:
        problems.append("M2-WU10 must bind the complete successful push and PR workflow sets")
    if m2_wu10.get("automation_can_record_operator_verdict") is not False:
        problems.append("M2-WU10 automation must not record the operator verdict")
    if m2_wu10.get("operator_verdict") == "pending" and m2_wu10.get("ordinary_live_apply") != "unavailable_pending_operator_acceptance":
        problems.append("M2-WU10 pending review must keep ordinary live apply unavailable")
    if m2_wu10.get("execution_authority") is not False or m2_wu10.get("h1_inference") != "none":
        problems.append("M2-WU10 must not promote execution or infer H1")
    machine_policy = status.get("m2_wu10_automated_acceptance_policy", {})
    if [
        machine_policy.get("status"), machine_policy.get("active_work_unit"),
        machine_policy.get("policy_id"), machine_policy.get("technical_acceptance"),
        machine_policy.get("human_review"), machine_policy.get("negative_control_count"),
    ] != [
        "accepted_corrected_policy_with_bound_machine_pass",
        "",
        "facman.m2.synthetic_portable_acceptance.v1",
        "MachinePass",
        "not_required_for_synthetic_non_executable_lane", 12,
    ]:
        problems.append("M2-WU10 automated policy must remain frozen and bind MachinePass separately")
    if [
        machine_policy.get("policy_schema"), machine_policy.get("observation_schema"),
        machine_policy.get("result_schema"), machine_policy.get("accepted_policy_revision"),
    ] != [
        "factorio.m2_synthetic_portable_acceptance_policy.v1",
        "factorio.m2_machine_acceptance_observation.v1",
        "factorio.m2_machine_acceptance_result.v1",
        "7a3f812ab0f81fb35e2e6104bd573d8832a44e59",
    ]:
        problems.append("M2-WU10 automated policy schema or revision separation changed")
    if machine_policy.get("fresh_lifecycle_rerun_required") or machine_policy.get("fresh_interruption_rerun_required"):
        problems.append("M2-WU10 corrected fresh reruns must be complete before the candidate")
    if machine_policy.get("ordinary_live_apply") != "candidate_within_machine_accepted_policy_scope" or machine_policy.get("local_managed_portable_setup") != "candidate":
        problems.append("M2-WU10 MachinePass must promote only bounded managed-setup candidacy")
    for key in [
        "factorio_archive_acceptance", "existing_factorio_mutation", "steam_mutation",
        "network", "registry", "elevation", "run_execute", "publication",
    ]:
        if machine_policy.get(key) is not False:
            problems.append(f"M2-WU10 policy-only revision must keep {key} excluded")
    if machine_policy.get("h1_inference") != "none":
        problems.append("M2-WU10 policy-only revision must not infer H1")
    if machine_policy.get("correction_revision") != "26eb7056984b42859e377c1ffd0ffb7c80488078":
        problems.append("M2-WU10 native-journal correction revision changed")
    if [
        machine_policy.get("accepted_policy_head_revision"), machine_policy.get("accepted_policy_pr"),
        machine_policy.get("accepted_policy_push_ci_run"), machine_policy.get("accepted_policy_pr_ci_run"),
    ] != [
        "7847b506a93d719c42d45d11cd145083e425b8a9", 26,
        "29556764607", "29556778901",
    ]:
        problems.append("M2-WU10 accepted policy merge or hosted proof identity changed")
    result_attempt = status.get("m2_wu10_automated_acceptance_result_attempt", {})
    if [
        result_attempt.get("status"), result_attempt.get("policy_revision"),
        result_attempt.get("runner_revision"), result_attempt.get("verifier_result"),
        result_attempt.get("observation_written"), result_attempt.get("machine_pass"),
        result_attempt.get("authority_promotion"),
    ] != [
        "blocked_before_evidence_pass", "7a3f812ab0f81fb35e2e6104bd573d8832a44e59",
        "3f8489275077347c2918f3bb03614ec6431362ff", "fail_closed",
        False, False, False,
    ]:
        problems.append("M2-WU10 blocked result attempt must remain non-accepting")
    candidate = status.get("m2_wu10_machine_acceptance_candidate", {})
    if [
        candidate.get("status"), candidate.get("policy_revision"),
        candidate.get("runner_revision"), candidate.get("verifier_revision"),
        candidate.get("run_id"), candidate.get("evidence_result"),
        candidate.get("machine_pass"), candidate.get("authority_promotion"),
    ] != [
        "hosted_validation_passed_bound_to_separate_machine_result",
        "26eb7056984b42859e377c1ffd0ffb7c80488078",
        "3f8489275077347c2918f3bb03614ec6431362ff",
        "26eb7056984b42859e377c1ffd0ffb7c80488078",
        "m2wu10-20260717-02", "EvidencePass", False, False,
    ]:
        problems.append("M2-WU10 candidate must remain a separately validated EvidencePass without authority")
    if candidate.get("observation_sha256") != "fb0fcb58eec795d45a56cb48773d74ed74a38d4b14834a4921c1542310777181":
        problems.append("M2-WU10 candidate observation identity changed")
    if [
        candidate.get("candidate_revision"), candidate.get("pull_request"),
        candidate.get("hosted_validation"), candidate.get("pr_ci_run"),
    ] != [
        "ff883cd7b88dda07c0a336ced267cbe1f9f2746f", 28,
        "pass_exact_candidate_revision", "29562194145",
    ]:
        problems.append("M2-WU10 candidate hosted-validation binding changed")
    machine_result = status.get("m2_wu10_machine_acceptance_result", {})
    if [
        machine_result.get("status"), machine_result.get("policy_revision"),
        machine_result.get("runner_revision"), machine_result.get("verifier_revision"),
        machine_result.get("candidate_revision"), machine_result.get("pull_request"),
        machine_result.get("result_sha256"), machine_result.get("human_review"),
        machine_result.get("local_managed_portable_setup"),
    ] != [
        "MachinePass", "26eb7056984b42859e377c1ffd0ffb7c80488078",
        "3f8489275077347c2918f3bb03614ec6431362ff",
        "26eb7056984b42859e377c1ffd0ffb7c80488078",
        "ff883cd7b88dda07c0a336ced267cbe1f9f2746f", 28,
        "a4a00a3f77b394f988a71f9eaa86de3c9c9b74a4051d1c2e3ad38f60b9ad8efa",
        "not_required_for_synthetic_non_executable_lane", "candidate",
    ]:
        problems.append("M2-WU10 MachinePass identity or bounded authority changed")
    for key in [
        "factorio_archive_acceptance", "existing_factorio_mutation",
        "existing_installation_adoption", "steam_mutation", "steam_cloud_mutation",
        "network", "credentials", "registry", "shortcuts", "elevation",
        "system_wide_installation", "run_execute", "signing", "publication",
    ]:
        if machine_result.get(key) is not False:
            problems.append(f"M2-WU10 MachinePass must keep {key} excluded")
    if machine_result.get("h1_inference") != "none":
        problems.append("M2-WU10 MachinePass must not infer H1")
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
