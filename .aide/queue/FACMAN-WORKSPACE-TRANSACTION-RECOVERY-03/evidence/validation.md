# Validation

Result: PASS locally; exact-SHA cross-platform CI is pending the WorkUnit
commit and push.

## Behavior proven locally

- The enabled writers `instance.create`, `mods.import`, `modsets.export`,
  `saves.backup`, `saves.clone`, `instance.export`, and `instance.import`
  create durable versioned transaction journals and advance through the
  declared requested-to-complete state model.
- Journals retain transaction/command/workspace identity, targets, sources,
  timestamps, completed steps, staging roots, expected hashes, commit
  strategy, errors, and recovery actions.
- `workspace.recovery.inspect` and `workspace.recovery.plan` are canonical
  read-only routes. `workspace.recovery.apply` requires an explicit ID,
  acquires an exclusive lock, and refuses write-shaped dry runs.
- Recovery preserves targets when commit is recorded, refuses manual target
  ambiguity when it is not, and removes staging only after ownership-marker,
  parent-binding, no-link, and durable rollback-state checks.
- Repeated recovery is idempotent. Missing staging is reconciled; corrupted or
  unknown journals, substituted staging, concurrent recovery, and read-only
  journal updates refuse without unsafe mutation.
- Doctor reports incomplete and corrupt transaction records without applying
  recovery.
- Every state has deterministic fault injection. Pre-commit faults create no
  target; post-commit faults preserve the complete target for recovery.

## Local gates

- Full native build: PASS.
- Native CTest: PASS (9/9).
- Complete Python suite: PASS (209/209).
- Strict checks: PASS (22 commands, 56 schemas, 83 refusal codes, 26 refusal
  goldens).
- Transaction recovery checker: PASS.
- AIDE Lite test: PASS.
- `git diff --check`: PASS.

## Authority boundary

The journal is intentionally bounded to the currently enabled writers listed
above; it is not claimed as a speculative universal transaction framework or
as shared-filesystem protection. General diagnostic export, `run.execute`,
real Factorio isolation, Safe beta, setup mutation, networking, credentials,
signing, tagging, release, and publication remain unpromoted.
