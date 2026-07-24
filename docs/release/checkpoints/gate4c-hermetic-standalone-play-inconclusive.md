# Gate 4C hermetic standalone Play verdict

## Disposition

```text
Inconclusive
```

The exact Windows x64 / Factorio 2.0.77 / standalone non-Steam / `menu` /
`hermetic` candidate did not reach the Factorio process boundary.

Two fresh, independently prepared operations passed observer self-test,
source, readiness, quiet-host, preflight, and baseline gates. After exact
one-use plan approval, both stopped at the same provider refusal:

```text
permit_wrong_evidence
independent observer was not active before process boundary
$candidate.observer
```

The frozen policy explicitly makes observation-provider failure and missing
required evidence `Inconclusive`. The result cannot be waived into Pass.

## Frozen identities

| Identity | Value |
| --- | --- |
| Policy ID | `facman.hermetic-standalone-play.2.0.77.windows-x64.v1` |
| Policy digest | `6fde31f26d57e23d67c01dd598cb869a4914d11711868b46d4f817709455e7a2` |
| Gate 4B reviewed candidate head | `da3e2274a3dc8a5757078b20276a1a6a93084860` |
| Gate 4B implementation merge | `e9c1e69fee1ae815f62638db8b7263cb01b70389` |
| Gate 4B closeout merge | `7fe12635f7309e4fd709810dd192d43ff920592f` |
| Gate 4C merged evidence tooling | `a8c73eb4e34f8fbac5c2cf2207fdf47d64bcb616` |
| Universal Launcher | `7bd4425f0c35414f738159b45d8bec42edf70235` |
| Universal Setup | `3f8489275077347c2918f3bb03614ec6431362ff` |
| Reviewed harness SHA-256 | `d1002424d5de840068cfc752a26b3cad9cf28c46c376a28b8e5540810c5613b7` |

## Attempt identities

| Evidence | Attempt 1 | Attempt 2 |
| --- | --- | --- |
| Observer self-test | `40c5215369baa02869f62238eeaa3409db0f4aa6c3a32455fcea600cfc85d246` | `0bde0465b57e808ee28db26a1712ca6eaffd57d20b0af60cdee3d1e598af6db6` |
| Ready preflight | `6155111ea02d395bd51e0b03dbb18f536aea63807bec121bf028c82a0717dc2a` | `0c15ff73850fac27f72e07758e16f0e7f9be5e7292c25412bfc77581c18cb46f` |
| Operation | `gate4c-menu-first-20260723t234705z-451c651c` | `gate4c-menu-first-20260724t005357z-926a6bd5` |
| Session | `0a0d9153d20753aa203958d1eb76c6be18890e16b1a114b3dbf1134817855179` | `fb90b55b83afa85989a87a78b5667bf857f65ffd2e581e91d4f0a4214f69ab0c` |
| Plan | `87069ebdf2eef8f5d2f9f37f31a40b39d48bee99895be0da9bd56ca57ad79c5b` | `3444817c2919824e34a33733ab9d68f2209621ff5d5a0a9bf21c2edec2c506dc` |
| Provider result | observer unavailable before process | observer unavailable before process |
| Factorio process | not created | not created |

The complete file hashes, baseline identities, and absence inventory are
recorded in the WorkUnit evidence:

```text
.aide/queue/active/
  FACMAN-HERMETIC-STANDALONE-PLAY-VERDICT-01/
    evidence/verdict-attempts.md
```

## Authority boundary

This result promotes nothing:

- no public `facman play` or `instance.play`;
- no product permit issuance;
- no real Factorio execution authority;
- no Setup, credential, network, Steam, host-mutation, signing, or publication
  authority;
- no playability, Safe beta, or canonical `main` promotion.

The ephemeral permits were never consumed. Both harness processes exited, so
their process-session authenticators and any in-memory permit material are
invalid and unrecoverable.

## Missing evidence

No observer capture token, ETL trace, process lifecycle journal, post-run
comparison, native technical packet, or human Factorio UI observation exists.
Those absences prevent Pass; they are not interpreted as proof of safety.

The current provider collapses the observer-start helper error into a generic
refusal and does not persist the nested command result. Therefore this verdict
does not claim a root cause.

## Next transition

`FACMAN-HERMETIC-STANDALONE-PLAY-OBSERVER-START-REPAIR-01` is active. It may:

1. reproduce observer startup without Factorio;
2. preserve exact command, exit status, stdout, and stderr;
3. identify and correct only the observer-start boundary;
4. prove active-before-process ordering with a non-Factorio probe; and
5. close a reviewed repair candidate.

Only then may a new
`FACMAN-HERMETIC-STANDALONE-PLAY-VERDICT-02` conduct fresh operations against
the unchanged frozen policy. No failed plan, baseline, permit, or operation
closure may be reused.
