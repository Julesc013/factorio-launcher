# FacMan Decisions

- Decision: `World` is the product and UX aggregate, while persistence remains
  decomposed into portable `WorldSpec`, machine-local `WorldBinding`, computed
  `WorldReadiness`, and a `WorldView` projection.
  - Status: accepted target architecture
  - Rationale: Players need one coherent playable concept without coupling
    portable intent to paths, credentials, providers, caches, or mutation
    records on one machine.

- Decision: Authority-bearing operations use short-lived, plan-bound
  `OperationPermit`s rather than long-lived capability grants.
  - Status: accepted target architecture
  - Rationale: Exact resources, evidence, policy, machine, provider identities,
    principal, nonce, and expiry must stay bound to the reviewed plan. Global
    admission and each provider revalidate independently.

- Decision: World readiness composes federated typed subplans and never becomes
  a universal mutation kernel.
  - Status: accepted target architecture
  - Rationale: FacMan owns Factorio and player policy, Universal Launcher owns
    runnable-state orchestration, and Universal Setup owns installation and
    host mutation.

- Decision: The host-environment programme is a parallel support lane and does
  not block a native Play route that does not depend on a host remedy.
  - Status: accepted
  - Rationale: Early list, inspect, doctor, support export, and user-scoped
    Sandbox profiles are useful, but World, operation permits, hermetic Play,
    and player validation remain the primary product path.

- Decision: Human-readable portable records are authoritative and performance
  indexes are rebuildable derived caches.
  - Status: accepted target architecture
  - Rationale: Portability and recovery must not depend on one opaque database;
    caches need explicit dependencies, freshness, and invalidation.

- Decision: Host readiness is evaluated against a versioned workflow
  requirement profile, never one global machine-health score.
  - Status: accepted
  - Rationale: Native Play, Sandbox support, WSL development, server hosting,
    and release work can be ready or blocked independently on one machine.

- Decision: Host remediation follows a formal least-invasive hierarchy and
  begins with a read-only contract spine.
  - Status: accepted
  - Rationale: A FacMan-local choice or user-scoped generated artifact is
    preferred over privileged policy, shared-service reset, or external-owner
    mutation. The first apply-capable host feature is a no-admin Windows
    Sandbox profile, not a registry repair.

- Decision: Privileged host repair requires typed signed recipes, explicit
  rollback classes, a one-shot broker, restart/resume, and shared-resource
  coordination.
  - Status: accepted
  - Rationale: Arbitrary scripts, global authority flags, and uncoordinated
    HNS/Hyper-V/WSL/Sandbox changes cannot provide bounded product safety.

- Decision: The product promise is "choose a world, press Play, and remain in
  control of everything that changes."
  - Status: accepted
  - Rationale: FacMan is a world-centric environment manager, not a command
    catalogue or a generic architecture demonstration.

- Decision: Execution exposes two distinct guarantees: instance-isolated and
  hermetic standalone.
  - Status: accepted
  - Rationale: Steam-aware use may change explicitly enumerated Steam-owned
    state and therefore cannot truthfully carry the hermetic claim. Standalone
    execution must fail on any persistent external change.

- Decision: M3 existing-portable adoption is authorised backlog after the
  playable alpha.
  - Status: accepted
  - Rationale: More setup authority does not unlock the current world-to-Play
    bottleneck. Existing M3 read-only and planning proof remains preserved.

- Decision: Refactor now only within the Play-driven convergence ceiling.
  - Status: accepted
  - Rationale: The current central dispatch and configuration reads need a
    narrow seam, but a full domain migration, plugin framework, daemon, AI
    layer, or repository reorganisation would add risk before user evidence.

- Decision: Current product readiness is tracked as separate dimensions.
  - Status: accepted
  - Rationale: Playability, workflow readiness, safety authority, platform
    support, release authenticity, compatibility, and user validation cannot
    be compressed into a truthful percentage.

- Decision: AIDE Lite is development governance tooling, not runtime.
  - Status: accepted
  - Rationale: FacMan production packages target native C/C++ kernels and
    platform frontends. AIDE provides repo-local context, validation, review,
    and advisory planning.

- Decision: Retire `source/` and use ownership roots.
  - Status: accepted
  - Rationale: `runtime/`, `apps/`, `content/`, `contracts/`, and `release/`
    describe ownership more clearly than a broad source bucket. `src/`,
    `source/`, `data/`, `schemas/`, and `packaging/` are forbidden retired
    roots.

- Decision: CLI, TUI, WinForms, AppKit, GTK, and Qt are sibling frontends.
  - Status: accepted
  - Rationale: No frontend should sit on top of another frontend as its real
    foundation. All frontends call the command graph, daemon, or C ABI.

- Decision: Universal Setup and Universal Launcher are sibling repos, not
  Factorio subtrees.
  - Status: accepted
  - Rationale: Setup mutation and launcher orchestration have their own public
    ABI, runtime, contract, content, release, docs, tests, and tool surfaces.

- Decision: Treat the public C ABI as an experimental correctness floor.
  - Status: accepted
  - Rationale: Size checks, ownership rules, ABI queries, and native smoke prove
    a bounded layout discipline; they do not yet prove stable third-party
    compatibility.

- Decision: Windows read-only discovery is implemented and is no longer the
  next product task.
  - Status: accepted
  - Rationale: Provider tests cover registry and Steam roots, bounded VDF
    parsing, standalone roots, de-duplication, malformed metadata, long and
    Unicode paths, read-only behavior, and junction refusal. Registry truth and
    instance isolation are the next gaps.
