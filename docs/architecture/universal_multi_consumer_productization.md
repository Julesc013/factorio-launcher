# Universal platform multi-consumer productization

Status: ratified architecture and active bounded contract-design wave

Last reviewed: 2026-08-04

Consumers: FacMan, Dominium, Compact Cassette Catalogue, and synthetic fixtures

## Decision

Universal Setup (USK) and Universal Launcher (ULK) are independent,
capability-based provider products. They are not folders to transplant between
product repositories, one combined repository, or a mandatory paired runtime.

The target split is:

```text
USK                          ULK
installed-software effects  runnable-product infrastructure
package and recipe tools    commands, clients and transports
transactions and recovery   references, plans and sessions
installed state and audit   process identity and containment
             \              /
              product repository
              identity, recipes, policy, semantics,
              presentation and exact provider pins
```

Productization means that each provider eventually ships its own contracts,
stable C ABI, SDK package, redistributable runtime, tools, neutral reference
applications, fixtures, and provenance. Product-branded applications remain in
their product repositories.

This decision extends the three-repository convergence strategy to multiple
genuinely different consumers. The authoritative consumer matrix is
`release/index/universal_consumer_requirements.v1.toml`.

## Reviewed identities

The bounded programme retains these exact FacMan provider pins:

| Provider | FacMan-consumed revision |
| --- | --- |
| Universal Launcher | `7fc25340623131ba86c08dca4fb8a43b18a4520d` |
| Universal Setup | `3048128963dc718a7c38c1cfcdda9e813a23b0db` |

The consumer characterizations bind immutable source snapshots:

| Consumer | Source revision | Evidence |
| --- | --- | --- |
| FacMan | `7ebbfa37b23ee173cbb15f399935d0e035e79375` | merged transport baseline |
| Dominium | `623ab08ae8c867719d5abc2e60c16a6fbb37b313` | function-level boundary audit |
| C3 | `ea984df9b7ab99cf47fcdbd8edcb571e6ce80d52` | two-lane consumer profile |

Later checkout movement does not rewrite these audit inputs. Any provider repin
requires a separate, reviewed consumer-adoption WorkUnit.

## Permanent ownership

USK owns installable package and source inspection, package manifests and
setup recipes, target classification and ownership, setup plans, install,
verify, repair, move, reinstall, update or downgrade, uninstall, rollback,
recovery, installed-state records, transaction journals, setup evidence, and
bounded extraction and staging.

USK does not own product content or data. That exclusion includes Factorio
mods, saves, worlds, backups and diagnostics; Dominium product rules and
content; C3 catalogue XML, user cassette data and backups; product GUIs;
launcher sessions; and product accounts.

ULK owns generic command, client and transport contracts; owned results;
durable operation and attempt identity; terminal outcome semantics; product,
install, instance, profile and artifact-set references; reference persistence;
launch plans and staleness; launcher journals; generic preference storage;
process specification and environment; execution sessions; process identity
and containment; bounded process I/O; cancellation and timeout law; and
frontend-neutral clients and bindings.

ULK does not own installed-software mutation, product semantics, product
readiness, branded presentation, or credential and network policy by default.

Every product repository owns its product identity and compatibility,
component and package recipes, provider interpretation, data and content
formats, product-specific readiness, presentation, branding, native
applications, release policy, support claims, and exact provider pins.

## Capability-based consumers

A consumer selects capabilities; provider breadth never grants unused
authority.

| Capability | FacMan | Dominium | C3 legacy x86 | C3 modern x64 |
| --- | --- | --- | --- | --- |
| Package authoring | yes | yes | yes | yes |
| Package verification | yes | yes | build-time | yes |
| Install, repair, uninstall | later | yes | no; manual portable | candidate |
| Update and rollback | later | yes | browser/manual | candidate |
| Product references | yes | yes | no | optional |
| Profiles and instances | yes | yes | no | no by default |
| Process supervision | yes | yes | application-owned | optional |
| Launch sessions | yes | yes | no | optional |
| Product GUI | FacMan-owned | Dominium-owned | C3-owned | C3-owned |
| Legacy OS constraint | no C1 x86 | product-specific | XP/.NET 4.0 unproven | Win7+/.NET 4.8 |

C3 legacy x86 is a USK package-authoring consumer only unless a native XP
feasibility proof closes its compiler, API, CRT, redistribution, signing,
packaging, and clean-VM runtime. C3 modern x64 may use package authoring and an
external USK maintenance host. ULK remains absent from C3 until a demonstrated
open-document, activation, or session journey requires it.

## Characterization result

Exactly three lanes were admitted for the first wave:

