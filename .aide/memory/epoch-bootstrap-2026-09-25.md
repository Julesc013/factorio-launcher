# Epoch bootstrap working checkpoint (2026-09-25)

## Current branch checkpoint after `562ba502`

- Draft PR #333 remains open on `task/facman-epoch-bootstrap-02`; do not merge
  it yet. The current pushed head is `562ba502dc3a7484541fe30d8c6b1cbe2ecf80bc`.
- Ordinary shell-integrated Setup now reaches the first real epoch; no-shell
  compatibility installs stay flat. Active-epoch repair selection, retirement
  preflight and separate epoch retirement are implemented, with native smoke
  evidence but no successful produced-package receipt at this head.
- `336586f1` adds validated real-epoch retirement completion digests and
  allows a completed predecessor journal when selecting a successor. The
  `562ba502` correction rejects orphan retirement state, tests idempotent
  native retirement, and diagnoses the Windows public repeat-uninstall path.
- CI `36079819746` at `853130b2` built and passed native authority smokes but
  Windows `facman_self_setup_lifecycle` failed: repeated flat uninstall
  returned `self_maintenance_retirement_recovery_required`. CI `36081075283`
  at `336586f1` stopped earlier at a Windows C4456 shadow warning. The
  `562ba502` head corrects that warning; hosted CI is pending. These source
  observations are not produced-package qualification.
- CI `36081612110` at `562ba502` passed Windows compilation and native
  maintenance smokes. Its lifecycle test failed on the *second* flat uninstall
  call, before completion: Setup's initial epoch discovery propagated the
  expected `self_maintenance_retirement_recovery_required` instead of routing
  the pending flat chain to `retire_active`. The current working edit allows
  only that exact recovery status through, refuses mixed epoch namespaces in
  preview, and adds the same orphan-namespace guard at the locked effect
  boundary. The existing integration test covers the two calls and repeat.
- The next executable checkpoint is a passing Windows native lifecycle run,
  followed by a source-exact product candidate. The current edit is
  syntax-checked but not yet committed or hosted-tested.
- The production reinstall path after completed real-epoch retirement remains
  missing even though core successor selection now works. Setup must install
  the new exact provider identity and publish genesis/native ownership through
  recoverable phases. Real-epoch rollback/reapply and source-distinct external
  continuation remain open. The older `b18018cd` candidate is unrelated.

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

## 2026-09-25 successor-install continuation

- Draft PR #333 on `task/facman-epoch-bootstrap-02` reached pushed head
  `8f243a74556638ced9413d063e4142c25b24d32b`. Candidate
  `36083525373` passed its Linux and Intel macOS package jobs and the
  Windows portable, installed workspace, and resource checks, then failed
  Windows real-current-user integration at the first reinstall after a
  registered epoch uninstall. Ordinary Setup had treated retained flat
  history as a live compatibility bootstrap source and refused with
  `self_maintenance_repair_source_missing`.
- The current uncommitted diff plans a content-addressed successor from the
  completed real-epoch retirement and the exact supplied package. Ordinary
  Setup directs its existing durable install transaction to that epoch's
  physical provider identity. It verifies the provider closure and both
  native effects before publishing the immutable epoch and genesis. The
  real-current-user package scenario now previews physical targets and checks
  multiple reinstall/interruption cycles against them. `strict_check.py`,
  Python compilation, C++ syntax checks, and `git diff --check` passed; no
  executable or produced-package result has been observed for this diff.
- Remaining high-risk edges before integration: native and produced-package
  result for this successor path; exact recovery after a successor manifest
  staging interruption; coordinator ownership across Setup completion and
  epoch publication; and source-distinct external continuation through a
  real installed epoch, including rollback/reapply and final removal.
- Pushed successor routing `d5ebe6be` and candidate contract correction
  `0702c4a8`. Candidate `36085551274` stopped at a static contract token;
  the corrected contract suite passed locally (82 tests). Candidate
  `36085806957` passed its contract job, while Linux static/native execution
  reported `facman_self_maintenance_authority_smoke` failure with the
  successor assertion; Windows and macOS candidate work was still running at
  the time of this note. The native failure requires exact diagnostic review
  before any integration claim.
- The next working diff reserves the successor manifest before Setup effects,
  rechecks its exact tail under Setup's singleton lock, and narrowly recovers
  an empty or exact staged successor manifest after interruption. It adds a
  native empty-directory recovery case and diagnostic errors for the failing
  successor assertion. Syntax checks, strict check, focused candidate
  contract tests, and `git diff --check` pass; hosted execution is pending.
