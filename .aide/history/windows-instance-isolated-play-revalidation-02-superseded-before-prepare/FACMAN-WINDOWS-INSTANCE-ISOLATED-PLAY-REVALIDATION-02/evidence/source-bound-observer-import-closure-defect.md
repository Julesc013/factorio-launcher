# Source-bound observer import-closure defect

## Disposition

`FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-REVALIDATION-02` is superseded
before prepare. Revalidation did not begin.

```text
candidate integrity      PASS
stage integrity          PASS
observer self-test       NOT STARTED
observer evidence        none
WPR                       idle
prepare                   false
Factorio execution        false
permit issuance           false
human verdict             unset
authority promotion       false
```

This is neither an observer self-test failure nor a human `Fail` or
`Inconclusive` verdict. Python failed during module initialization, before
`main()`, before the elevation and WPR checks, and before creation of an
observer run directory.

## Exact preserved identities

```text
FacMan source
  2c393acf838dd432d37f8acce50d01f91bfd28ca

Universal Launcher
  7fc25340623131ba86c08dca4fb8a43b18a4520d

Universal Setup
  3048128963dc718a7c38c1cfcdda9e813a23b0db

qualification digest
  99aee276b2968e493f7830ee0cf949efbcd4b0d843e0e93abe8729f13454d210

staged candidate digest
  f7ef4783dd153b1445ec3cd9882134fc0ccb14a19fe3494186b7fe95b721de9d
```

The retained machine-local stage remains immutable. The authorized
`operator/process-temporary` directory may remain empty and is not observer
evidence.

## Reproduction

The exact qualified and current `dev` script-path invocation fails with
`PYTHONPATH` absent:

```text
ModuleNotFoundError: No module named 'tools'
```

`tools/gate4c_observer_self_test.py` derives the repository root but does not
insert it into `sys.path` before dynamically executing
`tools/gate4c_verdict_preflight.py`. The loaded preflight module imports
`tools.*`, while Python places only the script directory on the initial import
path for an absolute script-path invocation.

Changing the working directory does not close this import topology. No WPR
recording began, no observer run directory was created, and WPR was verified
idle after each stopped launch.

## Required successor chain

```text
FACMAN-OBSERVER-SELF-TEST-IMPORT-CLOSURE-01
→ FACMAN-WINDOWS-INSTANCE-ISOLATED-CANDIDATE-QUALIFICATION-04
→ FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-REVALIDATION-03
```

The repair must be reviewed and integrated before fresh source closure,
qualification, and staging. No repaired file may be copied into the old stage,
and no external `PYTHONPATH` workaround may be used.
