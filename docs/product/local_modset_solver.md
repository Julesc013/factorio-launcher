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
identifier is the rollback transaction identifier. `modsets rollback` verifies
both applied state and backup hashes before restoring the exact earlier state;
the displaced applied state remains in history.

These commands never fetch missing mods, remove local archives, execute Factorio,
or grant setup, publication, or human-acceptance authority.
