# Instance product model and operation authority

FacMan's primary product and UX aggregate is a **game instance**: one
reconstructable Factorio environment that selects an installation/version,
isolated player-data root, profile, preset provenance, modpack or exact modset
lock, account reference, settings, resources, and launch policy.

Selecting an instance and pressing **Play** starts Factorio in that environment
and opens Factorio's own main menu by default. A save or world is optional
content available inside the instance; it is not the mandatory identity of the
instance and is not loaded implicitly.

This document describes the product ceiling. Gate 2 implements only the
read-only compatibility projections and commands documented in
[`instance_model_and_readiness.md`](instance_model_and_readiness.md). Other
records, commands, permits, credential providers, and apply paths described
here remain planned unless a current contract and project status explicitly
mark them available.

## Product promise

> FacMan lets players create any number of independent Factorio setups, select
> one, and launch the normal game as though Factorio had always been installed
> and configured exactly that way.

Each instance may independently select its Factorio version and installation,
content capabilities, modpack or modset, mod and game settings, graphics/audio/
interface profiles, player identity and supported account bindings, save
library, scenarios, server configuration, blueprint/script data, execution
environment, isolation guarantee, and backup/snapshot/recovery policy.

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

"Any combination" means every request can be represented, compared, planned,
and explained. Preparation or execution still requires compatibility, legal
availability to the player, provider support, and policy admission. FacMan
must explain version/mod/DLC/platform/account incompatibilities; it must not
bypass entitlement, fabricate compatibility, redistribute Factorio, or
silently fall back to another version, modset, account, or settings profile.

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

### Installation application closure

An `Installation` is the application image: Factorio binaries, exact
version/build, platform/architecture, base game data, observed expansion or
content files, entrypoints, source/provenance, ownership, and lifecycle
authority. It may be Steam-managed, vendor-installed, portable/reference-only,
FacMan-managed, explicitly adopted, headless, or an archived/cached source.

Multiple instances may share one verified installation only while its
application closure is immutable for those launches. Installed content files
are capability evidence, not entitlement proof.

### Isolated instance home

An `Instance` is a complete isolated Factorio home: selected installation,
write-data root, config, mods, mod settings, saves, scenarios, script output,
logs, crash state, player settings, profile bindings, account references,
launch settings, snapshots, and recovery state. Application binaries may be
shared; mutable data is instance-owned and cannot be silently shared between
concurrently runnable instances.

### Typed profiles and versioned presets

Profiles are reusable, independently inspectable, versioned configuration
facets. Initial profile families are:

```text
LaunchProfile
GraphicsProfile
AudioProfile
InterfaceProfile
MultiplayerProfile
ServerProfile
NewGameProfile
BackupProfile
```

An instance may pin an ordered set of profiles when reproducibility matters.
Every applied value retains visible provenance. Profiles cannot grant process,
network, credential, setup, signing, or publication authority.

Presets are versioned bundles of initial defaults and profile references—for
example Vanilla 2.0, Space Age, a named overhaul modpack, low-spec laptop,
headless server, mod development, or speedrunning. They may initialize version
requirements, content, modsets, profiles, data/backup policy, and launch mode.
Applying or explicitly upgrading a preset previews the resulting differences;
later preset edits never mutate existing instances implicitly.

### Desired, locked, and bundled mod content

```text
ModsetSpec
  desired mods
  version constraints
  optional features
  compatibility policy

ModsetLock
  exact versions
  dependency closure
  hashes
  load state
  startup-settings identity

ModpackBundle
  portable metadata
  ModsetLock
  permitted local artifacts or references
```

The lock, not an informal mod list, establishes reproducible content. A lock
does not prove that its artifacts are present, trusted, distributable, or
compatible with the selected Factorio version.

### Account and identity bindings

The instance model keeps independent identity domains:

| Binding | Meaning |
| --- | --- |
| `PlatformAccountBinding` | Steam or another external-platform session |
| `FactorioAccountBinding` | Factorio website or Mod Portal identity |
| `PlayerIdentityProfile` | Player name, colour, and non-secret presentation state |
| `ServerCredentialBinding` | Server-password or RCON credential reference |

Only logical credential references appear in instance configuration. Secret
values remain in an OS-backed credential provider. FacMan cannot silently
switch the active Steam client account, bypass authentication or entitlement,
or emulate an unsupported account/installation combination. Account-route
availability is readiness evidence and unsupported combinations are explained
and refused.

### Save and world library

An instance may contain zero, one, or many saves, plus new-game templates,
scenarios, autosaves, and server saves. They appear normally inside Factorio's
menu. Portable save/world metadata may record required Factorio version,
content capabilities, modset, and last-known-compatible configuration, but a
save remains secondary content rather than the mandatory launch identity.

## Decomposed instance aggregate

