---
document_id: FACMAN-PLATFORM-REFACTOR-TODO
schema_version: "1.1"
title: FacMan platform refactor, redesign, and cross-repository backlog
status: archived-planning-corpus
superseded_by: release/index/plan.v1.toml
archived_on: 2026-07-28
created: 2026-07-28
last_reviewed: 2026-07-28
planning_horizon: multi-release
canonical_repository: factorio-launcher
related_repositories:
  - universal-launcher
  - universal-setup
  - dominium
canonical_branch: main
integration_branch: dev
active_safety_gate_observed: FACMAN-PLAY-EVIDENCE-STABLE-IO-01
implementation_authority: none
primary_decision: converge contracts, clients, operations, presentation, composition, and conformance without merging authorities or repositories
source_reports_synthesized: 2
classic_shell_archetype: old Minecraft launcher visual grammar, not its backend or security model
classic_frontend_family:
  - WinForms
  - AppKit
  - GTK 3
modern_frontend_family:
  - WinUI 3
  - SwiftUI
  - Qt 6
---

# FacMan platform refactor, redesign, and cross-repository backlog

> This is the durable planning backlog for the architectural report reviewed on
> 2026-07-28. It records intended work, dependencies, ownership, decisions,
> investigations, acceptance gates, migration constraints, and explicitly
> deferred ideas. It is not an operation permit, release approval, branch
> promotion approval, or authorization to bypass the active Play-evidence gate.

## How to use this document

- A checked item is complete only when its stated acceptance evidence exists.
- An unchecked item may be planned, blocked, exploratory, or deliberately
  deferred; read its metadata before starting it.
- `P0` protects safety or architectural integrity, `P1` enables the next
  convergence milestone, `P2` improves product completeness, and `P3` is
  evidence-driven expansion.
- `BLOCKED` means the work must not start until the named prerequisite is
  satisfied.
- `EXPLORE` means investigate and record a decision before implementation.
- Repository names identify permanent ownership, not necessarily the repository
  in which an abstraction is currently incubating.
- Every implementation item must become a bounded task with changed-file,
  validation, remaining-risk, compatibility, migration, and rollback evidence.
- When this document conflicts with an accepted contract, authority policy,
  release gate, or newer reviewed architecture decision, the accepted source of
  truth wins and this document must be updated.

## Executive verdict

The existing direction is fundamentally correct. FacMan should become one
coherent product composition over two separate universal authorities:

```text
FacMan product shells
  -> Universal Client and Presentation SDK
  -> FacMan product composition
       -> Universal Launcher Kernel
       -> Universal Setup Kernel through a typed SetupPort
       -> Factorio providers and presentation pack
       -> platform, credential, source, and storage ports
```

The platform must unify:

- protocol definitions and generated bindings;
- frontend-neutral clients and interchangeable transports;
- operation, cancellation, recovery, refusal, and diagnostic semantics;
- product-composition contracts;
- task-oriented presentation semantics;
- build composition, package identities, and source closure;
- provider, transport, frontend, authority, and ABI conformance tests.

The platform must not unify:

- Universal Setup and Universal Launcher authority;
- Factorio and Dominium product semantics;
- installed-state and runnable-state databases;
- all repositories into a monorepo;
- every shell into one cross-platform GUI framework;
- every extension into an in-process plugin;
- all policy into a global “god object”;
- desired, observed, authoritative, resolved, and presentation state.

## Synthesis of the architecture and launcher-shell reports

The launcher-shell report reinforces the architecture report rather than
replacing it. The old Minecraft launcher contributes a useful **visual grammar**
for a classic FacMan shell:

- one resizable native window;
- ordinary platform menus, tabs, lists, tables, forms, dialogs, and chrome;
- a large central task area;
- a persistent instance selector and prominent primary launch action;
- concise status explaining what will happen;
- equivalent information architecture rendered natively on each platform.

It does not contribute the product architecture. FacMan must replace the old
launcher’s shallow profile, privileged remote HTML, raw log panes, weak
operation semantics, implicit launch behavior, and GUI/backend coupling with:

- installations, portable instance intent, machine binding, profiles, modset
  locks, saves, account references, launch intents, and computed readiness;
- federated plans with exact authorities and effects;
- durable operation, event, cancellation, recovery, and unknown-outcome models;
- native cached/sanitized content rather than unrestricted remote pages;
- an Activity center with structured events and Console as an advanced view;
- a shared direct client with bounded process RPC only as fallback;
- semantic presentation, accessibility, localization, and theming contracts;
- distinct launcher, setup/maintenance, and constrained recovery shell shapes.

The synthesized product verdict is:

> Build a classic native, instance-centric FacMan launcher inspired by the old
> Minecraft launcher, backed by Universal Launcher client, presentation,
> operation, and recovery contracts. Prove it in WinForms, AppKit, and GTK
> before independently designed WinUI, SwiftUI, and Qt modern shells advance.

The visual archetype never overrides the authority, compatibility, extraction,
or active proof-gate laws elsewhere in this document.

## Immediate hold point

- [ ] **P0 / BLOCKED — Protect the active Play-evidence proof gate.**
  - Owner: `factorio-launcher`.
  - Observed active work: `FACMAN-PLAY-EVIDENCE-STABLE-IO-01`.
  - Do not mix universal extraction, root-layout migration, workspace rewrites,
    real setup-authority promotion, process-authority promotion, or GUI redesign
    into the active determinism and verdict work.
  - Documentation, contract proposals, fixtures, inventories, and report-only
    validation may proceed when isolated from the active worktree.
  - Exit evidence: the active proof gate is closed, current project-state truth
    identifies the next task, and the architecture freeze permits the selected
    bounded refactor.

## Non-negotiable architecture laws

1. Universal Setup alone authoritatively mutates installed software and owns
   install, verify, repair, move, uninstall, rollback, recovery, ownership, and
   mutation audit.
2. Universal Launcher alone authoritatively orchestrates runnable product state,
   installation references, instances, profiles, artifact references, launch
   plans, operations, process sessions, and launcher recovery.
3. Product providers interpret product facts and produce recipes,
   contributions, or launch specifications; they do not inherit filesystem,
   process, network, credential, signing, or publication authority.
4. Frontends parse intent and render commands, views, plans, operations,
   refusals, diagnostics, and recovery. They do not discover installations,
   calculate compatibility, construct launch commands, issue permits, or mutate
   authoritative state.
5. Configuration, imported bundles, profiles, presets, UI state, and extensions
   may narrow authority but can never widen it.
6. Process creation goes through the launcher process port. Installed-application
   mutation goes through Universal Setup. Credentials remain in an OS/provider
   credential store and appear elsewhere only as logical references.
7. Readiness is a computed projection over versioned evidence. No persisted
   `ready = true` flag is authority.
8. Cancellation or timeout after dispatch is not proof that no effects occurred.
   Unknown outcome and recovery-required states must fail closed.
9. Every effectful plan binds exact source, target, product/provider revisions,
   resource identities, declared effects, expiry, policy decision, digest, and
   verification/recovery route.
10. Existing stable C-facing names and ABI symbols remain compatible until an
    explicit versioned migration is accepted.
11. Product-neutral code moves only after its interface is qualified by
    conformance evidence and, where required, a second real consumer.
12. Factorio concepts do not leak into universal contracts; Dominium simulation
    law does not move into Universal Launcher or Universal Setup.
13. The command graph is the exhaustive automation surface. The view/action
    graph is the primary task-oriented presentation surface. Neither replaces
    the other.
14. Direct, process, and any future local-service transport execute the same
    composition and handlers through the same normalized contracts.
15. Repositories remain separate unless a later evidence-backed decision proves
    that a new boundary reduces rather than increases coordination cost.
16. Classic and modern shells share semantic records and operations, not widget
    code or a pixel-identical skinning layer.
17. The selected instance, not a shallow profile or news feed, is the center of
    the FacMan product experience.
18. News, themes, notifications, and other downloaded presentation content are
    non-authoritative, bounded, validated, sanitized, cached, and unable to
    delay startup or Play.
19. A launcher shell, setup/maintenance shell, and recovery shell may reuse
    components but must not be forced into the same navigation shape.
20. No GUI may expose real mutation while its primary cancellation mechanism is
    killing a one-shot CLI transport process.

## Current-state assessment

### What is already strong and should be preserved

- Exact three-repository source closure is pinned by
  `release/index/workspace_lock.v1.toml`.
- The FacMan development composition validates sibling Git revisions before
  adding Universal Launcher and Universal Setup to the build.
- Universal Setup already has substantial lifecycle, transaction, state,
  recovery, and verification behavior.
- Universal Launcher already declares the correct product-neutral concepts and
  C-facing seams.
- The Factorio binding registers generated command descriptors into the
  Universal Launcher command registry and routes to typed product handlers.
- CLI and TUI consume a shared FacMan client instead of using the CLI parser as
  the application foundation.
- Command metadata already carries identities, schemas, effects, availability,
  refusal reasons, risk, CLI grammar, defaults, repeatability, localization, and
  renderer identities.
- Stable C-compatible boundaries support C/C++, .NET P/Invoke, Objective-C++,
  Swift C interop, GTK, Qt, and older platform toolchains.
- Operation outcomes already distinguish pre-dispatch cancellation, refusal,
  completion, cancellation-requested-but-completed, recovery-required, and
  outcome-unknown.
- FacMan’s ownership manifest already labels temporary product-neutral
  incubators and their extraction gates.
- The instance model already distinguishes spec, machine binding, readiness,
  effective configuration, and recent history.
- Dominium already has a strong intent/command/capability/refusal/result/evidence
  conceptual spine and can become the second consumer before its stubs harden
  into competing kernels.

### Primary gaps to fix

| ID | Priority | Gap | Consequence | Required direction |
| --- | --- | --- | --- | --- |
| ARCH-001 | P1 | Universal Launcher implementation is much smaller than its declared ownership | FacMan retains product-neutral runtime infrastructure | Extract clients, transports, persistence, process, permits, operations, and generic schemas incrementally |
| ARCH-002 | P1 | Universal Launcher and Universal Setup duplicate ABI/protocol primitives | Drift, duplicated fixes, inconsistent bindings | Generate prefixed compatibility surfaces from one logical protocol source |
| ARCH-003 | P1 | Raw JSON validation and routing are too widely handwritten | Large dispatchers, duplicated validation, unsafe divergence | Generate structural codecs and fixtures from command descriptors |
| ARCH-004 | P1 | Command metadata is treated as if it were a complete GUI model | Generic form-heavy UX instead of player tasks | Add a typed view/action presentation contract |
| ARCH-005 | P1 | Native GUIs spawn the CLI for each request | Weak operation lifetime, cancellation, progress, and executable discovery | Provide stable native client bindings and direct transport; retain process fallback |
| ARCH-006 | P1 | Dominium setup/launcher stubs could become duplicate authorities | A second incompatible platform architecture | Replace stub ownership with providers, presentation packs, and compositions |
| ARCH-007 | P1 | Source integration is pinned but tightly coupled through sibling paths and `add_subdirectory` | Cache/target pollution and weak installed-SDK consumption | Support top-level/subproject modes and exported namespaced packages |
| ARCH-008 | P2 | “Setup” names several different resources and apps | Ambiguous APIs, UX, and ownership | Standardize installation/instance/profile/preset/setup-operation/setup-shell terms |
| ARCH-009 | P1 | Per-call handwritten Setup gateway bypasses the canonical handoff shape | Weak correlation, cancellation, and recovery semantics | Use a long-lived generic setup client and typed handoff records |
| ARCH-010 | P1 | Central application composition and dispatch remain too broad | Difficult ownership, testing, and extraction | Introduce explicit modules, ports, descriptors, and generated admission |
| ARCH-011 | P1 | Reference persistence mixes generic bases and Factorio extensions | Whole-workspace moves would over-generalize product data | Split base records from versioned product extensions with compatibility projection |
| ARCH-012 | P1 | Process and permit abstractions are still FacMan incubators | Universal ownership is incomplete | Qualify with a second provider, then extract narrow primitives |
| ARCH-013 | P2 | Async operations are not a universal client capability | GUIs cannot safely survive long-running effects or restarts | Add submit/observe/inspect/cancel/resume/recover operation APIs |
| ARCH-014 | P2 | Conformance is not yet systematic across protocols, providers, transports, and shells | “Parity” can mean different things per platform | Build TCKs and semantic fixtures, including a synthetic product |
| ARCH-015 | P2 | Release composition is not a single runtime-inspectable manifest | Build, SBOM, About, and compatibility truth can drift | Generate from one product-composition manifest |
| ARCH-016 | P3 | Optional service, dynamic providers, self-update, and remote control lack qualified need and authority models | Premature complexity and expanded attack surface | Keep deferred behind explicit evidence gates |
| ARCH-017 | P1 | Classic GUI shells lack a frozen information architecture and instance-centric primary-action model | Platform shells can drift into unrelated generated forms | Define a universal classic shell contract and persistent Launch Deck |
| ARCH-018 | P1 | Existing FacMan navigation targets are resource-rich but not organized into a bounded classic top strip | Too many equally weighted pages and weak task hierarchy | Use eight top-level FacMan pages with nested resource views and Advanced surfaces |
| ARCH-019 | P1 | Home/news could repeat the privileged remote-web anti-pattern | Remote content could execute or track inside a privileged launcher | Use allowlisted bounded feeds, sanitization, native cached rendering, and external links |
| ARCH-020 | P1 | Raw Console framing is too narrow for downloads, setup, sessions, operations, and recovery | Users lose causal and authority context | Build structured Activity with Console as an advanced subpage |
| ARCH-021 | P1 | Launcher, setup, and recovery apps risk sharing one unsuitable navigation shell | Setup/recovery tasks become confusing or unsafe | Share presentation components but define three distinct shell shapes |
| ARCH-022 | P2 | Arbitrary cross-platform skinning would weaken native behavior and accessibility | Broken focus, contrast, security notices, and recovery | Define semantic, capability-aware themes with a non-removable System Native fallback |
| ARCH-023 | P2 | Legacy platform labels are broader than their proven native dependency closure | Compile-only or shell-only evidence may be mistaken for product support | Create architecture/sysroot-specific candidate lanes and require runtime closure proof |
| ARCH-024 | P2 | Frontends can expand unevenly before semantic parity is proven | One platform becomes a second product architecture | Build component galleries and one complete WinForms/AppKit/GTK vertical slice first |

