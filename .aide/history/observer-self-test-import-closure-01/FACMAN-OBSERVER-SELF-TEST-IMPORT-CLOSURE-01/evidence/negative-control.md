# Negative control

The exact absolute script-path invocation against the unmodified
qualification-03/current reviewed-dev implementation stopped during module
initialization with:

```text
ModuleNotFoundError: No module named 'tools'
```

Conditions:

```text
script path                absolute
working directory          repository root
PYTHONPATH                  absent
PYTHONDONTWRITEBYTECODE     1
entrypoint main             not reached
observer run directory     absent
WPR                         not started / idle
```

The defect is source-bound: `gate4c_observer_self_test.py` dynamically
executes `gate4c_verdict_preflight.py` without first making the repository
root importable, while the preflight module performs absolute `tools.*`
imports.

This record preserves the already observed negative control. The repaired
WorkUnit does not revert source merely to reproduce it again and does not run
the real elevated observer self-test.
