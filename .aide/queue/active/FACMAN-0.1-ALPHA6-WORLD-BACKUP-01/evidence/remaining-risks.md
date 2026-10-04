# World backup remaining gates

- The combined-source candidate `37172494677/1` passed with six exact assets
  at source `803bd98af05c7343977934a7c1b21c67ed897720`, tree
  `0a038464f24deb5ff946b091dd7b48a78a0ed995`. Its produced Linux CLI passed
  all 19 save-transfer tests and real low-space refusal/same-target recovery;
  its Windows CLI passed the new same-object write regression. Independent
  runtime review passed. Current-head required checks, normal dev integration
  and canonical acceptance closeout remain open. Prior failed/cancelled
  candidates and failed local extraction attempts remain retained.
- Real low-space refusal and recovery now pass against an admitted produced
  Linux CLI on WSL. The reusable regression exhausts a private 4 MiB tmpfs,
  preserves the source and prior backup/manifest, refuses before effects,
  and successfully retries the identical target after capacity is restored.
  The earlier PR371-tree proof remains in `real-low-space.v1.json`; exact
  final803 delivery-file custody and the additional observed regressions are
  retained in `produced-package-acceptance.v1.json`. Real ENOSPC is observed
  before the backup preflight, rather than during copy or sidecar flush.
- Source consistency is enforced by a pinned object, repeat SHA-256 reads,
  path identity and modification time checks. A hostile writer that changes
  and restores both bytes and timestamps during the narrow final interval is
  beyond this observed proof. Backup now checks the production `run.lock`
  before and after staging, while ordinary managed sessions use that lock.
- Publication uses an owned staging root and no-clobber path operation under
  the existing, pinned parent explicitly selected by `--to`. The source
  workspace remains owned. A POSIX parent swap during the test pause is now
  exercised against the produced Linux CLI and refused before publication;
  the final803 macOS candidate's native save-transfer lane also passed. A namespace swap in the narrow interval
  between the final revalidation and publish call remains a residual race.
- World restore, retention, and cross-platform native GUI use are separate
  successor outcomes; this slice does not close them.
- The additional regression changes only tests and evidence. Final803 assets
  retain their actual source revision; they are not represented as packages
  built from a later commit, nor as proof of reproducible bytes. Final release
  qualification still requires its own exact delivery files.
