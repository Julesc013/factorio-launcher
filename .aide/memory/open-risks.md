# FacMan Open Risks

- Risk: A monolithic persisted `Instance` could couple portable player intent to
  machine paths, providers, credentials, caches, and operation history.
  - Status: active design risk
  - Mitigation: Keep `InstanceSpec`, `InstanceBinding`, computed readiness, and
    `InstanceView` separate, with versioned logical references between them.

- Risk: Instance readiness could become a new cross-repository mutation kernel.
  - Status: active design risk
  - Mitigation: Compose immutable typed subplans while preserving FacMan,
    Universal Launcher, and Universal Setup ownership and provider-side
    independent validation.

- Risk: Long-lived or machine-wide capability grants could be replayed against
  stale plans or substituted targets.
  - Status: active design risk
  - Mitigation: Use short-lived operation permits bound to exact plan,
    resource, evidence, machine, provider, policy, principal, nonce, and expiry;
    require independent revalidation immediately before every effect.

- Risk: Host support work could delay the first trustworthy playable journey.
  - Status: active
  - Mitigation: Keep host inspection and remedies on a parallel lane. They may
    block only an instance whose selected workflow actually requires that host
    capability, never unrelated instance, permit, Play, or alpha work.

- Risk: Portable bundles could leak local secrets or unlawfully redistribute
  proprietary Factorio binaries.
  - Status: active design risk
  - Mitigation: Export logical desired state, selected saves, permitted content,
    and hashes; exclude machine bindings, credential values, registry state,
    host diagnostics, and unlicensed binaries, and request a player-owned source
    explicitly during reconstruction.

- Risk: Host-environment scope could turn FacMan into a generic machine repair
  or optimization tool.
  - Status: active
  - Mitigation: Admit only conditions required by a supported FacMan,
    Factorio, setup, launch, server, development, release, or support workflow;
    delegate external owners and keep unknown configurations inspect-only.

- Risk: A globally healthy/broken label could hide route-specific blockers or
  cause irrelevant remediation.
  - Status: active
  - Mitigation: Evaluate versioned workflow requirement profiles from fresh,
    source-attributed evidence and report ready, degraded, and blocked per
    workflow.

- Risk: Privileged or shared-resource host repairs could interrupt other
  consumers or overclaim reversibility.
  - Status: deferred behind gates
  - Mitigation: Require the read-only spine, support export, user-scoped
    Sandbox remedy, rollback classes, restart/resume, a one-shot privilege
    broker, and shared-resource leases before the first privileged recipe.

- Risk: Product truth can drift between the canonical status, README, roadmap,
  AIDE queue, runtime refusals, and historical evidence.
  - Status: active
  - Mitigation: Generate current human surfaces from
    `release/index/project_status.v2.toml`, keep historical proof explicitly
    labelled, and validate the current WorkUnit and product sequence.

- Risk: Architecture work can delay the first trustworthy playable journey.
  - Status: active
  - Mitigation: Cap the execution refactor at one immutable configuration,
    one admission seam, one process-supervision port, one Launch module, one
    versioned result, and one run-session journal. Every abstraction must be
    consumed by Play.

- Risk: Automated process tests could be mistaken for real Factorio isolation.
  - Status: active
  - Mitigation: Keep instance-isolated and hermetic execution claims unproven
    until their independent, revision-pinned real-product gates receive a
    human-reviewed verdict.

- Risk: The command-complete interfaces may still be unintuitive for players.
  - Status: active
  - Mitigation: Measure a Windows-first first-run journey—find Factorio,
    create or select an instance, choose version/profile/modpack/account and
    settings, review readiness, then Play to the game menu—before broadening
    product scope. Keep the command explorer as an advanced interface.

- Risk: The project has no real-player validation despite substantial proof
  infrastructure.
  - Status: active
  - Mitigation: Require observed golden-journey pilots, actionable refusals,
    zero data loss, and explicit external-write disclosure before public beta.

- Risk: The three-repository train can create integration and release drift.
  - Status: active
  - Mitigation: Start Universal Launcher or Universal Setup work only from a
    real FacMan workflow, pin exact revisions, and require one FacMan
    superbuild and package for release evidence.

- Risk: The repo may harden speculative extension surfaces too early.
  - Status: active
  - Mitigation: Keep static application modules, defer dynamic plugins and a
    daemon until a real consumer exists, and evolve only selected public
    compatibility surfaces.

- Risk: Gateway forwarding, provider/model calls, and autonomous loops remain deferred.
  - Status: accepted limitation
  - Mitigation: AIDE Lite use remains local, deterministic, and report/review
    oriented unless a future reviewed task enables those surfaces.

- Risk: Python repository tooling may become an accidental product dependency.
  - Status: monitored
  - Mitigation: Keep Python in validation and build tooling only. Product
    behavior enters through the native command boundary, contracts, handlers,
    audit, and tests.

- Risk: Universal setup or launcher semantics may leak into the Factorio binding.
  - Status: open
  - Mitigation: Keep Universal Launcher product-neutral, keep setup mutation in
    Universal Setup, and route Factorio semantics through registered FLB
    handlers into typed application operations.

- Risk: Static command-graph metadata can drift from registered dispatch.
  - Status: mitigated for the current registry descriptor versions
  - Mitigation: Derive introspection from retained runtime descriptors and
    prove graph-to-dispatch parity before adding more authoritative routes.

- Risk: The generated instance configuration may not isolate real Factorio
  writes.
  - Status: active
  - Mitigation: Parse and preflight the same effective configuration passed by
    `--config`, refuse unsafe roots, retain an exclusive instance lock, and keep
    both execution modes unproven until their separate real-play gates pass.

- Risk: A diagnostic bundle could cross a link, exceed resource budgets, or
  expose malformed structured input.
  - Status: foundation proven; general export remains quarantined
  - Mitigation: Use only allowlisted bounded no-follow traversal, emit explicit
    omissions, fail closed on malformed JSON/INI, and require a separate full
    bundle adversarial promotion before enabling export.
