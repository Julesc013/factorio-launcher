# Validation

Source checkpoint:
`e581f168a313d7fd23f35587ee63037c4b40df8a`, tree
`731da441aa8d23d1533ea90cdcd35346803ff4f6`.

Passed locally:

- `python tools/project_state.py --validate`
- `python tools/generate_plan_views.py --check`
- `python tools/technical_preview_census.py --check`
- `python tools/release_programme_check.py`
- `python tools/codegen/generate_metadata.py --check`
- `python -m unittest tests.test_source_closure_admission tests.test_current_truth_roles tests.test_aide_target_truth tests.test_facman_live_shell_integration tests.test_aide_compaction` — 52 tests
- pinned-environment `python -B -m unittest discover -s tests` under the real
  Windows user identity with exact ULK/USK main-pin worktrees and the native
  package fixture — 1,111 tests, 17 intentional skips
- pinned-environment `python -B .aide/scripts/aide_lite.py test`
- `git diff --check`

The independently reproduced native CTest result is 37/38. The sole failure is
`facman_presentation_service_smoke`, where the accepted dev source cannot
finalize the synthetic launch idempotency receipt. Both Ninja and canonical
Visual Studio Debug builds reproduce it. W10 changes no native runtime source;
the failure is retained as an explicit candidate/promotion blocker rather than
misreported as a W10 regression or a pass.

The exact pre-change protected `dev` hosted runs recorded in
`release/index/project_status.v2.toml` were all successful. Exact-head hosted
validation for this WorkUnit is required after push and is not claimed here.
