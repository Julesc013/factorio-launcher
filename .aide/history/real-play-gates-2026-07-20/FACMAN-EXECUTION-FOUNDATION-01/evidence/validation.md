# Validation evidence

## Complete matrix

- `py -3 tools/dev.py verify-all` — PASS on 2026-07-20.
- Native CTest matrix — 43/43 PASS.
- Python matrix — 355 PASS, 1 intentional skip.
- Schema inventory — 235 schemas PASS.
- Strict validator chain — PASS, including command/refusal contracts, generated metadata, application and CMake architecture, security, packages, releases, and canonical project truth.
- Complete-matrix elapsed time — 467.4 seconds.

## Focused execution proof

- `facman_execution_foundation_smoke` — PASS for success, argument boundaries, non-zero exit, timeout, cancellation, bounded output, ignored graceful termination, crash, process-tree termination, controlled-root write, path refusal, absent authority, and interrupted-journal recovery.
- `facman_client_smoke`, `facman_application_types_smoke`, `facman_tui_smoke`, `flb_setup_gateway_smoke`, `flb_command_bridge_smoke`, and `m1_three_repository_system_proof` — PASS.
- `py -3 tools/dev.py test --fast` fast native subset reached 11/11 PASS after the TUI metadata correction; the final complete matrix supersedes the earlier overlapping-build infrastructure failure and pre-fix Python result.

## Post-closeout truth reconciliation

- `py -3 -m unittest test_aide_target_truth test_aide_compaction test_status_onboarding_explain` — 18/18 PASS after moving canonical status to the inactive real-play gate checkpoint.
- `py -3 tools/strict_check.py` — PASS before closeout reconciliation; the targeted truth tests validate the subsequent generated phase transition.
- `git diff --check` — no whitespace errors; line-ending conversion warnings only.

The first attempted complete-matrix invocation was killed by its command harness timeout and left a compiler process briefly alive; a concurrent retry produced linker file collisions. No matching orphan remained, and the single-owner rerun above passed. This was not counted as product evidence.
