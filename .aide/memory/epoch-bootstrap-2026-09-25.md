# Epoch bootstrap working checkpoint (2026-09-25)

Work item: `FACMAN-0.1-ALPHA6-SELF-MAINTENANCE-01`. This is a local working
checkpoint, not product qualification or authority to publish.

## Current continuation (after the initial checkpoint)

- Draft PR #333 now contains `5a164b36`, `ee27dce7`, and `ec92d144`.
  These are pushed checkpoint commits. The earlier "uncommitted" sections below
  describe the initial takeover state and are retained as a chronology.
- `ec92d144` has syntax and strict-check evidence but hosted native/package
  validation is incomplete. Its first Linux native and coverage jobs failed
  during compilation because two test aggregate initializers omitted newly
  added `RetirementRequest` fields under `-Werror`; the current working diff
  fixes those call sites. Windows native tests were still running at this
  checkpoint.
- The current working diff also previews each provider uninstall under the
  held coordinator lock before publishing a retirement-step entered marker.
  This is intended to keep a foreign-file plan refusal retryable. The produced
  package lifecycle test now reads the real epoch genesis record to locate the
  active executable and requires complete epoch retirement. It has not yet
  passed from a produced package.
- The first Windows native run of `ec92d144` compiled but failed its generic
  current-generation-only archive: the metadata classifier had treated that
  compatibility archive as an epoch package and then could not find an offline
  repair ZIP in no-shell mode. The working diff uses the explicit maintenance
  descriptor as the epoch opt-in and tests both current-only and descriptor-only
  archives. The authority smoke also failed on a valid destructive flat
  retirement predecessor; the working diff excludes already removed flat
  generations from that successor's epoch retirement chain.
- Epoch rollback/reapply, successor epoch after completed retirement, and a
  source-distinct external continuation receipt remain open. Do not merge PR
  #333 or claim maintenance acceptance from the old `b18018cd` candidate.
- A later working change keeps no-shell portable Setup on the exact flat route:
  it has neither installed-mode repair-source retention nor native integration
  for epoch cutover. Strict maintenance metadata is still inspected before
  provider effects. The produced shell-integrated candidate must provide the
  bootstrap proof; the static no-shell package test cannot substitute for it.
- The next local change preflights every provider uninstall plan and active
  native identity under the coordinator lock before writing the first epoch
  retirement intent. A foreign file can then refuse a fresh retirement
  without entering an irreversible step; each step is inspected again at its
  effect boundary. This change is syntax-checked but not yet hosted-verified.
- Source-exact product candidate `36078990622` at `b8a8b443` passed its Linux
  and Intel macOS jobs but failed Windows in the native test stage, before
  produced-package installation. The synthetic epoch pre-handoff CLI fixture
  still expected the old unsupported verify/uninstall codes; real authority
  selection now reaches provider inspection and refuses the fixture's missing
  epoch provider state. The working test checks that typed no-effect refusal.

## Branch and integrated baseline

- Takeover branch: `task/facman-epoch-bootstrap-01`; base `origin/dev` was
  `10b42e436f558752f6ab39d4d3976219d023f343`. The six-file bootstrap
  working diff was transferred byte-for-byte to
  `task/facman-epoch-bootstrap-02` from the new integrated `origin/dev`.
- Guard slice commit: `94056d1c59edf3f5fba88269133fed71f168b948`, PR #332.
  It fences direct flat maintenance at epoch effect boundaries. All hosted
  checks passed; PR #332 merged to `dev` as merge commit
  `9361ada9c502f0ce65e75cd11a20c7837beb569c` (the repository disables
  squash and rebase merges). The merged task branch was retired.
- Bootstrap checkpoint `5a164b36` is pushed as draft PR #333. Draft status is
  intentional: the task-to-dev promotion check rejects draft PRs, and this
  checkpoint does not satisfy product acceptance.
- The bootstrap source/test work on `task/facman-epoch-bootstrap-02` includes
  Terra's original header stub. Treat it as a checkpoint awaiting full product
  qualification; it is not an integrated maintenance outcome.

## Current uncommitted implementation

- A distinct `authority-handoff.v1.json` marker binds the exact flat head and
  closes compatibility authority without claiming destructive uninstall.
- `authority-bootstrap.v1` records clone entry, exact clone verification,
  genesis activation, shortcut cutover, registration cutover, and completion.
  The core refuses a second provider apply after an entered clone and accepts
  recovery only after exact inspection.
