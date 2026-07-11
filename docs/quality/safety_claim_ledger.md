# Safety Claim Ledger

Baseline audit revision: `df2dd9487d51c30cf1bf404a9c7246288ee330b9`.
Bounded proof implementation revision: `4e6d8a191a8b17723cdd210fef2083d6814fc9b8`.
R3.2 registry and routed-preview revision: `d898d4e702043b186cf0669ba98fb1c69afbca70`.
R3.2 controlled-isolation revision: `17b11224db897bc11c8d4a024e2f1409cba4dd3f`.
R3.2 final bounded-foundation revision: `0c64d56c6d1efee6ef7faf17f2781c6a1c1db8cc`.
R3.2 public integration revision: `b739d271083c2883c94921a1441574cda55912ad`.

This ledger prevents a fixture, declaration, or generated file from being
reported as stronger runtime evidence.

| Claim | Current level after bounded gates | Evidence | Limitation / required promotion evidence |
| --- | --- | --- | --- |
| Managed paths remain inside the workspace | regression-proven for enabled paths | validation, containment, link refusal, escape corpus | new filesystem features must reuse these primitives |
| Persistent creation is no-clobber | regression-proven for current writers and same-host commit races | platform no-replace commits and concurrent tests | ancestor substitution and power-loss durability remain unproven |
| Package tools clean only owned output | regression-proven | owned-output markers for skeleton, built package, and archive roots plus preservation tests | other future destructive tools need their own ownership kind |
| Instance layout is structurally isolated | regression-proven for generated state | effective `config.ini`, import regeneration, exact-root preflight, link and sensitive-root refusals | real Factorio write semantics unproven |
| Process boundary preserves intended isolation | surrogate process proven | probe captures args, cwd, env, config, roots, writes, exit, and protected snapshots | proves FacMan and probe behavior, not Factorio internals |
| Per-instance run ownership is exclusive | local-filesystem native proof | stable handle, file identity, contention, stale recovery, substitution refusal | shared/network and multi-host filesystems remain unproven |
| Reviewed local diagnostic export is bounded | cross-platform CI proven | stable handles, known formats, reports, production ZIP, journal faults | no arbitrary formats, GUI UX, shared filesystems, or authenticity |
| JSON contracts describe runtime output | proven for the truth-floor slice | live response, refusal, persisted-instance, and package-verification schema tests | remaining legacy commands and goldens are not implicitly promoted |
| Command registry introspection matches dispatch | registry-proven | runtime descriptor projection, register/unregister parity, metadata lifetime and allocator tests | new descriptor versions and handlers require the same parity proof |
| Run preview uses the authoritative route | live-contract tested | normalized CLI, registered FLB handler, typed request/result, shared argument builder | no process starts; real Factorio remains unproven |
| Windows install discovery is read-only | provider-tested | Steam VDF, registry/default roots, standalone roots, zero-write tests | registry proof is host-dependent; macOS and Linux provider databases remain future work |
| Windows x64 static CLI package runs after relocation | host-tested built artifact | strict profile/component/lock verification and relocation matrix | local Windows x64 only; unsigned and unpublished |
| Linux x64 CLI tarball runs after relocation | target CI proven | ELF allowlist, archive, read-only and relocation matrix | Ubuntu 24.04 x64/glibc 2.39 only; rerun per revision; unsigned and unpublished |
| macOS x64 CLI tarball runs after relocation | target CI proven | Mach-O, deployment, integrity, relocation | Intel runner and target 13.0 only; no Apple Silicon, AppKit runtime, signing, or publication claim |
| Package verification is setup-authoritative | cross-repo tested | USK bounded verification and FacMan rendering | authenticity and setup mutation remain unproven |
| Package hashes authenticate publisher | not claimed | unsigned SHA-256 manifest | signatures or trusted external metadata required |
| Package inputs and provenance are recorded | target CI proven | SPDX component closure, licenses, identities, and digests | provider licenses are `NOASSERTION`; unsigned evidence is not publisher authentication |
| Experimental public C ABI has a correctness floor | bounded correctness proof | size, ownership, ABI-query, and native-smoke tests | stable third-party compatibility and independent consumers remain unproven |
| CLI uses only the client boundary | regression-proven | include/link checker, direct transport smoke, parity tests | process and daemon transports remain unavailable |
| Install-tree archives reproduce | Windows digest-proven | independent roots, normalized metadata, dirty refusal | other targets need per-revision CI; output is unsigned |
| Normal AIDE context excludes history bulk | locally regression-proven | active/next queue, history hashes, compact state | development governance only; no product or human proof |

Each promotion record must identify the repository revision, sibling
revisions, target platform/toolchain, proof command or operator procedure,
known limitations, and the change that requires revalidation.

The no-clobber proof covers the current writers. Future writers still need an
explicit create, replace, merge, or resume policy. Handle-relative parent
traversal, hostile cross-process substitution, and full power-loss durability
remain separate promotion evidence.

The exact gate and sibling revisions, platform, commands, and residual claims
are recorded in
[`r3-safety-package-proof.md`](../release/checkpoints/r3-safety-package-proof.md).

The R3.2 revision-pinned matrix and package evidence are recorded in
[`r3.2-isolation-foundation-proof.md`](../release/checkpoints/r3.2-isolation-foundation-proof.md).

The integrated universal main and FacMan dev identities are frozen in
[`r3.2-public-integration-proof.md`](../release/checkpoints/r3.2-public-integration-proof.md).

The R3.3 production-data, recovery, diagnostics, and Linux package core is
frozen in
[`r3.3-production-data-recovery-proof.md`](../release/checkpoints/r3.3-production-data-recovery-proof.md).
The local-lock, provenance, and macOS CLI stretches are frozen in
[`r3.3-stretch-proofs.md`](../release/checkpoints/r3.3-stretch-proofs.md).

The R3.4 architecture consolidation and exact local Windows artifact are
recorded in
[`r3.4-architecture-consolidation.md`](../release/checkpoints/r3.4-architecture-consolidation.md).
That checkpoint is a target-promotion hold: it does not reuse R3.3 Linux or
macOS evidence as fresh proof.

The R3.2 process-boundary promotion does not enable `run.execute`. Its operator
procedure and deliberately pending human-verdict template are in
[`real_factorio_isolation_smoke.template.md`](evidence/real_factorio_isolation_smoke.template.md).
The preparation harness records exact identities, refuses incomplete protected
snapshots, reports detailed before/after changes, supervises termination, and
retains external write classifications without converting them into a human
verdict.
