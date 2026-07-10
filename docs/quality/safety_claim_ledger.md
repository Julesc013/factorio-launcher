# Safety Claim Ledger

Baseline audit revision: `df2dd9487d51c30cf1bf404a9c7246288ee330b9`.
Bounded proof revision: `91db3baca3bdd741da9ffeb1f205bea16fe16379`.

This ledger prevents a fixture, declaration, or generated file from being
reported as stronger runtime evidence.

| Claim | Current level after bounded gates | Evidence | Limitation / required promotion evidence |
| --- | --- | --- | --- |
| Managed paths remain inside the workspace | regression-proven for enabled paths | validation, containment, link refusal, escape corpus | new filesystem features must reuse these primitives |
| Persistent creation is no-clobber | regression-proven for current writers | staging and existing-target tests | future writers need an explicit create/replace/merge policy |
| Package tools clean only owned output | regression-proven | owned-output markers for skeleton, built package, and archive roots plus preservation tests | other future destructive tools need their own ownership kind |
| Instance layout is structurally isolated | fixture-tested | instance layout and launch-plan tests | real Factorio write semantics unproven |
| Process boundary passes intended arguments | fixture-tested | controlled executable smoke | does not prove Factorio configuration semantics |
| Diagnostic redaction covers known corpus | fixture-tested plus multiline JSON | redaction fixtures and malformed-JSON refusal | general export remains unavailable pending safe traversal and budgets |
| JSON contracts describe runtime output | proven for the truth-floor slice | live response, refusal, persisted-instance, and package-verification schema tests | remaining legacy commands and goldens are not implicitly promoted |
| Command graph is authoritative | proven for first workflow | registered handlers for install scan/import/inspect, instance create, and launch-plan build | remaining CLI families still require strangler migration |
| Windows x64 static CLI package runs after relocation | host-tested built artifact | self-verification and relocation matrix | local Windows x64 only; unsigned and unpublished |
| Package hashes authenticate publisher | not claimed | unsigned SHA-256 manifest | signatures or trusted external metadata required |
| Public C ABI is stable | not claimed; correctness floor only | size validation, ownership rules, ABI query, native smoke | concurrency, cancellation, compatibility, and independent consumers remain unproven |

Each promotion record must identify the repository revision, sibling
revisions, target platform/toolchain, proof command or operator procedure,
known limitations, and the change that requires revalidation.

The exact gate and sibling revisions, platform, commands, and residual claims
are recorded in
[`r3-safety-package-proof.md`](../release/checkpoints/r3-safety-package-proof.md).
