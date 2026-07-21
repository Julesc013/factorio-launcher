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
CAPABILITY_PATH = ROOT / "contracts" / "policy" / "capabilities.v1.toml"
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


def capability_state() -> list[dict[str, Any]]:
    policy = load_toml(CAPABILITY_PATH)
    return sorted(policy.get("capability", []), key=lambda item: str(item.get("id", "")))


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
        "product": status["product"],
        "readiness": status["readiness"],
        "execution_foundation": status["execution_foundation"],
        "instance_product_program": status["instance_product_program"],
        "operation_permit_program": status["operation_permit_program"],
        "gate3_operation_permit_closeout": status["gate3_operation_permit_closeout"],
        "gate3_public_integration": status["gate3_public_integration"],
        "host_environment_program": status["host_environment_program"],
        "multi_version_install_lifecycle": status["multi_version_install_lifecycle"],
        "gate2_instance_spec_and_readiness_closeout": status["gate2_instance_spec_and_readiness_closeout"],
        "gate1_installation_model_v2_readonly_closeout": status["gate1_installation_model_v2_readonly_closeout"],
        "gate0_product_convergence_integration": status["gate0_product_convergence_integration"],
        "execution_modes": status["execution_mode"],
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
        "capabilities": capability_state(),
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
            "Historical milestone evidence does not select the current product objective.",
        ],
    }


def historical_markdown(data: dict[str, Any]) -> str:
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
        f"- product phase: `{data['product']['phase']}` / `{data['product']['phase_status']}`;",
        f"- product charter: {data['product']['charter']}",
        f"- primary persona: {data['product']['primary_persona']}",
        f"- golden journey: `{data['product']['golden_journey']}`;",
        f"- product version: `{data['product_version']}`;",
        f"- checkpoint: `{data['current_checkpoint']}`;",
        f"- active WorkUnit: `{data['active_work_unit'] or 'none'}`;",
        f"- next WorkUnit: `{data['product']['next_work_unit']}`;",
        f"- last closed WorkUnit: `{data['last_closed_work_unit'] or 'none'}`;",
        f"- next authority gate: `{data['next_authority_gate']}`;",
        f"- execution: `{data['execution']['status']}` / `{data['execution']['reason']}`;",
        f"- Safe beta: `{str(data['safe_beta']).lower()}`;",
        f"- release: `{data['release']['status']}` / `{data['release']['authenticity']}`.",
        "",
        "## Readiness dimensions",
        "",
        *[f"- {name.replace('_', ' ')}: `{value}`;" for name, value in data["readiness"].items()],
        "",
        "## Execution guarantees",
        "",
        *[
            f"- `{mode['id']}`: product mode `{mode['product_mode']}`, claim `{mode['claim_status']}`; "
            f"next gate `{mode['next_gate']}`. {mode['boundary']}"
            for mode in data["execution_modes"]
        ],
        "",
        "## Historical proof context",
        "",
        f"- completed technical wave: `{data['completed_wave']['id']}`;",
        f"- historical H1 candidate: `{revisions['factorio_launcher']}`;",
        f"- accepted integration evidence: `{revisions['accepted_integration']}`;",
        f"- Universal Launcher pin: `{revisions['universal_launcher']}`;",
        f"- Universal Setup pin: `{revisions['universal_setup']}`;",
        f"- historical Steam-backed H1 operator verdict: `{data['execution']['operator_verdict']}`;",
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
        "R3.7, M1, and the bounded M2 technical wave are historical proof, not the active roadmap. "
        "M2-WU10 records a bounded MachinePass for "
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


