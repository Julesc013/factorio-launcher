# Structure Assessment

The repo has left the bootstrap compromise and now uses ownership roots.

## Current Verdict

The structure is stronger than the previous `source/data/schemas/packaging`
model because the top-level names now describe ownership:

```text
runtime/    implementation ownership
apps/       frontend ownership
content/    product content ownership
contracts/  compatibility and policy ownership
release/    package/release ownership
```

This is a better fit for a three-repo launcher ecosystem.

## Improvements Over The Old Shape

- `source/` and `src/` are gone.
- App code lives in `apps/<role>/`; reusable behavior lives in `runtime/`.
- Factorio product data is now `content/factorio/`, not a generic `data/`
  drawer.
- JSON schemas are now under `contracts/schema/`.
- Package manifests are now under `release/packaging/`.
- `include/` now contains only `flb`, the Factorio binding public ABI.
- `usk` and `ulk` headers/runtime code moved to their own repositories.
- Redundant app names are gone: `apps/cli`, `apps/tui`, `apps/daemon`.

## Remaining Risks

The universal repos are still young. Factorio CMake currently consumes them as
sibling checkouts:

```text
../universal-setup
../universal-launcher
```

That is fine for active design work, but release engineering should eventually
choose a pinned dependency strategy.

The Python CLI remains in `apps/python_cli/` as a transitional prototype. It is
useful for current behavior checks, but production legacy packages must not
depend on Python.

## Required Enforcement

Run:

```powershell
python tools\structure_policy_check.py
python tools\strict_check.py
```

The validator should fail if retired roots return, if Factorio owns `usk` or
`ulk` implementation again, or if product content starts containing executable
code.

## Next Structural Work

1. Harden `universal-setup` with setup-only validators.
2. Harden `universal-launcher` with launcher-only validators.
3. Add cross-repo boundary checks once the dependency acquisition model is
   settled.
4. Replace sibling CMake paths with pinned dependencies before release.
