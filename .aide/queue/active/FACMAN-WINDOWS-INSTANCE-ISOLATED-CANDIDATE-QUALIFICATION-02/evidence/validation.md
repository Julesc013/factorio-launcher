# Validation

Status: LOCAL PASS; HOSTED REVIEW PENDING.

## Fresh remote source closure

The exact repaired source set was reconstructed from three previously
nonexistent `--no-local` HTTPS clone roots. The paths below are local
observations, not portable project requirements:

```text
clone root
  C:\Users\Jules\AppData\Local\Temp\fq27c

build root
  C:\Users\Jules\AppData\Local\Temp\fq27b

qualification and staged handoff root
  C:\Users\Jules\AppData\Local\Temp\
  FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-REVALIDATION-01
```

The closure report passed and is bound by:

```text
SHA-256
  48d6444f620d3f1791104822436a6990093ee6377a73844630de568716180409

observed_at_utc
  2026-07-27T04:07:45Z
```

Exact detached clean source identities:

| Repository | Revision | Tree | Required ref |
| --- | --- | --- | --- |
| FacMan | `d1a3c2029a4ae21c58eda34d7011938bf7bf04cb` | `79492f60c4b11ead7428ffc2dbccabbc090bb148` | `refs/heads/dev` |
| Universal Launcher | `7fc25340623131ba86c08dca4fb8a43b18a4520d` | `f7682630eaa91909aa7ae597dcce5f11846b9b39` | `refs/heads/main` |
| Universal Setup | `3f8489275077347c2918f3bb03614ec6431362ff` | `8861d0d640af8dc24e774f5ff934ad67f8a5d5cd` | `refs/heads/main` |

Every pin was remotely fetchable and contained by its required canonical ref.
All three worktrees were detached, had no alternates, and remained clean after
closure, qualification production and coordinator staging.

The complete proof passed:

- FacMan native CTest: 55;
- FacMan Python: 530;
- Universal Launcher native CTest: 5;
- Universal Setup native CTest: 16;
- strict validation in all three repositories;
- portable AIDE Lite validation;
- required Windows package proof: 14 with zero required skips;
- package pipeline and installed runtime smoke;
- archived-package runtime smoke;
- provenance verification.

The unsigned, unpublished qualification package was:

```text
facman-0.1.0-dev.contract-windows-cli-x64-portable.zip
SHA-256 1c214b6d93e247b4a5a8ae991fa2774a6f2a2a210f63679945f43dd9d5a7b6ea
provenance SHA-256
0a1db78252311c2133fa96681ad59a8800594caa49c041dd2ab13c02f9fe7a65
```

The frozen policy digests remained exact:

```text
hermetic
  6fde31f26d57e23d67c01dd598cb869a4914d11711868b46d4f817709455e7a2

instance_isolated
  8d8189a9e8fc9ff7e479f7dda1adf0ea516bed2878046468022b2da8355e2432
```

## Exact non-executing qualification

The producer authenticated the installed and source-member Factorio 2.0.77
executables as exact Wube Software Ltd bytes, staged the disposable Instance
once, derived its current verification/state identities and reloaded the
immutable qualification binding.

```text
qualification digest
  c73b3b41799246516fcc130fc631f64a80fcd956fd4cf5cb5eb3f92a39b12beb

qualification binding SHA-256
  0bb183c2888c75bf93f6fdb850819323b0772e1ce75a3b5ea2886c2b308bfa31

qualification report SHA-256
  631e043319534da8ddccab60ea7e88ea2be24416b15bce855fcf16d3b9ef2c10

qualification report digest
  230bba5915e783acba0ed51c42912d2ec109a6af211710bd9cc79c2cbe095fec

Factorio executable SHA-256
  d3bcfca4dbee407d472013b745ce2445d34af6f021aacc5753ee0dac54b56b0b

Factorio source archive SHA-256
  ad36e0591e336400e731d5b400038e37c8361fdc71c76c0f6db96ee31741b4c2

authentication evidence digest
  97282b16178bea188e9abc3eac08b2ca3b696976db32eb1e666e544aaabcbe3e
```

Exact candidate artifacts:

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `facman.exe` | 9,425,408 | `380e33e0beff65ab641b4ccd64a7d829e2f303e6906257c1a16af81544ed5a0c` |
| `facman_gate4c_verdict_harness.exe` | 5,565,440 | `7a57d3ab330cc659058ed886c20944ef5ad0858452776acc3ab268c30a9dc0d3` |
| `facman_hermetic_play_candidate_smoke.exe` | 2,703,360 | `7a755bf0a848371814d6b8354e65409b2896527ee01d752f9f5862e7fda060bb` |
| `CMakeCache.txt` | 21,613 | `96c236301c5d4a007d7b8d1a5392611dfec6517ab1acf571898cf98cf836546f` |

Instance identities:

```text
spec digest
  4cae0b49f6b3f85cf9defdfe7e0c57ff9d0ed855e9cc81a54e1cef05400bea79

binding digest
  3ed582105d3840d6e13c8603d943d9948b67bc1bd239c1b9762684f94b29abeb

readiness digest
  e3b6bf66b25a999c5257dec857262066431864793de56e80d13033106e3dc2d9

launch-preflight projection digest
  7608f1775ece2b4afe55dd19e9e7497b062cb76e7326d77b678acff3b1b1fd7f
```

The coordinator's `stage` command then verified and copied only the qualified
bytes:

```text
artifact binding SHA-256
  d4bcde77f8dd97c116fc1ee8230c411ab4a3731a5b80b678d892ecb9be548891

operator config SHA-256
  e24b78e20fdd5cd1d80f68a4a2972e1a155093ed4dca9f67092081ab5c00c7bc

first durable operation id
  0dd3b05f-ba25-4c6a-9cdc-e69afd1f5b5e

second durable operation id
  55e8510f-c633-4731-86c1-fb4de32ceaa0
```

The coordinator `prepare` command was not invoked. No permit was issued, no
Factorio process was started, no observer or baseline evidence was captured,
no human observation or verdict was recorded, and no route or authority was
promoted.
