# Interaction platform execution programme v1

Status: ratified implementation and evolution programme subordinate to
`release/index/plan.v1.toml` and
`docs/architecture/unified_interaction_platform.v1.md`.

This document adds no Factorio execution, Universal Setup mutation, provider
adoption, daemon, network, plugin, signing, publication, or support authority.
It converts the ratified interaction architecture into an implementation,
qualification, compatibility, and de-scope programme.

## Executive decision

FacMan has one authoritative product and application core with several
replaceable interaction adapters:

```text
Factorio product and state law
             |
FacMan application and presentation services
             |
CommandSpec + FrontendSession + operation/event law
             |
+------------+---------------+----------------+----------------+
|            |               |                |                |
CLI JSON   human CLI    same-binary TUI   native GUIs   later local service
|            |               |                |                |
machines   humans         humans           humans        lifecycle hosting
and agents
```

The system is made portable and future-proof by keeping semantics above the
renderer and transport boundaries, not by forcing every frontend into one
widget toolkit or one process topology.

The implementation priority is:

```text
correct authority and truthful outcomes
→ recoverability and data safety
→ compatibility and accessibility
→ portability and maintainability
→ performance and usability
→ customization and optional intelligence
```

A lower-priority objective may not weaken a higher-priority one. In
particular, customization, agents, themes, plugins, convenience automation,
and visual polish cannot bypass ownership, confirmation, recovery, redaction,
provider, execution, or release law.

## Product audiences

| Audience | Primary surface | Required outcome |
| --- | --- | --- |
| Ordinary player | WinForms, later AppKit/GTK, task-oriented TUI | Understand the selected instance, readiness, one safe next action, session, Last Run, and recovery without knowing internal command IDs. |
| Power user/operator | Human CLI, TUI Advanced, GUI Advanced | Inspect exact identities, plans, effects, operations, evidence, and recovery while retaining concise normal workflows. |
| Script and CI author | CLI JSON | Receive deterministic schemas, bounded output, stable IDs, exit classes, idempotency, and no prompts or decoration. |
| Machine or agent client | CLI JSON or a separately admitted local-service protocol | Discover capabilities, explain/dry-run, act under policy, inspect operations, and stop at human-only gates. |
| Support maintainer | Doctor, support bundle, Activity/recovery views | Reconstruct what happened without exposing secrets or inventing terminal outcomes. |
| Contributor | Generated specifications, TCKs, fixtures, module boundaries | Add a capability once and prove every required projection without duplicating product policy. |

## Quality-attribute constitution

| Attribute | Design response | Required proof |
| --- | --- | --- |
| Portability | Keep product contracts free of terminal, toolkit, OS-handle, shell-string, and renderer types. | Cross-platform, transport, PTY/ConPTY, offline-build, and degraded-mode proof. |
| Modularity | Give command, application, presentation, session, renderer, shell, service, and extension layers one-way dependencies. | Dependency/link checks, component tests, and forbidden-edge checks. |
| Extensibility | Prefer stable data and contracts; keep later executable extensions out of process and capability-scoped. | Schema/TCK, permissions, isolation, revocation, and resource-budget proof. |
| Maintainability | Generate repetitive grammar, help, and forms; hand-design ordinary workflows; assign each semantic decision one owner. | Generated-diff, ownership, module-budget, and characterization checks. |
| Robustness | Every boundary validates size, depth, identity, revision, capability, effect, and timeout. | Malformed/corrupt corpus, fuzzing, short read/write, terminal resize, disconnect, restart, and resource-exhaustion tests. |
| Reliability | Give durable work operation/attempt identity, terminal truth, idempotent retry, inspection, and recovery. | Test cancellation, transport loss, process death, corrupt journals, unknown outcomes, and recovery. |
| Compatibility | Version boundaries independently; preserve stable IDs; negotiate additive schemas explicitly. | Test prior fixtures, aliases, migrations, downgrades, and incompatible-version refusal. |
| Customizability | Treat themes, keymaps, layouts, views, aliases, shortcuts, and localization as validated data. | Test invalid-data recovery, Safe Mode, contrast, conflicts, migration, and lack of authority. |
| Moddability | Separate Factorio content management from FacMan extensions; admit extensions only through capabilities. | Prove identity, permissions, isolation from authority, and deterministic disable/revoke behavior. |
| Featurefulness | Ordinary workflows are task-oriented; Advanced retains exhaustive generated command access. | Capability matrix, command/action census equality, mutation test preventing a silent projection gap. |
| Performance | Use scoped snapshots, bounded queues, virtualized lists, rebuildable caches, and measured budgets. | Benchmark startup, refresh, large catalogues, events, memory, and terminal rendering. |
| Security/privacy | Default to local/offline and least authority; redact exports and forbid ambient provider/plugin loading. | Threat models, credential, path/IPC, support-bundle, dependency, and SBOM proof. |
| Intelligence | Explain or rank authorized actions; keep deterministic operation complete without intelligence. | Prove provenance, no invention or bypass, offline fallback, and preserved confirmation. |
| Intuitiveness | Use progressive disclosure, stable vocabulary, one primary action, visible recovery, and native conventions. | Observe journeys and test terminology, keyboard, screen-reader, and failure friction. |
| Future-proofing | Preserve replaceable boundaries and migrations instead of predicting permanent technology. | Replacement TCKs, state migration, consumer canaries, deprecation, and retirement evidence. |

