# FacMan provider SDK consumption

Date: 2026-08-06

Status: complete; provider pin reconciliation next

WorkUnit: `FACMAN-PROVIDER-SDK-CONSUMPTION-01`

## Exact result

```text
base                 844197dc8a4229dbbd88701935149553501c6bc9
implementation head  1a8bcbf641eb90056f5c7543140ea24bcfac83f2
implementation tree  b5d66eb2e6b9d6c196bc17babdb9ad860c3e58e7
pull request          126
provider inputs       exact and independently consumable
provider adoption     false
provider repin        false
release eligibility   false
next WorkUnit         FACMAN-PROVIDER-PIN-RECONCILIATION-01
```

The exact accepted provider sources are ULK
`1cafe4054297cc11e02458b83d230db0cd064471` (tree
`47018102de4b9fd20af9f77acd4e1e35e51590f3`) and USK
`32488fc13bd2439f9f6e52e83a97f6da345a7650` (tree
`12fe757b1fc2ae78768a8cf912d03835f46ca65b`). This checkpoint proves their
explicit consumption; it does not adopt them into FacMan's tracked locks.

## Closed consumption matrix

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

Source mode remains an exact rollback and source-closure path. Installed modes
use explicit package roots and identity sidecars, require no provider checkout
after configuration, and have no ambient registry, `PATH`, arbitrary
`CMAKE_PREFIX_PATH`, or sibling fallback. Static packages contain no provider
runtime; shared and private-runtime packages contain exactly the two declared
provider runtimes.

The candidate lock is
`9d1c636a6612fbf89af990ddd392fbe1ba808f3be7f7458247b818e1aa3cd3f6`.
It is classified `candidate_not_adopted`, `release_eligible=false`, and
`tracked_lock_mutated=false`.

## Hosted proof and custody

Workflow run `31101009139` passed at the exact implementation head on Linux
x64, Windows x64, and macOS Intel. All three observations contain exactly seven passing
modes, seven refused negative controls, zero required skips, exact provider
commits/trees, and an all-false authority table.

| Platform | Artifact ID | Archive SHA-256 | Observation SHA-256 |
| --- | ---: | --- | --- |
| Linux | `8968071963` | `2cdd71c9dbf834b1d1354462f62b11403b17135636e79a80de38507b0b9869e9` | `efc18aefd3e51431c9d9b43408f0770afb3c6ef5d647f5ee6e0ee7d676314cf7` |
| Windows | `8968889249` | `83f8d9ef7b6d84913f197e27a2d2c3eaa4eeaf6cf1592e56508fac398aabc9dd` | `b50fa634525a089e296a47b4c80e4d84a417d6964e57e2e634e54f07b7f7e62e` |
| macOS | `8968505880` | `cc1119d9a43f5253ec13bcd28e85462feb49f152da7d32c1507ce8d6591c06a6` | `5363c54b7fc10eb356ec567edf62a062e83c2dd02ca001cb2f87a9945f520a1a` |

Durable extracted copies are retained at
`D:\Projects\Factorio\Evidence\pr126-1a8bcbf-hosted`. The exact package,
inventory, ABI, contract, licence, toolchain, runtime, and provider-source
identities inside those artifacts are the selection inputs for atomic pin
reconciliation; no digest may be guessed from a source commit.

General CI (`31101008893`), code security (`31101011587`), schema
(`31101009058`), security policy (`31101009846`), synthetic TCK
(`31101010333`), and bounded provider conformance (`31101009364`) also passed
at the exact implementation head.

## Unchanged active truth

The tracked workspace lock, authored provider lock, and immutable successor
route v1 remain byte-identical to the accepted base. FacMan therefore still
consumes its prior accepted provider pins, while strict release coherence
continues to refuse the unreconciled authored provider identities.

## Next boundary

After this exact branch is accepted and integrated into `dev`, activate
`FACMAN-PROVIDER-PIN-RECONCILIATION-01` from the resulting merge commit. That
WorkUnit may select only the accepted canonical provider pair above and must
align the complete source/package/ABI/contract/build/TCK/observation truth in
one independently revertible change. Immutable successor route v1 remains
untouched.

## Authority ceiling

This checkpoint grants no Factorio execution, observer capture, prepare,
permit, product execution, Setup mutation, credentials, signing, publication,
support, route capability, route promotion, or `main` promotion authority.
