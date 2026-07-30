# FacMan Windows instance-isolated candidate qualification 04

Date: 31 July 2026

WorkUnit:
`FACMAN-WINDOWS-INSTANCE-ISOLATED-CANDIDATE-QUALIFICATION-04`

State: diagnostic qualification superseded before stage; stage-handoff
binding-filename repair active

## Purpose

Qualification-04 establishes a new source and evidence chain after the
source-bound observer self-test import-closure repair. It does not rewrite,
extend, or reinterpret qualification-03 or revalidation-02.

The producer and append-only v3 contracts are integrated on remote `dev`.
Fresh remote source closure and a first qualification-04 passed. Before
coordinator staging began, source inspection found that the coordinator would
copy the v3 binding under the historical v2 filename. That first
qualification is preserved as diagnostic and superseded before stage.

## Reviewed source input

```text
FacMan dev integration
569883a86c50ca203ccbecec6d37216f22f7c6a0

Qualification producer task
c8bc937f1190d1068745a255b9d28ff24a499c0c

Pull request
#99

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

The producer task passed the exact PR-head and integrated-`dev` workflow sets:

```text
PR CI                           30575090336
PR schema-check                 30575090335
PR code-security                30575090328
PR security-policy              30575090250

integrated-dev CI               30576115373
integrated-dev schema-check     30576115655
integrated-dev code-security    30576115573
integrated-dev security-policy  30576116097
```

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

## Diagnostic remote source closure

The first empty-root checkout stopped safely before build and report because
Windows Git omitted a tracked long AIDE path. It remains diagnostic and was
not repaired or reused.

The second attempt explicitly bound `core.longpaths=true` for the process and
passed:

```text
FacMan
569883a86c50ca203ccbecec6d37216f22f7c6a0

Universal Launcher
7fc25340623131ba86c08dca4fb8a43b18a4520d

Universal Setup
3048128963dc718a7c38c1cfcdda9e813a23b0db

closure report SHA-256
300ed1c9dac88d8d69085b79ed23e394cd9f9ed24096a5d727b1cf3bcb78b54c

package artifact SHA-256
c9015800c2ab569810bdf4cc15628f8df19ca4d922d1043113ab4a2d41082baf

provenance SHA-256
c5c8b8d8d0b07fdd2a130af9a322c2fac1678ed7bcfacf23b6877f39416b33
```

Acceptance counts were:

```text
FacMan native                  58
FacMan Python                  569
Universal Launcher native      5
Universal Setup native        16
required Windows package      14/14
```

## Diagnostic qualification-04

The producer then generated a valid v3 qualification:

```text
qualification digest
b6d1e7b030a17cf5279d363c341a8405526363217c96928d78d199d6a073363b

report digest
8116af7b8d9df1089e6211aca42273e44279f62eb1f77af0397301194373cb9d

qualification binding file SHA-256
3f2de719929065d4442546e66fb1729dbd8badac6c6bd79aa4c975a6570ded6f

qualification report file SHA-256
ce681351c27957dc54168a987e741bdc3f5f2fcee151f5055946eac665da950f

Factorio executable SHA-256
d3bcfca4dbee407d472013b745ce2445d34af6f021aacc5753ee0dac54b56b0b

Factorio source archive SHA-256
ad36e0591e336400e731d5b400038e37c8361fdc71c76c0f6db96ee31741b4c2

Factorio authentication digest
d777bf268f0f0795b1d622eed07482d5cf2b3158b9edbc7c8d7c2f7ff4dd930c

instance spec digest
4cae0b49f6b3f85cf9defdfe7e0c57ff9d0ed855e9cc81a54e1cef05400bea79

instance binding digest
c2f8563d7e08a6c6c6cd9a368fb88033c5f1a3e8ee76dfee8552b6d8d3820b26

instance readiness digest
0f9c22f6d9557ba3ae89196d75ea2273ed02d8d037b642638822360a5efe9e55
```

It grants no authority and is now:

```text
disposition        superseded_before_stage
coordinator stage  not invoked
stage root         absent
```

## Stage-handoff defect and repair

The integrated coordinator selected:

```text
artifacts/qualification-binding.v2.json
```

for any parsed qualification source. With a v3 source, the native copy would
have preserved the exact bytes but assigned a false historical version in the
authoritative staged path.

The bounded repair changes only that destination:

```text
QUALIFICATION_BINDING_FILENAME = "qualification-binding.v3.json"
```

The regression launches the stage path with a v3 qualification and proves:

```text
configuration binding path      qualification-binding.v3.json
v3 copy                         exists
historical v2 path              absent
staged-candidate binding        valid
```

No stage command is run as part of repair validation.

## Required regeneration

After this coordinator repair is reviewed, hosted, and integrated into
`dev`, qualification-04 must use new empty roots to:

1. close exact remote FacMan, Universal Launcher, and Universal Setup sources;
2. build the repaired composition from clean source;
3. authenticate the exact Factorio and instance inputs;
4. generate a fresh qualification report and digest;
5. preserve the diagnostic qualification and every historical chain;
6. create a fresh revalidation-03 root; and
7. invoke coordinator `stage` only.

No unpublished patch, diagnostic closure, diagnostic build, or diagnostic
qualification may enter the final stage.

## Authority boundary

This phase changes qualification and stage-handoff source identity only:

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