## Module topology

The target source topology is logical; directory changes occur only when the
implementation needs them and characterization evidence exists.

```text
runtime/
  application/       product use cases and orchestration
  presentation/      immutable scoped snapshots, actions, problems, explanations
  frontend/          FrontendSession, capability negotiation, operation observation
  client/            direct and bounded-process transports; later local service
  factorio/          Factorio domain, readiness, content, saves, launch intent
  workspace/         authoritative workspace records and migration

apps/
  terminal/
    cli/              machine and bounded human renderers
    tui/              controller, reducer, view models, renderer adapters
  gui/
    windows/winforms/
    macos/appkit/
    linux/gtk/
    linux/qt/         separately admitted
  service/            absent until admitted; same application authority

contracts/
  command/            CommandSpec and request/result law
  presentation/       snapshot/action/problem/event contracts
  transport/          direct/process/later-service compatibility
  preferences/        themes, keymaps, layouts, localization and migration
  extension/          future out-of-process manifest and contribution law
```

### Dependency direction

```text
renderers and native controls
        ↓
frontend controllers and local view state
        ↓
FrontendSession and typed presentation/action contracts
        ↓
FacMan application and presentation services
        ↓
FacMan domain + exact ULK/USK clients
        ↓
qualified providers
```

Reverse dependencies are forbidden. The application core never imports FTXUI,
WinForms, AppKit, GTK, Qt, terminal escape, named-pipe, socket, agent, or model
types.

### Language and ABI policy

- FacMan native implementation remains C++17 where required by the current
  core and candidate TUI renderer.
- Public/provider boundaries remain C-compatible where already established.
- Native GUI bindings may use C#, Objective-C/Objective-C++, C, or C++ behind
  generated/typed adapters; toolkit objects do not cross the semantic boundary.
- Internal C++ classes are not public compatibility contracts.
- A new language is admitted only for a named product outcome, package and
  toolchain closure, support owner, and migration/rollback plan.

## Contract stack

The minimum shared contract family is:

```text
CommandSpec                  command identity, fields, effects, risk, help
TransportRequest/Response    normative machine invocation and result envelope
PresentationQuery            scoped, freshness-aware product query
PresentationSnapshot         immutable product-facing state and actions
SemanticActionRequest        revision/idempotency-bound user intent
SemanticActionResult         operation/effect/problem/result projection
OperationEvent               ordered progress and terminal event record
TerminalCapabilities         bounded renderer capability observation
FrontendPreferences          versioned data-only interaction preferences
```

A future local-service protocol and future extension manifest are separate
version axes. Package version, command-catalog version, presentation version,
transport version, state version, provider ABI, service protocol, preference
schema, extension SPI, and support profile are never collapsed into one number.

### Compatibility law

