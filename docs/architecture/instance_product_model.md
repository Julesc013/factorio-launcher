# Instance product model and operation authority

FacMan's primary product and UX aggregate is a **game instance**: one
reconstructable Factorio environment that selects an installation/version,
isolated player-data root, profile, preset provenance, modpack or exact modset
lock, account reference, settings, resources, and launch policy.

Selecting an instance and pressing **Play** starts Factorio in that environment
and opens Factorio's own main menu by default. A save or world is optional
content available inside the instance; it is not the mandatory identity of the
instance and is not loaded implicitly.

This document is target architecture. Records, commands, permits, credential
providers, and apply paths described here are planned unless a current contract
and project status explicitly mark them available.

## Product promise

> Choose an instance, press Play, and arrive at Factorio's menu with the chosen
> version, mods, profile, account context, settings, saves, and resources
> already in effect.

The intended player flow is:

```text
find or add Factorio installations
  -> create, clone, import, or select an instance
  -> choose compatible version, profile, preset, modpack, account, and resources
  -> compute readiness from current evidence
  -> explain blockers and the least-invasive safe options
  -> prepare only the selected instance boundary
  -> preflight the exact effective launch configuration
  -> Play to the Factorio main menu
  -> select or create a save in Factorio
  -> exit, observe, and relaunch the same environment
```

"Any combination" means any combination that is compatible, legally
available to the player, and supported by the selected providers. FacMan must
explain version/mod/DLC/platform/account incompatibilities; it must not bypass
entitlement, fabricate compatibility, redistribute Factorio, or silently fall
back to another version, modset, account, or settings profile.

## Resource model

The aggregate keeps distinct resource types rather than flattening them into
one manifest:

| Resource | Meaning | Authority boundary |
| --- | --- | --- |
| Installation | One observed Factorio application closure and version | Inspection is read-only; lifecycle mutation belongs to Universal Setup |
| Instance | The runnable, isolated environment selected by the player | Primary UX aggregate and player-data boundary |
| Profile | Reusable Factorio configuration and launch preferences | Declarative input; cannot grant authority |
| Preset | Reusable partial composition defaults for creating or changing an instance | Resolves into explicit instance intent; never a hidden runtime dependency |
| Modpack | Shareable mod requirements and policy | Portable intent, not proof that artifacts are present |
| Modset lock | Exact resolved mod identities, versions, and hashes | Deterministic content identity |
| Account reference | Provider-scoped logical identity with no credential value | Resolution belongs to a credential/platform provider |
| Save/world | Optional content within an instance | May be listed, backed up, moved, or directly loaded explicitly |
| Resource policy | DLC/content capabilities, locale, storage, graphics, environment, and isolation requirements | Readiness input; must be observed or marked unknown |

Profiles and presets are intentionally different. A profile is reusable
effective Factorio behavior. A preset is a convenience template that may
reference a version constraint, profile, modpack, data policy, or launch mode.
Applying a preset produces explicit instance intent with provenance; later
changes to the preset do not silently mutate an existing instance.

## Decomposed instance aggregate

```text
InstanceView
  = InstanceSpec
  + InstanceBinding
  + InstanceReadiness
  + effective configuration summary
  + recent operation and recovery history
```

These components have different portability, authority, freshness, and
lifecycle rules.

### `InstanceSpec`: portable desired environment

`InstanceSpec` describes the player's desired environment independently of one
machine:

- instance identity and display name;
- Factorio version constraint and required content/DLC capabilities;
- profile reference plus explicit setting overrides;
- preset provenance after its values have been resolved;
- modpack reference and optional exact modset-lock identity;
- logical account requirement or account-reference selector;
- isolation, storage, backup, retention, and update policies;
- optional save library, scenario, benchmark, or server requirements;
- default launch intent, which is `open_game_menu`.

It contains logical references and content identities. It never contains
absolute machine paths, drive letters, process IDs, registry keys, credential
values, Steam tokens, entitlement claims, or redistributable Factorio
binaries.

The implemented `factorio.instance.v1` workspace record remains the current
compatibility record. A future `InstanceSpec` is additive and must not silently
rewrite existing workspaces or infer authority from legacy fields.

### `InstanceBinding`: machine-local resolution

`InstanceBinding` resolves one `InstanceSpec` on one machine. It binds:

- the selected installation and executable evidence;
- the instance data root and effective configuration identity;
- exact profile, preset-resolution, modpack, and modset-lock identities;
- resolved mod artifacts and content capabilities;
- provider-scoped account reference, never credential material;
- host, execution, isolation, graphics, filesystem, and storage providers;
- local save/content-cache locations;
- provider revisions and the evidence digest used for resolution.

A binding is replaceable and machine-local. Rebinding an instance on another
machine must not rewrite its portable intent merely because paths, providers,
credential-reference IDs, or storage placement differ.

### `InstanceReadiness`: computed projection

Readiness is recomputed from installation, executable, profile, mod, account,
content, save, environment, launch, operation, and recovery evidence. It is
never persisted as an authority flag.

The result is one of:

```text
ready
degraded
blocked
recovery_required
```

