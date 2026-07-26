---
status: reviewed-planning-snapshot
work_unit: FACMAN-THREE-REPOSITORY-COMPLETION-REVIEW-01
reviewed_on: 2026-07-26
scope:
  - factorio-launcher
  - universal-launcher
  - universal-setup
observed_revisions:
  factorio-launcher: bf7dfd5520f9ff851507ff0b1bd1c208009f0b88
  universal-launcher: e78cc9f3a23f748130749ebe7241dbd1166f8b25
  universal-setup: 3f8489275077347c2918f3bb03614ec6431362ff
authority_promotion: false
runtime_change: false
factorio_execution: false
publication: false
canonical_truth:
  - release/index/project_status.v2.toml
  - release/index/component_ownership.v1.toml
  - release/index/workspace_lock.v1.toml
---

# FacMan Three-Repository Completion Report

**Report date:** 26 July 2026

**Repositories:** `factorio-launcher`, `universal-launcher`, `universal-setup`

**Scope:** Current state, completed work, missed work, remaining work, target architecture, and the dependency-ordered path to a trustworthy v1

**Authority:** This is a planning and status report. It does not grant process, setup, network, credential, signing, publication, or route-promotion authority.

---

## 1. Executive summary

The three-repository system is technically substantial, unusually safety-conscious, and architecturally recoverable. It is not finished.

The central result is:

```text
Universal Setup is the most mature kernel.
Universal Launcher is the smallest kernel and the immediate source-closure blocker.
FacMan has the broadest implementation and governance surface, but is not yet a playable product.
```

The project is currently between “technically credible platform” and “usable
product.” It already has strong contracts, deterministic planning, extensive
refusal semantics, transaction and evidence machinery, multi-platform build
proof, and a well-defined three-repository ownership boundary. It does not yet
have:

- a publicly reconstructible Universal Launcher source chain for the pinned extraction;
- fail-closed launch lifecycle decoding;
- unambiguous cancellation, timeout, and durable-operation outcomes;
- an accepted, exact, route-scoped real-Play capability;
- a player-first GUI and observed golden journey;
- a production managed-install lane;
- signed, published, updateable packages;
- a stable supported v1 workflow contract.

The optimal critical path is:

```text
publish ULK extraction
  -> prove remote pin reachability
  -> repair fail-open correctness and current-truth drift
  -> repair operation outcome semantics
  -> separate candidate evidence from product runtime
  -> rebuild all three repos from empty remote clones
  -> run the exact Windows instance-isolated Play revalidation
  -> promote only the exact accepted route after Pass
  -> ship an instance-first controlled alpha
  -> validate with real players
  -> resume managed-install and content preparation
  -> sign, publish, update, migrate, and recover
  -> stabilize the proven workflow subset as v1
```

The immediate next action remains `ULK-EXTRACTION-PUBLICATION-01`. Starting
another broad FacMan framework refactor before closing that source chain would
increase local divergence and delay the only path that can make the current
system reproducible.

---

## 2. What “finished” means

Software can always be extended. For this report, “finished” means a trustworthy v1 with a bounded, supportable product contract.

### 2.1 Controlled playable alpha

A controlled alpha is complete when:

- one exact Windows x64 standalone Factorio route opens the normal menu;
- the route has an accepted human `Pass` against a published three-repository source closure;
- only the accepted route is compiled or packaged as executable authority;
- the player can create or select an instance, inspect readiness, make it ready where allowed, Play, exit, inspect last-run state, and relaunch;
- no hidden Steam, foreign-install, network, credential, or setup authority is enabled;
- recovery and refusal paths are understandable without reading raw JSON;
- no required validation obligation is skipped.

### 2.2 Trusted public beta

A public beta is complete when:

- primary packages are signed and published;
- SBOM and provenance are bound to exact public revisions;
- installation, update, downgrade, migration, rollback, and uninstall are clean-machine proven;
- at least one production managed standalone lifecycle is accepted through Universal Setup;
- the primary Windows player journey is tested with real users;
- crash, cancellation, timeout, interrupted setup, and unknown-outcome recovery are coherent;
- the supported compatibility surface and support policy are explicit.

### 2.3 Trustworthy v1

Version 1 is complete when the product train ships:

- isolated instances;
- one or more explicitly supported Play routes;
- readiness and Make Ready;
- side-by-side supported standalone versions;
- profiles, presets, reproducible modpacks/modset locks, settings, and optional saves;
- snapshots, backups, export/import, diagnostics, recovery, and last-run state;
- a task-oriented GUI and complete advanced CLI;
- a production managed standalone lifecycle;
- signed primary packages and signed update metadata;
- versioned workspace migration and rollback;
- a stable workflow-contract subset;
- documented support boundaries and no silent mutation of Steam or foreign installations.

Everything beyond that—daemon, plugin marketplace, cloud sync, broad connector framework, AI mutation, every GUI toolkit, every Factorio intent, and every platform—is evidence-driven expansion, not a prerequisite for v1.

---

## 3. Live repository snapshot

### 3.1 FacMan / `factorio-launcher`

| Field | Current state |
| --- | --- |
| Local observation path | `D:\Projects\Factorio\factorio-launcher` |
| Branch | `dev` |
| Revision | `bf7dfd5520f9ff851507ff0b1bd1c208009f0b88` |
| Upstream | clean and aligned with `origin/dev` |
| Canonical main | `f9670ed6afedcbf9b5c297e8ead478cd3aeea4c5` |
| Dev divergence | 15 commits ahead of `origin/main`, 0 behind |
| Product version | `0.1.0-dev` |
| Phase | `targeted_extraction_complete` |
| Playability | `not_yet_playable` |
| Workflow | `advanced_command_surface_only` |
| Current execution | unavailable |
| Release | unsigned and unpublished |
| Public ABI | experimental subset |
| User validation | not started |

The current `dev` tree is clean. The project reports 125 commands, 295 schemas, and 242 refusal codes for its current integrated development state. Those counts demonstrate surface size, not readiness.

The exact Windows instance-isolated candidate branch is already an ancestor of
`dev`, despite `release/index/project_status.v2.toml` still describing it as
`implementation_complete_pending_reviewed_integration`. The real remaining
gate is post-extraction revalidation and human verdict, not integration of the
candidate source.

### 3.2 Universal Launcher / `universal-launcher`

