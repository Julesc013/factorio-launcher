# Instance-isolated observer and native route-binding repair

Date: 1 August 2026

WorkUnit:
`FACMAN-INSTANCE-ISOLATED-OBSERVER-ROUTE-BINDING-01`

State: locally implemented and validated; hosted review and `dev` integration
required

## Disposition of revalidation-03

Qualification-04 and its exact staged candidate remain immutable and
cryptographically intact. Revalidation-03 is superseded before the observer
self-test because two source-bound identities made the procedure impossible:

1. the Python observer self-test projected the historical hermetic WorkUnit
   and candidate revision instead of the staged qualification; and
2. the native verdict harness recognized revalidation-02 rather than the
   current instance-isolated session WorkUnit.

The accepted Jules operator designation is historical evidence for
revalidation-03 only. No observer run directory was created, WPR remained
idle, and no prepare, baseline, permit, Factorio execution, verdict, or
authority action occurred.

## Repair

The Python self-test now admits instance-isolated use only through the exact
absolute staged v4 qualification binding. It validates the no-follow path,
closed route and WorkUnit, qualification digest, clean repository identity,
and exact bound FacMan revision before elevation or WPR discovery. Its output
projects the WorkUnit and candidate revision from that qualification.

Historical hermetic Verdict-03 remains a distinct, explicit legacy mode. An
instance-isolated task cannot fall back to those constants.

The native harness recognizes only:

```text
FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-REVALIDATION-04
```

for the successor instance-isolated session. Its independently specified
self-test rejects revalidation-02, revalidation-03, unknown WorkUnits, and
route confusion with hermetic Verdict-03.

## Immutable successor contracts

```text
qualification WorkUnit
FACMAN-WINDOWS-INSTANCE-ISOLATED-CANDIDATE-QUALIFICATION-05

qualification binding schema
facman.play_candidate_qualification_binding.v4

qualification report schema
facman.instance_isolated_candidate_qualification.v4

revalidation WorkUnit
FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-REVALIDATION-04

staged qualification filename
qualification-binding.v4.json
```

The v3 contracts, qualification-04, and revalidation-03 are not rewritten or
reinterpreted.

## Local acceptance

The bounded source and cross-component suite passed: 134 Python tests, 306
schema validations, strict checks, AIDE Lite, clean project-state and plan
generation, native harness compilation, and the exact native route-binding
smoke. The two Python skips were existing unsupported symlink-creation cases.

Hosted PR CI, schema, code-security, and security-policy checks are still
required before integration. Fresh remote-only source closure,
qualification-05, and revalidation-04 staging must occur after integration.

## Authority boundary

This repair grants no observer/WPR, prepare, permit, process execution, human
verdict, route, Setup, credential/network, signing, or publication authority.
