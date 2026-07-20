# World product model and operation authority

FacMan's product aggregate is a **World**: the playable thing a player creates,
imports, prepares, launches, protects, moves, and recovers. `World` is a UX and
application aggregate, not one monolithic persisted object and not a new owner
of installation, setup, host, or process mutation.

This document is target architecture. The records, commands, permits, and
apply paths described here are planned unless another contract and current
project status explicitly say they are available.

## Product promise

> Choose a world, press Play, and know which Factorio version, installation,
> mods, save, profile, environment, isolation guarantee, and recovery state
> apply.

The desired product flow is:

```text
open or create a world
  -> compute readiness from current evidence
  -> explain blockers and the least-invasive safe options
  -> compose typed plans owned by the responsible domains
  -> review effects, privilege, restart, rollback, and verification
  -> issue short-lived authority for the exact reviewed operation
  -> providers independently revalidate and apply their subplans
  -> verify, Play, observe, and record the result
```

## Decomposed World aggregate

```text
WorldView
  = WorldSpec
  + WorldBinding
  + WorldReadiness
  + recent operation and recovery history
```

These components have different portability, authority, freshness, and
lifecycle rules.

### `WorldSpec`: portable desired state

`WorldSpec` describes what the player wants independently of one machine:

- world identity and display name;
- save reference or new-world template;
- required Factorio version or range and content capabilities;
- modset lock, launch profile, and isolation requirement;
- backup and retention policy;
- optional server profile.

It contains logical resource references and content identities. It never
contains absolute machine paths, drive letters, process IDs, registry keys,
credential values, entitlement claims, or redistributable Factorio binaries.

### `WorldBinding`: machine-local resolution

`WorldBinding` resolves one `WorldSpec` on one machine. It records the world,
machine, installation, instance, save-path, content-cache, execution-
environment, credential-reference, and storage-placement identities plus the
evidence digest used to resolve them.

A binding is replaceable and machine-local. Rebinding a world must not rewrite
its portable intent merely because another machine uses different paths,
providers, or storage.

### `WorldReadiness`: computed projection

Readiness is recomputed from current installation, content, save, environment,
launch, operation, and recovery evidence. It is never persisted as
authoritative truth.

The result is one of:

```text
ready
degraded
blocked
recovery_required
```

Every blocker cites its evidence, affected resource and owner, required
capability, safest useful next action, effects, privilege and restart needs,
rollback class, and verification route. Cached readiness is disposable and
must carry explicit dependency identities, freshness, and invalidation rules.

### `WorldView`: task-oriented UI projection

`WorldView` composes the current spec, binding, readiness, and latest operation
history for frontends. It is optimized for tasks such as **Play**, **Make
Playable**, **Snapshot**, **Export**, and **Recover**. The generated command
catalogue remains the advanced automation surface rather than the primary
player navigation model.

## Federated world preparation

`WorldPreparationPlan` composes typed subplans; it does not become a universal
mutation kernel.

| Concern | Owning policy or mechanism |
| --- | --- |
| Factorio eligibility, versions, saves, mods, and world readiness | FacMan |
| Install references, bindings, launch staleness, and process orchestration | Universal Launcher |
| Installation and host mutation | Universal Setup |
| Exact Factorio launch policy and post-run interpretation | FacMan |
| Review, confirmation, and presentation | FacMan frontend |

Each subplan retains its own schema, identity, effects, owner, expiration,
verification, rollback, and refusal semantics. FacMan may rank and present the
combined plan, but it cannot manufacture setup or execution authority.

## Authority law

Five concepts remain separate:

1. **Effect declaration:** what an operation may attempt.
2. **Capability requirement:** what enforcement the operation needs.
3. **Capability observation:** what the selected machine and providers can
   actually enforce now.
4. **Policy decision:** what build, product, user, administrator, and support
   policy permit.
5. **Operation permit:** short-lived authority for one exact reviewed plan.

Configuration and environment variables may narrow policy. They cannot create
effects, capabilities, permits, credentials, setup authority, or process
authority.