| Field | Current state |
| --- | --- |
| Local observation path | `D:\Projects\Universal\universal-launcher` |
| Branch | `task/reference-model-extraction-01` |
| Revision | `e78cc9f3a23f748130749ebe7241dbd1166f8b25` |
| Worktree | clean |
| Public remote-tracking main | `7bd4425f0c35414f738159b45d8bec42edf70235` |
| Local branch divergence | 2 commits ahead, 0 behind |
| Unpublished commit 1 | `78c27da0de2cefc40ff0f9654ab46f777a1357ae` — client/transport ABI |
| Unpublished commit 2 | `e78cc9f3a23f748130749ebe7241dbd1166f8b25` — reference model |
| Current validation | strict pass, 7 Python tests pass, 4 native Release tests pass |
| Release | unsigned and unpublished |

The exact pinned ULK source is healthy enough for publication review. Its problem is not known bad code; its problem is that the commits exist only in the local provider repository and are not reachable from the public canonical branch.

### 3.3 Universal Setup / `universal-setup`

| Field | Current state |
| --- | --- |
| Local observation path | `D:\Projects\Universal\universal-setup` |
| Checkout | detached at the exact FacMan pin |
| Revision | `3f8489275077347c2918f3bb03614ec6431362ff` |
| Remote-tracking main | exact match |
| Worktree | clean |
| Current validation | strict pass, 21 Python tests pass |
| Native inventory | 16 CTest entries; recorded three-repository proof passed all 16 |
| Release | unsigned and unpublished |

Universal Setup does not block the first Play revalidation. Its exact pinned revision is already public and canonical. It should remain stable while the Launcher source closure and FacMan Play path are repaired.

### 3.4 Source-of-truth limitation

This report used the current local repositories, local remote-tracking
references, retained project evidence, and the supplied external audit.
Absolute paths in the repository tables are machine-local observations, not
portable project requirements. Repository policy forbids an unreviewed network
operation, so no new live remote fetch or GitHub mutation was performed while
writing this report. The supplied audit independently reported that the public
GitHub commit endpoint did not resolve `e78cc9f…`.

---

## 4. What has been completed

### 4.1 Correct repository boundary

The system has converged on the right permanent ownership model:

```text
Universal Setup
  install, verify, repair, move, uninstall, rollback, recovery,
  installed-state ownership, and setup audit

Universal Launcher
  product-neutral command graph, clients/transports, products,
  install references, instances, profiles, artifact sets,
  launch-plan references, orchestration, and later process sessions

FacMan
  Factorio discovery, Factorio installation interpretation,
  workspace composition, instances, profiles, mods, saves,
  launch policy, readiness, evidence, and player-facing frontends
```

This boundary is documented and mechanically checked through the component-ownership manifest. The repositories should not be merged and a fourth “universal common” implementation repository should not be created.

### 4.2 FacMan foundations

FacMan has completed or materially advanced:

- durable repository layout and retired-root enforcement;
- public C ABI boundary rules;
- versioned contracts and refusal vocabulary;
- generated frontend command catalogs;
- static application composition through nine domain modules;
- explicit global effect/capability admission;
- workspace, instance, install, profile, preset, modset, save, snapshot, server, diagnostic, and recovery domains;
- installation model v2 as a read-only evidence and reconciliation layer;
- portable `InstanceSpec`, machine-local `InstanceBinding`, computed readiness, and `InstanceView`;
- deterministic configuration precedence;
- a no-shell process-supervision foundation proven with fake processes;
- operation-permit infrastructure with provider-side revalidation and no product issuance;
- hermetic and Windows instance-isolated policy/candidate programs;
- transaction journaling, recovery, audit, stable file identity, path safety, and refusal handling;
- direct, process, CLI, TUI, WinForms, and AppKit-facing client work;
- platform package-preview matrices;
- SDK/package proof, SBOM/provenance generation, and three-repository clean reconstruction;
- AIDE Lite task, Git, evidence, and checkpoint governance.

The central dispatcher decomposition is real progress. `FactorioApplication` now composes:

```text
WorkspaceApplicationModule
SetupApplicationModule
InstallationApplicationModule
InstanceApplicationModule
ProfileApplicationModule
ContentApplicationModule
RecoveryApplicationModule
DiagnosticsApplicationModule
LaunchApplicationModule
```

The composition root has no direct command implementation cases.

### 4.3 Real execution learning

The project did not merely simulate every risk. It performed a real Factorio attempt under Gate 4C and learned why the hermetic normal-host claim was too strong.

Verdict 03:

- started Factorio through the reviewed split-privilege path;
- reached the human journey;
- consumed the exact permit;
- observed zero lost ETW events;
- remained `Inconclusive` because target resolution and packet closure failed;
- observed creation of `NVIDIA Corporation/umdlogs` under the selected installation;
- proved that the frozen subdirectory-only writable model did not match actual normal-host effects;
- did not start a second launch;
- did not promote a public route.

The post-run repair corrected artifact staging, observer handling,
working-directory isolation, and the process environment. The project then
correctly separated the weaker normal-host `instance_isolated` claim from the
stronger hermetic claim.

### 4.4 Universal Launcher work

Universal Launcher has:

- a product-neutral command graph and introspection;
- bounded descriptor registration without a fixed command ceiling;
- setup handoff and stale-reference behavior;
- a frontend-neutral C client/transport ABI;
- product, install, instance, profile, artifact-set, and launch-plan reference validation;
- stale versus invalid reference-graph classification;
- strict structure, language/runtime, license, command, setup-handoff, and reference-model validation;
- native command-graph, setup-handoff, client, and reference-model smoke tests.

The two extraction commits are locally clean and validated. FacMan already consumes them successfully.

### 4.5 Universal Setup work

Universal Setup is the strongest completed subsystem. It has:

- a descriptor-authoritative setup command graph;
- strict recipe, source, plan, installed-state, ownership, journal, audit, lifecycle, refusal, and policy contracts;
- stable no-follow source inspection;
- bounded classic-ZIP inspection;
- path, case, reserved-name, link/device/reparse, encryption, ZIP64, Unicode, size, depth, ratio, and elapsed-time refusals;
- known-answer-tested SHA-256;
- durable transaction journals and no-replace staging/commit;
- crash-window and interruption testing;
- exact installed-state and ownership repositories;
- append-only chained audit;
- fixture-backed install, verify, repair, move, uninstall, and recovery;
- adversarial concurrency, substitution, drift, fault-injection, sanitizer, and fuzz proof;
- live-target policy and acceptance-root authority;
- public plan/apply lifecycle commands for a deliberately narrow operator-acceptance lane;
- restart-safe staged rollback;
- live evidence capture and human-verdict contracts;
- a synthetic live acceptance CLI;
- package verify/audit that distinguishes integrity from authenticity.

