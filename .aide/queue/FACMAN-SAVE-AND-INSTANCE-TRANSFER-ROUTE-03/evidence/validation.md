# Validation

Result: local PASS; exact-SHA cross-platform CI pending.

## Behavior proven locally

- `saves.list`, `saves.backup`, `saves.clone`, `instance.export`, and
  `instance.import` route through canonical ULK descriptors, FLB, and typed
  Factorio application operations.
- CLI `export instance` and `import instance` spellings normalize to canonical
  registry IDs and retain no migrated backend behavior.
- Stored and deflated saves are structurally inspected through the production
  archive core. Recognition requires `level-init.dat`; deep save semantics are
  explicitly never claimed.
- Backup, clone, and export sources are copied from one no-follow handle with
  before/after identity and metadata checks. Multiply linked sources refuse.
  Hashes are calculated from the exact staged bytes.
- File and directory outputs stage under the destination parent, verify before
  no-clobber commit, and therefore use an explicit cross-volume copy/verify/
  same-volume-commit strategy.
- Portable export uses deterministic deflate, redacted metadata, a complete
  file-level SHA-256 closure, and writer self-verification.
- Import validates the complete archive plan and declared closure before
  output, extracts only to owned staging, verifies every staged hash, rewrites
  local config/manifest truth, and commits the directory without overwrite.
- Traversal and tamper cases leave no target. Eight injected interruption
  stages leave no destination before commit or a complete marked destination
  with `transaction_recovery_required` after commit.
- Valid-shaped write dry-runs refuse without mutation; save listing remains
  read-only.

## Local gates

- Full native build: PASS.
- Native CTest: PASS (9/9).
- Complete Python suite: PASS (204/204).
- Save/transfer adversarial suite: PASS (5/5).
- Strict checks: PASS (19 commands, 55 schemas, 79 refusal codes, 23 refusal
  goldens).
- AIDE Lite test: PASS.
- `git diff --check`: PASS.

## Authority boundary

The one remaining hand-written ZIP writer is named and machine-confined to the
still-quarantined diagnostic bundle path. General diagnostics, journaled
recovery, `run.execute`, real Factorio isolation, Safe beta, setup mutation,
networking, credentials, signing, tagging, release, and publication are not
promoted by this WorkUnit.
