# Universal product runtime and delivery programme

Status: ratified umbrella architecture; preparation does not grant execution or release authority

Last reviewed: 2026-08-10

Consumers: FacMan, Dominium, Compact Cassette Catalogue, and synthetic fixtures

This is an umbrella programme, not a fourth repository, shared runtime
installation, cross-platform skin, or permission to merge product histories.
The constitutional statement is:

> Providers define reusable capability. Products define meaning. A
> deterministic product-owned composition compiler resolves one exact target
> graph. Package adapters project, but never redefine, that graph.

The execution authority remains `release/index/plan.v1.toml`. This document is
durable architecture: it constrains future plans but does not activate a
WorkUnit, accept an external pull request, move a provider pin, issue an
operation permit, or authorize signing or publication.

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

## Semantic kernels and capability hosts

The provider names identify two different maturity surfaces in each provider
repository:

| Surface | Role | Stability rule |
| --- | --- | --- |
| **ULK — Launcher Kernel** | Runnable references, plans, operations, outcomes, commands and Setup handoff. | Durable semantic/C-ABI kernel; consumer evidence gates promotion. |
| **ULU — Launcher Host** | Persistence, process/session, IPC, activation, platform paths and runtime providers. | Experimental SPI until implementations and consumers qualify it. |
| **USK — Setup Kernel** | Packages, typed effects, installed state, transactions, recovery, refusal and audit. | Durable semantic/C-ABI kernel; maturity is separate from package version. |
| **USU — Setup Host** | Source, archives, cache, filesystem, elevation, native integration and trust providers. | Experimental SPI until effect, recovery and consumer evidence qualify it. |

ULU and USU are layers inside the existing provider repositories. They are not
additional repositories, mandatory global runtimes, or buckets for every
platform-specific implementation. An unimplemented host declaration is not an
installed SDK promise. Host APIs remain outside the stable/default surface
until callable providers, negative controls, lifecycle evidence and at least
one real consumer exist.

This decision extends the three-repository convergence strategy to multiple
genuinely different consumers. The authoritative consumer matrix is
`release/index/universal_consumer_requirements.v1.toml`.

## Programme north stars

The platform north star is one authoritative installed-software lifecycle,
one authoritative runnable-product lifecycle, product-specific interpretation
at the edges, independently releasable providers, exact consumer locks,
reversible migrations, and no hidden effect authority.

The FacMan north star is a player who can create or select a complete isolated
Factorio environment, understand readiness, make it ready only through
explicit authorities, reach the ordinary Factorio menu through an accepted
route, preserve and recover state, and reconstruct the environment without
silent mutation of foreign-owned resources.

The engineering stopping rule is:

- every reusable abstraction has one demonstrated consumer;
- every stable universal abstraction has two genuinely different consumers;
- stable contracts also require source/SDK equivalence, migration and rollback,
  compatibility and deprecation policy, and at least one shipped release;
- generic-looking code is not moved merely because its name appears reusable.

## Permanent six-plane constitution

| Plane | Permanent owner | Responsibility |
| --- | --- | --- |
| Product meaning | Product repository | Identity, compatibility, recipes, content semantics, readiness and product policy |
| Runnable state | Universal Launcher | References, plans, operations, sessions, process lifecycle and launcher persistence |
| Installed state | Universal Setup | Package verification, target authority, lifecycle mutation, rollback, recovery and audit |
| Acquisition | Product or product-owned connector | Discovery, download, entitlement and stable local-candidate production |
| Presentation | Product repository | Product views, actions, terminology, branding and native shells |
| Release and trust | Each repository for its releases | Versioning, composition, packages, signatures, channels, provenance and support |

Planes do not collapse. A URL is not a package identity; download completion is
not trust; a launch plan is not process authority; an installation plan is not
mutation authority; a technical packet is not a human verdict; and a package
digest is not publisher authenticity.

The resulting platform is:

```text
Universal Launcher       reusable runnable-product lifecycle
Universal Setup          reusable installed-software lifecycle
Product repositories     meaning, policy, connectors, presentation, releases
Composition compiler     one exact product graph for one target
Native shells            platform-appropriate projection of product semantics
Trust pipeline           exact packages, provenance, signatures and support
```

## Current-boundary reconciliation

The reviewed 5 August promotion chain is now recorded as durable programme
truth. Tracked FacMan truth has advanced in several areas:

