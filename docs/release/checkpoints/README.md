# Release and readiness checkpoints

<!-- FACMAN-RELEASE-STATUS:BEGIN -->
## Current Boundary

The accepted non-execution product wave is `r3.7`. The exact H1 candidate is `eb629caaec9d62536a272336e940c0d3003fdaae` and the operator verdict remains `Fail`.

Execution is `unavailable`; Safe beta is `false`; release status is `unpublished`; authenticity is `not_proven_unsigned`. Green structural, package, or CI checks do not enlarge those claims.
<!-- FACMAN-RELEASE-STATUS:END -->

The current product checkpoint is
[`R3.7 Instance and Local-Content Lifecycle`](r3.7-instance-content-lifecycle.md),
frozen at implementation proof revision
`774628f442b0cd92ba7de14553f9bcd423aa3d9a`.
`run.execute` remains unavailable and Safe beta is not promoted.

The later
[`R3.7 Public Integration Proof`](r3.7-public-integration-proof.md) binds that
frozen product evidence to the accepted task/dev/main integration chain and the
successful final workflows for canonical revision `d00456069eb509eabf6a63f831aadbd19813413f`.
It is an evidence-only addendum, not a new product checkpoint.

The human-reviewed Steam-backed H1 Fail is recorded separately in
[`R3.7 H1 Steam-backed operator verdict`](r3.7-h1-steam-backed-fail.md). It
opens a narrow isolation-repair WorkUnit and does not promote execution.

The bounded implementation result for that WorkUnit is recorded in
[`R3.8 Steam external-state isolation repair`](r3.8-steam-external-state-isolation-repair.md).
It adds the fail-closed Steam classification and refusal boundary, but does not
claim an H1 retest or open an execution candidate.

The later
[`R3.8 Public Integration Proof`](r3.8-public-integration-proof.md) binds the
repair and WU0 closeout chain to canonical `main` revision
`53ffbd6e02f098e0eacda9392131592ba421b90a` and its exact successful workflows.
It is a bookkeeping successor on `dev`, not self-validating product evidence.

Earlier checkpoints remain revision-pinned historical evidence:

- [R3.6 product readiness](r3.6-product-readiness.md)
- [R3.5 zero-exception productization](r3.5-zero-exception-productization.md)
- [R3.4 architecture consolidation](r3.4-architecture-consolidation.md)
- [R3.3 production data and recovery](r3.3-production-data-recovery-proof.md)
- [R3.3 stretch proofs](r3.3-stretch-proofs.md)
- [R3.2 isolation foundation](r3.2-isolation-foundation-proof.md)
- [R3.2 public integration](r3.2-public-integration-proof.md)
- [R3 safety and package proof](r3-safety-package-proof.md)
- [R2 local alpha proof](r2-local-alpha-proof.md)

None of these records is a release, publisher-authenticity proof, Safe beta
promotion, or real-Factorio operator verdict.
