# Remaining Risks

- The four migrated commands are locally authoritative through the registered
  route, but exact-SHA cross-platform CI remains pending until this commit is
  pushed.
- No Mod Portal networking, resolver, credential, or download claim is in
  scope.
- Save, instance-transfer, diagnostics, and transaction recovery remain later
  WorkUnits.
- `modsets.lock` still commits two deterministic lock files as separate
  no-clobber writes. Cross-file crash recovery belongs to the later transaction
  WorkUnit and is not claimed here.
- A POSIX hard-link commit whose staging unlink and destination rollback both
  fail reports `archive_commit_state_uncertain`; later recovery must reconcile
  that state rather than infer failure or success.
