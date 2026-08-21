# Validation

Status: in progress.

Completed against the forward-merged worktree:

- `python -B -m unittest tests.test_remote_source_closure tests.test_repro_workspace_smoke`
  — 34 passed after the Windows authority-order repair.
- `python -B tools/schema_validate.py` — PASS, 337 schemas.
- `python -B tools/source_format_check.py` — PASS.
- `python -B tools/successor_play_route_definition_check.py` — PASS.
- `python -B .aide/scripts/aide_lite.py test` — PASS.
- active route selection resolves route v2 and
  `facman.successor-play.source-closure.02` deterministically, but execution
  correctly refuses while the three explicit index gates remain false.
- retained profile-less v1 evidence remains schema-valid as legacy `.01`
  evidence; new `.02` output requires the hardened-v2 proof profile.
- provider revisions and trees, exact canonical remotes, immutable route/index
  records, proof code, schema-validator dependencies, and bounded archive
  identity have focused positive and negative coverage.
- exact-head hosted Linux, macOS, schema, policy, TCK, and CodeQL lanes passed at
  `9116b263...`; both Windows lanes exposed the same deterministic pre-admission
  archive-path ordering defect, which this follow-up repairs without weakening
  archive indirection refusal.

Pending before publication of the updated task head:

- structured commit validation;
- fresh exact-head hosted workflows for the repaired head.

Not attempted and not authorized: native task-ref source-closure execution,
Factorio execution, Setup mutation, signing, publication, or route promotion.
