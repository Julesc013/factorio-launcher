# Three-repository convergence strategy

Status: governing synthesis for bounded follow-up work

Last reviewed: 2026-08-03

Repositories: `factorio-launcher`, `universal-launcher`, `universal-setup`

External proof consumer: `dominium`

## Verdict

The repository split is correct. The implementation distribution is not yet
fully converged.

- Universal Setup is the mature, exclusive installed-software mutation
  authority. It has not been absorbed into FacMan.
- Universal Launcher is a valid contract kernel, but it is smaller than its
  declared permanent ownership. Several launcher-neutral implementations are
  still explicitly incubated in FacMan.
- FacMan is the Factorio product composition and the first serious Universal
  Launcher consumer. It must retain Factorio policy and presentation while
  progressively replacing generic incubators with thin provider adapters.
- Dominium is the required second-product proof. Its product shells and recipes
  belong in Dominium; generic setup or launcher kernels do not.

The governing objective is:

> Portable semantics, native presentation, constrained branding, explicit
> capability adaptation, and one authority for each effect class.

This document reconciles the detailed platform plan, component-ownership
manifest, current C1 cut line, and provider roadmaps. It does not supersede the
canonical execution graph in `release/index/plan.v1.toml`, grant product
authority, move a provider pin, or approve a release.

## Verified starting point

The following identities were re-observed locally after fetching remotes on
2026-08-03. They are evidence for this review, not values to maintain manually
in prose.

| Role | Observed revision | Meaning |
| --- | --- | --- |
| FacMan `origin/dev` | `84a0d496b1d4b71ad239e720390e914005dd4611` | Current integration base |
| FacMan `origin/main` | `133da925af13d475c959a336e0b0eec0427a0381` | Canonical published source |
| FacMan-consumed ULK pin | `7fc25340623131ba86c08dca4fb8a43b18a4520d` | Qualified provider identity |
| ULK `origin/main` | `7f4312faf2f1ac2856a51393fef0ec49fc276a78` | Merge commit containing the pin with the same tree |
| FacMan-consumed USK pin | `3048128963dc718a7c38c1cfcdda9e813a23b0db` | Qualified provider identity |
| USK `origin/main` | `3048128963dc718a7c38c1cfcdda9e813a23b0db` | Canonical provider identity |

FacMan remains at
`FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-REVALIDATION-04`, awaiting an operator.
No accepted real-Play route exists. Observer capture, prepare, permit issuance,
Factorio execution, verdict, and route promotion remain separate authority
boundaries.

Tracked source cannot truthfully contain the hash of the commit that contains
itself. Live checkout and provider-head truth must therefore be emitted as a
post-checkout CI/local observation artifact. Tracked project state records a
reviewed checkpoint and the immutable identities used by that checkpoint.

## Target system

```text
Native product shells
CLI | TUI | WinForms | AppKit | GTK 3 | later WinUI/SwiftUI/Kirigami
                           |
                           v
Product presentation and composition
FacMan / Factorio                  Dominium
                           |
             +-------------+-------------+
             |                           |
             v                           v
Universal Launcher                Universal Setup
commands and clients              source/package inspection
operation outcomes                target authority
references and plans              install lifecycle
execution sessions                transaction and recovery
process containment               installed state and audit
```

Dependency law:

```text
FacMan   -> Universal Launcher
FacMan   -> Universal Setup
Dominium -> Universal Launcher
Dominium -> Universal Setup

Universal Launcher -> Setup handoff/port only
Universal Setup    -X-> Universal Launcher or any product
Frontend           -X-> process, setup, credential, or product authority
Product            -X-> direct installed-software mutation
```

## Permanent ownership

