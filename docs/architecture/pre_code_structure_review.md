# Pre-Code Structure Review

The repository has moved from the bootstrap compromise:

```text
include/
source/
apps/
data/
schemas/
packaging/
```

to the ownership-root model:

```text
include/
runtime/
apps/
content/
contracts/
release/
docs/
tests/
tools/
cmake/
```

This should be treated as the canonical structure before substantial native
implementation work begins.

## Why The Move Was Worth It

The old tree was coherent, but `source/` was doing too much. It mixed package
runtime location, frontend code, Factorio binding code, prototype Python, and
incubated universal kernels. The new tree makes ownership visible:

```text
runtime/       reusable implementation
apps/          presentation/entrypoints
content/       product-owned templates and policy
contracts/     schemas, ABI policy, command law, result/refusal contracts
release/       package manifests and profiles
```

The universal kernels are no longer physically owned by `factorio-launcher`.
They live in sibling repos:

```text
universal-setup/
universal-launcher/
factorio-launcher/
```

## Decisions

- `source/` is retired.
- `src/` remains forbidden.
- `data/` is retired in favor of `content/`.
- `schemas/` is retired in favor of `contracts/schema/`.
- `packaging/` is retired in favor of `release/packaging/`.
- `apps/factorio_cli`, `apps/factorio_tui`, and `apps/factorio_daemon` are
  retired in favor of `apps/cli`, `apps/tui`, and `apps/daemon`.
- `include/usk` and `include/ulk` are moved to their universal repos.
- `runtime/usk` and `runtime/ulk` must not appear in this repo.

## Current Split

```text
universal-setup:
  install / verify / repair / uninstall / rollback authority

universal-launcher:
  command graph, products, install refs, instances, profiles, launch plans

factorio-launcher:
  Factorio binding, Factorio content/contracts, Factorio app frontends
```

## Remaining Risk

The current CMake integration uses sibling repo paths while the three packages
are still young:

```text
../universal-setup
../universal-launcher
```

That is acceptable for this split commit, but later release work should replace
it with pinned dependencies, submodules, package-manager integration, or another
explicit dependency acquisition policy.

## Next Work Before Feature Code

1. Decide whether the universal repos keep the same `runtime/content/contracts`
   grammar or refine it further with setup/launcher-specific roots.
2. Add cross-repo validators that reject Factorio semantics in universal repos.
3. Add command graph contract tests once `universal-launcher` owns real command
   dispatch.
4. Add setup transaction contract tests once `universal-setup` owns real
   mutation machinery.
