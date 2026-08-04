# FACMAN-SUCCESSOR-PLAY-ROUTE-DEFINITION-01

Date: 2026-08-04

State: `task_complete_no_authority`

## Defined route

The immutable machine-readable definition is
`release/index/successor_play_route.v1.toml`. It binds exactly:

```text
route       facman.play.windows-x64.factorio-2.0.77.standalone.menu.instance-isolated.successor.v1
platform    Windows x64
Factorio    2.0.77
source      standalone non-Steam
intent      menu
isolation   instance_isolated
policy      facman.windows-instance-isolated-play.2.0.77.x64.v1
policy SHA  8d8189a9e8fc9ff7e479f7dda1adf0ea516bed2878046468022b2da8355e2432
base        b70be10696855628c6d2948eb016c8424912e14e
```

The process provider is `factorio.launch.local` revision
`windows-instance-isolated-play-candidate.v1`. The independent observer is
`factorio.play.process-tree-observer` revision
`gate4c-etw-file-registry-process.v6`. The permit profile retains the current
authenticated, exact-plan/resource/provider/principal/evidence bindings, a
120-second maximum TTL, five-second future-skew allowance, and one-time
consumption. Permit issuance remains false.

The route also binds the accepted workspace-root marker contract, exact
package-relative backend identity, and bounded WinForms process transport.
FacMan continues to consume Universal Launcher
`7fc25340623131ba86c08dca4fb8a43b18a4520d` and Universal Setup
`3048128963dc718a7c38c1cfcdda9e813a23b0db` from provider `main`. No provider
pin changes in this WorkUnit.

## Fresh evidence-chain law

The definition reserves a new identity for every successor step:

```text
route definition
-> source closure
-> candidate qualification
-> stage
-> observer generation
-> baseline
-> prepare lease
-> launch 1 operation / attempt / permit / technical packet
-> launch 2 operation / attempt / permit / technical packet
-> human verdict
-> route capability
-> route promotion
```

Only the route-definition identity exists. Every later identity is reserved
but uncreated, unissued, or unrecorded. Runtime observer, baseline, lease,
operation, attempt, and permit values must be generated freshly by their
separately authorized steps. No revalidation-04 WorkUnit, operation, stage,
qualification, packet, or external path is reused.

Candidate source revision, source-closure digest, package/manifest identities,
Factorio archive/executable hashes, and instance specification/binding/
readiness digests remain `unassigned`. The next WorkUnit must write them to a
separate source-closure record that references this definition digest; it may
not edit the accepted route definition.

## Verdict law

Exactly two independently permitted launches and complete hash-closed
technical packets precede a human-only verdict:

- `Pass` makes the exact route eligible for separate route-capability and
  promotion review. It grants no authority itself.
- `Fail` requires bounded repair and fresh qualification. The policy cannot be
  weakened retroactively.
- `Inconclusive` requires improved evidence and a repeat using fresh runtime
  identities. It is never treated as a softer Pass.

Automation cannot infer any of these verdicts.

## Next WorkUnits

`FACMAN-SUCCESSOR-PLAY-SOURCE-CLOSURE-01` is ready but not active. It must use
fresh empty clones, prove remote-only object closure, retain the exact stable
provider pins, and create the missing candidate/source/package bindings outside
the checkout.

`FACMAN-SUCCESSOR-PLAY-QUALIFICATION-01` remains planned and blocked on that
source closure. Qualification may propose a fresh stage packet, but it cannot
create the stage or begin an authority-bearing action.

## Authority boundary

This checkpoint defines evidence law only. It performs no reconstruction,
qualification, stage creation, observer/WPR action, baseline, prepare lease,
`prepare`, permit issuance, Factorio execution, human verdict, route-capability
creation, route promotion, Setup mutation, credential or network action,
signing, or publication. Every corresponding machine-readable authority flag
remains false.
