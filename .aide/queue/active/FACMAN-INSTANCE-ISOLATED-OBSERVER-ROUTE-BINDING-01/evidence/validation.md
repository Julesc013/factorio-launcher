# Validation

Passing evidence:

```text
134 affected/cross-component Python tests passed
2 existing unsupported symlink-creation tests skipped
306 schemas validated
strict validation passed
AIDE Lite validation passed
project state and generated plan views current
native verdict harness compiled
native route-binding CTest 1/1 passed
git diff check passed
```

The broad promotion diagnostic ran 555 tests but is not claimed as passing:
the isolated worktree lacked the CI `build/native-smoke` package layout, and
unrelated MinGW Unicode-path journeys failed. Hosted PR workflows remain the
required complete platform evidence.