FacMan correctly delegates setup mutation and package inspection rather than reimplementing them.

### 4.6 Build and platform work

The project has candidate package proof for:

- Windows x64 CLI;
- Linux x64 CLI on the Ubuntu 24.04 runner baseline;
- macOS x64 CLI;
- Windows, Linux, and macOS x64 TUI preview lanes;
- Windows legacy WinForms as an experimental runtime-tested shell;
- macOS legacy AppKit as compile-only experimental proof.

GTK remains unavailable. The daemon remains an intentionally unavailable placeholder. Packages are not signed or publicly published.

### 4.7 Work performed during this review

This review:

- read and reconciled the supplied 1,500-line audit;
- inspected AIDE task state and Git policy;
- verified all three worktrees and exact revisions;
- confirmed the ULK commit exists only on its local extraction branch;
- confirmed the FacMan workspace lock lacks remote/ref/reachability policy;
- confirmed its validator checks local `HEAD` only;
- confirmed empty lifecycle becomes `"active"`;
- confirmed unknown lifecycle maps to `ULK_INSTALL_LIFECYCLE_ACTIVE`;
- confirmed direct transport can discard a provider result after cancellation;
- confirmed broad process booleans are not a safe route-promotion model;
- confirmed candidate evidence and runtime code share a 2,099-line source file and target;
- confirmed hard-coded provider revisions and stale readiness text;
- confirmed global application serialization and borrowed member-owned responses;
- confirmed JSON child lookup copies and retains subtrees behind a mutex;
- confirmed fast-test manifest/configuration drift;
- completed fresh ULK strict, Python, Release build, and native CTest validation;
- completed fresh USK strict and Python validation;
- left all three tracked worktrees clean before report creation.

Earlier inspection in this thread also established:

- FacMan dependency pins matched the configured local repositories;
- FacMan strict validation passed;
- the configured native fast-unit tests and fast Python tests passed when invoked from the actual configured graph;
- the canonical `tools/dev.py test --fast` path failed because it requested a conditional TUI target that was not built;
- a Release CLI build succeeded;
- the attempted performance benchmark did not provide a credible product-runtime baseline and must not be treated as optimization evidence.

---

## 5. What was missed, is incomplete, or has drifted

## 5.1 P0 — Public source closure

FacMan pins:

```text
universal_launcher = e78cc9f3a23f748130749ebe7241dbd1166f8b25
```

The local provider contains it. Public `origin/main` does not.

The current lock provides only:

```toml
id
source
pin
path
```

The validator proves only:

```text
local path exists
local HEAD == pin
```

It does not prove:

```text
the commit can be fetched from the declared remote
the commit is an ancestor of canonical main
an empty clone can reconstruct the checkout
the checkout is clean
```

This invalidates any claim that a new contributor or hosted runner can reproduce current FacMan `dev` from public source.

Required repair:

```text
ULK-EXTRACTION-PUBLICATION-01
FACMAN-FIRST-PARTY-PIN-REMOTE-REACHABILITY-01
FACMAN-REMOTE-ONLY-THREE-REPO-RECONSTRUCTION-01
```

Do not squash or rewrite the published extraction commits unless FacMan’s pin is deliberately updated and the full three-repository proof is repeated.

## 5.2 P0 — Missing lifecycle evidence fails open

FacMan currently does:

```text
empty lifecycle -> "active"
empty verification identity -> "unobserved"
empty state revision -> "unobserved"
unknown lifecycle text -> ULK active enum
```

This can turn missing, malformed, misspelled, or future evidence into apparently active state.

Required behavior:

```text
active only from exact "active" plus current verification and state identity
missing -> unbound/evidence_missing
unknown/unobserved -> explicitly unavailable
future/unsupported -> unsupported_lifecycle
identity conflict -> invalid
known prior evidence drift -> stale
```

This repair is mandatory before real route revalidation.

## 5.3 P0 — Cancellation and timeout can lie about durable effects

Direct transport checks cancellation after synchronous provider dispatch and can replace a completed provider response with `cancelled`.

Process and WinForms transports can terminate a child and report ordinary timeout/cancellation without proving whether the operation crossed a commit boundary.

The system lacks a consistent cross-transport model for:

- globally unique request IDs;
- durable semantic operation IDs;
- per-attempt IDs;
- idempotency keys;
- cancellation phase;
- `cancellation_requested_but_completed`;
- `outcome_unknown`;
- exact recovery references.

For mutation, “cancelled” must never mean “nothing happened” unless the provider proves no commit or complete rollback.

## 5.4 P0 before Play — Authority is too broad

`ApplicationConfiguration` exposes broad false booleans:

```text
process_execution_authorized
network_read_authorized
network_write_authorized
```

False is safe today. Turning `process_execution_authorized` true would be much broader than the exact reviewed route.

The first executable capability must bind:

- route ID;
- exact policy and claim;
- Windows/x64;
- exact Factorio version;
- standalone non-Steam distribution;
- menu intent;
- instance-isolated mode;
- process and observer provider revisions;
- permit profile.

No environment variable, preference, dynamic plugin, GUI checkbox, or general build flag may create or widen the route.

## 5.5 P1 — Evidence harness and product runtime are coupled

`flb_factorio_hermetic_candidate.cpp` is approximately 2,099 lines and contains:

- hermetic candidate policy;
- Windows instance-isolated candidate policy;
- evidence vocabularies;
- permit projection;
- observer classification;
- packet disposition;
- artifact persistence.

It compiles with ordinary launch infrastructure and still writes the historical marker:

```text
FACMAN-HERMETIC-STANDALONE-PLAY-CANDIDATE-01
```

The build graph does not enforce that evidence/harness code is absent from ordinary product packages.

## 5.6 P1 — Command truth is repeated

The command contract and generated catalog already know schemas, effects, owner, binding, availability, risk, and persistent-write behavior. Handwritten code separately repeats:

- request decoding;
- admission effects/capabilities;
- module ownership;
- module execution cases;
- denial handling;
- frontend catalog mapping.

This allows drift.

Module-wide denial exceptions are particularly risky. The Content module can
accept broad `network_forbidden` denials and the Launch module accepts denied
admission to produce richer refusals. Denial transformation must be explicit
per command.

## 5.7 P1 — Response lifetime and concurrency remain centralized

`FactorioApplication`:

