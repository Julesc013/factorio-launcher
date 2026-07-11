# AIDE Latest Review Packet

## Review Objective

Review the current AIDE queue phase from compact evidence only and decide whether it is ready to pass its review gate.

## Decision Requested

Return exactly one of `PASS`, `PASS_WITH_NOTES`, `REQUEST_CHANGES`, or `BLOCKED`.

## Task Packet Reference

- `.aide/context/latest-task-packet.md` (4313 chars, 1079 approximate tokens)

## Context Packet Reference

- `.aide/context/latest-context-packet.md` (1811 chars, 453 approximate tokens)
- `.aide/context/repo-map.json`
- `.aide/context/test-map.json`
- `.aide/context/context-index.json`

## Verification Report Reference

- `.aide/queue/FACMAN-SAVE-AND-INSTANCE-TRANSFER-ROUTE-03/evidence/local-verification.json`
- verifier_result: PASS
- report_chars: 6095
- report_approx_tokens: 1524

## Evidence Packet References

- `.aide/queue/FACMAN-SAVE-AND-INSTANCE-TRANSFER-ROUTE-03/evidence/activation-review.md`
- `.aide/queue/FACMAN-SAVE-AND-INSTANCE-TRANSFER-ROUTE-03/evidence/activation-verification.json`
- `.aide/queue/FACMAN-SAVE-AND-INSTANCE-TRANSFER-ROUTE-03/evidence/changed-files.md`
- `.aide/queue/FACMAN-SAVE-AND-INSTANCE-TRANSFER-ROUTE-03/evidence/local-verification.json`
- `.aide/queue/FACMAN-SAVE-AND-INSTANCE-TRANSFER-ROUTE-03/evidence/remaining-risks.md`
- `.aide/queue/FACMAN-SAVE-AND-INSTANCE-TRANSFER-ROUTE-03/evidence/validation.md`

## Changed Files Summary

- allowed: `.aide/queue/FACMAN-SAVE-AND-INSTANCE-TRANSFER-ROUTE-03/evidence/changed-files.md` (??; matches active task allowed path)
- allowed: `.aide/queue/FACMAN-SAVE-AND-INSTANCE-TRANSFER-ROUTE-03/evidence/local-verification.json` (??; matches active task allowed path)
- allowed: `.aide/queue/FACMAN-SAVE-AND-INSTANCE-TRANSFER-ROUTE-03/evidence/remaining-risks.md` (M; matches active task allowed path)
- allowed: `.aide/queue/FACMAN-SAVE-AND-INSTANCE-TRANSFER-ROUTE-03/evidence/validation.md` (??; matches active task allowed path)
- allowed: `.aide/queue/FACMAN-SAVE-AND-INSTANCE-TRANSFER-ROUTE-03/status.yaml` (M; matches active task allowed path)
- allowed: `.aide/queue/FACMAN-SAVE-AND-INSTANCE-TRANSFER-ROUTE-03/task.yaml` (M; matches active task allowed path)
- allowed: `CMakeLists.txt` (M; matches active task allowed path)
- allowed: `apps/cli/command_dispatch.cpp` (M; matches active task allowed path)
- allowed: `apps/gui/macos/appkit/CommandClient.mm` (M; matches active task allowed path)
- allowed: `apps/gui/macos/appkit/MainWindowController.m` (M; matches active task allowed path)
- allowed: `apps/gui/macos/appkit/README.md` (M; matches active task allowed path)
- allowed: `apps/gui/windows/winforms/CommandCatalog.cs` (M; matches active task allowed path)
- allowed: `apps/gui/windows/winforms/MainForm.cs` (M; matches active task allowed path)
- allowed: `apps/gui/windows/winforms/README.md` (M; matches active task allowed path)
- allowed: `contracts/command/factorio/export.instance.v1.toml` (RM; matches active task allowed path)
- allowed: `contracts/command/factorio/import.instance.v1.toml` (RM; matches active task allowed path)
- allowed: `contracts/command/factorio/instance.export.v1.toml` (RM; matches active task allowed path)
- allowed: `contracts/command/factorio/instance.import.v1.toml` (RM; matches active task allowed path)
- allowed: `contracts/command/factorio/saves.clone.v1.toml` (??; matches active task allowed path)
- allowed: `contracts/command/factorio/saves.list.v1.toml` (??; matches active task allowed path)
- allowed: `contracts/command/frontend/frontend.required_commands.v1.toml` (M; matches active task allowed path)
- allowed: `contracts/refusal/refusal_codes.v1.toml` (M; matches active task allowed path)
- allowed: `contracts/schema/factorio/factorio_instance_export.v1.schema.json` (M; matches active task allowed path)
- allowed: `contracts/schema/factorio/factorio_instance_import.v1.schema.json` (M; matches active task allowed path)
- additional changed paths omitted from compact packet: 34; see task evidence changed-files report

