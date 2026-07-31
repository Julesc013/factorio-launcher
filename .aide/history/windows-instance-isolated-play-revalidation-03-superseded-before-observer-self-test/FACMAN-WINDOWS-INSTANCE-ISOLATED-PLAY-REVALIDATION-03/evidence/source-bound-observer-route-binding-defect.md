# Source-bound observer and native route-binding defect

## Disposition

Revalidation-03 is superseded before the observer self-test. This is not a
human `Fail` or `Inconclusive` result.

```text
candidate integrity       exact
stage integrity           exact
operator designation      accepted for revalidation-03 only
observer self-test        not started
observer run directory    absent
WPR                       idle
prepare                   false
baseline                  false
permit                    false
Factorio execution        false
human verdict             unset
authority promotion       false
```

## Deterministic defect

`tools/gate4c_observer_self_test.py` projects the historical hermetic
`PREFLIGHT.WORK_UNIT` and `PREFLIGHT.CANDIDATE_REVISION` instead of loading the
instance-isolated identity from the exact qualification binding. Its result
cannot satisfy instance-isolated preflight for qualification-04.

The native verdict harness independently recognizes only revalidation-02 for
the instance-isolated route. A prepared revalidation-03 session would
therefore be rejected later by native session loading even if the Python
self-test identity were bypassed.

No observer run or evidence directory was created, WPR remained idle, and no
prepare, permit, process execution, verdict, or authority action occurred.

## Successor chain

The bounded source repair is
`FACMAN-INSTANCE-ISOLATED-OBSERVER-ROUTE-BINDING-01`. Because the repair changes
source-bound evidence tooling, qualification-04 and revalidation-03 remain
immutable historical records. The successor evidence chain is qualification-05
and revalidation-04 with fresh source closure, digests, stage, operation IDs,
operator designation, and authorization.