### `OperationPermit`

Authority-bearing operations use a plan-bound `OperationPermit`, not a
long-lived global capability grant. A permit binds:

```text
permit ID and nonce
operation kind
plan ID, canonical digest, and expiry
exact resource identities
machine identity
provider identities and versions
required capabilities and isolation mode
evidence digest and policy revision
approving principal
issued time and permit expiry
```

Permits are single-purpose, short-lived, non-transferable, replay-resistant,
and invalid after any bound plan, resource, evidence, policy, machine, or
provider identity changes. Harmless reads do not require permits.

Global admission validates the request and permit, but it is not the sole
protection. Universal Setup independently revalidates installation and host
targets. The process provider independently revalidates executable identity,
launch plan, isolation mode, and permit. Credential providers independently
enforce credential scope. Frontends and declarative extensions cannot issue
or widen permits.

After apply, an independent inspector produces observed results. Completion is
reported only when postconditions pass; otherwise the operation is refused,
rolled back, or enters recovery-required honestly.

## Portable reconstruction

A portable world bundle may include `WorldSpec`, selected saves, modset locks,
permitted mod artifacts or references, profiles, templates, backup metadata,
content hashes, logical resource IDs, and an optional redacted audit summary.

It must exclude machine bindings, absolute paths, registry state, credential
values, Steam tokens, arbitrary host diagnostics, and publisher-unlicensed
Factorio binaries. Installed files do not prove entitlement. When the required
Factorio source cannot legally travel with the bundle, import reports the
player-owned source requirement and makes no change.

Import follows `inspect -> verify -> resolve -> conflict report -> plan ->
reviewed apply -> readiness`. The conflict report distinguishes locally
satisfied resources, reconstructable resources, required player-owned sources,
and policy conflicts before mutation.

## Canonical state and derived caches

Human-readable, versioned JSON or TOML records remain authoritative. Databases
and indexes may accelerate discovery, stable identity lookup, hashing, mod and
save metadata, and readiness evaluation, but every such cache must be
rebuildable from canonical state and current evidence.

Persisted-state policy is **read old, write current, migrate explicitly**.
Migration is inspect, backup, plan, apply, verify, and recover; unknown future
schemas refuse.

## Candidate stable workflow surface

Compatibility should stabilize the user-critical subset rather than every
low-level command:

```text
world.list
world.inspect
world.readiness
world.prepare.plan
world.prepare.apply
world.play
world.export
world.import.inspect
world.import.plan
operation.inspect
operation.resume
operation.rollback
support.export
```

These are candidate contracts, not current availability claims. Lower-level
provider and installation surfaces may remain experimental while this subset
is proven by real journeys.

## Delivery gates

1. Close, review, commit, and cleanly reproduce the current convergence,
   execution-foundation, and installation-model-v2 work.
2. **`FACMAN-WORLD-SPEC-AND-READINESS-01`:** add the portable spec, local
   binding, computed readiness, WorldView projection, and read-only
   list/inspect/readiness commands.
3. **`FACMAN-OPERATION-PERMIT-01`:** separate effects, requirements,
   observations, policy, and short-lived permits; add exact resource binding
   and provider-side independent revalidation.
4. **`FACMAN-HERMETIC-STANDALONE-PLAY-01`:** prove one exact standalone route
   through preflight, Play, exit, relaunch, interruption, concurrency refusal,
   protected-root observation, and human review.
5. **`FACMAN-WORLD-CENTRIC-ALPHA-01`:** expose the golden journey to real
   players and let observed problems govern the next permanent abstractions.
6. Continue portable reconstruction, managed lifecycle, content preparation,
   and host support as parallel value lanes. Signed self-update blocks public
   beta, not the first controlled playable alpha.

Steam-aware Play remains an independent gate and may follow the first proven
standalone route. Per-resource concurrency, external extensions, a daemon,
marketplace, and advisory AI remain deferred until a demonstrated consumer
requires them.