- provider-neutral ULK composition and USK package/recipe contracts are
  recorded as promoted and `fixture_qualified`;
- the synthetic cross-provider product TCK is recorded complete;
- FacMan workspace-root authority and successor route definition are complete;
- canonical ULK and USK SDKs are promoted to `main` and synchronized into
  provider `dev`;
- `THREE-REPO-SOURCE-VS-SDK-CONFORMANCE-01` is the active dependency-ready
  WorkUnit;
- explicit SDK consumption and atomic provider-pin reconciliation follow as
  separate WorkUnits;
- immutable route definition v1 cannot be reused with a changed provider set,
  so a non-authorizing v2 definition follows reconciliation before source
  closure;
- `FACMAN-SUCCESSOR-PLAY-SOURCE-CLOSURE-01` remains
  `required_but_blocked` on coherent provider/route identity and a capable
  Windows native closure host;
- the FacMan release model v2, deterministic resolver, staging verifier and
  directory/ZIP/TAR conformance path are implemented and locally closed;
- reviewed lineage and observed build-source identity are separated, the ten
  resolution records have one domain-separated acyclic root, and packages
  receive only bounded runtime metadata;
- all package producers are censused under canonical-stage or temporary
  exception custody, and immutable malformed history has exact forward-only
  policy exceptions;
- FacMan still consumes its separately accepted provider pins and has not
  adopted installed provider SDKs;
- no real Play route, observed player journey, setup mutation, signing,
  publication or stable support claim has been accepted.

Provider SDK repository acceptance is complete. That does not adopt the new
provider identities into FacMan: source/static/shared/relocated/private-runtime
conformance is active, FacMan's consumed pins remain unchanged, and provider
adoption remains a separately reversible consumer sequence.

## Reviewed identities

The current repository and provider roles are:

| Repository | Canonical `main` | Synchronized `dev` | FacMan-consumed revision |
| --- | --- | --- | --- |
| FacMan | `b70be10696855628c6d2948eb016c8424912e14e` | `715422842c7db8ca52162091ca70026b99768da2` | n/a |
| Universal Launcher | `1cafe4054297cc11e02458b83d230db0cd064471` | `7d4fd8e25a8d529279c4ad18d983e9cd51839eb7` | `7fc25340623131ba86c08dca4fb8a43b18a4520d` |
| Universal Setup | `32488fc13bd2439f9f6e52e83a97f6da345a7650` | `6dc48673d54fb27ac4e8949da6f43275d36c9622` | `3048128963dc718a7c38c1cfcdda9e813a23b0db` |

The bounded programme therefore retains these exact FacMan provider pins:

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
| `ULK-CMAKE-SDK-PACKAGE-01` | canonical `main` `1cafe4054297cc11e02458b83d230db0cd064471`; synchronized `dev` `7d4fd8e25a8d529279c4ad18d983e9cd51839eb7` |
| `USK-CMAKE-SDK-PACKAGE-01` | canonical `main` `32488fc13bd2439f9f6e52e83a97f6da345a7650`; synchronized `dev` `6dc48673d54fb27ac4e8949da6f43275d36c9622` |

The provider-local neutral fixtures and hosted matrices qualify only the new
contracts. This is not FacMan consumer adoption: FacMan's tracked provider pins
remain unchanged until a separate post-promotion adoption WorkUnit.

The immutable earlier architecture inputs remain historical evidence at
`417c8b705d7b1a320091aa20954e382dcb62be4c` for ULK and
`1a3fe548d278da038b96579363c1ddb7d92edeee` for USK. They do not override the
current canonical SDK heads or FacMan's separately accepted consumed pins.

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
adoption. Provider SDK packaging is now canonical; the active bounded wave is
cross-mode conformance, still without a FacMan pin change.

Contract maturity is per contract:

```text
provider-local fixtures -> fixture-qualified
first real consumer adapter -> consumer-qualified
second independent consumer -> second-consumer-qualified
migration and shipped compatibility proof -> release-candidate
supported release and deprecation policy -> stable
```

## Three authoritative graphs

Universal Launcher owns the runnable graph:

```text
Product
├── Entrypoints and launch capabilities
├── Install, instance, profile, account and artifact references
├── Launch plans and staleness
├── Operations and attempts
├── Sessions and process containment
└── Contract-set identity
```

Universal Setup owns the installed-state graph:

