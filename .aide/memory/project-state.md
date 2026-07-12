# FacMan Project State

Generated from `.aide/memory/project-state.v1.json`; edit the generator or canonical repo truth, not this file.

## Current

- phase: `r3.6-real-world-product-readiness`;
- checkpoint: `r3.5-zero-exception-productization`;
- active WorkUnit: `none`;
- FacMan revision: live `HEAD` (resolve with `git rev-parse HEAD`);
- Universal Launcher pin: `de6c7c6cfa80c524296066bd6bb90a70ba02b760`;
- Universal Setup pin: `4855e4f5dd23ae5dfa0d7f23a61ffbf46e1439d2`.

R3.5 is the architecture endpoint: it records zero manual-JSON and critical-I/O exceptions, 51 command contracts, 49 registered routes, 122 schemas, generated command law, a typed Setup gateway, and a bounded machine protocol. R3.6 uses that foundation for real discovery and frontend product readiness rather than another repository-wide redesign. The public C ABI remains experimental and all recorded packages remain unsigned and unpublished.

## Frozen R3.5 proof

- completed wave revision: `966387280db4eb544e37f1f337c8bcf5d7cec3f4`;
- command catalog digest: `8408499480d1c7bf78f9eab8889b4ae2d867a536c8507606205935a6b70c05ff`;
- machine protocol: bounded newline-delimited JSON over stdio (implemented);

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
- R3.6 target proof must be rerun at the final R3.6 revision; R3.5 target proof remains revision-pinned historical evidence.
- AppKit remains compile-only until an actual bundle runtime invocation is recorded.
- Artifacts are unsigned and unpublished; integrity and provenance do not authenticate a publisher.
- Universal Launcher and Universal Setup licenses remain NOASSERTION pending an operator legal decision.

## Authorities

- claim levels and limitations: `docs/quality/safety_claim_ledger.md`;
- provider revisions: `release/index/workspace_lock.v1.toml`;
- active/next queue: `.aide/queue/index.yaml`;
- immutable completed evidence: `.aide/history/<checkpoint>/index.json`;
- affected validation: `contracts/policy/test_impact.v1.json`.
