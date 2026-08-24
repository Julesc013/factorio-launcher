# FacMan 2.1.14 base-game release route 01

Date: 24 August 2026

State: `review_ready_non_authorizing`

## Result

This checkpoint freezes the exact source-owned inputs for the authorized
Factorio 2.1.14 base-game Windows Sandbox release route. It does not execute
Factorio and it does not grant authority. The reviewed records must first
integrate into protected `dev`; only then may the separate, one-use external
D3/D4 route permits bind their exact integrated digests.

The active accepted 2.0.77 route index remains unchanged. Historical Space Age
2.1.14 engineering and preparation records remain immutable and are not
relabeled as base-game release evidence.

## Exact closure

```text
protected base   41dce656d6e75d9991a101c71b3a7683db873bb3
base tree        58e56a63f21af0747aa04e73e06b71333ec2a61e
product source   8362ddc55cbb98b538f4af410819c9503604ef99
product tree     859695fdcaead2e5e11c5454976432df13cacc1a
package SHA-256  95d5836effa1494d0e976dc4937c198085a61fa30350e7e9f66667c8ffb0a70f
ULK              5479939ca5cbc9ee0f901608a92012778b4752ae
USK              d2a2aae7e61c47035c92334b0522143b4fea3880
provider lock    d33943841431afdeffb7961c7453d8999619ef371793a6310ad2c2952b118f00
```

The retained licensed base-game portable archive is custody-bound outside Git
and distributed artifacts:

```text
archive size     1,649,579,438 bytes
archive SHA-256  4f2875cb5c1325a1fcd21b2d37248d508dc36f51ddeef7406ca96788773b872f
archive entries  12,421
executable       bin/x64/factorio.exe
version/build    2.1.14 / 87180
executable size  49,045,456 bytes
executable hash  0ee725652cfa340008d793bece687aea112475599da01521de05413bdf792695
signature        valid; Wube Software Ltd
content          base game; no optional Space Age dependency
```

The archive path is deliberately absent from source truth. The archive remains
read-only, proprietary, outside Git, packages, logs, and uploaded CI artifacts.

## Sandbox and observer

Two qualification launches proved fresh Windows Sandbox guests, disabled
networking, no prior guest marker, no ordinary FacMan workspace or live
Factorio installation visibility, no production credentials, declared
read-only input mapping only, declared writable evidence output only, and zero
Sandbox processes after teardown. The aggregate clean-host receipt SHA-256 is:

```text
8e7fb8ac781c7cad00a9504ae488069b08c39fbb48b06a88b04ba0110c17e08a
```

The release-route observer is source-bound before protected integration:

```text
harness source    55b4897cf5f5f20de64dac5d67f639073ebedf0ccaf339fca581b57cfcd9fcb8
build definition  89226b75154bd4660ed752893cbdbc6e36778254a3c91375beac7092e2be1c81
guest runner      61a4b18a690c732c14cb46161af6cd159ddd39b7c6f64203e7f0b3e50d38bc4d
bundle builder    916fd8ab69f6a44725f91610cc9e338fb18e4f9340be964169bed98a4f163f42
```

The exact harness binary identity is assigned externally only after this
reviewed source is integrated and built. This prevents the historical
Space-Age-bound engineering harness from being reused for the base-game
route and avoids a binary/route-record digest cycle.

The named route observer is `Jules`. Automated process or exit status may
never substitute for the observer's direct `Pass`, `Fail`, or `Inconclusive`.

## Frozen records

The source-owned records are:

- `contracts/policy/factorio/windows_sandbox_play_2_1_14_base_windows_x64.v1.toml`
- `release/index/successor_play_route.v3.toml`
- `release/index/factorio_2_1_14_release_route.v1.toml`

They bind exactly two launches, fresh operation/attempt/permit identities,
menu observation, clean exits, ULK-authoritative Last Run, relaunch, protected
input immutability, cleanup/reset proof, and eleven refusal controls. Their
source authority surfaces are closed and all false, including execution, D3,
D4, route capability, Setup mutation outside Sandbox, tagging, signing,
publication, and support.

Canonical digests:

```text
policy          0c9a17ab830c65e37f62eaae189fd6152210e6ec38c5c484753cd7acdca56603
source closure  4badcfcf3d9e57d09e4bb08fe186164b2095c4eafe7aab99ca9adb7536589013
route v3        973c1e7f8ac2df5e708c17e5a1de678ad3350988ff192a3d77047345fe2ea858
route record    c19781562d137f22a55bcf6ff93d653b639e68b3600a409c13036b2f2e8f32ff
```

## Execution boundary

After reviewed protected integration, the already granted external
authorization may materialize exactly two one-use route permits. It may create
and remove only task-owned Sandbox state. It may not touch host installations
or user state, update providers, upload proprietary bytes, tag, sign, publish,
activate support, or record beta/accessibility acceptance.

Before dispatch the exact execution request must pass every negative control.
A mismatch or ambiguous custody state stops only this route lane. A route Pass
requires both human-observed menus, exact distinct sessions, correct terminal
records and Last Run, complete immutability, cleanup/reset proof, and the named
human verdict.

## Validation

`tools/factorio_2_1_14_release_route_check.py` recomputes the canonical
digests, validates the three closed schemas, preserves the historical packet,
route v2, provider lock, and active route index, and validates pre-dispatch
request pairs. Focused tests mutate every required refusal boundary and prove
fresh identities for both launches.

No Factorio process, host installation, tag, signing, publication, or support
effect occurs in this checkpoint.
