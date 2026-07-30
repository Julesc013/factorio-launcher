# Validation

## Completed

```text
absolute script-path --help, repository cwd, no PYTHONPATH     PASS
absolute script-path --help, unrelated temporary cwd           PASS
tests.test_gate4c_observer_self_test                            PASS (16)
project-state generation and validation                        PASS
canonical plan generation and validation                       PASS
focused project-truth and observer tests                       PASS (75; 2 skipped)
affected Python suite                                           PASS (116; 3 skipped)
package runtime proof subset                                    PASS (25; 1 skipped)
source-format check                                             PASS
strict validation                                               PASS
portable AIDE validation                                        PASS
git diff check                                                  PASS
```

The subprocess regression uses `PYTHONDONTWRITEBYTECODE=1`, requires return
code zero, and rejects import tracebacks. No elevated observer self-test, WPR
session, observer evidence, `prepare`, permit, or Factorio process is part of
this validation.

The first affected-suite invocation lacked provider discovery and a native
package-proof binary because the task worktree is nested under an isolated
`out/worktrees` root. That environment result is not counted as acceptance.
The passing run explicitly bound the clean qualification-03 detached provider
clones at the exact retained Launcher and Setup pins, used the retained
unmodified native build for native package-runtime proof, and placed transient
test output under the WorkUnit-local temporary root.

## Integration evidence pending

```text
structured commit check
hosted pull-request matrix and security checks
reviewed dev integration
```
