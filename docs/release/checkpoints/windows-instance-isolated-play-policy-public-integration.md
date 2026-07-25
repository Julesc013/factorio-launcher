# Windows Instance-Isolated Play policy canonical integration

## Outcome

The exact reviewed Windows Instance-Isolated Play policy is canonical on
`main`, synchronized into `dev`, and immutable for the separately activated
candidate WorkUnit.

```text
policy ID:
  facman.windows-instance-isolated-play.2.0.77.x64.v1

claim ID:
  factorio.windows_instance_isolated_process_tree.v1

policy digest:
  8d8189a9e8fc9ff7e479f7dda1adf0ea516bed2878046468022b2da8355e2432
```

This checkpoint is policy and evidence only. It does not make FacMan
playable and does not promote product authority.

## Reviewed chain

| Boundary | Pull request | Exact revision |
| --- | ---: | --- |
| Policy implementation | #67 | `28495de937f1184dacc745f41dcac675756ef931` |
| Policy closeout | #68 | `5267d17b8fc8095d31448044dded6d42eda75fda` |
| Policy-only canonical promotion | #69 | `f9670ed6afedcbf9b5c297e8ead478cd3aeea4c5` |
| Ancestry-only synchronization | #70 | `c49a9b5cf1a660e63730cae02778af3e00894a87` |

The canonical and synchronized trees were identical:

```text
d7cbe1339423b1dcda2763231aa9e99d4a59476a
```

`main` is an ancestor of the synchronized `dev` revision.

## Closeout proof

PR #68 reviewed exact head
`e535f279c539477c127915ae3fd56b451dae4291`.

```text
push CI                 30145909636 PASS
push code security      30145909643 PASS
push security policy    30145909646 PASS
PR CI                   30145919714 PASS
PR code security        30145919721 PASS
PR security policy      30145919719 PASS
merged-dev CI           30146288814 PASS
merged-dev code security 30146288802 PASS
merged-dev security policy 30146288806 PASS
```

The closeout was documentation/truth only, so schema identity remained the
exact implementation schema result `30145199268`.

## Promotion proof

PR #69 used the exact closeout revision as its head; it added no new commit.
Its duplicated push and pull-request matrices passed:

```text
push CI                 30146680925 PASS
push code security      30146680930 PASS
push security policy    30146680926 PASS
PR CI                   30146702107 PASS
PR code security        30146702121 PASS
PR schema               30146702112 PASS
PR security policy      30146702129 PASS
```

Exact canonical `main` passed:

```text
CI                30147122318 PASS
code security     30147122296 PASS
schema            30147122303 PASS
security policy   30147122308 PASS
```

The promotion includes the accepted Gate 4B and Gate 4C evidence history.
In particular, Verdict 03 remains `Inconclusive`; canonicalization does not
reinterpret it as Pass.

## Synchronization proof

PR #70 contained one canonical ancestry commit and zero changed files:

```text
files       0
additions   0
deletions   0
```

Its duplicated push and pull-request matrices passed:

```text
push CI                 30147488160 PASS
push code security      30147488155 PASS
push security policy    30147488152 PASS
PR CI                   30147496286 PASS
PR code security        30147496272 PASS
PR security policy      30147496288 PASS
```

Exact synchronized `dev` passed:

```text
CI                30147917473 PASS
code security     30147917492 PASS
security policy   30147917475 PASS
```

The sync tree was identical to canonical `main`; schema disposition therefore
remains the exact canonical schema pass `30147122303`.

## Reproduction floor

The implementation closeout bound a clean pinned three-repository
reproduction:

```text
FacMan             28495de937f1184dacc745f41dcac675756ef931
Universal Launcher 7bd4425f0c35414f738159b45d8bec42edf70235
Universal Setup    3f8489275077347c2918f3bb03614ec6431362ff
elapsed            455.2 seconds
result             PASS
```

The accepted strict truth contains 292 schemas, 125 command contracts, 123
registered routes, and 242 refusal codes.

## Transition validation

The truth-only candidate activation was checked locally without changing
runtime or either frozen policy:

```text
focused truth/policy tests    32 PASS
full Python discovery         468 PASS, 314 expected skips
strict validation             PASS
project-state validation      PASS
AIDE Lite validation          PASS
queue-state validation        PASS
```

The full Python discovery reused the exact retained clean-reproduction native
build bound above; it did not create a new source-repository build tree.

## Activated boundary

Only this WorkUnit is activated:

```text
FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-CANDIDATE-01
```

Its implementation remains absent from this checkpoint. The later human
verdict remains a separate boundary:

```text
FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-VERDICT-01
```

## Authority exclusions

This checkpoint does not enable:

- public `instance.play`;
- product permit issuance;
- Factorio execution or a human Pass;
- Setup or installation mutation;
- credentials, networking, or Steam;
- signing or publication;
- external OS/driver writes as permit resources;
- normal-host hermetic or whole-host immutability claims;
- playability or Safe beta.

The canonical Gate 4A hermetic policy remains unchanged. Future hermetic Play
requires an enforced sandbox boundary.