- holds the complete command path under one mutex;
- stores `current_command_`, `response_json_`, and `error_message_` on the application object;
- returns response views into those members;
- invalidates response lifetime on a later command.

This serializes independent reads and writes and couples ABI lifetime to context state.

The correct next ABI is an owned response or caller-provided allocator/buffer API. Concurrency can then move gradually to shared workspace reads, exclusive workspace writes, per-instance locks, per-install locks, and per-instance run locks.

## 5.8 P1 — Request decoding is still a large variant/switch

The central module decomposition is good, but `ApplicationPayload` and `ServiceOperationRequest` still span unrelated domains. `command_dispatch.cpp` is approximately 927 lines.

Authority-bearing requests need dedicated types first. Decoders should then be split by module, with generated shape validation and handwritten semantic conversion.

## 5.9 P1 — JSON lookup copies subtrees

Each `Value::find()` or `Value::at()`:

- copies the child PicoJSON subtree;
- allocates a new wrapper;
- locks a mutex;
- retains the wrapper until the parent dies.

This is a confirmed inefficient code path for large modsets, instance
projections, evidence packets, and setup responses. It should be replaced with
immutable document-backed views before attempting speculative
micro-optimizations elsewhere.

There is no credible current end-to-end performance baseline. The attempted benchmark did not exercise a representative compiled product path and did not produce sufficient metadata.

## 5.10 P1 — Runtime truth is hard-coded and stale

Provider revisions are compiled as source literals. Readiness still tells users
to await an already completed OperationPermit gate. Workspace and launch
explanations still say both real-Play designs are unproven instead of reporting
the precise current absence of an accepted route.

The current status file also says the Windows instance-isolated candidate is pending reviewed integration even though its branch is already contained in `dev`.

Build identity must be generated from:

- actual FacMan source revision;
- exact checked-out provider revisions;
- workspace lock;
- package profile;
- exact enabled route capabilities.

Player language must describe capabilities, not WorkUnit history.

## 5.11 P1 — Launch preparation is duplicated

Preview and preflight independently:

- load instance and installation;
- map records;
- resolve effective profile;
- construct launch references;
- inject lifecycle and verification fallbacks.

Similar install mapping is repeated in other handlers and models.

One `LaunchPreparation` should provide the stable observations, effective configuration, reference graph, readiness, selected route candidate, resource identities, and evidence dependencies used by preview, preflight, and execute.

Other launch correctness gaps:

- native `path.string()` remains at machine-output boundaries;
- launch-plan policy reads process environment variables during evaluation rather than from the declared process-lifetime configuration snapshot;
- authoritative filesystem checks need stable no-follow observations;
- executable, config, instance-root, and install-root identities need immediate pre-process revalidation.

## 5.12 P1 — Workspace root authority is weaker than execution authority

Explicit, environment, and preference workspace roots do not consistently receive the same link/reparse and stable-object inspection as descendants.

Inspection failures can collapse to “not a link,” normal directory creation is used, and nonempty foreign roots do not always require explicit adoption.

The player alpha must eventually distinguish:

```text
missing
empty_unowned
facman_owned
legacy_facman
foreign_nonempty
link_or_reparse
inspection_failed
```

## 5.13 Testing defects

The canonical fast-test path is not trustworthy:

- `contracts/policy/test_impact.v1.json` always lists `facman_tui_smoke`;
- CMake creates that test only when `facman_tui_static` exists;
- a legitimate non-TUI build therefore makes `tools/dev.py test --fast` request a nonexistent test;
- the manifest omits current fast-unit targets including operation-permit, instance-model, launch-permit, and candidate smoke tests;
- the architecture validator checks source declarations but not the actual configured CTest graph.

The default `tools/dev.py` build root and README examples still use in-tree `build/...`, conflicting with the documented external task-root policy.

Skip reporting is also too opaque. Historical records contain hundreds of expected skips without classifying whether each skip is unsupported, optional, not applicable, historical-only, or required-but-blocked.

Promotion must require:

```text
required obligations skipped = 0
```

## 5.14 Governance and state defects

The project says there is no active WorkUnit, but `.aide/queue/active/` contains 23 task directories:

- 19 passed or passed-with-notes;
- 1 verified;
- 2 blocked;
- 1 superseded.

Completed work should be archived, blocked work should be indexed as blocked, and only genuinely current work should be active.

`release/index/project_status.v2.toml` is approximately 1,755 lines and combines present truth with extensive historical evidence. No compact `release/index/current_state.v1.toml` exists.

The current-state layer should answer only:

- what works;
- what is blocked;
- why;
- exact revisions;
- current capabilities;
- next gate.

Historical proof belongs in immutable checkpoints and `.aide/history/`.

## 5.15 Product gaps

FacMan’s current GUI/TUI surface is a generated command browser, not the intended player product.

Missing product capabilities include:

- instance-first home and detail views;
- readiness and Make Ready;
- prominent Play-to-menu;
- last-run state;
- relaunch;
- recovery center;
- player-oriented errors and safe next actions;
- observed first-run usability;
- accessibility and localization proof;
- stable install/update/uninstall experience;
- signed public downloads.

The command explorer is valuable and should remain under Advanced.

## 5.16 Platform gaps

- Windows is the only sensible first player target.
- Linux and macOS CLI/TUI are candidate package lanes, not full player routes.
- WinForms is experimental.
- AppKit is compile-only.
- GTK is unavailable.
- The daemon is intentionally unavailable.
- No platform route should be promoted merely because it compiles.

## 5.17 Universal Launcher remaining work

Immediate:

- publish client/transport and reference commits;
- establish canonical source/release identity;
- add operation/session outcome semantics used by FacMan;
- define owned-response lifetime where required.

After the first route:

- reference persistence when the product workflow needs it;
- product-neutral execution/session foundation extracted from proven FacMan behavior;
- diagnostic and account-reference model completion where consumed;
- internal decomposition into registry, command graph, dispatch, client, transport, references, and setup handoff.

Deferred intentionally:

- daemon runtime;
- dynamic plugin system;
- general workflow engine;
- abstractions without a real second consumer.

## 5.18 Universal Setup remaining work

Universal Setup does not need immediate Play-path feature work, but the complete product train still needs:

- a reviewed human acceptance decision for ordinary managed-portable activation;
- production source/authenticity policy;
- clean-machine managed standalone install/update/downgrade/repair/move/uninstall proof;
- visible-target recovery finalization with exact original operation context;
- public audit list/inspect/export handlers;
- compatibility `verify.report` resolution or explicit retirement;
- signed package and publisher-authenticity integration;
- characterization tests before decomposing `usk_public_lifecycle.cpp`;
- a real product proof consumer, currently intended to be Dominium.

