# Changed Files

Source candidate:

- `1d94fcfc567b3ffe8d7d7dc3829cc7984147b3a7`
- tree `932f0d47a6fbf48d9e7734cba9110eec1faea6fb`

Proof implementation and contract:

- `tools/remote_source_closure.py`
- `tools/repro_workspace_smoke.py`
- `contracts/schema/release/remote_source_closure.v1.schema.json`

Regression coverage:

- `tests/test_remote_source_closure.py`
- `tests/test_repro_workspace_smoke.py`

Operator documentation:

- `docs/reference/remote-source-closure.md`
- `docs/architecture/cross_repo_integration.md`
- `docs/README.md`

Durable machine evidence:

- `docs/quality/evidence/source-closure/remote-source-closure.v1.json`

Task and generated state:

- `.aide/queue/active/FACMAN-REMOTE-SOURCE-CLOSURE-PROOF-01/`
- `.aide/queue/active/FACMAN-FIRST-PARTY-PIN-REMOTE-REACHABILITY-01/`
- `.aide/queue/index.yaml`
- `.aide/memory/project-state.md`
- `.aide/memory/project-state.v2.json`
- `.aide/git/workflow-detection.json`
- `.aide/git/workflow-detection.md`
- `README.md`

The source candidate and the evidence-preservation commit are intentionally
separate. The report binds the exact source commit reconstructed from the
remote; preserving that report necessarily creates a later commit.
