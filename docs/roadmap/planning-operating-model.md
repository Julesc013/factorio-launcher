---
document_id: FACMAN-PLANNING-OPERATING-MODEL
schema_version: "1.0"
status: governing-draft
created: 2026-07-28
last_reviewed: 2026-08-03
canonical_plan: release/index/plan.v1.toml
generated_dashboard: todo.md
generated_roadmap: docs/roadmap/current.md
archive: docs/roadmap/archive/facman-platform-refactor-plan-2026-07-28.md
---

# FacMan planning and execution operating model

## Verdict

FacMan does not need a larger backlog. It needs a smaller, self-validating
execution system that preserves the architectural depth of the backlog without
making every possible idea appear equally current.

The previous plan remains valuable as a planning corpus. It is intentionally
archived because its scale obscures the release cut-line, makes status decay
inevitable, and encourages metadata maintenance in place of product proof.
Current execution now flows through one machine-readable plan, one active
release, a bounded ready queue, explicit product claims, paired user journeys,
and evidence that can be invalidated when its assumptions change.

This operating model governs how the detailed corpus is converted into work. It
does not grant mutation authority, approve a release, supersede repository
invariants, or bypass the active AIDE task gate.

## 1. Outcomes the planning system must produce

The planning system is successful only when it makes the following questions
cheap and unambiguous:

1. What meaningful user outcome is the active release proving?
2. What is explicitly inside and outside that release?
3. Which product claims are being made, at what maturity, and with what
   evidence?
4. Which positive journey and paired failure journey prove those claims?
5. Which work unit is active, which work is actually ready, and what is blocked?
6. Which repository owns each permanent authority and contract?
7. Which platform and frontend qualifications exist independently of product
   capability?
8. Which evidence becomes stale when a contract, fixture, adapter, platform,
   package, or workflow changes?
9. Can the release and its proof be reconstructed from a clean checkout?
10. Which appealing ideas have been deliberately excluded, and what evidence
    would justify revisiting them?

If a document does not improve one of these answers, it should not become a new
planning authority.

## 2. Source-of-truth hierarchy

For convergence and release execution, conflicts are resolved in this order:

1. `release/index/plan.v1.toml` — canonical execution intent, dependency graph,
   cut line, gates, and status.
2. `release/index/component_ownership.v1.toml` — permanent repository and
   effect authority.
3. `release/index/workspace_lock.v1.toml` — exact consumed source identities
   and source-closure requirements.
4. `release/index/current_state.v1.toml` — compact reviewed-checkpoint roles and
   state, never a self-referential live-HEAD claim.
5. Durable architecture, accepted contracts, safety invariants, product
   journeys, and claim policy.
6. Out-of-tree live checkout observation — current local Git facts within the
   observer's explicit offline claim boundary.
7. A run-specific generated prompt and run profile.
8. Historical reports, archived plans, research notes, and prior prompts.

Each source is authoritative only for its declared field: a live observation
can correct a checkout fact without changing ownership, a provider pin, or a
gate. A lower source may explain a higher source, but it may not silently
override it. Generated views are disposable projections. A master prompt is a
run snapshot, not durable project law; model selection, reasoning effort,
delegation topology, and other agent settings belong in the generated profile
for that run. Historical reports and archives are discovery sources, not an
executable backlog.

## 3. Planning horizons

### Active

There is exactly one active release. Active work is limited by the global WIP
limit. Every active work unit has:

- one owner;
- one release and one epic;
- a bounded outcome;
- a repository set;
- dependencies;
- decision blockers;
- acceptance evidence;
- an S, M, or L size;
- an explicit status.

An active XL item is invalid. It must be split.

### Ready

The ready queue contains no more than ten work units. A ready item has satisfied
dependencies, no open decision blocker, an owner, a clear acceptance boundary,
and a size small enough to complete without becoming a hidden program.

Priority does not make an item ready. Desire does not make an item ready.

### Next

The canonical plan normally exposes only the next five work units beyond the
plan-system bootstrap. They may be planned rather than ready. This keeps the
dependency chain visible without pretending that unresolved work can start.

