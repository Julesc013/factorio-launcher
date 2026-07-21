# Future layers plan

This document no longer describes completed R2/R3 work as future work. Current
truth is generated in `.aide/memory/project-state.v2.json`; completed proof is
indexed under `.aide/history/` and `docs/release/checkpoints/`.

## Completed product-readiness lane

R3.5 is the architecture endpoint. It establishes the reusable core types,
platform services, repositories, transactions, application handlers, generated
command law, bounded machine transport, reproducible packaging, compact AIDE
state, and supply-chain verification. R3.6 consumed that foundation in real
discovery and frontend workflows; it did not create another consolidation
wave. Its autonomous lane is complete.

## Ordered future authority gates

1. Review, commit, and cleanly reproduce product convergence, the
   capability-scoped execution foundation, and installation-model-v2 without
   promoting real execution or setup authority.
2. Add portable `InstanceSpec`, machine-local `InstanceBinding`, computed
   readiness, and the read-only instance list/inspect/readiness surface.
   `Instance` is the UX aggregate composed from installation/version, data
   root, template provenance, pinned preset, ordered typed profiles,
   `ModsetSpec`/`ModsetLock`, decomposed account bindings, settings, resources,
   and optional saves. The default `LaunchIntent` is `menu`.
3. Add short-lived `OperationPermit`s bound to one reviewed plan, exact
   resources, evidence, policy, machine, and providers. Global admission and
   each authority-bearing provider revalidate independently.
4. Prefer hermetic standalone Play as the first revision-pinned real-product
   gate. Steam-aware Play remains separate; at least one human-reviewed route
   must pass before the instance-centric playable alpha.
5. After the alpha, preserve World as a secondary content lane through
   `FACMAN-WORLD-BUNDLE-AND-SAVE-COMPATIBILITY-01`; add portable requirements,
   compatibility, import/export, and instance creation/preparation from a world
   bundle without making World the launch aggregate.
6. In parallel after gate 1, add workflow-specific read-only host
   list/inspect/doctor, bounded support export, and the first no-admin Windows
   Sandbox profile. Host support must not block an unrelated native Play route.
   Restart operations, a one-shot privilege broker, and shared-resource
   coordination precede any privileged host recipe.
7. Advance workspace formats only through dry-run migration, backup, journal,
   rollback, and compatibility proof.
8. Add network, credentials, Mod Portal access, or setup mutation only in
   separate reviewed tasks with explicit ownership and threat-model changes.
9. Promote daemon or GUI packages only after their actual transports,
   runtime behavior, accessibility, and operator usability are proven.
10. Require signed packages, migration, and update rollback for public beta,
   but do not make signed self-update block the first controlled playable alpha.
11. Add signing/notarization/publication only after integrity, provenance, and
   publisher-authenticity gates are explicitly separated and approved.

## Permanent order

```text
contracts first
runtime second
frontend third
automation fourth
intelligence last
```

No future layer may bypass the command graph, make a frontend a backend,
duplicate an established authority, or convert a fixture or green CI run into
a stronger product claim.

The implemented execution-foundation boundary is documented in
[`execution_foundation.md`](execution_foundation.md).
The planned instance aggregate and operation authority are documented in
[`instance_product_model.md`](instance_product_model.md).
The prerequisite-gated but Play-independent host support lane is documented in
[`host_environment_lifecycle.md`](host_environment_lifecycle.md).
