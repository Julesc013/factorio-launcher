# World backup remaining gates

- Final combined-head produced-package candidate, current-head required
  checks, final review, and dev integration remain open. Candidate
  `36175342699` at source correction `07ec7159` had cancellation requested
  before the evidence update.
  Prior candidate `36173342608` failed its Linux parent-swap case at `28f22163`
  and was cancelled. Earlier successful candidates do not qualify this change.
- The available-space preflight is implemented and write failures are typed,
  but low-space host behavior has not been reproduced in a package test.
- Source consistency is enforced by a pinned object, repeat SHA-256 reads,
  path identity and modification time checks. A hostile writer that changes
  and restores both bytes and timestamps during the narrow final interval is
  beyond this observed proof. Backup now checks the production `run.lock`
  before and after staging, while ordinary managed sessions use that lock.
- Publication uses an owned staging root and no-clobber path operation under
  the existing, pinned parent explicitly selected by `--to`. The source
  workspace remains owned. A POSIX parent swap during the test pause is now
  exercised locally and refused before publication; hosted Linux and macOS
  package results remain pending. A namespace swap in the narrow interval
  between the final revalidation and publish call remains a residual race.
- World restore, retention, and cross-platform native GUI use are separate
  successor outcomes; this slice does not close them.