1. `FACMAN-C1-BACKEND-IDENTITY-01` binds WinForms production dispatch to the
   exact package-relative backend and its source, build, contract, transport,
   provider, closure, and route-capability identity.
2. `DOMINIUM-UNIVERSAL-BOUNDARY-AUDIT-01` records a symbol-level disposition,
   characterization test, migration dependency, and rollback for the local
   setup, content-store, launcher, native and compatibility surfaces.
3. `C3-UNIVERSAL-CONSUMER-PROFILE-01` records the distinct legacy and modern
   packaging choices and keeps application, configuration, catalogue and user
   data in C3.

The audit evidence is:

- `release/index/dominium_universal_boundary_audit.v1.toml` and
  `docs/product/dominium_universal_boundary_audit_01.md`;
- `release/index/c3_universal_consumer_profile.v1.toml` and
  `docs/product/c3_universal_consumer_profile_01.md`.

The matrices ratify no immediate deletion. Dominium contains generic-looking
USK and ULK candidates, but several transaction, logging, rollback,
content-store publication, garbage-collection, launcher-execution and native
surfaces first require characterization or repair. Historical C3 installer and
uninstaller experiments are retirement evidence, not reusable provider code.

## Extraction and deletion law

No implementation moves merely because a file or directory looks generic.
Each concern follows this reversible train:

```text
characterize current behavior
-> define product-neutral provider contract
-> land additive provider implementation and TCK proof
-> merge provider main
-> add product compatibility adapter
-> update one exact provider pin in a separate WorkUnit
-> prove old/new equivalence and source closure
-> switch the consumer
-> retain a compatibility window
-> delete or thin the product-local incubator
```

Deletion additionally requires a reference and ABI census, dual-run evidence,
and a proven rollback. Product payloads and semantics remain with the product
even when their generic envelope or lifecycle moves.

## Active provider contract-design wave

The two consumer audits are complete, so the exact next wave is now
`active_contract_design`:

```text
ULK-PRODUCT-COMPOSITION-CONTRACT-01
USK-PRODUCT-PACKAGE-AND-RECIPE-CONTRACT-01
SYNTHETIC-PRODUCT-TCK-01
```

The authoritative design projection is
`release/index/universal_provider_contract_wave.v1.toml`. This is contract
design in the FacMan programme record only. It creates no provider-repository
branch, task, or worktree; implements or moves no provider or product code;
and executes no product or fixture.

The contract designs bind these immutable provider baselines without changing
FacMan's qualified consumer pins:

| Target repository | Contract-design baseline | FacMan consumer pin |
| --- | --- | --- |
| Universal Launcher | `417c8b705d7b1a320091aa20954e382dcb62be4c` | `7fc25340623131ba86c08dca4fb8a43b18a4520d` |
| Universal Setup | `1a3fe548d278da038b96579363c1ddb7d92edeee` | `3048128963dc718a7c38c1cfcdda9e813a23b0db` |

The ULK WorkUnit must deliver `ulk.product_descriptor.v2`,
`ulk.entrypoint.v1`, `ulk.launch_capability.v1`,
`ulk.product_composition.v1`, and `ulk.contract_set_identity.v1`. Its
capability vocabulary is `single_process`, `open_document`, `multi_instance`,
`profile_selection`, `artifact_sets`, `session_supervision`,
`background_service`, and `server`.

The USK WorkUnit must deliver `usk.product_package.v1`, `usk.setup_recipe.v1`,
`usk.component_manifest.v1`, and `usk.source_manifest.v1`, with explicit
compatibility rules for `usk.installed_state.v1`.

Its exact product-neutral contract-field set is:

```text
product_id
product_version
publisher identity/reference
component IDs
platform/architecture
entry paths and hashes
source identity
target policy
mutable versus immutable paths
data/config roots
migration requirements
install/repair/update/uninstall support
rollback/recovery disposition
license/SBOM/provenance references
```

The synthetic product must prove package authoring, inspection, plan preview,
installation fixture behavior, reference composition, launch preview,
structured refusal, and recovery fixture behavior. Its forbidden product
vocabulary is `factorio`, `dominium`, `domino`, `c3`, `cassette`, `catalogue`,
`game`, and `simulation`. In particular, ULK capability kinds remain limited to
the product-neutral vocabulary above rather than `game`, `catalogue`, or
`simulation` categories.

## Authority boundary

This programme and its green tests grant no provider repin, real Setup
mutation, product or Factorio execution, credential or network use, protected
merge, signing, publication, human verdict, successor Play route, permit, or
release authority. Revalidation-04 remains superseded immutable history. A
future authority-bearing action needs its own reviewed WorkUnit and evidence.
