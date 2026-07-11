# Remaining Risks

- Journal durability and directory flush behavior differ across Windows,
  Linux, and macOS and must be stated precisely rather than described as
  universal power-loss atomicity.
- Recovery must treat a complete target as authoritative even when journal
  finalization is missing.
- Network/shared filesystems remain outside this WorkUnit.
- Diagnostics, `run.execute`, real Factorio isolation, Safe beta, setup
  mutation, signing, release, and publication remain quarantined.
