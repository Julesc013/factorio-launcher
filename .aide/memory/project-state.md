# FacMan Project State

Generated from `release/index/project_status.v2.toml`, the workspace lock,
the command/refusal registries, and the support matrix. Edit those canonical
inputs, then run `py -3 tools/project_state.py --write`.

## Current

- product version: `0.1.0-dev`;
- completed wave: `r3.7`;
- checkpoint: `r3.7-public-integration-proof`;
- active WorkUnit: `none`;
- next authority gate: `H1`;
- H1 candidate: `eb629caaec9d62536a272336e940c0d3003fdaae`;
- accepted integration evidence: `d00456069eb509eabf6a63f831aadbd19813413f`;
- Universal Launcher pin: `de6c7c6cfa80c524296066bd6bb90a70ba02b760`;
- Universal Setup pin: `4855e4f5dd23ae5dfa0d7f23a61ffbf46e1439d2`;
- execution: `unavailable` / `real_factorio_isolation_not_proven`;
- operator verdict: `pending`;
- Safe beta: `false`;
- release: `unpublished` / `not_proven_unsigned`.

R3.7 is complete. The exact R3.7 runtime is frozen as the H1 candidate. No execution, Safe beta, SDK, daemon, setup, networking, credential, signing, or publication authority is inferred from the completed non-execution proof.

## Contract and validation identity

- command contracts: `111`;
- registered routes: `109`;
- schemas: `215`;
- refusal codes: `212`;
- command catalog digest: `43fc28256c3b14c6d4fb0c4bd7ea48fed33515878788117bc2a15e0c42f7da86`;
- accepted CI revision: `d00456069eb509eabf6a63f831aadbd19813413f`;
- CI / CodeQL / security / schema runs: `29208144217` / `29208144220` / `29208144246` / `29208144255`;
- accepted matrix counts: `22` native and `314` Python tests.

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
- setup mutation
- network and credential operations
- server and developer process execution
- daemon publication
- release signing, notarization, publication, and publisher authenticity

## Known blockers

- H1 has no reviewed operator verdict.
- AppKit remains compile-only until an actual bundle runtime invocation is recorded.
- Artifacts are unsigned and unpublished; integrity and provenance do not authenticate a publisher.
- Universal Launcher and Universal Setup licenses remain NOASSERTION pending an operator legal decision.

## Authorities

- canonical status: `release/index/project_status.v2.toml`;
- provider revisions: `release/index/workspace_lock.v1.toml`;
- platform proof: `release/index/support_matrix.v1.toml`;
- claim levels and limitations: `docs/quality/safety_claim_ledger.md`;
- immutable accepted evidence: `docs/release/checkpoints/`.