```text
InstanceView
  = InstanceSpec
  + InstanceBinding
  + InstanceReadiness
  + effective configuration summary
  + recent run, snapshot, operation, and recovery history
```

These components have different portability, authority, freshness, and
lifecycle rules.

### `InstanceSpec`: portable desired environment

`InstanceSpec` describes the player's desired environment independently of one
machine:

- instance identity and display name;
- Factorio version constraint and required content/DLC capabilities;
- ordered typed-profile references plus explicit setting overrides;
- template provenance and pinned preset identity/version after resolution;
- `ModsetSpec`, modpack, and optional exact `ModsetLock` identity;
- logical platform, Factorio, player-identity, and server-credential requirements;
- data-routing, save-library, isolation, storage, backup, retention, and update
  policies;
- optional scenario, benchmark, server, blueprint, and script-data requirements;
- default `LaunchIntent`, which is `menu`.

It contains logical references and content identities. It never contains
absolute machine paths, drive letters, process IDs, registry keys, credential
values, Steam tokens, entitlement claims, or redistributable Factorio
binaries.

The implemented `factorio.instance.v1` workspace record remains the current
compatibility record. Gate 2 computes an additive `factorio.instance_spec.v1`
projection without persisting it, rewriting existing workspaces, or inferring
authority from legacy fields. A future persisted portable specification must
retain those compatibility laws.

### `InstanceBinding`: machine-local resolution

`InstanceBinding` resolves one `InstanceSpec` on one machine. It binds:

- the selected installation and executable evidence;
- the instance data root and effective configuration identity;
- exact profile, preset-resolution, modpack, and modset-lock identities;
- resolved mod artifacts and content capabilities;
- provider-scoped platform, Factorio, and server credential-reference IDs,
  never credential material;
- host, execution, isolation, graphics, filesystem, and storage providers;
- local mod-cache, save, blueprint, and script-data locations;
- provider revisions and the evidence digest used for resolution.

A binding is replaceable and machine-local. Rebinding an instance on another
machine must not rewrite its portable intent merely because paths, providers,
credential-reference IDs, or storage placement differ.

### `InstanceReadiness`: computed projection

Readiness is recomputed from installation, executable, profile, mod, account,
content, save, environment, launch, operation, and recovery evidence. It is
never persisted as an authority flag.

It answers whether the exact Factorio version is available and healthy,
required content exists, the modset is resolved and version-compatible,
startup settings are valid, account routes are available, saves are
structurally compatible, the execution environment and requested isolation
mode are available, recovery is pending, and the launch plan is still current.

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
configuration summary, and latest run/snapshot/operation/recovery history. It supports **Play**,
**Configure**, **Change Version**, **Choose Profile**, **Choose Modpack**,
**Manage Saves**, **Snapshot**, **Export**, and **Recover**. Generated command
metadata remains the advanced automation surface rather than the primary
player navigation model.

The default card makes the resolved setup legible before launch:

```text
Space Age 2.0 — Main Setup

Factorio        2.0.77
Installation    Managed standalone
Modpack         Space Age QoL — 34 mods locked
Account         Factorio account: Jules
Saves           7
Preset          Desktop / High quality
Isolation       Hermetic
Backup          Current
Last run        Clean exit
Status          Ready

[Play]
```

## Launch-intent law

The launch intent is explicit and bound into readiness, plans, permits, and
post-run evidence:

```text
menu              default player action
continue_last     explicit last-save shortcut
load_save         explicit direct-load action
new_game          explicit scenario/map-generation action
map_editor        explicit editor action
connect_server    explicit multiplayer action
start_server      explicit server workflow
benchmark         advanced explicit action
instrumented_dev  advanced development workflow
```

`facman play <instance>` means `menu` unless the player explicitly
selects another supported intent. The default launch plan must not add a save
path, map, benchmark, or server flag. Exiting Factorio returns to the same
instance record; the save chosen inside Factorio does not redefine the
instance.

The prominent action is **Play — open main menu**. Continue, Load Save, Start
New Game, Map Editor, Join Server, and advanced modes are explicit shortcuts,
not implicit behavior derived from the presence of saves.

The implemented launch builder already provides the compatible foundation: it
generates an instance-specific config whose `read-data` selects the
installation, whose `write-data` selects the instance, and whose update checks
are disabled. Its ordinary shape is:

```text
factorio
  --config <instance>/config/config.ini
  --mod-directory <instance>/mods
```

Without an intent-specific save, scenario, connection, server, benchmark, or
editor argument, Factorio opens its normal menu and sees that instance's mods,
saves, settings, and player data. This architectural fit is not evidence that
real Factorio execution is currently available.

## Effective configuration and provenance

The effective environment is deterministic and explainable:

