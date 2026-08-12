# Validation

Current state: admission implementation locally validated; qualified task-ref
proof externally blocked.

Completed before publishing the task head:

- schema validation: PASS, 337 schemas;
- source format, queue, target-truth, plan-view, project-state, route, and
  admission checks: PASS;
- AIDE Lite portable validation: PASS;
- consolidated admission, source-closure, current-truth, provider-mode, TUI,
  and package-runtime suite: PASS, 153 tests with one optional skip;
- Visual Studio 2022 x64 source-provider build against exact canonical ULK and
  USK worktrees: PASS for static and shared linkage;
- native CTest: PASS, 38 of 38, using a permitted out-of-tree temporary root;
- immutable route, lock, proof-engine, and report-schema hashes: PASS through
  the closed admission validator.

The 973-test broad discovery rehearsal proved all release, source-closure,
provider-lock, package, policy, and schema checks, then exposed three local
test-environment classes: an ignored `.vscode` directory is visible only in
this developer checkout; a workspace-local temporary root is deliberately
rejected by candidate-lock and path-leak checks; and the original native build
was stale. Exact-provider rebuilds and the bounded external temporary root
closed the substantive affected lanes in the 153-test consolidated rerun.

The MinGW characterization configured correctly but stopped in unchanged
Universal Setup code on an existing `-Werror=unused-function` diagnostic.
The supported MSVC lane is green and this admission changes no provider code.

- clean diff and structured AIDE commit-message validation: PASS.

Required before an admission merge decision:

- exact-head hosted CI, schema, security, CodeQL, and TCK success;
- one qualified clean-Windows task-ref source-closure run with zero required or unknown skips;
- schema-valid immutable report and independent evidence review.

## 2026-08-12 synthesis validation

Current `dev` was merged into this task branch, not this task branch into
`dev`. The history-preserving synthesis merge is
`7f71c9179943036564674fde29b93dd834bfc793`, with exact parents
`68642575b23613c1ce6716546e4d0616196ac95c` and
`2e790d518b6a37d1456e99aad363dc617909f424`.

The follow-up test-routing repair is
`13f9d2b5db1adf733ae80d3f6ab41682041edbcc`. A fresh detached checkout of
that exact head passed:

- strict validation, including structure, admission, route, package, schema,
  security, and release checks;
- Visual Studio 2022 x64 native CTest, 38/38;
- the local Python obligation profile, 973 tests with zero failures or errors
  and 13 classified skips;
- the focused combined admission, route, plan, current-truth, and archive
  matrix, 91/91; and
- archive regression execution from the configured external build root, 8/8.

The 13 full-profile skips are seven optional lanes, five Windows symlink cases
unsupported without link privilege, and one required-blocked shared WinForms
package lane that was not built by this local source-mode configuration. There
are zero unknown skips and zero archive required-blocked skips.

This synthesis does not satisfy the clean-host task-ref proof and does not
authorize an admission merge into `dev`.
