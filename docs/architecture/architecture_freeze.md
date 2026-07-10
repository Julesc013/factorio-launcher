# Architecture Freeze

The FacMan macro-architecture is frozen while the safety proof gates are in
progress. The freeze prevents another repository or root-layout migration; it
does not grant compatibility to unsafe or unproven behavior.

## Frozen Decisions

- `universal-setup` owns installed-software mutation.
- `universal-launcher` owns product-neutral runnable-state orchestration.
- `factorio-launcher` owns Factorio semantics and Factorio-facing apps.
- Frontends parse input and present typed command results.
- Contracts define observable compatibility.
- Validators and tests prove claims and prevent regressions.
- The durable FacMan roots remain `include/`, `runtime/`, `apps/`, `content/`,
  `contracts/`, `release/`, `docs/`, `tests/`, and `tools/`.

## Decisions That Remain Experimental

- application-service boundaries
- command registration and aliases
- persistence and transaction APIs
- package linkage and runtime resource loading
- public C ABI details
- process supervision
- JSON shapes that have not passed runtime conformance tests

Unsafe behavior has no compatibility entitlement. Hand-authored goldens are
examples until they have been compared with live command output and validated
against the corresponding schema.

## Change Rule

New abstractions require a real consumer. During the proof gates, changes must
either repair a shared trust primitive, make an exposed capability truthful,
or move the selected install-to-launch-preview workflow through its intended
command route.
