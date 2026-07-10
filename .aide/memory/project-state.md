# FacMan Project State

## Summary

FacMan is an unofficial Factorio launcher and isolated instance manager. The
three-repository ownership split and durable root grammar are frozen. Universal
Setup owns installed-state mutation, Universal Launcher owns product-neutral
runnable-state orchestration, and this repository owns Factorio semantics and
Factorio-facing applications.

## Current Phase

R3 post-Gate-4 truth hardening.

## Current Proof

- The five migrated commands `install_refs.scan`, `install_refs.import`,
  `install_refs.inspect`, `instance.create`, and `launch_plan.build` execute
  through the authoritative Universal Launcher route.
- Path traversal, unmanaged cleanup, and silent persistent overwrite have
  committed adversarial regression coverage.
- A Windows x64 static-first package proof exists for the CLI-only lane.
- Public sibling revisions are pinned by
  `release/index/workspace_lock.v1.toml` and checked before three-repository
  builds.

## Current Goal

Make the selected live contracts, typed application requests, filesystem
commit behavior, package component roles, and CI jobs describe and enforce the
same bounded proof. Then extend real Windows read-only discovery through the
existing command route.

## Quarantined Capabilities

- Real `run.execute` remains unavailable until both a controlled write-probe
  and an operator-supplied Factorio isolation smoke pass.
- General diagnostic export remains unavailable until traversal budgets,
  no-follow behavior, and format-aware fail-closed redaction are proven.
- Setup mutation, networking, credentials, dynamic plugins, and release
  publication remain deferred.

## Root Truth

- `include/` is public ABI only.
- `runtime/` is private compiled implementation.
- `apps/` contains frontend entrypoints and presentation shells.
- `content/` contains declarative Factorio content and policy.
- `contracts/` contains compatibility law, including but not limited to schema.
- `release/` contains packaging and release definitions.
- `docs/`, `tests/`, `tools/`, `cmake/`, and `external/` retain their named
  responsibilities.
- `source/`, `src/`, `data/`, `schemas/`, and `packaging/` are retired roots.

Production packages must not bundle Factorio binaries, credentials, AIDE, or a
Python runtime.
