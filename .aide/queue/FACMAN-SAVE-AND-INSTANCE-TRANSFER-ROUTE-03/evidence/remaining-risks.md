# Remaining Risks

- Save recognition remains explicitly shallower than deep Factorio save
  semantics. This is represented in every typed result and cannot be promoted
  by structural ZIP proof.
- Cross-volume behavior uses destination-volume staging and stable-handle
  copy/verify before a same-volume commit. The interruption path is injected
  deterministically, but a second physical Windows volume was not available in
  the local matrix.
- The subsequent transaction-recovery WorkUnit remains responsible for one
  bounded journal shared by currently enabled multi-file writers.
- The dormant diagnostic bundle still owns the only quarantined hand-written
  stored ZIP writer. It is not reachable as an enabled export and must be
  removed when diagnostics migrates to the production writer.
- Diagnostics, `run.execute`, real Factorio isolation, Safe beta, setup
  mutation, signing, release, and publication remain outside this scope.