### Later

Later entries contain only:

- an identifier;
- a short outcome or subject;
- the reason it is not current;
- a concrete revisit trigger.

Later entries have no pseudo-precise task checklists or stale owners.

### Archive

The archive is unlimited and immutable except for corrective metadata. It may
contain deep architectural proposals, old checklists, rejected designs, and
research inventories. Extracting an idea from it requires a new bounded plan
node; archive presence never implies approval.

## 4. Work hierarchy and metadata placement

The hierarchy is:

```text
Release
└── Epic
    └── WorkUnit
        └── local checklist or implementation notes
```

Release-level metadata includes the user outcome, cut-line, non-goals, journeys,
claim set, platform/frontend cut, release risks, and exit evidence.

Epic-level metadata includes the cross-work-unit outcome, permanent ownership,
repository impact, and epic exit.

Work-unit metadata includes dependencies, decision blockers, priority, size,
owner, repository set, outcome, acceptance, and evidence.

Checklists describe the implementation of one work unit. They are not copied
into the release graph and do not become cross-release obligations.

Metadata must live at the highest level at which it is true and the lowest level
at which it is actionable. Repeating the same metadata on hundreds of leaf
tasks is a planning defect.

## 5. Capability model

Product capability, frontend parity, and platform qualification are orthogonal.
A release may advance on one axis without making an implicit promise on either
of the others.

### C0 — foundation

Purpose: prove safe composition without product mutation.

Includes:

- the canonical envelope and result semantics;
- a direct client on one platform;
- stable operation identities and truthful terminal outcomes;
- a synthetic fixture;
- composition and provenance manifests;
- generated status views and validation;
- read-only discovery and planning.

Excludes Play, setup mutation, network sources, accounts, news, themes,
cross-platform qualification, and modern-shell completion.

### C1 — playable instance

Purpose: give a user one safe, comprehensible path from an existing installation
to the Factorio main menu.

Includes:

- one existing-install class;
- one isolated instance;
- summary and readiness;
- launch preflight;
- an explicit Play action;
- process supervision and exit history;
- Activity and inspect/recover behavior;
- CLI and one reference GUI;
- one reference platform lane.

Excludes managed installation, updates, Mod Portal and other downloads,
credentials, arbitrary themes, multiple release GUIs, modern-shell completion,
and a stable public SDK.

### C1P — frontend parity

Purpose: prove semantic parity of the stable C1 workflows across selected
WinForms, AppKit, and GTK surfaces.

C1P is not extra C1 product scope. It is not platform qualification. A frontend
may render the same semantics while its operating-system lane remains
compatible or experimental.

### C2 — managed content

Purpose: make instance content deterministic, inspectable, reversible, and
reconstructable offline.

Includes snapshots, a local mod archive, cache policy, locks, deterministic
resolution, apply/verify/rollback, and offline reconstruction.

Public Mod Portal integration, account authentication, marketplace behavior,
and cloud sync remain deferred unless separately approved.

### C3 — managed installation

Purpose: add permit-backed installation ownership without mutating foreign
installations.

Includes source inspection and Universal Setup-backed plan/apply for
side-by-side install, verify, repair, move, uninstall, recovery, the setup shell,
and installation-reference refresh.

FacMan self-update and foreign-install mutation remain excluded.

### C4 — beta operations

Purpose: qualify networked and distributed operations for real users.

Includes accounts, network sources, Mod Portal access, product updates,
packaging, migrations, support export, signed release candidates, target
personas, and the reviewed classic-platform matrix.

### C5 — stable product

Purpose: make stable-channel promises supportable over time.

Includes stable workflows, signed packages and update metadata, key rotation and
revocation, rollback, migrations, support and security ownership, EOL policy,
accessibility, supply-chain and license assurance, and clean installation and
removal.

### Parallel incubators

