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

Establish the AIDE baseline and decide whether the compact directory structure
needs further changes before native command graph parity work begins.

## Deferred Surfaces

- Gateway forwarding, provider/model calls, UI, runtime, and autonomous loops.
- GUI implementation beyond app shells.
- Universal Setup and Universal Launcher repo structure finalization.
- Direct production package dependency on Python or AIDE.

## Notes

- `source/` is the only implementation source root.
- `include/` contains public ABI headers.
- `apps/` contains frontend project/package shells; implementation lives under
  `source/apps/`.
- `source/prototypes/python_launcher/` is the current runnable prototype and
  golden behavior harness until native parity.
- Native command graph implementation is still the major gap.
- Production packages must not bundle Factorio binaries, credentials, AIDE, or
  a Python runtime.
