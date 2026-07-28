# Validation

## Implementation head

- PR #37 reviewed head:
  `c9ae60405d0b221faaba364be5f47e524649bb97`.
- PR CI `29799245632`: pass.
- PR code-security `29799245642`: pass.
- PR schema-check `29799245604`: pass.
- PR security-policy `29799245629`: pass.
- Local canonical full matrix: 43/43 native tests and 359 Python tests with
  seven declared optional skips; strict validation passed with 250 schemas,
  123 commands, 121 registered routes, and 217 refusal codes.
- Portable AIDE Lite self-test: pass.

## Exact merged dev

- Merge revision: `6ec47046d1b1f4ab8bddfcc27bcec76a774ff305`.
- CI `29799938954`: pass.
- code-security `29799939008`: pass.
- schema-check `29799938962`: pass.
- security-policy `29799938996`: pass.

## Clean pinned reconstruction

An isolated three-repository reproduction pinned:

- FacMan: `6ec47046d1b1f4ab8bddfcc27bcec76a774ff305`;
- Universal Launcher: `7bd4425f0c35414f738159b45d8bec42edf70235`;
- Universal Setup: `3f8489275077347c2918f3bb03614ec6431362ff`.

All three clones were detached and clean. Provider configure, build, tests, and
strict checks passed; FacMan configure, build, 43-test CTest suite, AIDE Lite,
strict validation, and the full Python suite passed. The proof completed in
362.9 seconds. Its separate build root and source-clone root were removed.

## Gate laws

- Equivalent evidence and desired state produce the same canonical plan digest.
- Changed evidence or desired state changes the plan digest.
- Plan effects use the closed `common.effects.v1` vocabulary.
- Raw source references remain `selected_unverified` and block materialisation.
- Describe and reconcile-plan operations leave installation, source, registry,
  v1 records, workspace, journals, temporary state, and candidate targets
  unchanged.
- `mutation_executed`, `apply_available`, inferred mutation authority, and
  source deletion remain false.

## Truth-only closeout validation

- Canonical project-state validation: pass.
- Focused target-truth, compaction, architecture-fitness, and release-structure
  tests: 20 pass.
- Full strict validator chain: pass.
- Portable AIDE Lite self-test: pass.
- Diff whitespace validation: pass.

An unscoped Python discovery was also attempted after the canonical build root
had been deliberately removed. Its only harness error was the expected missing
`build/native-smoke/Debug/facman.exe` package-proof prerequisite; strict was
initially blocked by one generated README line over the 240-character limit.
The line was corrected and the applicable truth-only suite passed without
recreating package or build residue. The earlier canonical full matrix and
exact hosted Windows package lane remain the package evidence for this gate.
