# World backup remaining gates

- Independent high-risk review, exact-head candidate runs on Windows, Linux,
  and Intel macOS, and dev integration remain open. The local package was
  built from dirty source and is not a release candidate.
- The available-space preflight is implemented and write failures are typed,
  but low-space host behavior has not been reproduced in a package test.
- Source consistency is enforced by a pinned object, repeat SHA-256 reads,
  path identity and modification time checks. A hostile writer that changes
  and restores both bytes and timestamps during the narrow final interval is
  beyond this observed proof; native save-write locks are relied upon for
  ordinary managed sessions.
- Publication uses the existing owned staging and no-clobber path operation.
  Held directory identity and workspace ownership are revalidated immediately
  before and after it, but a parent namespace swap exactly inside that effect
  boundary has not been exercised on all hosts.
- World restore, retention, and cross-platform native GUI use are separate
  successor outcomes; this slice does not close them.