## Permanent repository ownership

| Repository | Permanent responsibility | Must not own |
| --- | --- | --- |
| `universal-setup` | Product-neutral installed-software lifecycle, exact setup plans, target ownership, mutation transactions, rollback, recovery, installed-state verification, and mutation audit | Launcher state, product compatibility, GUI behavior, process sessions, credentials, Factorio/Dominium rules |
| `universal-launcher` | Product registry, installation references, instance/profile/artifact bases, launch plans, operations, launcher transactions, process supervision, client SDK, transports, and presentation SDK | Installed-state mutation implementation, product semantics, toolkit-specific shells |
| `factorio-launcher` | Factorio binding, discovery interpretation, setup recipes, instances, mods/modpacks, saves/worlds, accounts, launch/session interpretation, FacMan presentation, product packaging, and branded apps | Generic setup or launcher authority; generic transport/process/persistence implementations after extraction |
| `dominium` | Dominium engine/game semantics, package recipes, environments/profiles, content packs, client/server/workbench providers, presentation, packaging, and branded apps | Independent launcher/setup kernels once universal composition begins |

## Cross-repository code movement ledger

### Move or split from `factorio-launcher` to `universal-launcher`

| Current FacMan surface | Permanent destination | Keep in FacMan | Gate | Migration notes |
| --- | --- | --- | --- | --- |
| `runtime/client` | ULK client SDK | Factorio response adapters and FacMan-friendly facade | `ULK-CPP-CLIENT-ADAPTER-EXTRACTION-01` | Preserve behavior and public compatibility adapters while CLI/TUI switch to extracted client |
| Direct/process/daemon transport implementations | ULK transport layer | FacMan composition bootstrap and product discovery | `ULK-CLIENT-SCHEMA-CONSOLIDATION-01` plus transport TCK | One normalized request/result/event model; no product IDs hardcoded in transport |
| `contracts/result` generic envelope | ULK contracts | Factorio result payload schemas | `ULK-CLIENT-SCHEMA-CONSOLIDATION-01` | Preserve legacy FacMan envelope reader during transition |
| `contracts/schema/command` generic request/response | ULK contracts | Factorio command schemas | `ULK-CLIENT-SCHEMA-CONSOLIDATION-01` | Generate codecs and negative fixtures |
| `contracts/schema/transport` | ULK contracts | Product-specific payload bindings | `ULK-CLIENT-SCHEMA-CONSOLIDATION-01` | Version negotiation and bounded payload/lifetime rules required |
| Product-neutral portions of `runtime/workspace` | ULK reference persistence | Factorio workspace extensions, product schema, mod/save/account records | `ULK-REFERENCE-PERSISTENCE-EXTRACTION-01` | Read old format, project to new base, write current format, refuse future unknown versions |
| Generic `runtime/preferences` storage | ULK preferences mechanism | FacMan preference keys and presentation defaults | `ULK-REFERENCE-PERSISTENCE-EXTRACTION-01` | Separate user-local shell preferences from launcher/workspace policy |
| `runtime/transaction` launcher journals | ULK launcher transaction/recovery | Factorio-specific recovery guidance and projections | `ULK-REFERENCE-PERSISTENCE-EXTRACTION-01` | Never merge these with Universal Setup mutation transactions |
| `runtime/platform` process/session foundations | ULK process/platform layer | Factorio launch-spec creation and exit/log interpretation | `ULK-EXECUTION-FOUNDATION-EXTRACTION-01` | Move process identity, containment, environment, working directory, timeout, tree kill, session journal, exit classification |
| `runtime/core/permit` | ULK operation-permit kernel | Product policy contributions; never permit issuance | `ULK-PERMIT-KERNEL-QUALIFICATION-01` | Wait for Dominium or another real consumer; bind permits to exact plan/resources/revision/expiry |
| Generic application composition patterns in `runtime/factorio/application` | ULK product composition host | All Factorio domain/application modules | second-consumer composition proof | Extract interfaces and host laws, not Factorio command implementations |
| Cancellation/progress/operation-result primitives | ULK client and operation model | FacMan UX text and product-specific progress interpretation | async operation contract gate | Maintain synchronous compatibility path |
| Generic structural JSON codecs in `runtime/core/json` | Generated ULK/common boundary codecs | FLB/product JSON payload boundaries | protocol generation gate | Remove duplicated structural checks; retain semantic validation in product code |

### Keep permanently in `factorio-launcher`

- Factorio identity, release/channel/version interpretation, and component
  capabilities.
- Factorio installation and source discovery rules.
- Factorio archive layout and package recipe interpretation.
- Factorio-specific setup recipe generation and verification of returned plan
  identity/digest.
- Instances, isolation modes, configuration layout, launch arguments, and
  effective configuration rules.
- Mods, modsets, modpacks, dependency solving, Mod Portal semantics, content
  capabilities, DLC/Space Age interpretation, and reproducible locks.
- Saves, worlds, snapshots, backups, transfer, redaction, server, and developer
  workflows.
- Factorio account references and product-specific entitlement interpretation;
  secret material remains outside the repository state model.
- Factorio launch specification construction, session/log/crash
  interpretation, and product diagnostics.
- FacMan branding, navigation, localization, icons, empty-state guidance,
  product settings, and task-action mappings.
- FacMan package profiles, bootstrap configuration, release metadata, and
  product-specific SBOM composition.
- The Factorio binding ABI and compatibility layer.

### Consolidate logically across `universal-launcher` and `universal-setup`

- Canonical primitive ABI types.
- String and byte views and their lifetime rules.
- Export and calling-convention generation.
- Status, error, refusal, and diagnostic envelopes.
- Command request/response envelopes.
- Effects, capabilities, prompts, confirmations, and risk metadata.
- Operation identity, attempt identity, event, outcome, cancellation, and
  recovery records.
- Protocol version and transport negotiation.
- Positive, negative, future-field, lifetime, ABI-size, and cross-kernel
  fixtures.

Do this as one logical Universal Protocol Contracts package that generates the
existing `ulk_*` and `usk_*` names and symbols. Do not create a fourth
repository until two real products and cross-kernel conformance prove that a
separate repository lowers coordination cost.

### Reshape `dominium` without moving product semantics

- Replace `apps/launcher`’s independent `launcher_core` ownership with a
  Dominium product composition over Universal Launcher.
- Replace `apps/setup`’s independent `setup_core` ownership with a Dominium
  setup-recipe provider and Universal Setup client.
- Retain launcher/setup application roots as branded entrypoints, presentation,
  platform packaging, and composition wiring.
- Implement capability-specific Dominium providers rather than a single
  product-provider god interface.
- Keep the deterministic simulation engine independent; Universal Launcher may
  launch and supervise it but must not become part of simulation law.
- Make Workbench another client/frontend of the same composition; do not grant
  it setup or process authority by virtue of being a developer tool.

## Target platform shape

```text
Product shells
  Terminal: CLI | TUI
  Classic:  WinForms | AppKit | GTK 3/X11
  Modern:   WinUI | SwiftUI | Qt 6/Wayland (after classic proof)
                         |
      Universal Presentation Client + Product Pack
                         |
           Universal Client + Operation API
                         |
       direct | process fallback | optional local service
                         |
              Product Composition Host
             /                 \
      FacMan composition    Dominium composition
        Factorio providers    Dominium providers
        presentation pack     presentation pack
             \                 /
       Universal Launcher Kernel
                    |
               typed SetupPort
                    |
         Universal Setup Kernel
                    |
       Universal protocol contracts
```

## Master dependency and delivery order

```text
Active Play-evidence gate closes
  -> UNIVERSAL-PRODUCT-COMPOSITION-CONTRACT-01
  -> client/schema consolidation
  -> C++ client and transport extraction
  -> common protocol generation
  -> reference persistence extraction
  -> Dominium read-only vertical slice
  -> setup adapter consolidation
  -> process and permit qualification/extraction
  -> UNIVERSAL-CLASSIC-SHELL-CONTRACT-01
  -> typed presentation records, Launch Deck and theme manifest
  -> native GUI client bindings before GUI mutation
  -> component galleries on WinForms, AppKit and GTK
  -> one complete three-platform instance/operation vertical slice
  -> classic pages in dependency order
  -> setup/maintenance and recovery shells
  -> modern WinUI, SwiftUI and Qt shells after classic semantic proof
  -> setup-focused bootstrap compositions
  -> optional service/connectors/update mechanisms only after need is proven
```

Starting a later phase early is allowed only for isolated documents, schemas,
fixtures, or spike code that cannot create authority or become a competing
implementation. Every exception needs a recorded reason and disposal or
promotion criteria.

## Roadmap views

### Product roadmap

| Horizon | Product outcome | Principal work | Exit signal |
| --- | --- | --- | --- |
| Now | Preserve Play-evidence truth while capturing the target | Documentation, schemas, inventories, fixtures only | Active proof gate closes without mixed refactor work |
| Platform foundation | One qualified composition and client/protocol family | Composition contract, client/schema extraction, generated protocol, reference persistence, Dominium read-only slice | Factorio and Dominium consume product-neutral kernels and fixtures |
| Authority foundation | Safe setup/process/permit/operation behavior | Setup adapter, federated planning, process/session extraction, permit qualification, async operations | Exact plans and operations retain owners, effects, cancellation, and recovery |
| Classic shell foundation | One shared semantic shell contract | Classic shell contract, typed presentation, Launch Deck, theme/accessibility, direct native bindings | WinForms/AppKit/GTK galleries render equivalent fixtures |
| Classic playable slice | Immediate instance-centric launching experience | Instance list/detail, readiness, plan preview, safe fixture dispatch, Activity result | Complete three-platform vertical slice passes |
| Classic product alpha | Useful daily FacMan shell | Instances, Activity/Recovery, Installations, Updates, Mods, Accounts | Player workflows are task-oriented and semantically conformant |
| Classic product beta | Complete shell family and productization | Home/News, Settings/themes, setup/maintenance, standalone recovery, exact packages | Offline/accessibility/recovery/package/platform proof passes |
| Modern expansion | Independent modern layouts on proven semantics | WinUI, SwiftUI, Qt/Wayland | No new backend or authority semantics appear in a modern shell |
| Optional expansion | Only measured operational needs | Local service, connectors, dynamic providers, self-update, remote administration | Each independent need/trust gate passes |

### Critical path

```text
proof gate
  -> composition contract
  -> client/protocol extraction
  -> reference state + second product
  -> setup/process/permit/operation model
  -> classic shell + presentation contract
  -> direct native clients
  -> galleries
  -> three-platform vertical slice
  -> classic page expansion
  -> setup/recovery shells
  -> exact platform packages
  -> modern shells
```

### Safe parallel lanes

- Documentation, ADRs, ownership maps, terminology, and machine-readable
  dependency laws.
- Synthetic/Factorio/Dominium provider and presentation fixtures.
- Component-gallery fixture design and accessibility test cases.
- Platform dependency-closure inventories without release claims.
- Theme token/schema design without arbitrary theme execution.
- Safe Home/News feed contract and parser fixtures without enabling network
  access in the product.
- Package profile proposals, SBOM inputs, and reproducible toolchain manifests.

### Work that must not be parallelized ahead of its gate

- Real GUI mutation before direct client, operation ID, plan review, recovery,
  and authority conformance.
- One classic frontend expanding far beyond the shared vertical slice.
- Modern shells before classic semantics are stable.
- Persistent local service before a quantified restart/multi-client/background
  requirement.
- i386/i686/Windows-legacy release claims before full native closure proof.
- Dynamic providers, self-update, or remote control before their trust,
  signing, provenance, and recovery models.

# Detailed execution backlog

## Phase 0 — Freeze protection and architecture contract

### `GOV-PROOF-GATE-SEPARATION-01`

- Priority: P0.
- Repositories: `factorio-launcher`.
- Status: BLOCKED on active proof completion.
- [ ] Record the exact active safety gate and architecture-freeze status before
  every refactor task begins.
- [ ] Confirm the proposed task does not change Play verdict semantics, evidence
  identity, candidate qualification, project-state determinism, or active queue
  truth.
- [ ] Require a clean or explicitly classified worktree and isolate concurrent
  work with a task branch, separate worktree, or clean clone.
- [ ] Reject opportunistic root moves, broad renames, or workspace format
  rewrites during safety-gate work.
- Acceptance:
  - no mixed safety/refactor diff;
  - task dependencies and authority boundaries are explicit;
  - active proof evidence remains reproducible.

### `UNIVERSAL-PRODUCT-COMPOSITION-CONTRACT-01`

- Priority: P0/P1.
- Repositories: all four, document/contract/fixture-first.
- Prerequisite: active FacMan proof gate closed.
- Goal: define the smallest shared composition contract before moving code.
- [ ] Produce a universal product-composition diagram.
- [ ] Produce a repository and component ownership matrix with current owner,
  permanent owner, extraction gate, compatibility adapter, and expiration
  condition.
- [ ] Define capability-specific product-provider contracts.
- [ ] Define the typed `SetupPort` contract and its failure/cancellation/recovery
  semantics.
