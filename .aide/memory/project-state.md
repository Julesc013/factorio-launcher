# FacMan Project State

Generated from `.aide/memory/project-state.v1.json`; edit the generator or canonical repo truth, not this file.

## Current

- phase: `r3.4-architecture-consolidation`;
- active WorkUnit: `FACMAN-R3.4-ARCHITECTURE-CLOSEOUT-01`;
- FacMan revision: live `HEAD` (resolve with `git rev-parse HEAD`);
- Universal Launcher pin: `80a848375227dc858865874ef594c4b466877241`;
- Universal Setup pin: `4855e4f5dd23ae5dfa0d7f23a61ffbf46e1439d2`.

R3.4 consolidates the native architecture, install-tree packaging, test proof, AIDE state, and supply-chain policy. Commands use the authoritative Universal Launcher route. Windows read-only discovery is implemented and must not be scheduled again. The public C ABI remains experimental. The Windows x64 static-first package proof remains unsigned and unpublished.

## Quarantined capabilities

- run.execute pending operator-supplied real Factorio verdict
- setup mutation
- network and credential operations
- release signing, notarization, publication, and publisher authenticity
- experimental TUI and daemon publication

## Proof platforms

- `windows_portable_cli_x64`: runner `windows-2025`, architecture `x86_64`, format `portable_zip`;
- `linux_portable_cli_x64`: runner `ubuntu-24.04`, architecture `x86_64`, format `tarball`;
- `macos_portable_cli_x64`: runner `macos-15-intel`, architecture `x86_64`, format `tarball`;

## Known blockers

- Real Factorio isolation remains operator-only and has no human verdict.
- Linux sanitizer, libFuzzer, clang-tidy, coverage, and target package results are CI-owned per revision.
- macOS target package proof is CI-owned per revision; AppKit remains compile-only.
- Artifacts are unsigned and unpublished; integrity and provenance do not authenticate a publisher.

## Authorities

- claim levels and limitations: `docs/quality/safety_claim_ledger.md`;
- provider revisions: `release/index/workspace_lock.v1.toml`;
- active/next queue: `.aide/queue/index.yaml`;
- immutable completed evidence: `.aide/history/<checkpoint>/index.json`;
- affected validation: `contracts/policy/test_impact.v1.json`.
