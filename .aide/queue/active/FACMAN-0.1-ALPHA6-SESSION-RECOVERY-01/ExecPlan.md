# Make Play session ownership and crash recovery durable

1. Inspect the exact current source and relevant prior evidence; classify
   remaining gaps against this task's acceptance criteria.
2. Check actual start prerequisites and claim a WIP slot in the canonical
   plan. Complete the AIDE task and Git helper checks and record an exact-base
   branch plan before branch mutations.
3. Implement the bounded scope from task.yaml with focused regression tests.
   If it exceeds one reviewable work unit, split it before further changes.
4. Run affected native/Python/strict/package checks and retain failures.
   Remediate findings and obtain independent review of the resulting source.
5. Commit and normally integrate with required current checks; record exact
   integration evidence. Recheck close_after prerequisites before closing.

Current user authority includes necessary source changes, tests, docs, sync,
commits and normal checked merges. Publication and genuine experience remain
separate. Unavailable host/input cells block their own qualification only.

### Current-source implementation checkpoint — 2026-09-10 UTC

The task branch is based on exact protected `dev` revision
`757e2332e0c47f2d3e488ea8fcfdcc51f588595f`. The implementation persists a
platform-specific stable process-start identity before dispatch, observes it
through a tri-state matching/exited/inconclusive interface, and reconciles
interrupted journals while holding the existing instance run lock. Recovery
uses bounded stable no-follow reads, refuses intermediate and leaf link
crossings, preserves original journal fields and never infers successful game
effects.

Focused Windows native execution passed, followed by the affected full native
build and all 44 CTests. The affected Python selection passed 146 of 147 tests;
the sole failure reported stale generated contract catalogs. Regenerating the
two canonical catalogs remediated that finding, after which the complete strict
suite, plan-view check, project-state validation and portable AIDE test passed.
The failed attempt remains recorded with its original scope.

A separate non-authoring GPT-5.6 Terra review found two defects in the first
candidate: recovery-root link traversal and missing Darwin start-identity
support. Both were corrected. The final model-based re-review passed the exact
source bytes and regression coverage; no human review is claimed.

This checkpoint qualifies its exact current source and Windows test inputs.
Fresh hosted macOS and Linux evidence, protected integration, packaged real-Play
effects and human experience remain pending. The WorkUnit stays active and no
release acceptance, signing, tagging or publication claim is made.
