# FacMan Project State

Generated from `release/index/project_status.v2.toml`, the workspace lock,
the command/refusal registries, and the support matrix. Edit those canonical
inputs, then run `py -3 tools/project_state.py --write`.

## Current

- product version: `0.1.0-dev`;
- completed wave: `r3.7`;
- checkpoint: `r3.8-public-integration-proof`;
- active WorkUnit: `none`;
- last closed WorkUnit: `FACMAN-R3.8-STEAM-EXTERNAL-STATE-ISOLATION-REPAIR-01`;
- next authority gate: `H1`;
- H1 candidate: `eb629caaec9d62536a272336e940c0d3003fdaae`;
- accepted integration evidence: `53ffbd6e02f098e0eacda9392131592ba421b90a`;
- Universal Launcher pin: `c43d390efe0db17480f9d0262827659b4ae242dd`;
- Universal Setup pin: `bc5991fb9ada6d9900eeda410bcd19fef98b036a`;
- execution: `unavailable` / `steam_external_state_not_isolated`;
- operator verdict: `Fail`;
- Safe beta: `false`;
- release: `unpublished` / `not_proven_unsigned`.
- public SDK: `experimental_installed`; stable compatibility is not promised.

R3.7 is complete. The exact R3.7 runtime is frozen as the H1 candidate. No execution, Safe beta, stable SDK, daemon, setup, networking, credential, signing, or publication authority is inferred from the completed non-execution proof.

## Contract and validation identity

- command contracts: `111`;
- registered routes: `109`;
- schemas: `218`;
- refusal codes: `213`;
- command catalog digest: `43fc28256c3b14c6d4fb0c4bd7ea48fed33515878788117bc2a15e0c42f7da86`;
- accepted CI revision: `53ffbd6e02f098e0eacda9392131592ba421b90a`;
- CI / CodeQL / security / schema runs: `29282101200` / `29282101171` / `29282101155` / `29282101110`;
- accepted matrix counts: `23` native and `330` Python tests.

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

- H1 is a human-reviewed Fail for the tested Steam-backed 2.0.77 route; a standalone/manual distribution has no reviewed H1 Pass.
- AppKit remains compile-only until an actual bundle runtime invocation is recorded.
- Artifacts are unsigned and unpublished; integrity and provenance do not authenticate a publisher.
- Universal Launcher and Universal Setup licenses remain NOASSERTION pending an operator legal decision.

## Authorities

- canonical status: `release/index/project_status.v2.toml`;
- provider revisions: `release/index/workspace_lock.v1.toml`;
- platform proof: `release/index/support_matrix.v1.toml`;
- claim levels and limitations: `docs/quality/safety_claim_ledger.md`;
- immutable accepted evidence: `docs/release/checkpoints/`.
