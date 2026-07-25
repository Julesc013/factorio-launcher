# Windows instance-isolated Play policy closeout

## Disposition

`FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-POLICY-01` is accepted on reviewed
`dev` as a policy-only checkpoint. PR #67 merged reviewed head
`c25491e5250f80d9b1f9813ddf37910315bcc96c` at exact `dev` revision
`28495de937f1184dacc745f41dcac675756ef931`.

The accepted policy freezes:

```text
policy  facman.windows-instance-isolated-play.2.0.77.x64.v1
claim   factorio.windows_instance_isolated_process_tree.v1
digest  8d8189a9e8fc9ff7e479f7dda1adf0ea516bed2878046468022b2da8355e2432
```

It defines a normal-host Instance-isolation claim. It does not revise the
canonical Gate 4A hermetic policy, claim sandbox containment, issue a permit,
expose a Play route, or execute Factorio.

## Frozen candidate law

The candidate remains limited to Windows x64, Factorio 2.0.77, standalone
non-Steam, `menu`, and `instance_isolated`.

The writable product boundary is one exact FacMan-owned Instance directory
object and safe descendants. It is bound by logical Instance identity, stable
root identity, volume and filesystem identity, owning Instance record digest,
InstanceBinding digest, and no-follow/reparse state. It is not a string-prefix
rule.

Six additional operation resources are exact operation-owned closures. Twelve
selected installation, sibling installation, other Instance, default Factorio
data, FacMan package, source, Steam, uninstall, and integration resources
remain protected.

## Effect and authority law

Every observed effect has exactly one disposition:

```text
instance_owned
operation_owned
protected_software
expected_external_disclosed
unexpected_external
unresolved
observation_gap
```

The only frozen external disclosure is the exact Windows BAM process-execution
effect for the bound principal and Factorio executable. That machine-owned
consequence is not a permit resource and is not part of the portable Instance.

DirectInput effects are not accepted. NVIDIA effects are not accepted.
Installation-relative NVIDIA writes are `Fail`. Any unresolved target,
incomplete completion, object-lifetime ambiguity, event loss, overflow, or
provider gap is `Inconclusive`.

## Verdict 03 evidence input

The retained trace inventory totals 611 ETW effects:

| Family | Count | Policy disposition |
| --- | ---: | --- |
| Instance writes excluded by the old subdirectory model | 195 | Instance closure input |
| Installation-relative NVIDIA creates | 2 | Protected software / Fail |
| Drive-root NVIDIA creates | 2 | Not accepted |
| Factorio Registry effects | 327 | Not blindly accepted |
| Windows BAM effect | 1 | Exact disclosed external effect |
| Unresolved file targets | 6 | Inconclusive |
| Remaining effects | 78 | Require exact classification |

The packet-staging collision is recorded separately as an evidence-tooling
defect. The inventory is policy input, not a whitelist.

## Exact reviewed-head proof

| Proof | Push run | Pull-request run | Result |
| --- | --- | --- | --- |
| CI | `30144796327` | `30144805820` | Pass |
| Code security | `30144796337` | `30144805795` | Pass |
| Schema check | `30144796328` | `30144805851` | Pass |
| Security policy | `30144796329` | `30144805806` | Pass |

CI covered Linux, macOS, and Windows native builds, coverage, sanitizers,
bounded fuzzing, packaging and reproducibility, AppKit and WinForms/TUI lanes,
the complete Python suite, strict validation, and policy negative controls.
Code security passed for every configured language.

## Exact merged-`dev` proof

| Proof | Run | Result |
| --- | --- | --- |
| CI | `30145199265` | Pass |
| Code security | `30145199294` | Pass |
| Schema check | `30145199268` | Pass |
| Security policy | `30145199267` | Pass |

## Local and clean reconstruction proof

The implementation passed:

- Windows Debug native CTest, 50 of 50;
- the complete Python suite, 466 tests with 315 expected skips;
- 292 schemas, 125 command contracts, 123 registered routes, and 242 refusal
  codes;
- strict, AIDE Lite, project-state, source-format, and commit-policy checks.

A fresh pinned three-repository workspace then reproduced exact merged `dev`:

| Repository | Revision |
| --- | --- |
| FacMan | `28495de937f1184dacc745f41dcac675756ef931` |
| Universal Launcher | `7bd4425f0c35414f738159b45d8bec42edf70235` |
| Universal Setup | `3f8489275077347c2918f3bb03614ec6431362ff` |

All three repositories configured, built, tested, and passed strict checks.
FacMan additionally passed AIDE Lite and its complete Python suite. The serial
matrix completed in 455.2 seconds with clean detached source checkouts.

## Authority boundary

This checkpoint does not promote:

- product permit issuance;
- `instance.play` or real Factorio execution;
- preparation, installation apply, or Universal Setup mutation;
- external OS or driver writes as permit resources;
- credentials, networking, Steam, host mutation, signing, or publication;
- a human Play verdict, playability, Safe beta, or canonical `main`.

## Next transition

The exact policy-only checkpoint must be promoted separately to canonical
`main`, then `main` ancestry must be synchronized back into `dev` without
changing the accepted tree. Only after that sequence may
`FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-CANDIDATE-01` become active.

Candidate implementation remains separate from a fresh human verdict. The
policy cannot be weakened retroactively in response to candidate behavior.