Network acquisition, package-manager integration, vendor installers, registry, shortcuts, elevation, and credentials must remain separate reviewed capabilities, not one broad “production installer” switch.

---

## 6. Why the project reached this state

The project’s strengths and weaknesses have the same origin: safety and governance advanced faster than the player product.

### 6.1 Evidence was treated as a product

The project built sophisticated policies, evidence packets, observers,
interruption matrices, and retained histories before one supported player
route existed. That work prevented false claims and exposed real Windows
behavior, but it also concentrated candidate machinery inside the runtime and
delayed the primary user journey.

### 6.2 Local proof outran public source closure

Cross-repository extraction was integrated and cleanly reconstructed locally before provider commits were published. The lock proved local object identity, not public reachability.

### 6.3 Truth exists in too many representations

Contracts, generated catalogs, runtime switches, status TOML, AIDE state, README blocks, branch state, and evidence checkpoints overlap. They have started to drift.

### 6.4 Safety gates correctly stopped authority

The system remains unplayable because it refused to infer authority from fake
processes, local tests, or inconclusive real runs. That is correct. The repair
is not to weaken the gates; it is to narrow the route and finish the required
proof.

### 6.5 UX was deferred behind architecture

The command graph and generated forms proved backend breadth, but they became the visible product. The next product architecture must organize the same capabilities around player tasks.

---

## 7. Target architecture

The target remains a statically composed modular monolith:

```text
Instance-first GUI / CLI / TUI / Advanced explorer
                         |
                         v
              Universal Launcher client
          direct / process / later daemon transport
                         |
                         v
       Generated command + capability descriptor table
   schemas | module | decoder | effects | risk | denial | lock scope
                         |
                         v
              FacMan application modules
        workspace | installs | instances | profiles
        content | launch | recovery | diagnostics
                         |
                         v
               Capability-scoped provider ports
          ULK references/session | USK setup mutation
          process | filesystem | observer | credentials
                         |
                         v
            Stable stores, journals, audit, evidence
```

Required separations:

```text
product runtime route != operator evidence harness
route capability != global process authority
cancellation request != proof of no effects
missing evidence != active state
local Git object != public reproducible source
integrity != publisher authenticity
configuration != authority
plan != permit
test pass != route promotion
```

### 7.1 Generated command descriptor

The authoritative descriptor should contain:

```text
command ID
public name
module
decoder
request/response/result/refusal schemas
effects
required static capabilities
risk tier
dry-run behavior
availability
denial disposition
concurrency scope
persistent-write property
```

Handwritten code should supply only dynamic product eligibility, current evidence, provider availability, exact resource identities, route capability, and permit validation.

### 7.2 Exact route capability

The first route should be one immutable packaged capability:

```text
windows-instance-isolated-factorio-2.0.77-menu-v1
```

It must bind the policy digest, claim, platform, architecture, Factorio version, distribution, menu intent, isolation mode, provider revisions, and permit profile.

### 7.3 Product UI

Primary navigation:

```text
Instances
Installations
Modpacks
Profiles and Presets
Saves and Worlds
Accounts
Backups and Snapshots
Recovery Center
Advanced
```

Instance view:

```text
identity and version
install and ownership
effective profile/preset
modset state
account state
saves
readiness
Play
Configure
Make Ready
Clone
Snapshot
Export
Repair
Archive
last run
recovery
```

---

## 8. Optimal dependency-ordered plan

## Wave 0 — Publish and close the source chain

### WorkUnits

```text
ULK-EXTRACTION-PUBLICATION-01
FACMAN-FIRST-PARTY-PIN-REMOTE-REACHABILITY-01
FACMAN-REMOTE-ONLY-THREE-REPO-RECONSTRUCTION-01
```

### Actions

1. Push `task/client-transport-extraction-01` at `78c27da…`.
2. Open a reviewed PR to ULK `main`.
3. Require strict, Python, native, and hosted matrix checks.
4. Merge without rewriting the exact commit unless all consumer pins are deliberately updated.
5. Push `task/reference-model-extraction-01` at `e78cc9f…`.
6. Open and review the second PR after the client commit is canonical.
7. Merge and verify `e78cc9f…` is an ancestor of canonical ULK `main`.
8. Extend the FacMan lock with `remote`, `required_ref`, and `reachability`.
9. Split validation into:
   - offline structural/local checkout checks;
   - hosted or explicitly authorized remote reachability proof.
10. From empty remote clones, fetch only canonical refs, check out exact pins, and run the complete three-repository reconstruction.

### Exit gate

```text
any authorized contributor can reconstruct the exact source and build
without relying on a local Git object database
```

No new real-Play evidence becomes durable before this gate.

## Wave 1 — Bounded correctness consolidation

### WorkUnit

```text
FACMAN-PRE-REVALIDATION-CORRECTNESS-CONSOLIDATION-01
```

### Scope

- fail-closed lifecycle decoding;
- explicit evidence availability instead of magic strings;
- command-specific denial disposition;
- generated build/provider revision truth;
- current capability/readiness wording;
- UTF-8 machine path output;
- process-lifetime environment snapshot;
- generic candidate artifact ownership marker;
- configuration-aware fast-test selection;
- external task-root default;
- required-obligation skip classification;
- compact current-state generation and active-queue cleanup.

### Constraints

- no route authority;
- no policy widening;
- no real Factorio execution;
- no new product feature;
- no hidden change to canonical packet bytes unless explicitly versioned.

### Exit gate

- every missing/unknown lifecycle negative test refuses or remains unbound;
- no unknown lifecycle becomes active;
- current runtime revision output matches the configured build;
- `tools/dev.py test --fast` passes for TUI-on and TUI-off configurations;
- required skips equal zero in promotion profiles;
- present state is compact and agrees with branch/task truth.

## Wave 2 — Product-neutral operation outcome semantics

### WorkUnits

```text
ULK-OPERATION-OUTCOME-CONTRACT-01
FACMAN-TRANSPORT-OUTCOME-SEMANTICS-01
```

### Deliverables

- globally unique request, operation, and attempt IDs;
- idempotency key support where safe;
- explicit cancellation phases;
- `cancellation_requested_but_completed`;
- `outcome_unknown`;
- `recovery_required`;
- exact transaction/recovery reference;
- equivalent direct, process, CLI RPC, TUI, WinForms, and later daemon semantics;
- negative race tests proving a completed result cannot be replaced by cancellation.