Legacy Windows, macOS i386, Linux i686, modern shells, a Dominium second
consumer, a daemon, self-update, dynamic authority, remote operation, and cloud
features may be researched independently. They do not block the capability
ladder unless a release explicitly adopts them.

## 6. Product claims

A claim is a user- or release-visible assertion whose truth must survive
implementation changes. Claims are not test names and not marketing copy.

The initial claim set is:

| ID | Claim |
|---|---|
| FACMAN-CLAIM-001 | A foreign-owned installation is never modified by FacMan. |
| FACMAN-CLAIM-002 | The default Play journey reaches the main menu without loading a save. |
| FACMAN-CLAIM-003 | Mutable instance data is isolated from foreign-owned installation state. |
| FACMAN-CLAIM-004 | An interrupted authority-bearing operation never reports success without a proven terminal outcome. |
| FACMAN-CLAIM-005 | Any operation with possible effects maps to a specific inspect/recover path. |
| FACMAN-CLAIM-006 | Workspace export contains no credentials or unmarked machine-local paths. |
| FACMAN-CLAIM-007 | Stable workflows have semantic equivalence across supported frontends. |
| FACMAN-CLAIM-008 | A supported release can be reconstructed exactly from declared inputs. |
| FACMAN-CLAIM-009 | Malformed archives, themes, feeds, or other content cannot acquire setup, process, or credential authority. |
| FACMAN-CLAIM-010 | A blocked instance exposes a specific explanation and a safe action when one exists. |

Claim maturity is:

1. `declared` — scope, owner, and falsification condition exist.
2. `fixture` — a deterministic fixture demonstrates the claim.
3. `integration` — repository integration evidence exists.
4. `live-canary` — controlled real-product evidence exists.
5. `user-validated` — target users demonstrate comprehension or success.
6. `release-proven` — the release reconstruction proves the claim on its named
   lane.
7. `withdrawn` — the claim is no longer made and downstream surfaces have been
   corrected.

Maturity is monotonic only while its evidence remains valid. A contract change,
fixture change, adapter change, platform change, package change, or workflow
change may invalidate evidence and lower effective maturity.

The claim ledger is its own registry because claim lifecycle, evidence,
falsification, and release impact differ from work status.

## 7. Release-blocking journeys

Every release-blocking journey has a positive path and a paired failure path.
Each specification records:

- persona and relevant experience;
- starting state and ownership;
- platform lane and frontend;
- online or offline assumptions;
- maximum major decisions;
- claims exercised;
- positive terminal state;
- paired failure state;
- recovery or refusal behavior;
- time, interaction, resource, and accessibility budgets;
- required evidence;
- explicit exclusions.

### J01 — existing installation to Play

Positive: select a supported existing installation, create or select an isolated
instance, understand readiness, choose Play, and reach the main menu without
loading a save or modifying the installation.

Paired failure: the installation changes after readiness was established.
FacMan detects stale evidence, refuses the launch, explains the change, and
offers a safe rescan path.

### J02 — create an isolated instance

Positive: create instance-owned mutable state while preserving installation
ownership and provenance.

Paired failure: disk space is exhausted or the target changes during creation.
FacMan reports a recovery-required or safely refused result and preserves all
foreign-owned state.

### J03 — apply a locked mod set

Positive: resolve declared content deterministically and produce a verified
snapshot.

Paired failure: an archive is corrupt, resolution fails, or apply is
interrupted. The previous snapshot remains valid, the desired state is not
reported current, and a specific recovery path exists.

### J04 — recover an interrupted operation

Positive: inspect an interrupted operation and deterministically resume,
rollback, abandon, or prove no effects.

Paired failure: journal or staged state changed externally. Automatic recovery
refuses to guess, preserves evidence, and offers support export or an explicit
operator decision.

### J05 — reconstruct a portable workspace

Positive: reproduce a supported workspace from declared, permitted inputs.

Paired failure: a proprietary source, credential, or exact version is missing.
FacMan does not substitute silently; it reports the precise reconstruction gap
and preserves an inspectable partial result when safe.

Only J01 blocks C1. The remaining journeys become release-blocking at the
capability level that owns them.