Every blocker cites its evidence, affected resource and owner, missing
capability, safest useful next action, effects, privilege/restart needs,
rollback class, and verification route. Unknown account, entitlement, mod
compatibility, filesystem, or provider state remains explicit. Cached
readiness is disposable and carries dependency identities, freshness, and
invalidation rules.

### `InstanceView`: task-oriented UI projection

`InstanceView` composes the current spec, binding, readiness, effective
configuration summary, and latest operation history. It supports **Play**,
**Configure**, **Change Version**, **Choose Profile**, **Choose Modpack**,
**Manage Saves**, **Snapshot**, **Export**, and **Recover**. Generated command
metadata remains the advanced automation surface rather than the primary
player navigation model.

## Launch-intent law

The launch intent is explicit and bound into readiness, plans, permits, and
post-run evidence:

```text
open_game_menu    default player action
load_save         optional explicit direct-load action
new_game          optional explicit scenario/map-generation action
benchmark         advanced explicit action
headless_server   separate server workflow
```

`facman play <instance>` means `open_game_menu` unless the player explicitly
selects another supported intent. The default launch plan must not add a save
path, map, benchmark, or server flag. Exiting Factorio returns to the same
instance record; the save chosen inside Factorio does not redefine the
instance.

## Effective configuration and provenance

The effective environment is deterministic and explainable:

```text
product defaults
  < platform defaults
  < workspace policy
  < resolved preset values
  < profile
  < instance overrides
  < explicit launch request
```

Every effective value exposes its source. Later edits to presets, profiles,
modpacks, or account selections make dependent readiness stale; they do not
silently alter a running or already prepared instance. Configuration may
restrict authority but can never grant process, setup, network, credential,
signing, or publication authority.

## Federated instance preparation

`InstancePreparationPlan` composes typed subplans; it does not become a
universal mutation kernel.

| Concern | Owning policy or mechanism |
| --- | --- |
| Factorio eligibility, profiles, presets, mods, saves, and instance readiness | FacMan |
| Installation references, instance bindings, launch staleness, and process orchestration | Universal Launcher |
| Installation and host mutation | Universal Setup |
| Exact launch intent and post-run interpretation | FacMan |
| Credential values and platform sessions | Credential/platform provider |
| Review, confirmation, and presentation | FacMan frontend |

Each subplan retains its schema, identity, effects, owner, expiration,
verification, rollback, and refusal semantics. FacMan may rank and present the
combined plan, but it cannot manufacture setup, credential, network, or
execution authority.

## Authority law

Effect declarations, capability requirements, capability observations, policy
decisions, and short-lived `OperationPermit`s remain separate. An
authority-bearing operation binds one exact reviewed plan, resource set,
machine, provider set, evidence digest, policy revision, principal, nonce,
isolation mode, and expiry.

Global admission validates the request and permit, but every owning provider
independently revalidates. Universal Setup revalidates installation/host
targets; the process provider revalidates executable, effective configuration,
instance boundary, and launch intent; credential providers revalidate the
account scope without exposing secrets. Frontends, presets, profiles,
modpacks, imported manifests, and extensions cannot issue or widen permits.

## Portable reconstruction

An instance bundle may include `InstanceSpec`, resolved preset provenance,
profiles, modpack requirements, modset locks, selected saves, permitted mod
artifacts or references, templates, backup metadata, hashes, logical resource
IDs, and an optional redacted audit summary.

It excludes machine bindings, absolute paths, registry state, credential
values, Steam tokens, arbitrary host diagnostics, and publisher-unlicensed
Factorio binaries. Import classifies locally satisfied resources,
reconstructable resources, player-owned source/account requirements, and
policy conflicts before any mutation.

## Candidate stable workflow surface

```text
instance.list
instance.inspect
instance.readiness
instance.prepare.plan
instance.prepare.apply
instance.play
instance.export
instance.import.inspect
instance.import.plan
profile.list
preset.list
modpack.list
operation.inspect
operation.resume
operation.rollback
support.export
```

These are candidate contracts, not current availability claims. Saves/worlds
remain content workflows under the selected instance; direct save loading is
an optional launch intent rather than the product's default entry point.

## Delivery gates

1. Close installation-model-v2 as a reviewed read-only projection with
   deterministic plan-only reconciliation.
2. **`FACMAN-INSTANCE-SPEC-AND-READINESS-01`:** add portable instance intent,
   machine-local binding, computed readiness, effective-configuration
   projection, and read-only list/inspect/readiness commands.
3. **`FACMAN-OPERATION-PERMIT-01`:** add exact operation-bound authority and
   provider-side independent revalidation.
4. **`FACMAN-HERMETIC-STANDALONE-PLAY-01`:** prove one exact standalone
   instance opens to the Factorio menu, can select/create/save content, exits,
   and relaunches without persistent writes outside the authorised boundary.
5. **`FACMAN-INSTANCE-CENTRIC-ALPHA-01`:** expose Instances, readiness,
   Configure, Play, last run, saves/backups, recovery, installations, and the
   advanced explorer to real players.
6. Continue portable reconstruction, managed installation lifecycle, content
   preparation, and host support as parallel value lanes. Signed self-update
   blocks public beta, not the first controlled playable alpha.

Steam-aware Play remains an independent gate. Dynamic plugins, a daemon,
marketplace, cloud synchronization, remote administration, and advisory AI
remain deferred until observed player demand earns them.
