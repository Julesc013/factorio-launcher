# FacMan Project State

Generated from `release/index/project_status.v2.toml`, the workspace lock,
the command/refusal registries, and the support matrix. Edit those canonical
inputs, then run `py -3 tools/project_state.py --write`.

## Current

- product version: `0.1.0-dev`;
- completed wave: `r3.7`;
- checkpoint: `universal-mit-license-integration`;
- active WorkUnit: `M2-WU1-LIVE-TARGET-POLICY-01`;
- last closed WorkUnit: `M1-PUBLIC-INTEGRATION-PROOF-01`;
- next authority gate: `H1`;
- H1 candidate: `eb629caaec9d62536a272336e940c0d3003fdaae`;
- accepted integration evidence: `73bec99916d509b0ab055a43562e93ef20a6b4b7`;
- Universal Launcher pin: `6d41e07b76cd19b2a7630835e05ac3aa125d57b8`;
- Universal Setup pin: `264bb1939a67231878313155157abd0f83d24c13`;
- execution: `unavailable` / `steam_external_state_not_isolated`;
- operator verdict: `Fail`;
- Safe beta: `false`;
- release: `unpublished` / `not_proven_unsigned`.
- public SDK: `experimental_installed`; stable compatibility is not promised.
- M1 managed portable install: `fixture_proven`; ordinary setup apply: `unavailable_pending_live_target_acceptance`.
- M1 public integration: `accepted` at canonical main `73bec99916d509b0ab055a43562e93ef20a6b4b7`.
- M2 live portable setup: `active_policy_contract`; operator verdict: `pending`; ordinary live apply: `unavailable_pending_operator_acceptance`.
- Universal repository licenses: `accepted_mit`; publication authority: `false`.

R3.7 is complete. The exact R3.7 runtime is frozen as the H1 candidate. M1 is independently fixture-proven for managed portable setup. No execution, Safe beta, stable SDK, daemon, live-target setup, networking, credential, signing, or publication authority is inferred from the completed non-execution proof.

## Contract and validation identity

- command contracts: `121`;
- registered routes: `119`;
- schemas: `228`;
- refusal codes: `216`;
- command catalog digest: `76410c383ec5e0dc5393f04bb142b1c752e152eae59bfa7b1a5f28040c5e4222`;
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
- setup mutation outside fixture, disposable, and package-proof roots
- network and credential operations
- server and developer process execution
- daemon publication
- release signing, notarization, publication, and publisher authenticity

## Known blockers

- H1 is a human-reviewed Fail for the tested Steam-backed 2.0.77 route; a standalone/manual distribution has no reviewed H1 Pass.
- AppKit remains compile-only until an actual bundle runtime invocation is recorded.
- Artifacts are unsigned and unpublished; integrity and provenance do not authenticate a publisher.

## Authorities

- canonical status: `release/index/project_status.v2.toml`;
- provider revisions: `release/index/workspace_lock.v1.toml`;
- platform proof: `release/index/support_matrix.v1.toml`;
- claim levels and limitations: `docs/quality/safety_claim_ledger.md`;
- immutable accepted evidence: `docs/release/checkpoints/`.
