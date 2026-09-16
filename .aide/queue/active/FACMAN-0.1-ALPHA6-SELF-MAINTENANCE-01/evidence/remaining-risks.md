# Remaining qualification and product risks

This checkpoint keeps `FACMAN-0.1-ALPHA6-SELF-MAINTENANCE-01` active and does
not close its acceptance.

- FacMan now owns the public side-by-side update/downgrade/rollback transition
  and the pinned production provider bridge while keeping Universal Setup
  whole-root `update.*` outside its effect surface. The source transition uses
  distinct digest-bound roots/install IDs, verifies a candidate before exact
  shell cutover, retains old roots, and appends immutable generation/activation
  records. Complete package and real-shell qualification remain pending.
  `automatic_update` stays excluded from the Windows installer profile.
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

## Public setup and pinned-provider checkpoint limits

The public verbs, strict package/active-state discovery, deterministic legacy
genesis, pinned install-local provider bridge, exact verification binding, and
Windows cutover composition are now implemented and focused-tested. The
WorkUnit remains active because the following product evidence and behavior are
still absent:

- complete Python and produced-product qualification;
- two source-distinct packaged update/downgrade inputs with durable receipts;
- real current-user Start Menu and HKCU registration update/rollback effects;
- a packaged parent-exit and retained-helper resume lifecycle;
- side-by-side active repair, multi-generation removal, activation-chain
  retirement, retention pruning, and garbage collection.

Generic uninstall now refuses every installation with an activation chain,
including migrated legacy state. Generic verify also refuses a chain, and
repair accepts only a provider-inspected and provider-verified active migrated
`facman.self`. These refusals remain until the missing chain-aware operations
are implemented.

The isolated no-shell public journey uses explicit qualification roots and
synthetic package fixtures. It demonstrates public routing and durable state
transitions, but it does not qualify supported package profiles or real shell
effects. The previously rejected cleanup of marker-owned task root
`D:\Development\FacMan\repositories\factorio-launcher-5db2844e2f29\tasks\task-facman-s-469a894f69`
was not retried; cleanup remains an operator/root-agent action.
