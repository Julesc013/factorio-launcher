# Validation evidence

## Exact implementation state

```text
FacMan base      715422842c7db8ca52162091ca70026b99768da2
FacMan head      5584912409629a8b9ddbf4f981540792b6e96242
FacMan tree      2affe7effcdfb02590d0be79c5d2c83a4e18a59e
PR               125
branch           task/facman-provider-semantic-conformance-01
topology         6 ahead, 0 behind
ULK main         1cafe4054297cc11e02458b83d230db0cd064471
ULK tree         47018102de4b9fd20af9f77acd4e1e35e51590f3
USK main         32488fc13bd2439f9f6e52e83a97f6da345a7650
USK tree         12fe757b1fc2ae78768a8cf912d03835f46ca65b
```

The semantic implementation is six commits above the exact accepted Phase-A
integration and zero behind it. PR #123's original source-closure branch was not
modified.

## Hosted semantic matrix

Workflow run `31083408091` passed at the exact implementation head. Every
semantic observation validates against
`facman.provider_semantic_conformance_observation.v1`, binds the exact FacMan
commit/tree and accepted provider commits/trees, contains exactly seven passing
modes, reports all six semantic classes as `pass`, refuses all eleven negative
controls, has `required_skips = []`, and keeps every authority field false.

| Platform | Job | Result | Normalized semantic SHA-256 | Observation SHA-256 |
| --- | --- | --- | --- | --- |
| Linux x64 | `92557391622` | PASS | `29bd59f90feee0b99ab2ed30698fa33e80ef94739b1b86f1d01e1e53ecba2a29` | `3b7f695e84387fa27312d4ca845a2082604dd4efb10279a39114de0ed1f45bca` |
| Windows x64 | `92557391642` | PASS | `f07d8225a117a29b0474591d0034d61795870a0e490fd540fd17677287f2d379` | `cd2825dcb1f8a6bc11645fab95f13f170a484fe1bec56839c8979dec0e41a945` |
| macOS Intel | `92557391578` | PASS | `c01e26466982fbd196c67c418e4b2c334580b4134cd8252342059a8ed8d37a32` | `3dde164876c0f9279a2977775bfda18418e3151757aad822027d5800a23de5bf` |

The platform digests intentionally differ because the target and toolchain are
material inputs. Within each platform all seven modes have the one recorded
normalized digest.

## Hosted artifact custody

| Artifact | ID | Bytes | Archive SHA-256 |
| --- | ---: | ---: | --- |
| Linux provider input | `8960710041` | 143356 | `a2515e96fccbf3555dc9d229b31d140e26f0015034c923b351da16c632a75568` |
| Linux semantic | `8960771817` | 223792 | `dfe76885872ffcd20ddf964a78d7a15cb8693b8a4e147debe34e4883f4e97bc9` |
| Windows provider input | `8961107162` | 144268 | `692f0a4fb07dff165f834a27fa156e020acb327d9ae135af11f1f078ce7f0ab7` |
| Windows semantic | `8961145371` | 224714 | `f23154596e140023d6ba4f6e7ce7c156681cdd15b3df7d6bd799f70c44dfac67` |
| macOS semantic | `8960938487` | 224802 | `2c28add0a0202504508e4c49c2bf8430522499f180bdad3440e89c3ef81d56c0` |

Extracted copies are retained outside the repository under
`D:\Projects\Factorio\Evidence\pr125-5584912-hosted`. The independently
audited semantic directories contain 134 files each. The Linux, Windows, and
macOS extracted byte counts are 1,939,823; 1,980,955; and 1,943,637
respectively.

The standalone provider-input observations also pass their bounded matrix:
six provider-input/runtime modes, nineteen refused negative controls, full and
relocatable ULK/USK self-conformance, a shared non-adopted candidate-lock digest
`1aebf232e2e26330c0a73dbb50ce26d75706bc6bf329e4bf1692d1d3927290ee`,
and every authority false. Their observation SHA-256 values are
`5ecc62854df0a44ecbc9643b63799b7eea26205053959fcd3b3006a8236a2639`
for Linux and
`3b98327ace5f072534af3532dd6ed6a20b47b7d45ae77d256f5913740f020faf`
for Windows.

## Exact-head repository checks

```text
ci                              31083407955  PASS
code-security                   31083407753  PASS
schema-check                    31083408213  PASS
security-policy                 31083407882  PASS
synthetic-product-tck           31083407760  PASS
bounded-provider-input          31083408091  PASS
```

General CI passed Linux native and coverage, Windows native/package, macOS
native/archive, and AppKit compile jobs. The PR has no review threads.

## Local promotion validation

The canonical Visual Studio native tree was regenerated at exact head
`5584912409629a8b9ddbf4f981540792b6e96242` with the unchanged workspace pins,
`provider_mode=source`, `provider_release_identity_coherent=false`, and
`source_dirty=false`. The Debug build completed successfully.

`python tools/test_obligations.py --profile promotion` then passed:

```text
tests                       878
failures                    0
errors                      0
required_blocked skips      0
unknown skips               0
unsupported skips           5
optional skips              1
gate_passed                 true
```

The five unsupported cases require local Windows symlink privileges; the one
optional case is the separately enabled full-scale bounded performance corpus.
Strict validation within the profile passed with 330 schemas, 694 SPDX-scoped
files, 125 commands, and 242 refusal codes.

## Immutable inputs and authority

```text
workspace_lock.v1.toml SHA-256
866a053416d5d4f648d7f777c3ba709b8f089da3e9bb3b65281b58c8d243597f

providers.lock.v2.toml SHA-256
2cfcbf4ce320e01c760a045deaeac62d8c902c79a197e55ae387ae481fefb799

successor_play_route.v1.toml SHA-256
98561d1c956435d0d57fd7f184545c0fdfa3bf2586ec944c59b9ee75bdde8632
```

All three are byte-identical to the exact base. Provider adoption, provider
repin, release eligibility, Factorio execution, observer capture, permit
issuance, product execution, Setup mutation, signing, publication, and route
promotion remain false.
