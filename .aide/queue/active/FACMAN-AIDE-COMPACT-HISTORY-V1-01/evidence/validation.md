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
- FacMan strict validation: BLOCKED BY DEPENDENCY-ORDERED CLOSEOUT. More than
  100 validators passed before the gate correctly detected stale generated
  project truth at merge head `da7c825f...`. Schema/release checks also lacked
  the pinned development packages and expected provider sibling paths in this
  isolated worktree. These are environment/current-truth prerequisites, not
  compact-policy regressions. Rerun after `FACMAN-D1-INTEGRATION-CLOSEOUT-01`
  and provider workspace qualification.
- Hosted validation: pending publication after closeout rebases this unpublished
  task commit onto current canonical `dev`.
