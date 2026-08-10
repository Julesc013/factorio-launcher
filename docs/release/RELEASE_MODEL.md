# Release Model

FacMan releases are product distributions. A release is not a global install of
Universal Launcher or Universal Setup, and it is not a single executable that
pretends to be every frontend.

Every FacMan distribution must be self-contained:

```text
FacMan product package
├─ FacMan frontend executables
├─ Factorio binding
├─ pinned Universal Launcher runtime
├─ pinned Universal Setup runtime or helper
├─ contracts/
├─ content/
├─ release/
├─ docs/
└─ licenses/
```

Before packaging, one reviewed v2 product model is compiled into one immutable
resolution per target. The canonical resolution, not a package script, selects
components, entrypoints, paths, ownership, authority, compatibility, claims,
and qualification obligations. See
[Composition Compiler](COMPOSITION_COMPILER.md).

The release contract preserves three repository boundaries and two provider
layers inside each universal repository:

- FacMan owns Factorio-specific binding, frontends, content, and product
  packaging.
- Universal Launcher owns the ULK semantic kernel for runnable-product state;
  ULU is its capability-selected host/provider layer for process, session,
  persistence, transport, and platform effects.
- Universal Setup owns the USK semantic kernel for installed-software state;
  USU is its capability-selected host/provider layer for source, archive,
  filesystem, transaction, elevation, and platform effects.
- FacMan owns the resolved product graph, Factorio meaning, compatibility,
  policy, presentation, acquisition decisions, release selection, and exact
  provider identities.

## Hard Rules

- Product packages bundle pinned Universal Launcher and Universal Setup
  components.
- No global universal runtime is required to run a FacMan package.
- FacMan does not mutate its own install directory directly.
- Update, repair, uninstall, and rollback are delegated to Universal Setup.
- CLI, TUI, daemon, and GUI entrypoints remain separate executables.
- Package formats can vary by OS, but install and update semantics must remain
  the same.
- Package adapters may wrap the canonical staged image and add only their
  declared integration overlay; they cannot redefine product payload or law.
- Every first-family CLI package embeds its exact ten-record resolution under
  `manifest/resolution/`.

## Release Identity

Each release records separate compatibility surfaces:

```text
FacMan product version
Factorio binding version
Universal Launcher version
Universal Setup version
contract and schema versions
ABI versions
platform package revision
build metadata
```

These values originate in `release/index/version.v2.toml`, the other reviewed
v2 model inputs, and exact provider/toolchain locks. Legacy build and profile
files are compatibility projections checked for drift.

## First Release Direction

The current C1 route remains an internal alpha foundation. It is not renamed
to, and does not by itself satisfy, the first public beta. The intended first
public release is finite and Windows-first:

```text
0.1.0-alpha.N  autonomous immutable engineering candidates
0.1.0-beta.N   human-tested Windows product candidates
0.1.0-rc.N     frozen release candidates
0.1.0          public beta: Windows 10/11 x64 CLI + TUI + WinForms
```

Every capability admitted to the `0.1.0` matrix must work through the shared
semantic backend in all four admitted projections, including positive,
refusal, fault, recovery, packaged, clean-machine, accessibility, and support
evidence. Unadmitted features are explicit exclusions, not hidden blockers.

The longer train adds AppKit, GTK, and Qt 6 Widgets product lanes before a measurable
`1.0.0` freeze. Different platform profiles may select different binaries,
runtime closures, and host providers while preserving the same product and
command semantics. One modern binary is not expected to run unchanged on
legacy Windows, macOS, and Linux floors.

The exact release classes, canonical-plan milestones, capability matrix,
autonomous delegation ceiling, and withdrawal law live in:

- `release/index/version_train.v1.toml`;
- `release/index/plan.v1.toml`;
- `release/index/capability_frontend_matrix.v1.toml`;
- `release/index/autonomy_policy.v1.toml`;
- `release/ledger/` append-only record types.

These contracts remain non-authorizing. The first package proof still proves
reproducible layout, contracts, and refusal semantics—not signing,
notarization, public distribution, or production lifecycle maturity.
