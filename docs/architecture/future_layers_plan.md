# Future layers plan

This document no longer describes completed R2/R3 work as future work. Current
truth is generated in `.aide/memory/project-state.v1.json`; completed proof is
indexed under `.aide/history/` and `docs/release/checkpoints/`.

## Completed product-readiness lane

R3.5 is the architecture endpoint. It establishes the reusable core types,
platform services, repositories, transactions, application handlers, generated
command law, bounded machine transport, reproducible packaging, compact AIDE
state, and supply-chain verification. R3.6 consumed that foundation in real
discovery and frontend workflows; it did not create another consolidation
wave. Its autonomous lane is complete.

## Ordered future authority gates

1. Obtain the operator-supplied real Factorio isolation verdict before any
   `run.execute` promotion. Automated checks cannot provide that verdict.
2. Advance workspace v2 only through dry-run migration, backup, journal,
   rollback, and compatibility proof.
3. Add network, credentials, Mod Portal access, or setup mutation only in
   separate reviewed tasks with explicit ownership and threat-model changes.
4. Promote daemon or GUI packages only after their actual transports,
   runtime behavior, accessibility, and operator usability are proven.
5. Add signing/notarization/publication only after integrity, provenance, and
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