## 8. Platform and frontend qualification

Platform lanes use four tiers:

- `supported` — release-blocking journeys, packaging, install/remove, recovery,
  and support ownership are proven.
- `compatible` — core workflows pass, but at least one supported-lane obligation
  is absent.
- `experimental` — bounded evidence exists, but the lane carries known
  qualification or operational gaps.
- `rejected` — the lane violates a hard prerequisite or has exceeded its kill
  criterion.

Promotion requires named journey evidence, claim evidence, reproducible build
and package identity, an owner, support posture, and no unresolved release
blocker.

Each experimental or legacy lane has a kill criterion such as unavailable
toolchains, non-reproducible packaging, unmaintainable dependencies, missing
process semantics, or evidence cost that exceeds its user value.

The classic Minecraft-launcher archetype is a design reference: familiar frame,
instance-centric navigation, strong primary action, compact status, Activity,
and platform-native restraint. It does not import the old launcher's backend,
authority model, update behavior, theming system, or security assumptions.

Classic-shell design and legacy-platform qualification remain separate
programs. Visual appeal cannot qualify an operating-system lane.

## 8A. Native interface and OEM+ appearance

Framework, design language, platform convention, and deployment capability are
separate planning dimensions. AppKit and SwiftUI both follow the Apple HIG for
macOS. WinForms follows Windows desktop conventions while WinUI 3 follows
current Fluent guidance. GTK 3 uses GTK 3 behavior and selected general GNOME
principles without pretending to be Libadwaita. GTK 3 is the initial primary
Linux GUI for `1.0`. TUI ordinary-product status and any Qt stack require a
separate admission decision; neither is an implicit release multiplier.

The interface architecture shares semantic page, action, result, refusal,
operation, recovery, and theme-capability records. It never shares toolkit
objects. Platform adapters own menu placement, Settings placement, button
ordering, literal shortcuts, control metrics, native dialogs, focus behavior,
and capability fallbacks.

Appearance has three tiers:

1. **System Native** — always available, compatibility/accessibility baseline,
   and theme-failure recovery target.
2. **OEM+** — supported bounded FacMan branding over native controls and
   behavior.
3. **Custom theme** — optional data-only semantic tokens and bounded assets,
   with no strict native-appearance claim and no ability to override
   accessibility or recovery.

Themes never contain code, scripts, raw CSS/QML/XAML/QSS, commands, remote
references, arbitrary layouts, or privileged capabilities. Themes, game mods,
presentation contributions, provider connectors, and first-party static
modules are separate trust classes.

C1 keeps WinForms as its supported reference GUI and may ship AppKit and GTK 3
as explicitly labelled previews against the same FacMan-local experimental
semantics. A preview artifact does not acquire a stable support or live Play
claim without its own evidence. Theme v1 follows stable classic evidence.
WinUI 3, SwiftUI, and Qt Quick/Kirigami remain optional modern projections
after the shared view/action/operation model and mandatory Qt Widgets profile
are stable.

Accessibility is a release property, not a theme feature. Supported shells
require keyboard, screen-reader, scaling, contrast, focus, status, motion, and
platform accessibility evidence. Closing a shell or transport never implies
that an authority-bearing operation was cancelled.

The complete framework mappings, shell profiles, semantic records, appearance
model, theme package, safe mode, trust classes, performance rules, recovery
rules, evidence, and staged implementation program are governed by
`docs/product/interface_design_system.md`.

## 9. Contract maturity

Cross-repository contract maturity is:

1. `experimental`
2. `fixture-qualified`
3. `consumer-qualified`
4. `second-consumer-qualified`
5. `release-candidate`
6. `stable`
7. `deprecated`
8. `removed`

One real consumer plus fixtures may justify consumer qualification. It does not
justify universal or stable claims. A second independent real consumer is
required for second-consumer qualification.

Dominium therefore does not block FacMan C1. It blocks only a claim that a
contract is already universal or stable across product families.

