# Three-repository convergence strategy

Status: governing synthesis for bounded follow-up work

Last reviewed: 2026-08-05

Repositories: `factorio-launcher`, `universal-launcher`, `universal-setup`

External proof consumer: `dominium`

The later multi-consumer productization decision, including Compact Cassette
Catalogue and capability-selective provider consumption, is recorded in
`docs/architecture/universal_multi_consumer_productization.md`. That record
extends this convergence strategy without changing its authority boundary.

Current preparation adds no physical migration. Provider-neutral contracts,
the synthetic cross-provider TCK, FacMan workspace-root authority, successor
route definition and the FacMan release compiler are recorded complete. The
next convergence boundary is exact source/static/shared/relocated/private-
runtime equivalence, followed by a separately reviewed FacMan SDK adoption.
Both remain non-authorizing and preserve current consumer pins until their
canonical WorkUnits satisfy dependency and decision gates.

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

The following identities were reconciled on 2026-08-05. Canonical machine
records remain authoritative; this table explains the reviewed roles.

| Role | Observed revision | Meaning |
| --- | --- | --- |
| FacMan reviewed `dev` | `715422842c7db8ca52162091ca70026b99768da2` | Provider-input phase integrated; semantic-equivalence base |
| FacMan `origin/main` | `b70be10696855628c6d2948eb016c8424912e14e` | Canonical source; intentionally not advanced by this convergence phase |
| FacMan-consumed ULK pin | `7fc25340623131ba86c08dca4fb8a43b18a4520d` | Qualified provider identity |
| ULK canonical `main` | `1cafe4054297cc11e02458b83d230db0cd064471` | Accepted relocatable SDK source |
| ULK synchronized `dev` | `7d4fd8e25a8d529279c4ad18d983e9cd51839eb7` | Contains canonical main with the same source tree |
| FacMan-consumed USK pin | `3048128963dc718a7c38c1cfcdda9e813a23b0db` | Qualified provider identity |
| USK canonical `main` | `32488fc13bd2439f9f6e52e83a97f6da345a7650` | Accepted relocatable SDK source |
| USK synchronized `dev` | `6dc48673d54fb27ac4e8949da6f43275d36c9622` | Contains canonical main with the same source tree |

FacMan's `FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-REVALIDATION-04` is
superseded and archived before observer self-test. It is not resumable and
grants no authority. Successor route definition v1 is immutable and binds the
old consumed provider set. If conformance selects new provider identities, a
fresh non-authorizing v2 definition must precede source closure. No accepted
real-Play route or successor stage exists; source closure, qualification,
observer capture, prepare, permit issuance, execution, verdict, and route
promotion remain separate boundaries.

Tracked source cannot truthfully contain the hash of the commit that contains
itself. Live checkout and provider-head truth must therefore be emitted as a
post-checkout CI/local observation artifact. Tracked project state records a
reviewed checkpoint and the immutable identities used by that checkpoint.

## Canonical truth order

The convergence programme uses one durable order: canonical plan, component
ownership, workspace lock, compact current state, durable architecture and
contracts, out-of-tree live observation, run-specific generated prompt/profile,
then historical report or archive. Each source remains bounded to its domain;
for example, live checkout evidence can update a local HEAD fact but cannot
change a pin or authority. Master prompts are run snapshots. Model, reasoning,
and agent-topology choices belong to the generated run profile rather than this
architecture or the canonical plan.

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
commands and clients              installable package/source archives
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

Universal Setup permanently owns decoding and bounded materialization of
installable-software package and source archives, target authority, every setup
mutation and recovery operation, setup transactions, installed-state
ownership, and audit. It excludes product rules and UI, launch sessions,
Factorio mods/modpacks, saves/worlds/scenarios, snapshots, backups,
diagnostic archives, and accounts.

Universal Launcher permanently owns command, client, and transport contracts;
owned results; durable operation identity and outcome; generic references and
persistence; launch-plan staleness; execution sessions and process
containment; launcher journals; and the preference mechanism. It excludes
setup mutation, Factorio or Dominium semantics, and product presentation.

FacMan permanently owns Factorio discovery, installation classification,
InstanceSpec and Binding, readiness, profiles, mods/modsets/modpacks,
saves/worlds/scenarios, snapshots, backups, diagnostic archives, launch intent,
policy and evidence, product presentation, native shells, and packaging. It
excludes a generic installable-software setup engine and permanent generic
launcher infrastructure.

Dominium permanently owns product identity and compatibility, component
recipes, product release policy, content packs, product launch and readiness
interpretation, and branded shells. It excludes parallel generic setup or
launcher kernels.

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

Revalidation-04 has been formally superseded. Preserve its retained stage as
historical evidence and do not restart it. A successor may be constructed only
after the pre-successor hardening chain, and then only through fresh route,
source, qualification, stage, observer, prepare, permit, execution, verdict,
and promotion identities.

Provider-side additive work may proceed independently when it is not consumed
or repinned by FacMan. The relocatable ULK and USK SDKs are accepted on
provider `main` and synchronized into `dev`; FacMan deliberately retains its
older accepted pins while canonical cross-mode conformance runs.

### Lane 1: truthful publication and bounded provider hardening

- Emit exact checkout and provider reachability as an out-of-tree observation
  artifact bound to the CI checkout SHA.