def markdown(data: dict[str, Any]) -> str:
    law = data["command_law"]
    validation = data["validation"]
    revisions = data["current_revisions"]
    lines = [
        "# FacMan Project State",
        "",
        "Generated from `release/index/project_status.v2.toml`, the workspace lock,",
        "the command/refusal registries, capability policy, and support matrix.",
        "Edit canonical inputs, then run `py -3 tools/project_state.py --write`.",
        "",
        "## Current product truth",
        "",
        f"- phase: `{data['product']['phase']}` / `{data['product']['phase_status']}`;",
        f"- charter: {data['product']['charter']}",
        f"- persona: {data['product']['primary_persona']}",
        f"- golden journey: `{data['product']['golden_journey']}`;",
        f"- checkpoint: `{data['current_checkpoint']}`;",
        f"- active WorkUnit: `{data['active_work_unit'] or 'none'}`;",
        f"- next WorkUnit: `{data['product']['next_work_unit']}`;",
        f"- next authority gate: `{data['next_authority_gate']}`;",
        f"- truth scope: `{data['product']['truth_scope']}`; canonical integration: "
        f"`{str(data['product']['canonical_integration']).lower()}`; local counts promoted: "
        f"`{str(data['product']['local_counts_promoted']).lower()}`;",
        f"- Gate 0 integration: `{data['gate0_product_convergence_integration']['status']}` at dev "
        f"`{data['gate0_product_convergence_integration']['dev_integration_revision']}`;",
        f"- Gate 1 installation closeout: "
        f"`{data['gate1_installation_model_v2_readonly_closeout']['status']}` at dev "
        f"`{data['gate1_installation_model_v2_readonly_closeout']['dev_integration_revision']}`;",
        f"- Gate 2 instance closeout: "
        f"`{data['gate2_instance_spec_and_readiness_closeout']['status']}` at dev "
        f"`{data['gate2_instance_spec_and_readiness_closeout']['final_dev_revision']}`;",
        f"- Gate 3 permit closeout: "
        f"`{data['gate3_operation_permit_closeout']['status']}` at dev "
        f"`{data['gate3_operation_permit_closeout']['dev_integration_revision']}`;",
        f"- Gates 0-3 canonical integration: "
        f"`{data['gate3_public_integration']['status']}` at main "
        f"`{data['gate3_public_integration']['canonical_main_revision']}` and synchronized dev "
        f"`{data['gate3_public_integration']['final_dev_revision']}`;",
        f"- execution: `{data['execution']['status']}` / `{data['execution']['reason']}`;",
        f"- Safe beta: `{str(data['safe_beta']).lower()}`;",
        f"- release: `{data['release']['status']}` / `{data['release']['authenticity']}`.",
        "",
        "## Readiness dimensions",
        "",
        *[f"- {name.replace('_', ' ')}: `{value}`;" for name, value in data["readiness"].items()],
        "",
        "## Execution guarantees",
        "",
        *[
            f"- `{mode['id']}`: product mode `{mode['product_mode']}`, claim "
            f"`{mode['claim_status']}`, next gate `{mode['next_gate']}`. {mode['boundary']}"
            for mode in data["execution_modes"]
        ],
        "",
        "## Instance product programme",
        "",
        f"- status: `{data['instance_product_program']['status']}`;",
        f"- active WorkUnit: `{data['instance_product_program']['work_unit']}`;",
        f"- next WorkUnit: `{data['instance_product_program']['next_work_unit']}`;",
        f"- portable record: `{data['instance_product_program']['portable_record']}`;",
        f"- machine-local record: `{data['instance_product_program']['machine_local_record']}`;",
        f"- readiness: `{data['instance_product_program']['readiness_model']}`;",
        f"- preparation: `{data['instance_product_program']['preparation_model']}`;",
        f"- default launch intent: `{data['instance_product_program']['default_launch_intent']}`;",
        f"- launch intents: `{', '.join(data['instance_product_program']['launch_intents'])}`;",
        f"- save role: `{data['instance_product_program']['save_role']}`;",
        f"- profile families: `{', '.join(data['instance_product_program']['profile_families'])}`;",
        f"- account bindings: "
        f"`{', '.join(data['instance_product_program']['account_binding_types'])}`;",
        f"- secondary save/world WorkUnit: "
        f"`{data['instance_product_program']['world_save_work_unit']}`;",
        f"- runtime authority: `{str(data['instance_product_program']['runtime_authority']).lower()}`;",
        "",
        "## Operation-permit programme",
        "",
        f"- status: `{data['operation_permit_program']['status']}`;",
        f"- WorkUnit: `{data['operation_permit_program']['work_unit']}`;",
        f"- authority model: `{data['operation_permit_program']['authority_model']}`;",
        f"- provider revalidation required: "
        f"`{str(data['operation_permit_program']['provider_revalidation_required']).lower()}`;",
        f"- permit issuance authority: "
        f"`{str(data['operation_permit_program']['permit_issuance_authority']).lower()}`;",
        "",
        "## Host-environment programme",
        "",
        f"- status: `{data['host_environment_program']['status']}`;",
        f"- next WorkUnit: `{data['host_environment_program']['next_work_unit']}`;",
        f"- first runtime scope: `{data['host_environment_program']['first_runtime_scope']}`;",
        f"- first apply WorkUnit: `{data['host_environment_program']['first_apply_work_unit']}`;",
        f"- installation-model-v2 reviewed, committed, and clean: "
        f"`{str(data['host_environment_program']['installation_model_v2_reviewed_committed_clean']).lower()}`;",
        f"- blocks real Play: `{str(data['host_environment_program']['blocks_real_play']).lower()}`;",
        f"- host mutation authority: `{str(data['host_environment_program']['host_mutation_authority']).lower()}`;",
        f"- privileged broker authority: `{str(data['host_environment_program']['privileged_broker_authority']).lower()}`;",
        "- prerequisite: the current convergence, execution-foundation, and installation-model-v2 tree "
        "must be reviewed, committed, and reproduced cleanly.",
        "",
        "## Capability snapshot",
        "",
    ]
    for status in ("available", "conditional", "backlog", "unavailable"):
        ids = [item["id"] for item in data["capabilities"] if item["status"] == status]
        lines.append(f"- {status}: `{', '.join(ids) if ids else 'none'}`;")
    lines.extend([
        "",
        "## Historical proof boundary",
        "",
        f"- completed technical wave: `{data['completed_wave']['id']}`;",
        f"- last closed WorkUnit: `{data['last_closed_work_unit'] or 'none'}`;",
        f"- accepted FacMan integration: `{revisions['accepted_integration']}`;",
        f"- historical Steam-backed H1 candidate/result: `{revisions['factorio_launcher']}` / "
        f"`{data['execution']['operator_verdict']}`;",
        f"- Universal Launcher / Setup pins: `{revisions['universal_launcher']}` / "
        f"`{revisions['universal_setup']}`;",
        f"- M2 synthetic managed-target result: `{data['m2_live_portable_setup']['technical_acceptance']}`;",
        f"- M3 disposition: `{data['product']['m3_disposition']}`; adoption apply remains "
        f"`{str(data['m3_existing_portable_adoption']['adoption_apply']).lower()}`.",
        "",
        "Historical M1/M2 details remain in `release/index/project_status.v2.toml`,",
        "`.aide/history/`, and `docs/release/checkpoints/`. They do not select current",
        "work or promote execution, network, credential, signing, or publication authority.",
        "",
        "## Contract and validation identity",
        "",
        f"- commands / registered routes: `{law['contracts']}` / `{law['registered_routes']}`;",
        f"- schemas / refusal codes: `{law['schemas']}` / `{law['refusal_codes']}`;",
        f"- command catalog digest: `{law['catalog_digest']}`;",
        f"- accepted historical CI revision: `{validation['accepted_revision']}`;",
        f"- accepted historical matrix: `{validation['native_test_count']}` native and "
        f"`{validation['python_test_count']}` Python tests.",
        "",
        "## Quarantined capabilities",
        "",
        *[f"- {value}" for value in data["quarantined_capabilities"]],
        "",
        "## Known blockers",
        "",
        *[f"- {value}" for value in data["known_blockers"]],
        "",
        "## Authorities",
        "",
        "- current status: `release/index/project_status.v2.toml`;",
        "- capability vocabulary: `contracts/policy/capabilities.v1.toml`;",
        "- provider revisions: `release/index/workspace_lock.v1.toml`;",
        "- platform proof: `release/index/support_matrix.v1.toml`;",
        "- claim limitations: `docs/quality/safety_claim_ledger.md`;",
        "- accepted evidence: `.aide/history/` and `docs/release/checkpoints/`.",
        "",
    ])
    return "\n".join(lines)