- [ ] Define the resource/state ownership graph.
- [ ] Propose operation/event protocol v1.
- [ ] Propose presentation view/action model v1.
- [ ] Propose composition manifest v1.
- [ ] Add a deterministic FacMan provider fixture.
- [ ] Add a deterministic Dominium provider fixture.
- [ ] Add a synthetic minimal product fixture so neither product defines the
  universal vocabulary.
- [ ] Update dependency-direction validators in report-only mode first.
- [ ] Map every current FacMan temporary incubator to a target, retained product
  slice, extraction gate, adapter, migration, and deletion gate.
- [ ] Record ABI, state-format, CLI, machine-JSON, and package compatibility
  promises.
- Explicit non-goals:
  - no repository merger;
  - no root-layout migration;
  - no daemon;
  - no dynamic plugin system;
  - no real setup or process authority promotion;
  - no GUI redesign implementation;
  - no workspace rewrite.
- Exit evidence:
  - contracts have positive/negative fixtures;
  - dependency laws are machine-readable;
  - Factorio and Dominium fixtures pass without product terms in universal
    schemas;
  - all open decisions have owners and deadlines.

## Phase 1 — Universal client and schema consolidation

### `ULK-CLIENT-SCHEMA-CONSOLIDATION-01`

- Priority: P1.
- Source: `factorio-launcher`.
- Destination: `universal-launcher`.
- [ ] Inventory FacMan result, command, transport, diagnostic, operation, and
  cancellation schemas.
- [ ] Classify each field as universal envelope, Factorio payload, FacMan
  presentation, compatibility alias, or obsolete.
- [ ] Define a normalized result envelope covering success, refusal,
  diagnostics, effects, operation identity, attempt identity, recovery, unknown
  outcome, payload type, and contract version.
- [ ] Define one transport request/response schema used by direct, process, and
  future local-service transports.
- [ ] Define payload size, nesting, text encoding, lifetime, redaction, and
  version-negotiation limits.
- [ ] Move generic schemas to ULK while retaining product schemas and generated
  compatibility projections in FacMan.
- [ ] Generate old FacMan-compatible envelopes during migration.
- [ ] Add cross-language fixtures for C/C++, .NET, Objective-C/Swift interop,
  and machine JSON.
- [ ] Add malformed, truncated, oversized, future-field, wrong-version,
  mismatched-operation, and invalid-UTF fixtures.
- [ ] Prove that a refusal never becomes generic success and an unknown outcome
  never becomes failure-with-no-effects.
- Exit:
  - one schema source drives all transport variants;
  - FacMan CLI/TUI behavior is unchanged;
  - no Factorio term enters the universal result envelope.

### `ULK-CPP-CLIENT-ADAPTER-EXTRACTION-01`

- Priority: P1.
- Source: `runtime/client`.
- Destination: ULK client SDK.
- Depends on: normalized client/result schemas.
- [ ] Extract the product-neutral client interface and typed response model.
- [ ] Extract direct transport.
- [ ] Extract bounded process transport.
- [ ] Preserve a daemon/local-service interface only as an inactive transport
  contract until a real service gate is accepted.
- [ ] Move shared cancellation, progress, operation-result, timeout, and
  diagnostic normalization.
- [ ] Keep FacMan response mapping, convenience commands, and product labels in
  FacMan.
- [ ] Provide compatibility adapters so existing FacMan call sites move one
  vertical slice at a time.
- [ ] Ensure clients do not know the CLI grammar or spawn path except inside the
  process fallback implementation.
- [ ] Prove equal normalized output through direct and process transports.
- [ ] Add leak, double-free, stale-view, cancellation-race, transport-crash, and
  response-lifetime tests.
- Exit:
  - FacMan CLI and TUI use the extracted client;
  - direct and process TCKs pass;
  - product handlers and visible behavior do not change.

### `ULK-TRANSPORT-CONFORMANCE-01`

- Priority: P1.
- [ ] Define a transport TCK runnable against every transport.
- [ ] Cover acceptance/refusal, typed payload, diagnostics, declared effects,
  operation IDs, progress order, prompts, cancellation before dispatch,
  cancellation after effects, recovery-required, and outcome-unknown.
- [ ] Verify bounded stdin/stdout behavior for process RPC.
- [ ] Verify child termination never falsely claims rollback or no effects.
- [ ] Verify redaction and no secret leakage in requests, logs, crash output, or
  diagnostics.
- [ ] Verify identical version negotiation and unsupported-version refusal.

## Phase 2 — Common protocol generation

### `UNIVERSAL-PROTOCOL-CONTRACTS-01`

- Priority: P1.
- Repositories: ULK and USK; logical shared package.
- [ ] Inventory duplicated `size`, Boolean, string-view, byte-view, export,
  calling-convention, error, request, and response definitions.
- [ ] Select one canonical schema/source representation and record why.
- [ ] Generate existing `ulk_*` and `usk_*` public structures without renaming
  symbols or changing binary layout.
- [ ] Generate static assertions for size, alignment, offsets, enum values,
  calling convention, and ownership/lifetime rules.
- [ ] Generate language-binding metadata and documentation.
- [ ] Generate diagnostics, effects, capabilities, prompts, confirmations,
  operation IDs, outcomes, and negotiation structures.
- [ ] Add compatibility readers for old versions and fail-closed refusal for
  unknown future versions.
- [ ] Add cross-kernel fixture equivalence tests.
- [ ] Add ABI diff reports to release validation.
- [ ] Define stewardship, review, and coordinated-release policy for the logical
  package.
- Decision gate:
  - keep the source in an existing universal repository, co-generated during
    the pinned superworkspace build, unless independent consumers prove a fourth
    repository is cheaper;
  - do not copy-edit two canonical schema trees.
- Exit:
  - ULK and USK pass identical primitive/envelope fixtures;
  - manual duplicated definitions are removed;
  - ABI compatibility evidence is accepted.

### `COMMAND-DESCRIPTOR-CODEGEN-01`

- Priority: P1.
- [ ] Make one command descriptor source generate structural request
  validation, safe decoders, response encoders, ABI metadata, CLI grammar,
  TUI/GUI field metadata, docs, and fixtures.
- [ ] Distinguish structural validation from handwritten semantic validation.
- [ ] Generate required/optional/default/repeatability/range/enum/path rules.
- [ ] Generate stable error paths so every frontend reports the same invalid
  field.
- [ ] Generate positive, boundary, and adversarial fixtures for every command.
- [ ] Shrink `command_dispatch.cpp` to registry lookup, admission, generated
  decode/encode, and module invocation.
- [ ] Eliminate broad manual command switches only after fixture parity.
- [ ] Keep policy, ownership, authority, compatibility, and domain behavior
  handwritten and reviewable.
- Acceptance:
  - no generated layer decides authority;
  - every command has machine-readable effects and refusal behavior;
  - dispatcher complexity and duplicate JSON validation measurably decline.

## Phase 3 — Reference persistence and launcher transactions

### `ULK-REFERENCE-PERSISTENCE-EXTRACTION-01`

- Priority: P1.
- Source: FacMan workspace/preferences/transaction incubators.
- Destination: ULK reference and persistence modules.
- [ ] Inventory every persisted record, version, owner, portability class,
  identity rule, migration, lock, journal, backup, and recovery path.
- [ ] Split generic bases from product extensions:
  - install references;
  - instance base specs and machine bindings;
  - profile bases;
  - artifact-set references;
  - account references only, never credentials;
  - launch-plan references and staleness;
  - generic launcher preferences;
  - launcher transaction and recovery journal.
- [ ] Keep Factorio mods, saves, worlds, accounts, content, launch extensions,
  and product diagnostics in FacMan.
- [ ] Define extension envelopes with product ID, provider version, schema
  version, digest, and migration/refusal rules.
- [ ] Preserve deterministic read precedence and visible effective-value
  provenance.
- [ ] Use the migration law:

```text
read old format
  -> validate and project into new owner model
  -> preserve product extension
  -> write only current format
  -> retain compatibility view where promised
  -> refuse unknown future versions
```

- [ ] Add dry-run migration, backup, journal, atomic replace, crash injection,
  rollback, and recovery fixtures.
- [ ] Prove concurrent readers/writers cannot silently lose state.
- [ ] Prove Universal Setup installed state is referenced, not copied and
  re-owned.
- [ ] Prove launcher transaction recovery cannot mutate installed application
  files.
- [ ] Add explicit storage quotas and bounded history retention.
- Exit:
  - old workspaces remain readable;
  - Factorio extensions round-trip unchanged;
  - no wholesale Factorio workspace move occurred;
  - compatibility and recovery tests pass.

### `CONFIGURATION-CLASSIFICATION-01`

- Priority: P1/P2.
- [ ] Preserve deterministic precedence:

```text
built-in product defaults
  < platform defaults
  < workspace policy
  < user preferences
  < instance profiles
  < explicit command request
```

- [ ] Classify each value as shell preference, launcher preference, workspace
  policy, product profile, machine binding, secret reference, or authority.
- [ ] Expose effective value and provenance to clients.
- [ ] Prevent imported data from widening process/setup/network/credential
  authority.
- [ ] Separate portable desired state from machine-local binding.
- [ ] Validate unknown keys, future versions, conflicting layers, invalid
  provenance, and non-portable exports.

## Phase 4 — Dominium second-consumer vertical slice

### `DOMINIUM-UNIVERSAL-COMPOSITION-SLICE-01`

- Priority: P1.
- Repository: `dominium` with pinned ULK/USK consumers.
- Purpose: qualify universality before extracting more FacMan incubators.
- Initial read-only workflow:

```text
product.inspect
installation/source.inspect
setup.plan.preview
environment/profile.inspect
launch.plan.preview
diagnostics
```

- [ ] Replace stub launcher initialization with a product composition that
  registers Dominium providers in ULK.
- [ ] Replace stub setup status/version ownership with a Dominium setup-recipe
  provider and generic USK client.
- [ ] Implement Dominium identity, package, environment/profile, content-pack,
  launch, session, diagnostic, and presentation interfaces only as needed by the
  slice.
- [ ] Keep all mutation and live process execution disabled in the first slice.
- [ ] Add deterministic Dominium source, installation, profile, launch-plan, and
  refusal fixtures.
- [ ] Run the same provider and protocol TCKs used by Factorio.
- [ ] Reject any universal field or command that encodes Factorio or Dominium
  terminology.
- [ ] Record every interface change demanded by the second consumer; prefer
  capability-specific interfaces over optional methods on one god object.
- Exit:
  - Factorio and Dominium are hosted by the same kernels;
  - neither product owns a competing setup/launcher kernel;
  - no universal contract contains product terminology;
  - the vertical slice is deterministic and read-only.

## Phase 5 — Setup adapter and federated planning

### `UNIVERSAL-SETUP-CLIENT-ADAPTER-01`

- Priority: P1.
- Source: FacMan per-call `SetupGateway`.
- Destination: generic setup client adapter, with product recipe providers.
- [ ] Replace per-call context construction with a long-lived, explicitly
  configured USK client/context.
- [ ] Generate setup request/response codecs.
- [ ] Use canonical ULK setup-handoff records for plan references,
  installed-state references, lifecycle status, and launch-plan staleness.
- [ ] Correlate product, setup, launcher, and presentation operation IDs.
- [ ] Carry exact plan identity, digest, source/target identity, provider/kernel
  revisions, expiry, and verification route.
- [ ] Preserve Factorio responsibility for source/layout interpretation and
  generic recipe production.
- [ ] Preserve USK responsibility for target ownership, mutation, rollback,
  recovery, and installed-state audit.
- [ ] Normalize cancellation, timeout, recovery-required, and unknown outcomes.
- [ ] Prevent a stale or mismatched setup result from refreshing an install
  reference.
- [ ] Add FacMan and Dominium adapter fixtures using different recipe providers.
- Exit:
  - both products use the same generic adapter;
  - no handwritten product gateway duplicates generic JSON envelopes;
  - setup handoff and staleness behavior are conformance-tested.

### `FEDERATED-PREPARATION-PLAN-01`

- Priority: P2.
- [ ] Define an `InstancePreparationPlan` that composes, without re-owning:
  - USK installation subplan;
  - product/content subplan;
  - profile/configuration subplan;
  - credential requirement;
  - typed host-environment subplan;
  - ULK launch-plan refresh.
- [ ] Require each subplan to retain owner, ID, digest, resources, effects,
  authority requirements, expiry, verification, and rollback/recovery
  disposition.
- [ ] Make the combined plan rank and explain work but never manufacture
  authority.
- [ ] Define partial completion, changed observations, supersession,
  cancellation, and recovery behavior.
- [ ] Present subplan ownership and risks clearly in every shell.

## Phase 6 — Process, session, and permit extraction

### `ULK-EXECUTION-FOUNDATION-EXTRACTION-01`

- Priority: P1.
- Prerequisite: second real provider qualifies the process abstractions.
- Source: `runtime/platform` and generic session infrastructure.
- Destination: ULK process/platform/session modules.
- [ ] Extract process specification without product command-line construction.
- [ ] Extract executable/process identity and pre-dispatch revalidation.
- [ ] Extract controlled working directory, environment, inherited handles/file
  descriptors, and no-shell launch.
- [ ] Extract OS containment:
  - Windows Job Object and explicit inherited-handle list;
  - POSIX process group/session and bounded signal escalation;
  - platform-specific capability reporting and refusal.
- [ ] Extract timeout, cancellation, process-tree termination, and kill outcome.
- [ ] Extract session journal, restart inspection, orphan reconciliation, and
  exit classification.
- [ ] Define stdout/stderr/log capture limits, encoding, redaction, truncation,
  and crash evidence.
- [ ] Preserve product launch-spec creation and exit interpretation in product
  providers.
- [ ] Add fake-process fixtures for start, normal exit, non-zero exit, hang,
  crash, child tree, identity swap, cancellation race, and supervisor restart.
