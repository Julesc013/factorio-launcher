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

### Protected dev integration closeout — 2026-09-10 UTC

PR 270 qualified exact source `4b19f4b34a5dd1f95560356ffe521a9ffba26ab9`
and tree `5a1364a5eee146662e3391983944573fd34cc03c` against exact base
`757e2332e0c47f2d3e488ea8fcfdcc51f588595f`. All eleven checks in the live
`dev` ruleset passed, including current Windows, Linux and macOS native/package
jobs, Linux coverage, AppKit compile and the three language security jobs.
CodeQL also passed. The normal protected merge produced
`782be06e22d2979723f2f614cf77561f6c7c7f97` with the same tree, and local
`dev` was fast-forwarded to that exact merge.

The task-to-dev promotion advisory failed because the repository variable that
names its trusted ruleset workflow is unset. It is not a live ruleset check and
was neither bypassed nor relabelled as passing. Its separate repair remains on
PR 266.

The source and hosted-platform obligations of this WorkUnit are complete. It
does not qualify an actual Factorio game session, packaged Play acceptance,
human experience, signing, publication or the wider Alpha.6/Beta.1 programme.
