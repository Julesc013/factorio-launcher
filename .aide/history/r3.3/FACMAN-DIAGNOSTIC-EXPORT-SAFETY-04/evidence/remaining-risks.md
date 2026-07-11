# Remaining Risks

- Stable file identity and sharing semantics differ between Windows and POSIX
  and must be represented without claiming universal race freedom.
- Only explicitly reviewed formats may be collected; adding a new source type
  requires a new format-policy test rather than a generic text fallback.
- The source-read and staged-output paths are locally adversarially green;
  exact-SHA Linux, Windows/package, macOS archive, and AppKit CI is pending.
- POSIX can detect a concurrent writer through before/after metadata but does
  not deny writes as the Windows sharing mode does.
- Native GUI diagnostic export remains deferred; enabling the canonical
  backend does not add GUI path/instance selection UX.
- `run.execute`, real Factorio isolation, Safe beta, setup mutation,
  networking, credentials, signing, release, and publication remain outside
  this WorkUnit.
