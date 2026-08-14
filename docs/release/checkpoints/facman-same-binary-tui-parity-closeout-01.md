# Same-binary TUI parity closeout checkpoint

Status: active bounded closeout; the terminal boundary is integrated on `dev`
with exact-head qualification complete and merge-head requalification running.
Ordinary backend semantic projection is active; remaining product, fault,
accessibility, and performance cells are not yet closed.

## Identity and authority boundary

- WorkUnit: `FACMAN-SAME-BINARY-TUI-PARITY-CLOSEOUT-01`
- branch: `task/facman-same-binary-tui-parity-closeout-01`
- exact qualified base: FacMan `dev@af3c27232b04b692f6749bcb52cec2a4f4cd901a`
- base result: PR #146 provider adoption integrated; all seven merge-head
  workflow groups passed
- terminal result: PR #147 exact head
  `90e0295cd1e5bc3ae1222bc598861ddc4f6d2ca7` passed 32/32 checks and merged as
  `dev@d12768d59093c7362d246635f69470124642c40e`
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
- the POSIX PTY suite specifies Ctrl+C, resize fallback, terminal guard,
  Ctrl+Z suspend/resume, and signal-exit restoration; exact-head hosted
  Linux/macOS results pass. The first Linux run exposed a
  headless orphan-process-group case in which `SIGTSTP` was discarded; the
  repaired boundary preserves ordinary `SIGTSTP` job control and falls back to
  resumable `SIGSTOP` only when no `SIGCONT` was observed.
- all output remains under the task-owned
  `E:\Temporary\FacMan\FACMAN-SAME-BINARY-TUI-PARITY-CLOSEOUT-01` build root.

## Ordinary semantic projection slice

The follow-on `task/facman-tui-ordinary-semantic-parity-01` branch preserves
the reviewed terminal history and normally merges exact
`dev@d12768d59093c7362d246635f69470124642c40e`. Its feature revision is
`15f0981a5580a5a2dbda9750f528bd36357bb886`; the forward-integration revision
is `92a048d4eefd0db5cbf4b6848e61e37caaede0e3`.

This slice adds `content`, `saves`, and `settings_support` as first-class
`presentation.query` scopes. The backend projects profiles and selected
instance modset status, selected-instance save inventory, process-lifetime
validated preferences, support context, and exact runtime identity. Search,
selection, blockers, actions, revision, freshness, and authority remain in the
same immutable snapshot. The TUI now routes its Content, Saves, and Settings
pages to those scopes and uses `presentation.refresh` as their contextual
read-only action; it no longer instructs users to use Advanced for ordinary
inspection.

The schema enum, generated CLI grammar, completions, command catalogues, native
frontend metadata, and request validators are regenerated from the same source.
The slice passes a canonical source-provider Release build, 44/44 native tests,
seven presentation/TUI process tests, generated-metadata validation, and schema
validation. It grants no new write, process, Setup, daemon, signing,
publication, or release authority.

## Ordinary action-dispatch slice

The stacked `task/facman-tui-ordinary-actions-01` branch builds on the exact
semantic-projection head. Its feature revision is
`17288581f7fa5368665cfb49f234f6ecbf559825` and its draft review shell is PR
#149. It introduces no page-specific product command table in the terminal
adapter. Instead, the TUI renders the ordered `available_semantic_actions`
supplied by the backend, retains the selected action identity across an
authoritative refresh, cycles actions with Tab and Shift+Tab, and dispatches
the selected action with Space. Enter remains item selection/opening, so item
and action intent are not conflated.

Every dispatch uses `presentation.action` with the scope-bound snapshot
revision, a fresh request ID and idempotency key, and the selected-instance
identity when present. Availability and refusal remain backend decisions. The
first useful ordinary action is read-only Doctor: the presentation service
advertises it on the Launch Deck, invokes the existing diagnostic handler, and
returns the diagnostic report as the typed semantic-action payload. Linear and
full-screen renderers expose the same action set; direct and process transports
produce the same Doctor result. A returned replacement snapshot is validated
against the active scope and reduced immediately; backend invalidation requests
instead trigger a fresh query. No execution or workspace-write action is
admitted by this slice.

The exact feature revision passes a canonical adopted-provider Release build,
44/44 native CTest, four TUI product process tests, and three presentation
process tests. The complete 1,004-test Python census passed every product and
policy check; its single default-build-path setup error was rerun against the
exact external build, where all 17 package artifact tests passed with two
declared not-applicable skips.

## Remaining acceptance

This checkpoint does not close TUI parity. The remaining required work is:

- expose and prove every Technical Preview ordinary journey cell without using
  Advanced, while preserving Advanced as the exhaustive generated plane; the
  Content, Saves, and Settings read projections are now implemented, but their
  admitted write journeys and the remaining workspace/instance/session cells
  still require closure; read-only Doctor dispatch is implemented on the
  stacked action slice but is not yet canonical;
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