| Owner | Permanent responsibilities | Explicit exclusions |
| --- | --- | --- |
| Universal Setup | Package/source inspection; target authority; install, verify, repair, update, move, uninstall, rollback and recovery; setup transactions; installed-state ownership and audit | Product rules and UI, launch sessions, mods, saves, accounts |
| Universal Launcher | Command/client/transport contracts; owned results; durable operation identity/outcome; generic references and persistence; launch-plan staleness; execution sessions and process containment; launcher journals and preference mechanism | Setup mutation, Factorio/Dominium semantics, product presentation |
| FacMan | Factorio discovery, installation classification, InstanceSpec/Binding, readiness, profiles, mods, saves, backups, launch intent/policy/evidence, product presentation, native shells, packaging | Generic setup engine or permanent generic launcher infrastructure |
| Dominium | Product identity and compatibility, component recipes, product release policy, content packs, product launch/readiness interpretation and branded shells | Parallel generic setup/launcher kernels |

The machine-readable authority is
`release/index/component_ownership.v1.toml`. Every temporary incubator must
retain a final owner, current consumer, extraction dependency, expiry trigger,
latest review, and retention justification. New product-neutral incubation is
not allowed without the same data.

## Interface strategy

Frameworks, platform conventions, and design languages are different layers.
The product shares meaning, not widgets or a universal skin.

The stable direction is:

```text
domain and authority
  -> command and operation contracts
  -> FacMan-local presentation service
  -> immutable snapshots and semantic actions
  -> native platform adapters
```

No toolkit type crosses the presentation boundary. Primary journeys use
hand-designed native views; generated metadata forms remain an Advanced and
diagnostic surface.

Classic profiles are WinForms, AppKit, and GTK 3/X11. Modern profiles are
WinUI 3, SwiftUI for macOS, and Qt Quick Controls with Kirigami, only after the
shared semantic model and classic conformance are stable. AppKit and SwiftUI
both follow macOS conventions; GTK 3 must not copy GTK 4/Libadwaita recipes;
Qt has no single built-in design language; WinForms must use its adaptive
layout, DPI, keyboard, and accessibility facilities rather than fixed pixels.

Appearance has three explicit tiers:

1. System Native: mandatory compatibility and accessibility baseline.
2. OEM+: native controls with bounded FacMan branding in product surfaces.
3. Custom Theme: optional declarative data/assets, never executable styling.

Accessibility, high contrast, reduced motion/transparency, and safe-mode
fallback override every theme choice.

## Execution programme

### Gate 0: preserve the qualified candidate

Either execute revalidation 04 exactly as qualified or formally supersede it.
Until then, do not change candidate, observer, policy, permit, evidence,
provider-pin, operation-ID, native-routing, or route semantics beneath the
staged qualification.

Provider-side additive work may proceed on isolated task branches only when it
is not consumed or repinned by FacMan and cannot alter the qualified source
closure.

### Lane 1: truthful publication and bounded provider hardening

- Emit exact checkout and provider reachability as an out-of-tree observation
  artifact bound to the CI checkout SHA.
- Render machine JSON and human Markdown from the same observation.
- Distinguish reviewed tracked checkpoint truth from live checkout truth.
- Add ULK owned-response validation/copy/release without replacing borrowed v1
  APIs or switching FacMan.
- Parse USK archive-inspection requests with its existing strict bounded JSON
  parser and exact closed-object law.

### Lane 2: frontend client convergence after the Play verdict

1. Consolidate generic request, response, transport, operation-result,
   refusal, redaction, and size-budget schemas in ULK.
2. Add a frontend-neutral ULK client with owned response lifetime, exact
   operation identity, trusted backend resolution, package/build handshake,
   bounded streaming I/O, cancellation/timeout law, and process-tree
   containment.
3. Replace WinForms, AppKit, and GTK process implementations with thin P/Invoke
   or C wrappers.
4. Prove direct/process and cross-toolkit semantic conformance before removing
   compatibility adapters.

No daemon is introduced without measured operation-survival or multi-client
need.

### Lane 3: FacMan product convergence

Keep `facman.presentation.v0` product-local and centralize it once in the
authoritative FacMan backend:

```text
presentation.snapshot
presentation.action
presentation.refresh
```

Frontends render immutable views, submit semantic actions, display progress,
and announce accessibility state. They do not reconstruct workspace truth or
reinterpret unknown outcomes as success.

### Lane 4: state and execution extraction

Extract additively, one independently revertible provider/consumer pair at a
time:

1. Universal reference persistence plus Factorio extension documents.
2. Launcher metadata journal, separate from USK mutation transactions and
   FacMan content/save/mod transactions.