### Exit gate

Every authority-bearing command can answer:

```text
did not start
refused before dispatch
completed
cancelled before dispatch
cancel requested but completed
recovery required
outcome unknown
```

No transport invents a stronger result than the provider can prove.

## Wave 3 — Separate runtime and evidence machinery

### WorkUnit

```text
FACMAN-PLAY-CANDIDATE-RUNTIME-SEPARATION-01
```

### Deliverables

```text
flb_factorio_launch_runtime_static
flb_factorio_play_candidate_evidence_static
flb_factorio_operator_harness_static
```

Default product packages exclude candidate/evidence targets.

Split source into:

```text
launch/plan
launch/execution
launch/candidate/common
launch/candidate/hermetic_standalone_v1
launch/candidate/windows_instance_isolated_v1
```

### Exit gate

- canonical plans, packets, evidence digests, policy digests, and negative controls remain byte-identical;
- the generic artifact marker is versioned;
- ordinary runtime packages contain no operator-harness target by default;
- semantic changes require new policy/provider revisions.

## Wave 4 — Reconstruct and freeze the exact revalidation candidate

### WorkUnit

```text
FACMAN-REMOTE-ONLY-THREE-REPO-RECONSTRUCTION-01
```

### Prerequisites

- all three commits public;
- all worktrees clean;
- lock and actual checkouts exact;
- hosted matrices green;
- task build root initially absent;
- no old candidate artifact reused;
- candidate/evidence split validated;
- exact policy digest unchanged or deliberately re-reviewed.

### Exit gate

A hash-closed candidate package and procedure exist for one exact revalidation attempt.

## Wave 5 — Real Windows instance-isolated Play revalidation

### WorkUnit

```text
FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-REVALIDATION-01
```

### Procedure

- preflight exact executable, config, instance root, install root, environment, and provider identities;
- open Factorio 2.0.77 standalone non-Steam to the main menu;
- prove no implicit save/scenario/server/benchmark intent;
- verify selected instance data;
- exercise exit and authorized relaunch;
- record disclosed Windows effects;
- complete protected comparisons;
- record human result as exactly `Pass`, `Fail`, or `Inconclusive`;
- hash-close the packet.

### Exit decisions

```text
Pass         -> exact route becomes eligible for a separate promotion review
Fail         -> bounded repair; do not weaken criteria retroactively
Inconclusive -> improve observation and repeat without claiming success
```

## Wave 6 — Promote only the exact accepted route

### WorkUnits

```text
FACMAN-EXACT-PLAY-ROUTE-CAPABILITY-01
FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-ROUTE-PROMOTION-01
```

### Deliverables

- immutable compiled/package route capability;
- exact request-to-route matching;
- current readiness;
- exact plan and operation permit;
- provider-side immediate revalidation;
- permit consumption immediately before process creation;
- run-session state and recovery;
- compatible `facman run <instance> --execute`;
- preferred `facman play <instance>`.

### Non-goals

- Steam;
- other Factorio versions;
- save-target launch;
- servers;
- benchmarks;
- hermetic claims;
- general `process=true`.

## Wave 7 — Instance-first controlled alpha

### WorkUnit

```text
FACMAN-INSTANCE-CENTRIC-ALPHA-01
```

### Deliverables

- Instances home;
- selected instance view;
- readiness;
- Make Ready preview;
- Play to menu;
- exit and last-run state;
- relaunch;
- snapshot;
- recovery center;
- actionable refusal language;
- Advanced command explorer retained.

### User-validation gate

Run observed player journeys:

- fresh user with existing standalone install;
- fresh instance creation;
- blocked readiness and remediation;
- Play to menu;
- exit and relaunch;
- recovery from an interrupted local operation.

Targets:

- no external guide for the golden path;
- no silent foreign mutation;
- every blocker has a safe next action;
- zero data-loss incidents;
- measured time-to-first-play;
- accessibility keyboard and screen-reader baseline.

## Wave 8 — Managed standalone lifecycle and content preparation

### WorkUnits

```text
FACMAN-MANAGED-INSTALL-RECONCILIATION-01
USK-MANAGED-PORTABLE-ACCEPTANCE-01
USK-PUBLIC-AUDIT-OPERATIONS-01
USK-VISIBLE-TARGET-RECOVERY-01
FACMAN-CONTENT-PREPARATION-01
FACMAN-PORTABLE-INSTANCE-BUNDLE-01
FACMAN-WORLD-BUNDLE-AND-SAVE-COMPATIBILITY-01
```

### Sequence

1. Characterize current USK lifecycle behavior with golden outputs.
2. Accept one exact managed-portable target class through human review.
3. Authenticate selected source material.
4. Promote create first.
5. Promote verify.
6. Promote repair.
7. Promote move.
8. Promote update/downgrade/reinstall.
9. Promote uninstall.
10. Prove interruption and recovery for each operation.

Each operation receives a separate authority review. Existing foreign and Steam installs remain read-only or require an explicit managed clone.

## Wave 9 — Deeper architecture and measured performance

### WorkUnits

```text
FACMAN-GENERATED-APPLICATION-ROUTING-01
FACMAN-RESPONSE-LIFETIME-AND-CONCURRENCY-01
FACMAN-JSON-VIEW-AND-DECODE-PERFORMANCE-01
FACMAN-WORKSPACE-ROOT-AUTHORITY-01
ULK-REFERENCE-PERSISTENCE-01
ULK-EXECUTION-SESSION-EXTRACTION-01
USK-PUBLIC-LIFECYCLE-DECOMPOSITION-01
```

### Rules

- benchmark before and after;
- preserve public behavior;
- split by proven responsibility;
- avoid framework generalization;
- add per-resource concurrency only after owned responses;
- characterize USK security-sensitive lifecycle code before decomposition;
- extract ULK process/session behavior only after FacMan’s first route is stable.

Performance instrumentation:

```text
parse duration
JSON lookup count
subtree bytes copied
allocation count
serialization duration
hashing duration
repository I/O
lock wait
provider duration
end-to-end command latency
```

## Wave 10 — Trusted distribution

### WorkUnit

```text
FACMAN-TRUSTED-DISTRIBUTION-01
```

### Deliverables

- reproducible three-repository superbuild;
- exact public pin closure;
- signed primary packages;
- SBOM and provenance;
- publisher-authenticity verification;
- install/update/downgrade/uninstall;
- workspace migration inspect/plan/backup/apply/recovery;
- signed update and repair metadata;
- self-update rollback;
- clean-machine validation;
- support and compatibility policy;
- release channel separation.