- Stable IDs are never reused with new meaning.
- Additive optional fields are the default compatible evolution.
- A newly required field or changed behavior requires a new contract version.
- Clients negotiate supported ranges and refuse incompatibility explicitly.
- Human prose may improve; machine envelopes and stable command/action IDs
  receive compatibility fixtures and deprecation windows.
- Read old supported state, write the current state, and migrate through
  inspect → plan → backup → apply → verify → publish → recover/rollback.
- Unknown future authoritative state refuses; unknown safe extension data may
  be retained opaquely where its contract permits.

## State, concurrency, and operation law

Frontends contain only local interaction state:

```text
focus
selection context
filter/search
expanded panels
scroll position
transient form input
pending confirmation
```

They do not contain alternate readiness, ownership, action availability,
operation terminal state, Last Run, or recovery truth.

The presentation service emits scoped immutable snapshots with revision and
freshness. A semantic action binds the expected revision, request ID,
idempotency key, and—where durable—operation ID. A stale request refuses before
effects and returns a refresh action. Duplicate idempotency keys return the
original terminal result or a truthful in-progress/unknown state.

Renderer event loops never execute blocking backend work. Controllers submit
work through `FrontendSession`; completion and progress return as ordered events
that the UI reducer applies on its own event loop. Closing a frontend detaches
or requests cancellation according to the action contract; it never rewrites a
backend-owned outcome.

## CLI programme

### One executable and deterministic routing

```text
facman <command>          bounded human CLI
facman <command> --json   normative machine CLI
facman tui                interactive terminal UI
facman --rpc              bounded process transport host
```

Precedence is fixed:

1. JSON/RPC is noninteractive.
2. An explicit command is CLI.
3. `facman tui` is TUI.
4. Redirection never auto-enters a full-screen renderer.
5. Bare `facman` retains bounded help until a separate compatibility decision.

### Machine CLI

Machine mode produces exactly one documented terminal envelope on stdout, or
explicit NDJSON only when separately selected for event streaming. It never
prints prompts, progress decoration, colour, paging, localized prose, or cursor
control. Diagnostics go to stderr. Exit codes classify completion, invalid
invocation, refusal, unavailable capability, recovery required, outcome
unknown, and internal/transport failure; the structured result remains
authoritative.

### Human CLI

Human CLI provides concise task-oriented summaries, tables, plan/effect review,
problems, next actions, operation IDs, and recovery commands. It must not dump
raw backend JSON by default. Every ordinary diagnostic/support/recovery journey
is complete without opaque internal IDs where the current snapshot offers a
selection.

### Generated and hand-authored responsibilities

Generate:

```text
command tree and aliases
field grammar and validation metadata
help synopsis and completions
schema/documentation links
Advanced command discovery
```

Hand-author:

```text
ordinary workflow composition
human result renderers
explanations and remediation order
plan/effect review
support and recovery guidance
```

The current monolithic dispatcher is decomposed by capability without a
rewrite. Existing spellings and output receive characterization tests before
movement.

## TUI programme

### Ordinary and Advanced planes

Ordinary plane:

```text
Instances
Installations
Activity and Last Run
Settings / Support / About
contextual Launch Deck
```

Advanced plane:

```text
searchable generated command palette
typed forms from CommandSpec/request schemas
exact effect and confirmation review
raw normalized result/details
contract and diagnostic inspection
```

The ordinary plane is designed for tasks. Advanced guarantees exhaustive
command reach without turning 100+ commands into top-level navigation.

### Renderer boundary

The preferred full-screen candidate is FTXUI `v7.0.3`, verified as the latest
upstream release at programme ratification. Adoption still requires an exact
commit/source digest, offline-staged source, MIT notice, SBOM identity,
vulnerability review, compiler/target matrix, static package proof, terminal
TCK, and rollback path. Release builds never fetch it dynamically.

`TerminalRenderer` remains project-owned. A dependency-free linear renderer is
mandatory in the same binary for dumb terminals, redirected transcripts,
accessibility, Safe Mode, debugging, unsupported capabilities, and renderer
failure containment.

### Terminal capabilities

One bounded observation record covers:

```text
interactive input/output
terminal dimensions
Unicode width behavior
ASCII fallback
colour depth
mouse availability
VT input/output
alternate-screen support
accessibility/linear preference
```

