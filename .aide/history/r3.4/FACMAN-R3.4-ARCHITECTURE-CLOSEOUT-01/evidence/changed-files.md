# R3.4 closeout changed files

- `tests/test_archive_dependency_admission.py`: selects Miniz by stable SBOM
  component identity.
- Windows platform, package, archive, diagnostics, mod, and modset sources:
  clear GCC 15 warnings without changing capability policy.
- `tests/native/fl_archive_core_smoke.cpp`: includes its direct algorithm
  dependency.
- `tools/project_state.py`, generated project state, and `docs/roadmap.md`:
  reconcile completed compliance and remaining target-runner/provider-license
  holds.
- `.aide/queue/next/FACMAN-R3.4-TARGET-RUNNER-PROMOTION-01/`: preserves the
  external runner handoff.
- `.aide/scripts/aide_lifecycle.py` and R3.4 archive status records: keep
  evidence paths truthful after queue and history moves, with regression proof.
- `docs/release/checkpoints/r3.4-architecture-consolidation.md`: pins the local
  closeout evidence and non-promotions.

No provider repository, workflow, tag, release, signature, publication target,
or real Factorio execution surface was changed.
