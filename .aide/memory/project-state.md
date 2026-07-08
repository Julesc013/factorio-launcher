# FLaunch Project State

## Summary

FLaunch is an unofficial Factorio launcher and isolated instance manager. It
discovers existing installs, creates per-instance data roots, generates dry-run
launch plans, and keeps destructive install mutation behind Universal Setup.
AIDE Lite is imported as repo-local development tooling only.

## Current Phase

pre-code structure governance and native command graph planning

## Primary Goal

Make the repository self-governing before writing substantial native product
code: roots, ownership boundaries, safety invariants, command graph claims,
prototype boundaries, schemas, package manifests, and validation evidence should
be queryable and checkable.

## Next Task

Finish the three-repo ownership split, keep the new root grammar enforced, and
start native command graph parity work only after the universal repos are
structurally clean.

## Deferred Surfaces

- Gateway forwarding, provider/model calls, UI, runtime, and autonomous loops.
- GUI implementation beyond app shells.
- Universal Setup and Universal Launcher repo structure finalization.
- Direct production package dependency on Python or AIDE.

## Notes

- `source/`, `src/`, `data/`, `schemas/`, and `packaging/` are retired roots.
- `include/` contains only the Factorio binding public ABI in this repo.
- `runtime/` contains reusable private implementation.
- `apps/` contains frontend entrypoints and presentation code.
- `content/` contains Factorio product content and policy.
- `contracts/` contains schema, ABI, command, result, diagnostic, refusal, and
  policy contracts.
- `release/` contains package manifests and release profiles.
- `apps/python_cli/` is the current runnable prototype and
  golden behavior harness until native parity.
- Native command graph implementation is still the major gap.
- Production packages must not bundle Factorio binaries, credentials, AIDE, or
  a Python runtime.