Capability loss degrades presentation only. It cannot alter semantic actions,
authority, effects, or outcomes.

### Responsive UX

- Wide: navigation + list + detail + Launch Deck.
- Medium: list/detail with collapsible Launch Deck.
- Narrow: stacked page with tabs/sections.
- Tiny/incapable: linear guided mode.

Keyboard is complete; mouse is optional. Stable bindings include search or
command palette, tab/focus traversal, navigation arrows, Enter, Escape,
contextual help, refresh, and truthful cancellation request. No meaning depends
only on colour, animation, icons, border style, or mouse hover.

### Forms and confirmation

Typed forms support strings, multiline text, integers, booleans, enums,
multiselect, paths, sizes, durations, versions, digests, times, and secret
references. Dynamic choices come from the current snapshot; validation is
inline and revision-bound. Sensitive input is not echoed, logged, or placed on
command lines.

Effectful actions show exact targets, declared effects, authority, expected
revision, rollback/recovery, and confirmation law. Generic “Are you sure?” is
insufficient.

## Native GUI programme

WinForms, AppKit, and GTK consume the same snapshots/actions and remain native
to their platforms. Pixel identity is not required; equivalent task completion,
state, effects, refusals, operation truth, accessibility, and support evidence
are required.

Recommended ordinary information architecture:

```text
Home / status and first-run guidance
Instances
Library / installations and versions
Content / mods and modsets when admitted
Saves / snapshots when admitted
Activity / operations, sessions, Last Run, recovery
Settings / support / about
Advanced
persistent contextual Launch Deck
```

The Windows Technical Preview retains its narrower admitted pages. Additional
pages appear only when their capabilities enter the milestone.

### WinForms

WinForms is the first supported experiential shell. Migrate incrementally from
frontend command joins and view caches to typed presentation snapshots. Use
native controls, system fonts/colours, access keys, logical focus, UI Automation,
High Contrast, DPI scaling, long text/path handling, and a separate maintenance
host for self-replacement or later privileged setup.

### AppKit

AppKit follows the stable semantic product after Windows. Use native menus,
windows, sheets, preferences, keyboard conventions, VoiceOver, signing and
notarization. Do not port WinForms controls literally.

### GTK

GTK is the initial primary Linux GUI. Replace string-scanned JSON and
frontend-owned presentation/session state with typed models and the same
presentation/action seam. Qualify AT-SPI/Orca, themes, high contrast, font
scaling, X11/Wayland profiles, packaging and runtime floors independently.

### Qt and modern shells

Qt, WinUI, SwiftUI, web, and mobile are separately admitted projections. Qt
begins only after a user or platform outcome justifies carrying a second Linux
GUI and the semantic model is stable. Choose Qt Widgets or Qt Quick/Kirigami for
the first Qt train; do not implement both simultaneously.

## Optional local service

A daemon/service is not required to make the architecture asynchronous. It is
admitted only when evidence shows that:

- operations must survive all frontends;
- simultaneous clients need one event authority;
- server/acquisition supervision needs background lifetime; or
- repeated process startup is a measured reliability/performance problem.

If admitted, prefer:

```text
facman service run
facman service status
facman service stop
```

The service hosts the same application service and state stores. It adds only
connection, authentication, subscription, event delivery, backpressure,
restart, and abuse-control law. Default transport is per-user named pipe on
Windows and per-user Unix-domain socket on macOS/Linux. No TCP listener, remote
administration, elevation, implicit startup, new database authority, or broader
permissions follow automatically.

Direct and bounded-process transports remain supported for portable mode, Safe
Mode, diagnostics, and recovery.

## Machines and agents

Agents are structured machine clients, never UI scrapers. They:

- negotiate protocol and capabilities;
- bind an explicit workspace and policy envelope;
- use stable command/action IDs and schemas;
- explain and dry-run before mutation;
- provide expected revision and idempotency;
- inspect durable operation and recovery state;
- obey `requires_human_confirmation` with no machine bypass;
- keep secrets out of prompts, logs, errors, traces, and model context.

