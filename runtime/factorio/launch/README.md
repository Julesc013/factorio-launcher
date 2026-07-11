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
- `preflight_launch` parses the exact `config.ini` passed through `--config`,
  verifies the selected install and instance roots, rejects sensitive or linked
  roots, and checks local lock files without starting a process.
- The run-lock helper provides exclusive per-instance ownership, structured
  contention, conservative malformed-lock refusal, and bounded stale recovery.
- The purpose-built test probe owns process-boundary proof. Real Factorio
  spawning remains unavailable pending the operator smoke and human verdict.
