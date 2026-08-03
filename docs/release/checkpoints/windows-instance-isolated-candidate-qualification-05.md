# FacMan Windows instance-isolated candidate qualification 05

Date: 1 August 2026

WorkUnit:
`FACMAN-WINDOWS-INSTANCE-ISOLATED-CANDIDATE-QUALIFICATION-05`

State: `accepted_for_revalidation_04_stage`

## Purpose

Qualification-05 establishes the fresh source and evidence chain after the
qualification-bound observer and native successor-route repair was integrated
into `dev`. It does not rewrite qualification-04, revalidation-03, or any
earlier evidence chain.

This checkpoint records source closure and qualification only. It grants no
observer, WPR, `prepare`, permit, Factorio execution, verdict, or route
authority.

## Reviewed repair integration

```text
FacMan dev integration
8f495d63b412a3af5a22305d9d8b424efd4303d2

implementation revision
376fe5066afcb663f8712c25c4f662c3b0f97f46

CI correction revision / PR head
aea8b132dfde557b1e047443c7cd0c87914e5df8

pull request
#102
```

PR-head and exact integrated-`dev` CI, schema, code-security, and
security-policy workflows passed. The integrated task tree is byte-identical
to the reviewed PR-head tree.

## Fresh remote-only source closure

The accepted closure used new empty clone, build, and evidence roots. Every
checkout was detached, clean, free of Git alternates, and reconstructed from
the exact remote source and provider pins.

```text
FacMan
8f495d63b412a3af5a22305d9d8b424efd4303d2

Universal Launcher
7fc25340623131ba86c08dca4fb8a43b18a4520d

Universal Setup
3048128963dc718a7c38c1cfcdda9e813a23b0db

closure report SHA-256
6877cab671a97179a20dcacde424caaf8e94d1c5275a1dd7a4bda5ecb143e4ba

package artifact SHA-256
5ddbc9726fc7cc657e221807b03710aa0040b3d366e78cb8e7dacf6f31b46094

provenance SHA-256
c2eb69908433f7097846bdd278d3340c21756160492c55f2228050c50252d72f
```

Acceptance counts were:

```text
FacMan native                  58
FacMan Python                  580
Universal Launcher native      5
Universal Setup native        16
required Windows package      14/14
required package skips         0
```

## Exact qualification

The exact qualification root is:

```text
C:\Users\Jules\AppData\Local\Temp\facman-q05-final-qualification\
FACMAN-WINDOWS-INSTANCE-ISOLATED-CANDIDATE-QUALIFICATION-05
```

The line break is presentation only.

```text
qualification schema
facman.play_candidate_qualification_binding.v4

qualification report schema
facman.instance_isolated_candidate_qualification.v4

target evidence WorkUnit
FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-REVALIDATION-04

qualification digest
eaea8e2bbc03268f49f0fa8c077e329edae317c3757ef42a628a05da06cf1788

qualification report digest
8c85d1e5c5bdb5f643bbda7699b7bcdacd21e172934e252c469105af2e3f1324

qualification binding file SHA-256
4f3cf5a5ab0e1da72c1314f98aca4d64dbe36fe24d46a26b8358f4eaca041971

qualification report file SHA-256
9089b255d19847851e47f44c3b660259ce090c0a84f2a79c0c0ee0a1ca0051a5
```

Bound product identities are:

```text
Factorio executable SHA-256
d3bcfca4dbee407d472013b745ce2445d34af6f021aacc5753ee0dac54b56b0b

Factorio source archive SHA-256
ad36e0591e336400e731d5b400038e37c8361fdc71c76c0f6db96ee31741b4c2

Factorio authentication digest
069bb50b3bb913cf3a04ee98af17dae9ab7f99bd6024e26653424905e6cd15e4

instance spec digest
4cae0b49f6b3f85cf9defdfe7e0c57ff9d0ed855e9cc81a54e1cef05400bea79

instance binding digest
ffb62a584ec110daf429543ee69e3cf14bd8fb56e46cb7296137530caead7d9e

instance readiness digest
8b7f9da9bbb99d0cdf5c4fd24515ca48262dfdc24cdffc7ff066fbcb03eda5f9
```

The first producer invocation stopped before task-root creation because the
qualification parent did not yet exist. Creating only the empty parent and
rerunning the identical command produced this accepted qualification. No
diagnostic qualification bytes exist and no evidence was repaired in place.

## Authority boundary

```text
observer self-test     not started
observer run directory absent
WPR/ETW                not started
prepare                false
baseline               false
permit                 false
Factorio execution     false
human verdict          unset
route authority        false
authority promotion    false
```

Qualification-05 was admitted only to a new immutable revalidation-04 stage.
All older chains remain historical and immutable.
