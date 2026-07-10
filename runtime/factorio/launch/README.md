# Launch

Launch profile expansion, preflight checks, command construction, and post-run
indexing.

Current implementation:

- `flb_factorio_launch_plan.*` owns the one canonical launch-argument builder,
  typed launch-plan and preflight results, and their boundary JSON encoders.
- `runtime/factorio/application/` loads install and instance refs, builds typed
  results here, and returns them through registered `launch_plan.build`,
  `launch_plan.preflight`, and `run.preview` handlers.
- `apps/cli/` parses aliases and renders the routed result. It does not load
  backend state or construct launch arguments for the migrated preview path.
- `preflight_launch` checks executable/config/mod-directory presence and local
  lock files without starting a process.
- Process spawning and post-run audit writing are still hosted by the native CLI
  slice, with runtime/platform migration remaining a later hardening target.
