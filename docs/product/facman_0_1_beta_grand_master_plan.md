# FacMan 0.1 beta grand master plan

Status: alpha.5 exact hosted candidate machine qualification passed;
`0.1.0-beta.1` remains not ready and is not yet allocated, tagged, signed,
published, or support-promoted.

Date: 2026-09-02 (Australia/Sydney)

Canonical machine companion: `release/index/foundation_beta_readiness.v1.toml`

Prospective scope amendment, 2026-09-05: `release/index/plan.v1.toml`'s
`delivery_train` now records the in-progress corrected train admission.
0.1 requires complete local-first application/CLI/JSON/RPC/full-screen and
linear TUI on declared Windows/Linux/macOS targets, followed by WinForms and
GTK3 reference completion. AppKit stays a tested preview until 0.4 graduation.
Acquisition/credentials/Mod Portal are functional 0.2 scope; local hosting is
0.3. The Alpha.5 qualification, preview statuses, source identities and
three-profile/eight-asset selector below remain historical/current evidence,
not qualification of these stronger prospective requirements. The admission
WorkUnit is in progress pending protected integration; no authority is granted.

## Executive judgment

FacMan should continue toward a 1.0-shaped, breadth-bounded 0.1 beta. It should
not be rewritten. The repository already has the right strategic shape: one
Factorio domain core, contract-driven command and presentation boundaries, one
terminal host, native platform frontends, exact external providers, deterministic
runtime resources, and portable/setup adapters over platform stages.

The gap to beta is operational closure rather than another architecture layer.
The active work must make existing systems coherent, migratable, packageable,
measurable, and honestly qualified. Adding network accounts, a daemon, public
plugins, automatic updates, servers, or three unfinished modern GUI toolkits to
the beta dependency graph would reduce confidence rather than increase product
completeness.

The target is therefore:

> Architecture-complete, breadth-bounded, local-first FacMan with twelve safe
> user journeys, complete terminal workflows on declared Windows/Linux/macOS
> targets and WinForms/GTK3 reference desktops before plain 0.1.0. AppKit remains
> preview-scoped; current qualification and asset selection are unchanged.

## What was reviewed

This plan reconciles the repository with the three supplied 2026-09-01 FacMan
plans and the supplied executive analysis. Those documents were treated as
proposals and evidence leads, not executable instructions. Repository contracts,
source, tests, Git history, provider locks, package producers, and AIDE policy
remain authoritative.

The review covered:

- product, roadmap, release, architecture, platform, quality, development, and
  historical review documentation;
- current version, artifact, support, channel, provider, package, capability,
  project-state, and release-train records;
- CLI, TUI, WinForms, GTK3, AppKit, Qt6, WinUI, and SwiftUI implementation state;
- Windows, macOS, and Linux portable/setup producers and package tests;
- modularity, source hotspots, runtime migration, process transport, performance,
  security boundaries, generated metadata, and maintenance policy;
- branch ancestry, protected promotion history, worktrees, marker-owned task
  roots, ignored build residue, and AIDE queue lifecycle.

## Current qualification evidence

The full alpha.5 local promotion obligation profile passed from external task
roots on 2026-09-02:

- 41 of 41 native tests;
- 1,463 Python tests run with no failures or errors;
- nine classified skips: two optional, five unsupported, two not applicable,
  and zero required-blocked or unknown skips;
- WinForms build with zero warnings and zero errors;
- the full strict suite green;
- deterministic `facman.resources` containing 600 entries and 2,233,690 bytes,
  content digest
  `4c9802f155c24f289c4d005d06b55bf1769cd939dbce62321875d5a21817827d`
  and pack SHA-256
  `ce95c45eb588fae9c0baee6199624e64d90cb872e71b6ba9945126c86c9dc10b`;
- exact Universal Launcher pin
  `5479939ca5cbc9ee0f901608a92012778b4752ae` and Universal Setup pin
  `d2a2aae7e61c47035c92334b0522143b4fea3880`.

