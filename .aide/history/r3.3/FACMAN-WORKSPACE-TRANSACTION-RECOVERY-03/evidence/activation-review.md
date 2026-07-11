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

- `.aide/queue/FACMAN-WORKSPACE-TRANSACTION-RECOVERY-03/evidence/activation-verification.json`
- verifier_result: PASS
- report_chars: 1191
- report_approx_tokens: 298

## Evidence Packet References

- `.aide/queue/FACMAN-WORKSPACE-TRANSACTION-RECOVERY-03/evidence/activation-verification.json`
- `.aide/queue/FACMAN-WORKSPACE-TRANSACTION-RECOVERY-03/evidence/remaining-risks.md`

## Changed Files Summary

- allowed: `.aide/memory/project-state.md` (M; matches active task allowed path)
- allowed: `.aide/profile.yaml` (M; matches active task allowed path)
- allowed: `.aide/queue/FACMAN-SAVE-AND-INSTANCE-TRANSFER-ROUTE-03/evidence/validation.md` (M; matches active task allowed path)
- allowed: `.aide/queue/FACMAN-SAVE-AND-INSTANCE-TRANSFER-ROUTE-03/status.yaml` (M; matches active task allowed path)
- allowed: `.aide/queue/FACMAN-SAVE-AND-INSTANCE-TRANSFER-ROUTE-03/task.yaml` (M; matches active task allowed path)
- allowed: `.aide/queue/FACMAN-WORKSPACE-TRANSACTION-RECOVERY-03` (??; matches active task allowed path)
- allowed: `.aide/queue/index.yaml` (M; matches active task allowed path)

## Validation Summary

- validation evidence not found

## Token Summary

- packet_path: `.aide/queue/FACMAN-WORKSPACE-TRANSACTION-RECOVERY-03/evidence/activation-review.md`
- method: chars / 4, rounded up
- chars: 3930
- approx_tokens: 983
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

- Journal durability and directory flush behavior differ across Windows,
- Recovery must treat a complete target as authoritative even when journal
- Network/shared filesystems remain outside this WorkUnit.
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