Optional intelligence may summarize state, explain blockers, compare plans, or
rank already available actions. It cannot invent an unregistered action,
weaken policy, make an unsupported capability appear available, silently apply
an effect, or become necessary for ordinary operation. Every intelligent result
carries provenance and degrades to deterministic non-AI behavior offline.

## Human experience programme

### Mental model

The ordinary vocabulary is:

```text
Installation  the Factorio program/version and its ownership
Instance      an isolated playable environment
Profile       configuration choices
Content       mods/modset associated with the instance
Save          optional world data
Readiness     whether the selected intent can safely run
Activity      current/recent operations and sessions
Recovery      explicit next action after interruption or uncertainty
```

Internal terms such as provider pin, permit, journal codec, contract-set digest,
or route admission remain behind Advanced/Support unless needed to explain a
specific blocker.

### Interaction principles

- Show the current state and ownership before offering effects.
- Prefer one contextual primary action and a small number of safe secondary
  actions.
- Use progressive disclosure: summary → explanation → evidence.
- Refusals state what is unavailable, why, whether effects occurred, and the
  safest next action.
- Loading, empty, stale, unavailable, refused, running, interrupted, unknown,
  corrupt, recovery, and completed are designed states.
- Close is not Cancel; Cancel is a request; terminal outcome is backend-owned.
- Safe Mode always retains system-native presentation, local inspection,
  diagnostics, and recovery while disabling optional customization/extensions.

### Human checkpoints

1. Non-authorizing prototype review after the shared snapshot/action seam and
   first terminal/WinForms journey: terminology, navigation, readiness,
   Launch Deck, recovery, keyboard and accessibility direction.
2. Exact Technical Preview candidate review: complete fake-process journey,
   accessibility, support bundle and package behavior.
3. Separately authorized real-Play route verdict.
4. Beta/RC/stable promotion with exact package identity.

Human feedback changes product semantics through reviewed contracts; frontends
do not accumulate hidden local fixes.

## Customization, modding, and extension

### Data-defined customization first

Admitted data-only packages/preferences may define:

```text
semantic colour tokens and system-native policy
keymaps with conflict detection
layout/density/column/sort/filter preferences
saved views
localization resources keyed by stable IDs
command aliases
user task shortcuts expanding only to existing typed actions
```

They are versioned, validated, importable/exportable, migratable, resettable,
and ignored by Safe Mode. They cannot add executable code, arbitrary paths,
network access, hidden actions, confirmation bypass, or authority.

Factorio mods/modsets are managed product content and are not FacMan code
plugins. Their acquisition, lock, application, compatibility, and rollback use
FacMan content law.

### Executable extensions later

A future out-of-process extension manifest declares:

```text
extension identity and publisher
contract and compatibility ranges
requested capabilities and permissions
commands/views/importers/exporters/recommendations contributed
resource and time budgets
network/credential needs
package signature and revocation status
```

The host grants a narrowed capability set. Extensions cannot directly open the
authoritative workspace store, ULK journal, USK state, credentials, providers,
or native UI objects. Failure is isolated; disable/revoke/uninstall is
deterministic. No arbitrary in-process native plugin ABI or public marketplace
is required for `1.0`.

## Portability and target profiles

Portability is evidence per exact target, not a universal claim inferred from
C/C++ or CMake.

Each target profile binds:

```text
OS and minimum supported version
architecture and ABI
compiler, SDK and standard library
runtime dependencies
filesystem and terminal assumptions
GUI toolkit/runtime
provider implementations and guarantees
package layout
qualification and support evidence
```

Primary modern profiles may use current features. Compatibility profiles use
separate builds/providers and may expose lower guarantees. Old Windows, macOS,
Linux and architectures do not force the modern product core to their lowest
language/runtime floor.

No runtime dependency download is required. Third-party source is exact,
digest-locked, licence/SBOM recorded, offline reconstructible, and replaceable
behind a project-owned boundary.

## Reliability, security, observability, and performance

### Reliability and fault model

Required faults include:

