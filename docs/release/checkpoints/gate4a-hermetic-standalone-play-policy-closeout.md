# Gate 4A hermetic standalone Play policy closeout

## Disposition

Gate 4A is accepted on reviewed `dev` as a policy-only checkpoint. PR #47
merged the reviewed head `cf674d852e16ceb237ab83dc9254b37b0d900aa2`
at `dev` revision `51f4fc24c9164762a88b92b4f865b04fe9256d4b`.

The accepted policy freezes one measurable claim before candidate code or a
real-product run:

```text
policy  facman.hermetic-standalone-play.2.0.77.windows-x64.v1
claim   factorio.hermetic_process_tree.v1
digest  6fde31f26d57e23d67c01dd598cb869a4914d11711868b46d4f817709455e7a2
```

It does not claim whole-host immutability, issue a permit, expose a launch
route, execute Factorio, or grant process authority.

## Frozen candidate law

The first candidate is limited to:

- Windows x64;
- Factorio 2.0.77 from an authenticated Wube-owned, non-Steam standalone
  source;
- a fixed local NTFS volume with stable identities and no link or reparse
  traversal;
- one FacMan-owned instance with base-game capability and an explicit empty
  mod lock;
- no account, credential, Mod Portal, or network requirement;
- `menu` as the only launch intent; and
- `hermetic` as the singular isolation mode.

The canonical policy contains 13 exact writable resources, 18 protected,
forbidden-observed, or disclosed external domains, 31 evidence requirements,
two independent observation forms, and 29 automated, human, and deferred
interruption or journey cases.

Writable authority is bound to exact stable resources. A workspace string
prefix, an instance-root prefix, a wildcard, or path equality alone is not an
acceptable resource identity.

## Observation and verdict law

The later candidate must combine:

1. attributed observation of FacMan, Factorio, supervised children, and
   explicitly identified providers; and
2. stable no-follow before/after manifests for protected files, directories,
   identities, hashes, absence states, and relevant registry values.

Lost events, observer overflow, unknown process identity, unresolved paths,
incomplete manifests, attribution gaps, host restart, or corrupt evidence
force `Inconclusive`. They cannot be waived into `Pass`.

A `Pass` also requires the normal Factorio menu, no inferred save or alternate
intent, successful instance-local saving and relaunch, no attributed write
outside the writable set, unchanged protected roots, exact one-time permit
consumption, hash-closed evidence, and a human reviewer bound to that packet.

An attributable external write, protected-root change, wrong intent, inferred
save, accepted stale or replayed permit, or falsely completed recovery state is
a `Fail`. Neither `Fail` nor `Inconclusive` grants authority.

## Exact reviewed-head proof

The exact PR #47 head passed both push and pull-request workflow sets:

| Proof | Push run | Pull-request run | Result |
| --- | --- | --- | --- |
| CI | `29846149703` | `29846178980` | Pass |
| Code security | `29846150053` | `29846179861` | Pass |
| Schema check | `29846150047` | `29846179477` | Pass |
| Security policy | `29846149398` | `29846179286` | Pass |

CI included Linux, macOS, and Windows native builds, coverage, sanitizers,
packaging and reproducibility proof, AppKit compile proof, the full Python and
strict suites, and the policy's negative-control corpus. Code security passed
for every configured language.

## Exact merged-`dev` proof

The exact merge revision passed:

| Proof | Run | Result |
| --- | --- | --- |
| CI | `29847230819` | Pass |
| Code security | `29847230890` | Pass |
| Schema check | `29847230200` | Pass |
| Security policy | `29847230265` | Pass |

The local implementation matrix additionally passed:

- fresh Visual Studio 2022 x64 Debug configure and warnings-as-errors build;
- native CTest, 47 of 47;
- full Python suite, 372 passed and 2 expected skips;
- strict state of 274 schemas, 125 commands, 123 registered routes, and 242
  refusal codes;
- AIDE Lite, project-state, schema, source-format, commit-policy, changelog,
  and diff validation.

Two local wrappers reached their 120-second command window. The build passed
when resumed; the first Python process had already printed `OK`, and a second
wider-window run returned exit code zero. These were recorded command-duration
limits, not test failures.

## Clean pinned reconstruction

One unique temporary root used detached, clean clones at:

| Repository | Revision |
| --- | --- |
| FacMan | `51f4fc24c9164762a88b92b4f865b04fe9256d4b` |
| Universal Launcher | `7bd4425f0c35414f738159b45d8bec42edf70235` |
| Universal Setup | `3f8489275077347c2918f3bb03614ec6431362ff` |

All three repositories configured, built, tested, and passed strict checks.
FacMan additionally passed AIDE Lite and its complete Python suite. The serial
matrix completed in 404.8 seconds, the three source checkouts remained clean,
and the complete temporary clone/build root was removed immediately.

## Authority boundary

This checkpoint does not promote:

- product permit issuance;
- `instance.play` or real Factorio execution;
- preparation, installation apply, or Universal Setup mutation;
- credentials, networking, host mutation, signing, or publication;
- alternate launch intents, Steam, foreign installations, or third-party
  modpacks;
- a human Play verdict, playability, Safe beta, or canonical `main`.

## Next transition

The exact policy digest must be promoted separately to canonical `main` with
no authority change, then `main` ancestry must be synchronized back into
`dev`. Only after that sequence may
`FACMAN-HERMETIC-STANDALONE-PLAY-CANDIDATE-01` become active.

Candidate implementation remains distinct from the later human-reviewed
`FACMAN-HERMETIC-STANDALONE-PLAY-VERDICT-01`. The policy criteria cannot be
weakened retroactively in response to a candidate result.
