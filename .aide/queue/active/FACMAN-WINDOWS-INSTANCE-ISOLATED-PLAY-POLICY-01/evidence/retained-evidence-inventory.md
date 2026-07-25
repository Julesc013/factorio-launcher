# Retained Verdict 03 evidence inventory

This policy input is derived from the retained, unchanged Verdict 03 attempt
and reviewed post-run diagnosis. It is not a replacement packet and none of it
is reused for permit issuance, execution, or a future verdict.

| Identity | Value |
| --- | --- |
| Verdict | `Inconclusive` |
| Operation | `gate4c-verdict03-launch1-20260725a` |
| Source revision | `885b9822809c4b3e91e784bdd7e3b8b261533901` |
| Repair implementation | `8382cb5768bd5d2690a6b34a2b6aa2e646b3d8b0` |
| Repair `dev` integration | `ab24b9c417726c9be2daa23684756d24ac0977ae` |
| Hermetic policy digest | `6fde31f26d57e23d67c01dd598cb869a4914d11711868b46d4f817709455e7a2` |
| ETL SHA-256 | `ffd0e7648bc43e08d95c87abc5f1ff016ac55c1168fc07047162aae8e16f56e6` |
| CSV SHA-256 | `37e0684e1aef8a39aece855d90cefa09344a08e55a09f662216e27ec16f64085` |

## Policy-relevant inventory

| Family | Count | Observed scope | Frozen treatment |
| --- | ---: | --- | --- |
| Instance-closure writes | 195 | inside Instance, outside old subdirectory list | `instance_owned` only after exact root binding |
| Installation `umdlogs` creates | 2 | selected installation | `protected_software` / Fail |
| Drive-root `umdlogs` creates | 2 | `D:\NVIDIA Corporation\umdlogs` | `unexpected_external` / Fail |
| Factorio Registry mutations | 327 | includes DirectInput state | unexpected; suppress and freshly classify |
| Windows BAM mutation | 1 | value naming exact Factorio executable | only proposed disclosed family |
| Unresolved file targets | 6 | unsafe/missing file-object name lifetime | `unresolved` / Inconclusive |
| Remaining resolved effects | 78 | remainder of reported source buckets | not an allowlist; freshly classify |
| Packet ownership collision | 1 | observer precreated runtime closure | `observation_gap` / Inconclusive |

The ETW rows reconcile to the reported 611 effects:

```text
195 + 2 + 2 + 327 + 1 + 6 + 78 = 611
```

The packet collision is operation evidence, not an ETW effect.

## Decisions

- The exact Instance directory object and safe descendants form the writable
  player-state boundary.
- Installation and drive-root NVIDIA state remain Fail.
- DirectInput is not accepted; environment v2 must prevent it.
- Only exact Windows BAM state is frozen as a candidate disclosure.
- External effects are observations, never permit resources.
- One unresolved target or evidence gap remains Inconclusive.
- The canonical Gate 4A hermetic policy remains unchanged.

The machine-readable inventory is digest-bound inside
`windows_instance_isolated_play_2_0_77_windows_x64.v1.toml`.
