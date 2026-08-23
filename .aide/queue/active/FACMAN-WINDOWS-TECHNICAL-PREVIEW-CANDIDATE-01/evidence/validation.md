# Validation

## Accepted source

- PR #174 exact head `cbba55662f496603daa329f06117b06918dd8a23`
  passed its clean-clone qualification and merged to protected `dev` as
  `39cf8341d92524cd3a0b7dafbb626bd41514e79e`.
- The merge tree is `b79efe195878dab46235c012f3112b3728ec319c`
  and is byte-identical to the accepted task tree.
- Protected-dev CI, code security, schema, policy, and synthetic provider TCK
  completed successfully.

## Integrated candidate validation

- Session lifecycle focused native presentation and TUI tests pass; focused
  WinForms/TUI Python contracts pass with expected platform skips.
- Release archive, staging, compiler, assurance, structure, and resolution
  tests pass, including deterministic ZIP/TAR.GZ, no-clobber, substitution,
  stale-sidecar, and unsupported-target negative controls.
- The 2.1.14 route packet validator and its negative controls pass without using
  a private Factorio artifact or widening execution authority.
- CI trigger/concurrency proof and workflow validators pass; required protected
  and pull-request contexts remain emitted while task-branch push duplication
  is removed.
- The combined locked Python selection reports 74 passes and one expected
  Windows symlink-privilege skip. All 358 schemas validate.
- Exact clean ULK `5479939ca5cbc9ee0f901608a92012778b4752ae` and USK
  `d2a2aae7e61c47035c92334b0522143b4fea3880` provider clones satisfy the
  architecture-fitness and dependency-revision gates.

The enclosing strict gate is still being rerun against this exact integrated
head. No pass is claimed for the full 29 rows, a native candidate build, a real
Factorio route, or a human accessibility verdict.
