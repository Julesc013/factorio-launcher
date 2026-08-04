# Universal platform multi-consumer productization

Status: ratified architecture; provider contracts and cross-provider TCK fixture-qualified

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

The bounded C3 delta gate separately compares that immutable profile with
`f27c1d0c6798ea68b81ac0b0889ef770ad19d2d9`. Its result is recorded in
`release/index/c3_universal_consumer_profile_delta.v1.toml`: the original
profile remains valid with the exact acquisition/setup ownership amendment and
toolchain-evidence note stated there.

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

## Reconciled provider contract wave

The authoritative projection is
`release/index/universal_provider_contract_wave.v1.toml`.

The provider contracts advanced from `design_ready` through bounded
implementation to `fixture_qualified`. Both reviewed provider changes are now
merged and promoted with synchronized `main` and `dev` branches. Their exact
promotion heads allowed the synthetic TCK to complete as a bounded fixture proof:

| WorkUnit | State |
| --- | --- |
| `ULK-PRODUCT-COMPOSITION-CONTRACT-01` | `fixture_qualified`; task `766fe181709eaee15139303f95a649caf30abbda`, promotion `719a3ec240831547071d69098e1fe8c76f327fb7` |
| `USK-PRODUCT-PACKAGE-AND-RECIPE-CONTRACT-01` | `fixture_qualified`; task `629d3011f784e833b26887a4b8403602c181a055`, promotion `7f8f2baa14e78b0329db8eef8ac872818c4cf30d` |
| `SYNTHETIC-PRODUCT-TCK-01` | `complete`; task `926850007a72269ceddd7f85905e934b6c4dcfc7`, hosted TCK `30877499521` |

The provider-local neutral fixtures and hosted matrices qualify only the new
contracts. This is not FacMan consumer adoption: FacMan's tracked provider pins
remain unchanged until a separate post-promotion adoption WorkUnit.

The immutable architecture inputs remain
`417c8b705d7b1a320091aa20954e382dcb62be4c` for ULK and
`1a3fe548d278da038b96579363c1ddb7d92edeee` for USK. After branch-model
ratification, exact provider task branches must start from the current
provider `dev` closeouts:

| Target repository | Exact task base | FacMan consumer pin |
| --- | --- | --- |
| Universal Launcher | `db58cdffefe470cbd01a79558d177db3dda8aa32` | `7fc25340623131ba86c08dca4fb8a43b18a4520d` |
| Universal Setup | `095a6cf4e5d9635201c29c466dcb71ce359f9374` | `3048128963dc718a7c38c1cfcdda9e813a23b0db` |

The ULK WorkUnit delivers additive product-neutral descriptors for product,
entrypoint, capabilities, composition, and contract-set identity. Its closed
capability vocabulary is `single_process`, `open_document`, `multi_instance`,
`profile_selection`, `artifact_sets`, `session_supervision`,
`background_service`, and `server`. It preserves ABI 1.6/1.7 and does not add
setup recipes, update policy, GUI/navigation descriptions, a process client,
persistence, daemon runtime, or SDK packaging.

The USK WorkUnit delivers additive product-package, component, source, recipe,
and installed-state compatibility contracts. Acquisition remains separate:

```text
consumer schedule/channel/discovery/acquisition
-> verified local package reference
-> USK verification and lifecycle plan/apply/recovery
```

USK is not a GitHub API client, general downloader, release-channel owner, or
notification service. Its first contract PR opens no live mutation, streaming
extraction, DEFLATE, launch, session, presentation, or SDK-packaging authority.

Content-addressing does not determine ownership. USK owns setup-only cache,
staging, installed immutable payload, rollback material, generic
integrity/closure/authenticity evidence, and collection of unreferenced
setup-owned payload. Dominium owns runtime packs, authored content and pack
semantics, compatibility/dependency policy, and retention. ULK/product
composition owns mounted runnable references, active-session reachability, and
launch-plan binding.

The TCK uses no fourth repository. ULK and USK each carry provider-local
neutral fixtures; after both provider contracts merge, the existing FacMan
superbuild tests host the visibly development-only cross-provider orchestration.
The neutral fixture uses `org.example.fixture`, versions `1.0.0` and `1.1.0`,
one `core` component, one entrypoint, one data file, `single_process`, and one
interrupted setup journal. It emits exact provider identities and normalized
results only as out-of-tree evidence, changes no stable consumer pin, performs
no setup mutation, and starts no product process.

The exact hosted observation passed all eight proof obligations and the full
FacMan matrix passed at the same task head. This joint proof does not promote
either provider contract beyond `fixture-qualified` and is not consumer
adoption. The next bounded wave is provider SDK packaging, beginning with
`ULK-CMAKE-SDK-PACKAGE-01`; that wave is not activated here.

Contract maturity is per contract:

```text
provider-local fixtures -> fixture-qualified
first real consumer adapter -> consumer-qualified
second independent consumer -> second-consumer-qualified
migration and shipped compatibility proof -> release-candidate
supported release and deprecation policy -> stable
```

## Authority boundary

This programme and its green tests grant no provider repin, real Setup
mutation, product or Factorio execution, credential or network use, protected
merge, signing, publication, human verdict, successor Play route, permit, or
release authority. Revalidation-04 remains superseded immutable history. A
future authority-bearing action needs its own reviewed WorkUnit and evidence.
