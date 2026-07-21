# Instance model and readiness: Gate 2 read-only contract

Gate 2 implements the first bounded, instance-centric player projection. It
adds `instances.describe` and `instances.readiness` without changing the
persisted `factorio.instance.v1` compatibility record or the existing
`instances.inspect` lifecycle contract.

The implemented path is:

```text
factorio.instance.v1 + current evidence
  -> InstanceSpec projection
  -> InstanceBinding projection
  -> InstanceReadiness projection
  -> InstanceView projection
```

This path reads existing workspace and installation state. It does not prepare
an instance, issue a permit, access credentials or the network, invoke
Universal Setup, start Factorio, or write any record, log, journal, cache, or
temporary file.

## Commands

```text
facman instances describe <instance-id> [--intent menu] --json
facman instances readiness <instance-id> [--intent menu] --json
```

Omitting `--intent` means `menu`. The full launch-intent vocabulary is
registered so requests can be represented consistently, but Gate 2 accepts
only `menu`. Every other intent receives the typed
`unsupported_launch_intent` refusal. No save, scenario, server, editor, or
benchmark is inferred from instance contents.

Both command contracts have exactly the `workspace_read` effect and declare:

```text
executes_process = false
mutates_workspace = false
dry_run_default = true
```

## Portable `InstanceSpec`

`factorio.instance_spec.v1` is a computed compatibility projection of logical
intent. Its initial fields cover:

- immutable instance identity and display name;
- exact Factorio version intent, or explicit `not_recorded`;
- required base-content capability;
- compatible registered-installation selection policy;
- template provenance;
- ordered legacy-profile reference and revision;
- projected legacy modset-lock reference and digest when one exists;
- explicit override summary;
- conservative isolation, backup, and account defaults; and
- `menu` as the default launch intent.

The spec does not contain machine paths, drive letters, registry data, process
identity, credential values, tokens, or installation binaries. Machine-local
unlocked mods affect readiness but not this portable digest. The projection
does not persist a new record and reports that the source compatibility record
was not rewritten.

## Local `InstanceBinding`

`factorio.instance_binding.v1` resolves that intent against the current
machine. It binds:

- one registered installation and its Gate 1 evidence digest;
- the instance root and observed identity;
- exact read-data, write-data, mod-root, and effective-config paths;
- effective-config digest;
- profile, template, and modset-lock identities;
- the currently known native execution environment;
- provider revisions; and
- explicit evidence dependencies and per-use revalidation requirements.

Missing evidence is represented as `missing` or `not_observed`; it never
creates authority. `freshness_state = current` means the projection describes
the evidence observed by that invocation. Consumers must still revalidate all
dependencies marked `revalidate_before_use` before a later operation.

## Computed `InstanceReadiness`

`factorio.instance_readiness.v1` evaluates the exact `menu` intent across these
initial dimensions:

| Dimension | Gate 2 evaluation |
| --- | --- |
| Installation | Registered Gate 1 evidence, application root, and executable health |
| Version | Exact legacy-record requirement against selected installation |
| Content | Required base application data |
| Instance root | Existing root with no link/reparse traversal |
| Configuration | Read-data routes to the installation and write-data/mods route to the instance |
| Profile | Effective profile and override resolution |
| Mod content | No external mods, explicitly degraded unlocked mods, or verified exact lock/artifacts/hashes/metadata/compatibility |
| Saves | Informational; zero saves is valid for menu launch |
| Accounts | Not applicable to standalone menu readiness in this slice |
| Recovery | Any incomplete or invalid transaction takes precedence |
| Environment | Explicitly degraded until per-operation filesystem/process capabilities are proven |
| Isolation | Explicitly not observed in the legacy record |
| Play authority | Blocked because OperationPermit and real Play are later gates |

Configuration readiness is reported separately as `ready`, `degraded`, or
`blocked`. Preparation is `already_prepared`, `changes_required`, or
`unavailable`. The overall state remains `blocked` for an otherwise usable
instance because real process authority is unavailable; it becomes
`recovery_required` when transaction recovery takes precedence.

Every blocker has a stable code, dimension, reason, detail, recoverability,
and safe next action. Findings expose non-blocking uncertainty. Resource and
dependency arrays state exactly which evidence supported the result.

## Player `InstanceView`

`factorio.instance_view.v1` composes the spec, binding, and readiness with a
compact player summary: name, version, installation, profile/template,
modset, save/snapshot counts, isolation, backup, last-run observation,
primary blocker, and recommended action.

The large future action remains **Play — open the normal Factorio menu**. Gate
2 intentionally reports that action as unavailable. `instances.describe` is a
read-only explanation surface, not an execution shortcut.

## Deterministic identities

Each component uses canonical sorted JSON and a SHA-256 digest:

```text
spec_digest       = digest(InstanceSpec without spec_digest)
binding_digest    = digest(InstanceBinding without binding_digest)
readiness_digest  = digest(InstanceReadiness core without presentation guarantees)
view_digest       = digest(InstanceView without view_digest)
```

The readiness digest binds the spec and binding digests. The binding binds the
Gate 1 installation evidence digest, configuration, roots, profiles, modset,
recovery observation, and provider revisions. Equivalent evidence and intent
produce equivalent output. Changing relevant evidence changes the appropriate
component digest. Volatile timestamps are absent.

## Compatibility and safety laws

1. `factorio.instance.v1` remains the persisted compatibility source and is
   byte-identical after projection.
2. `instances.inspect` remains the R3.7 lifecycle inspection contract.
3. A spec is portable logical intent; a binding is machine-local evidence.
4. Missing or unknown evidence never becomes authority.
5. Menu is the only implemented launch intent and never infers a save.
6. Zero saves and no account are valid for standalone menu configuration.
7. Unlocked local mods are visible and degraded, not silently treated as a
   reproducible modset.
8. A lock is satisfied only after exact artifact, hash, metadata, and
   compatibility verification.
9. Recovery state takes precedence over preparation and Play.
10. Readiness never creates directories or persistent state, even when the
    requested workspace does not exist.
11. Every authority and effect guarantee remains false in the output.
12. OperationPermit, preparation apply, and real Factorio execution remain
    unavailable and require separate reviewed gates.

## Proof surface

Native and CLI tests cover deterministic repeated projection, digest
reconstruction, schema validation, byte-for-byte workspace snapshots,
non-existent-workspace no-create behavior, unsupported intents, missing
installations, invalid configuration, unlocked mods, missing and incompatible
modset locks, zero-save/account semantics, and recovery precedence. The
`instance_model_check` strict validator enforces the command effects, schema
separation, compatibility contract, no-authority constants, model safety
anchors, and absence of mutation/process primitives.

These tests establish the read-only software contract. They do not promote
Play, installation mutation, credential, signing, release, or publication
authority and do not replace the later human-reviewed real-product Play gate.
