# Remaining Risks

- Stable file identity and sharing semantics differ between Windows and POSIX
  and must be represented without claiming universal race freedom.
- Only explicitly reviewed formats may be collected; adding a new source type
  requires a new format-policy test rather than a generic text fallback.
- A diagnostic archive can be enabled only after both the source-read and
  staged-output paths pass adversarial proof on the exact revision.
- `run.execute`, real Factorio isolation, Safe beta, setup mutation,
  networking, credentials, signing, release, and publication remain outside
  this WorkUnit.