The contract registry is distinct from the plan and claim registries because
contract versions can outlive work units and can be consumed by releases with
different product maturity.

## 10. Cross-repository migration protocol

Every migration across `factorio-launcher`, `universal-launcher`, and
`universal-setup` follows this sequence:

1. Add a compatible producer surface while retaining the old surface. Mark the
   candidate experimental and add deterministic fixtures.
2. Produce an immutable candidate with ABI/schema identity, compatibility
   bounds, and a rollback pin.
3. Add consumer adapters that allow old and new paths to coexist.
4. Test supported old-producer/old-consumer, old/new, new/old, and new/new
   combinations.
5. Switch one consumer, preserving locks, reconstruction inputs, journeys, and
   adapters.
6. Switch remaining consumers independently.
7. Deprecate and remove the old surface only after the compatibility window,
   consumer inventory, archived evidence, and rollback policy permit it.

Each step must be independently mergeable and independently revertible.
No migration plan may require simultaneous merges to all implementation
repositories. Code moves only after permanent authority, dependency direction,
version ownership, compatibility, and rollback are explicit.

## 11. Decisions

A bounded decision records:

- identifier and question;
- owner;
- status;
- resolution work unit;
- latest useful decision point;
- evidence needed;
- default if time expires;
- de-scope or escalation path.

Valid terminal outcomes are accept, reject, defer with trigger, or supersede.
“Keep discussing” is not a decision state.

An item with an open blocking decision is not ready. A decision that can be
reversed cheaply should use the documented default and move forward. A decision
that changes authority, compatibility, security, user promises, or repository
ownership requires explicit review.

## 12. WIP and sizing

Default limits:

- one active release;
- one active architecture epic;
- one active work unit per repository by default, or two when their recorded
  path ownership is disjoint and one is a native frontend/package projection;
- three active work units total;
- ten ready work units;
- one large cross-repository migration.

An external gate consumes WIP capacity but is never a global mutex unless its
record explicitly says so. An `authority_only` gate must enumerate the exact
authority-bearing outcomes it blocks and the product work that remains
independent. Revalidation may therefore block route capability, route
promotion, and live acceptance while fixture journeys, native shells,
packaging, accessibility, refusal/recovery UI, and documentation proceed.

Sizes:

- `S`: no more than one focused working day;
- `M`: two to three focused working days;
- `L`: no more than one working week;
- `XL`: invalid for active or ready work and must be split.

A blocked item records owner, next review, fallback, and kill criterion. If it
cannot do so, it returns to Later rather than occupying WIP.

## 13. Definition of Ready

A work unit is ready only when:

- its release and epic are active or intentionally queued;
- its user or architectural outcome is explicit;
- its dependencies are complete;
- its decision blockers are resolved;
- its repository and permanent ownership are known;
- its changed surface is bounded;
- acceptance evidence and negative-path evidence are named;
- compatibility and rollback expectations are known;
- its size is S, M, or L;
- its addition does not violate the release cut-line or WIP limits.

## 14. Definition of Done

A work unit is done only when:

- the bounded outcome exists;
- acceptance and negative-path checks pass;
- evidence has immutable identity and provenance;
- changed contracts, adapters, fixtures, packages, and docs agree;
- compatibility and rollback claims are tested;
- generated artifacts are current;
- affected claims and evidence invalidation edges are updated;
- remaining risk and exclusions are explicit;
- a clean consumer can reproduce or inspect the result;
- obsolete code, flags, adapters, or docs scheduled for this unit are removed.

Code merged without these conditions is implementation progress, not completed
product proof.

## 15. Evidence and invalidation

Evidence identity includes:

- producer commit and repository;
- contract or schema identity;
- fixture identity;
- consumer adapter identity;
- platform and architecture;
- frontend where relevant;
- package/composition identity;
- journey and claim identifiers;
- command or procedure;
- result and terminal outcome;
- collection time;
- environment assumptions.

Evidence classes are:

