# Validation evidence

## Exact implementation state

```text
FacMan base      844197dc8a4229dbbd88701935149553501c6bc9
FacMan head      1a8bcbf641eb90056f5c7543140ea24bcfac83f2
FacMan tree      b5d66eb2e6b9d6c196bc17babdb9ad860c3e58e7
PR               126
branch           task/facman-provider-sdk-consumption-01
topology         3 ahead, 0 behind
ULK main         1cafe4054297cc11e02458b83d230db0cd064471
ULK tree         47018102de4b9fd20af9f77acd4e1e35e51590f3
USK main         32488fc13bd2439f9f6e52e83a97f6da345a7650
USK tree         12fe757b1fc2ae78768a8cf912d03835f46ca65b
```

## Exact hosted SDK-consumption matrix

Workflow run `31101009139` passed at the exact implementation head. Each
observation validates against
`facman.provider_sdk_consumption_observation.v1`, binds the exact FacMan and
provider commits/trees, contains exactly seven passing modes, refuses all seven
negative controls, records zero required skips, and keeps every authority
false.

| Platform | Job | Semantic SHA-256 | Observation SHA-256 |
| --- | ---: | --- | --- |
| Linux x64 | `92614302233` | `29bd59f90feee0b99ab2ed30698fa33e80ef94739b1b86f1d01e1e53ecba2a29` | `efc18aefd3e51431c9d9b43408f0770afb3c6ef5d647f5ee6e0ee7d676314cf7` |
| Windows x64 | `92614302305` | `f07d8225a117a29b0474591d0034d61795870a0e490fd540fd17677287f2d379` | `b50fa634525a089e296a47b4c80e4d84a417d6964e57e2e634e54f07b7f7e62e` |
| macOS Intel | `92614302317` | `c01e26466982fbd196c67c418e4b2c334580b4134cd8252342059a8ed8d37a32` | `5363c54b7fc10eb356ec567edf62a062e83c2dd02ca001cb2f87a9945f520a1a` |

All seven modes on every platform have the expected provider-runtime count:
zero for source/installed/relocated static and two for source/installed/
relocated shared plus private runtime. Installed modes are source-independent,
source rollback passes, and the normalized semantic digest is equal across all
seven modes within each target. Cross-platform digest differences remain
material target/toolchain inputs rather than being normalized away.

The shared SDK-consumption candidate-lock SHA-256 is
`9d1c636a6612fbf89af990ddd392fbe1ba808f3be7f7458247b818e1aa3cd3f6`.
The nested Phase-A candidate-lock SHA-256 is
`add152ae456bccf5940a87fa005979dca544fb590e530a60b5970beda51c901b`.
Every nested Phase-A result is `bounded_provider_input_conformance_pass` with
zero required skips and all authority false.

## Hosted artifact custody

| Platform | Artifact ID | Archive bytes | Archive SHA-256 | Extracted files | Extracted bytes |
| --- | ---: | ---: | --- | ---: | ---: |
| Linux | `8968071963` | 157930 | `2cdd71c9dbf834b1d1354462f62b11403b17135636e79a80de38507b0b9869e9` | 59 | 2059588 |
| Windows | `8968889249` | 151875 | `83f8d9ef7b6d84913f197e27a2d2c3eaa4eeaf6cf1592e56508fac398aabc9dd` | 59 | 1996098 |
| macOS | `8968505880` | 158645 | `cc1119d9a43f5253ec13bcd28e85462feb49f152da7d32c1507ce8d6591c06a6` | 59 | 2066055 |

Durable extracted copies are retained outside the repository under
`D:\Projects\Factorio\Evidence\pr126-1a8bcbf-hosted`. The Phase-A observation
SHA-256 values are `dfcbba6c2e35a652da7b8921ae409f334b837cecef8c738a364290d4b9aee6b3`
(Linux), `c7a2fac0f8cf4bf8bdc72cbdca39bab06484b87338c6618c933ec291268fab8e`
(Windows), and `bf10987e38a86c233871591e09255a82a3a7c160f7dfd23093cb169158fe849d`
(macOS).

## Exact-head repository checks

```text
ci                              31101008893  PASS
code-security                   31101011587  PASS
schema-check                    31101009058  PASS
security-policy                 31101009846  PASS
synthetic-product-tck           31101010333  PASS
bounded-provider-input          31101009364  PASS
provider-sdk-consumption        31101009139  PASS
```

General CI passed Linux native/coverage, Windows native/package, macOS
native/archive, and AppKit compile. The bounded provider rerun passed its exact
Linux, Windows, and macOS matrix. There are no required or unknown skips in the
hosted SDK-consumption proof.

## Local validation

- Complete Windows seven-mode development rehearsal: PASS. It is explicitly
  classified as a rehearsal because provider self-conformance was skipped and
  is superseded for acceptance by the hosted exact-head proof.
- Normal tracked-source Windows package reproduction: PASS, including all nine
  built-package artifact tests and exact ULK/USK shared-runtime presence.
- Focused provider/CMake/semantic/package suite after the compatibility repair:
  PASS, 69 tests with one unsupported local symlink-privilege skip.
- Strict validation: PASS, including 331 schemas, 696 SPDX-scoped sources, 125
  commands, and 242 refusal codes.
- Portable AIDE validation: PASS.

## Immutable records

```text
workspace_lock.v1.toml
866a053416d5d4f648d7f777c3ba709b8f089da3e9bb3b65281b58c8d243597f

providers.lock.v2.toml
2cfcbf4ce320e01c760a045deaeac62d8c902c79a197e55ae387ae481fefb799

successor_play_route.v1.toml
98561d1c956435d0d57fd7f184545c0fdfa3bf2586ec944c59b9ee75bdde8632
```

Provider adoption, provider repin, release eligibility, Factorio execution,
observer capture, permit issuance, product execution, Setup mutation, signing,
publication, route capability, route promotion, and `main` promotion remain
false.
