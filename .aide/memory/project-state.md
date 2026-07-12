# FacMan Project State

Generated from `.aide/memory/project-state.v1.json`; edit the generator or canonical repo truth, not this file.

## Current

- phase: `r3.7-instance-content-lifecycle-active`;
- checkpoint: `r3.7-baseline`;
- active WorkUnit: `none`;
- implementation revision: live `HEAD` (resolve with `git rev-parse HEAD`);
- integration revision: `29cf22fa15250698b7587a9868737c10f3bcc749`;
- evidence revision: `29cf22fa15250698b7587a9868737c10f3bcc749`;
- Universal Launcher pin: `de6c7c6cfa80c524296066bd6bb90a70ba02b760`;
- Universal Setup pin: `4855e4f5dd23ae5dfa0d7f23a61ffbf46e1439d2`.

R3.5 is the architecture endpoint. R3.6 used that foundation to deliver bounded cross-platform discovery, 58 command contracts, 56 registered routes, 130 schemas, deterministic guidance, generated desktop parity, a functional TUI, and a hermetic non-execution journey rather than another repository-wide redesign. The public C ABI remains experimental and all recorded packages remain unsigned and unpublished.
R3.7 now adds reversible local instance and content management without changing execution authority.

## Frozen R3.6 proof

- completed wave revision: `fc8423572e9c055991558f8a4e7cbbc95e0c4a24`;
- command catalog digest: `8bc0dd0e9ad16acd34c9d8fc992407b46f5627b50b714e1311f79f5ceb274d2b`;
- machine protocol: bounded newline-delimited JSON over stdio (implemented);
- clean R3.7 baseline: PASS in 166.5 seconds;

## Structured artifact evidence

- `facman-0.1.0-dev.contract-windows-cli-x64-portable.zip`: checkpoint `r3.5-zero-exception-productization`, revision `a4f28b8155ed3f79ea217c37886c4c73618d9d0a`, target `windows_portable_cli_x64`, SHA-256 `fba446780e5cb96c4f5afe1b03b59689e1010b2acf9de38257b2f8dc1dfed58b`, authenticity `not_proven_unsigned`;
- `facman-0.1.0-dev.contract-linux-cli-x64-portable.tar.gz`: checkpoint `r3.5-zero-exception-productization`, revision `a4f28b8155ed3f79ea217c37886c4c73618d9d0a`, target `linux_portable_cli_x64`, SHA-256 `f36748ccf436ef1a50e6667c315761d5210d0def559c15951e0f3f4e0f6b6d74`, authenticity `not_proven_unsigned`;
- `facman-0.1.0-dev.contract-macos-cli-x64-portable.tar.gz`: checkpoint `r3.5-zero-exception-productization`, revision `a4f28b8155ed3f79ea217c37886c4c73618d9d0a`, target `macos_portable_cli_x64`, SHA-256 `ed7479529ffe27c58ada5725c842bde8a0bf6c425d3d2accf8fe8377e0d7b706`, authenticity `not_proven_unsigned`;
- `facman-0.1.0-dev.contract-windows-cli-x64-portable.zip`: checkpoint `r3.6-product-readiness`, revision `fc8423572e9c055991558f8a4e7cbbc95e0c4a24`, target `windows_portable_cli_x64`, SHA-256 `2526a5f5d085087301f66d2855a1942d01457cb598c1bf41704388948295b595`, authenticity `not_proven_unsigned`;
- `facman-0.1.0-dev.contract-windows-tui-x64-portable.zip`: checkpoint `r3.6-product-readiness`, revision `fc8423572e9c055991558f8a4e7cbbc95e0c4a24`, target `windows_portable_tui_x64`, SHA-256 `8b87f28e098096dfd6672b1d9701bd227bdfaf99d0d8f5ade9eacb9021ddd3a1`, authenticity `not_proven_unsigned`;

## Quarantined capabilities

- run.execute pending operator-supplied real Factorio verdict
- setup mutation
- network and credential operations
- release signing, notarization, publication, and publisher authenticity
- OS-neutral TUI and daemon publication; target-specific TUI profiles remain package previews

## Proof platforms

- `windows_portable_cli_x64`: runner `windows-2025`, architecture `x86_64`, format `portable_zip`;
- `linux_portable_cli_x64`: runner `ubuntu-24.04`, architecture `x86_64`, format `tarball`;
- `macos_portable_cli_x64`: runner `macos-15-intel`, architecture `x86_64`, format `tarball`;
- `windows_portable_tui_x64`: runner `windows-2025`, architecture `x86_64`, format `portable_zip`;
- `linux_portable_tui_x64`: runner `ubuntu-24.04`, architecture `x86_64`, format `tarball`;
- `macos_portable_tui_x64`: runner `macos-15-intel`, architecture `x86_64`, format `tarball`;

## Known blockers

- Real Factorio isolation remains operator-only and has no human verdict.
- AppKit remains compile-only until an actual bundle runtime invocation is recorded.
- Artifacts are unsigned and unpublished; integrity and provenance do not authenticate a publisher.
- Universal Launcher and Universal Setup licenses remain NOASSERTION pending an operator legal decision.

## Authorities

- claim levels and limitations: `docs/quality/safety_claim_ledger.md`;
- provider revisions: `release/index/workspace_lock.v1.toml`;
- active/next queue: `.aide/queue/index.yaml`;
- immutable completed evidence: `.aide/history/<checkpoint>/index.json`;
- affected validation: `contracts/policy/test_impact.v1.json`.