```text
malformed request/result/snapshot/preferences
stale revision and duplicate idempotency
cancel before dispatch and cancel/complete race
transport loss before and after possible dispatch
frontend close and crash
backend/service restart
corrupt or truncated journal/state/cache
outcome unknown and recovery required
disk full, permission change and path substitution
terminal resize/suspend/capability loss
```

Every fault has a truthful state, bounded resource behavior, and a safe next
action. Derived caches are disposable; authoritative records are journaled and
migratable.

### Security and privacy

- Least authority and explicit effect admission.
- No ambient DLL/shared-library/extension/provider discovery.
- No shell-string process model.
- No secret in arguments, logs, support bundles, generated help, or agent
  context.
- Redact before staging/export and verify the final bundle.
- Local-only default; network capability is separately admitted.
- Service/extension peers are authenticated and permission-bounded.
- Dependency identity, licences, vulnerabilities, provenance, and withdrawal
  are release inputs.

### Observability

Structured local records include request/operation/attempt IDs, stage, outcome,
provider identities, redacted diagnostics, log references, and recovery links.
Human views summarize them; machine clients receive structured records. No
telemetry is required by default. Any future telemetry requires explicit opt-in,
privacy schema, minimization, retention, export/delete controls, and support
purpose.

### Performance budgets

Establish reproducible reference profiles and budgets for:

```text
CLI cold start and JSON response
TUI first render and input latency
GUI time to usable state
scoped snapshot query and invalidation
large instance/mod/save lists
operation event throughput and backpressure
peak memory and output/log size
package relocation/startup
```

Performance optimizations cannot create alternate state authority. SQLite or a
resident service is admitted only after measured pressure and remains a
rebuildable index/lifecycle host unless separately promoted.

## Packaging and distribution

The Technical Preview console package contains one required `facman` executable
providing CLI JSON, human CLI, RPC host, full-screen TUI, and linear TUI. Build-
time static libraries remain internal. `facman-tui` is not a required package
artifact.

Native GUI packages contain the exact matching backend/provider/contract
identities. A later maintenance host may be a separate executable when
self-replacement or privilege boundaries require it. Every artifact derives
from the FacMan resolved release graph; native package adapters cannot redefine
components, paths, authority, compatibility, or support.

## Verification and TCK programme

### Shared semantic proof

- command registry = CLI discovery = TUI Advanced = documentation/agent
  discovery;
- identical semantic intent produces equivalent request/action records;
- snapshots, blockers, actions, effects, operation outcomes, Last Run and
  recovery normalize identically across required frontends;
- direct and bounded-process transports pass the same TCK;
- a fixture mutation proves a required command/action cannot land with a silent
  projection gap.

### Terminal proof

- headless reducer/view-model goldens at wide, medium, narrow and linear sizes;
- Windows ConPTY, macOS PTY and Linux PTY interaction;
- resize, Unicode width, ASCII, colour levels, `TERM=dumb`, `NO_COLOR`, redirected
  streams, EOF, suspend/resume and terminal restoration;
- keyboard-only, visible focus, non-colour meaning, reduced motion, linear
  transcript and screen-reader-oriented announcements;
- package proof that no second TUI executable is required.

### Native GUI proof

- semantic journey adapters plus toolkit-specific UI Automation/accessibility;
- keyboard, focus, screen-reader, high contrast/theme, scaling/font size, long
  text/path, minimum window and frontend-close faults;
- relocation, clean-machine, package dependency and support-profile evidence.

### Compatibility proof

Retain fixtures for previous command, result, presentation, state, preference,
keymap, theme, service and extension versions when they become public. Test
migration, downgrade/refusal, aliases, unknown additive fields, corrupt state,
and Safe Mode.

## Dependency-ordered delivery

At most one product WorkUnit, one provider WorkUnit, and one release/evidence
WorkUnit may be active; only one large migration is active across them.

### Current convergence

```text
Terminal foundation ───────────────┐
  FACMAN-TERMINAL-FRONTEND-FOUNDATION-01
  → FACMAN-SAME-BINARY-TUI-PARITY-01
                                   ├→ FACMAN-WINDOWS-EXISTING-INSTALL-JOURNEY-01
ULK promotion/adoption ────────────┘
  ULK exact consumer canary
  → ULK dev-to-main promotion
  → FACMAN-ULK-SESSION-PIN-ADOPTION-01

→ FACMAN-WINDOWS-TECHNICAL-PREVIEW-CANDIDATE-01
→ FACMAN-FIRST-ROUTE-VERSION-DECISION-01
→ FACMAN-CLEAN-WINDOWS-PROOF-HOST-01
→ separately authorized real-Play qualification
```