- [ ] Prove no frontend or product provider can bypass the process port.
- Exit:
  - Factorio and Dominium consume the same process port;
  - platform conformance passes;
  - product semantics remain outside ULK.

### `ULK-PERMIT-KERNEL-QUALIFICATION-01`

- Priority: P1.
- Prerequisite: Dominium or another real provider plus reviewed authority model.
- [ ] Define one short-lived, single-purpose, non-transferable,
  replay-resistant operation permit.
- [ ] Bind permit to command, reviewed plan digest, exact resources, machine,
  user/session, product/provider/kernel revisions, declared effects, expiry, and
  attempt.
- [ ] Separate observation, policy decision, confirmation, permit issuance, and
  provider revalidation.
- [ ] Require owning authorities to revalidate independently at effect time.
- [ ] Keep harmless reads permit-free.
- [ ] Prevent providers, frontends, profiles, imported bundles, and configuration
  from issuing or widening permits.
- [ ] Define one-time consumption, crash-before-consume, crash-after-consume,
  retry, supersession, clock skew, and audit behavior.
- [ ] Add forgery, replay, resource-swap, stale-plan, revision-mismatch,
  wrong-user, wrong-machine, and over-broad-effect tests.
- [ ] Extract only after both product fixtures pass.

## Phase 7 — Classic shell contract, presentation model, and shell SDK

### `UNIVERSAL-CLASSIC-SHELL-CONTRACT-01`

- Priority: P1.
- Type: document, schema, fixture, and component-contract work before shell
  expansion.
- Repositories: `universal-launcher`, `factorio-launcher`, and `dominium`
  presentation fixtures.
- Goal: freeze the classic shell’s semantic information architecture without
  freezing toolkit widgets or pixel geometry.
- Accepted archetype decisions:

| Old launcher characteristic | Synthesized FacMan decision |
| --- | --- |
| Native window and controls | Retain |
| Top-level tab strip | Retain with overflow, keyboard navigation, and a complete View menu |
| Fixed profile selector | Replace with a persistent instance selector |
| Large Play button | Retain as a stateful primary action plus explicit launch-intent menu |
| Account status | Retain as logical account-reference and route availability |
| Central remote webpage | Replace with bounded, sanitized, cached native Home/News content |
| Profile editor | Replace with task-oriented Instance, Profile, Settings, and effective-value views |
| Launcher log/game output | Replace with structured Activity; keep Console as Advanced |
| One flat profile | Replace with installation, instance, profiles, modset lock, account references, saves, and launch intent |
| GUI-specific business rules | Prohibit |
| CLI process as permanent backend | Replace with direct client; retain bounded process RPC fallback |
| Pixel-identical cross-platform skin | Reject; preserve semantic parity and native rendering |

- [ ] Define the full launcher-shell information architecture.
- [ ] Define setup/maintenance-shell information architecture.
- [ ] Define constrained recovery-shell information architecture.
- [ ] Define Launch Deck, navigation, page, action, operation/event, theme,
  accessibility, product-pack, and frontend-capability contracts.
- [ ] Define narrow-window, overflow, keyboard, focus, restoration, and
  minimum-layout behavior.
- [ ] Provide semantic FacMan, Dominium, empty, offline, blocked, running,
  recovery-required, and unsupported fixtures.
- [ ] Record which presentation capabilities are required, optional, or
  unsupported per shell and platform lane.
- [ ] Keep command metadata as the advanced automation surface rather than the
  primary navigation generator.
- Explicit non-goals:
  - no GUI toolkit abstraction layer;
  - no shared widget tree;
  - no arbitrary skin scripting;
  - no remote HTML execution;
  - no GUI-side authority or compatibility calculation;
  - no implementation of real mutation.
- Exit:
  - WinForms, AppKit, and GTK can render the same fixture semantics;
  - shell shapes and product contributions are clearly separated;
  - every primary action maps to a command/action contract and structured
    refusal;
  - the classic contract can be consumed later by independently designed modern
    shells.

### Classic FacMan window and navigation contract

Target shell grammar:

```text
File | Edit | View | Instance | Tools | Help

Home | Updates | Installations | Mods | Instances | Accounts | Activity | Settings

                        current native task page

Instance selector | readiness | environment | account | primary action | intent menu

global status | offline/cache state | recovery state | active task count
```

- [ ] Use one resizable native window with ordinary platform chrome, menus,
  controls, lists, tables, forms, details, dialogs, and focus behavior.
- [ ] Treat eight top-level pages as the practical classic maximum.
- [ ] Use short localized labels.
- [ ] Provide horizontal scrolling or overflow at narrow widths.
- [ ] Provide `Ctrl+Tab`/platform-equivalent page navigation.
- [ ] Put every page in the View menu.
- [ ] Permit configurable visibility for advanced pages without hiding required
  recovery or security information.
- [ ] Persist the last selected page, except first-run, blocking recovery, or
  policy-directed startup.
- [ ] Default to Instances after onboarding; Home/News never stands between the
  player and Play.
- [ ] Maintain a usable minimum layout at a qualified old-laptop resolution,
  large text, and narrow aspect ratio.
- [ ] Collapse the Launch Deck only to a compact summary during modal
  plan-review or recovery work.
- [ ] Keep global operation/recovery status visible even when the selected page
  is not Activity.

### `LAUNCH-DECK-CONTRACT-01`

- Priority: P1.
- Purpose: make the selected instance and its safe next action persistent on
  every ordinary launcher page.
- [ ] Define:

```text
LaunchDeckSnapshot
  selected_instance
  instance_display_name
  installation_summary
  exact_game_version
  content_capabilities
  modset_summary
  account_summary
  save_summary
  readiness
  isolation_mode
  backup_status
  last_run_status
  active_session
  primary_action
  alternate_launch_intents
  blockers
  safe_next_actions
```

- [ ] Define state-to-action mapping:

| Instance state | Primary action | Required behavior |
| --- | --- | --- |
| Ready | **Play** | Open Factorio to main menu using an exact reviewed launch plan |
| Preparation available | **Make Ready** | Open a federated preparation plan; never apply silently |
| Blocked | **Review Problems** | Show evidence-backed blockers, refusals, and alternatives |
| Recovery required | **Recover** | Open the exact operation/transaction recovery view |
| Running | **Show Game** | Focus or reveal the running instance through a typed platform capability |
| Running with management | **Manage** | Open session controls; Stop remains separately explicit |
| Unsupported | Disabled action | Show structured refusal and safe alternatives |

- [ ] Expose explicit alternate launch intents:
  Open Main Menu, Continue Last Save, Load Save, Start New Game, Map Editor,
  Join Server, Start Server, Benchmark, and Developer Launch where supported.
- [ ] Keep Open Main Menu as the default.
- [ ] Never infer a changed launch target merely because a save was detected.
- [ ] Bind selected intent through readiness, launch plan, operation permit,
  process specification, session, and history.
- [ ] Model zero, one, and multiple running instances.
- [ ] Show stale readiness, active preparation, recovery, unavailable account,
  foreign installation, missing content, and snapshot-needed states.
- [ ] Define focus/show-game capability refusal when the OS/platform cannot
  provide it.
- [ ] Keep Stop, Kill, Delete, Repair, and other destructive actions out of the
  primary Play button.

### `UNIVERSAL-PRESENTATION-CONTRACT-01`

- Priority: P1.
- [ ] Replace opaque UI JSON with versioned schemas and typed bindings.
- Naming reconciliation:
  - `ProductShellModel` remains the conceptual aggregate;
  - `ShellSnapshot` is the serializable current-state root;
  - `*Descriptor` records stable metadata and action/form/navigation law;
  - `*Snapshot` records current derived state;
  - legacy `OperationView` maps to canonical `OperationSnapshot`;
  - JSON remains a transport/compatibility encoding, not the internal widget
    interface.
- [ ] Define the versioned family:
  - `ShellSnapshot`;
  - `NavigationDescriptor`;
  - `PageSnapshot`;
  - `ResourceCollection`;
  - `ResourceDetail`;
  - `FormDescriptor`;
  - `ActionDescriptor`;
  - `LaunchDeckSnapshot`;
  - `InstanceView` / `EnvironmentView`;
  - `ReadinessView`;
  - `EffectiveConfigurationView`;
  - `PlanReviewView`;
  - `OperationSnapshot`;
  - `SessionSnapshot`;
  - `RecoveryView`;
  - `DiagnosticView`;
  - `PromptDescriptor`;
  - `NotificationDescriptor`;
  - `SettingsView`;
  - `ThemeDescriptor`;
  - `AccessibilityDescriptor`;
  - `EmptyStateView`;
  - `CommandExplorerView`.
- [ ] Define `ActionDescriptor` fields:
  `action_id`, localization keys, command ID, resource binding, availability,
  refusal, risk, effects, confirmation policy, required capability, prominence,
  keyboard role, accessibility role, safe default, and destructive separation.
- [ ] Define `PlanReviewView` fields:
  owner, source, target, product/version, components, changes, risk, external
  effects, privilege, capacity, download/source ownership, executor,
  verification, rollback/recovery, restart, digest, expiry, and confirmation.
- [ ] Define `OperationSnapshot` fields:
  operation/attempt IDs, owner/provider, product/resource bindings, command,
  phase, status, progress, message, diagnostics, committed effects,
  cancellation, recovery, follow-up actions, and terminal outcome.
- [ ] Define `SessionSnapshot` for process identity, instance, launch intent,
  start/end, running state, logs, child containment, focus/manage/stop
  capabilities, and exit interpretation.
- [ ] Define stable identity, patch/update, pagination, empty, loading, stale,
  partial, offline, refused, error, and unknown-outcome semantics.
- [ ] Generate C, C++, .NET, and Objective-C-compatible bindings.
- [ ] Make accessibility metadata and localization keys contract requirements.
- [ ] Keep toolkit layout, platform menus, native controls, and interaction
  details platform-owned.

### `FACMAN-CLASSIC-PRESENTATION-PACK-01`

- Priority: P1/P2.
- Top-level pages:
  1. Home
  2. Updates
  3. Installations
  4. Mods
  5. Instances
  6. Accounts
  7. Activity
  8. Settings
- Reconcile the earlier larger FacMan navigation inventory as nested views:
  - Modpacks and locks live under Mods;
  - Profiles, presets, saves, worlds, backups, and snapshots live under the
    selected Instance and Activity where appropriate;
  - Recovery Center lives under Activity and contextual banners;
  - environment/host views live under Instances, Installations, Settings, or
    Advanced according to ownership;
  - the exhaustive command graph remains under Advanced.
- [ ] Register page IDs, ordering, localization, icons, route capabilities,
  default page, overflow priority, empty states, task actions, and help topics.
- [ ] Keep page modules capability-specific and lazily loaded.
- [ ] Never hardcode these Factorio/FacMan pages into the universal shell.

#### Home / News

- [ ] Show selected-instance summary and readiness/blocker banner.
- [ ] Show recent instances and recent operations.
- [ ] Show urgent FacMan notices and official Factorio announcements.
- [ ] Remain useful offline from validated cache.
- [ ] Make failure to load content non-blocking for startup, inspection, and
  Play.
- [ ] Implement safe content pipeline:

```text
network/source provider
  -> allowlisted official endpoint
  -> bounded fetch
  -> schema/content validation
  -> structured parsing or HTML sanitization
  -> cache with provenance, expiry, and size budget
  -> native text/image model
  -> external browser for full links
```

- [ ] Prefer structured feeds and native rendering.
- [ ] If a WebView fallback is retained, disable scripting where possible,
  expose no native bridge, share no credentials/cookies, allowlist navigation,
  disable downloads, bound content, and provide Open in Browser.
- [ ] Treat news/cache updates as non-authoritative presentation content.

#### Updates

- [ ] Present one unified review surface without pretending one authority owns
  every update class.
- [ ] Cover FacMan application, ULK/USK components, Factorio installations,
  DLC/content, mods, modpacks/locks, profiles/presets, compatibility metadata,
  and news/cache metadata.
- [ ] Preserve federated ownership:

| Update class | Resolver/planner | Applying authority |
| --- | --- | --- |
| FacMan application | FacMan release provider | Bootstrap/USK maintenance composition |
| Managed Factorio | Factorio source/recipe providers | Universal Setup |
| Steam-owned Factorio | Steam/provider observation | Steam/external owner; FacMan read-only |
| Mods | Factorio mod resolver | FacMan instance-content transaction |
| Modpack lock | FacMan modset resolver | FacMan workspace transaction |
| Profiles/presets | FacMan configuration service | FacMan workspace transaction |
| Host repair | Typed host provider | USK only when explicitly authorized |

- [ ] Make Review All Updates produce a federated plan of separately owned
  subplans.
- [ ] Show current/proposed versions, compatibility, source/download owner,
  changed resources, disk use, required snapshots, rollback/recovery, accounts,
  network, restart, privilege, and executor for every step.
- [ ] Never let the page manufacture setup, network, credential, or process
  authority.

#### Installations

- [ ] Name this page Installations in FacMan; reserve Library for a
  multi-product universal/reference shell.
- [ ] Provide a native table/list with name, version, platform/architecture,
  location, source, ownership, deployment type, DLC/content, health, dependent
  instances, and update state.
- [ ] Provide detail for identity/version, entrypoints, provenance, mutation
  authority, application closure, capabilities, data routing, verification,
  dependents, safe actions, and operation history.
- [ ] Define typed actions:
  Discover, Import Reference, Install Side-by-Side, Clone to Managed, Adopt,
  Verify, Repair, Move, Update, Downgrade, Detach, Archive Source, Uninstall,
  Open Location, and Export Diagnostics.
- [ ] Make Detach remove only the ULK reference.
- [ ] Make Uninstall available only for USK-owned installed state through an
  exact plan.