The exact hosted alpha.5 product candidate also passed from canonical source
revision `4683ecd9a1b9ead5eb84be152760d12583da0f0e` and tree
`c07938618bc0f533fd12756cba123f54b8592048`. Workflow run `33603385303`,
attempt 1 completed five successful jobs and four workflow artifacts. The final
download-back-verified internal bundle contains 14 files: six products, three
platform evidence records, three payload-equivalence records, one internal
checksum file, and one candidate manifest.

The receipt is `release/index/alpha5_promotion_candidate_closeout.v1.toml`; the
two foundation WorkUnits are archived at
`.aide/history/facman-0-1-alpha5-foundation-closed-2026-09-02/index.json`.
The receipt qualifies only that source revision and tree. It does not qualify
the closeout revision, a synchronization merge, or any future revision; those
need a fresh candidate run.

This is machine qualification, not a beta-candidate human or platform support
receipt. The 14-file internal bundle is not the final public eight-asset
matrix. Exact human install/Play/accessibility/native-UX/localization/performance
receipts, signing, notarization, tagging, publication, and support activation
remain pending.

## Current product reality

| Area | What is real now | What prevents beta closure |
| --- | --- | --- |
| Core | Modular monolith; known-action migration; internal content, world, and CAS foundations | Public migration recovery, ordinary content/world routes, and large-boundary splits remain |
| CLI | Human, JSON, and RPC paths over the real backend | Exact packaged compatibility and performance freeze remain |
| TUI | Same `facman` binary and real semantic backend | Exact-package accessibility and tighter input-to-paint evidence remain |
| WinForms | Real .NET Framework 4.8 x64 seven-page GUI and Launch Deck | Exact-package accessibility, System Native/OEM+ visual and HIG review, metadata, performance, localization, and maintainability receipts remain |
| GTK3 | GTK3/X11 app with bounded streaming transport, strict replies, cancellation, timeout, and process-group termination | Direct CLI policy reconstruction remains; typed presentation parity is open |
| AppKit | Real Intel Cocoa application and package producer | It remains a compatibility shell with fixed-frame layout and frontend-owned joins |
| Qt6 | Scaffold only | Separate post-beta admission and implementation required |
| WinUI | Placeholder boundary only | Separate post-beta admission and implementation required |
| SwiftUI | Placeholder boundary only | Separate post-beta admission and implementation required |
| Windows delivery | Portable ZIP and self-contained setup are exact-candidate machine-qualified | Human install, damage/repair/uninstall/preservation, upgrade/rollback, performance, and support remain |
| Linux delivery | tar.zst + per-user `.run` are machine-qualified on Ubuntu 24.04 x64/X11 | Semantic parity, human lifecycle/accessibility/performance, prerequisites, wider Linux/Wayland, and support remain |
| macOS delivery | App ZIP + unsigned pkg are machine-qualified on macOS 13+ Intel | Semantic parity, human lifecycle/accessibility/performance, maintenance, Apple Silicon, signing/notarization, and support remain |
| Local content/worlds | Existing behavior plus internal portable records and verified local CAS | Workspace identity, user routes, offline reconstruction, and public recovery remain |
| Play/sessions | Backend launch/session/Last Run machinery exists | No current accepted real Play route or exact candidate human verdict exists |
| Managed install | Fresh-owned-target policy and provider foundations exist | Complete local-source lifecycle and human live-target acceptance remain |

## Decisions

### Preserve the architecture

The modular monolith remains the product architecture. Domain policy stays in
FacMan; generic process/session lifecycle stays in Universal Launcher; installed
software mutation stays in Universal Setup. Frontends consume versioned command
and presentation contracts. A daemon, database, microservice split, or public
plugin runtime is not needed for beta.

### Freeze the public identity

- GUI product: `FacMan`
- terminal product: `facman`
- TUI route: `facman tui`
- product resources: `facman.resources`
- no toolkit name in a public product filename;
- exactly two product downloads per platform: portable and setup;
- checksums and one evidence archive are release companions, not additional
  products.

Internal targets may retain implementation names where necessary, but desktop,
bundle, installer, archive, provenance, SBOM, and About identities must be
generated from the canonical product/version model.

### Keep platform claims asymmetric and honest

