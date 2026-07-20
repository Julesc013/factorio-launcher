# Validation

Final local result: **PASS**.

- `py -3 tools/dev.py test --fast`: PASS in 12.9 seconds after repair; 10/10
  fast-labelled native tests and 26 focused Python tests.
- `py -3 tools/dev.py verify-all`: PASS in one final 475.6-second invocation;
  42/42 native tests, 354 Python tests, one intentional opt-in skip, and the
  strict validator chain.
- `py -3 tools/capability_policy_check.py`: PASS; all 17 durable capabilities
  have unique IDs, valid status, known effects, and valid command mappings.
- `py -3 tools/project_state.py --summary`: PASS; phase, WorkUnits, golden
  journey, readiness, execution reason, both modes, release authenticity, and
  user validation are visible from one command.
- AIDE target-truth, queue-state, and compaction validators: PASS.
- AIDE snapshot/index/context/pack generation: PASS for 2,585 files and 929
  test mappings; the task packet is within budget.
- AIDE changed-file verification: WARN with zero errors; all warnings classify
  reviewed deletions caused by archiving closed queue tasks or replacing the
  obsolete `flaunch-root-authority` policy path. Archived records are retained
  under the hash-indexed convergence checkpoint.
- `py -3 .aide/scripts/aide_lite.py validate`: PASS; concise project state is
  1,161 tokens against the 1,600-token hard limit.
- `py -3 .aide/scripts/aide_lite.py selftest`: PASS.
- `py -3 .aide/scripts/aide_lite.py test tiers`: PASS; report-only test tier
  model retained.
- Contract, refusal, generated metadata, release structure, source format,
  and `git diff --check` validators: PASS.
- Built CLI runtime check: `FacMan 0.1.0 (revision 2056c8d0a16c,
  configuration Debug)` and `capabilities inspect --json` returned the new
  durable capability vocabulary without creating the inspected workspace.

An earlier full attempt correctly failed one stale native bridge assertion;
the assertion was migrated and its isolated rerun passed. A second full attempt
then found two stale Python expectations; both were migrated, passed 5/5
focused tests, and the final full invocation passed completely.