## Validation Summary

- `saves.list`, `saves.backup`, `saves.clone`, `instance.export`, and
- CLI `export instance` and `import instance` spellings normalize to canonical
- Stored and deflated saves are structurally inspected through the production
- Backup, clone, and export sources are copied from one no-follow handle with
- File and directory outputs stage under the destination parent, verify before
- Portable export uses deterministic deflate, redacted metadata, a complete
- Import validates the complete archive plan and declared closure before
- Traversal and tamper cases leave no target. Eight injected interruption
- Valid-shaped write dry-runs refuse without mutation; save listing remains
- Full native build: PASS.
- Native CTest: PASS (9/9).
- Complete Python suite: PASS (204/204).
- Save/transfer adversarial suite: PASS (5/5).
- Strict checks: PASS (19 commands, 55 schemas, 79 refusal codes, 23 refusal

## Token Summary

- packet_path: `.aide/queue/FACMAN-SAVE-AND-INSTANCE-TRANSFER-ROUTE-03/evidence/local-review.md`
- method: chars / 4, rounded up
- chars: 7151
- approx_tokens: 1788
- budget_status: PASS
- max_token_warning: 2400
- warnings:
- none
- formal ledger: `.aide/reports/token-ledger.jsonl`

## Outcome Controller Summary

- outcome_report: `.aide/controller/latest-outcome-report.md` (missing)
- recommendations: `.aide/controller/latest-recommendations.md` (missing)
- applies_automatically: false

## Route Decision Summary

- route_decision: `.aide/routing/latest-route-decision.json` (missing)
- advisory_only: true

## Cache / Local State Summary

- cache_keys: `.aide/cache/latest-cache-keys.json` (missing; run cache report)
- local_state_ignored: true
- tracked_local_state_paths: 0
- raw_prompt_storage: false
- raw_response_storage: false

## Gateway Skeleton Summary

- gateway_status: `.aide/gateway/latest-gateway-status.json` (missing; run gateway status)
- local_skeleton: true
- provider_or_model_calls: none

## Provider Adapter Summary

- provider_status: `.aide/providers/latest-provider-status.json` (missing; run provider status)
- offline_metadata_only: true
- live_provider_calls: false

## Risk Summary

- Save recognition remains explicitly shallower than deep Factorio save
- Cross-volume behavior uses destination-volume staging and stable-handle
- The subsequent transaction-recovery WorkUnit remains responsible for one
- The dormant diagnostic bundle still owns the only quarantined hand-written
- Diagnostics, `run.execute`, real Factorio isolation, Safe beta, setup

## Non-Goals / Scope Guard

- Gateway
- provider calls
- model routing
- Runtime/Service/Commander/UI/Mobile
- MCP/A2A
- automatic model calls or repair

## Reviewer Instructions

- Review only this packet and the referenced evidence when needed.
- Do not request full chat history unless the packet is insufficient to judge correctness.
- Do not re-summarize the whole project.
- Do not reward scope creep.
- Do not approve missing validation as a pass.
- Required output sections: `DECISION`, `REASONS`, `REQUIRED_FIXES`, `OPTIONAL_NOTES`, `NEXT_PHASE`.
- Decision policy: `.aide/verification/review-decision-policy.yaml`.
