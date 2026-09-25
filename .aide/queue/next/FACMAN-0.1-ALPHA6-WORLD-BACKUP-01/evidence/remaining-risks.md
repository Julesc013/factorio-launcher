# World backup remaining gates

- Independent high-risk review, an exact-head candidate for the external-path
  correction, and dev integration remain open. Run `36125970801` passed all
  candidate jobs at earlier head `73d67389`; it does not qualify this change.
- The available-space preflight is implemented and write failures are typed,
  but low-space host behavior has not been reproduced in a package test.
- Source consistency is enforced by a pinned object, repeat SHA-256 reads,
  path identity and modification time checks. A hostile writer that changes
  and restores both bytes and timestamps during the narrow final interval is
  beyond this observed proof. Backup now checks the production `run.lock`
  before and after staging, while ordinary managed sessions use that lock.
- Publication uses an owned staging root and no-clobber path operation under
  the existing, pinned parent explicitly selected by `--to`. The source
  workspace remains owned. Held directory identity and workspace ownership are
  revalidated immediately before and after publication, but a parent namespace
  swap exactly inside that effect boundary has not been exercised on all hosts.
- World restore, retention, and cross-platform native GUI use are separate
  successor outcomes; this slice does not close them.
