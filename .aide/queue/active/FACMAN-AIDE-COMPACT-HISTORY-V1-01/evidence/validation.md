# Validation

- Focused Q27 commit recovery: PASS, 29 tests.
- Focused Q34 changelog/release: PASS, 15 tests.
- Python compile of `.aide/scripts/aide_lite.py`: PASS.
- Canonical `py -3 .aide/scripts/aide_lite.py test`: PASS.
- Generated template inspection: PASS; no Markdown H2 headings or generated
  AIDE result/phase/quality trailers.
- `git diff --check`: PASS before strict validation.
- Raw optional AIDE source discovery: NOT A REQUIRED FACMAN GATE. It ran 423
  tests and reported 20 failures/82 errors exclusively in source roots,
  examples, and reports intentionally excluded by the safe portable import.
  `docs/architecture/aide_lite_integration.md` records this expected boundary
  and prohibits vendoring those roots merely to make optional self-tests green.
- The task was rebased and conflict-reconciled onto exact D1 closeout head
  `58789676d892f68f8a07eaced23f2ded772e907e`; queue-state and compaction
  validators pass with both WorkUnits represented in canonical order.
- `tools/project_state.py --write`: PASS; target-local machine projections now
  include this verified-pending-closeout WorkUnit.
- FacMan strict validation: PASS with the exact pinned development environment,
  ULK `1cafe4054297cc11e02458b83d230db0cd064471`, and USK
  `32488fc13bd2439f9f6e52e83a97f6da345a7650`; all target-truth, queue,
  schema, provider workspace, release, package, and policy checks passed.
- Hosted validation: running on draft PR #138, stacked behind #137.