3. Namespaced preference-store mechanism, leaving keys/defaults/policy in the
   product.
4. Product-neutral execution session, process identity, containment, bounded
   I/O, cancellation and terminal classification.

Migrations use characterize -> dual read -> validate -> write -> rollback.
They never silently rewrite or destructively move existing records.

### Lane 5: second-consumer qualification

Dominium first consumes read-only inspection, plan preview, diagnostics and
structured refusal through ULK/USK. Only a genuinely different second consumer
can qualify shared permit or presentation concepts. The permit kernel remains
in FacMan until that proof or an explicit permanent-retention decision.

### Lane 6: production Setup lifecycle

After strict request codecs:

1. Bind plans to stable source/entry manifests.
2. Stream one stored entry at a time into owned staging with SHA/CRC checks.
3. Add bounded DEFLATE with ratio, output, memory and time limits.
4. Journal entry-level completion and prove restart-safe recovery.
5. Prove Dominium consumption, then reconcile FacMan managed installs.

Streaming is a contract and recovery programme, not a mechanical replacement
of byte vectors.

### Lane 7: independent SDKs and distribution

Retain exact sibling/source-workspace mode for source-closure proof. Add an
installed SDK mode with namespaced CMake packages only after public surfaces
are honest. Initially export stable C APIs; do not expose private C++ lifecycle
internals or unimplemented client symbols as supported SDK targets.

## Cross-repository delivery protocol

Every extraction follows the same train:

1. A FacMan or Dominium need demonstrates the boundary.
2. Product-specific and product-neutral behavior are separated.
3. The provider lands additive contract, implementation and conformance proof.
4. The provider change reaches canonical `main`.
5. The product updates one exact pin in a separate, reversible change.
6. Empty-clone source closure and consumer integration are proven.
7. The product incubator is deleted or reduced to a thin compatibility adapter.

There is no atomic three-repository merge. Producer commits precede consumer
switches; each switch can be reverted independently. A provider pin never
moves merely to make repositories appear equally active.

## Required provider-health observation

The generated observation must report, for both providers:

- canonical-main revision;
- exact consumed pin;
- pin checkout match;
- pin reachability from canonical main;
- public ABI version;
- last accepted provider capability;
- current consumer proof;
- pending incubator extractions and their trigger;
- whether any new product authority was opened.

Unknown or unavailable Git/provider evidence is reported as unknown, never as
healthy. Tracked README text must not impersonate a live remote query.

## Commit and review discipline

- One bounded concern per commit; code, contract, tests and focused docs stay
  together when separating them would make an intermediate commit invalid.
- Provider branches start from verified `origin/main`; FacMan task branches
  start from verified `origin/dev`.
- Existing user changes and qualified worktrees remain untouched.
- Every commit passes focused checks; every branch passes the complete
  repository suite before sharing.
- Provider task branches may be shared after mechanical checks. Protected
  branch merges, release tags, signing, publication, Factorio execution,
  observer capture, verdict and route promotion remain explicit authorities.

## Non-goals

Do not:

- merge the three repositories or create a fourth common repository;
- create provider `dev` branches for symmetry;
- bulk-move FacMan runtime directories into ULK;
- allow Dominium to retain a parallel generic Setup kernel;
- universalize FacMan presentation before a second product proves the records;
- implement a daemon, actor system, distributed lock, dynamic plugin system,
  embedded browser, or executable theme without a measured need and trust gate;
- add modern GUI toolkits before the live classic reference journey is
  accepted;
- treat compilation, test count, commit volume, or a closed frontend as product
  authority or proof that effects did not occur;
- repin the active Play candidate to consume preparatory provider branches.

## Completion test

The programme is complete when provider status is exact and reproducible;
generic launcher incubators have moved behind proven ULK APIs; Setup mutation
remains solely in USK; FacMan frontends are native projections of one product
service; Dominium is a real second consumer; source and installed SDK modes are
equivalent; migrations and interrupted operations recover truthfully; and each
release claim has platform, accessibility, package, source-closure and
authority evidence appropriate to that claim.