```text
Product package
├── Stable source identity and source manifest
├── Components and lifecycle-classified paths
├── Target topology and ownership
├── Setup recipe and migration graph
├── Installed state and native receipts
├── Transactions, rollback and recovery
└── Audit chain
```

Each product owns its resolved-release graph. FacMan's v1 resolver currently
binds exact product, provider, target, component, entrypoint, path, authority,
compatibility, qualification, package and claim records. Future release closure
must additionally bind the actual observed build source, full product/provider
contract-set identity, installation topology, mutable and preserved-data law,
SBOM, provenance and adapter obligations.

Every persistent reference should carry a stable ID, schema version, product
ID, revision, provider identity, freshness state and optional product-extension
reference. The provider base, product extension and derived runtime state must
remain separable for migration and support.

## Identity and compatibility law

These identities are independent and must never be substituted for one another:

```text
reviewed source base
observed build source and tree
provider source pin
provider package and ABI
provider contract-set digest
product binding ABI
workspace and installed-state schemas
resolved product digest
staged-image digest
package digest
signature and publisher identity
support and publication claim
```

Tracked source cannot contain the final hash of the commit that contains that
hash. A reviewed base may remain tracked, but the actual build source must be a
post-checkout or CI observation bound into release evidence. A package digest
proves integrity, not source identity or publisher authenticity.

A composite contract-set identity eventually covers ULK and USK packages,
ABIs and schemas; product binding ABI; workspace and installed-state schemas;
command, refusal and presentation contracts; provider revisions; and actual
product revision. Packages, runtime handshakes, support bundles and evidence
packets carry that identity.

Compatibility is a transition graph rather than a flat matrix. Nodes include
product version, workspace schema, product-binding ABI, provider packages and
contracts, installed-state schema, target profile, package backend and Factorio
compatibility set. Each transition records preconditions, migration, backup,
rollback, downgrade, irreversibility, minimum maintenance host, qualification
evidence and support window. Binary rollback without state compatibility or
restoration is not rollback.

## Provider productization contract

ULK and USK should each independently ship the capabilities their consumers
actually prove:

```text
stable C ABI and public headers
static and shared libraries
relocatable CMake package
private redistributable runtime
contract and schema bundle
ABI and exported-symbol snapshots
SDK guide, examples and TCK fixtures
reference tools appropriate to provider ownership
source, symbols, licence, SBOM and provenance artifacts
```

ULK reference tools may include CLI/TUI hosts, client/process/session tools and
reference-persistence examples. USK reference tools may include package
authoring, verification and maintenance/recovery applications. Product-branded
launchers and setup applications remain in their product repositories.

The stable compatibility floor is C. Thin C++, C#, Objective-C, Swift, GTK,
Qt or tooling bindings map types, lifetimes, allocators, callbacks, results and
operations only; they do not own business logic or establish a cross-compiler
C++ ABI.

Three consumption modes must become behaviorally equivalent:

1. exact source workspaces with full source closure;
2. installed static/shared and relocated SDKs;
3. exact private product-local redistributable runtimes.

Static linking or private deployment is the initial default. A global shared
ULK/USK runtime is rejected until loader, coexistence, compatibility, update
and support policy are proven.

`THREE-REPO-SOURCE-VS-SDK-CONFORMANCE-01` prepares the cross-mode proof.
`FACMAN-PROVIDER-SDK-CONSUMPTION-01` follows only as a separate, reversible
consumer adoption. `FACMAN-PROVIDER-PIN-RECONCILIATION-01` then aligns one
exact provider truth atomically. If that truth differs from immutable route
definition v1, `FACMAN-SUCCESSOR-PLAY-ROUTE-DEFINITION-02` creates a fresh,
non-authorizing definition before source closure; v1 is never edited or treated
as simultaneously active with the new provider set.

## FacMan product and presentation direction

C1 remains deliberately narrow and is an internal alpha foundation: one
supported existing standalone
installation, one isolated vanilla instance, truthful readiness, one exact
Play-to-menu route, backend session supervision, Last Run, relaunch, recovery,
and Windows x64 WinForms as the reference lane. The current Instances,
Installations, Activity, Settings/About, Launch Deck and Advanced shell remains
stable through C1. C1 is not the complete public `0.1.0` capability contract.

After C1 user evidence, the product may converge on Home, Instances, Library
and Activity. The visible term `Library` must be user-tested. Accounts remain
contextual unless a real journey proves a top-level destination.