- [ ] Keep foreign installations read-only by default.
- [ ] Make Adopt a separately reviewed lifecycle with ownership proof.
- [ ] Prefer Clone to Managed over mutating a foreign installation.
- [ ] Avoid ambiguous Convert/Modify primary actions; resolve them into exact
  typed operations.

#### Mods

- [ ] Provide nested Browse, Local Library, Downloads, Installed by Instance,
  Modpacks, Modset Locks, Compatibility, and Cache/Cleanup views.
- [ ] Browse/search Mod Portal through a Factorio-specific source provider.
- [ ] Filter by Factorio version, DLC, category, and compatibility.
- [ ] Download exact versions into a content-addressed cache.
- [ ] Retain multiple artifact versions simultaneously.
- [ ] Inspect ZIP metadata safely without uncontrolled extraction.
- [ ] Detect duplicate, malformed, truncated, suspicious, path-traversing, or
  identity-mismatched archives.
- [ ] Resolve dependencies deterministically and explain unsatisfiable chains.
- [ ] Create portable `ModsetSpec` and exact version/hash `ModsetLock`.
- [ ] Compare locks and show compatibility effects.
- [ ] Snapshot the specific instance before active-modset changes where policy
  requires it.
- [ ] Journal, roll back, or recover interrupted apply.
- [ ] Delete only explicitly planned unreferenced cache content.
- [ ] Never swap one global mods directory; every apply targets an exact
  instance boundary.
- [ ] Keep Factorio dependency syntax out of ULK; ULK sees generic artifact-set
  identities and operation state.

#### Instances

- [ ] Make Instances the primary page after onboarding.
- [ ] Use instance list plus selected-instance details with Overview, Content,
  Profiles, Settings, Saves, Launch, History, and Advanced sections.
- [ ] Overview: effective installation/version/content/modpack/account/save,
  readiness, isolation, backup, and last run.
- [ ] Content: DLC, mods, spec, lock, missing artifacts, conflicts, and
  compatibility.
- [ ] Profiles: launch, graphics, audio, interface, multiplayer, server,
  new-game, and backup profiles as applicable.
- [ ] Settings: provenance-aware Factorio settings and per-instance overrides.
- [ ] Saves: saves/worlds/scenarios, import/export, compatibility, backup, and
  restore.
- [ ] Launch: intents, arguments, environment, isolation, plan, and preflight.
- [ ] History: runs, snapshots, changes, plans, operations, and recovery.
- [ ] Advanced: raw versioned records, command explorer, hashes, and diagnostics.
- [ ] Keep startup, runtime-global, runtime-per-user, game configuration,
  launcher-only, and one-run override settings distinct.
- [ ] Never flatten all settings into one property grid.
- [ ] Show effective-value provenance, compatibility, and authority limits.

#### Accounts

- [ ] Model Factorio account, Mod Portal account, platform account, player
  identity profile, multiplayer credential, and RCON credential as distinct
  domains.
- [ ] Add/authenticate, reauthenticate, revoke, inspect availability, assign
  reference, show consumers, and remove reference without deleting unrelated
  platform credentials.
- [ ] Select player identity independently of online credentials.
- [ ] Explain offline/unavailable states.
- [ ] Never imply FacMan can silently switch Steam identity or bypass platform
  authentication.
- [ ] Store only provider-scoped references in instance/workspace records.
- [ ] Use reviewed platform credential providers such as Windows Credential
  Manager, macOS Keychain, and Linux Secret Service/libsecret when available.
- [ ] Define explicit session-only or separately encrypted fallback only after
  a security review; never silently downgrade.
- [ ] Redact secrets from diagnostics, events, logs, and exports.

#### Activity, Console, diagnostics, and recovery

- [ ] Make Activity the top-level supervisor page.
- [ ] Provide Overview, Operations, Running Instances, Setup/Maintenance,
  Downloads, Logs, Console, Diagnostics, and Recovery views.
- [ ] Show all current work and attention states, including game sessions,
  downloads, verification, snapshots, prompts, and recovery-required.
- [ ] Define structured event fields:
  time, operation ID, attempt ID, product, instance, owner/provider, phase,
  severity, message, progress, effects, diagnostics, related resources, and
  available actions.
- [ ] Correlate events causally across command, plan, permit, setup transaction,
  launcher transaction, content apply, and process session.
- [ ] Console Advanced features:
  process/operation tabs, aggregate timeline, search/filter/severity,
  pause auto-scroll, copy/export, structured command palette, stdout/stderr
  separation, Factorio log interpretation, setup journal interpretation, and
  typed stdin only where explicitly supported.
- [ ] Do not expose an arbitrary operating-system shell by default.
- [ ] Define “intelligence” initially as deterministic correlation, recognized
  diagnostics, causal links, explanations, safe next actions, and
  rule-declared anomaly detection.
- [ ] Do not require an AI model and never let advisory analysis issue
  authority-bearing commands.
- [ ] Drive terminal rendering from completed/refused/cancelled/
  cancellation-requested-but-completed/recovery-required/outcome-unknown law.

#### Settings

- [ ] Separate global shell/launcher settings from selected-instance
  configuration.
- [ ] Provide General, Appearance, Workspaces/Storage, Updates,
  Downloads/Network, Accounts/Credentials, Backups/Retention, Notifications,
  Privacy/Diagnostics, Accessibility, Advanced, and About.
- [ ] Allow preferences, providers, update policy, storage roots, backup
  policy, narrower permissions, themes, and density.
- [ ] Do not allow settings to grant setup/process/network/credential authority,
  mark installations verified, mark instances ready, adopt foreign state,
  suppress required plan review, or turn unknown outcome into success.
- [ ] Show restart requirements and whether settings are user-local, machine,
  workspace, profile, or instance scoped.

### `UNIVERSAL-THEME-MANIFEST-01`

- Priority: P2.
- Goal: semantic, capability-aware theming without cross-platform widget
  recreation.
- [ ] Apply layers:

```text
operating-system appearance
  < FacMan product defaults
  < selected theme
  < accessibility constraints
  < platform adaptation
```

- [ ] Define semantic tokens:
  `surface.window`, `surface.content`, `surface.raised`,
  `surface.selection`, `text.primary`, `text.secondary`, `text.disabled`,
  `text.link`, `accent.primary`, `accent.secondary`, `status.ready`,
  `status.warning`, `status.blocked`, `status.error`, `status.running`,
  `status.recovery`, `border.normal`, `border.focus`, `border.destructive`,
  compact/normal/relaxed spacing, density, corner treatment, icon style,
  texture policy, and motion policy.
- [ ] Permit bounded accent colors, content backgrounds/textures, icons,
  density, spacing ranges, installed/system typography roles, table emphasis,
  contrast-preserving status colors, and capability-gated modern effects.
- [ ] Prohibit changes to window-management behavior, native title controls,
  focus visibility, accessibility roles, warning/destructive meaning, command
  availability, confirmation, security notices, executable scripts, downloaded
  fonts, unbounded animation, and unreachable layouts.
- [ ] Define package:

```text
theme-package/
  manifest.toml
  tokens.json
  icons/
  images/
  platform/
    winforms.json
    appkit.json
    gtk3.json
    winui.json
    swiftui.json
    qt6.json
```

- [ ] Require schema/theme ID/version, author/license, shell capabilities,
  hashes, byte/dimension budgets, fallback theme, contrast declaration, and
  optional bounded platform overrides.
- [ ] Retain a non-removable System Native theme.
- [ ] Add startup safe mode that ignores a broken user theme.
- [ ] Use restrained Factorio branding in headers, icons, instance art, empty
  states, bounded textures, and accents; never simulate another OS’s controls.

### `SHELL-SHAPE-SEPARATION-01`

- Priority: P1/P2.
- [ ] Full launcher shell:
  navigation pages, resource views, persistent Launch Deck, Activity, and
  recovery entrypoints.
- [ ] Setup/maintenance shell:

```text
Welcome
  -> Source
  -> Product and Version
  -> Components
  -> Destination
  -> Compatibility and Capacity
  -> Review Plan
  -> Confirm
  -> Apply
  -> Verify
  -> Complete or Recover
```

- [ ] Maintenance mode:
  select installation, choose Verify/Repair/Move/Modify/Uninstall, review exact
  plan, apply, and verify.
- [ ] Constrained recovery shell:
  interrupted operation, exact target/transaction, known effects, changed or
  foreign material, inspect/resume/rollback actions, and diagnostic export.
- [ ] Reuse source/target selectors, package/component summaries, effects
  tables, plan review, confirmation, progress, diagnostics, and recovery views.
- [ ] Do not reuse the eight-tab launcher navigation in setup or recovery.
- [ ] Make recovery shell independently launchable when the main product cannot
  start.

### `FRONTEND-TWO-PLANE-01`

- Priority: P2.
- Workflow plane:
  - [ ] `product.inspect`
  - [ ] `instance.list`
  - [ ] `instance.inspect`
  - [ ] `instance.readiness`
  - [ ] `instance.prepare.plan`
  - [ ] `instance.prepare.apply`
  - [ ] `instance.play`
  - [ ] `instance.export`
  - [ ] `instance.import.inspect`
  - [ ] `operation.inspect`
  - [ ] `operation.resume`
  - [ ] `operation.rollback`
  - [ ] `support.export`
- Expert plane:
  - [ ] retain the complete generated command graph for automation,
    diagnostics, development, provider inspection, compatibility aliases, and
    low-level administration;
  - [ ] expose it through CLI machine mode, TUI command explorer, GUI Advanced,
    and diagnostic tooling.
- [ ] Adapt friendly CLI output to the view/action model.
- [ ] Adapt TUI primary screens to tasks rather than a flat command list.
- [ ] Adapt WinForms, AppKit, and GTK primary navigation to task pages while
  retaining generated generic forms under Advanced.
- [ ] Prove semantic parity, not pixel identity.

### `PRODUCT-PRESENTATION-PACKS-01`

- Priority: P2.
- [ ] Define declarative pack fields for product identity, branding,
  localization, navigation/page registration, tasks, resource labels, icon
  roles, actions, help, settings, empty states, status summaries, and advanced
  categories.
- [ ] Keep arbitrary executable UI logic out of v1 packs.
- [ ] Allow complex trusted views through statically registered view providers
  only after demonstrated need.
- [ ] Make the eight-page FacMan classic pack one product projection, not a
  universal navigation requirement.
- [ ] Let Dominium contribute its own Play/Resume, Environments, Worlds,
  Content Packs, Profiles, Servers, Projects/Workbench, Installations,
  Operations, Recovery, and Advanced structure according to its product tasks.
- [ ] Keep exact product terminology, ordering, default route, and status
  summaries product-owned.

### `FRONTEND-CONFORMANCE-01`

- Priority: P2.
- For CLI, TUI, WinForms, AppKit, GTK, and later modern shells:
  - [ ] stable workflow coverage;
  - [ ] command explorer coverage;
  - [ ] structural and semantic argument errors;
  - [ ] refusal, risk, effects, and owner rendering;
  - [ ] progress and event order;
  - [ ] cancellation and cancellation-requested-but-completed;
  - [ ] recovery-required and outcome-unknown;
  - [ ] Launch Deck primary-action mapping;
  - [ ] keyboard navigation, focus, and accessibility roles;
  - [ ] long localization strings and right-to-left readiness assessment;
  - [ ] narrow, resized, low-resolution, high-DPI, large-font, and empty layouts;
  - [ ] offline, stale, loading, partial, and unavailable-capability behavior;
  - [ ] broken-theme recovery and System Native fallback;
  - [ ] safe Home/News content failure;
  - [ ] multiple running instances and global activity status.

## Phase 8 — Direct native clients, classic shell proof, and modern-shell gate

### `NATIVE-CLIENT-BINDINGS-01`

- Priority: P1/P2.
- Safety gate: complete before native GUIs expose real mutation, large
  downloads, backups, process supervision, interrupted operations, or recovery.
- [ ] Export a stable native client library with explicit memory/lifetime rules.
- [ ] Generate .NET Framework-compatible raw P/Invoke bindings and safe wrappers.
- [ ] Generate an Objective-C/Objective-C++ facade suitable for AppKit and Swift
  C interoperability.
- [ ] Provide direct C/C++ integration for GTK and Qt.
- [ ] Preserve process RPC as compatibility, bootstrap, diagnostic, and test
  fallback.
- [ ] Make direct transport the classic frontend default:

| Frontend | Primary | Fallback |
| --- | --- | --- |
| WinForms | P/Invoke to architecture-matched native client | Bounded process RPC |
| AppKit | Objective-C++ bridge to native C client | Bounded process RPC |
| GTK 3 | Direct C/C++ native client | Bounded process RPC |
| CLI | Direct native client | Optional accepted service |
| TUI | Direct native client | Optional accepted service |

- [ ] Remove requirements for users to browse for `facman.exe`.
- [ ] Ensure cancellation targets an operation ID, not only a transport process.
- [ ] Package architecture-matched native dependencies, ABI metadata, schemas,
  licenses, and composition identity.
- Exit:
  - WinForms, AppKit, and GTK inspect products/instances, preview plans, run
    diagnostics, dispatch safe fixture operations, and observe them without
    spawning the CLI;
  - process fallback remains bounded and conformance-tested;
  - no architecture-mismatched managed/native package is produced.

### `ASYNC-OPERATION-API-01`

- Priority: P1/P2.
- [ ] Retain synchronous execute for compatibility.
- [ ] Add:

```text
submit command -> accepted or refused -> operation ID
poll/subscribe -> started -> progress -> diagnostic -> prompt
               -> effect committed -> cancellation acknowledged
               -> completed | recovery required | outcome unknown
inspect | cancel | resume | recover | rollback
```

- [ ] Define event sequencing, replay cursor, deduplication, backpressure,
  disconnection, retention, and terminal-state laws.
