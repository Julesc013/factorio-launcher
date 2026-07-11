# Future layers plan

This document no longer describes completed R2/R3 work as future work. Current
truth is generated in `.aide/memory/project-state.v1.json`; completed proof is
indexed under `.aide/history/` and `docs/release/checkpoints/`.

## Current consolidation

R3.4 establishes reusable core types, platform services, repositories,
transactions, application handlers, a client-only CLI, truthful frontend
transports, module-local CMake, reproducible install-tree packaging,
impact-based tests, compact AIDE state, and supply-chain verification.

## Ordered future authority gates

1. Obtain the operator-supplied real Factorio isolation verdict before any
   `run.execute` promotion. Automated checks cannot provide that verdict.
2. Complete per-revision Linux/macOS/Windows package and native-quality CI for
   the exact release candidate.
3. Advance workspace v2 only through dry-run migration, backup, journal,
   rollback, and compatibility proof.
4. Add network, credentials, Mod Portal access, or setup mutation only in
   separate reviewed tasks with explicit ownership and threat-model changes.
5. Promote TUI, daemon, or GUI packages only after their actual transports,
   runtime behavior, accessibility, and operator usability are proven.
6. Add signing/notarization/publication only after integrity, provenance, and
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
