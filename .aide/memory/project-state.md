# FacMan Project State

Generated from `release/index/project_status.v2.toml`, the workspace lock,
the command/refusal registries, and the support matrix. Edit those canonical
inputs, then run `py -3 tools/project_state.py --write`.

## Current

- product version: `0.1.0-dev`;
- completed wave: `m2`;
- checkpoint: `m2-closeout-candidate`;
- active WorkUnit: `M2-CLOSEOUT-CANONICAL-PROMOTION-01`;
- last closed WorkUnit: `M2-WU10-AUTOMATED-ACCEPTANCE-RESULT-02`;
- next authority gate: `H1`;
- H1 candidate: `eb629caaec9d62536a272336e940c0d3003fdaae`;
- accepted integration evidence: `73bec99916d509b0ab055a43562e93ef20a6b4b7`;
- Universal Launcher pin: `7bd4425f0c35414f738159b45d8bec42edf70235`;
- Universal Setup pin: `3f8489275077347c2918f3bb03614ec6431362ff`;
- execution: `unavailable` / `steam_external_state_not_isolated`;
- operator verdict: `Fail`;
- Safe beta: `false`;
- release: `unpublished` / `not_proven_unsigned`.
- public SDK: `experimental_installed`; stable compatibility is not promised.
- M1 managed portable install: `fixture_proven`; ordinary setup apply: `unavailable_pending_live_target_acceptance`.
- M1 public integration: `accepted` at canonical main `73bec99916d509b0ab055a43562e93ef20a6b4b7`.
- M2 live portable setup: `complete_machine_pass_pending_canonical_promotion`; technical acceptance: `MachinePass`; human review: `not_required_for_synthetic_non_executable_lane`; ordinary live apply: `candidate_within_machine_accepted_policy_scope`.
- M2-WU1 target policy: `accepted_dev_integration_proof` at Universal Setup main `f322655fa8fa287a400f7afb6c661eade30d707b`; mutation authority: `false`.
- M2-WU2 public lifecycle: `accepted_dev_integration_proof`; operator verdict: `pending`; execution authority: `false`.
- M2-WU3 live evidence: `accepted_dev_integration_proof` at Universal Setup main `fbbeb762f25921ae05945206fd0c004a52239c13`; operator verdict: `pending`; automated verdict authority: `false`.
- M2-WU4 live acceptance: `accepted_dev_integration_proof_pending_operator_verdict` at Universal Setup main `9b8196437e41e45bd8d5a613246dabe5b8cdb968`; run: `m2wu4-20260714-01`; operator verdict: `pending`.
- M2-WU5 interruption recovery: `accepted_dev_integration_proof_pending_operator_verdict` at Universal Setup main `e1ce68e9593ae8d9a35cc0821b5e42c798524453`; run: `m2wu5-20260714-01`; operator verdict: `pending`.
- M2-WU6 Launcher handoff: `accepted_dev_integration_proof_pending_operator_verdict` at Universal Launcher main `7bd4425f0c35414f738159b45d8bec42edf70235`; recovery status: `managed_install_recovery_required`; operator verdict: `pending`.
- M2-WU7 FacMan portable workflow: `accepted_dev_integration_proof_pending_operator_verdict`; plan: `install_local.plan`; apply: `unavailable_pending_operator_acceptance`; operator verdict: `pending`.
- M2-WU8 generated frontend workflow: `accepted_dev_integration_proof_pending_operator_verdict`; clients: `cli, tui, winforms, appkit`; apply: `unavailable_pending_operator_acceptance`; operator verdict: `pending`.
- M2-WU9 adversarial proof: `accepted_dev_integration_proof_pending_operator_verdict`; cases: `16`; Setup main: `3f8489275077347c2918f3bb03614ec6431362ff`; operator verdict: `pending`.
- M2-WU10 operator acceptance: `historical_machine_evidence_ready_pending_operator_verdict`; run: `m2wu10-20260715-01`; operator verdict: `pending`.
- M2-WU10 automated acceptance policy: `accepted_corrected_policy_with_bound_machine_pass`; technical acceptance: `MachinePass`; human review: `not_required_for_synthetic_non_executable_lane`.
- M2-WU10 first automated result attempt: `blocked_before_evidence_pass`; verifier: `fail_closed`; MachinePass: `false`.
- M2-WU10 corrected acceptance candidate: `hosted_validation_passed_bound_to_separate_machine_result`; evidence: `EvidencePass`; MachinePass: `false`.
- M2-WU10 machine acceptance result: `MachinePass`; human review: `not_required_for_synthetic_non_executable_lane`; managed setup: `candidate`.
- M2 closeout: `machine_pass_closeout_pending_exact_dev_and_main_promotion`; dev merge: `5250db1d17ac330f5ae0b672ccc7466431a1e4a2`; canonical main: `pending_dev_to_main_promotion`.
- M3 existing-portable adoption: `authorized_next_wave_pending_m2_canonical_promotion`; scope: `read_only_and_plan_only`; adoption apply: `false`.
- Universal repository licenses: `accepted_mit`; publication authority: `false`.

