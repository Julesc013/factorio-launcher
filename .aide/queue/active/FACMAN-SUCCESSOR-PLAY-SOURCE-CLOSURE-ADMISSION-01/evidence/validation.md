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
