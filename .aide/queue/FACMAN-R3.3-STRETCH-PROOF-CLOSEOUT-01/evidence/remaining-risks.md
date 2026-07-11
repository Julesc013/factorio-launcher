# Remaining Risks

- Real Factorio write isolation still requires the prepared operator procedure
  and an explicit human Pass, Fail, or Inconclusive verdict.
- `run.execute`, Safe beta, setup mutation, general GUI expansion, signing,
  notarization, release creation, and publication remain unavailable.
- Local lock proof excludes shared/network and multi-host filesystems.
- macOS proof covers Intel `macos-15-intel`, deployment target 13.0, and the
  recorded toolchain only; Apple Silicon, universal binaries, AppKit runtime,
  and broader macOS versions remain unproven.
- Unsigned provenance records inputs and identities but does not authenticate a
  publisher.