R3.7, M1, and the bounded M2 technical wave are complete. The exact R3.7 runtime is frozen as the H1 candidate. M2-WU10 records a bounded MachinePass for newly created policy-approved managed targets. No execution, Safe beta, stable SDK, daemon, real-Factorio archive, existing-installation, networking, credential, signing, or publication authority is inferred from that synthetic proof.

## Contract and validation identity

- command contracts: `121`;
- registered routes: `119`;
- schemas: `234`;
- refusal codes: `217`;
- command catalog digest: `7b587bd0b8f3f1317aca52509aa9996d787a075ed6d3b3837dcea44a1ce96c41`;
- accepted CI revision: `2f13923a9cbdd60d47cab114ba1e280282259bb5`;
- CI / CodeQL / security / schema runs: `29299245206` / `29299245093` / `29299245082` / `29297933368`;
- accepted matrix counts: `35` native and `337` Python tests.

## Platform proof

| Platform | Compile | Runtime | Package | Publication | Support |
| --- | --- | --- | --- | --- | --- |
| `linux_portable_cli_x64` | passed | passed | passed | unpublished | candidate |
| `macos_portable_cli_x64` | passed | passed | passed | unpublished | candidate |
| `windows_portable_cli_x64` | passed | passed | passed | unpublished | candidate |
| `windows_portable_tui_x64` | passed | passed | passed | unpublished | candidate |
| `linux_portable_tui_x64` | passed | passed | passed | unpublished | candidate |
| `macos_portable_tui_x64` | passed | passed | passed | unpublished | candidate |
| `windows_legacy_winforms_x64` | passed | passed | contract_only | unpublished | experimental |
| `macos_legacy_appkit_x64` | passed | not_proven | contract_only | unpublished | experimental |
| `linux_x11_gtk_x64` | deferred | deferred | contract_only | unpublished | unavailable |
| `portable_cli_x64` | passed | contract_tested | contract_only | unpublished | experimental |
| `portable_tui_x64` | opt_in_only | not_proven | not_built | unpublished | experimental |

## Quarantined capabilities

- run.execute
- setup mutation outside newly created, explicitly selected, policy-approved managed targets
- network and credential operations
- server and developer process execution
- daemon publication
- release signing, notarization, publication, and publisher authenticity

## Known blockers

- M2 MachinePass closeout is recorded on a task branch; exact-dev proof, canonical main promotion, public integration, and dev synchronization remain incomplete.
- H1 is a human-reviewed Fail for the tested Steam-backed 2.0.77 route; a standalone/manual distribution has no reviewed H1 Pass.
- AppKit remains compile-only until an actual bundle runtime invocation is recorded.
- Artifacts are unsigned and unpublished; integrity and provenance do not authenticate a publisher.

## Authorities

- canonical status: `release/index/project_status.v2.toml`;
- provider revisions: `release/index/workspace_lock.v1.toml`;
- platform proof: `release/index/support_matrix.v1.toml`;
- claim levels and limitations: `docs/quality/safety_claim_ledger.md`;
- immutable accepted evidence: `docs/release/checkpoints/`.
