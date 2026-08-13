# Same-binary TUI parity closeout checkpoint

Status: active bounded closeout; terminal-boundary implementation and local
Windows evidence are complete on the task branch, while exact-head hosted
qualification and the remaining ordinary product/fault cells are pending.

## Identity and authority boundary

- WorkUnit: `FACMAN-SAME-BINARY-TUI-PARITY-CLOSEOUT-01`
- branch: `task/facman-same-binary-tui-parity-closeout-01`
- exact qualified base: FacMan `dev@af3c27232b04b692f6749bcb52cec2a4f4cd901a`
- base result: PR #146 provider adoption integrated; all seven merge-head
  workflow groups passed
- canonical ULK main pin: `09f0639ab6529fba2f2aa22e9bf68e5eebed0553`
- canonical USK pin: `32488fc13bd2439f9f6e52e83a97f6da345a7650`

The closeout grants no Factorio execution, Setup mutation, daemon, signing,
publication, release, frontend-local state authority, or broader provider SPI.
The portable AIDE task surfaces remain intentionally absent from the Lite Pack;
the tracked release plan is the WorkUnit definition.

## Implemented terminal boundary

The product-owned terminal adapter now has an owning full-screen session guard.
Alternate-screen and cursor state unwind on every C++ return and exception path,
and raw console/termios state unwinds after it. POSIX signal scope converts
`SIGINT` into the same typed cancellation law as Ctrl+C, restores the terminal
before job-control suspension, re-enters it after `SIGCONT`, and returns bounded
shell-style codes after `SIGTERM` or `SIGHUP`. Windows raw input disables
processed Ctrl+C only for the owned session and restores the original console
mode on exit.

Full-screen admission now requires an observed terminal of at least 40 columns
by 12 rows. Initial and resized terminals below that boundary use the mandatory
linear renderer; the application no longer invents a larger viewport. A resize
can leave full-screen mode and continue the same ordinary shell in linear mode.

`terminal_text` supplies dependency-free, bounded UTF-8 decoding, sanitization,
display-cell measurement, and cluster-safe clipping. It preserves combining
sequences, joined emoji and regional-indicator pairs, treats CJK/emoji as wide,
replaces invalid UTF-8, and prevents projected control characters from becoming
terminal escape sequences. Long and narrow output therefore clips by display
cells rather than bytes.

Installation scan intent now receives a fresh bounded request/idempotency
identity for each user activation, while one dispatch retains one key. A later
scan from the same snapshot revision is no longer incorrectly replayed as the
earlier scan. Refresh retains only frontend-local selection identity; name,
version, profile, readiness, and every other descriptive attribute must be
reprojected by the backend.

## Current evidence

- MSVC warnings-as-errors source-provider Debug build: pass.
- native CTest: 44/44 pass.
- terminal capability, product reducer/model, UTF-8 display width, control-text
  sanitization, small-terminal fallback, and action-identity native smokes: pass.
- Python TUI product/foundation suite: 10 tests pass; the POSIX-only receipt is
  correctly skipped on the Windows host.
- live Windows ConPTY: navigation, typed Ctrl+C cancellation, live resize below
  the admitted minimum, full-screen-to-linear handoff, clean exit, and no
  workspace mutation pass against the same `facman.exe`.
- the POSIX PTY suite now specifies Ctrl+C, resize fallback, terminal guard,
  Ctrl+Z suspend/resume, and signal-exit restoration; hosted Linux/macOS results
  are required before this evidence is accepted. The first Linux run exposed a
  headless orphan-process-group case in which `SIGTSTP` was discarded; the
  repaired boundary preserves ordinary `SIGTSTP` job control and falls back to
  resumable `SIGSTOP` only when no `SIGCONT` was observed.
- all output remains under the task-owned
  `E:\Temporary\FacMan\FACMAN-SAME-BINARY-TUI-PARITY-CLOSEOUT-01` build root.

## Remaining acceptance

This checkpoint does not close TUI parity. The remaining required work is:

- pass the complete exact-head Windows, Linux, and macOS hosted matrix;
- expose and prove every Technical Preview ordinary journey cell without using
  Advanced, while preserving Advanced as the exhaustive generated plane;
- prove authoritative ULK Last Run, `outcome_unknown`, `recovery_required`,
  corrupt journal, restart, stale revision, duplicate intent, and pre/post
  dispatch transport-loss equality through CLI JSON, TUI, direct, and process;
- qualify packaged same-binary invocation, redirected/dumb/no-colour/Safe Mode,
  keyboard/focus and screen-reader transcript behavior;
- record startup, refresh, input-to-render, memory, and long-list performance
  budgets and their exact candidate measurements.

Only after those receipts pass may the canonical plan mark
`FACMAN-SAME-BINARY-TUI-PARITY-01` and this closeout complete and advance to the
fake-process Windows existing-install journey.