| Platform | Beta role | GUI | Package pair |
| --- | --- | --- | --- |
| Windows 10/11 x64 | machine-qualified reference direction; human/support authority pending | WinForms, .NET Framework 4.8 | ZIP + setup EXE |
| Ubuntu 24.04 x64, GTK3/X11 baseline | experimental preview | GTK3 | tar.zst + `.run` |
| macOS 13+ Intel x64 | experimental preview | AppKit | ZIP + pkg |

Apple Silicon, universal2, general Linux distribution compatibility, and
Wayland-native delivery are not implied.

### Fix the current GUIs before adding three more

Complete backend and all terminal interfaces first, with small GUI contract
canaries throughout, then WinForms and GTK3. Both reference desktops block
plain 0.1.0; full AppKit completion belongs to 0.4. Maintain AppKit preview
builds and contract checks during 0.1. Qt6, WinUI and SwiftUI require separate
admission; speculative stable APIs and placeholders are not required now.

## Twelve beta journeys

1. **First run and workspace** — acquire FacMan, run portable or setup, create or
   open a workspace, understand ownership, inspect migration, and recover.
2. **Installation library** — discover, inspect, register, and select supported
   foreign installations without modifying them.
3. **Managed local installation** — plan and confirm a fresh FacMan-owned install
   from local input; verify, repair, recover, and uninstall it.
4. **Instance lifecycle** — create, inspect, select, clone, and safely remove an
   isolated instance.
5. **Profiles and configuration** — create, select, edit, explain, export, import,
   validate, and migrate profile data.
6. **Local content and modpacks** — inspect local mods, resolve a deterministic
   set, lock it, diff, apply, roll back, export, import, and reconstruct offline.
7. **Worlds and saves** — inspect, verify, back up, clone, restore, associate,
   import/export, and apply retention policy without silent loss.
8. **Readiness and Make Ready** — explain every blocker, preview a safe plan, and
   apply only explicitly authorized owned-state changes.
9. **Play and session supervision** — preflight, Play, supervise, stop, show Last
   Run, relaunch, and recover unknown outcomes through an accepted route.
10. **Recovery** — inspect and recover interrupted workspace, content, world,
    setup, managed-install, and session operations.
11. **FacMan setup and maintenance** — portable use plus install, verify,
    damage-detect, repair, uninstall, preservation, relocation, and explicit
    upgrade/rollback policy.
12. **Diagnostics and support** — Doctor, status, actionable refusals, bounded
    logs, redacted support bundle, version, provenance, and dependency identity.

Advanced is not allowed to be the only route to an ordinary beta journey.

## What was missing or suboptimal

### P0: canonical truth was stale and fragmented

Alpha.4 implementation had been merged, but current-state, roadmap, release
programme, support, profile, package-producer, and workflow records still mixed
pre-merge alpha.4, alpha.3 historical distribution, technical-preview, and
future 1.0 models. Terminal AIDE records also remained physically in active/next
queues after their lifecycle had ended.

Remediation:

- keep historical ledgers immutable;
- establish this single beta-readiness record;
- allocate forward-only alpha identities for release-significant byte changes;
- generate human views from canonical machine records;
- archive terminal AIDE work through lifecycle tools;
- make validators derive current identity instead of embedding one alpha number.

### P0: workspace migration applied nothing

Migration inspect and plan existed, but apply deliberately refused whenever the
plan contained actions. That was a sound fail-closed alpha behavior and an
explicit beta gap.

Required closure:

- only known deterministic migrations are actionable;
- precondition hashes and target ownership are revalidated immediately before
  mutation;
- backup and journal are durable before replacement;
- apply is atomic where the platform permits it;
- interruption exposes an inspectable recovery state;
- rollback is idempotent and never silently discards user state;
- unknown versions and unknown actions continue to refuse.

Current alpha.5 result: two exact, non-destructive canonicalizations now apply
through a durable journal, preserve their sources, and roll forward interrupted
`planned` or `applying` work. Unknown actions, identities, paths, ownership, and
divergent targets refuse. This is a real migration engine, but it is not the
finished beta recovery surface: there is no public journal-inspection or
explicit rollback/recovery command, `recovery_required` requires manual
intervention, multi-action apply is not globally atomic, and retained migration
data still needs lifecycle policy.

