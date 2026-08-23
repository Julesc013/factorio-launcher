# FacMan 0.1.0-alpha.1 Windows prerelease template

This document describes the allocated unsupported `0.1.0-alpha.1` Windows
prerelease source. It is not a claim of the complete public `0.1.0` beta. A
beta candidate must additionally carry the exact completed human receipt and
accepted limitations required by the canonical milestone matrix.

This document travels inside the Windows 10/11 x64 portable candidate. The
candidate contains the native WinForms shell, bounded-process FacMan backend,
pinned Universal Launcher and Universal Setup closure, contracts, Factorio
content binding, SBOM, exact source identity, hashes, licenses, and notices.

The normal startup mode reads presentation state from the backend. Deterministic
fixtures are available only when `FACMAN_PRESENTATION_MODE=evidence` is selected
explicitly; evidence mode is labelled in the shell and grants no Play authority.

## Support export

Use Advanced or the packaged CLI command
`facman diagnostics export --instance <instance-id> --out <bundle.zip> --json`.
Review diagnostic bundles before sharing them. Diagnostic redaction and the
absence of repository/development paths are release-qualification requirements.

## Known limitations

- Public alpha publication remains unavailable until the exact packaged
  Factorio 2.1.14 Play-to-menu, exit, Last Run, relaunch, and immutability route
  passes and separate tag/publication authority is active.
- The release source is allocated, but the current alpha.1 package is not yet
  constructed. The eventual alpha may remain unsigned only with explicit
  disclosure.
- Windows 10 and Windows 11 clean-machine, non-administrator, relocation,
  keyboard, Narrator, Accessibility Insights, high-contrast, and 100/150/200%
  scaling evidence must be recorded before the supported release claim.
- Closing a frontend does not cancel or rewrite backend operation state; inspect
  Activity and recovery after restarting the shell.
- Stale readiness is never retried automatically and interrupted work is never
  recovered or relaunched automatically.

The macOS AppKit and Linux GTK packages are separate preview claims and are not
qualified by this Windows candidate.

No inclusion of this document assigns a beta, RC, or stable release identity,
or grants Factorio execution, Setup mutation, signing, publication, support,
route capability, or route promotion.
