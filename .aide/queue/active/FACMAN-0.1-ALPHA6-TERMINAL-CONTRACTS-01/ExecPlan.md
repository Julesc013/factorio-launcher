# Close CLI JSON RPC and TUI compatibility mechanics

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

## 2026-09-14 current-dev activation

This WorkUnit started as the fourth active item from exact protected `dev`
`a158a6aa6eae947832fdd16101531ac122f7a3a6`, tree
`f47600447ae36b67e35d077fa05e94817f506a8d`. The reviewed process-transport
implementation commit `1b962531f1d386294b44c2230c230c9f66ad2fcc` is already
an ancestor of that head. PR 277 requalified and synchronized the same source
tree through normal protected `dev` integration.

Current code and the native terminal-capability smoke preserve the intended
`NO_COLOR` behavior: a nonempty value disables color without forcing linear
mode. The architecture document incorrectly grouped it with `TERM=dumb` and
`FACMAN_UI=plain`; this slice corrects that contract text. Existing native
process, capability, PTY/ConPTY and Python frontend suites remain the
independent behavior oracles.

## 2026-09-14 current Windows validation

The existing owned Debug build was reconfigured and rebuilt from the exact
current C++ source with Visual Studio 18 2026 and the pinned clean ULK/USK
sources. Both selected native tests passed, 37 executable-bound Python RPC and
frontend tests passed, and both applicable Windows ConPTY tests passed. The
client boundary, architecture, format, generated plan, project-state and AIDE
Lite checks also passed. The exact binary and input identities are retained in
`evidence/terminal-contract-current-dev-validation.v1.json`.

The first CMake invocation named the nonexistent `facman` target and the first
combined Python invocation omitted the required repository/test import path.
Both were invocation defects; the corrected `facman_cli` build and clean 37-test
run passed. No failed result was relabelled or removed.
