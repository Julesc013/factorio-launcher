# Product Vision

FacMan is an unofficial, native, portable, scriptable, instance-first launcher
and environment manager for Factorio.

Its value is not simply launching Factorio. Its value is:

```text
one install, many isolated worlds
many Factorio versions, safely pinned
many modsets, reproducibly locked
many saves, protected and backed up
many frontends, one command graph
many platforms, one native core
many products later, one universal launcher pattern
```

The central workflow is:

```text
Create a new isolated Factorio instance,
choose an install/version,
attach a locked modset,
attach saves/profiles/server settings,
preview the exact launch plan,
then run without touching global Factorio data.
```

## Product Rules

- No bundled Factorio binaries.
- No ownership bypass.
- No official branding assets.
- No silent writes to the default Factorio data directory.
- No global mod folder swapping.
- Dry-run launch plans before execution.
- Managed install operations go through Universal Setup.

## v1 Shape

v1 is useful when it has read-only install discovery, ownership
classification, isolated instances, dry-run launch plans, safe launch
execution, local ZIP mod import, modset lockfiles, save backup, diagnostics,
portable workspace behavior, CLI-first command coverage, and native packaging
skeletons.

v1 should not require full GUI parity, managed network installs, full Mod
Portal automation, auto-updating everything, AI recommendations, or a
cross-product marketplace.

## Non-Goals

Do not start with GUI parity. Do not make WinForms, Python tooling, or any
frontend the backend. Do not put Mod Portal logic in Universal Launcher. Do not make
Universal Launcher huge before Factorio proves it. Do not make Universal Setup
huge before Dominium proves it. Do not bundle Factorio binaries, repair Steam
installs, touch Steam Cloud files silently, store Factorio passwords, or make a
single executable the architecture.