## Wave 11 — Stabilize trustworthy v1

### Deliverables

- freeze the proven workflow subset;
- publish compatibility guarantees;
- publish migration policy;
- publish security and privacy model;
- establish release cadence and supported versions;
- run regression, upgrade, downgrade, recovery, usability, accessibility, and clean-machine matrices;
- archive experimental evidence lanes that are no longer active;
- declare v1 only after the product—not merely the kernels—passes its acceptance criteria.

---

## 9. Critical path and parallel lanes

### 9.1 Critical path

```text
ULK publication
  -> remote source closure
  -> correctness consolidation
  -> outcome semantics
  -> candidate/runtime separation
  -> empty-clone reconstruction
  -> exact revalidation
  -> route promotion
  -> player alpha
  -> managed lifecycle
  -> trusted distribution
  -> v1
```

### 9.2 Safe parallel work

These may proceed without widening runtime authority:

- instance-first wireframes and usability prototypes;
- accessibility and localization foundations;
- test-obligation classification;
- compact current-state generation;
- release/signing threat-model planning;
- characterization tests;
- benchmark harness design;
- documentation of supported workflows;
- support bundle and diagnostics UX.

They must not delay the critical path.

### 9.3 Work that should wait

- daemon;
- dynamic plugins;
- general connector framework;
- broad Steam support;
- additional GUI toolkits;
- cloud sync;
- marketplace;
- headless fleet manager;
- advisory AI;
- cross-repository common implementation library.

---

## 10. Cross-repository work ownership

| Work | Owner | Consumer/reviewer |
| --- | --- | --- |
| Publish client/reference extraction | ULK | FacMan |
| Remote pin policy and reconstruction | FacMan | ULK, USK |
| Lifecycle decoding and LaunchPreparation | FacMan | ULK contract reviewer |
| Operation outcome contract | ULK | FacMan transports/frontends |
| Exact Factorio route | FacMan | ULK process/session boundary |
| Setup mutation, rollback, recovery | USK | FacMan and later Dominium |
| Player UI and Factorio readiness | FacMan | players |
| Reference persistence | ULK | FacMan when needed |
| Managed standalone lifecycle | USK kernel + FacMan product policy | operator/player evidence |
| Signing and product release | FacMan release train | all three providers |

Rules:

- provider-first changes land in the provider before consumer integration;
- provider commits are public and canonical before consumer evidence;
- FacMan pins exact revisions;
- consumer tests prove integration;
- no repository copies another repository’s authority-bearing implementation;
- similar utility names do not justify a shared implementation package.

---

## 11. Validation and promotion gates

### Gate A — Source

- exact commits published;
- remote and canonical ref declared;
- pin fetchable from empty clone;
- pin ancestor of required ref;
- checkout exact and clean.

### Gate B — Correctness

- missing evidence fails closed;
- command denials are command-specific;
- runtime build truth is generated;
- fast and strict entrypoints are reliable;
- no required validation skip.

### Gate C — Outcome

- every operation has durable identity;
- cancellation/timeout cannot erase a completed result;
- unknown outcomes include recovery instructions.

### Gate D — Route

- exact route capability;
- exact policy and provider revisions;
- immediate resource revalidation;
- human `Pass`;
- hash-closed packet;
- separate promotion review.

### Gate E — Alpha

- golden journey works;
- recovery works;
- no silent mutation;
- observed player validation;
- actionable UI.

### Gate F — Beta

- signed packages;
- update/migration/rollback;
- managed lifecycle;
- clean-machine proof;
- support policy.

### Gate G — v1

- stable workflow subset;
- supported upgrade path;
- regression and recovery matrices;
- documented compatibility/security/privacy;
- operational release process.

---

## 12. Engineering-system improvements

### 12.1 One present-tense truth pipeline

Generate:

```text
release/index/current_state.v1.toml
generated build identity
runtime capability output
README status block
AIDE compact state
```

from one validated current-state source plus exact build inputs.

### 12.2 Archive task state aggressively

Move passed and superseded tasks from active queues after closeout. Retain hash-indexed evidence. Show blocked tasks in a distinct blocked index.

### 12.3 Test configured graphs, not source text

Test tooling should query CTest’s configured inventory and intersect it with requested labels/capabilities. Conditional targets must not appear as mandatory when disabled.

### 12.4 Make obligations explicit

Every build profile should declare required, optional, unsupported, and operator obligations. CI reports names and reasons, not only counts.

### 12.5 Add advisory architecture metrics

Report:

- source/function line count;
- command cases;
- policy vocabularies per source;
- include fan-in;
- target fan-out;
- public ABI lifetime model;
- duplicated generated metadata.

Use these as review signals before turning them into hard CI limits.

### 12.6 Use characterization before security-sensitive refactors

Golden bytes, state transitions, refusal codes, recovery actions, and fault-injection behavior must be frozen before changing transaction, candidate, or setup lifecycle internals.

### 12.7 Measure product latency

Build a representative native benchmark suite around real manifests, modsets, instance views, evidence packets, and direct/process command paths. Do not use Python-only or metadata-poor results as product optimization evidence.

---

## 13. Risk register

| Risk | Impact | Probability | Mitigation |
| --- | --- | --- | --- |
| ULK commits remain local | Critical reproducibility failure | High until published | Wave 0 publication and empty-clone proof |
| Missing lifecycle becomes active | Unsafe route eligibility | Confirmed | Explicit decoder and negative tests |
| Cancellation hides durable effects | Data/state ambiguity | Confirmed in design | Operation outcome contract |
| Broad process flag enables excess authority | Security boundary violation | High if naively promoted | Exact route capability |
| Evidence refactor changes verdict semantics | Invalidates proof | Medium | Byte-identical characterization and new revisions for semantics |
| Current status drifts from code/branches | Wrong next action | Confirmed | Generated compact current state |
| Fast test gives false failure or incomplete coverage | Contributor/CI distrust | Confirmed | Configured-graph selection |
| Workspace root is substituted/foreign | Ownership violation | Medium | Stable root authority |
| JSON copies create scale problems | Performance/memory degradation | High on large payloads | Immutable views and benchmark |
| GUI remains command browser | Product adoption failure | Certain without Wave 7 | Instance-first UX |
| Managed setup expands too broadly | Destructive mutation risk | Medium | One operation/target class at a time |
| Signing/update added late | Beta delay | High | Design in parallel, implement after alpha |
| More frameworks delay first route | Schedule failure | High | Enforce critical-path ceiling |
| USK lacks real proof consumer | Setup v1 confidence gap | Medium | Dominium or equivalent real product proof |

