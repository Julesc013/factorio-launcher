# Windows instance-isolated Play policy

Status: frozen criteria with a technically qualified candidate; the
operator-only verdict harness is implemented and requires a fresh remote-only
post-harness qualification before any human revalidation. There is no accepted
verdict, product route, or authority.

```text
policy_id       facman.windows-instance-isolated-play.2.0.77.x64.v1
policy_revision 1
claim_id        factorio.windows_instance_isolated_process_tree.v1
policy_digest   8d8189a9e8fc9ff7e479f7dda1adf0ea516bed2878046468022b2da8355e2432
```

The machine-readable policy is
[`windows_instance_isolated_play_2_0_77_windows_x64.v1.toml`](../../contracts/policy/factorio/windows_instance_isolated_play_2_0_77_windows_x64.v1.toml).
Its digest is SHA-256 over the decoded policy after removing only
`policy_digest` and encoding the result with `facman.sorted-json.v1`.

## Claim

> FacMan confines Factorio mutable product state to the exact bound Instance
> closure. Protected software remains immutable. Every external OS or driver
> effect must be resolved, classified, and exactly disclosed or rejected.

The user label is **Instance-isolated — Windows**. This is a normal-host
process-tree claim, not whole-host immutability, enforced containment, or
hermetic execution. External Windows state is not FacMan-owned, is not part of
a portable Instance, and is not authorized by the Play permit.

The canonical Gate 4A policy remains byte-identical and separately defines
`hermetic`. A future hermetic route needs a sandbox, disposable VM, or another
boundary that prevents—not merely observes—external effects.

## Candidate

| Dimension | Frozen value |
| --- | --- |
| Platform | Windows x64 |
| Factorio | exactly 2.0.77 |
| Distribution | authenticated Wube standalone, non-Steam |
| Storage | fixed local NTFS |
| Instance | FacMan-owned |
| Content and mods | base game; explicit empty lock |
| Account, credentials, network | none |
| Intent | `menu` |
| Isolation | `instance_isolated` |
| Process environment | `factorio.menu-minimal.v2` |
| Observer | `gate4c-etw-file-registry-process.v6` |

No alternate intent, Steam state, acquisition, preparation, Setup, signing,
publication, or general process authority is included.

The separate operator mechanics and qualification boundary are documented in
[Instance-isolated verdict harness](instance-isolated-verdict-harness.md).

## Exact writable boundary

The policy binds one Instance logical ID to its stable root object, volume,
filesystem, no-follow state, owning Instance record digest, and
`InstanceBinding` digest. It permits descendant creation and mutation beneath
that exact directory object, including Factorio's fixed top-level write-data
files such as:

```text
factorio-current.log
factorio-previous.log
crop-cache.dat
player-data.json
player-data.tmp.json
achievements.dat
achievements.tmp.dat
mod-list.json
.lock
temp/
config/
mods/
saves/
scenarios/
script-output/
```

This is not a string-prefix rule. Reparse points, mount substitution, ancestor
replacement, sibling escape, and traversal outside the bound root refuse or
make the evidence Inconclusive.

Six operation-bound resources remain separate:

```text
operation.record
operation.temporary
operation.observer_artifacts
operation.candidate_artifacts
operation.audit_record
operation.process_logs
```

`observer-artifacts` is observer-owned and `candidate-artifacts` is
runtime-owned. That disjoint ownership preserves the Verdict 03 collision
repair.

## Protected software

The selected and sibling installations, every other Instance, default/global
Factorio data, Factorio AppData/LocalAppData/ProgramData, Steam
installation/userdata, the FacMan package, source artifacts, and Factorio
uninstall registration remain immutable. Stable pre/post identity, manifest,
Registry-value, and absence comparison are required. A resolved mutation is
Fail.

`NVIDIA Corporation/umdlogs` beneath the installation remains Fail. The
drive-root equivalent is not disclosed as expected; recurrence is
`unexpected_external` and Fail.

## Closed effect taxonomy

| Classification | Meaning | Verdict |
| --- | --- | --- |
| `instance_owned` | Inside the exact stable Instance closure | allowed |
| `operation_owned` | Inside one exact operation-owned resource | allowed |
| `protected_software` | Mutation of immutable software/product state | Fail |
| `expected_external_disclosed` | Exact frozen machine-owned effect | allowed and disclosed |
| `unexpected_external` | Resolved external mutation outside the disclosure | Fail |
| `unresolved` | Target, completion, process, lifetime, or ownership ambiguous | Inconclusive |
| `observation_gap` | Lost, incomplete, or corrupt evidence | Inconclusive |

External effects never receive permit authority. The permit remains limited
to `workspace_read`, exact Instance/operation `workspace_write`, and
`process_execute`.

## Frozen external disclosure

The policy contains exactly one external family:

```text
windows.bam.factorio_process_execution.v1
```

It covers successful `RegSetValue` observation only when the exact Windows BAM
`UserSettings` domain, principal SID, selected Factorio executable native path
and stable identity, Windows session, process lifetime, and provider revision
all match. Windows owns this state. FacMan does not restore, redirect, export,
or include it in the Instance.

Verdict 03 DirectInput effects are deliberately not accepted.
`SDL_DIRECTINPUT_ENABLED=0` must prevent them. A future successful DirectInput
mutation is unexpected and Fail.

## Observation and verdict law

The process-tree ETW observer and stable protected-state comparison are both
mandatory. They start before process creation and continue through
quiescence. Every successful mutation needs exact target, completion, process,
file-object/KCB lifetime, and ownership evidence.

Lost events, overflow, missing completion, unresolved targets, reuse
ambiguity, incomplete comparisons, packet collision, attribution gaps, or
provider failure force Inconclusive.

Pass requires exact identities, one fresh permit per launch, medium-integrity
FacMan and Factorio, high-integrity observer only, the normal menu, no inferred
save or intent, successful save/exit/relaunch, all controlled writes inside
the exact closure, protected roots unchanged, only exact disclosed external
effects, and a complete human-reviewed hash-closed packet.

Protected mutation, unexpected external mutation, elevated Factorio, resource
escape, accepted invalid authority, wrong intent, implicit save loading,
candidate-caused journey failure, or false lifecycle reporting is Fail.

Pass is evidence only. It cannot enable a route.

## Governance

```text
policy implementation PR to dev
→ policy closeout PR
→ no-authority canonical policy promotion to main
→ main ancestry synchronization into dev
→ separate candidate
→ separate human verdict
→ separate exact-route promotion after Pass
```

No WPR or Factorio process may run during policy work. The policy creates no
public command, issuer, runtime capability, Setup, credential, network, Steam,
signing, publication, or Safe-beta authority.
