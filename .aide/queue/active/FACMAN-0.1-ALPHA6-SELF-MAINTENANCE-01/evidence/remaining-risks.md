# Remaining qualification and product risks

This checkpoint keeps `FACMAN-0.1-ALPHA6-SELF-MAINTENANCE-01` active and does
not close its acceptance.

- FacMan now owns a side-by-side update/downgrade/rollback transition and keeps
  Universal Setup whole-root `update.*` outside its effect surface. The source
  transition uses distinct digest-bound roots/install IDs, verifies a candidate
  before exact shell cutover, retains old roots, and appends immutable
  generation/activation records. Public setup command routing and the concrete
  production provider bridge remain the next slice. `automatic_update` stays
  excluded from the Windows installer profile.
- The setup/native recovery predecessor remains active until the update path
  has corresponding interruption and rollback qualification.
- The Windows inherited-process-handle primitive and exact shortcut/registry
  cutover are implemented and covered by focused native fixtures. The helper
  image and journal stay pinned against writes/deletion across process creation,
  the child remains suspended until their post-create admission succeeds, and
  the helper consumes the original absolute deadline. Refusal distinguishes
  confirmed process exit from cleanup outcome unknown and preserves the spawned
  PID in either post-create result. A complete packaged retained-helper
  parent-exit/resume candidate run is not yet qualified.
- A provider operation whose durable phase is `apply_entered` still requires
  the existing reviewed recovery path when its receipt is unavailable. This
  slice only makes the safe `plan_reviewed` pre-entry state independently
  resumable.
- The new real current-user package cases require the gated Windows candidate
  job before any Start Menu, registry, or produced-package qualification claim.
- Workspace hygiene reported pre-existing unowned task-root, task-root size,
  unmanaged historical worktree, and merged local branch violations. This work
  created no worktree and kept builds in the marker-owned external task root.

This source checkpoint does not establish human or supported-platform
acceptance. It also does not yet provide multi-generation repair/removal or
retention pruning, so both maintenance WorkUnits remain active.