The Launch Deck has one authoritative primary action:

| State | Primary action |
| --- | --- |
| ready | Play |
| preparation possible | Make Ready |
| attention required | Review |
| blocked | View Problems |
| running | Show Game or Manage |
| recovery required | Recover |
| outcome unknown | Inspect Operation |

A future FacMan presentation service owns `presentation.snapshot`,
`presentation.action` and `presentation.refresh`. Immutable snapshots carry
revision, freshness, dependency identities, navigation, selected instance,
readiness, blockers, Launch Deck state, operations, Last Run, recovery and
available actions. Frontends do not reconstruct product truth through
independent command sequences.

Presentation doctrine remains portable semantics with native presentation.
WinForms is the C1 reference and public-`0.1.0` GUI. AppKit, GTK and Qt are
later than C1 but mandatory for the admitted `1.0.0` matrix. WinUI and SwiftUI
remain optional post-`1.0.0` projections. System Native is mandatory; OEM+ is
bounded; custom themes are declarative data and assets only. Accessibility and
high-contrast policy override themes. Setup/maintenance retains its separate
Source → Inspect → Review → Confirm → Apply → Verify → Recover flow.

## Finite release completion contracts

Public `0.1.0` is a complete Windows 10/11 x64 public beta, not a renamed C1
checkpoint. Its frozen finite matrix admits only capabilities the programme
commits to completing for that release. Every required row must have one shared
semantic implementation and complete CLI, TUI and WinForms projections, plus
positive, negative, fault, recovery, package, accessibility, documentation and
support evidence. No ordinary journey may depend on a fixture, scaffold,
permanent refusal, hidden Advanced form or undocumented command.

`1.0.0` closes a second measurable matrix. Every admitted ordinary capability
must be complete through CLI, TUI, WinForms, AppKit, GTK and Qt on its exact
supported target profiles. Completion means zero required matrix gaps, zero
known P0/P1 defects, independently reconstructible supported packages,
qualified accessibility and lifecycle behavior, supported migrations and
rollback, and no advertised incomplete feature. It is an enforceable contract,
not a claim of metaphysical perfection.

Compatibility lanes may select different binaries, runtime closures, ULU/USU
providers and local sidecars while preserving kernel and product semantics.
Legacy floors are qualified per target profile; one binary for modern Windows,
old Windows, frozen macOS and old glibc is explicitly not a goal.

The release doctrine is machine-readable in:

- [`version_train.v1.toml`](../../release/index/version_train.v1.toml)
- [`autonomy_policy.v1.toml`](../../release/index/autonomy_policy.v1.toml)
- [`plan.v1.toml`](../../release/index/plan.v1.toml)
- [`capability_frontend_matrix.v1.toml`](../../release/index/capability_frontend_matrix.v1.toml)
- [append-only release ledger](../../release/ledger/README.md)

Those records are ratified planning contracts with activation gates. They do
not make a current checkout release-eligible or authorize a tag, protected
merge, signing, publication, support claim or withdrawal. Autonomous agents may
construct, test, document and qualify alpha candidates within their declared
envelope. Accountable human validation is concentrated at the end of beta,
release-candidate and stable trains, after automated evidence is complete.

## Physical convergence and migration law

No directory moves because its name looks generic. Every extraction follows:

```text
characterize current behavior
→ split generic mechanism from product law
→ add an additive provider surface and TCK
→ promote the provider independently
→ migrate one exact consumer through an adapter
→ prove source/SDK and old/new equivalence
→ retain rollback and one compatibility window
→ delete or thin the product incubator
```

Likely FacMan-to-ULK candidates include generic client/process transport,
process/session containment, references and stores, launcher metadata journals,
preference persistence and generic result/operation envelopes. Factorio
response interpretation, workspace extensions, content transactions,
preference keys, refusals and application modules remain in FacMan. The permit
kernel stays FacMan-local until a distinct authority-bearing consumer exists.

Workspace migration always characterizes and backs up the old state, adds a
dual reader, projects provider base and product extension, writes and reopens a
staged result, switches atomically, retains rollback and preserves the old
reader for one support window. Unknown future versions fail closed.

Portable instance, content, world and support bundles eventually carry product
and provider identities, content locks, hashes, lifecycle classification,
compatibility and redaction policy. Credentials never enter portable bundles.

