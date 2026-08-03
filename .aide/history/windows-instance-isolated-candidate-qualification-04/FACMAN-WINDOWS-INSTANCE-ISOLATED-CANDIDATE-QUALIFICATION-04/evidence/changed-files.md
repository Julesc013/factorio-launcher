# Changed files — stage-handoff binding-filename repair

Functional source scope:

```text
tools/instance_isolated_verdict_coordinator.py
tests/test_instance_isolated_verdict_coordinator.py
```

Governance scope:

```text
.aide queue/memory records
release/index/plan.v1.toml
release/index/project_status.v2.toml
release/index/current_state.v1.toml
tools/project_state.py
generated project and roadmap views
project-truth regression tests
docs/release/checkpoints/windows-instance-isolated-candidate-qualification-04.md
```

The source repair changes only the immutable filename used when the
coordinator copies an already-validated qualification binding into a new
stage. It does not change binding bytes, schema validation, route semantics,
observer or ETW behavior, provider pins, Factorio inputs, or authority.
