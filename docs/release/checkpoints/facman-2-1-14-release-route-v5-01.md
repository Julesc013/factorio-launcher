# FacMan 2.1.14 exact-alpha release route v5

Date: 29 August 2026

State: `review_ready_non_authorizing`

## Result

WorkUnit `FACMAN-2.1.14-RELEASE-ROUTE-V5-01` defines one immutable v5
successor for the sealed FacMan `0.1.0-alpha.1` candidate. It does not launch
Factorio or Windows Sandbox, issue a permit, record a human verdict, select an
accepted route, publish a GitHub release, sign an asset, activate support, or
promote `main`.

The source must first integrate through protected `dev`. Only a later,
separately authorized host-side D3 packet may supply launch-specific freshness
and one-use permit material, and only Jules may record the route verdict.

## Protected base and sealed candidate

The v5 definition is based on protected `dev` merge `428ff530` after all five
push workflows completed successfully. Its exact candidate closure is:

```text
protected base     428ff530e09d0a63ed4ecebe11f17cac29f51451
protected tree     5cd260c461c75b93b60b0eaf3d9cf0d76f22cc4d
product source     fa60aaa17e9044bef7bb7347261056959690f1cd
product tree       5536891662461d3617ee40e93654cb2f0659905c
tag object         52a7a66092ff2b3b3c1059e9c29260f95b1cb287
candidate record   8e18cf7b35d34aee2e39bc6bae0710db48dceef4196d5ff0373b880bfc866573
WinForms package   00fcf5dfc9597a7118ad8d81ff4489d5ace6019c272e79bcc12e966547149c86
contract set       7d59831268babc1be96192f8ed74f5aa5f5c85d9d1fdf9e392cc943f99eae264
provider lock      d33943841431afdeffb7961c7453d8999619ef371793a6310ad2c2952b118f00
qualification run  33200886091
```

The route package is the 6,127,233-byte
`FacMan-0.1.0-alpha.1-windows-x64-portable.zip`. The candidate and package
remain unsigned, unsupported, and unpublished.

## Private Factorio input

The retained licensed input remains outside Git and every distributable:

```text
archive size        1,649,579,438 bytes
archive SHA-256     4f2875cb5c1325a1fcd21b2d37248d508dc36f51ddeef7406ca96788773b872f
executable          bin/x64/factorio.exe
executable size     49,045,456 bytes
executable SHA-256  0ee725652cfa340008d793bece687aea112475599da01521de05413bdf792695
version/build       2.1.14 / 87180
capability          base game
```

The route exposes no private archive path. The builder requires a regular,
non-symlink local file with the exact size/hash binding and maps it read-only
into a network-disabled Sandbox.

## Isolation and permit topology

Policy v3 preserves the v2 five-folder WSB topology: candidate, private input,
harness, and permit handshake are read-only; only the evidence folder is
writable. Networking, clipboard, printer, audio input, video input, and vGPU
are disabled, and Protected Client is enabled.

The v2 freshness record additionally binds the raw route record, canonical
route digest, candidate record and package, contract set, providers, Factorio
archive and executable, clean-host receipt, observer source, generated WSB,
guest runner, bundle builder, exact launch ordinal/action/operation/attempt,
and the first terminal receipt for launch two.

Launch one uses:

```text
facman.successor-play.launch-1.operation.05
facman.successor-play.launch-1.attempt.05
```

Launch two uses:

```text
facman.successor-play.launch-2.operation.05
facman.successor-play.launch-2.attempt.05
```

The second permit cannot be preissued. It requires exported launch-one
terminal evidence and a fresh host safety revalidation. Both permits are
short-lived, HMAC-authenticated, atomically claimed before dispatch, one-use,
and distinct in operation, attempt, permit, and freshness identity.

## Canonical source identities

```text
policy v3 digest       beabc7de89c2d450ddff1c02ee82daa5b535b350a50da609e83e85f71627e88b
source closure         6e3345e887540ac085d64b7fd0eeb54aa5e5ea77d2642abccd93549dcb9267dc
route v5 digest        d4627348d997ab20d8f5a540b8571bca145048ff6da365d0b42fdc18714c689e
observer source        4fbb9a6bd23b8a89a66c95a4a8ab93cedceabfd4a59646d50088c023c026b6ef
harness source         f86035674c01e2a57a0cf1108b8e7998046d0e66a0520e9c6ca874ffe4b98859
permit gate source     a23279ad56bad7ffe51fe6a00af012ff777e59ffb928db3aa8b1b4018efa3275
permit gate header     b5f7b4c04b758d9452e76863208357854c37c12eeedeee6b3f2fdf0b1981f7df
build definition       8facb7b6c95b3edcbde85654ba8498010cbbe9dc9fd80fc14252c1a7e0e42066
guest runner           fce2daf19f5ba17ce0da95f7b1f0524b0f5d4fbdb3c42ad37781377891f1f818
bundle builder         96e07e9470f6beb74c2d9cf91aa058b02a0e33b95074bbad300f4123c966d5c0
```

The v4 route SHA-256 remains
`32c5df2d755965aaf07f4193c6754c3a9a1d49526bf6573e6546b03417cb9541`;
the v2 policy SHA-256 remains
`0fa86b6abf0f7fb5feb9c387d6b9b6d1618e25210ee6d7740fd77f33bf9e9825`.
Neither historical file is rewritten or relabeled as alpha.1 route evidence.

## Validation and next gate

The v5 validator recomputes policy, source-closure, route, observer, and schema
digests; preserves v4, policy v2, and the provider lock; keeps the accepted
route index unchanged; and mutates every exact pre-dispatch binding in focused
tests. The current source authority surface is closed and entirely false.

After protected integration, the next packet must build the exact observer
binary, prepare one fresh WSB bundle from the sealed assets and private archive,
issue launch-one only after host revalidation, pause for the exported terminal
receipt, issue launch-two only after a second revalidation, and ask Jules for
`Pass`, `Fail`, or `Inconclusive`. Automated exit status cannot supply that
verdict and no verdict directly grants publication or support authority.