### P0: portable/setup same-stage law lacked payload proof

Package manifests and layouts were tested, but the TCK did not prove that the
portable adapter and setup adapter contained the same canonical payload. Each
platform needs one stage inventory, adapter-specific normalization, extracted
payload comparison, relocation tests, and lifecycle proof.

Current alpha.5 result: the package TCK now has platform normalization adapters,
safe archive inventory, no-clobber evidence receipts, and a hosted workflow path
that compares Windows setup, expanded macOS pkg, and installed Linux `.run`
payloads with their canonical stages. Exact run `33603385303` passed all three
payload-equivalence checks for the recorded source revision/tree. This is
machine proof of the six candidate products, not human lifecycle evidence or
release authority.

### P0: no version-current six-product candidate workflow

The cross-platform workflow was tied to alpha.3. A manually triggered,
non-publishing candidate workflow must derive the current version, use runner
temporary/external roots, consume exact providers, create the six products,
produce checksums/evidence, and never create a tag or release.

Current alpha.5 result: `product-candidate.yml` and its bounded evidence helper
implement that non-authorizing route. They keep tag, signing, notarization,
publication, support, and release authority false. Run `33603385303`, attempt 1
qualified the exact integrated alpha.5 source/tree on all three hosted
platforms. It assembled the six product files plus workflow-internal checksums
and evidence into a verified 14-file bundle; it is not the final eight-asset
release factory. A later authorized finalization step must emit the versioned
checksum file and consolidated evidence ZIP required by
`artifact_matrix.v1.toml`.

### P0: GTK3 and AppKit were not semantic peers

WinForms consumes typed `presentation.query` and `presentation.action`. GTK3 and
AppKit still call lower-level commands and reconstruct parts of readiness and
presentation. Last Run no longer has frontend cache authority; those shells
show authoritative Last Run as unavailable until they adopt `presentation.query`.
They must consume `presentation_snapshot.v1`, send semantic actions, reject
malformed/oversized/mismatched replies, and pass the same ordinary-journey
conformance fixtures. GTK3 also needs streaming output enforcement and process
group termination rather than post-hoc truncation.

Current alpha.5 result: GTK3 transport hardening is complete and adversarially
tested, including byte caps before append, strict UTF-8/JSON/correlation rules,
timeout, cancellation, and process-group termination. GTK3 semantic convergence
and all AppKit transport/presentation convergence remain open.

### P1: large modules lacked enough ratchets

Known hotspots include the presentation service, release/package pipeline,
project-state generator, diagnostics, hermetic execution, and WinForms shell and
store. A rewrite is not justified. Characterize first, then extract scope
projectors, action handlers, page controls, view binders, lifecycle adapters, and
renderers behind unchanged contracts. Add no-growth line and complexity budgets
before splitting.

Current alpha.5 result: no-growth budgets now cover the existing hotspots and
the newly extracted package equivalence, candidate evidence, migration,
workspace I/O, content record, and content-cache modules. Migration and package
proof responsibilities were extracted without changing public commands. The
larger presentation, diagnostics, hermetic-execution, project-state, and
WinForms splits remain future bounded refactors.

### P1: performance evidence was too narrow

Resource and basic CLI budgets existed, but beta needs measured regression gates
for:

- cold and warm CLI/TUI/GUI startup;
- presentation query latency by scope;
- TUI key-to-paint latency;
- WinForms/GTK/AppKit UI-thread stalls;
- large installation, instance, mod, and save lists;
- memory ceilings and bounded process output;
- resource verification and package startup;
- cancellation, timeout, and process-tree termination.

Budgets are regression thresholds, not support claims. Baselines must be taken on
declared hardware and exact packaged bytes.

Current alpha.5 result: thresholds and bounded process-reply policy are recorded,
but exact-package startup, latency, UI-stall, memory, large-list, and declared
hardware baselines have not been measured. Performance is therefore still a
beta gate.

### P1: naming and metadata drifted

GTK and AppKit retained `.preview` identities; AppKit and WinForms contained
fixed version values; Qt retained an old target name; public and internal
architecture spellings differed. Canonical generated metadata must own public
version and product identity, while legacy internal target renames are bounded,
mapped, and performed only when they do not break consumers.

