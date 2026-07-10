# Safety Claim Ledger

Baseline audit revision: `df2dd9487d51c30cf1bf404a9c7246288ee330b9`.

This ledger prevents a fixture, declaration, or generated file from being
reported as stronger runtime evidence.

| Claim | Current level at baseline | Evidence | Limitation / required promotion evidence |
| --- | --- | --- | --- |
| Managed paths remain inside the workspace | refuted | adversarial install and instance identifier probes | containment-aware path API and passing escape corpus |
| Persistent creation is no-clobber | refuted | existing instance/import probes | explicit replace policy and passing no-clobber tests |
| Package tools clean only owned output | refuted | external output cleanup probe | recognized ownership marker required before deletion |
| Instance layout is structurally isolated | fixture-tested | instance layout and launch-plan tests | real Factorio write semantics unproven |
| Process boundary passes intended arguments | fixture-tested | controlled executable smoke | does not prove Factorio configuration semantics |
| Diagnostic redaction covers known corpus | fixture-tested | deterministic line-oriented redaction fixtures | arbitrary structured input and hostile traversal unproven |
| JSON contracts describe runtime output | partial | schemas and hand-authored goldens exist | live response and persisted-object conformance required |
| Command graph is authoritative | partial | descriptors and static kernel responses exist | selected workflow must dispatch through registered handlers |
| Portable package runs after relocation | host-tested | built package runtime smoke | host-specific, unsigned, resource enforcement incomplete |
| Package hashes authenticate publisher | not claimed | unsigned SHA-256 manifest | signatures or trusted external metadata required |
| Public C ABI is stable | not claimed | experimental headers and smoke calls | ownership, size negotiation, concurrency, and compatibility proof required |

Each promotion record must identify the repository revision, sibling
revisions, target platform/toolchain, proof command or operator procedure,
known limitations, and the change that requires revalidation.