## Security and operational trust

One authority owns each effect class: USK for installed-software mutation, an
ULK execution provider for process/session effects, the product for product
eligibility, a connector for acquisition/network effects, a credential
provider for secrets, and a release service for signing/publication. No Boolean
configuration option, frontend, package script or theme may manufacture these
authorities.

The first FacMan route remains one immutable Windows x64, standalone,
Factorio 2.0.77, menu, instance-isolated record. Evidence for it says nothing
about Steam, Factorio 2.1, save/server/editor/benchmark intents, enforced
hermetic execution or arbitrary process authority.

Acquisition produces only a stable local candidate and expected evidence. USK
reopens and verifies that candidate independently before setup planning.
Credentials live in platform stores, appear in workspaces as opaque references,
are disclosed only to exact connectors, and remain redacted from logs, support
bundles, manifests and themes.

Trusted distribution ultimately requires key ownership, rotation, revocation,
incident response, signed package and channel metadata, publisher verification,
SBOM, provenance, dependency inventory, withdrawal and rollback policy. An
external maintenance host should perform early self-update rather than an
in-process executable replacing itself.

## Reliability and performance preparation

Provider-owned responses require explicit allocation and release,
source-independent lifetime, validated structure and bounded total size.
Durable operations bind request, operation, attempt and plan IDs; phase;
possible effects; progress; terminal outcome; and recovery reference. No
frontend may manufacture a stronger terminal result.

Direct native clients are preferred for ordinary native shells. One-shot
process RPC remains the compatibility, diagnostics and isolation path. A
persistent service is justified only by measured need such as survival across
frontend death, multiple observers, background acquisition or multi-session
supervision.

The concurrency floor is shared workspace inspection, exclusive workspace
mutation, per-instance operations and Play, per-install lifecycle, and a global
exclusive workspace migration. An actor system or distributed lock manager is
not required.

Performance work measures startup, workspace open, 1,000/10,000 references,
large modsets, save indexing, presentation snapshots, direct/process command
latency, archive inspection, streaming staging and support export. Evidence
records wall/CPU time, peak memory, allocation, copy, I/O, hashing, lock wait
and provider duration. Fault injection covers allocation, short I/O, disk full,
source replacement, permission loss, journal interruption, frontend death,
child survival, timeout, output exhaustion, package corruption, clock change,
network interruption and signing-metadata mismatch.

## Repository and CI governance

All participating repositories retain protected `main`, integrated `dev`,
bounded `task/*` and synchronized `hotfix/*` roles. Main remains an ancestor of
dev; provider changes land independently before consumer adoption; no force
push, floating dependency or atomic multi-repository merge is allowed.

The bounded canary matrix is pairwise rather than Cartesian: FacMan with locked
providers, FacMan with one provider dev at a time, FacMan with both provider
dev branches, the synthetic product with both, Dominium with both where
available, and the C3 package profile with USK dev.

A future narrow adoption application may observe provider main promotions,
create consumer task branches, update exact pins and contract-set identity,
open pull requests and run checks. It may not merge, approve itself, bypass
branch protection, sign, publish or access product credentials.

Provider health reports main/dev ancestry, consumer pins and reachability, ABI
and schema versions, contract-set digest, canaries, SDK/runtime artifacts,
source closure, incubator debt and authority booleans. Continuous evidence, not
empty commits, demonstrates provider health.

The truth hierarchy is canonical plan; component ownership; exact provider
locks; reviewed checkpoint; durable architecture and contracts; out-of-tree
live observation; run-specific execution profile; and retained history. WIP is
bounded to one active release, one migration wave, one WorkUnit per repository,
three implementation WorkUnits overall, ten ready items and one large
migration.

## Dependency-ordered preparation register

The long programme has four tracks that meet only at explicit gates:

| Track | Purpose |
| --- | --- |
| A | FacMan product route, C1 package, user evidence and later product capabilities |
| B | Independently consumable ULK/USK SDKs, runtimes, tools and lifecycle maturity |
| C | Synthetic, FacMan, Dominium and C3 consumer convergence and incubator removal |
| D | Release closure, signing, updates, support, security and operations |

Current disposition by wave:

