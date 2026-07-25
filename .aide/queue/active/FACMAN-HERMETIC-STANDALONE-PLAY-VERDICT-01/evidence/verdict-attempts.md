# Gate 4C verdict attempts

## Frozen disposition

```text
Inconclusive
```

The independent observation provider failed to become active before the
process boundary in two separately prepared attempts. The frozen policy makes
`Inconclusive` mandatory when the observation provider fails or required
evidence is unavailable.

Neither attempt started Factorio. Neither produced an observer capture token,
ETL trace, process lifecycle journal, protected-state comparison, technical
candidate packet, or human UI observation. Each process-session permit was
constructed only after exact operator approval, but provider execution stopped
before permit consumption and before process creation. Harness exit destroyed
the process-session authenticator, so no reusable authority remains.

The frozen policy digest remained:

```text
6fde31f26d57e23d67c01dd598cb869a4914d11711868b46d4f817709455e7a2
```

The reviewed Gate 4B harness SHA-256 remained:

```text
d1002424d5de840068cfc752a26b3cad9cf28c46c376a28b8e5540810c5613b7
```

## Attempt 1

| Evidence | Identity |
| --- | --- |
| Observer self-test digest | `40c5215369baa02869f62238eeaa3409db0f4aa6c3a32455fcea600cfc85d246` |
| Observer artifact SHA-256 | `c7d1320690ee156d3364d8db72ca4515ea9547ee6e837c3b1fb1f11baf332a70` |
| Observer result | `pass`; zero lost events; exact attribution complete |
| Ready-preflight digest | `6155111ea02d395bd51e0b03dbb18f536aea63807bec121bf028c82a0717dc2a` |
| Ready-preflight file SHA-256 | `c2946a3b5d0d8e34e9a1832a7e924bb5810b355fb812ee076c1d10f84d72b617` |
| Blockers | `0` |
| Operation ID | `gate4c-menu-first-20260723t234705z-451c651c` |
| Session digest | `0a0d9153d20753aa203958d1eb76c6be18890e16b1a114b3dbf1134817855179` |
| Session file SHA-256 | `d091125fbeb583d859be7d9a217dbeca81700b5a2d0692cda6369f6f3fdae638` |
| Protected baseline digest | `886a2ec43b188fb61d92a2d77b6b128d367afac0ffc2cd9eb3025674065cd1ae` |
| Writable baseline digest | `5380bf864764e1bbdf5d40cddf52bf353f379791655e2d8ca32caf6eadea6072` |
| Baseline file SHA-256 | `4841e412963817e1ca1db55996449ec7caaecc0b5621d8422fea35228aea3132` |
| Plan ID | `play-plan-87069ebdf2eef8f5d2f9f37f31a40b39` |
| Plan digest | `87069ebdf2eef8f5d2f9f37f31a40b39d48bee99895be0da9bd56ca57ad79c5b` |
| Plan file SHA-256 | `067828b0d250049e58d0a020c02b02045d36a05839dc6e59c04d4d6571d588a0` |
| Provider refusal | `permit_wrong_evidence` at `$candidate.observer` |
| Factorio process | not created |

The baseline began at `2026-07-23T23:47:05.325441Z` and completed at
`2026-07-23T23:51:33.593441Z`.

## Attempt 2

| Evidence | Identity |
| --- | --- |
| Observer self-test digest | `0bde0465b57e808ee28db26a1712ca6eaffd57d20b0af60cdee3d1e598af6db6` |
| Observer artifact SHA-256 | `ef0ea85d53e2a75d83f5253e398e1b048e2d82e31a898477e0af5218c2d82c61` |
| Observer result | `pass`; zero lost events; exact attribution complete |
| Ready-preflight digest | `0c15ff73850fac27f72e07758e16f0e7f9be5e7292c25412bfc77581c18cb46f` |
| Ready-preflight file SHA-256 | `4237ee8d8175c64f7744679a1260b2ba5f1eedbd315343103367594cb75a1227` |
| Blockers | `0` |
| Operation ID | `gate4c-menu-first-20260724t005357z-926a6bd5` |
| Session digest | `fb90b55b83afa85989a87a78b5667bf857f65ffd2e581e91d4f0a4214f69ab0c` |
| Session file SHA-256 | `132c1741e5da442800a10b08fb77e1a868fb98ff5d4bf8d2e98c8834c9fdde25` |
| Protected baseline digest | `886a2ec43b188fb61d92a2d77b6b128d367afac0ffc2cd9eb3025674065cd1ae` |
| Writable baseline digest | `096a8a9956d9866452bcdfc9d69a970495a7baebaa8f8e59a282723c06bfe3f2` |
| Baseline file SHA-256 | `79d094e7cc4ef3a2b58dd511d4e5f5da19fbe96e389dda17f4921149976530b9` |
| Plan ID | `play-plan-3444817c2919824e34a33733ab9d68f2` |
| Plan digest | `3444817c2919824e34a33733ab9d68f2209621ff5d5a0a9bf21c2edec2c506dc` |
| Plan file SHA-256 | `0a6d1496044afcbb7fd02d0bd584b2af03a7461711c55b72c3b4ba9f1af8a1a6` |
| Provider refusal | `permit_wrong_evidence` at `$candidate.observer` |
| Factorio process | not created |

The baseline began at `2026-07-24T00:53:57.149439Z` and completed at
`2026-07-24T00:54:57.385439Z`.

## Operator transcript

The retained operator transcript has SHA-256:

```text
dc518cdd716ab01edd4e4c32c13672d8d48992955b8f67e98e83be9d6dbabb99
```

It records both exact provider refusals. It contains no permit authenticator,
session HMAC key, credential, Steam token, or reusable permit envelope.

## Missing evidence

The following absence is part of the Inconclusive result, not evidence that
the corresponding condition passed:

- no `capture-token.json`;
- no ETL trace, decoded event dump, or observer loss report;
- no process lifecycle or separated process output;
- no post-run comparison;
- no native technical packet;
- no normal-menu, save, exit, or relaunch human observation.

The current harness maps the underlying observer-start helper failure to the
generic provider refusal and does not persist the helper stderr. Root cause is
therefore not established by this verdict task.