Current alpha.5 result: WinForms, GTK3, and AppKit public product/version
metadata now comes from the canonical version model; GTK uses the canonical
`io.github.julesc013.facman` desktop and icon identity. Remaining internal target
names are compatibility details, not extra public products.

### P1: profile taxonomy mixed product and laboratory surfaces

Profiles need explicit lifecycle classes:

- `active`: current Windows reference product;
- `preview`: current GTK3/AppKit product previews;
- `lab`: modern toolkit scaffolds and evidence-only experiments;
- `legacy`: compatibility package/build surfaces retained for consumers;
- `retired`: preserved identities with no executable release role;
- generated catalog: one validated index over those authored classifications.

Profile classification does not itself grant support or publication authority.

Current alpha.5 result: every authored profile now has an explicit lifecycle
classification and install-mode truth. Temporary producer exceptions remain
enumerated and cannot grant product or support authority.

## Alpha.5 implementation report

This branch has completed the highest-value safe portion of the plan without
claiming beta closure:

| Area | Implemented now | Still required |
| --- | --- | --- |
| Canonical truth | Alpha.5 identity, readiness contract, journeys, waves, promoted/synchronized source, exact candidate receipt, and archived foundation WorkUnits | Fresh candidate for any successor revision; human and authority truth |
| Migration | Two admitted actions, durable journal, source retention, roll-forward, invocation rollback | Public recovery/rollback, global atomicity, and data cleanup |
| Content/world portability | Six schemas, portable records, verified local CAS, no-clobber materialization, plan-only GC | Workspace and user routes, reconstruction, WorldBundle workflows, GC recovery |
| Product packaging | Profile lifecycle, platform stage law, payload TCK, safe ZIP inventory, and exact hosted six-product candidate | Human lifecycle, relocation/upgrade/rollback, performance/security/fault, and release receipts |
| GUIs | Canonical metadata; WinForms 4.8 build; hardened GTK transport | GTK/AppKit parity and exact accessibility/performance receipts; future toolkits stay post-beta |
| Maintainability | New module boundaries and no-growth budgets; external CMake preset roots | Continue bounded splits of the remaining hotspots and measure regression budgets |
| Repository hygiene | Prior candidate synchronized; external outputs; foundation archived | Integrate remediation, requalify source, synchronize protected branches, and clean eligible roots/refs |

The decisive remaining work is recovery and ordinary-route closure, not more
scaffolding. J03 and J06-J11, semantic parity, human accessibility and
performance, live install/Play evidence, and all release-authority gates remain
open. Exact cross-platform alpha.5 machine candidate evidence is closed only
for the recorded source revision/tree.

## Systems safely brought forward from 1.0

| System | Bring into 0.1 beta? | Bounded form |
| --- | --- | --- |
| Versioned command/presentation contracts | Yes | Freeze v1 compatibility and conformance fixtures |
| Workspace/profile/content/world migrations | Yes | Known migrations only; journaled apply now, explicit public recovery/rollback required before beta |
| Content set and lock | Yes | Local inputs, deterministic resolution, no portal |
| Modpack manifest | Yes | Export/import and offline reconstruction |
| World bundle | Yes | Identity, save metadata, backup/restore and portability |
| Content-addressed cache | Yes | Local immutable blobs, verified digest, GC policy, no network authority |
| Managed install lifecycle | Yes | Fresh explicit FacMan-owned target and local source only |
| Session journal and Last Run | Yes | One backend authority, accepted Play route required |
| Package lifecycle manifest | Yes | Stage identity, adapter identity, install/repair/uninstall receipts |
| Generated frontend DTOs/TCK | Yes | WinForms, GTK3, AppKit now; future toolkit adapters later |
| Extension points | Yes | In-process/internal interfaces and capability discovery only |
| Public plugin execution/marketplace | No | Design seam only |
| Network Mod Portal/accounts | No | Explicit unavailable capability |
| Daemon/remote control | No | No public process or protocol |
| Automatic updater execution | No | Version/report contracts only |
| Servers/fleets | No | Out of beta scope |

