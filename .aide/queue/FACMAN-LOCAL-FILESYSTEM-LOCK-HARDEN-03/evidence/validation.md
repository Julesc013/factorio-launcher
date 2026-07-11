# Validation

Result: LOCAL GATES PASS; EXACT-SHA CROSS-PLATFORM CI PENDING.

- Full native Windows build: PASS.
- Native CTest: PASS (9/9).
- Complete Python suite: PASS (221/221, zero skips).
- Strict checks, including the new local-lock checker: PASS.
- AIDE Lite portable suite: PASS.
- Source format and `git diff --check`: PASS.

The native proof covers stable identity presence, active contention, stale
metadata recovery, malformed metadata refusal, hardlink refusal, hostile
unlink/replacement detection where the platform permits it, Windows sharing
prevention where it does not, and renamed-parent detection or prevention.
Python recovery proof confirms a linked recovery lock refuses without changing
the foreign inode.

Linux `flock`/device/inode behavior and macOS compilation/local-filesystem
classification require the exact implementation revision's target matrix.
Shared/network and multi-host filesystems remain unpromoted regardless of that
result.
