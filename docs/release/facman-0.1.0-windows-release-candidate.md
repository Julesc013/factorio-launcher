# FacMan C1 / 0.1.0-alpha Windows candidate template

This document currently describes the C1 internal-alpha Windows candidate. It
is a retained input to, not a claim of, the complete public `0.1.0` beta. A
public-beta candidate must additionally close every admitted backend,
CLI/TUI/WinForms, package, accessibility, documentation, support, and human
receipt row in the canonical milestone matrix.

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

- Live Play remains unavailable until the separately controlled exact Windows
  route passes revalidation, capability registration, promotion, and packaged
  acceptance.
- The current candidate is unsigned and unpublished.
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