def readme_status(data: dict[str, Any]) -> str:
    law = data["command_law"]
    active = data["active_work_unit"] or "none (operator gate required)"
    return "\n".join([
        "## Current Status",
        "",
        f"**Phase:** `{data['product']['phase']}`. **Active WorkUnit:** `{active}`. "
        f"**Next:** `{data['product']['next_work_unit']}`.",
        "",
        f"> {data['product']['charter']}",
        "",
        "The golden journey is:",
        f"`{data['product']['golden_journey']}`.",
        "M3 existing-portable adoption is authorised backlog after the playable alpha, not the "
        "current critical path.",
        f"This reviewed and reproduced dev-integrated tree enumerates {law['contracts']} commands, "
        f"{law['schemas']} schemas, and {law['refusal_codes']} refusal codes. These are integrated "
        "development-state counts, not release, playability, or authority claims.",
        "",
        "Two execution modes are accepted product designs but remain unproven: Steam-aware "
        "`instance_isolated` and standalone `hermetic`. `run.execute` remains unavailable because "
        f"`{data['execution']['reason']}`; no real-play gate has passed.",
        f"Readiness is playability `{data['readiness']['playability']}`, workflow "
        f"`{data['readiness']['user_workflow']}`, user validation `{data['readiness']['user_validation']}`, "
        f"and release authenticity `{data['readiness']['release_authenticity']}`.",
        "Historical M2 setup proof remains preserved and does not promote execution, existing-install "
        "adoption, network, credential, signing, or publication authority.",
        "Installation model v2 is closed as a read-only, evidence-bound planning layer.",
        "Gate 2 portable InstanceSpec, local InstanceBinding, and computed readiness are closed as "
        "menu-first read-only projections. Saves/worlds remain optional instance content.",
        "Gate 3 exact permit infrastructure is closed with provider-side revalidation and no "
        "product issuance.",
        "Gates 0-3 are canonically promoted and dev-synchronized without "
        "authority promotion. The active path now freezes the hermetic standalone Play-to-menu policy.",
        "The planned host-environment spine is a non-blocking parallel support lane; it starts read-only "
        "and grants no host mutation or privileged authority.",
        "Packages are unsigned and unpublished. The public C ABI and installed SDK remain experimental; "
        "neither carries a stable compatibility promise.",
        "Contributor status command: `py -3 tools/project_state.py --summary`.",
    ])


