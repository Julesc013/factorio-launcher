# Epoch bootstrap working checkpoint (2026-09-25)

Work item: `FACMAN-0.1-ALPHA6-SELF-MAINTENANCE-01`. This is a local working
checkpoint, not product qualification or authority to publish.

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
- Epoch uninstall still explicitly refuses in `apps/setup/main.cpp`; epoch
  rollback still refuses in Setup and the epoch planner requires an absent
  target. These consumers must be implemented and tested before bootstrap can
  be integrated as an ordinary installed path. Existing current-user package
  lifecycle tests assume flat uninstall and need corresponding updates.
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