---

## 14. What not to do

Do not:

- merge the three repositories;
- create a fourth common implementation repository;
- rewrite the runtime in another language;
- add dynamic in-process plugins;
- build a daemon before a real requirement;
- add AI-driven mutation;
- extract every generic-looking helper;
- rename all roots again;
- migrate every workspace record before the player journey needs it;
- add more GUI toolkits before one GUI proves the golden journey;
- weaken evidence criteria to obtain a Pass;
- infer authority from tests, local Git objects, configuration, or commit counts;
- enable global process, network, credential, setup, signing, or publication switches;
- optimize small lookup tables before profiling;
- treat Steam or foreign installations as FacMan-owned;
- perform another broad architecture wave before source closure and first-route completion.

---

## 15. Immediate next actions

In exact order:

1. Obtain explicit operator approval for ULK branch publication and GitHub PR operations.
2. Publish and review `78c27da…`.
3. Publish and review `e78cc9f…`.
4. Verify both commits from an empty remote clone and canonical `main`.
5. Add remote policy to every first-party provider pin.
6. Run remote-only three-repository reconstruction.
7. Open `FACMAN-PRE-REVALIDATION-CORRECTNESS-CONSOLIDATION-01`.
8. Repair lifecycle decoding first and add negative tests.
9. Repair build truth, readiness text, fast-test selection, and compact current state.
10. Land product-neutral operation outcome semantics in ULK and integrate every FacMan transport.
11. Split evidence targets without changing bytes.
12. Reconstruct and freeze the exact candidate.
13. Run the human Windows instance-isolated revalidation.
14. If and only if `Pass`, promote the exact route.
15. Build and test the instance-first alpha.

---

## 16. Final assessment

The project is not architecturally broken. Its repository ownership, safety posture, transaction design, evidence discipline, and contract coverage are stronger than most projects at this stage.

Its main weakness is convergence:

```text
too much locally proven infrastructure
too little publicly closed source
too many parallel truths
no accepted product route
no player-first experience
no trusted distribution
```

The best way forward is not another general framework. It is to close the
public source chain, repair the few correctness boundaries that can produce
false truth, establish one unambiguous operation model, pass one exact Play
route, and turn that route into an observed player journey.

Universal Setup should remain stable during the immediate Play work. Universal
Launcher should grow only through capabilities directly consumed by FacMan.
FacMan should stop expanding breadth until the first route and instance journey
are real.

That sequence converts the current system from an excellent safety-oriented development platform into a finished product without discarding the rigor that made the platform trustworthy.

---

## Appendix A — Current FacMan active-queue inventory

The directory `.aide/queue/active/` currently contains:

| WorkUnit | Recorded status |
| --- | --- |
| `FACMAN-APPLICATION-MODULE-DECOMPOSITION-01` | passed |
| `FACMAN-CROSS-REPO-OWNERSHIP-AUDIT-01` | passed |
| `FACMAN-GATE4C-PRIVILEGE-SEPARATION-REPAIR-01` | passed |
| `FACMAN-GATE4C-VERDICT03-POSTRUN-REPAIR-01` | passed |
| `FACMAN-HERMETIC-STANDALONE-PLAY-CANDIDATE-01` | passed |
| `FACMAN-HERMETIC-STANDALONE-PLAY-OBSERVER-START-REPAIR-01` | passed |
| `FACMAN-HERMETIC-STANDALONE-PLAY-POLICY-01` | passed |
| `FACMAN-HERMETIC-STANDALONE-PLAY-VERDICT-01` | passed with notes |
| `FACMAN-HERMETIC-STANDALONE-PLAY-VERDICT-02` | blocked |
| `FACMAN-HERMETIC-STANDALONE-PLAY-VERDICT-03` | passed with notes |
| `FACMAN-IGNORED-BUILD-TREE-CLEANUP-01` | passed |
| `FACMAN-INSTALLATION-MODEL-V2-READONLY-CLOSEOUT-01` | passed |
| `FACMAN-INSTANCE-SPEC-AND-READINESS-01` | passed |
| `FACMAN-LOCAL-DEPENDENCY-PIN-ENFORCEMENT-01` | passed |
| `FACMAN-MULTI-VERSION-INSTALL-LIFECYCLE-01` | superseded |
| `FACMAN-OPERATION-PERMIT-01` | passed |
| `FACMAN-ULK-INTEGRATION-PROOF-01` | passed |
| `FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-CANDIDATE-01` | passed |
| `FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-POLICY-01` | passed |
| `M2-WU10-AUTOMATED-ACCEPTANCE-RESULT-01` | blocked |
| `M2-WU10-OPERATOR-LIVE-TARGET-VERDICT-01` | verified |
| `ULK-CLIENT-TRANSPORT-EXTRACTION-01` | passed |
| `ULK-REFERENCE-MODEL-EXTRACTION-01` | passed |

These records should not all remain in an “active” lane.

## Appendix B — Key evidence sources

Primary project truth:

- `release/index/project_status.v2.toml`
- `release/index/workspace_lock.v1.toml`
- `release/index/component_ownership.v1.toml`
- `release/index/support_matrix.v1.toml`
- `docs/product/master_plan.md`
- `.aide/memory/project-state.v2.json`

Critical implementation locations:

- `runtime/factorio/application/handlers/launch.cpp`
- `runtime/factorio/launch/flb_factorio_launch_plan.cpp`
- `runtime/client/facman_transport_direct.cpp`
- `runtime/client/facman_transport_process.cpp`
- `runtime/factorio/application/flb_factorio_application.cpp`
- `runtime/factorio/application/command_admission.cpp`
- `runtime/factorio/application/command_dispatch.cpp`
- `runtime/factorio/launch/flb_factorio_hermetic_candidate.cpp`
- `runtime/core/json/fl_json.cpp`
- `runtime/core/json/fl_json.h`
- `tools/validators/release/check_workspace_lock.py`
- `contracts/policy/test_impact.v1.json`
- `tools/dev.py`

Provider truth:

- Universal Launcher `README.md`, `docs/roadmap.md`, `CMakeLists.txt`
- Universal Setup `README.md`, `docs/roadmap.md`, `CMakeLists.txt`
- exact local/provider Git revisions listed in section 3