- Render machine JSON and human Markdown from the same observation.
- Distinguish reviewed tracked checkpoint truth from live checkout truth.
- ULK owned-response validation/copy/release is accepted on provider `main`,
  including zero/default and explicit 16 MiB budgets, without replacing
  borrowed v1 APIs or switching FacMan.
- USK strict archive-request decoding and absolute normalized local UTF-8
  source identity are accepted on provider `main` without switching FacMan.

### Lane 2: pre-successor C1 hardening

1. Harden the current WinForms process transport so malformed, mismatched,
   exhausted, timed-out, interrupted, and post-dispatch unknown outcomes fail
   closed and the complete process tree is contained.
2. Bind the supported shell to the exact package-relative backend, source,
   build, protocol, and contract-set identity; reject arbitrary `PATH`,
   environment, working-directory, or stale-copy substitution.
3. Classify and bind workspace roots before mutation; refuse foreign nonempty,
   link/reparse, changed, and inspection-failed roots.

### Lane 3: fresh successor Play qualification

1. Define a new exact route and candidate after Lane 2 is accepted.
2. Prove remote-only source closure from empty clones with no alternate,
   shallow, promisor, replace-ref, or unreviewed-config ambiguity.
3. Qualify the fresh candidate and prepare a separately reviewable new stage.
4. Gate observer, prepare, permit, two launches, verdict, route capability, and
   promotion separately. Only Pass can advance the route.

### Lane 4: FacMan product convergence

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

### Lane 5: frontend client convergence after C1

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

### Lane 6: state and execution extraction

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

### Lane 7: second-consumer qualification

Dominium first consumes read-only inspection, plan preview, diagnostics and
structured refusal through ULK/USK. Only a genuinely different second consumer
can qualify shared permit or presentation concepts. The permit kernel remains
in FacMan until that proof or an explicit permanent-retention decision.

### Lane 8: production Setup lifecycle

After strict request codecs:

1. Bind plans to stable source/entry manifests.
2. Stream one stored entry at a time into owned staging with SHA/CRC checks.
3. Add bounded DEFLATE with ratio, output, memory and time limits.
4. Journal entry-level completion and prove restart-safe recovery.
5. Prove Dominium consumption, then reconcile FacMan managed installs.

Streaming is a contract and recovery programme, not a mechanical replacement
of byte vectors.

### Lane 9: independent SDKs and distribution

Retain exact sibling/source-workspace mode for source-closure proof. Add an
installed SDK mode with namespaced CMake packages only after public surfaces
are honest. Initially export stable C APIs; do not expose private C++ lifecycle
internals or unimplemented client symbols as supported SDK targets.

## Cross-repository delivery protocol

Every extraction follows the same train:

1. A FacMan or Dominium need demonstrates the boundary.
2. Product-specific and product-neutral behavior are separated.
3. The provider task lands additive contract, implementation and conformance
   proof on provider `dev`.
4. Consumer canaries test the exact provider `dev` SHA without changing any
   tracked consumer lock.
5. The provider `dev` change reaches canonical `main` through reviewed
   promotion.
6. The product updates one exact provider-`main` pin in a separate, reversible
   adoption change.
7. Empty-clone source closure and consumer integration are proven.
8. The product incubator is deleted or reduced to a thin compatibility adapter.

There is no atomic three-repository merge. Producer commits precede consumer
switches; each switch can be reverted independently. A provider pin never
moves merely to make repositories appear equally active.

The accepted ULK and USK SDK trains are canonical at `1cafe405...` and
`32488fc...`, with synchronized dev heads `7d4fd8e...` and `6dc4867...`.
FacMan has not repinned either provider. Provider-first ordering remains mandatory
only when a consumer adopts or repins a provider contract or implementation.
It does not serialize independent documentation, observation, additive
provider hardening, or other
work that changes no consumed provider identity.

## Required provider-health observation

The generated checkout observation must report, for both providers:

- local `origin/main` tracking-ref revision;
- local `origin/dev` tracking-ref revision and whether `main` is its ancestor;
- exact consumed pin;
- pin checkout match;
- pin reachability from that local tracking ref;
- public ABI version;
- last accepted provider capability;
- current consumer proof;
- pending incubator extractions and their trigger;
- whether any new product authority was opened.

It must also report `local_tracking_ref_only`, `fetch_performed=false`, and
`fetched_at=null`. Unknown or unavailable Git/provider evidence is reported as
unknown, never as healthy. This offline observation is not current remote
evidence and cannot satisfy source closure; that claim requires the separate
fetched empty-clone proof. Tracked README text must not impersonate either.

## Commit and review discipline

- One bounded concern per commit; code, contract, tests and focused docs stay
  together when separating them would make an intermediate commit invalid.
- Provider and FacMan task branches start from an exact verified `origin/dev`.
- Provider `main` accepts reviewed `dev` promotions or explicit hotfixes only;
  hotfixes are synchronized back to `dev` without force-resetting either ref.
- Existing user changes and qualified worktrees remain untouched.
- Every commit passes focused checks; every branch passes the complete
  repository suite before sharing.
- Provider task branches may be shared after mechanical checks. Protected
  branch merges, release tags, signing, publication, Factorio execution,
  observer capture, verdict and route promotion remain explicit authorities.

## Non-goals

Do not:

- merge the three repositories or create a fourth common repository;
- copy unrelated FacMan commits into provider `dev` or create no-op provider
  commits merely to show activity;
- pin canonical product builds to provider `dev` rather than exact commits
  reachable from provider `main`;
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