- [ ] Define prompt ownership and frontend-disconnect behavior.
- [ ] Make effects already performed visible.
- [ ] Ensure timeout maps to inspection/recovery rather than assumed rollback.
- [ ] Add cancel/complete, restart/reconnect, duplicate submit, stale cursor,
  prompt abandonment, process-fallback death, and multiple-observer race tests.

### `CLASSIC-COMPONENT-GALLERY-01`

- Priority: P2.
- [ ] Build a development-only component gallery for WinForms, AppKit, and GTK.
- [ ] Render all:
  - primary/secondary/destructive/disabled action states;
  - Launch Deck readiness and session states;
  - plan-review ownership/effects/capacity/restart states;
  - operation phases and event timelines;
  - recovery-required and outcome-unknown;
  - empty, loading, stale, partial, error, and offline states;
  - forms, validation, tables, details, prompts, notifications, and diagnostics;
  - theme tokens and System Native fallback;
  - long translations, large text, high contrast, and keyboard focus.
- [ ] Capture semantic snapshots and platform screenshots without requiring
  pixel equality.
- [ ] Use the gallery to qualify toolkit capabilities before product page work.
- [ ] Keep it development-only and unable to gain product authority.

### `CLASSIC-THREE-PLATFORM-VERTICAL-SLICE-01`

- Priority: P1/P2.
- Implement equally in WinForms, AppKit, and GTK:

```text
open application
  -> list instances
  -> select instance
  -> render InstanceView and Launch Deck
  -> show readiness and blockers
  -> build launch-plan preview
  -> render Play or structured refusal
  -> dispatch a safe fixture operation
  -> observe progress in Activity
  -> render completion, recovery-required, or outcome-unknown
```

- [ ] Use identical semantic fixtures and normalized client operations.
- [ ] Prove keyboard-only operation and accessible state announcements.
- [ ] Prove narrow/minimum layout and offline startup.
- [ ] Prove direct transport primary and process fallback equivalence.
- [ ] Do not implement live Factorio mutation or launch authority in this slice.
- [ ] Prevent one platform from expanding substantially beyond the others until
  this slice passes.

### `CLASSIC-PAGE-EXPANSION-01`

- Priority: P2.
- Expand only after the vertical slice, in dependency order:

```text
1. Instances and Launch Deck
2. Activity and Recovery
3. Installations
4. Updates
5. Mods
6. Accounts
7. Home / News
8. Settings and themes
9. Setup and maintenance shell
```

- [ ] Require page-specific contract fixtures and conformance before the next
  page family becomes release-blocking.
- [ ] Implement visually distinctive Home/News late because it proves little of
  the core architecture.
- [ ] Keep real mutation disabled per page until direct client, operation,
  authority, plan-review, recovery, and platform proof are complete.

### `CLASSIC-SHELL-CROSSCUTTING-FEATURES-01`

- Priority: P2.
- [ ] First-run onboarding before normal shell.
- [ ] Recovery Center under Activity plus contextual banners and standalone
  recovery shell.
- [ ] Backups/snapshots under Instances and Activity.
- [ ] Downloads/cache under Mods, Updates, and Activity.
- [ ] Global search and command palette.
- [ ] Notifications with Activity history and accessibility announcements.
- [ ] Explicit offline mode and cached-capability reporting.
- [ ] Proxy/network policy under Settings.
- [ ] Privacy and any telemetry controls under Settings; no hidden collection.
- [ ] Support-bundle preview/export under Activity/Diagnostics.
- [ ] Import/export/rebinding under Instances and Installations.
- [ ] Multiple running-instance state in Launch Deck and Activity.
- [ ] Source acquisition under Updates/Installations, separate from USK apply.
- [ ] Privilege/restart requirements in plan review and Activity.
- [ ] Workspace migration on startup with Settings/Recovery inspection.
- [ ] Broken-theme startup recovery.
- [ ] Low-resource mode with bounded feeds, lazy pages, reduced motion, and
  release-profile budgets.

### `CLASSIC-PLATFORM-RELEASE-LANES-01`

- Priority: P2.
- Status: candidate profiles; not release claims until official requirements,
  toolchains, native dependency closure, packaging, and runtime fixtures are
  revalidated under a network-enabled reviewed task.
- General:
  - [ ] Pin exact OS floor, architecture, toolkit/runtime, compiler/SDK/sysroot,
    C/C++ runtime, package form, signing, dependency closure, and proof host.
  - [ ] Distinguish shell compilation from complete FacMan+ULK+USK runtime proof.
  - [ ] Never label an unsupported legacy OS as currently secure.

#### Windows classic candidates

```text
facman-winforms-win7-x86
facman-winforms-win7-x64
```

- [ ] Use architecture-specific managed packages; never `AnyCPU` when loading
  native FacMan/ULK/USK libraries.
- [ ] Qualify .NET Framework 4.8 and its bootstrap detection on Windows 7 SP1
  without silent network installation.
- [ ] Build the complete native closure for x86 and x64.
- [ ] Use standard Windows chrome, high contrast, and qualified DPI behavior
  with safe legacy fallback.
- [ ] Require no WebView2 or WinUI dependency in the classic core.
- [ ] Prove runtime behavior in Windows 7 VMs and newer supported Windows hosts.
- [ ] Label Windows 7 support as legacy compatibility, not a security-support
  promise.

#### macOS classic candidates

```text
facman-appkit-i386
  candidate target: macOS 10.9 through 10.14
  candidate toolchain: frozen Xcode 9.4-or-earlier class

facman-appkit-x86_64
  candidate target: macOS 10.9 or later after API/dependency qualification
```

- [ ] Treat lowering the current 10.13 compile target as a full dependency and
  runtime qualification, not a flag change.
- [ ] Freeze reproducible legacy compiler/SDK environment for any i386 claim.
- [ ] Audit every C++17 dependency and the complete FacMan/ULK/USK closure.
- [ ] Keep AppKit/Objective-C in the shell and Objective-C++ at the bridge.
- [ ] Guard post-10.9 APIs with qualified alternatives.
- [ ] Prove separate signing, packaging, launch, direct client, and operation
  fixtures.
- [ ] Keep i386 candidate-only until the complete native closure passes; a
  shell binary alone proves nothing about the backend.

#### Linux classic candidates

```text
facman-gtk3-x11-i686
facman-gtk3-x11-x86_64
```

- [ ] Adopt GTK 3/X11 as the intended classic Linux family and reserve Qt
  6/Wayland for the later modern family.
- [ ] Freeze reference distributions/sysroots, glibc, GLib, GTK 3 revision,
  compiler, C++ runtime, icon/desktop integration, package form, X11,
  sound/notification, and credential-provider behavior.
- [ ] Build independent i686 and x86_64 sysroots and packages.
- [ ] Prove complete runtime closure, not one Ubuntu build.
- [ ] Document unsupported display backends and distribution ranges precisely.

### `MODERN-SHELL-GATE-01`

- Priority: P3 / BLOCKED.
- Prerequisite: classic semantic contract, component galleries, three-platform
  vertical slice, direct client, and frontend conformance accepted.
- Intended families:
  - WinUI 3 with an exactly pinned supported Windows/SDK floor;
  - SwiftUI with an exactly pinned macOS/Xcode floor;
  - Qt 6/Wayland with exactly pinned distributions, architectures, Qt version,
    and QPA/runtime closure.
- [ ] Revalidate current primary vendor requirements before every release
  profile is accepted.
- [ ] Avoid indefinite labels such as Windows 10+, macOS 11+, or Linux.
- [ ] Permit sidebars, responsive cards, larger touch targets, animations, and
  compact layouts.
- [ ] Require the same command, action, operation, refusal, recovery,
  accessibility, and product-pack semantics.
- [ ] Do not copy the classic visual layout or share widget code.

## Phase 9 — Build, SDK packaging, bootstrap, and maintenance

### `UNIVERSAL-CMAKE-PACKAGE-EXPORT-01`

- Priority: P1/P2.
- Repositories: ULK and USK, consumed by products.
- [ ] Default apps/tests/conformance ON only when `PROJECT_IS_TOP_LEVEL`.
- [ ] In embedded mode build only requested components; avoid global cache,
  option, include-path, install-rule, and target pollution.
- [ ] Export namespaced targets:
  - `UniversalLauncher::Kernel`
  - `UniversalLauncher::Client`
  - `UniversalLauncher::Process`
  - `UniversalLauncher::Platform`
  - `UniversalSetup::Kernel`
  - `UniversalSetup::Lifecycle`
  - `UniversalSetup::Client`
- [ ] Install headers, static/shared libraries, package config/version files,
  ABI metadata, schema bundles, generated metadata, license data, SBOM
  components, and conformance fixtures.
- [ ] Preserve developer source mode with exact sibling Git pins.
- [ ] Add release package mode with exact SDK package hashes and versions.
- [ ] Prove identical public behavior and composition identity in both modes.
- [ ] Add relocation, spaces/Unicode path, read-only package root, empty `PATH`,
  missing component, wrong architecture, and mismatched-contract tests.

### `PRODUCT-COMPOSITION-MANIFEST-01`

- Priority: P2.
- [ ] Define:
  - composition ID and product ID;
  - ULK and USK versions/pins;
  - provider IDs, versions, and protocol ranges;
  - presentation pack;
  - platform adapters;
  - transports and shells;
  - package components and capabilities;
  - release profile;
  - contract-set digest.
- [ ] Generate build inputs, package manifests, About diagnostics,
  compatibility checks, source closure, SBOM, and runtime capability inspection
  from the same manifest.
- [ ] Sign/bind the manifest only when release signing is available.
- [ ] Fail closed on unknown provider, unsupported protocol, digest mismatch, or
  missing packaged component.

### `PRODUCT-BOOTSTRAP-COMPOSITIONS-01`

- Priority: P2.
- [ ] Create setup-only branded compositions:
  - FacMan Bootstrap;
  - Dominium Bootstrap.
- [ ] Statically compose Universal Setup, product package recipe provider,
  package verification, minimal setup presentation, recovery, and rollback.
- [ ] Keep source acquisition/network/credential authority separate from local
  deterministic apply.
- [ ] Support install, verify, repair, move, uninstall, rollback, and recovery
  according to USK capability.
- [ ] Record installed-state ownership and exact package provenance.
- [ ] Ensure a setup-focused shell is not a new setup engine.

### `SIGNED-SELF-UPDATE-01`

- Priority: P3 / BLOCKED.
- Prerequisites: package signing, provenance, bootstrap proof, rollback proof.
- [ ] Design a small external maintenance host because a running application
  cannot safely replace its loaded files.
- [ ] Bind updates to signed manifests, exact source/target versions, channels,
  downgrade policy, and rollback/recovery.
- [ ] Separate update discovery/download from deterministic local apply.
- [ ] Add interrupted update, revoked signature, disk-full, locked file,
  downgrade, and bootstrapper-version tests.
- [ ] Do not implement before signing key governance and recovery ownership are
  reviewed.

## Phase 10 — Optional service and extension expansion

### `LOCAL-SERVICE-NEED-GATE-01`

- Priority: P3 / EXPLORE.
- Add a persistent local service only if evidence shows one or more:
  - operations must survive frontend restart;
  - multiple clients must observe one operation;
  - downloads or process sessions are long-lived;
  - tray/background behavior is required;
  - explicit remote administration is introduced.
- [ ] Quantify the requirement and alternatives.
- [ ] Define service identity, authentication, per-user/system scope, lifecycle,
  upgrade, crash recovery, logs, and state ownership.
- [ ] Host the same product composition and handlers; do not create a second
  implementation.
- [ ] Reuse the same protocol and transport TCK.
- [ ] Threat-model privilege boundaries, local impersonation, replay, stale
  clients, denial of service, and secret exposure.

### `EXTENSION-LADDER-01`

- Priority: P2/P3.
- Level 1, preferred first:
  - [ ] declarative profiles, presets, setup recipes, templates, compatibility
    metadata, content descriptors, presentation resources, diagnostic rules.
- Level 2, principal v1 code model:
  - [ ] statically composed trusted providers for Factorio, Dominium, platform
    process, credentials, sources, and package interpretation.
- Level 3, after protocol proof:
  - [ ] out-of-process connectors for stores, repositories, mod services, remote
    servers, accounts, and third-party automation.
- Level 4, deferred:
  - [ ] signed dynamic providers only after version negotiation, crash
    containment, signing/provenance, authority proof, and at least two genuine
    external-provider demands.
- [ ] Require capability declarations and least-authority ports at every level.
- [ ] Never grant authority merely because a provider or pack is registered.

# Shared models to define and enforce

## Capability-specific provider family

Avoid a single giant `ProductProvider`. Define and version:

- `ProductIdentityProvider` — identity, versions, components, branding refs.
- `DiscoveryProvider` — product-specific installation and source discovery.
- `InstallationInterpreter` — layout, version, health, and capabilities.
- `SetupRecipeProvider` — source/target intent to generic setup recipe.
- `InstanceProvider` — product instance extensions and readiness contributions.
- `ArtifactProvider` — mods, packs, DLC/content/resources, reproducible locks.
- `ProfileProvider` — profile families and effective-value validation.
- `LaunchProvider` — exact launch specification without process start.
- `SessionInterpreter` — exit, logs, crash evidence, post-run interpretation.
- `DiagnosticsProvider` — product diagnostics, redaction, recovery guidance.
- `PresentationProvider` — localization, navigation, views, and actions.

For every provider:

- [ ] stable provider ID and version;
- [ ] supported protocol range;
- [ ] capability list and required host capabilities;
- [ ] schemas and migrations;
- [ ] command and presentation contributions;
- [ ] deterministic fixtures;
- [ ] required ports and prohibited authority;
- [ ] concurrency and lifetime rules;
- [ ] diagnostics/redaction behavior;
- [ ] compatibility and refusal behavior.

