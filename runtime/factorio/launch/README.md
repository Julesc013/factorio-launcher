# Launch

Launch profile expansion, preflight checks, command construction, and post-run
indexing.

Current implementation:

- `facman::launch_planning` owns launch-plan construction, effective
  configuration, preflight and the dormant permit seam.
- `facman::product_execution` owns only the product-neutral supervised execution
  adapter and depends on launch planning.
- `facman::candidate_policy` owns frozen candidate-plan, stable-manifest and
  evidence-packet semantics. It is not part of the default product model.
- `facman::candidate_projection` binds instance/install observations to the
  candidate policy and is likewise excluded from default product composition.
- `facman::play_observer`, `facman_play_evidence_classification` and
  `facman_gate4c_verdict_harness` are operator-only test targets gated by
  `FACMAN_BUILD_PLAY_EVIDENCE_TOOLS`.
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
- `flb_factorio_execution.*` adapts the product-neutral process supervisor,
  journals the versioned launch lifecycle, and reconciles interrupted sessions.
- The purpose-built fake process owns process-boundary proof. Its test-only
  authority does not promote either real Factorio execution mode; those remain
  unavailable pending their separate real-play gates and human verdicts.
- `flb_factorio_launch_static` remains only as an internal compatibility
  aggregate. New code must depend on the narrow namespaced target.
- `flb_factorio_launch_permit.*` is the Gate 3 dormant owning-provider seam.
  It obtains a fresh validation context through a provider-controlled callback,
  independently validates it, and atomically consumes only the exact
  `foundation.factorio-permit-proof` permit. It explicitly rejects
  `instance.play`, non-menu intent, non-hermetic proof mode, process effects,
  and the wrong audience. It does not reference the process supervisor or
  expose execution authority.
