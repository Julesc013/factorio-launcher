# Adding a persisted model

Persisted state requires a versioned schema, a typed repository interface, and
an explicit compatibility decision. Place schema law under
`contracts/schema/workspace/` and implementation under `runtime/workspace/` or
the owning Factorio domain. IDs are typed values; do not make display names or
absolute local paths authoritative identities.

Readers must validate before use. Writers must use the platform I/O and
transaction primitives, declare create/replace/merge semantics, and preserve
no-clobber behavior. A format change needs dry-run migration, backup, journal,
rollback, and compatibility tests before the new version becomes writable.

Add schema, repository, filesystem, corruption, migration, and recovery tests.
Update the compatibility policy and claim ledger if the evidence level changes.