## Resource and state ownership graph

| Resource | Authoritative owner | Required rule |
| --- | --- | --- |
| `ProductDescriptor` | Product provider | Identity/capability description only |
| `InstalledState` | Universal Setup | Managed target, transaction, ownership, recovery |
| `InstallReference` | Universal Launcher | Reference to observed or USK-managed state |
| `InstanceSpecBase` | Universal Launcher | Portable generic runnable intent |
| Product instance extension | Product provider | Versioned Factorio/Dominium requirements |
| `InstanceBinding` | ULK plus provider contributions | Machine-local resolution |
| `Profile` | ULK base plus product schema | Declarative; never grants authority |
| `ArtifactSet` | ULK base plus product provider | Generic reference/lock plus product semantics |
| `LaunchPlan` | Universal Launcher | Exact runnable plan |
| `SetupPlan` | Universal Setup | Exact mutation plan |
| `Operation` | Owning authority, universally correlated | One logical operation with attempts |
| `Session` | Universal Launcher | Process lifecycle and exit classification |
| Product evidence | Product provider | Product interpretation, versioned and redacted |
| Credentials | OS/provider credential store | Logical references elsewhere |
| View model | Derived presentation projection | Never authoritative |

All workflows must distinguish:

```text
desired state        what the user requests
observed state       what discovery/verification found
authoritative state  what an authority owns and can recover
resolved state       what ULK can safely orchestrate now
presentation state   what a shell derives and displays
```

## Internal application modularity

Target structure:

```text
application/
  composition/
    product_host
    module_registry
    dependency_graph
  admission/
    capability_admission
    effect_admission
    permit_validation
  modules/
    products
    installations
    instances
    profiles
    artifacts
    launch
    operations
    recovery
    diagnostics
  ports/
    setup_authority
    process_supervisor
    reference_store
    credential_provider
    source_provider
    clock
    audit_sink
    platform_services
  generated/
    command_registry
    request_codecs
    response_codecs
    schema_index
```

For every module:

- [ ] declare owned commands;
- [ ] declare input/output schemas;
- [ ] declare required ports and prohibited ports;
- [ ] declare effects and risk;
- [ ] declare concurrency scope and lock ordering;
- [ ] declare persistent records and migrations;
- [ ] declare dependencies and detect cycles;
- [ ] declare readiness contributions;
- [ ] provide unit, contract, and adversarial fixtures;
- [ ] expose diagnostics without leaking secrets.

# Cross-cutting quality backlog

## Compatibility and migration

- [ ] Maintain an explicit compatibility ledger for C ABI, CLI human grammar,
  CLI machine JSON, transport envelopes, workspace records, setup state,
  composition manifests, package layout, and provider schemas.
- [ ] Define support windows and removal criteria for aliases/adapters.
- [ ] Read supported old state, write only current state, and refuse unknown
  future versions.
- [ ] Never silently reinterpret an old refusal, effect, permit, or outcome.
- [ ] Provide dry-run migration with exact changed-record preview.
- [ ] Back up before mutation and bind backup to source digest/version.
- [ ] Inject failure at every write/rename/fsync/journal stage.
- [ ] Prove idempotent recovery and classify irrecoverable cases.
- [ ] Add downgrade refusal or explicit downgrade migration; never assume
  forward-written data is backward compatible.
- [ ] Keep product extensions byte/semantic round-trippable when the universal
  base migrates.

## Security and authority

- [ ] Machine-check that installed application mutation exists only behind USK.
- [ ] Machine-check that process creation exists only behind ULK process ports.
- [ ] Scan persisted state, logs, fixtures, diagnostics, and support bundles for
  credentials and secret-like data.
- [ ] Require exact source and target identity for every setup plan.
- [ ] Require executable/provider/config identity at process dispatch.
- [ ] Refuse stale plans, mismatched revisions, expired permits, replayed
  attempts, and widened effects.
- [ ] Preserve refusal taxonomies across transports and shells.
- [ ] Redact paths/usernames/tokens according to product and support-export
  policy.
- [ ] Define audit event integrity, retention, privacy, and local export.
- [ ] Threat-model archive extraction, path traversal, symlinks/reparse points,
  hardlinks, case collisions, Unicode normalization, device paths, and
  time-of-check/time-of-use swaps.
- [ ] Keep network/source acquisition separate from deterministic apply.
- [ ] Do not infer that a signed package grants runtime process or credential
  authority.

## Reliability and operations

- [ ] Define operation state-machine invariants and terminal outcomes.
- [ ] Define retry safety per command and subplan.
- [ ] Correlate command, plan, permit, operation, attempt, setup transaction,
  launcher transaction, and process session IDs.
- [ ] Expose effects already performed and next safe action.
- [ ] Bound event/log/history storage and preserve terminal evidence.
- [ ] Reconcile orphaned operations and sessions after crash/restart.
- [ ] Make lock ordering and contention observable.
- [ ] Define disk-full, read-only, permission-denied, antivirus lock,
  disconnected volume, clock shift, and corrupt-state behavior.
- [ ] Avoid global mutable singletons; inject clock, filesystem, process,
  credential, and audit ports.
- [ ] Add deterministic clocks and IDs in fixtures.

## Performance and scalability

- [ ] Establish baselines before refactoring:
  startup, command discovery, instance list/inspect, readiness calculation,
  workspace load, plan generation, process launch overhead, GUI first view, and
  memory footprint.
- [ ] Set budgets per release profile and platform floor.
- [ ] Avoid reparsing full schemas/catalogues per command.
- [ ] Cache only derived data with explicit source digest, invalidation, and
  bounded retention.
- [ ] Paginate large collections and operation history.
- [ ] Stream bounded progress/log events with backpressure.
- [ ] Test thousands of instances/artifacts and large mod/save inventories using
  synthetic fixtures.
- [ ] Keep optimization subordinate to authority, determinism, and compatibility.

## Diagnostics and supportability

- [ ] Generate a runtime composition report with kernel/provider/protocol/package
  identities and digests.
- [ ] Explain why an action is unavailable and which observation/policy caused
  the refusal.
- [ ] Provide readiness contribution breakdown and effective-value provenance.
- [ ] Provide plan and operation timelines without secrets.
- [ ] Export bounded, redacted support bundles with a preview.
- [ ] Distinguish user-correctable, policy, compatibility, corruption,
  unavailable-capability, and internal-error diagnostics.
- [ ] Make every unknown outcome direct the user to inspect/recover rather than
  retry blindly.

## Accessibility, localization, and UX

- [ ] Treat localization keys, accessible names, roles, descriptions, keyboard
  actions, focus order, and live progress announcements as contract data.
- [ ] Avoid using color alone for readiness, refusal, risk, or progress.
- [ ] Test long strings, pluralization, date/number formats, right-to-left
  feasibility, high contrast, screen readers, 200%+ scaling, and reduced motion.
- [ ] Use product tasks such as Play, Make Ready, Recover, Clone, and Back Up as
  primary actions; keep exhaustive commands under Advanced.
- [ ] Present owner, effects, privileges, target/source, rollback, digest, and
  expiry before confirmation.
- [ ] Ensure closed or restarted frontends can rediscover non-terminal operations.
- [ ] Keep native platform interaction patterns while preserving semantic parity.

## Documentation and governance

- [ ] Keep the architecture verdict, ownership manifest, component map,
  composition contract, roadmap, and this backlog mutually consistent.
- [ ] Add a link checker and machine validation for referenced task IDs and
  component paths.
- [ ] Record accepted architecture decisions as ADRs with context, decision,
  consequences, alternatives, and reconsideration triggers.
- [ ] Add “last verified against” commit IDs for cross-repository claims.
- [ ] Regenerate diagrams/tables from machine-readable ownership and composition
  sources where practical.
- [ ] Require each extraction task to update source and destination docs in the
  same reviewed change set.
- [ ] Mark obsolete plans superseded instead of silently deleting history.
- [ ] Keep raw prompts/responses, secrets, and source AIDE memory out of target
  repositories.

# Conformance architecture

## Universal protocol TCK

- [ ] C ABI sizes, alignment, offsets, enums, calling convention, and symbol
  export.
- [ ] Memory ownership, null/empty, string/byte lifetime, and allocator rules.
- [ ] Request/response compatibility and unknown future fields.
- [ ] Error/refusal normalization.
- [ ] Diagnostics and redaction.
- [ ] Effects and capabilities.
- [ ] Operation identity, attempts, outcomes, cancellation, and recovery.
- [ ] Prompt/confirmation semantics.
- [ ] Version and transport negotiation.

## Transport TCK

For the same fixture through direct, process, and any accepted local service:

- [ ] normalized outcome;
- [ ] payload and payload type;
- [ ] refusal and diagnostics;
- [ ] effects;
- [ ] operation and attempt identity;
- [ ] progress/event ordering;
- [ ] cancellation and timeout classification;
- [ ] prompt behavior;
- [ ] recovery and unknown outcome;
- [ ] version negotiation and bounds.

## Provider TCK

Run against a synthetic fixture product, Factorio, and Dominium:

- [ ] product description;
- [ ] discovery;
- [ ] installation/source interpretation;
- [ ] setup recipe production;
- [ ] instance extension validation;
- [ ] artifact/profile contributions;
- [ ] launch-spec construction;
- [ ] session interpretation;
- [ ] diagnostics/redaction;
- [ ] presentation contributions;
- [ ] refusal and unavailable-capability behavior;
- [ ] no unauthorized port access.

## Authority fitness checks

Reject:

- [ ] installed-application mutation outside USK;
- [ ] process creation outside the ULK process provider;
- [ ] credentials in workspace or diagnostic records;
- [ ] product terms in universal contracts;
- [ ] GUI-owned discovery/compatibility/domain decisions;
- [ ] setup plans without exact source/target identity;
- [ ] success inferred after unknown outcome;
- [ ] stale plans or provider/kernel revision mismatch;
- [ ] product-provider permit issuance;
- [ ] configuration or imported data widening authority.

# Terminology migration

Use these terms in contracts, code, docs, and UX:

| Ambiguous user phrase | Preferred architecture term |
| --- | --- |
| Factorio program files | Installation |
| Independent playable Factorio setup | Instance |
| Reusable settings | Profile |
| Initial convenience template | Preset |
| Installing/repairing program files | Setup operation |
| Installer/maintenance application | Setup shell |
| Universal mutation authority | Universal Setup Kernel |

- [ ] Inventory ambiguous `setup` names.
- [ ] Classify each as installation, instance, profile, preset, operation, shell,
  kernel, recipe, plan, or installed state.
- [ ] Rename internal/new surfaces first.
- [ ] Preserve public compatibility aliases where required.
- [ ] Add glossary tooltips/help to product shells.
- [ ] Do not create “FacMan Setup engine” or “Factorio Setup engine”.

# Product compositions

## FacMan target composition

```text
Universal Launcher
+ Universal Setup adapter
+ Factorio identity/discovery
+ installation interpreter
+ setup recipe provider
+ instance provider
+ mod/modpack and save/world providers
+ account-reference provider
+ launch/session provider
+ diagnostics
+ FacMan presentation pack
+ platform/source/credential adapters
```

## Dominium target composition

```text
Universal Launcher
+ Universal Setup adapter
+ Dominium identity/package provider
+ environment/profile provider
+ pack/content provider
+ client/server launch provider
+ session interpreter
+ diagnostics
+ Dominium presentation pack
+ platform/source/credential adapters
```

## Named application responsibilities

| Application | Meaning |
| --- | --- |
| Universal Launcher | Reusable kernel, client SDK, reference shell, TCK |
| Universal Setup | Reusable mutation kernel, client, operator/reference tools, TCK |
| FacMan Launcher | Full ULK + USK + Factorio branded composition |
| FacMan Setup | Setup-focused shell over that composition or constrained bootstrap |
| Factorio Setup | User workflow, never another kernel |
| Dominium Launcher | Full ULK + USK + Dominium branded composition |
| Dominium Setup | Dominium setup shell using USK and recipe provider |
| Universal Launcher GUI | Developer/reference host for registered products |
| Universal Setup GUI | Generic plan/apply/recovery shell, normally product branded |

# Explorations requiring a decision before implementation

## `EXP-COMMON-PROTOCOL-HOME-01`

- Question: where should the logical common protocol source live before a
  separate repository is justified?
- Compare: ULK stewardship, USK stewardship, generated superworkspace input, or
  a vendored release artifact.
- Decide using: authority neutrality, release coordination, bootstrap,
  independent tests, package consumption, and copy-drift risk.
- Reconsider a fourth repository only after two real product consumers and
  independent package use.

## `EXP-LOCAL-SERVICE-01`

- Question: is a persistent local operation host required?
- Gather operation-duration, restart, multi-client, background-download, tray,
  and remote-control use cases.
- Prefer direct transport plus durable authority state unless quantified needs
  justify service lifecycle and attack surface.

## `EXP-LINUX-RELEASE-CLOSURE-01`

- Architecture direction is now split by shell family:
  - GTK 3/X11 for classic i686/x86_64 candidates;
  - Qt 6/Wayland for the later modern 64-bit line.
- Remaining question: which exact distributions/sysroots, glibc/GLib/GTK/Qt
  versions, compilers, C++ runtimes, desktop integrations, package formats, and
  credential/notification providers can be proven and maintained?
- Measure accessibility, package size, native integration, ABI/runtime closure,
  developer capacity, test automation, and old-machine performance.
- Record precise supported and unsupported matrices; never infer “Linux
  support” from one CI image.

## `EXP-LEGACY-PLATFORM-CLOSURE-01`

- Question: can the complete FacMan + ULK + USK dependency closure genuinely
  support Windows x86, macOS i386, and Linux i686 candidate lanes?
