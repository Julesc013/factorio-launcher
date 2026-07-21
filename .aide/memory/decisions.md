# FacMan Decisions

- Decision: `Instance` is the product and UX aggregate, composed from an
  installation/version, profile, resolved preset provenance, modpack/modset
  lock, account reference, settings, resources, and optional saves. Persistence
  remains decomposed into portable `InstanceSpec`, machine-local
  `InstanceBinding`, computed `InstanceReadiness`, and `InstanceView`.
  - Status: accepted target architecture; supersedes the earlier World aggregate
  - Rationale: Players select a complete game environment and expect Factorio's
    own menu. A save/world is optional content inside that environment, not the
    required identity of every launch.

- Decision: `facman play <instance>` defaults to the `menu` launch
  intent.
  - Status: accepted target architecture
  - Rationale: Direct save loading, new-game setup, benchmarks, and headless
    servers are explicit optional intents and must never be inferred from the
    presence of saves or other instance content.

- Decision: Profiles are typed, presets initialize or explicitly upgrade
  instances, and reproducible mod content separates `ModsetSpec`, `ModsetLock`,
  and `ModpackBundle`.
  - Status: accepted target architecture
  - Rationale: Reuse must retain versioned provenance without creating hidden
    mutable dependencies or confusing desired content with an exact artifact
    closure.

- Decision: Account configuration is decomposed into platform, Factorio,
  player-identity, and server-credential bindings.
  - Status: accepted target architecture
  - Rationale: These identities have different owners and trust boundaries;
    instance records contain references and non-secret presentation state, not
    credentials or entitlement assertions.

- Decision: World/save portability remains a secondary content lane under
  `FACMAN-WORLD-BUNDLE-AND-SAVE-COMPATIBILITY-01`.
  - Status: accepted target architecture
  - Rationale: Save compatibility and import/export remain valuable without
    making a save the required identity of ordinary Play.

- Decision: Authority-bearing operations use short-lived, plan-bound
  `OperationPermit`s rather than long-lived capability grants.
  - Status: accepted target architecture
  - Rationale: Exact resources, evidence, policy, machine, provider identities,
    principal, nonce, and expiry must stay bound to the reviewed plan. Global
    admission and each provider revalidate independently.

- Decision: Instance readiness composes federated typed subplans and never becomes
  a universal mutation kernel.
  - Status: accepted target architecture
  - Rationale: FacMan owns Factorio and player policy, Universal Launcher owns
    runnable-state orchestration, Universal Setup owns installation and host
    mutation, and credential/platform providers retain account secrets and
    session enforcement.

- Decision: The host-environment programme is a parallel support lane and does
  not block a native Play route that does not depend on a host remedy.
  - Status: accepted
  - Rationale: Early list, inspect, doctor, support export, and user-scoped
    Sandbox profiles are useful, but Instance, operation permits, hermetic Play,
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

- Decision: The product promise is "create any number of independent Factorio
  setups, select one, and launch the normal game as though Factorio had always
  been installed and configured exactly that way."
  - Status: accepted
  - Rationale: FacMan is an instance-centric environment manager, not a command
    catalogue, a save-only launcher, or a generic architecture demonstration.

- Decision: Execution exposes two distinct guarantees: instance-isolated and
  hermetic standalone.
  - Status: accepted
  - Rationale: Steam-aware use may change explicitly enumerated Steam-owned
    state and therefore cannot truthfully carry the hermetic claim. Standalone
    execution must fail on any persistent external change.

- Decision: M3 existing-portable adoption is authorised backlog after the
  playable alpha.
  - Status: accepted
  - Rationale: More setup authority does not unlock the current instance-to-menu
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
