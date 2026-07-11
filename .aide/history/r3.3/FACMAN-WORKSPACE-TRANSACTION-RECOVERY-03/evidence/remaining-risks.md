# Remaining Risks

- Journal durability and directory flush behavior differ across Windows,
  Linux, and macOS and must be stated precisely rather than described as
  universal power-loss atomicity.
- Recovery preserves a complete target after recorded commit, but an existing
  target without recorded commit remains a manual-audit condition rather than
  being inferred safe.
- Stale recovery locks are deliberately not broken automatically; an operator
  must inspect and remove a demonstrably orphaned lock outside the command.
- `modsets.lock` was not named among the WorkUnit's current journal consumers
  and retains its existing bounded two-file behavior.
- Network/shared filesystems remain outside this WorkUnit.
- Diagnostics, `run.execute`, real Factorio isolation, Safe beta, setup
  mutation, signing, release, and publication remain quarantined.