- Audit C++17, runtime libraries, archive/crypto/network dependencies, binding
  generation, packaging, signing, credential providers, and build hosts.
- Distinguish:
  - shell compile;
  - shell launch;
  - direct-client load;
  - read-only workflow;
  - fixture operation;
  - product launch;
  - setup mutation and recovery.
- Publish no legacy compatibility claim before the required proof level passes.

## `EXP-NEWS-CONTENT-SAFETY-01`

- Question: which official FacMan/Factorio feed formats can be consumed without
  embedding privileged active web content?
- Prefer a versioned structured feed with bounded images and external-browser
  links.
- Compare native structured rendering, strict sanitization, and an isolated
  scripting-disabled fallback only against offline cache, provenance,
  accessibility, localization, privacy, and parser attack surface.
- News remains optional and can never gate startup or Play.

## `EXP-THEME-CAPABILITY-01`

- Question: which semantic theme capabilities can every classic and modern
  toolkit implement accessibly?
- Define a mandatory portable core and optional capability flags.
- Measure contrast, focus, large-text behavior, asset budgets, startup cost,
  broken-package recovery, and platform-native adaptation.
- Reject executable themes, remote fonts, security-notice suppression, and
  layouts that make actions unreachable.

## `EXP-BINDING-GENERATION-01`

- Question: how should C ABI metadata generate safe .NET and Objective-C/Swift
  bindings?
- Compare custom generation, Clang-based generation, and thin handwritten safe
  facades over generated raw bindings.
- Require deterministic output, ABI diffing, lifetime safety, old-toolchain
  compatibility, and readable diagnostics.

## `EXP-PERSISTENCE-BACKEND-01`

- Question: what storage implementation best serves ULK reference state?
- Compare versioned files/directories and an embedded database only against
  atomicity, portability, inspection, corruption recovery, concurrency,
  migrations, backups, and package footprint.
- Do not merge ULK and USK state merely to share a storage technology.

## `EXP-CREDENTIAL-PORTS-01`

- Question: which credential-store baselines and reference semantics are needed
  per platform?
- Define unavailable-store refusal, headless behavior, migration, deletion,
  consent, redaction, and product-account binding without exposing secrets.

## `EXP-SOURCE-ACQUISITION-01`

- Question: which component owns network/download/entitlement/cache workflows?
- Preserve:

```text
Acquire = network + credentials + entitlement + download + cache
Apply   = deterministic local verification + target mutation
```

- Universal Setup must remain able to apply a verified local source offline.

## `EXP-DYNAMIC-PROVIDERS-01`

- Question: when are signed dynamic providers worth the risk?
- Required evidence: at least two external provider demands, protocol
  negotiation, capability/authority proof, crash containment, signing,
  provenance, upgrade/rollback, and support ownership.

## `EXP-REMOTE-ADMIN-01`

- Question: is remote control a product requirement?
- Treat as a new trust boundary with explicit authentication, authorization,
  transport security, audit, rate limits, user presence/consent, and recovery;
  never let local-service convenience imply remote authority.

# Risk register

| Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- |
| Refactor disrupts active Play evidence | High if mixed | Critical | Phase-0 hold, isolated tasks, no mixed diffs |
| Product-specific behavior leaks into ULK | Medium | High | Synthetic product + Dominium TCK, dependency fitness |
| USK and ULK authority collapse through shared protocol work | Medium | Critical | Share envelopes only; separate state, transactions, ports, and effects |
| Workspace migration loses Factorio extensions | Medium | Critical | Split base/extensions, round-trip fixtures, backup/journal/recovery |
| GUI cancellation misreports effect status | High today for process transport | High | Operation IDs, async model, inspect/recover, direct transport |
| Direct native bindings introduce ABI/lifetime defects | Medium | High | Generated metadata, safe wrappers, ABI/lifetime TCK |
| Dominium creates a second kernel before integration | Medium | High | Read-only provider slice before stub expansion |
| Common package becomes a coordination bottleneck | Medium | Medium/High | Logical package first; no fourth repo without evidence |
| Broad provider interface becomes a god object | Medium | High | Capability-specific interfaces and least-authority ports |
| Service/daemon creates hidden state model | Medium | High | Same composition/handlers/contracts; need gate and TCK |
| Build source/package modes drift | Medium | High | Identical composition fixtures and manifest digest |
| Compatibility adapters become permanent debt | High | Medium | Owner, expiry gate, usage metrics, removal criteria |
| Generated code decides semantic policy | Medium | Critical | Generate structure only; handwritten authority/domain decisions |
| Overloaded terminology causes competing engines | High | Medium | Glossary, inventory, aliases, naming validation |
| Too many GUI lanes dilute release proof | High | Medium | One release-blocking baseline per platform |
| Dynamic extensions expand attack surface | Medium | Critical | Defer to Level 4 evidence gate |
| Remote Home/News content executes in a privileged launcher | Medium without controls | Critical | Structured allowlisted feed, bounds, sanitization, native cache, external browser |
| Broken or hostile theme hides focus, warnings, or actions | Medium | High | Semantic tokens, strict budgets, accessibility override, System Native safe mode |
| Legacy shell compilation is mistaken for complete product support | High | High | Proof ladder for full native closure and exact compatibility labels |
| WinForms `AnyCPU` loads the wrong native architecture | High if shipped | High | Separate x86/x64 packages and architecture-matched dependency manifests |
| i386 backend cannot satisfy current C++ dependency floor | High until audited | High | Candidate-only lane, frozen toolchain, full closure proof |
| Generic “Linux” package fails outside one build image | High | High | Pinned sysroots, independent i686/x86_64 proof, explicit supported matrix |
| Classic shell contract becomes a cross-platform widget framework | Medium | High | Share descriptors/snapshots only; toolkit adapters own widgets and layout |
| Eight top-level pages hide secondary resources | Medium | Medium | Nested product routes, overflow/View menu, global search, Advanced explorer |
| GUI mutation begins while cancellation still kills RPC child | High if sequencing slips | Critical | Hard gate on direct client, operation IDs, recovery, and transport conformance |

# Milestone acceptance dashboard

## M0 — Architecture contract accepted

- [ ] Active proof gate closed.
- [ ] Composition, provider, SetupPort, resource, operation, presentation, and
  manifest proposals reviewed.
- [ ] Incubator migration map complete.
- [ ] Synthetic, Factorio, and Dominium fixtures exist.

## M1 — Client/protocol convergence

- [ ] FacMan CLI/TUI run through extracted ULK client.
- [ ] Direct/process transport semantic parity passes.
- [ ] ULK/USK common primitives are generated with ABI compatibility.
- [ ] Central dispatch structural JSON is generated.

## M2 — State and second-consumer proof

- [ ] Product-neutral reference persistence is ULK-owned.
- [ ] Old FacMan workspaces migrate/round-trip/recover.
- [ ] Dominium read-only vertical slice runs on the same kernels.
- [ ] Universal contracts remain product-neutral.

## M3 — Authority and operation convergence

- [ ] Generic setup adapter is shared by FacMan and Dominium.
- [ ] Process/session foundation is ULK-owned.
- [ ] Permit kernel is qualified by two products.
- [ ] Async operations safely express cancellation, recovery, and unknown
  outcome.

## M4 — Presentation and native-shell convergence

- [ ] Classic launcher, setup/maintenance, and recovery shell contracts are
  versioned and distinct.
- [ ] Shell/page/action/Launch Deck/theme/accessibility records and product
  presentation packs are versioned.
- [ ] Component galleries pass on WinForms, AppKit, and GTK.
- [ ] The complete instance/readiness/plan/fixture-operation/Activity vertical
  slice passes on all three classic shells.
- [ ] Friendly CLI, TUI, WinForms, AppKit, and GTK are semantically conformant.
- [ ] Native GUIs no longer require the CLI executable for primary operations.
- [ ] Home/News failure, broken-theme recovery, minimum layout, keyboard,
  accessibility, localization, and offline conformance pass.
- [ ] No real GUI mutation depends on killing a process-RPC child for
  cancellation.

## M5 — Reproducible product distribution

- [ ] ULK/USK export installable namespaced SDK packages.
- [ ] Source and package consumption modes are equivalent.
- [ ] Product composition manifest drives build/package/About/SBOM truth.
- [ ] FacMan and Dominium bootstrap compositions pass rollback/recovery proofs.
- [ ] Every classic platform package states an exact architecture, runtime,
  toolkit, toolchain/sysroot, dependency closure, and proven compatibility
  range.

## M6 — Evidence-driven expansion

- [ ] Local service, connectors, dynamic providers, self-update, or remote
  control start only after their individual need and trust gates pass.

# Definition of ready for every implementation task

- [ ] Permanent owner and current owner identified.
- [ ] Authority and non-authority boundaries stated.
- [ ] Dependencies and active proof gates cleared.
- [ ] Exact source paths and target API/package identified.
- [ ] Compatibility surfaces and support window identified.
- [ ] State/schema/ABI migrations identified.
- [ ] Positive, negative, adversarial, and recovery fixtures planned.
- [ ] Platform and frontend impact classified.
- [ ] Rollback/revert strategy documented.
- [ ] Validation commands and expected evidence named.
- [ ] Work isolated from unrelated dirty trees.

# Definition of done for every implementation task

- [ ] Code and contracts live in the permanent owner or an explicitly expiring
  adapter.
- [ ] No product semantics or unauthorized effects crossed the boundary.
- [ ] Source and destination repository docs and manifests agree.
- [ ] Compatibility adapters pass fixtures and have removal gates.
- [ ] Unit, integration, contract, conformance, migration, recovery, security,
  and relevant platform tests pass or warnings are explicitly reviewed.
- [ ] Generated outputs are reproducible and checked for drift.
- [ ] ABI/schema/package/composition identity reports are captured.
- [ ] Changed files, validation, remaining risks, changelog, and follow-up
  evidence exist.
- [ ] No unknown outcome is represented as success or no-effect failure.
- [ ] The next bounded task is clear; deferred work remains deferred.

# First actionable queue after the active proof gate

1. [ ] Start `UNIVERSAL-PRODUCT-COMPOSITION-CONTRACT-01` as a
   document/contract/fixture-only task.
2. [ ] Freeze and review the permanent/current ownership matrix.
3. [ ] Build the synthetic minimal product plus FacMan and Dominium provider
   fixtures.
4. [ ] Execute `ULK-CLIENT-SCHEMA-CONSOLIDATION-01`.
5. [ ] Execute `ULK-CPP-CLIENT-ADAPTER-EXTRACTION-01`.
6. [ ] Add direct/process transport conformance.
7. [ ] Execute common protocol generation with preserved `ulk_*`/`usk_*` ABI.
8. [ ] Generate command structural codecs and shrink the central dispatcher.
9. [ ] Execute `ULK-REFERENCE-PERSISTENCE-EXTRACTION-01`.
10. [ ] Deliver the Dominium read-only provider/composition vertical slice.
11. [ ] Consolidate the generic setup client and typed setup handoff.
12. [ ] Qualify and extract process/session foundations.
13. [ ] Qualify and extract the operation-permit kernel.
14. [ ] Freeze `UNIVERSAL-CLASSIC-SHELL-CONTRACT-01`, including distinct
    launcher, setup/maintenance, and recovery shell shapes.
15. [ ] Define typed presentation records, the persistent Launch Deck, the
    eight-page FacMan classic pack, semantic theme manifest, and accessibility
    contract.
16. [ ] Add WinForms P/Invoke, AppKit Objective-C++, and GTK direct native
    clients before exposing GUI mutation.
17. [ ] Build WinForms, AppKit, and GTK component galleries.
18. [ ] Complete the same instance/readiness/plan/safe-operation/Activity
    vertical slice on all three classic shells.
19. [ ] Expand classic pages in dependency order: Instances/Launch Deck,
    Activity/Recovery, Installations, Updates, Mods, Accounts, Home/News,
    Settings/themes, then setup/maintenance.
20. [ ] Move friendly CLI/TUI/native GUIs to the workflow plane while retaining
    the expert command explorer.
21. [ ] Qualify exact Windows x86/x64, macOS i386/x86_64, and Linux
    i686/x86_64 candidate dependency closures without overstating support.
22. [ ] Export namespaced ULK/USK SDK packages and prove source/package parity.
23. [ ] Generate product composition manifests.
24. [ ] Build setup-only product bootstrap compositions and independent recovery
    entrypoints.
25. [ ] Begin WinUI, SwiftUI, and Qt modern shells only after classic semantic
    conformance passes.
26. [ ] Re-evaluate optional service, connectors, dynamic providers, and signed
    self-update from measured product needs.

# Final target

```text
One protocol family.
One frontend-neutral client family.
One operation and recovery model.
One presentation and view/action model.
One product composition host pattern.
One pinned, reproducible composition per product.

Two separate universal authorities:
  Universal Launcher
  Universal Setup

Multiple product providers:
  Factorio
  Dominium
  future qualified products

Multiple native shells:
  CLI
  TUI

  Classic family:
    WinForms
    AppKit
    GTK 3 / X11

  Modern family after the shared model is proven:
    WinUI 3
    SwiftUI
    Qt 6 / Wayland

One classic FacMan visual grammar:
  native menus, tabs, controls and dialogs
  large task-oriented content page
  persistent selected-instance Launch Deck
  prominent safe primary action
  structured global Activity and recovery status

Three reusable but distinct application shapes:
  full launcher shell
  setup and maintenance shell
  constrained standalone recovery shell
```

FacMan proves product-neutral orchestration with a complex external game.
Dominium proves product-native installation, packaging, and lifecycle. Together
they prove that the universal contracts are genuinely universal without
creating a monolith. The classic FacMan line should feel as immediate as the old
Minecraft launcher while retaining the deeper installation, instance, content,
readiness, operation, recovery, portability, and authority model that a serious
product manager and launch supervisor requires.
