# FacMan Project State

## Summary

FacMan is an unofficial Factorio launcher and isolated instance manager. The
three-repository ownership split and durable root grammar are frozen. Universal
Setup owns installed-state mutation, Universal Launcher owns product-neutral
runnable-state orchestration, and this repository owns Factorio semantics and
Factorio-facing applications.

## Current Phase

R3.2 authoritative registry and instance-isolation foundation.

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
- Windows read-only discovery is implemented for Steam registry roots, bounded
  `libraryfolders.vdf` parsing, standalone roots, deterministic de-duplication,
  Unicode and long paths, malformed metadata, and junction refusal.
- The public C ABI is experimental. Its current proof is a correctness floor,
  not a stable third-party compatibility promise.
- Universal Launcher introspection is generated from retained runtime
  descriptors, and canonical `run.preview` plus `launch_plan.preflight` route
  through the registered Factorio application handler into typed results.
- Instance creation and import generate the effective Factorio `config.ini`;
  preflight parses that same file and refuses mismatched, sensitive, or linked
  roots.
- A purpose-built process probe proves argument transfer, intended writes,
  protected-root invariance, and exclusive run-lock behavior. This evidence is
  not a substitute for a real Factorio operator verdict.

## Current Goal

Confirm the revision-pinned R3.2 task-branch CI matrix. Only after it is green,
begin read-only Universal Setup package verification and audit. Keep
`run.execute` quarantined and do not schedule Windows discovery again.

## Quarantined Capabilities

- Real `run.execute` remains unavailable until the prepared operator-supplied
  Factorio isolation smoke receives a reviewed human pass.
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
