# FacMan Windows instance-isolated candidate qualification 04

Date: 31 July 2026

WorkUnit:
`FACMAN-WINDOWS-INSTANCE-ISOLATED-CANDIDATE-QUALIFICATION-04`

State: producer binding update active; remote source closure not started

## Purpose

Qualification-04 establishes a new source and evidence chain after the
source-bound observer self-test import-closure repair. It does not rewrite,
extend, or reinterpret qualification-03 or revalidation-02.

The first bounded phase updates the qualification producer from the historical
literal qualification-03 identity to the new literal qualification-04
identity. The producer continues to reject every differently named task root.
It does not accept a command-line, environment, working-directory, or other
ambient WorkUnit override.

## Reviewed source input

```text
FacMan dev integration
3b33efafc7c7027b6c66122b2f0f41194ac26ff3

Universal Launcher reviewed pin
7fc25340623131ba86c08dca4fb8a43b18a4520d

Universal Setup reviewed pin
3048128963dc718a7c38c1cfcdda9e813a23b0db
```

The provider pins are observed and preserved by this source phase. They are
not silently advanced to a provider branch tip.

## Producer-binding change

The source-bound producer identity is:

```text
FACMAN-WINDOWS-INSTANCE-ISOLATED-CANDIDATE-QUALIFICATION-04
```

The exact-root regression proves that a root named for qualification-03 is
rejected with the qualification-04-specific refusal. This is a source
integrity boundary, not an authority control supplied by the operator
environment.

The new chain uses append-only versioned identities:

```text
qualification binding schema
facman.play_candidate_qualification_binding.v3

qualification report schema
facman.instance_isolated_candidate_qualification.v3

target evidence WorkUnit
FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-REVALIDATION-03
```

The accepted v2 schemas remain byte-for-byte unchanged and retain their
qualification-03/revalidation-02 meanings.

## Historical evidence preserved

Qualification-03 remains immutable:

```text
qualification digest
99aee276b2968e493f7830ee0cf949efbcd4b0d843e0e93abe8729f13454d210

staged candidate digest
f7ef4783dd153b1445ec3cd9882134fc0ccb14a19fe3494186b7fe95b721de9d
```

Revalidation-02 remains `superseded_before_prepare` with no observer
self-test, observer evidence, WPR execution, prepare, permit, Factorio
execution, human verdict, or authority promotion.

## Required second phase

After this producer update is reviewed, hosted, and integrated into `dev`,
qualification-04 must use new empty roots to:

1. close exact remote FacMan, Universal Launcher, and Universal Setup sources;
2. build the repaired composition from clean source;
3. authenticate the exact Factorio and instance inputs;
4. generate a fresh qualification report and digest;
5. preserve all qualification-03 and revalidation-02 files unchanged; and
6. provide new immutable inputs to revalidation-03.

No unpublished local producer patch may enter the qualification.

## Authority boundary

This phase changes qualification source identity only:

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
