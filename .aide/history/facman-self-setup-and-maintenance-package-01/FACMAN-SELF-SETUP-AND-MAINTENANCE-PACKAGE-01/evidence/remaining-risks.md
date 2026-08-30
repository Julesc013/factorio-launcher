# Remaining risks

- Alpha.2 is an unsigned, unsupported private draft candidate until Jules
  completes exact-hash manual testing on the intended machines.
- No shortcut, uninstall-registry entry, automatic updater, MSI/MSIX, elevated
  per-machine profile, network acquisition, or Factorio mutation is included.
- The setup wrapper intentionally waits for USK's second-resolution lifecycle
  timestamp to advance before an apply receipt; this preserves truthful,
  strictly monotonic audit state for rapid consecutive operations.
- Legacy native tests can exceed old Windows path limits when invoked from an
  unusually deep working directory. Qualification uses the governed stable
  short-drive mapping, and manual-test roots remain under \`C:\FacManTest\`.
- The tag, draft release, and assets do not exist yet; they require exact
  merged-source three-root qualification and download-back verification.
- Alpha.1 must remain a 16-asset private draft with unchanged tag and bytes.