### Terminal foundation WorkUnit

`FACMAN-TERMINAL-FRONTEND-FOUNDATION-01` delivers:

- deterministic one-binary routing and compatibility;
- callable CLI/TUI hosts and modular renderers;
- common FrontendSession identity/revision/idempotency/cancellation behavior;
- normalized machine envelope and preserved human CLI compatibility;
- TerminalCapabilities and linear renderer;
- exact optional FTXUI admission record and offline package closure;
- direct/process TCK and package identity proof.

It does not implement the entire product TUI or change ULK pins.

### Same-binary TUI parity WorkUnit

`FACMAN-SAME-BINARY-TUI-PARITY-01` delivers:

- ordinary task shell and Launch Deck;
- generated Advanced palette and typed forms;
- reducer/view-model architecture;
- responsive/full-screen/linear/accessibility modes;
- parity, PTY/ConPTY, fault, compatibility and mutation TCK;
- removal of the second required package artifact.

### ULK adoption WorkUnit

After exact ULK main promotion,
`FACMAN-ULK-SESSION-PIN-ADOPTION-01`:

- updates all exact provider/package/ABI/contract identities atomically;
- retains rollback to the previous pin for one compatibility window;
- adapts ULK journal records into the FacMan presentation service;
- makes ULK the sole live Last Run authority;
- removes frontend cache authority or shows explicit unavailable state;
- changes no real Factorio execution authority.

### Windows existing-install journey

`FACMAN-WINDOWS-EXISTING-INSTALL-JOURNEY-01` proves:

```text
workspace
→ Doctor
→ discover existing installation
→ inspect ownership
→ register read-only
→ create/select isolated instance
→ readiness
→ Launch Deck
→ fake process session
→ authoritative Last Run
→ relaunch
→ outcome unknown/recovery
```

CLI JSON, same-binary TUI and WinForms use the same presentation/action records.
Human CLI covers bounded diagnostic/support/recovery surfaces.

### Technical Preview candidate

`FACMAN-WINDOWS-TECHNICAL-PREVIEW-CANDIDATE-01` closes:

```text
clean reconstruction
single console executable
WinForms package
exact providers/contracts/licences/SBOM/provenance
Unicode relocation and empty PATH
non-admin and long-path operation
keyboard/accessibility/scaling/high contrast
frontend-close and corrupt-journal faults
support-bundle redaction
reproducibility and clean removal
```

The result remains unsigned, internal, unpublished and unsupported. Real Play,
signing and public release are separate authority gates.

### Post-preview product trains

1. Qualify one exact real Play-to-menu route and human receipt.
2. Publish the separately authorized `0.1.0` train.
3. Complete USK streaming managed-install lifecycle and recovery.
4. Complete ordinary content, save, snapshot, update and removal journeys as
   separately admitted capabilities.
5. Qualify AppKit and GTK over the stable semantic product.
6. Stabilize required command/presentation/state/provider subsets, signing,
   migration, support and withdrawal for `1.0`.
7. Admit service, Qt, extensions, remote control or intelligent assistance only
   when a measured user outcome and support budget justify them.

## Execution checklist

### Immediate P0

- [ ] Run the exact FacMan consumer canary against the qualified ULK session
  subset and promote ULK through its normal `dev → main` procedure.
- [ ] Start `FACMAN-TERMINAL-FRONTEND-FOUNDATION-01` from current canonical
  `dev`; preserve CLI JSON and human CLI behavior before decomposition.
- [ ] Freeze the `CommandSpec`, `FrontendSession`, `TerminalCapabilities`,
  renderer, machine-envelope and compatibility characterization corpus.
- [ ] Decide and record the exact FTXUI source/digest or explicitly select only
  the linear renderer until admission passes.
