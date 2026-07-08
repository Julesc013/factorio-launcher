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
- App code lives in `apps/<role>/`; GUI providers live in
  `apps/gui/<provider>/`; reusable behavior lives in `runtime/`.
- Factorio product data is now `content/factorio/`, not a generic `data/`
  drawer.
- JSON schemas are now under `contracts/schema/`.
- Package manifests are now under `release/packaging/`.
- `include/` now contains only `flb`, the Factorio binding public ABI.
- `usk` and `ulk` headers/runtime code moved to their own repositories.
- Redundant app names are gone: `apps/cli`, `apps/tui`, `apps/daemon`, with
  GUI toolkits grouped under `apps/gui/`.
- `contracts/` now has a broader spine than schemas: ABI, command, result,
  refusal, diagnostic, and policy contracts are first-class.
- `release/profiles/` now has target-specific lanes instead of vague
  `legacy`/`modern` buckets.
- `runtime/factorio/c11` and `runtime/factorio/cpp11` are retired in favor of
  product-domain folders such as `install_validation/`, `modsets/`, and
  `compat/`.

## Remaining Risks

The universal repos are still young. Factorio CMake currently consumes them as
sibling checkouts:

```text
../universal-setup
../universal-launcher
```

That is fine for active design work, but release engineering should eventually
choose a pinned dependency strategy.

The former Python CLI prototype has been retired. The native CLI now owns the
initial runnable slice for product inspection, doctor checks, install import,
instance creation, launch-plan preview, and dry-run reporting. Python remains
available for repo tooling and tests only.

## Required Enforcement

Run:

```powershell
python tools\structure_policy_check.py
python tools\strict_check.py
```

The validator should fail if retired roots return, if `apps/python_cli/` or a
Python product `pyproject.toml` returns, if Factorio owns `usk` or `ulk`
implementation again, if language-version runtime buckets return, or if product
content starts containing executable code.

## Next Structural Work

1. Harden `universal-setup` with setup-only validators.
2. Harden `universal-launcher` with launcher-only validators.
3. Add cross-repo boundary checks once the dependency acquisition model is
   settled.
4. Replace sibling CMake paths with pinned dependencies before release.
