# Local modset solver

`modsets plan`, `diff`, and `explain` resolve requested enabled and disabled
packages against bounded local inventory. Required dependencies are added;
optional and hidden-optional dependencies constrain ordering only when already
selected. Incompatibilities, version constraints, derived built-in virtual
packages, and the instance Factorio version are evaluated without portal or
network access.

Selection is deterministic: a compatible current lock wins, then an explicit
`--prefer name=version`, then the highest compatible local version, then stable
normalized filename order. Plans contain the complete explanation, state
fingerprint, budget usage, and a content-derived plan identifier. Package,
version, edge, state, backtrack, elapsed-time, and explanation-node budgets all
fail closed with `solver_budget_exceeded`.

`modsets apply` always resolves and verifies a plan before mutation. It preserves
the current `mod-list.json`, instance lock, and shared lock in managed activation
history, stages new Factorio-compatible state, revalidates archive identities and
external drift, and commits through the workspace transaction journal. The plan
identifier remains deterministic. Applied results also report `transaction_id`,
the identity to pass to `modsets rollback`. The first attempt retains the plan ID
as its transaction ID for existing consumers; retries use a separate ID and
preserve all previous history and journals. A retry verifies the restored file
presence, contents, backups, activation identity and journal-owned marker-only
staging. Active attempts, unknown staged content and inconsistent history refuse.
Apply and rollback share the existing instance configuration lock.
Immediately before publication, apply checks selected local archive identities,
the instance binding, and the exact presence and bytes of all three managed
files again. A detected external edit refuses without restoring over that edit.
Staging and history must retain their owned markers, safe paths, exact expected
files, staged output and original backup bytes. Changed or unknown staged data
remains intact for recovery. Failed applies retain the original failure detail
in both the refusal and journal after verified restoration.
`modsets rollback` verifies
both applied state and backup hashes before restoring the exact earlier state;
the displaced applied state remains in history.

`modsets verify` checks only the packages pinned by the lock. It reinspects local
archives and derives built-in packages from the instance's registered install;
lock metadata cannot grant built-in provenance. Unselected local versions do not
invalidate a solver selection. Human inventory and solver commands show the
owner's package identities, selection, changes, explanation and rollback ID.

The older `modsets export` path still requires its all-archive physical lock.
Exporting a solver selection with virtual packages or unselected archives remains
an explicit refusal pending the local-content/modpack acceptance work. A passing
solver verification does not qualify that reconstruction path.

These commands never fetch missing mods, remove local archives, execute Factorio,
or grant setup, publication, or human-acceptance authority.
