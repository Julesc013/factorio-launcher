# Safety Claim Ledger

Baseline audit revision: `df2dd9487d51c30cf1bf404a9c7246288ee330b9`.
Bounded proof implementation revision: `4e6d8a191a8b17723cdd210fef2083d6814fc9b8`.

This ledger prevents a fixture, declaration, or generated file from being
reported as stronger runtime evidence.

| Claim | Current level after bounded gates | Evidence | Limitation / required promotion evidence |
| --- | --- | --- | --- |
| Managed paths remain inside the workspace | regression-proven for enabled paths | validation, containment, link refusal, escape corpus | new filesystem features must reuse these primitives |
| Persistent creation is no-clobber | regression-proven for current writers and same-host commit races | platform no-replace commits and concurrent tests | ancestor substitution and power-loss durability remain unproven |
| Package tools clean only owned output | regression-proven | owned-output markers for skeleton, built package, and archive roots plus preservation tests | other future destructive tools need their own ownership kind |
| Instance layout is structurally isolated | regression-proven for generated state | effective `config.ini`, import regeneration, exact-root preflight, link and sensitive-root refusals | real Factorio write semantics unproven |
| Process boundary preserves intended isolation | surrogate process proven | probe captures args, cwd, env, config, roots, writes, exit, and protected snapshots | proves FacMan and probe behavior, not Factorio internals |
| Per-instance run ownership is exclusive | native concurrency proven | no-clobber lock, contention, malformed refusal, token release, stale recovery | shared filesystems and hostile substitution remain unproven |
| Diagnostic redaction covers known corpus | fixture-tested plus multiline JSON | redaction fixtures and malformed-JSON refusal | general export remains unavailable pending safe traversal and budgets |
| JSON contracts describe runtime output | proven for the truth-floor slice | live response, refusal, persisted-instance, and package-verification schema tests | remaining legacy commands and goldens are not implicitly promoted |
| Command registry introspection matches dispatch | registry-proven | runtime descriptor projection, register/unregister parity, metadata lifetime and allocator tests | new descriptor versions and handlers require the same parity proof |
| Run preview uses the authoritative route | live-contract tested | normalized CLI, registered FLB handler, typed request/result, shared argument builder | no process starts; real Factorio remains unproven |
| Windows install discovery is read-only | provider-tested | Steam VDF, registry/default roots, standalone roots, zero-write tests | registry proof is host-dependent; macOS and Linux provider databases remain future work |
| Windows x64 static CLI package runs after relocation | host-tested built artifact | strict profile/component/lock verification and relocation matrix | local Windows x64 only; unsigned and unpublished |
| Package hashes authenticate publisher | not claimed | unsigned SHA-256 manifest | signatures or trusted external metadata required |
| Experimental public C ABI has a correctness floor | bounded correctness proof | size, ownership, ABI-query, and native-smoke tests | stable third-party compatibility and independent consumers remain unproven |

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

The R3.2 process-boundary promotion does not enable `run.execute`. Its operator
procedure and deliberately pending human-verdict template are in
[`real_factorio_isolation_smoke.template.md`](evidence/real_factorio_isolation_smoke.template.md).