- schema/contract validation;
- deterministic fixture;
- component;
- transport or ABI;
- producer-consumer compatibility;
- positive journey;
- paired failure journey;
- adversarial or fault-injection;
- live canary;
- user validation;
- clean release reconstruction.

The invalidation graph maps evidence to every input capable of changing its
meaning. When an input changes, affected evidence becomes stale until rerun or
explicitly requalified. A release requires a clean reconstruction; an old green
result on an unknown composition is not release evidence.

## 16. Test strategy

Reference-lane release evidence is the critical path. Broader matrices run only
where their result changes a support or compatibility claim.

The layered matrix is:

1. contract and schema validation;
2. component tests;
3. transport, ABI, and serialization tests;
4. producer-consumer compatibility pairs;
5. positive journeys;
6. paired failure journeys;
7. adversarial and interruption tests;
8. controlled live-product canaries;
9. target-user validation;
10. clean release reconstruction.

Pairwise coverage is preferred over combinatorial expansion. Old/old, old/new,
new/old, and new/new combinations are required only for supported migration
windows, not forever.

## 17. Budgets

Budgets begin as measured baselines. Thresholds become release gates only after
representative evidence exists.

Budget categories include:

- time to first useful screen;
- decisions required for the primary journey;
- time from Play to main menu;
- memory and process count;
- installation and workspace disk growth;
- network transferred and offline behavior;
- recovery time;
- support-bundle size and privacy;
- keyboard, screen-reader, contrast, scaling, and reduced-motion behavior;
- build, package, and evidence-reconstruction time.

Any exception has an owner, rationale, affected claim, expiry, and remediation
or de-scope action.

## 18. Research and spikes

Research progresses through:

1. terminology and feasibility;
2. a clickable or deterministic fixture;
3. a C1-relevant live spike;
4. specialist qualification only when evidence justifies investment.

Every spike states the decision it will inform, evidence it will collect, time
box, success condition, failure condition, and kill criterion. A spike does not
become production architecture by inertia.

## 19. Support, security, privacy, and EOL

Before beta, FacMan names owners for security intake, supported release lines,
incident response, signing and key custody, credential handling, privacy, and
support export.

Support artifacts default to data minimization. They mark machine-local paths,
redact or omit credentials and tokens, declare included logs and manifests, and
record user consent for any sensitive collection.

Stable releases define compatibility windows, migration support, rollback,
deprecation, and EOL. Removing a contract or platform lane requires consumer
inventory, user communication, archive evidence, and a last-supported path.

## 20. Complexity and change budgets

Before C1, do not add a new repository, daemon, dynamic authority mechanism,
marketplace, arbitrary theme engine, second persistence system, frontend-owned
domain service, stable public SDK, or broad abstraction without an accepted
decision proving it is necessary for a C1 claim.

Scope uses substitution: adding a release obligation removes or defers an
obligation of comparable cost unless the release owner explicitly increases the
budget.

An abstraction needs at least two concrete pressures or a hard boundary that
would otherwise be violated. Speculative reuse is not enough.

Every meaningful refactor names what it deletes, collapses, or makes
unnecessary. A redesign that only adds layers has not yet demonstrated
simplification.

## 21. Priority model

Priority combines:

- user value;
- safety or release risk reduced;
- dependency leverage;
- evidence unlocked;
- implementation and maintenance cost.

Bands are:

- `P0`: protects authority, truth, recovery, or the active release;
- `P1`: unlocks the active release or a necessary contract boundary;
- `P2`: completes the current capability after its critical path is proven;
- `P3`: evidence-driven expansion;
- `P4`: incubator or archive.

Only P0 through P2 may normally be active. Priority never overrides readiness,
WIP, ownership, or evidence requirements.

## 22. Progress measures

Progress is reported as:

- journeys passing positive and paired failure paths;
- claims by maturity and staleness;
- open release risks and blockers;
- work-unit lead time and WIP age;
- rework and escaped defects;
- target-user success and decision count;
- supported/compatible/experimental platform lanes;
- contracts by maturity;
- incubators promoted, rejected, or killed;
- false or withdrawn claims;
- clean-reconstruction success.

