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

The release contract preserves three boundaries:

- FacMan owns Factorio-specific binding, frontends, content, and product
  packaging.
- Universal Launcher owns product, instance, profile, artifact-set, and launch
  orchestration contracts.
- Universal Setup owns install, verify, repair, uninstall, update, rollback,
  and audit mutation.

## Hard Rules

- Product packages bundle pinned Universal Launcher and Universal Setup
  components.
- No global universal runtime is required to run a FacMan package.
- FacMan does not mutate its own install directory directly.
- Update, repair, uninstall, and rollback are delegated to Universal Setup.
- CLI, TUI, daemon, and GUI entrypoints remain separate executables.
- Package formats can vary by OS, but install and update semantics must remain
  the same.

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

These values are recorded by `release/index/build_manifest.v1.toml` and
`release/index/dependency_lock.v1.toml` until real release artifact manifests
are produced by the build pipeline.

## First Release Direction

The first real release lane remains proof-oriented:

```text
0.1.0-dev
portable archive first
native GUI shells call doctor/package verification
no managed Factorio install mutation
no self-update mutation
```

The first package proof is about reproducible layout, contracts, and refusal
semantics. It is not a claim that production installers, signing, notarization,
package-manager channels, or delta updates are implemented.
