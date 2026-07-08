# Launch

Launch profile expansion, preflight checks, command construction, and post-run
indexing.

Current implementation:

- `flb_factorio_launch_plan.*` builds the isolated launch arguments and
  `factorio.launch_plan.v1` JSON used by the native CLI vertical slice.
- `apps/cli/` loads install and instance refs, then delegates launch-plan
  construction here instead of owning the product launch schema directly.
- `preflight_launch` checks executable/config/mod-directory presence and local
  lock files before `run --execute` can spawn a process.
- Process spawning and post-run audit writing are still hosted by the native CLI
  slice, with runtime/platform migration remaining a later hardening target.
