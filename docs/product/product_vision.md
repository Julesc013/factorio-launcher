# Product Charter

FacMan is an unofficial, native, portable, scriptable, world-centric launcher
and environment manager for Factorio.

Its user promise is:

> Choose a world, press Play, and remain in control of everything that changes.

Its long-term outcome is to make every player-owned Factorio world
understandable, playable, reproducible, repairable, portable, and recoverable
without silently taking ownership of foreign software or data.

The primary persona is a Factorio player who wants multiple safe,
reproducible worlds without learning launcher internals or constructing JSON.

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

The golden journey is:

```text
Find Factorio,
choose or create a world,
review readiness and the advertised isolation guarantee,
press Play,
save and exit,
then relaunch the same world with an explainable last-run result.
```

Advanced instance, install, modset, save, profile, diagnostic, and automation
surfaces remain available through the CLI, TUI, and command explorer.

## Execution Guarantees

FacMan must never describe all execution as simply "isolated." It supports two
separate product modes, each with its own evidence gate:

- **Instance-isolated:** FacMan-owned instance data is isolated. Enumerated
  Steam or platform-owned state may change only after explicit disclosure and
  acknowledgement. This mode cannot carry the hermetic claim.
- **Hermetic standalone:** no persistent change may occur outside the
  authorised FacMan workspace. Any external change fails the claim.

Both modes are accepted product designs and currently unproven. Automated
fake-process tests can validate the supervisor; only revision-pinned real
Factorio evidence and human review can promote either execution claim.

## Product Rules

- No bundled Factorio binaries.
- No ownership bypass.
- No official branding assets.
- No undisclosed writes to external Factorio, Steam, or platform state.
- No global mod folder swapping.
- Dry-run launch plans before execution.
- Managed install operations go through Universal Setup.

## v1 Shape

v1 is useful when it has one proven real Play route, read-only install
discovery, ownership classification, multiple isolated worlds, portable world
specifications with explicit local rebinding, computed readiness, dry-run
launch and preparation plans, safe launch execution, local content
preparation, modset lockfiles, save backup, rollback and recovery, managed
standalone lifecycle, diagnostics, signed primary packages, a task-oriented
GUI, complete CLI coverage, and a documented stable workflow-contract subset.

v1 should not require every GUI toolkit, Steam-aware Play when standalone Play
is proven, full Mod Portal automation, a headless server manager, remote
support, AI recommendations, cloud synchronization, or a cross-product
marketplace.

## Non-Goals

Do not start with GUI parity. Do not make WinForms, Python tooling, or any
frontend the backend. Do not put Mod Portal logic in Universal Launcher. Do not make
Universal Launcher huge before Factorio proves it. Do not make Universal Setup
huge before Dominium proves it. Do not bundle Factorio binaries, repair Steam
installs, manipulate Steam state, touch Steam Cloud files silently, store
Factorio passwords, or make a single executable the architecture. Do not add a
dynamic in-process plugin framework, daemon, or AI action layer before a real
consumer earns the complexity.