- [ ] Make `facman tui` callable inside `facman` while keeping the unpublished
  migration executable out of release requirements.
- [ ] Promote and adopt ULK, then cut every live Last Run path to the ULK journal.

### Technical Preview P0

- [ ] Complete ordinary TUI pages and generated Advanced command coverage.
- [ ] Pass direct/process semantic and operation TCKs.
- [ ] Pass cross-platform headless and PTY/ConPTY terminal evidence.
- [ ] Complete the fake-process existing-install journey through CLI JSON, TUI
  and WinForms.
- [ ] Remove all live frontend Last Run authority and frontend policy joins from
  the preview path.
- [ ] Qualify the exact unsigned Windows package and support boundary.

### Post-preview P1

- [ ] Select and qualify the first real Factorio route on the clean proof host.
- [ ] Complete public-release authentication, human acceptance and withdrawal
  policy before publication.
- [ ] Implement USK streaming managed installation and recovery.
- [ ] Qualify AppKit and GTK ordinary journeys.
- [ ] Establish public compatibility fixtures and migration windows from the
  first distributed preview.

### Separate admission

- [ ] Local service/daemon.
- [ ] Qt, WinUI, SwiftUI, web or mobile shells.
- [ ] Out-of-process extension ecosystem and marketplace.
- [ ] Remote administration.
- [ ] Online accounts/acquisition/update services.
- [ ] Intelligent recommendation or assistant layer.
- [ ] Legacy operating-system and architecture profiles.

## Definitions of done

### Terminal foundation

- Existing CLI machine and human behavior is characterized and intentionally
  migrated.
- One binary routes all terminal modes deterministically.
- Common frontend session/operation behavior passes direct/process TCKs.
- Linear mode works without FTXUI.
- Optional renderer is exact, offline and replaceable.
- No new product authority or second state store exists.

### TUI parity

- Every required ordinary Technical Preview action is task-oriented.
- Every admitted command appears in Advanced automatically.
- Wide/narrow/linear/accessibility/fault journeys pass on all CI terminal hosts.
- No frontend computes readiness, Last Run, recovery or terminal outcomes.
- The package requires only `facman` for terminal behavior.

### Native GUI parity

- Required task journeys consume typed shared snapshots/actions.
- Toolkit-specific accessibility and packaging pass.
- No GUI parses human CLI output or owns fallback product truth.

### Service admission

- A measured lifecycle/multi-client problem exists.
- Direct/process fallback remains supported.
- Local peer security, backpressure, restart and abuse tests pass.
- The service has no independent policy or state authority.

### Agent/intelligence admission

- Deterministic non-agent operation is complete.
- Machine schema/policy/confirmation behavior is stable.
- Recommendations are provenance-bound and cannot invent or execute actions.
- Offline and no-model fallback passes every ordinary journey.

## De-scope and kill criteria

- If FTXUI fails portability, package, accessibility, security or maintenance
  admission, ship the project-owned linear renderer and reassess alternatives.
- If same-binary integration threatens stable CLI JSON, retain separate internal
  build targets while keeping one required package artifact and shared semantics.
- If full-screen terminal UX cannot meet accessibility requirements, linear mode
  remains a complete first-class ordinary path rather than a hidden fallback.
- If a service is not justified by measured operation lifetime or multi-client
  evidence, do not build it.
- If an extension cannot be isolated out of process with bounded capability,
  do not admit it.
- If intelligence cannot preserve deterministic, inspectable and offline
  operation, keep it outside the product.
- If a second GUI toolkit adds no supported platform/user outcome, defer it.

## Non-goals

This programme does not authorize or require:

```text
one cross-platform widget toolkit
one process topology for every target
one database as universal authority
ambient plugin/provider discovery
runtime dependency downloads
screen scraping by agents
hidden autonomous mutation
remote administration
mandatory service/daemon
mandatory Qt/WinUI/SwiftUI/web/mobile
legacy targets constraining the modern core
```

The long-term objective is not the greatest number of frontends or extension
points. It is the smallest set of stable boundaries that lets every supported
human and machine client express the same intent, observe the same truth,
perform the same bounded effects, and recover from the same failures.
