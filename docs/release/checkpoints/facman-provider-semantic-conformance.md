# FacMan provider semantic conformance

Date: 2026-08-06

Status: complete; SDK consumption next

WorkUnit: `THREE-REPO-SOURCE-VS-SDK-CONFORMANCE-01`

## Exact result

```text
base                 715422842c7db8ca52162091ca70026b99768da2
implementation head  5584912409629a8b9ddbf4f981540792b6e96242
implementation tree  2affe7effcdfb02590d0be79c5d2c83a4e18a59e
pull request          125
provider-input phase complete
semantic phase       complete
parent result        PASS
next WorkUnit         FACMAN-PROVIDER-SDK-CONSUMPTION-01
```

The exact accepted provider sources are ULK
`1cafe4054297cc11e02458b83d230db0cd064471` and USK
`32488fc13bd2439f9f6e52e83a97f6da345a7650`. This checkpoint records their
conformance; it does not adopt them as active FacMan product inputs.

## Closed semantic matrix

The same deterministic corpus passed through:

```text
source_static
source_shared
installed_static
installed_shared
relocated_installed_static
relocated_installed_shared
private_runtime
```

Each mode agrees within its platform on command dispatch, operation outcomes,
structured refusals, interrupted recovery, release resolution, and provider
contract identity. Eleven adversarial mutations are refused, including changes
to authority, command availability, effects classification, operation outcome,
contract identity, recovery action, refusal code, release-resolution root,
forged normalization markers, unknown absolute paths, and unknown
mode-dependent fields.

## Hosted proof

Workflow run `31083408091` passed at the exact implementation head on Linux
x64, Windows x64, and macOS Intel. Semantic artifact IDs and archive digests:

```text
Linux    8960771817  dfe76885872ffcd20ddf964a78d7a15cb8693b8a4e147debe34e4883f4e97bc9
Windows  8961145371  f23154596e140023d6ba4f6e7ce7c156681cdd15b3df7d6bd799f70c44dfac67
macOS    8960938487  2c28add0a0202504508e4c49c2bf8430522499f180bdad3440e89c3ef81d56c0
```

All observations validate against the checked-in schema, contain exactly seven
passing modes, six passing semantic classes, eleven refused negative controls,
zero required skips, and an all-false authority table. Platform-specific
normalized digests are retained in the WorkUnit validation evidence rather
than incorrectly asserting binary or toolchain identity across platforms.

The exact-head general CI, code-security, schema, security-policy, and synthetic
TCK workflows also passed. The local promotion profile passed 878 tests with
zero failures/errors and zero required/unknown skips after the canonical native
tree was rebuilt at the exact head.

## Unchanged inputs

The active workspace lock, authored provider lock, and successor route v1 are
byte-identical to the accepted base. In particular, the workspace continues to
consume ULK `7fc25340623131ba86c08dca4fb8a43b18a4520d` and USK
`3048128963dc718a7c38c1cfcdda9e813a23b0db` while release coherence remains
fail-closed.

## Next boundary

`FACMAN-PROVIDER-SDK-CONSUMPTION-01` may now begin from the exact integrated
`dev`. It must turn installed provider inputs into independently consumable,
production-capable but still non-adopted build inputs. It may not change active
provider pins or combine SDK consumption with provider reconciliation.

## Authority ceiling

This checkpoint grants no provider adoption, provider repin, Factorio
execution, observer capture, prepare, permit, product execution, Setup mutation,
signing, publication, support, route capability, route promotion, or `main`
promotion authority.
