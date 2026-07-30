# FacMan observer self-test import closure

Date: 31 July 2026

WorkUnit: `FACMAN-OBSERVER-SELF-TEST-IMPORT-CLOSURE-01`

State: local implementation validated; review and `dev` integration pending

## Purpose

This bounded source repair makes the observer self-test independently
import-closed when Python launches it through its absolute script path with
the repository as the working directory and `PYTHONPATH` absent.

It does not change the observer profile, ETW policy, capture classification,
lost-event rules, native harness, candidate, provider pins, route, permit, or
authority.

## Negative control

The source in qualification-03 and at the reviewed `dev` input derives the
repository root but does not insert it into `sys.path` before dynamically
executing `tools/gate4c_verdict_preflight.py`. The preflight module then
imports `tools.*` and module initialization stops with:

```text
ModuleNotFoundError: No module named 'tools'
```

The stop occurred before `main()`, elevation checks, WPR, observer run
directory creation, `prepare`, or Factorio execution.

## Bounded repair

`tools/gate4c_observer_self_test.py` now inserts its exact resolved repository
root at import precedence zero before executing the source-bound preflight
module:

```python
ROOT_TEXT = str(ROOT)
if ROOT_TEXT not in sys.path:
    sys.path.insert(0, ROOT_TEXT)
```

No external `PYTHONPATH` is required or accepted as the repair.

The regression launches the absolute script path as a separate process with:

```text
working directory            repository root
PYTHONPATH                    absent
PYTHONDONTWRITEBYTECODE       1
argument                      --help
expected return code          0
```

This exercises top-level import semantics while remaining non-elevated and
non-authority-bearing. It starts no WPR session and creates no observer
evidence.

## Revalidation-02 disposition

`FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-REVALIDATION-02` is archived as
`superseded_before_prepare`.

```text
observer self-test       not started
observer evidence        none
WPR                      idle
prepare                  false
Factorio execution       false
permit issuance          false
human verdict            unset
authority promotion      false
```

Its historical bindings remain exact:

```text
qualification digest
99aee276b2968e493f7830ee0cf949efbcd4b0d843e0e93abe8729f13454d210

staged candidate digest
f7ef4783dd153b1445ec3cd9882134fc0ccb14a19fe3494186b7fe95b721de9d
```

The retained stage is not patched, copied into, cleaned, or reused by this
repair.

## Successor chain

The repaired source must be reviewed and integrated before:

```text
FACMAN-WINDOWS-INSTANCE-ISOLATED-CANDIDATE-QUALIFICATION-04
→ FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-REVALIDATION-03
```

Qualification-04 must perform fresh remote source closure and establish a new
qualification digest. Revalidation-03 must create a new stage, new operation
identities, and fresh observer and human evidence. Neither may overwrite or
reinterpret qualification-03 or revalidation-02.

## Authority boundary

This checkpoint records source repair only:

```text
prepare                    false
WPR execution              false
observer capture           false
permit issuance            false
Factorio execution         false
human verdict              unset
route authority            false
Setup mutation             false
credential/network use     false
signing/publication         false
```