| Wave | Prepared outcome | Current disposition |
| --- | --- | --- |
| 0 | Independently integrate the reviewed provider/product train | Provider SDK task/dev/main/synchronized-dev chain complete; FacMan pins unchanged |
| 1 | Source/static/shared/relocated/private-runtime equivalence | Active as `THREE-REPO-SOURCE-VS-SDK-CONFORMANCE-01`; no adoption authority |
| 2 | Explicit SDK consumption, atomic pin reconciliation and successor route v2 | Planned in dependency order; immutable route v1 remains historical and unchanged |
| 3 | Workspace authority and exact successor source closure | Workspace authority complete; source closure required but blocked on wave 2 and a capable Windows host |
| 4 | Fresh successor qualification with negative controls | Planned after source closure; no execution authority |
| 5 | Separately authorized stage, observer, two launches and human verdict | Blocked authority-only; old revalidation stays closed |
| 6 | Narrow Windows C1 package, live acceptance, clean-machine and accessibility proof | Planned/later; unsigned or explicitly classified until trusted preview |
| 7 | Release model, compiler, adapter and release closure | Resolver, source custody, aggregate root, runtime projection and release-build staging complete; producer convergence, exact-head closure and security review remain gated |
| 8 | Presentation v1 and classic native parity | Post-C1 evidence only |
| 9 | Dominium and C3 as real capability-selective consumers | Later; no contract stabilization before adoption |
| 10 | Physical ULK convergence and FacMan incubator reduction | Later per characterized surface |
| 11 | Streaming, recoverable and authentic USK production lifecycle | Later after a real lifecycle consumer is selected |
| 12 | FacMan managed content | After C1 foundation proof; public admission is controlled by the frozen milestone matrix |
| 13 | Permit-backed managed installations | C3 after C2 and consumer-qualified USK lifecycle |
| 14 | Acquisition, updates, accounts and Mod Portal connector | Later capability-scoped connectors |
| 15 | Complete Windows `0.1.0` public beta | After its finite matrix, exact package and operational ownership close |
| 16 | AppKit, GTK and Qt product closure | Post-C1; all admitted rows must close before `1.0.0` |
| 17 | Trustworthy `1.0.0` | After stable workflows, migrations, six-frontend parity, support and security evidence |

Only the canonical plan may move a prepared item to ready or active. The plan
now activates canonical provider conformance while leaving SDK consumption,
pin reconciliation, route definition v2, source closure, qualification,
security verdict and route evidence behind their exact dependencies and
authority boundaries.

## Evolution-proof architecture

The post-C1 evolution law is ratified in
[`evolution_spine.md`](evolution_spine.md). It defines the independently
versioned **Compatibility vector**, four-axis **Capability-guarantee model**,
**Durable state and migration law**, and bounded **Extension trust ladder**.
It also prepares a shared explanation graph, Doctor, and Safe Mode without
moving Factorio meaning or presentation out of FacMan.

Those constitutions remain later-horizon planning. They do not enter the C1
dependency graph, move a provider pin, accept source closure, enable an
extension, execute Setup or Factorio, qualify a support floor, sign, publish,
or promote a route. Their five bounded WorkUnits may activate only after C1 is
release-proven.

## Deferred and rejected directions

Deferred until evidence exists: a daemon, full TUF implementation, delta
updates, cloud sync, marketplace, all modern GUI toolkits, all package formats,
sandboxed scripts, automatic self-update, broad account management and remote
administration.

Rejected: repository merger; a fourth generic implementation repository;
global provider runtime by default; atomic cross-repository merges; package
scripts defining product truth; USK directly editing package-manager-owned
paths; frontends holding setup/process/credential authority; native plugins
before isolation and stable ABI; executable themes; one universal branded GUI;
empty activity commits; floating provider dependencies; and broad
`process_execution_authorized` switches.

## Programme success measures

Progress is judged by accepted routes, removed duplication, real consumers,
reversible migrations, clean package proof, observed user journeys and
supportable releases. Schema, branch, framework, WorkUnit and document counts
are not success measures.

The stable platform threshold is two distinct real consumers for each provider,
source/installed-SDK equivalence, independently signed provider packages,
supported migration and deprecation, removal or explicit retention of generic
incubators, and no product-local competing provider kernel.

## Authority boundary

This programme and its green tests grant no provider repin, real Setup
mutation, product or Factorio execution, credential or network use, protected
merge, signing, publication, human verdict, successor Play route, permit, or
release authority. Revalidation-04 remains superseded immutable history. A
future authority-bearing action needs its own reviewed WorkUnit and evidence.