## Finite release waves

### Alpha.5 — content, world, migration, and truth closure

- reconcile current version, plan, project state, support, capability, profile,
  package, and documentation truth;
- apply only known workspace migrations with durable journal and roll-forward;
- keep public inspect/recover/rollback closure as an explicit beta gate;
- define `ContentSetSpec`, `ContentLock`, `ModpackManifest`, and `WorldBundle`;
- implement internal content/world records and a verified local content-addressed cache;
- keep workspace-bound offline reconstruction and user routes as explicit later gates;
- prove profile taxonomy and canonical-stage payload equivalence;
- add the non-publishing, version-current six-product candidate workflow;
- add no-growth source budgets and repair obvious metadata/naming drift.

Current exit evidence: the complete local alpha.5 promotion obligation profile
passes from external outputs, the candidate source was protected-branch
promoted/synchronized, and exact hosted platform run `33603385303` passed for
the recorded source revision/tree. Human packaged-byte receipts and every
unavailable authority gate remain explicit and pending.

### Alpha.6 — managed install and product lifecycle

- expose exact-package first-run workspace inspection/creation and the public
  migration inspect/plan/confirm/apply/resume/recover/bounded-rollback routes;
- keep the admitted migration set explicit and fail unsupported, stale,
  corrupt, interrupted, or no-clobber cases closed with durable evidence;
- add bounded streaming ZIP64/Deflate extraction and recovery for the real
  local-source corpus, or narrow the supported source contract explicitly;
- close local-source managed install plan/apply/verify/recover/repair/uninstall;
- make ownership, preconditions, cancellation, unknown outcomes, and rollback
  first-class;
- unify portable/setup lifecycle manifests and adapter extraction tests;
- define upgrade/downgrade compatibility and preserved workspace behavior;
- make macOS installer claims honest: either add maintenance operations or label
  it installation-only;
- document and test Linux runtime/setup prerequisites.

Exit: J01, the workspace-migration slice of J10, J03, and J11 are
machine-complete on every claimed platform, and Windows has a separate
exact-candidate human managed-install receipt.

### Alpha.7 — Play, sessions, and frontend convergence

- integrate ContentSetSpec, ContentLock, ModpackManifest, WorldBundle, and save
  identity through public application routes rather than internal records only;
- prove deterministic content/world export, import, clean-root offline
  reconstruction, destructive recovery, and retention without silent loss;
- qualify a fresh exact Windows Play route without importing old authority;
- make long execution durable and asynchronous so inspect/stop are not blocked by
  a global request lock;
- close all declared terminal targets, then WinForms and GTK3 ordinary
  workflows through the typed presentation snapshot/action seam; keep AppKit
  preview checked without requiring its 0.4 graduation;
- add Content, Saves, Activity/Recovery, and Settings/Support journey parity;
- add streaming transport caps, strict UTF-8/JSON/correlation checks, timeout,
  cancellation, and process-tree termination;
- retain the exact hosted package baseline while adding semantic-convergence,
  human lifecycle, accessibility, and performance receipts for macOS Intel and
  Ubuntu GTK3/X11.

Exit: J06-J10 and the remaining local terminal journeys pass machine
conformance on declared targets, WinForms/GTK3 reference workflows are
complete, exact Windows Play has its own verdict, and preview claims match
their bounded evidence.

### Feature-freeze alpha.N

- refuse entry until all twelve machine journeys are already closed;
- require complete human CLI, JSON/RPC, full-screen/linear TUI and WinForms/GTK3
  ordinary parity; the Terminal v1 checkpoint alone is not final 0.1 completion;
- freeze command, state, package, TCK, and presentation compatibility;
- complete security, fuzz/adversarial, accessibility preflight, performance, and
  reproducibility gates;
- build twice from separate clean roots and compare deterministic products where
  the native format permits it;
- document any unavoidable nondeterminism, especially native macOS package
  metadata, and bind semantic payload equivalence instead;
- generate the exact beta human packet.

Exit: no release-blocking machine gap, no unknown skip, no stale canonical truth,
and no unowned high-severity defect.

### Exact `0.1.0-beta.1`