- Hosted Linux native at `333e234d` identified the exact successor retry
  fault: the planner held a reference to the tail of a copied epoch vector,
  popped that tail for a published successor, then compared through the
  invalidated reference. The next one-line fix copies the tail before pop.
  The authority smoke includes both prepublication and published retry and
  will be rerun before a new product candidate.
- Candidate harness audit after `4022534b` found the successor preview helper
  had been inserted into the source-distinct function instead of the real
  current-user reinstall function. The real function would have raised a
  missing helper error. A second check found Setup previews report phase
  `plan`, and reserved-epoch validation must run only for apply: previews do
  not publish a reservation. The next correction moves the helper and fixes
  both preview conditions before another package run.
- A further installed-use audit found qualification permits for public repair
  are validated against the user's logical root before the authoritative
  resolver selects the physical active epoch root. The Setup request now
  carries the validated permit through that exact resolver mapping, and the
  real current-user test binds its repair permit to the logical CLI root.
  This correction still requires a produced-package result.
- Candidate `36087467973` at `596dfda2` reached the first interrupted
  successor install but the low-level reservation guard read the user-wide
  coordinator rather than the selected provider state's lifecycle history.
  Commit `c12c6cb1` checks the local lifecycle reservation while retaining
  the user-wide Setup effect lock. Candidate `36088824254` at that commit
  passed Linux/macOS package jobs and Windows native/portable/resource checks,
  then reached `files_applied`; retry was misrouted to first-epoch bootstrap
  because the retired logical root retained a legacy descriptor.
- Commit `91bb5d15` keeps published successor retries on the successor route.
  Static inspection found a second post-Setup fallthrough into first-epoch
  bootstrap; commit `96cbd8e9` gates that block to non-successor installs.
  Candidate `36090196261` is the first dispatched package run including both
  retry corrections and the new source-distinct real-epoch journey. No
  success receipt exists yet for the corrected resume or external transition.
- The new journey starts ordinary Alpha.6 Setup from its own overlay, requires
  a real genesis epoch, downgrades through its installed helper to the exact
  Alpha.5 package, reapplies Alpha.6, and retires the epoch. It is expected
  to expose the still-open retained-generation reapply limitation: epoch
  preparation currently requires an absent target, and public epoch rollback
  still refuses. Do not mark maintenance complete until that behavior and
  interruption/restart are implemented and qualified from produced packages.
- Candidate `36090196261` at `96cbd8e9` passed Linux/macOS package jobs and
  Windows native/portable/resource checks. The produced Windows current-user
  journey passed interrupted successor resume, repeated successor installs,
  and repair. Its foreign-file uninstall check failed. The retained resource
  artifact contains `real current-user integration/windows-real-current-user-
  integration.v1.json`: the foreign note remained and native integration was
  unchanged, but Setup wrote another journal before provider apply refused
  with `self_maintenance_retirement_recovery_required`. The planned preflight
  did not inventory unknown files. The current working correction verifies
  each generation read-only in retirement preflight and at effect-boundary
  reinspection, returning `foreign_content_review_required` before intent.
- Candidate `36091852510` at `e4d35384` passed Linux/macOS package jobs and
  Windows native/portable/resource checks, then stopped in the Windows
  current-user foreign-file assertion. The retained Windows resource artifact
  `10846695252` shows the preflight now returned
  `self_setup_provider_refused`, kept the foreign note and native state, and
  left the Setup journal count at two. The CLI response's `detail` was empty
  because the new refusal constructed `Error` with its third constructor
  argument, which is `path`, not `detail`. The pending correction uses
  `setup_error_with_detail` for this refusal and the inventory-error diagnostic.
  This candidate did not run the source-distinct external journey.
- Candidate `36092903174` at `56bcc314` retained a passing Windows current-user
  receipt in resource artifact `10846443028`; the foreign refusal included
  `detail=foreign_content_review_required`. Its requested final Alpha.5
  baseline `a7a518db` had different provider-lock bytes, so the optional
  source-distinct runner stopped before building the predecessor.
- Alpha.5 ancestor `94f5eccd822a9076e32310355542b36d707752c9` has the exact
  current provider lock and self-maintenance package source. Candidate
  `36093863511` built its source-distinct Alpha.5 package and passed the flat
  A-to-B-to-A-to-B transition. The separate ordinary real-epoch install then
  failed with USK `native_path_limit_exceeded`: the candidate fixture had only
  eight UTF-16 code units of flat-path headroom, while its nested epoch fixture
  added more than that. Setup had already written `10-clone-entered` and
  reported recovery-required. Pending corrections shorten the marker-owned
  disposable fixture, measure the longest epoch path before building the
  predecessor, and run a read-only provider clone plan before any bootstrap
  reservation or provider-entry journal. External continuation remains unrun.
