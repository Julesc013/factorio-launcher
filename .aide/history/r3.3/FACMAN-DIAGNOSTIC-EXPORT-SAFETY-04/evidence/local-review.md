# AIDE Latest Review Packet

## Review Objective

Review the current AIDE queue phase from compact evidence only and decide whether it is ready to pass its review gate.

## Decision Requested

Return exactly one of `PASS`, `PASS_WITH_NOTES`, `REQUEST_CHANGES`, or `BLOCKED`.

## Task Packet Reference

- `.aide/context/latest-task-packet.md` (4329 chars, 1083 approximate tokens)

## Context Packet Reference

- `.aide/context/latest-context-packet.md` (1811 chars, 453 approximate tokens)
- `.aide/context/repo-map.json`
- `.aide/context/test-map.json`
- `.aide/context/context-index.json`

## Verification Report Reference

- `.aide/queue/FACMAN-DIAGNOSTIC-EXPORT-SAFETY-04/evidence/local-verification.json`
- verifier_result: PASS
- report_chars: 4507
- report_approx_tokens: 1127

## Evidence Packet References

- `.aide/queue/FACMAN-DIAGNOSTIC-EXPORT-SAFETY-04/evidence/activation-review.md`
- `.aide/queue/FACMAN-DIAGNOSTIC-EXPORT-SAFETY-04/evidence/activation-verification.json`
- `.aide/queue/FACMAN-DIAGNOSTIC-EXPORT-SAFETY-04/evidence/changed-files.md`
- `.aide/queue/FACMAN-DIAGNOSTIC-EXPORT-SAFETY-04/evidence/local-verification.json`
- `.aide/queue/FACMAN-DIAGNOSTIC-EXPORT-SAFETY-04/evidence/remaining-risks.md`
- `.aide/queue/FACMAN-DIAGNOSTIC-EXPORT-SAFETY-04/evidence/validation.md`

## Changed Files Summary

- allowed: `.aide/memory/project-state.md` (M; matches active task allowed path)
- allowed: `.aide/profile.yaml` (M; matches active task allowed path)
- allowed: `.aide/queue/FACMAN-DIAGNOSTIC-EXPORT-SAFETY-04/evidence/changed-files.md` (??; matches active task allowed path)
- allowed: `.aide/queue/FACMAN-DIAGNOSTIC-EXPORT-SAFETY-04/evidence/local-verification.json` (??; matches active task allowed path)
- allowed: `.aide/queue/FACMAN-DIAGNOSTIC-EXPORT-SAFETY-04/evidence/remaining-risks.md` (M; matches active task allowed path)
- allowed: `.aide/queue/FACMAN-DIAGNOSTIC-EXPORT-SAFETY-04/evidence/validation.md` (??; matches active task allowed path)
- allowed: `.aide/queue/FACMAN-DIAGNOSTIC-EXPORT-SAFETY-04/status.yaml` (M; matches active task allowed path)
- allowed: `.aide/queue/FACMAN-DIAGNOSTIC-EXPORT-SAFETY-04/task.yaml` (M; matches active task allowed path)
- allowed: `CMakeLists.txt` (M; matches active task allowed path)
- allowed: `README.md` (M; matches active task allowed path)
- allowed: `apps/cli/command_dispatch.cpp` (M; matches active task allowed path)
- allowed: `contracts/command/factorio/diagnostics.export.v1.toml` (??; matches active task allowed path)
- allowed: `contracts/command/frontend/frontend.required_commands.v1.toml` (M; matches active task allowed path)
- allowed: `contracts/refusal/refusal_codes.v1.toml` (M; matches active task allowed path)
- allowed: `contracts/schema/factorio/diagnostic_bundle.v1.schema.json` (M; matches active task allowed path)
- allowed: `contracts/schema/factorio/diagnostic_bundle_export.v1.schema.json` (??; matches active task allowed path)
- allowed: `contracts/schema/factorio/diagnostic_file_read_report.v1.schema.json` (??; matches active task allowed path)
- allowed: `contracts/schema/factorio/diagnostic_omission_report.v1.schema.json` (??; matches active task allowed path)
- allowed: `docs/architecture/diagnostic-export-safety.v1.md` (??; matches active task allowed path)
- allowed: `docs/quality/safety_claim_ledger.md` (M; matches active task allowed path)
- allowed: `docs/roadmap.md` (M; matches active task allowed path)
- allowed: `runtime/base/fl_sha256.cpp` (M; matches active task allowed path)
- allowed: `runtime/base/fl_sha256.h` (M; matches active task allowed path)
- allowed: `runtime/factorio/application/flb_factorio_application.cpp` (M; matches active task allowed path)
- additional changed paths omitted from compact packet: 19; see task evidence changed-files report

## Validation Summary

- `diagnostics.export` routes through the registered ULK descriptor, FLB, and
- Windows sources use wide stable handles with reparse, containment, volume,
- Only reviewed manifests, config files, Factorio logs, and explicit text
- The typed bundle contains traversal, redaction, file-read consistency, and
- Output uses deterministic production deflate, owned destination-volume
- Fault injection covers all ten success states. Pre-commit faults leave no
- Source fixtures and instance files remain unchanged. No required test was
- Full native build: PASS.
- Native CTest: PASS (9/9).
- Complete Python suite: PASS (216/216, zero skips).
- Strict checks: PASS (23 commands, 59 schemas, 89 refusal codes, 27 refusal
- Diagnostic export and transaction recovery checkers: PASS.
- AIDE Lite test: PASS.
- `git diff --check`: PASS.

## Token Summary

- packet_path: `.aide/queue/FACMAN-DIAGNOSTIC-EXPORT-SAFETY-04/evidence/local-review.md`
- method: chars / 4, rounded up
- chars: 6967
- approx_tokens: 1742
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

- Stable file identity and sharing semantics differ between Windows and POSIX
- Only explicitly reviewed formats may be collected; adding a new source type
- The source-read and staged-output paths are locally adversarially green;
- POSIX can detect a concurrent writer through before/after metadata but does
- Native GUI diagnostic export remains deferred; enabling the canonical
- `run.execute`, real Factorio isolation, Safe beta, setup mutation,

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