```text
product defaults
  < platform defaults
  < template initial values
  < pinned preset values
  < ordered typed profiles
  < instance overrides
  < explicit one-run override
```

Workspace and security policies constrain the resolved result rather than
silently winning a value conflict. Templates normally initialize an instance;
later template changes do not alter it. Preset/profile upgrades are pinned and
previewed. Incompatible values or equally ranked conflicting profile values
produce explicit differences or blockers rather than undocumented tie-breaks.

Modset locks, account bindings, machine binding, and launch intent join the
resolved configuration as independently identified inputs. Every effective
value exposes its provenance and overridden sources, for example:

```json
{
  "value": "high",
  "source": "graphics_profile",
  "source_id": "desktop-high-v3",
  "overrides": ["product_default", "preset:space-age"]
}
```

Later edits to presets, profiles, modpacks, account selections, or local
bindings make dependent readiness stale; they do not silently alter a running
or already prepared instance. Configuration may restrict authority but can
never grant process, setup, network, credential, signing, or publication
authority.

## Universal representation, conservative execution

FacMan may model, compare, and diagnose any requested combination, including a
contradictory one such as Factorio 1.1 plus 2.0-only expansion content, a
2.0-only mod, an old save, a standalone install, a Steam session, and a server
profile. Representation never implies compatibility or authority.

The resolver returns one of:

```text
ready
can_be_prepared
can_be_prepared_with_changes
blocked_by_incompatibility
blocked_by_missing_owned_source
blocked_by_entitlement_or_account_requirement
blocked_by_unsupported_platform
recovery_required
```

The result explains viable alternatives such as selecting a compatible
Factorio/mod version, disabling an unavailable content requirement, cloning
before a downgrade, providing a player-owned standalone source, or using the
active Steam account. It never silently substitutes a version, modset,
installation, account, entitlement, or settings profile.

## Instance lifecycle law

The completed product supports creating an empty instance or one from a
template/preset, cloning, renaming, archiving/restoring, moving, switching
version or installation, attaching/updating modsets and profiles, attaching
account references, importing/branching saves, resetting settings, snapshot,
verification, repair of FacMan-owned state, export/import/rebind, Play,
recovery, and deletion of only the FacMan-owned closure.

A version, modset, preset, or material profile change follows:

```text
snapshot
  -> preview differences
  -> prepare
  -> verify
  -> switch
  -> retain rollback
```

When the desired combination is materially different, cloning is the preferred
safe action over repeatedly rewriting the only known-good instance.

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

## Player navigation

The primary navigation is:

```text
Instances
Installations
Modpacks
Profiles and Presets
Saves and Worlds
Accounts
Backups and Snapshots
Recovery Center
Environments
Advanced
```

Instance actions are Play, Configure, Make Ready, Clone, Snapshot, Export,
Repair, and Archive. The Play menu offers Play — open main menu, Continue Last
Save, Load Save, Start New Game, Map Editor, and Join Server. The first remains
the prominent default. Generated command forms remain the advanced automation
surface rather than the player's mental model.

## Safety laws

1. An instance binds one exact installation for each launch.
2. Installation application files remain read-only unless Universal Setup has
   explicit authority for the exact operation.
3. Mutable Factorio data belongs to the instance.
4. The default `LaunchIntent` is `menu`.
5. A save is never loaded without an explicit launch intent.
6. Accounts are references to authenticated identities; instance files never
   store secret values.
7. Steam identity remains owned by the active Steam session.
8. Installed expansion/content files do not prove entitlement.
9. Profile, preset, and template changes are versioned and previewed.
10. A modset is reproducible only when locked to exact versions and hashes.
11. Writable saves are not silently shared across concurrently runnable
    instances.
12. Readiness never creates authority.
13. Every process launch binds an exact instance, installation, plan, isolation
    mode, and permit.
14. Every material change declares verification and honest rollback or recovery
    disposition.
15. Foreign installations remain read-only unless explicitly and safely
    adopted through a later authorised lifecycle.

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
6. **`FACMAN-WORLD-BUNDLE-AND-SAVE-COMPATIBILITY-01`:** add portable save/world
   metadata, required version/modset/content analysis, save import/export, and
   creation or preparation of an instance from a world bundle. World remains a
   secondary content lane.
7. Continue portable instance reconstruction, managed installation lifecycle,
   content preparation, and host support as parallel value lanes. Signed
   self-update blocks public beta, not the first controlled playable alpha.

The product ceiling is an instance-centric Factorio environment manager in
which each instance behaves like an independent Factorio setup. Selecting one
opens the normal game with its exact version, modpack, settings, identity
bindings, saves, profiles, presets, resources, and safety policies already in
effect.

Steam-aware Play remains an independent gate. Dynamic plugins, a daemon,
marketplace, cloud synchronization, remote administration, and advisory AI
remain deferred until observed player demand earns them.