Allocate beta only from an exact human-tested stabilization commit. Build all six
products from that commit and exact provider locks. Bind source, tree, toolchains,
stage digests, product hashes, checksums, SBOM, provenance, test evidence, and
human receipts. Signing, notarization, GitHub publication, and support promotion
remain separate explicit authorities.

## Beta release gates

Machine gates:

- canonical plan, state, version, profiles, package producers, support, docs, and
  generated metadata agree;
- native, Python, strict, schema, package, security, AIDE, and hygiene suites pass;
- required/unknown skip count is zero;
- exact providers materialize outside the checkout and their locks match;
- all six products build from external roots;
- portable/setup payload equivalence passes per platform;
- relocation and lifecycle tests pass;
- command, presentation, migration, and package compatibility TCKs pass;
- no toolkit placeholder appears in beta product/support truth;
- no in-checkout build/dist/out/tmp root or unowned worktree remains.

Human gates on exact bytes:

- Windows 10/11 x64 first run, portable, setup, verify, damage/repair, uninstall,
  preservation, managed local install, real Play, stop, Last Run, relaunch, and
  recovery;
- keyboard-only use, focus order, UI Automation names, Narrator, high contrast,
  and 100/150/200-percent DPI on WinForms;
- System Native screenshots, platform HIG/convention review, native-control and
  OEM+ delta inventory, visual hierarchy, and platform-appropriate interaction
  acceptance for every claimed GUI;
- localization/text-expansion and scaling review, including clipped, elided,
  bidirectional, missing-key, and long-path states;
- large-list and live-console responsiveness with accessible progress,
  cancellation, and no hidden main-thread stalls;
- macOS Intel AppKit launch and pkg behavior on the declared baseline;
- Ubuntu x64 GTK3/X11 launch and `.run` behavior on the declared baseline;
- performance observations on declared reference machines;
- an explicit Pass, Fail, or Inconclusive receipt bound to each asset hash.

Authority gates:

- beta version allocation;
- tag creation from the exact stabilization commit;
- signing credentials and signing operation;
- Apple notarization;
- prerelease publication;
- support claim activation.

No machine test grants an authority gate.

## Refactor and maintenance programme

1. Characterize behavior with golden and malicious fixtures.
2. Add no-growth line/complexity budgets to existing hotspots.
3. Extract cohesive modules behind unchanged interfaces.
4. Add focused tests for each extracted boundary.
5. Measure performance before and after; reject regressions without an explicit
   reviewed budget change.
6. Delete compatibility code only after all consumers and profiles have migrated.
7. Keep public compatibility records append-only and published Git history/tags
   immutable.

Priority extractions:

- presentation scope projectors and action handlers;
- lazy scope queries and immutable derived-state caching;
- WinForms page controls, view binders, dialogs, and action services;
- GTK/AppKit generated DTO decoders and shared conformance fixtures;
- package stage builder versus platform adapter versus evidence writer;
- project-state collectors versus renderers;
- diagnostics collectors versus redaction and archive writing.

## Repository and disk hygiene

- Use `task/* → dev → main → dev`; delete merged task branches after exact-head
  confirmation and no open PR dependency.
- Keep at most two secondary worktrees and never create nested or drive-root
  worktrees.
- Build/package/test only through `tools/dev.py` or marker-owned external task
  roots.
- Replace source-local CMake preset output defaults with external roots.
- Retire ignored `bin`, `obj`, `__pycache__`, and tool-cache directories only by
  exact validated path; never use broad `git clean -fdX`.
- Archive terminal AIDE records through AIDE lifecycle commands, not manual moves.
- Preserve unique abandoned history in one verified recovery bundle before
  deleting references.
- Keep release tags immutable and delete merged task branches.

## Definition of done

FacMan `0.1.0-beta.1` is done only when all twelve journeys are machine-complete,
the exact six products are reconstructed and hash-bound, portable/setup stage
equivalence passes, the required human receipts pass on their claimed platforms,
the release model contains no stronger claim than its evidence, external
authority has been explicitly granted, and the protected branches and workspace
are synchronized and clean.

Until then the correct status is an alpha implementation candidate progressing
toward beta—not a beta release with caveats.
