# Transaction session v2

Status: implemented locally for R3.4 WorkUnit 7.

New transactions use an OS-random `tx-<128-bit>` identity and a typed state
machine. The explicit transition table rejects state jumps such as requested to
committed, complete to staging, and rolled-back to committing. Existing v1
journals remain readable and are updated as v1 during recovery; no implicit
journal migration occurs.

Each v2 staging root receives `.facman-transaction-staging.v2.json` once the
root exists. The marker binds schema version, transaction ID, command ID,
target-path SHA-256, and an independent OS-random nonce. Recovery requires exact
marker/journal agreement before cleanup. Generic marker-name existence is not
sufficient for v2 state.

Expected outputs are structured as a normalized relative path, validated
SHA-256 digest, and byte size. `TransactionSession` provides the ordered
validated, planned, staging, staged, verified, committing, committed, and
complete flow. Leaving an active session scope writes `recovery_required`
rather than silently abandoning an in-memory operation.

Reusable commit authorities cover staged files, staged directories, and
cross-volume copy/verify/no-clobber publication. Terminal-journal retention is
explicit: retain is the default, archive is opt-in, and age-based prune requires
a positive day count and can remove terminal journals only.

The enabled install import, instance creation/import/export, mod import,
modset lock/export, save backup/clone, and diagnostic export writers all enter
through `TransactionSession`. Domain code cannot use the raw begin/advance/fail
compatibility functions; the strict architecture check keeps that compatibility
surface confined to the transaction and legacy-recovery implementation.