- Ordinary Setup install now attempts to adopt an exact installed flat source
  and bootstrap the real epoch from its retained package. The provider adapter
  clones under the epoch identity; native cutover uses exact target pins.
- Resolver and public real-epoch active discovery withhold authority until all
  six bootstrap records match. Direct compatibility install checks epoch
  namespace/handoff under the setup lock. Public verify selects the active
  generation identity.
- Core native smoke covers interrupted clone, interrupted registration
  cutover, exact retry, and unproven handoff rejection. Direct setup install
  guard has a native smoke assertion.

## Validation and concrete remaining risks

- `py -3 tools/strict_check.py`, `py -3 .aide/scripts/aide_lite.py test`,
  `git diff --check`, and syntax-only compilation of changed core, Setup, and
  native test translation units passed. `facman_self_setup.cpp` was not syntax
  checked locally because its pinned USK header is not in this checkout.
- Executable native and produced-package tests have not run for the uncommitted
  bootstrap patch. Local builds are gated by workspace hygiene: 13 task roots
  against a maximum of 8; the helper dry run stops on an unmarked old root.
  Direct recursive removal was rejected by automatic approval review. Do not
  work around that rejection by moving builds into unowned roots.
- Work after `ee27dce7` routes real-epoch uninstall through a separate
  coordinator retirement journal. The core combines validated flat and epoch
  installation identities (the genesis package hash is shared, but the
  provider install IDs differ), blocks ordinary selection during retirement,
  and returns no active generation after completion. Setup drives bounded
  per-step retirement to completion in one ordinary uninstall invocation,
  while retaining shared repair sources. This is still uncommitted and has
  syntax-only evidence. It needs executable and produced-package validation.
- Epoch rollback still refuses in Setup and the epoch planner requires an
  absent target. Reinstall after completed epoch retirement also needs a new
  successor epoch and genuine installed-use proof. Existing produced-package
  lifecycle tests exercise reinstall and must be adapted only after the
  product path exists.
- A crash after creation of an epoch directory but before its immutable
  manifest publishes was not recoverable through `publish_lifecycle_epoch`.
  Work after the checkpoint adds narrow recovery for the exact empty or
  fully staged manifest, under the coordinator lock and only after verified
  compatibility handoff. A native fault-injection assertion targets the
  pre-rename edge. Corrupt or foreign partial state still fails closed.
- Hosted Linux native and coverage jobs for checkpoint `5a164b36` compiled
  but failed `facman_self_maintenance_smoke`: legacy genesis adoption lost the
  public compatibility-epoch discovery view. The next working diff restores
  that view through the authoritative resolver while retaining incomplete
  bootstrap refusal. It also exposes the validated real-epoch activation
  lineage (including repeats) for retirement and rollback planning. Those
  edits still need hosted executable validation.
- The same checkpoint's Windows static lifecycle also failed: its generic
  Setup archive has no self-maintenance metadata, so the unconditional
  post-install bootstrap could not retain an exact active package. A later
  working diff classifies valid generic archives separately and keeps their
  exact flat install/retry path; archives containing maintenance identity
  records enter strict bootstrap. This preserves the old generic-package test
  without claiming it proves the produced-package epoch journey.
- A public retry currently relaunches the external continuation helper with a
  fresh `GetTickCount64() + budget` in the original patch. The current working
  diff adds an immutable UTC deadline to newly prepared handoffs, carries it
  through pending discovery and retry, and bounds each helper launch by its
  remaining time. Existing journals without the field remain readable. A
  native smoke assertion covers retry with a later proposed deadline; full
  executable/package validation remains outstanding.
- No real produced-package epoch bootstrap/external continuation receipt
  exists. Candidate `35724336883/1` belongs to `b18018cd` and proves the
  earlier flat path only.

## Resume order

1. Finish epoch uninstall/rollback and partial-publication recovery before
   activating ordinary Setup in a pushed build.
2. Compile/run native tests and add a disposable produced-package test that
   installs, bootstraps, updates via parent-exit continuation, interrupts,
   restarts, repairs, rolls back/reapplies, and uninstalls while preserving
   workspace/history.
3. Dispatch a source-exact candidate and attach its receipts only to that
   source revision; then integrate the coherent bootstrap slice.
