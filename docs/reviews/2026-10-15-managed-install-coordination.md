# Managed installation coordination, 15 October 2026

Work item: `FACMAN-0.1-ALPHA6-MANAGED-INSTALL-RECONCILIATION-01`.
Base: `c089396b6210b8da18299fe8376bf1cea203826a`.

Install, repair, uninstall and operation-specific recovery share an OS-backed
FacMan lease for one configured Setup installation identity. Transaction-only
leases previously allowed different transactions to interleave provider effects
and FacMan reference projection. The repository CAS continues to protect the
exact record preimage; it is the last, short lock in the operation.

The order is a nonblocking transaction lease, durable requested coordinator,
shared installation lease, immediate preimage/plan revalidation, provider work,
and repository projection. The requested coordinator is a durable locator if
the process dies after shared lease creation but before provider entry. Existing
recovery inspection classifies actual provider evidence, and apply validates the
reviewed plan before acquiring a shared cell and again while holding it.

The shared file is a FacMan-owned sibling of the configured Setup root, under
its existing plain local parent. Its key binds the parent filesystem identity,
normalized Setup leaf and ASCII-folded installation ID. Windows existing 8.3
aliases are expanded before selecting the leaf. This creates no unmarked
provider root during first installation and coordinates FacMan workspaces that
share the configured provider installation identity.

The configured Setup-root leaf uses the existing portable identifier profile:
1–64 ASCII letters, digits, dots, underscores or hyphens, with reserved names
and trailing dots/spaces refused. Unicode and spaces in parent paths are
supported through their physical parent identity. Unsupported leaves are
refused consistently for absent and existing roots, so first-root creation
cannot change the coordination key. General Unicode-leaf coordination remains
outside this bounded implementation.

Metadata binds the normalized state root, physical owner workspace, operation,
transaction and held OS file identity. Parent identity, file identity and exact
metadata bytes are rechecked before provider entry, projection and release.
Unknown effects, incomplete projection and failed closure retain the lease.
Only a caller that proved no effects or an exact terminal disposition releases
it after durable `refused` or `complete` closure. Foreign, malformed, linked or
changed metadata is preserved and refused. Recovery adopts only its exact owner.
The complete prospective metadata serialization, including its newline and
maximum OS identity length, must fit 8192 bytes before a shared file is created.
Adoption requires the deterministic v1 serialization; whitespace or format
edits are preserved and refused even when the parsed identities match.

Planning, verification and recovery inspection remain read-only. Default
mutation authority remains unavailable; `operator_acceptance_candidate`
configuration is still required. This does not coordinate direct USK actors or
different configured provider roots that point at one target.

The focused M1 and public `coordination` scenario use synthetic owned bytes.
They cover cross-operation and cross-workspace contention, the shared metadata
window, process death, stale terminal recovery, changed metadata and foreign
preservation. Execution and independent review receipts remain external until
qualification. This source change grants no genuine Factorio, human, physical
host, package, Beta or release acceptance.
