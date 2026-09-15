# Remaining qualification and product risks

This checkpoint keeps `FACMAN-0.1-ALPHA6-SELF-MAINTENANCE-01` active and does
not close its acceptance.

- The pinned Universal Setup provider has no explicit update/downgrade
  primitive that binds old and new source identities with rollback. FacMan
  therefore still exposes only install, verify, repair, and uninstall and keeps
  `automatic_update` excluded from the Windows installer profile.
- The setup/native recovery predecessor remains active until the update path
  has corresponding interruption and rollback qualification.
- Locked-file replacement and an executable restart handoff are not
  implemented or qualified.
- A provider operation whose durable phase is `apply_entered` still requires
  the existing reviewed recovery path when its receipt is unavailable. This
  slice only makes the safe `plan_reviewed` pre-entry state independently
  resumable.
- The new real current-user package cases require the gated Windows candidate
  job before any Start Menu, registry, or produced-package qualification claim.
- Workspace hygiene reported pre-existing unowned task-root, task-root size,
  unmanaged historical worktree, and merged local branch violations. This work
  created no worktree and kept builds in the marker-owned external task root.