Lines of code, checklist count, document count, and nominal percent complete are
not primary progress measures.

## 23. Required registries and generated views

Four registries are justified:

1. Plan registry — release, epic, work-unit, decision, gate, risk, and horizon
   state.
2. Claim registry — product assertions, maturity, evidence, falsification, and
   release impact.
3. Compatibility registry — platform, architecture, frontend, packaging,
   support tier, and qualification evidence.
4. Contract-maturity registry — contract versions, consumers, compatibility,
   promotion evidence, deprecation, and removal.

Do not combine them merely to reduce file count; their lifecycles differ.

`todo.md` is generated and kept between 80 and 150 lines. It shows the active
release, external gate, active work, ready queue, decisions, risks, non-goals,
critical path, and commands.

`docs/roadmap/current.md` is generated as the expanded current-release view.
Optional agent context may be generated locally, but portable AIDE rules govern
what may be committed under `.aide/`.

The generator rejects:

- duplicate or unknown identifiers;
- missing owners;
- dependency cycles;
- active work outside the active release;
- ready work with incomplete dependencies or open decision blockers;
- completed work without evidence;
- WIP or ready-queue overflow;
- XL active/ready work;
- releases without a cut-line, non-goals, or exit;
- dependencies on archived or unknown work;
- missing archives or evidence paths;
- stale generated views.

Future validators must also connect the plan to claim, compatibility, and
contract registries so unsupported platform, stability, and product claims
cannot enter generated release surfaces.

## 24. Initial bounded sequence

The first sequence is intentionally smaller than the architectural corpus:

1. `PLAN-CANON-01` — archive the corpus, establish the canonical graph,
   generator, validator, and compact views.
2. `FACMAN-C1-CUTLINE-01` — ratify C1 inclusions, exclusions, and exit.
3. `FACMAN-JOURNEYS-01` — specify J01 positive and paired failure journeys.
4. `CLAIM-LEDGER-01` — create and connect the first product claims.
5. `PLATFORM-LANES-01` — define tiers and select the reference lane.
6. `CONTRACT-MATURITY-01` — define contract promotion and migration gates.

The following candidates remain Later until that sequence completes:

- `DIRECT-CLIENT-SPIKE-01`
- `OPERATION-DEATH-SPIKE-01`
- `INSTANCE-VIEW-MINIMUM-01`
- `C1-VERTICAL-SLICE-01`
- `C1-USER-VALIDATION-01`
- `C1-RELEASE-RECONSTRUCTION-01`
- `FACMAN-C1P`
- `THEME-V1-01`
- `PRESENTATION-CONTRIBUTIONS-01`
- `MODERN-PROJECTIONS-01`

## 25. Governing rules

1. One canonical plan graph.
2. One active release.
3. One explicit release cut-line.
4. Product capability, frontend parity, and platform qualification remain
   separate.
5. Every release claim has an owner and evidence maturity.
6. Every release-blocking journey has a paired failure journey.
7. Ready means dependencies and decisions are resolved.
8. WIP limits are constraints, not suggestions.
9. Generated views are never edited by hand.
10. Evidence can become stale and must have invalidation edges.
11. Cross-repository migrations are independently mergeable and revertible.
12. One consumer does not prove a universal contract.
13. New scope requires substitution, ownership, evidence, and a kill criterion.
14. Refactors must delete or collapse complexity, not merely relocate it.
15. Clean reconstruction, not accumulated local state, is the final release
    proof.
16. Interface semantics are portable; platform presentation and HIG
    conventions remain native.
17. System Native is always recoverable, and OEM+ branding never replaces
    native control behavior.
18. Themes are data-only and cannot acquire layout, command, network,
    filesystem, setup, process, or credential authority.
19. One gate blocks only its enumerated authority; an operator gate cannot
    freeze unrelated product work.

These rules are deliberately harder to satisfy than adding another task. That
is the point: FacMan should optimize for truthful user outcomes and recoverable
product evolution, not for the apparent completeness of its backlog.