def roadmap_status(data: dict[str, Any]) -> str:
    active = data["active_work_unit"]
    opening = (
        f"The active phase is **{data['product']['phase']}** and the active WorkUnit is `{active}`."
        if active else
        f"The current phase is **{data['product']['phase']}** and no authority-gate WorkUnit is active."
    )
    first_step = (
        f"1. Complete `{active}`."
        if active else
        "1. Freeze one independent real-Play gate policy and obtain explicit operator acknowledgement."
    )
    return "\n".join([
        "## Current Product Sequence",
        "",
        opening,
        "",
        first_step,
        "2. Keep the accepted Gate 1 installation model read-only and transfer all general mutation to `FACMAN-MANAGED-INSTALL-RECONCILIATION-01`.",
        "3. Keep the accepted Gate 2 InstanceSpec, InstanceBinding, InstanceReadiness, and InstanceView projections read-only and menu-first.",
        "4. Keep accepted Gate 3 permits exact, expiring, replay-resistant, provider-revalidated, and unavailable to product issuance.",
        "5. Freeze `FACMAN-HERMETIC-STANDALONE-PLAY-POLICY-01`, then implement `FACMAN-HERMETIC-STANDALONE-PLAY-CANDIDATE-01` and record `FACMAN-HERMETIC-STANDALONE-PLAY-VERDICT-01`; keep Steam-aware Play independent.",
        "6. Require one passing, human-reviewed Play-to-menu route before `FACMAN-INSTANCE-CENTRIC-ALPHA-01` and pilot the golden journey with real players.",
        "7. In parallel, run read-only host inspect/doctor/support work and the first no-admin Sandbox profile without blocking unrelated Play.",
        "8. After alpha, run `FACMAN-WORLD-BUNDLE-AND-SAVE-COMPATIBILITY-01` as a secondary content lane for compatibility, import/export, and instance creation from world bundles.",
        "9. Deepen portable instance reconstruction, permit-backed managed install reconciliation, content preparation, and host repair from observed player needs.",
        "10. Require signed distribution, migration, and update rollback for public beta, not for the first controlled playable alpha.",
        "",
        "The historical Steam-backed H1 result remains a scoped **Fail**, not a verdict on the new "
        "Steam-aware instance-isolated product mode. Neither new execution mode has authority yet.",
        "The installation model is accepted read-only infrastructure for the selected local "
        "standalone route. General lifecycle apply, execution, Safe beta, networking, credentials,",
        "server processes, daemon publication, signing, and publication remain unavailable.",
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
    active = data["active_work_unit"] or "none (operator gate required)"
    return "\n".join([
        "## Current Boundary",
        "",
        f"The active product phase is `{data['product']['phase']}` and the active WorkUnit is "
        f"`{active}`. Historical M2/H1 evidence remains preserved separately.",
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
    phase_contracts = {
        "product_convergence": {
            "checkpoint": "product-convergence",
            "active": "FACMAN-PRODUCT-CONVERGENCE-01",
            "last_closed": "M2-CLOSEOUT-CANONICAL-PROMOTION-01",
            "next": "FACMAN-EXECUTION-FOUNDATION-01",
            "safety": "non_execution_foundation_proven",
            "execution_reason": "execution_foundation_not_implemented",
        },
        "execution_foundation": {
            "checkpoint": "execution-foundation",
            "active": "FACMAN-EXECUTION-FOUNDATION-01",
            "last_closed": "FACMAN-PRODUCT-CONVERGENCE-01",
            "next": "FACMAN-STEAM-AWARE-PLAY-01 + FACMAN-HERMETIC-STANDALONE-PLAY-01",
            "safety": "execution_foundation_in_progress",
            "execution_reason": "execution_foundation_in_progress",
        },
        "real_play_gates": {
            "checkpoint": "real-play-gates",
            "active": "",
            "last_closed": "FACMAN-EXECUTION-FOUNDATION-01",
            "next": "FACMAN-STEAM-AWARE-PLAY-01 + FACMAN-HERMETIC-STANDALONE-PLAY-01",
            "phase_status": "awaiting_operator_gate",
            "safety": "execution_foundation_proven_real_play_unproven",
            "execution_reason": "real_play_gate_not_passed",
        },
        "multi_version_install_lifecycle": {
            "checkpoint": "multi-version-install-lifecycle",
            "active": "FACMAN-MULTI-VERSION-INSTALL-LIFECYCLE-01",
            "last_closed": "FACMAN-EXECUTION-FOUNDATION-01",
            "next": "FACMAN-INSTANCE-SPEC-AND-READINESS-01",
            "safety": "execution_foundation_proven_real_play_unproven",
            "execution_reason": "real_play_gate_not_passed",
        },
        "instance_spec_and_readiness": {
            "checkpoint": "instance-spec-and-readiness",
            "active": "FACMAN-INSTANCE-SPEC-AND-READINESS-01",
            "last_closed": "FACMAN-INSTALLATION-MODEL-V2-READONLY-CLOSEOUT-01",
            "next": "FACMAN-OPERATION-PERMIT-01",
            "safety": "execution_foundation_proven_real_play_unproven",
            "execution_reason": "real_play_gate_not_passed",
        },
        "operation_permit": {
            "checkpoint": "operation-permit",
            "active": "FACMAN-OPERATION-PERMIT-01",
            "last_closed": "FACMAN-INSTANCE-SPEC-AND-READINESS-01",
            "next": "FACMAN-HERMETIC-STANDALONE-PLAY-01",
            "safety": "execution_foundation_proven_real_play_unproven",
            "execution_reason": "real_play_gate_not_passed",
        },
        "hermetic_standalone_play_policy": {
            "checkpoint": "hermetic-standalone-play-policy",
            "active": "FACMAN-HERMETIC-STANDALONE-PLAY-POLICY-01",
            "last_closed": "FACMAN-OPERATION-PERMIT-01",
            "next": "FACMAN-HERMETIC-STANDALONE-PLAY-CANDIDATE-01",
            "safety": "permit_infrastructure_proven_real_play_unproven",
            "execution_reason": "real_play_gate_not_passed",
        },
    }
    product = status.get("product", {})
    phase = product.get("phase")
    phase_contract = phase_contracts.get(phase)
    if phase_contract is None:
        problems.append(f"canonical product phase is unsupported: {phase!r}")
        phase_contract = phase_contracts["product_convergence"]
    if status.get("current_checkpoint") != phase_contract["checkpoint"]:
        problems.append(f"canonical status checkpoint must be {phase_contract['checkpoint']!r}")
    if status.get("next_authority_gate") != "real-play-isolation":
        problems.append("canonical status must route the next authority gate to real-play isolation")
    if status.get("safe_beta") is not False:
        problems.append("canonical status must not promote Safe beta")
    if status.get("active_work_unit") != phase_contract["active"]:
        problems.append(f"active WorkUnit must be {phase_contract['active']!r}")
    if status.get("last_closed_work_unit") != phase_contract["last_closed"]:
        problems.append(f"last closed WorkUnit must be {phase_contract['last_closed']!r}")
    expected_product = {
        "phase": phase,
        "phase_status": phase_contract.get("phase_status", "active"),
        "current_work_unit": phase_contract["active"],
        "next_work_unit": phase_contract["next"],
        "m3_disposition": "authorized_backlog_after_playable_alpha",
        "truth_scope": "canonical_main_promoted_dev_synchronized",
        "canonical_integration": True,
        "local_counts_promoted": True,
    }
    for key, expected in expected_product.items():
        if product.get(key) != expected:
            problems.append(f"product {key} must be {expected!r}")
    for key in ("primary_persona", "charter", "golden_journey", "platform_scope"):
        if not product.get(key):
            problems.append(f"product {key} must be defined")
    if product.get("current_work_unit") != status.get("active_work_unit"):
        problems.append("product and top-level active WorkUnit disagree")
    readiness = status.get("readiness", {})
    expected_readiness = {
        "playability": "not_yet_playable",
        "user_workflow": "advanced_command_surface_only",
        "safety_authority": phase_contract["safety"],
        "platform_support": "windows_first_alpha_planned",
        "release_authenticity": "not_proven_unsigned",
        "compatibility": "experimental_public_subset",
        "user_validation": "not_started",
    }
    if readiness != expected_readiness:
        problems.append("readiness dimensions must remain explicit and unpromoted")
    foundation = status.get("execution_foundation", {})
    if foundation != {
        "status": "complete_fake_process_proof",
        "work_unit": "FACMAN-EXECUTION-FOUNDATION-01",
        "process_authority": "foundation_test_process_only",
        "real_factorio_execution": False,
        "real_play_authority": False,
        "native_test_count": 43,
        "python_test_count": 355,
        "python_expected_skips": 1,
        "schema_count": 235,
        "full_verification": "pass",
    }:
        problems.append("execution foundation evidence must remain complete, bounded, and non-authoritative")
    instance_program = status.get("instance_product_program", {})
    if instance_program != {
        "status": "gate2_read_only_projection_complete",
        "architecture": "docs/architecture/instance_product_model.md",
        "work_unit": "FACMAN-INSTANCE-SPEC-AND-READINESS-01",
        "next_work_unit": "FACMAN-OPERATION-PERMIT-01",
        "portable_record": "InstanceSpec",
        "machine_local_record": "InstanceBinding",
        "readiness_model": "computed_projection_not_authoritative_state",
        "ui_aggregate": "InstanceView",
        "preparation_model": "federated_typed_subplans_by_owner",
        "default_launch_intent": "menu",
        "save_role": "optional_content_within_instance",
        "composition": [
            "installation", "instance_data_root", "template_provenance", "pinned_preset",
            "ordered_profiles", "modset_spec", "modset_lock", "account_bindings",
            "settings", "saves", "resources", "launch_intent",
        ],
        "launch_intents": [
            "menu", "continue_last", "load_save", "new_game", "map_editor",
            "connect_server", "start_server", "benchmark", "instrumented_dev",
        ],
        "profile_families": [
            "LaunchProfile", "GraphicsProfile", "AudioProfile", "InterfaceProfile",
            "MultiplayerProfile", "ServerProfile", "NewGameProfile", "BackupProfile",
        ],
        "account_binding_types": [
            "PlatformAccountBinding", "FactorioAccountBinding", "PlayerIdentityProfile",
            "ServerCredentialBinding",
        ],
        "mod_content_records": ["ModsetSpec", "ModsetLock", "ModpackBundle"],
        "world_save_work_unit": "FACMAN-WORLD-BUNDLE-AND-SAVE-COMPATIBILITY-01",
        "templates_are_initializers": True,
        "conflicts_silently_resolved": False,
        "portable_factorio_binaries": False,
        "credential_values_in_instance": False,
        "presets_grant_authority": False,
        "foreign_installation_mutation": False,
        "runtime_authority": False,
    }:
        problems.append("instance programme must remain decomposed, menu-first, portable, and non-authoritative")
    permit_program = status.get("operation_permit_program", {})
    if permit_program != {
        "status": "gate3_infrastructure_complete_no_issuance",
        "work_unit": "FACMAN-OPERATION-PERMIT-01",
        "authority_model": "short_lived_plan_bound_exact_resource_permit",
        "global_admission_is_sole_enforcer": False,
        "provider_revalidation_required": True,
        "harmless_reads_require_permit": False,
        "permit_issuance_authority": False,
    }:
        problems.append("operation permits must remain short-lived, plan-bound, and unissued")
    gate3 = status.get("gate3_operation_permit_closeout", {})
    expected_gate3 = {
        "status": "accepted_reviewed_dev_integration",
        "work_unit": "FACMAN-OPERATION-PERMIT-01",
        "implementation_pull_request": 42,
        "reviewed_head_revision": "5f9f122d6d3e95a006c44e46ba54c0927e9d288c",
        "dev_integration_revision": "91c2aa4fe0a30be97bf16165b41a95a8fab4cd11",
        "universal_launcher_revision": "7bd4425f0c35414f738159b45d8bec42edf70235",
        "universal_setup_revision": "3f8489275077347c2918f3bb03614ec6431362ff",
        "exact_head_ci_run": "29825371714",
        "exact_head_code_security_run": "29825371722",
        "exact_head_schema_check_run": "29825371753",
        "exact_head_security_policy_run": "29825371793",
        "exact_dev_ci_run": "29826221338",
        "exact_dev_code_security_run": "29826221318",
        "exact_dev_schema_check_run": "29826221373",
        "exact_dev_security_policy_run": "29826221366",
        "exact_dev_clean_reproduction": True,
        "clean_reproduction_seconds": 442.0,
        "native_test_count": 47,
        "python_test_count": 364,
        "python_expected_skips": 2,
        "schema_count": 268,
        "command_count": 125,
        "registered_route_count": 123,
        "refusal_code_count": 242,
        "canonicalization_version": "facman.sorted-json.v1",
        "authenticator_algorithm": "hmac-sha256.process.v1",
        "projected_instance_resource_count": 9,
        "provider_revalidation_proof": "dormant_factorio_launch_foundation_operation",
        "permit_issuance_authority": False,
        "real_factorio_execution": False,
        "setup_authority_promotion": False,
        "credential_authority_promotion": False,
        "network_authority_promotion": False,
        "signing": False,
        "publication": False,
        "canonical_main_promotion": False,
    }
    if gate3 != expected_gate3:
        problems.append("Gate 3 closeout must bind exact reviewed and merged-dev proof without promoting issuance or execution")
    gate3_integration = status.get("gate3_public_integration", {})
    expected_gate3_integration = {
        "status": "accepted_canonical_main_dev_synchronized",
        "closeout_pull_request": 43,
        "closeout_head_revision": "ec4159f05678ad1ea55326ea881728354f5182c6",
        "closeout_dev_revision": "11feb2e53539e4b272f061374b2a07450c8e32bf",
        "closeout_head_ci_run": "29828529397",
        "closeout_head_code_security_run": "29828529368",
        "closeout_head_security_policy_run": "29828529380",
        "closeout_dev_ci_run": "29829439259",
        "closeout_dev_code_security_run": "29829439147",
        "closeout_dev_security_policy_run": "29829439134",
        "promotion_pull_request": 44,
        "promotion_source_revision": "11feb2e53539e4b272f061374b2a07450c8e32bf",
        "canonical_main_revision": "810e92ccd52ad89fada8a9bb5699805cb5580c24",
        "shared_tree_identity": "1f15a9ff477db9f4713e82ce23aedea1914293d9",
        "promotion_head_ci_run": "29830315611",
        "promotion_head_code_security_run": "29830315615",
        "promotion_head_schema_check_run": "29830315614",
        "promotion_head_security_policy_run": "29830315656",
        "exact_main_ci_run": "29831299212",
        "exact_main_code_security_run": "29831299101",
        "exact_main_schema_check_run": "29831299292",
        "exact_main_security_policy_run": "29831299545",
        "synchronization_pull_request": 45,
        "synchronization_head_revision": "ff57488e3cd5a04d6aab7a28f667be64ac54992a",
        "synchronization_head_ci_run": "29832438748",
        "synchronization_head_code_security_run": "29832438688",
        "synchronization_head_security_policy_run": "29832438665",
        "final_dev_revision": "08d4318ffd32bd9553ce8914cbd8bfc98fde7b74",
        "final_dev_ci_run": "29833442835",
        "final_dev_code_security_run": "29833442940",
        "final_dev_security_policy_run": "29833442807",
        "main_is_ancestor_of_dev": True,
        "trees_equal_at_synchronization": True,
        "authority_promotion": False,
        "playability_promotion": False,
        "permit_issuance_authority": False,
        "real_factorio_execution": False,
        "signing": False,
        "publication": False,
    }
    if gate3_integration != expected_gate3_integration:
        problems.append("Gate 3 public integration must bind exact canonical and synchronized proof without promoting authority")
    gate2 = status.get("gate2_instance_spec_and_readiness_closeout", {})
    expected_gate2 = {
        "status": "accepted_reviewed_dev_integration",
        "work_unit": "FACMAN-INSTANCE-SPEC-AND-READINESS-01",
        "implementation_pull_request": 39,
        "scope_revision": "a2b851c258e901055ae2edbc3c9379f5aa502652",
        "implementation_revision": "fa11b056c03784964e66ef391a81a6dfa8fcedc1",
        "implementation_dev_revision": "7113011a6c4fe1d76d4c09cc36bc8a3aafa34b36",
        "reproduction_correction_pull_request": 40,
        "reproduction_correction_revision": "f5915475eff78c255fe1f618a8be12c9c0f2d0f9",
        "final_dev_revision": "bbb46c5bfd10cd35fb965b23edc4951784f93ef4",
        "universal_launcher_revision": "7bd4425f0c35414f738159b45d8bec42edf70235",
        "universal_setup_revision": "3f8489275077347c2918f3bb03614ec6431362ff",
        "exact_head_ci_run": "29812506939",
        "exact_head_code_security_run": "29812506919",
        "exact_head_schema_check_run": "29812506783",
        "exact_head_security_policy_run": "29812507063",
        "correction_head_ci_run": "29814299428",
        "correction_head_code_security_run": "29814299449",
        "correction_head_security_policy_run": "29814299432",
        "exact_dev_ci_run": "29815159526",
        "exact_dev_code_security_run": "29815159602",
        "exact_dev_security_policy_run": "29815159595",
        "exact_dev_schema_check_run": "29813605517",
        "exact_dev_schema_disposition": "implementation_merge_passed_and_final_correction_had_no_schema_delta",
        "local_full_matrix": True,
        "exact_dev_clean_reproduction": True,
        "clean_reproduction_seconds": 387.0,
        "native_test_count": 44,
        "implementation_python_test_count": 360,
        "final_python_test_count": 361,
        "python_expected_skips": 7,
        "schema_count": 261,
        "command_count": 125,
        "registered_route_count": 123,
        "refusal_code_count": 217,
        "canonicalization_version": "facman.sorted-json.v1",
        "default_launch_intent": "menu",
        "supported_launch_intents": ["menu"],
        "compatible_v1_record_rewritten": False,
        "read_only_projection": True,
        "zero_write_proof": True,
        "preparation_available": False,
        "execution_available": False,
        "permit_issuance_authority": False,
        "authority_promotion": False,
        "playability_promotion": False,
        "canonical_main_promotion": False,
        "signing": False,
        "publication": False,
    }
    if gate2 != expected_gate2:
        problems.append("Gate 2 closeout must bind exact reviewed and merged-dev proof without promoting authority")
    host_program = status.get("host_environment_program", {})
    if host_program != {
        "status": "planned_parallel_support_lane",
        "architecture": "docs/architecture/host_environment_lifecycle.md",
        "next_work_unit": "HOST-ENVIRONMENT-CONTRACT-SPINE-01",
        "first_runtime_scope": "workflow_specific_read_only_list_inspect_doctor",
        "first_apply_work_unit": "WINDOWS-SANDBOX-PROFILE-01",
        "workflow_health_model": "versioned_requirement_profiles_no_global_health_score",
        "installation_model_v2_reviewed_committed_clean": True,
        "critical_path": False,
        "blocks_real_play": False,
        "host_mutation_authority": False,
        "privileged_broker_authority": False,
        "remote_mutation_authority": False,
        "arbitrary_script_authority": False,
    }:
        problems.append("host-environment programme must remain parallel, non-blocking, and non-mutating")
    lifecycle = status.get("multi_version_install_lifecycle", {})
    if lifecycle.get("status") != "gate1_read_only_model_complete_remaining_mutation_transferred":
        problems.append("installation-model-v2 must record the accepted Gate 1 boundary and transferred mutation lifecycle")
    if lifecycle.get("installation_model_v2") != "implemented_read_only_projection":
        problems.append("installation-model-v2 must remain a read-only projection")
    if lifecycle.get("reconciliation_plan") != "implemented_evidence_bound_deterministic_plan_only":
        problems.append("installation reconciliation must remain evidence-bound, deterministic, and plan-only")
    if lifecycle.get("reconciliation_apply") is not False:
        problems.append("installation reconciliation apply must remain unavailable")
    if lifecycle.get("umbrella_objective_complete") is not False:
        problems.append("the broad installation lifecycle objective must not be marked complete")
    if lifecycle.get("remaining_lifecycle_work_unit") != "FACMAN-MANAGED-INSTALL-RECONCILIATION-01":
        problems.append("remaining installation mutation scope must be transferred explicitly")
    if not lifecycle.get("plan_identity_binds_current_evidence"):
        problems.append("installation reconciliation plan identity must bind current evidence")
    if not lifecycle.get("zero_write_proof"):
        problems.append("installation read-only closeout must retain zero-write proof")
    gate1 = status.get("gate1_installation_model_v2_readonly_closeout", {})
    expected_gate1 = {
        "status": "accepted_reviewed_dev_integration",
        "work_unit": "FACMAN-INSTALLATION-MODEL-V2-READONLY-CLOSEOUT-01",
        "implementation_pull_request": 37,
        "implementation_revision": "ecd157570dfe3f87006cb00e8fe07a959f44ae8c",
        "reviewed_head_revision": "c9ae60405d0b221faaba364be5f47e524649bb97",
        "dev_integration_revision": "6ec47046d1b1f4ab8bddfcc27bcec76a774ff305",
        "universal_launcher_revision": "7bd4425f0c35414f738159b45d8bec42edf70235",
        "universal_setup_revision": "3f8489275077347c2918f3bb03614ec6431362ff",
        "exact_head_ci_run": "29799245632",
        "exact_head_code_security_run": "29799245642",
        "exact_head_schema_check_run": "29799245604",
        "exact_head_security_policy_run": "29799245629",
        "exact_dev_ci_run": "29799938954",
        "exact_dev_code_security_run": "29799939008",
        "exact_dev_schema_check_run": "29799938962",
        "exact_dev_security_policy_run": "29799938996",
        "local_full_matrix": True,
        "exact_dev_clean_reproduction": True,
        "clean_reproduction_seconds": 362.9,
        "canonicalization_version": "facman.sorted-json.v1",
        "effect_vocabulary_version": "common.effects.v1",
        "plan_identity_binds_current_evidence": True,
        "plan_identity_binds_desired_state": True,
        "source_candidate_is_authenticated_evidence": False,
        "zero_write_proof": True,
        "compatible_v1_record_rewritten": False,
        "apply_route_added": False,
        "reconciliation_apply": False,
        "authority_promotion": False,
        "playability_promotion": False,
        "canonical_main_promotion": False,
        "signing": False,
        "publication": False,
    }
    if gate1 != expected_gate1:
        problems.append("Gate 1 closeout must bind exact reviewed and merged-dev proof without promoting authority")
    gate0 = status.get("gate0_product_convergence_integration", {})
    expected_gate0 = {
        "status": "accepted_reviewed_dev_integration",
        "pull_request": 34,
        "reviewed_head_revision": "61a7afe6718d3ca36b2c530b83890fcd37cc5c03",
        "dev_integration_revision": "62c2503110cdb89b9cc89f19a69903f214d33e3c",
        "universal_launcher_revision": "7bd4425f0c35414f738159b45d8bec42edf70235",
        "universal_setup_revision": "3f8489275077347c2918f3bb03614ec6431362ff",
        "exact_head_ci_run": "29758642385",
        "exact_head_code_security_run": "29758642411",
        "exact_head_schema_check_run": "29758642428",
        "exact_head_security_policy_run": "29758642557",
        "exact_dev_ci_run": "29760235796",
        "exact_dev_code_security_run": "29760235888",
        "exact_dev_schema_check_run": "29760236038",
        "exact_dev_security_policy_run": "29760236168",
        "exact_head_clean_reproduction": True,
        "exact_dev_clean_reproduction": True,
        "five_slice_review": "pass_with_documented_notes_no_p0_findings",
        "generated_contract_counts_verified": True,
        "setup_global_admission_verified": True,
        "authority_promotion": False,
        "playability_promotion": False,
        "canonical_main_promotion": False,
        "signing": False,
        "publication": False,
    }
    if gate0 != expected_gate0:
        problems.append("Gate 0 integration evidence must bind the exact reviewed head and merged-dev proofs without promoting authority")
    execution_modes = {mode.get("id"): mode for mode in status.get("execution_mode", [])}
    if set(execution_modes) != {"instance_isolated", "hermetic"}:
        problems.append("canonical status must define exactly the two accepted execution modes")
    for mode in execution_modes.values():
        if mode.get("product_mode") != "accepted" or mode.get("claim_status") != "unproven":
            problems.append(f"execution mode {mode.get('id', '<unknown>')} must remain accepted but unproven")
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
    if m1_integration.get("canonical_main_revision") != "73bec99916d509b0ab055a43562e93ef20a6b4b7":
        problems.append("M1 public integration must preserve its accepted canonical main revision")
    if m1_integration.get("dev_tree_identity") != m1_integration.get("main_tree_identity"):
        problems.append("M1 dev and main integration trees must be identical")
    if m1_integration.get("checkpoint_tree_identity") != m1_integration.get("main_tree_identity"):
        problems.append("M1 checkpoint and canonical main trees must be identical")
    if not m1_integration.get("main_dev_synchronized_at_proof"):
        problems.append("M1 public integration must bind canonical main ancestry into dev")
    if m1_integration.get("authority_promotion") is not False:
        problems.append("M1 public integration proof must not promote authority")
    m2 = status.get("m2_live_portable_setup", {})
    if m2.get("status") not in {
        "complete_machine_pass_pending_canonical_promotion",
        "complete_machine_pass_canonically_promoted",
    }:
        problems.append("M2 must remain complete at a recognized canonical-promotion state")
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
        closeout.get("work_unit"),
        closeout.get("wu10_pull_request"), closeout.get("wu10_dev_merge_revision"),
        closeout.get("technical_acceptance"), closeout.get("human_review"),
        closeout.get("result_sha256"), closeout.get("local_managed_portable_setup"),
    ] != [
        "M2-CLOSEOUT-CANONICAL-PROMOTION-01", 28,
        "5250db1d17ac330f5ae0b672ccc7466431a1e4a2", "MachinePass",
        "not_required_for_synthetic_non_executable_lane",
        "a4a00a3f77b394f988a71f9eaa86de3c9c9b74a4051d1c2e3ad38f60b9ad8efa",
        "candidate",
    ]:
        problems.append("M2 closeout candidate identity or scope changed")
    closeout_status = closeout.get("status")
    if closeout_status not in {
        "machine_pass_closeout_pending_exact_dev_and_main_promotion",
        "canonically_promoted_public_integration_pending_dev_synchronization",
        "accepted_public_integration_dev_synchronized",
    }:
        problems.append("M2 closeout must record a recognized monotonic promotion state")
    if closeout_status == "machine_pass_closeout_pending_exact_dev_and_main_promotion":
        if closeout.get("canonical_main_revision") != "pending_dev_to_main_promotion":
            problems.append("pending M2 closeout must not claim a canonical revision")
    else:
        if [
            closeout.get("closeout_pull_request"), closeout.get("closeout_task_revision"),
            closeout.get("dev_integration_revision"), closeout.get("shared_promoted_tree_identity"),
            closeout.get("promotion_pull_request"), closeout.get("promotion_head_revision"),
            closeout.get("canonical_main_revision"), closeout.get("exact_main_ci_run"),
            closeout.get("exact_main_code_security_run"), closeout.get("exact_main_schema_check_run"),
            closeout.get("exact_main_security_policy_run"),
        ] != [
            29, "3fc80882e7da0e38cddd901dfc965775281b0411",
            "4afab65448831b05ab790957abf0e1798074ad1a",
            "ee54dc220ed5fd80a9f450988033c5e29599a326", 30,
            "4afab65448831b05ab790957abf0e1798074ad1a",
            "bd0642951a4a3abfb2cc1916c8b9c2c4e81d880f",
            "29569007275", "29569007270", "29569007323", "29569007290",
        ]:
            problems.append("M2 canonical promotion or exact-main proof identity changed")
        if status.get("accepted_integration_revision") != closeout.get("canonical_main_revision"):
            problems.append("accepted integration must bind the canonical M2 main revision")
    if closeout_status == "accepted_public_integration_dev_synchronized":
        if [
            closeout.get("public_integration"), closeout.get("public_integration_task_revision"),
            closeout.get("public_integration_pull_request"), closeout.get("public_integration_dev_revision"),
            closeout.get("public_integration_tree_identity"), closeout.get("public_integration_dev_ci_run"),
            closeout.get("public_integration_dev_code_security_run"),
            closeout.get("public_integration_dev_security_policy_run"),
            closeout.get("dev_synchronization"), closeout.get("dev_synchronization_task_revision"),
            closeout.get("dev_synchronization_pull_request"), closeout.get("dev_synchronization_revision"),
            closeout.get("dev_synchronization_tree_identity"),
            closeout.get("dev_synchronization_main_ancestor"),
            closeout.get("dev_synchronization_ci_run"),
            closeout.get("dev_synchronization_code_security_run"),
            closeout.get("dev_synchronization_security_policy_run"),
        ] != [
            "accepted_exact_dev_checkpoint", "44687765815174db8afc1da6fa768f7a655a6290",
            31, "1678cb6d3c9545f09c4ae729054f68cf0fbc7bf2",
            "8487c87a097395186cccbcd13d929dd88d3b16fa", "29571806755",
            "29571806753", "29571806738", "accepted_exact_dev_head",
            "6fb4a0c96503f32ad9070a5c557f2fa1a31209c8", 32,
            "51977de8120202958fc35776d284077b1fc027d3",
            "8487c87a097395186cccbcd13d929dd88d3b16fa", True,
            "29573335555", "29573335458", "29573335488",
        ]:
            problems.append("M2 public integration or dev synchronization proof identity changed")
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
    expected_m3_status = "authorized_backlog_after_playable_alpha"
    if [
        m3.get("status"), m3.get("scope"), m3.get("existing_portable_inspection"),
        m3.get("adoption_plan"), m3.get("adoption_apply"),
        m3.get("deletion_authority"), m3.get("existing_installation_mutation"),
        m3.get("steam_adoption"), m3.get("steam_mutation"), m3.get("run_execute"),
    ] != [
        expected_m3_status,
        "read_only_and_plan_only", True, True, False, False, False, False, False, False,
    ]:
        problems.append("M3 must remain in its phase-appropriate read-only and plan-only state")
    if m3.get("opened_after_m2_dev_revision") != "51977de8120202958fc35776d284077b1fc027d3":
        problems.append("M3 backlog must retain the accepted synchronized M2 dev revision")
    if m3.get("resume_after") != "FACMAN-INSTANCE-CENTRIC-ALPHA-01":
        problems.append("M3 backlog must resume only after the playable alpha")
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
    if execution.get("reason") != phase_contract["execution_reason"]:
        problems.append("canonical execution reason must match the current product phase")
    verdict = execution.get("operator_verdict")
    if verdict not in {"pending", "Fail"}:
        problems.append("canonical status may record only pending or the reviewed H1 Fail before promotion")
    if verdict == "Fail" and not execution.get("proof"):
        problems.append("canonical H1 Fail must bind a sanitized proof record")
    if execution.get("operator_verdict_scope") != "historical_steam_backed_h1_only":
        problems.append("historical H1 verdict must remain explicitly scoped")
    if execution.get("current_gate_status") != "not_started":
        problems.append("real-play execution gates must remain not started")
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


def summary(data: dict[str, Any]) -> str:
    modes = ", ".join(
        f"{mode['id']}={mode['claim_status']}"
        for mode in data["execution_modes"]
    )
    return "\n".join([
        "FacMan product status",
        f"phase: {data['product']['phase']} ({data['product']['phase_status']})",
        f"active_work_unit: {data['active_work_unit'] or 'none'}",
        f"next_work_unit: {data['product']['next_work_unit']}",
        f"golden_journey: {data['product']['golden_journey']}",
        f"playability: {data['readiness']['playability']}",
        f"execution: {data['execution']['status']} ({data['execution']['reason']})",
        f"execution_modes: {modes}",
        f"release_authenticity: {data['readiness']['release_authenticity']}",
        f"user_validation: {data['readiness']['user_validation']}",
    ])


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate FacMan project truth from canonical data.")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--write", action="store_true")
    modes.add_argument("--summary", action="store_true")
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
    if args.summary:
        print(summary(data))
        return 0
    print("project-state: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
